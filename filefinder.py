#!/usr/bin/env python2.7
"""
filefinder
(c) Antonio Tejada 2022

Simplistic but cross-platform version of Everything https://www.voidtools.com/

XXX Filtering is slow when it forces full db scan on Raspberry Pi, needs sqlite3
    Full Text Search?
XXX Use trees and transitive closure?
    See https://charlesleifer.com/blog/querying-tree-structures-in-sqlite-using-python-and-the-transitive-closure-extension/
XXX Use tree and recursive queries?
    https://www.sqlite.org/lang_with.html#rcex1
    https://stackoverflow.com/questions/38465186/sqlite-recursive-query-to-return-file-path
XXX This could even open Everything files?
XXX Handle filesystem listing errors


XXX Python 2.7 sqlite3 doesn't have FTS compiled in, but accessing through 
    QT5 does have FTS3
XXX QtSql needs 
        apt-get install python-pyqt5.qtsql
    on raspberry pi and has upto FTS5
XXX See https://blog.kapeli.com/sqlite-fts-contains-and-suffix-matches
XXX See FTS5 trigram (note needs 2020 sqlite 3.34.0)
XXX See https://github.com/simonw/sqlite-fts5-trigram
XXX See https://pypi.org/project/sqlitefts/
XXX See https://github.com/hideaki-t/sqlite-fts-python
XXX See https://stackoverflow.com/questions/16872700/sqlite-data-change-notification-callbacks-in-python-or-bash-or-cli
       but https://stackoverflow.com/questions/677028/how-do-i-notify-a-process-of-an-sqlite-database-change-done-in-a-different-proce

"""
import collections
import csv
import datetime
import errno
import logging
import os
import string
import sqlite3
import sys
import time

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

class LineHandler(logging.StreamHandler):
    def __init__(self):
        super(LineHandler, self).__init__()

    def emit(self, record):
        text = record.getMessage()
        messages = text.split('\n')
        indent = ""
        for message in messages:
            r = record
            r.msg = "%s%s" % (indent, message)
            r.args = None
            super(LineHandler, self).emit(r)
            indent = "    " 


def setup_logger(logger):
    """
    Setup the logger with a line break handler
    """
    logging_format = "%(asctime).23s %(levelname)s:%(filename)s(%(lineno)d):[%(thread)d] %(message)s"

    logger_handler = LineHandler()
    logger_handler.setFormatter(logging.Formatter(logging_format))
    logger.addHandler(logger_handler) 

    return logger

def dbg(*args, **kwargs):
    logger.debug(*args, **kwargs)

def info(*args, **kwargs):
    logger.info(*args, **kwargs)

def warn(*args, **kwargs):
    logger.warning(*args, **kwargs)

def error(*args, **kwargs):
    logger.error(*args, **kwargs)

def exc(*args, **kwargs):
    logger.exception(*args, **kwargs)


def launch_with_preferred_app(filepath):
    # pyqt5 on lxde raspbian fails to invoke xdg-open for unknown reasons and
    # falls back to invoking the web browser instead, use xdg-open explicitly on
    # "xcb" platforms (X11) 
    # See https://github.com/qt/qtbase/blob/067b53864112c084587fa9a507eb4bde3d50a6e1/src/gui/platform/unix/qgenericunixservices.cpp#L129
    if (QApplication.platformName() != "xcb"):
        url = QUrl.fromLocalFile(filepath)
        QDesktopServices.openUrl(url)
        
    else:
        # Note there's no splitCommand in this version of Qt5, build the
        # argument list manually
        QProcess.startDetached("xdg-open", [filepath])


def size_to_human_friendly_units(u):
    """
    @return {string} u as a human friendly power of 1024 unit (TB, GB, MB, KB,
            B)
    """
    d = 1
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        new_d = d * (2 ** 10)
        if (u < new_d):
            break
        d = new_d
        
    return "%0.2f %s" % (u * 1.0/d, unit)

database_filepath = os.path.join("_out", "files.db")
##database_filepath = os.path.join("_out", "test.db")

class TableModel(QAbstractTableModel):
    """
    TableModel with filtering, sorting and on-demand display

    The on-demand display is done by
    - returning only loaded_row_count in rowCount()
    - returning True in canFetchMore if loaded_row_count < len(data)
    - updating loaded_row_count in fetchMoreRows

    Sorting is done by regenerating the query with the sort clauses and
    resetting the model, this causes UI to be disturbed (ie row
    selection/focusing is lost).

    Filtering is done by regenerating the query with the filter clauses and
    resetting the model. This also causes the UI to be disturbed.

    It's always the case that

        total_row_count >= loaded_row_count
        total_row_count = len(data)
        0 < loaded_row_count

    XXX Ideally for virtual/infinite data, would like a different mechanism
        where:

        - rowCount() returns total_row_count. This makes the scroll bar size stable
        - a viewport height worth of rows is fetched as the table is scrolled up
          or down, forgetting the rows before or after those (modulo guardband)
        - 

    """

    def __init__(self, data, headers):
        super(TableModel, self).__init__()
        self.data = data
        self.headers = headers
        self.filter_words = []
        self.sort_orders = collections.OrderedDict(
            reversed(((2, Qt.DescendingOrder), (1, Qt.AscendingOrder), (0, Qt.AscendingOrder), (3, Qt.DescendingOrder)))
        )
        
        self.conn = sqlite3.connect(database_filepath)
        self.cursor = None
        
        self.reset()

    def createIndex(self, *args, **kwargs):
        dbg("createIndex %s", [a for a in args])
        return super(TableModel, self).createIndex(*args, **kwargs)

    def index(self, row, col, parent):
        dbg("index %d %d", row, col)
        return super(TableModel, self).index(row, col, parent)
        

    def data(self, ix, role):
        # Data gets called by columns: all visible rows for column 1, all
        # visible rows for column 2, etc
        if (role == Qt.DisplayRole):
            
            # XXX Use a data "window" to minimize memory footprint? instead of
            #     storing all the elements from the beginning to this point (but
            #     requires to redo the query when moving the window to previous
            #     rows)
            row = self.data[ix.row()]
            dbg("data %d %d %d", ix.row(), ix.column(), row[-1])
            value = row[ix.column()]
            if (ix.column() == 2):
                if (value == -1):
                    # Directory
                    value = "-"
                else:
                    # File, convert size into human friendly units
                    value = size_to_human_friendly_units(value)
            elif (ix.column() == 3):
                # Truncate to seconds for display
                value = str(datetime.datetime.fromtimestamp(value/1000))
            return value

    def loadedRowCount(self):
        """
        Number of rows on-demand loaded <= totalRowCount
        """
        return self.loaded_row_count

    def totalRowCount(self):
        """
        Total number of rows in data
        """
        return self.total_row_count

    def canFetchMore(self, parent):
        dbg("canFetchMore %d, %d", self.loaded_row_count, len(self.data))
        if (parent.isValid()):
            dbg("parent is valid")
            return False
        
        return not self.end_of_cursor

    def internalGetFilepath(self, row):
        filename = self.data[row][0]
        dirpath = self.data[row][1]
    
        filepath = os.path.join(dirpath, filename)

        return filepath
        

    def filterMoreRows(self, count):
        """
        Load more rows using the current cursor (with the filter and sort SQL
        query) and update data, loaded_row_count and end_of_cursor
        """
        dbg("filterMoreRows %d", count)
        if (not self.end_of_cursor):
            # XXX This next iterator can take some time (eg when the word is
            #     not found and a full table scan is needed), should send a
            #     message to the view so it can update the status bar
            # XXX Will probably also need to do it in a different thread?
            # XXX Filtering can take some time, ideally would like to 
            #       QApplication.processEvents() 
            #     here, but it causes different errors because processEvents may
            #     cause reentrant calls to fetchMore which were not easy to fix.
            #     (looks like processEvents causes more calls to fetchMore while
            #     still inside fetchMore).
            #     Another option is to move the filtering to a thread and send a
            #     signal when the filtering is done but would probably cause UX
            #     problems (eg user scrolls down, filtering is deferred so it can't
            #     scroll, rows are added, but cursor is not scrolled down)
            #     Would need some kind of async prefetch and block if ever
            #     scrolls ahead of the prefetch
            new_data = self.cursor.fetchmany(count)
            self.loaded_row_count += len(new_data)
            self.data.extend(new_data)
            self.end_of_cursor = (len(new_data) < count)
            
                
    def fetchMore(self, parent):
        dbg("fetchMore %d %d %d %d", self.loaded_row_count, self.totalRowCount(), parent.row(), parent.column())
        if (parent.isValid()):
            warn("index is valid")
            return False

        loaded_row_count = self.loaded_row_count

        # Don't use too big of a number since Qt will call fetchMore as many
        # times as necessary to fill the viewport, and using a big number causes
        # costly skipping for rows that could end up outside of the viewport
        # anyway
        fetch_batch_size = 5
        self.filterMoreRows(fetch_batch_size)

        self.beginInsertRows(parent, loaded_row_count, self.loaded_row_count - 1)
        self.endInsertRows()


    def rowCount(self, index):
        if (index.isValid()):
            dbg("index is valid")
            return 0

        # Returning the currently loaded count causes the vertical scroll bar
        # position to change as new entries are loaded. This is not ideal, would
        # like to return the total count here in order to have a stable vertical
        # scroll bar, but that's not possible with on-demand row loading via
        # canFetchMore/fetchMore. An option would be to move on demand loading
        # to the data() method, but if resizeColumnsToContents() is used, QT
        # will traverse the full rowCount to find the content to resize to
        return self.loaded_row_count

    def columnCount(self, ix):
        return len(self.headers)

    def headerData(self, section, orientation, role):
        if (role == Qt.DisplayRole):
            if (orientation == Qt.Horizontal):
                return str(self.headers[section])
        return None

    def getFilepath(self, ix):
        return self.internalGetFilepath(ix.row())
        
    def reset(self):
        if (self.cursor is not None):
            self.cursor.close()

        self.total_row_count = self.conn.execute("SELECT count(*) FROM files").fetchone()[0]

        # Build the filter clause
        filter_params = []
        filter_clause = ""
        if (len(self.filter_words) > 0):
            filter_clauses = []
            for filter_word in self.filter_words:
                filter_params.append(filter_word)
                # XXX Note like is case-insensitive, may need changing if
                #     case-sensitivity can be set

                # XXX Note an index for path || name can be created but it's
                #     only used for strict equality, not for LIKE, even for
                #     prefix searches

                # XXX Create an index for each sorting combination (or the first
                #     time a new combination is found), makes the worst case
                #     where all files are filtered out quite faster (from a
                #     second on 600K files to ~instantaneous)
                filter_clauses.append("((path || \"" + os.sep + "\" || name) LIKE (\"%\" || ? || \"%\"))")
            filter_clause = " WHERE %s" % string.join(filter_clauses, " AND ")

        # Build the order clause
        order_clause = ""
        sort_sections = ["name", "path", "size", "mtime"]
        order_clauses = []
        for sort_section in reversed(self.sort_orders):
            sort_order = self.sort_orders[sort_section]
            order_clauses.append(" %s%s" % (sort_sections[sort_section],
            "" if (sort_order == Qt.AscendingOrder) else " DESC"))
        order_clause = " ORDER BY%s" % string.join(order_clauses, ",")

        sql_query_string = "SELECT *, rowid FROM files%s%s" % (filter_clause, order_clause)
        info("Filter query %r params %s", sql_query_string, filter_params)
        self.cursor = self.conn.execute(sql_query_string, filter_params)

        self.end_of_cursor = False
        self.data = []

        self.loaded_row_count = 0
        

    def setFilter(self, filter):
        # XXX This rebuilds the query from scratch, in the normal case
        #     the filter is typed sequentially and the old filter is a superset
        #     of the new filter (less or longer words), could store the result
        #     in a table and fetch from that table if the new filter is a subset?

        # Do case-insensitive by default by comparing lowercase
        self.filter_words = filter.lower().split()
        self.beginResetModel()
        # XXX This should try to preserve the focused and selected rows
        self.reset()
        self.endResetModel()

    def sort(self, section, sort_order, ignore_redundant = True):
        info("sort %d %d", section, sort_order)

        if (section == -1):
            # section can be -1 if called to disable sorting
            
            # XXX Disabling sorting was used for the case rows were appended
            #     unsorted in order to not disturb the UI, probably doesn't make
            #     sense anymore with an indexed database.
            self.sort_orders.clear()

        else:
            # When a header is clicked, QT ends up calling sort twice in a row
            # with the same section and sort order, ignore redundant calls
            # (although this is not that important because DB sorting is
            # relatively fast)
            
            # XXX With DB, sorting also rebuilds the filter, and if the filter
            #     causes a full table scan then sorting won't be fast, does it
            #     make sense to store into a temp table and then re-sort the
            #     temp table instead. This will turn any filter change into a
            #     full table scan (bad), but if the new filter string is a
            #     superset of the previous filter string (usual) then only the
            #     temporary table would need to be re-filtered, which not only
            #     would be fast but would also benefit the current (common) worst case 
            #     which is when a filter word is entered with no matches, which 
            #     causes a full table scan.
            
            # Store the sort_orders lower priority first, sorting by different 
            # columns can be done by consecutively calling sort() for each column
            # to be sorted, in priority order (highest priority sorting last)
            if ((not ignore_redundant) or 
                # There's no sorting
                (len(self.sort_orders) == 0) or 
                # This section is not already the highest priority or, if it is,
                # it had a different order
                (self.sort_orders.keys()[-1] != section) or
                (self.sort_orders[section] != sort_order)):

                # Remove and add the sort order so it becomes last in the
                # ordered dict, the sort query constructor will visit them in
                # reverse
                if (section in self.sort_orders):
                    del self.sort_orders[section]
                self.sort_orders[section] = sort_order
                dbg("sorted rows %s", self.totalRowCount())
                dbg("resetting model")

                self.beginResetModel()
                # XXX This should try to preserve the focused and selected rows
                self.reset()
                self.endResetModel()
                dbg("resetted model")
                
            else:
                warn("ignoring redundant sort call")
        

class TableView(QTableView):
    
    filepathCopied = pyqtSignal(str)
    defaultAppLaunched = pyqtSignal(str)

    def __init__(self, *args, **kwargs):
        super(TableView, self).__init__(*args, **kwargs)

        # XXX This interacts in a weird way with the lineedit, when return is
        #     presed on the lineedit, the default application is launched, which is
        #     weird UX-wise, use a keypressEvent instead or consume that one
        #     in the lineEdit?
        self.openAct = QAction('Open', self, shortcut="return", triggered=self.launchSelectedFilepaths)

        # Override the default tableview copy action which only copies the
        # filename, with one that copies the full filepath
        self.copyFilepathsAct = QAction('Copy Filepaths', self, shortcut="ctrl+c", triggered=self.copySelectedFilepaths)
        
        # XXX Adding the action to the TableView here won't be necessary if
        # added to QMainWindow menubar
        self.addAction(self.openAct)
        self.addAction(self.copyFilepathsAct)

    def launchWithPreferredApp(self, ix):
        
        filepath = self.model().getFilepath(ix)
        info("launchWithPreferredApp %r", filepath)
        
        launch_with_preferred_app(filepath)

        self.defaultAppLaunched.emit(filepath)

    def launchSelectedFilepaths(self):
        # XXX Could also do selectedRows(column)?
        for ix in self.selectedIndexes():
            # Note for each row there's a selection per column, only copy
            # one filepath per row
            if (ix.column() == 0):
                self.launchWithPreferredApp(ix)

    def copySelectedFilepaths(self):
        filepaths = []
        # XXX Could also do selectedRows(column)? (but that method doesn't seem
        #     to be available?)
        for ix in self.selectedIndexes():
            # Note for each row there's a selection per column, only copy
            # one filepath per row
            if (ix.column() == 0):
                filepath = self.model().getFilepath(ix)
                filepaths.append(filepath)
                
                self.filepathCopied.emit(filepath)
        clipboard = qApp.clipboard()
        clipboard.setText(string.join(filepaths, "\n"))
        
    def contextMenuEvent(self, event):
        self.menu = QMenu(self)

        self.menu.addAction(self.openAct)
        
        # XXX Provide a way of copying all the filtered elements straight from
        #     the database without having to scroll to the end of the table and
        #     without having to populate the table with them (needs access to
        #     the db from here?)
        self.menu.addAction(self.copyFilepathsAct)

        # XXX Add more actions like copying the selected files, cutting the
        #     selected files, and pasting into the destination row dirpath or
        #     into some directory chosen by dialog box, export selected to csv
        
        self.menu.popup(QCursor.pos())

      
class VLine(QFrame):
    # a simple VLine, like the one you get from designer
    # See https://stackoverflow.com/questions/57943862/pyqt5-statusbar-separators
    def __init__(self):
        super(VLine, self).__init__()
        self.setFrameShape(self.VLine|self.Sunken)

class MainWindow(QMainWindow):
    # XXX Add option to create new window/instance? Allow multiple instances of
    #     the app and move the db update to a different process?
    #     Moving the db update to a different process will also remove the UI
    #     stalls due to the GIL when the db is updating.
    #     see https://stackoverflow.com/questions/26746379/how-to-signal-slots-in-a-gui-from-a-different-process
    # XXX Add server mode
    # XXX Add client mode (for launching apps, a mapping from server local dir
    #     to client remote share will be needed, or the server can serve the
    #     file to a temporary local file, but that won't be good for big files)
    # XXX Add QSettings storage
    # XXX Add configuration dialog box (paths, servers, clients, window sizes)
    def __init__(self, parent = None):
        super(MainWindow, self).__init__(parent)
        self.resize(1000, 500)
        self.setWindowTitle("FileFinder")
        wid = QWidget(self)
        self.setCentralWidget(wid)

        l = QVBoxLayout()
        wid.setLayout(l)

        widd = QWidget(self)
        h = QHBoxLayout()
        widd.setLayout(h)
        h.setContentsMargins(0, 0, 0, 0)

        l.addWidget(widd)

        combo = QComboBox()
        combo.setEditable(True)
        search_on_enter = False
        if (search_on_enter):
            combo.lineEdit().returnPressed.connect(self.updateFilter)

        else:
            combo.lineEdit().textEdited.connect(self.updateFilter)
        self.combo = combo
        h.addWidget(combo, 1)

        # XXX Have a scan/stop scan button?
        if (False):
            button = QPushButton("Scan")
            h.addStretch()
            h.addWidget(button, 0)
            self.scan_button = button

        entries = []

        model = TableModel(entries, ["Name", "Path", "Size", "Date"])
        self.model = model

        table = TableView()
        # Table font is a bit larger than regular, use the same as in the
        # combobox
        font = QFont(table.font().family(), combo.font().pointSize())
        table.setFont(font)
        table.setModel(model)
        # Set the sort indicator first before enabling sorting, so sorting only
        # happens once, at enable time
        table.horizontalHeader().setSortIndicator(2, Qt.DescendingOrder)
        table.horizontalHeader().sortIndicatorChanged.connect(self.sortModel)
        table.setSortingEnabled(True)
        table.setSelectionBehavior(QTableView.SelectRows)
        table.setTabKeyNavigation(False)
        # Flag the table to be resized to content when the first rows are
        # inserted. Resize only at startup, don't mess with the size set by the
        # user after startup
        self.resize_table_to_contents = True
        # Set the name column to stretch if the wider is larger than the table
        # Note this prevents resizing the name column, but other columns can be
        # resized and the name column will pick up the slack
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.doubleClicked.connect(table.launchWithPreferredApp)
        table.filepathCopied.connect(lambda s: self.statusBar().showMessage("Copied path %s" % s, 2000))
        table.defaultAppLaunched.connect(lambda s: self.statusBar().showMessage("Launched %s" % s, 2000))
        model.rowsInserted.connect(self.onRowsInserted)
        self.table = table

        l.addWidget(table)
        
        self.statusBar().addPermanentWidget(VLine())
        self.status_widget = QLabel()
        self.statusBar().addPermanentWidget(self.status_widget)
        self.statusBar().addPermanentWidget(VLine())
        self.status_count_widget = QLabel()
        self.statusBar().addPermanentWidget(self.status_count_widget)
        
        self.updateStatusBar()

        # XXX Looks like there are two ways of doing Qt threads, investigate more:
        #     a) Derive Qthread, reimplement run
        #     b) Create a worker, move (reparent) to the thread and tie many
        #        cleanup signals
        #     c) Use a Python thread
        #
        #     There's some discussion on whether a) is the wrong approach because
        #     the QThread belongs to the current thread, not the started thread.
        #     Also whether a) queues connections or not by default (it's also
        #     said that PyQt5 doesn't queue by default even with the worker
        #     approach anyway).
        #
        #     Some discussions also say that signal and slots or even Qt functions
        #     cannot be used on c)
        #     See https://doc.qt.io/qt-5/qthread.html#details
        #     See https://realpython.com/python-pyqt-qthread/#multithreading-in-pyqt-with-qthread
        #
        #     The worker approach doesn't allow debugging in vscode (but the QThread 
        #     does?), one workaround is to call the run method serially or to add 
        #           import debugpy; debug_this_thread()
        #     https://stackoverflow.com/questions/71834240/how-to-debug-pyqt5-threads-in-visual-studio-code
        #     https://code.visualstudio.com/docs/python/debugging#_troubleshooting
        self.thread = QThread()
        self.worker = Worker()
        
        # Step 4: Move worker to the thread
        self.worker.moveToThread(self.thread)

        # Step 5: Connect signals and slots
        self.thread.started.connect(self.worker.run)
        connection_type = Qt.AutoConnection
        self.worker.started.connect(lambda s: self.status_widget.setText("%s" % s), connection_type)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(lambda : self.status_widget.setText("Idle"), connection_type)
        self.worker.finished.connect(lambda : self.statusBar().clearMessage(), connection_type)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.worker.traversing.connect(lambda s: self.statusBar().showMessage("%s" % s), connection_type)
        # XXX Setting Idle priority doesn't seem to make any difference to the
        #     UI freezes, docs say in Linux priority is not supported?
        self.thread.start(QThread.IdlePriority)
                
        info("done initialization")

    
    def onRowsInserted(self, index, start, end):
        dbg("onRowsInserted %d %d %d %d", index.row(), index.column(), start, end)
        if (self.resize_table_to_contents):
            # There should be some rows in the table
            # assert (self.table.model().filteredRowCount() > 0)
            info("resizing for rows %d", self.table.model().loadedRowCount())
            self.table.resizeColumnsToContents()
            self.table.resizeRowsToContents()
            self.resize_table_to_contents = False
        self.updateStatusBar()

    def sortModel(self, section, sort_order):
        # XXX This could preserve the selection and focus by saving before sort
        #     and restoring aftersort?
        self.statusBar().showMessage("Sorting...")
        self.model.sort(section, sort_order)
        self.statusBar().clearMessage()
        
    def updateStatusBar(self):
        # Display a "?" indicator if there are still rows to load
        c = "" if self.model.end_of_cursor else "?"
        self.status_count_widget.setText("%d%s/%d" % (
            self.model.loadedRowCount(), 
            c,
            self.model.totalRowCount()
        ))

    def updateFilter(self):
        filter = self.combo.lineEdit().text()
        
        self.statusBar().showMessage("Filtering...")
        self.model.setFilter(filter)
        self.statusBar().clearMessage()
        self.updateStatusBar()


class Worker(QObject):
    traversing = pyqtSignal(str)
    finished = pyqtSignal()
    started = pyqtSignal(str)

    def update_db_subdir(self, conn, read_cursor, subdirpath, row):
        """
        SQLite Important isolation behavior:

        "Changes made in one database connection are invisible to all other
        database connections prior to commit."

        "A query sees all changes that are completed on the same database
        connection prior to the start of the query, regardless of whether or not
        those changes have been committed."

        "If changes occur on the same database connection after a query starts
        running but before the query completes, then the query might return a
        changed row more than once, or it might return a row that was previously
        deleted."

        "If an application issues a SELECT statement on a single table like
        "SELECT rowid, * FROM table WHERE ..." ... "it is safe for the
        application to delete the current row or any prior row using "DELETE
        FROM table WHERE rowid=?""

        "Within a single database connection X, a SELECT statement always sees
        all changes to the database that are completed prior to the start of the
        SELECT statement, whether committed or uncommitted"

        "WAL mode permits simultaneous readers and writers. It can do this
        because changes do not overwrite the original database file, but rather
        go into the separate write-ahead log file. That means that readers can
        continue to read the old, original, unaltered content from the original
        database file at the same time that the writer is appending to the
        write-ahead log." (this is for diferent connections, the on isolation on
        same connection rule still holds)

        See https://www.sqlite.org/isolation.html

        The current option is for the outer query to use a readonly cursor with
        a different connection (which preserves the original cursor until commit
        happens) and to use WAL mode.

        Using a different connection also requires to defer the commit until the
        whole dirpath (not just the subdirpath) has been updated

        Alternatively, insertions and deletions could be stored in Python lists
        and deferred until the end of the dirpath or some batch size.
        """
        dbg("update_db_subdir %r %s", subdirpath, row)

        # XXX This is missing notifying the view of updates, for now the user
        #     will have to update the filter so the view is refreshed with the 
        #     new DB contents

        # XXX The filesystem access (listdir, getsize, getmtime) should happen
        #     on multiple threads and a single thread should collect those and
        #     update the database, or collect the database updates and send them
        #     to the database writer thread
        
        # XXX db updates should be moved to a different process, they cause UI
        #     stalls when ingesting remote  directories with lots of files.
        
        # This is a hotpath when no updates are found but at least on laptop
        # this emit makes no difference at all even with lots of subdirs
        self.traversing.emit(subdirpath)

        # Get the mtime for this specific path, we could use the mtime for the
        # global dirpath, but that one is not updated in the database until the
        # whole dirpath has been updated, so using this specific path allows fine
        # grain committing and avoiding doing the work again if it's aborted for
        # some reason.
        subdirpath_max_mtime = conn.execute("SELECT mtime FROM files WHERE ((path == ?) AND (name = ?))", 
            [os.path.dirname(subdirpath), os.path.basename(subdirpath)]).fetchone()
        if (subdirpath_max_mtime is None):
            # XXX This should never be none, even the root path is created in
            #     the outer loop (in order for smart updates to work) but some
            #     traversals hit this (maybe some problem with not trapping
            #     exceptions/exit? investigate)
            #
            #     When it's none, trying to set the subdirpath_mtime below
            #     will fail and this subdirpath will always fail to be smart skipped
            #     so this should be unconditionally created here?
            # XXX In addition, this is wrong when the directory was deleted and
            #     leaves this phantom directory with 0 date
            subdirpath_max_mtime = 0
            warn("Missing subdirpath %s from database, recreating now", subdirpath)
            inserted_row = (
                os.path.basename(subdirpath),
                os.path.dirname(subdirpath),
                -1,
                0
            )
            conn.execute("INSERT INTO files VALUES (?, ?, ?, ?)", inserted_row)

        else:
            # Note this could be 0 if this directory was never traversed so the
            # db entry has zero to force the traversal
            subdirpath_max_mtime = subdirpath_max_mtime[0]

        # This triggers an exception if the subdirpath has been removed, in that
        # case the subdirpath was already deleted from the database, but don't
        # early exit since the children still need to be deleted

        # XXX Delete all children by using a single prefix query? (but needs to
        #     redo the outer query or will still be found here again)
        # XXX This time was already recovered somewhere, find where and don't
        #     fetch it?
        try:
            subdirpath_mtime = int(os.path.getmtime(subdirpath) * 1000.0)

        except OSError as e:
            # XXX Missing protecting against:
            #   Linux:
            #   host is down errno 112 (Linux) EHOSTDOWN maybe also EHOSTUNREACH?
            #   Windows
            #   network path not found WindowsError.winerror 53
            # XXX Not clear why this didn't raise on windows one time the host was
            #     down?
            if (e.errno != errno.ENOENT):
                raise
            dbg("Deleting children for subdirpath %r", subdirpath)
            subdirpath_mtime = subdirpath_max_mtime + 1
        
        # XXX Note testing the subdirpath mtime is not robust enough, will fail
        #     to update when only file sizes or attributes have been modified
        # XXX Verify that the following updates cause a newer parent dir
        #     date
        #     - file/subdir created/deleted
        #     - file/subdir modified (name, size or attributes)
        # XXX Looks like only creation/deletion modifies the parent
        #     directory date, renames only modify the parent
        #     See https://stackoverflow.com/questions/1025187/rules-for-date-modified-of-folders-in-windows-explorer
        #     See https://web.archive.org/web/20080219020154/http://support.microsoft.com/kb/299648
        if (subdirpath_mtime > subdirpath_max_mtime):
            try:
                # XXX This fails with long paths on Windows, need to use long
                #     path prefix, see
                #     https://stackoverflow.com/questions/18390341/unable-to-locate-files-with-long-names-on-windows-with-python
                filenames = os.listdir(subdirpath)
                filenames.sort()

            except OSError as e:
                if (e.errno != errno.ENOENT):
                    raise
                filenames = []

            i_filename = 0
            refresh_read_cursor = False
            while (True):

                done_with_filenames = (i_filename >= len(filenames))
                done_with_rows = ((row is None) or (row[1] != subdirpath))

                if (done_with_filenames and done_with_rows):
                    break
                
                if (done_with_filenames):
                    # done with filenames, the remaining rows with the same subdirpath
                    # have been deleted
                    comp = 1

                elif (done_with_rows):
                    # Done with the rows, the rest of the filenames need to be
                    # inserted
                    comp = -1

                else:
                    dbg("comp %r vs %r", filenames[i_filename], row[0])
                    comp = cmp(filenames[i_filename], row[0])

                if (comp == 0):
                    # Common case, no update, just increment row and filename Note
                    # that is this is a directory it will be visited by the outer
                    # query so there's no need to push it here, only new directories
                    # that are not in the outer query need to be pushed
                    dbg("same entry %r", filenames[i_filename])
                    i_filename += 1
                    row = read_cursor.fetchone()

                elif (comp < 0):
                    # Common case, new entry
                    dbg("new entry %r", filenames[i_filename])
                    filename = filenames[i_filename]
                    # XXX This needs to guard against file unavailable, etc
                    # XXX This fails for long paths
                    filepath = os.path.join(subdirpath, filename)
                    is_dir = os.path.isdir(filepath)
                    inserted_row = (
                        filename,
                        subdirpath,
                        -1 if is_dir else os.path.getsize(filepath),
                        # Set mtime to zero for new directories so they are not
                        # ignored by the smart update. The directory date will
                        # be properly set when visited
                        0 if is_dir else int(os.path.getmtime(filepath) * 1000.0)
                    )
                    if (is_dir):
                        # Create a dummy entry for this directory so the outer
                        # loop catches it and traverses it. The entry is
                        # irrelevant since it will be found to not exist and
                        # deleted when the directory is visited
                        
                        # Forcing traversal this way has the following
                        # advantages:
                        # - Forces directories to be visited even in the
                        #   presence of aborts
                        # - The entry is removed once the directory is visited
                        # - When a directory is renamed, the children still have
                        #   the old path, but children will be added in the new
                        #   path and deleted from the old
                        # - Won't be skipped by the smart update check because
                        #   the directory has a zero date.

                        # Note that renaming a directory updates the renamed
                        # directory date but not the entries inside, but those
                        # entries still need to be updated recursively so they
                        # store the new path. 
                        # Considering the renamed directory a new directory and
                        # setting the date to zero makes that work through the 
                        # usual flow of detecting deleted and created entries
                        # and skipping the smart update because new directory
                        # dates are set to zero. The old entries will be deleted
                        # recursively here when visited by the outer loop
                        
                        # XXX Should have rowids instead of absolute paths,
                        #     would make the rename case just a re-link and make
                        #     DB a lot smaller, but would the query be slower?
                        #     From tests, a DB with rowids instead of paths is
                        #     38% of the size, the no-results join query is 3x
                        #     slower, the no-results in (select) query is 10%
                        #     slower

                        dummy_row = (
                            ".",
                            filepath,
                            -3,
                            0
                        )
                        dbg("Creating dummy entry %r", dummy_row)
                        conn.execute("INSERT INTO files VALUES (?, ?, ?, ?)", dummy_row)
                        refresh_read_cursor = True
                        
                    conn.execute("INSERT INTO files VALUES (?, ?, ?, ?)", inserted_row)
                    # Commit is done when updating the date the subdirpath being
                    # traversed
                    
                    i_filename += 1
                    
                else:
                    # Uncommon case, deleted entry
                    
                    # XXX This is now in the new ingestion hotpath because of
                    #     creating and deleting dummy entries. Note that this is
                    #     not normally hit for new regular entries because row
                    #     is usually none in case of new ingestion - new subdirs
                    #     shouldn't require to refresh the current cursor but
                    #     anything can happen if there's no isolation? - dummy
                    #     entries could be deleted on a second pass?

                    info("deleted entry %r", row[0])
                    filename = row[0]
                    conn.execute("DELETE FROM files WHERE name = ? AND path = ?", row[0:2])
                    row = read_cursor.fetchone()
                    # Commit is done when updating the date the subdirpath being
                    # traversed


            # Done with this subdirpath, update the subdirpath date
            # XXX Note this is still called if the subdirpath was deleted,
            #     should be harmless but avoid?
            info("updating time for %r to %d max was %d", subdirpath, subdirpath_mtime, subdirpath_max_mtime)
            conn.execute("UPDATE files SET mtime = ? WHERE ((name = ?) AND (path = ?))",
                [subdirpath_mtime, os.path.basename(subdirpath), os.path.dirname(subdirpath)])
            # Commit any changes
            info("committing changes for %r", subdirpath)
            conn.commit()

            if (refresh_read_cursor):
                # Note this query can spill into other dirpaths, the caller has
                # to handle that and stop
                info("refreshing read cursor")
                read_cursor.execute("SELECT * FROM files WHERE (path > ?) ORDER BY path ASC, name ASC", [subdirpath])
                row = read_cursor.fetchone()

        else:
            # This subdirpath wasn't modified, advance the cursor upto the next 
            # subdirpath
            # Subdirectories will be visited as part of the outer query
            dbg("subpath %r not modified, skipping by recreating query", subdirpath)
            # This is a hotpath and skipping by requerying seems to be at least
            # as fast as skipping manually, use the query
            # Note this query can spill into other dirpaths, the caller has
            # to handle that and stop
            read_cursor.execute("SELECT * FROM files WHERE (path > ?) ORDER BY path ASC, name ASC", [subdirpath])
            row = read_cursor.fetchone()

        return row


    def update_db(self, dirpath):
        self.started.emit(dirpath)
            
        conn = sqlite3.connect(database_filepath)
        
        # Make sure dirpath is unicode so os.dirlist, etc return unicode too
        dirpath = unicode(dirpath)
        # Make the path absolute for good measure, note abspath requires to do
        # expanduser first or it will fail to abspath ~
        dirpath = os.path.abspath(os.path.expanduser(dirpath))
        # Incoming path may have forward slashes and caps on Windows, normalize 
        # XXX Note normcase cannot be just used on filenames because then os.listdir
        #     after normcase has different order than stored in the csv
        # XXX Python doesn't properly case the drive unit, force to uppercase
        #     See https://stackoverflow.com/questions/3692261/in-python-how-can-i-get-the-correctly-cased-path-for-a-file
        dirpath = os.path.normpath(dirpath)
        d = os.path.splitdrive(dirpath)
        dirpath = d[0].lower() + d[1]

        # If dirpath is not in the database, create a dummy entry so the read
        # cursor starts with it
        # The update_db_subdir will be called with the dummy path dirpath and
        # update the mtime for that dirpath
        
        # XXX The dummy entry is required because update_db_subdir will take the
        #     basename of the provided subdirpath instead of the subdirpath
        #     itself, so the loop uses row[1] subdir to traverse, it should use
        #     row[1],row[0] and simplify even more? (all this complication
        #     because the initial update_db_subdir assumption was that
        #     directories were not stored in the db so they had to be worked out
        #     from an existing directory content)
        row = conn.execute("SELECT * FROM files WHERE path = ? AND name = ?", 
            [os.path.dirname(dirpath), os.path.basename(dirpath)]).fetchone()
        if (row is None):
            info("inserting new dirpath %r in the database", dirpath)
            inserted_row = (
                os.path.basename(dirpath),
                os.path.dirname(dirpath),
                -2,
                0
            )

            conn.execute("INSERT INTO files VALUES (?, ?, ?, ?)", inserted_row)
            dummy_row = (
                ".",
                dirpath,
                -3,
                0
            )
            info("Creating new dirpath %r dummy entry %r", dirpath, dummy_row)
            conn.execute("INSERT INTO files VALUES (?, ?, ?, ?)", dummy_row)
            
            conn.commit()
        
        # Note that ord("\\") == 92, ord("/") == 47, so this query doesn't guarantee
        # that paths inside the same directory are sorted consecutively, eg one sort
        # order would be 
        #   dir1\dir2A\dir3
        #   dir1\dir2\dir3
        #   dir1\dir2a\dir3
        # where the subdirs of dir1: dir2A, dir2 and dir2a are not visited
        # sequentially 
        read_conn = sqlite3.connect(database_filepath)
        read_cursor = read_conn.execute("SELECT * FROM files WHERE path >= ? ORDER BY path ASC, name ASC", [dirpath])

        row = read_cursor.fetchone()
        while (row is not None):
            subdirpath = row[1]

            # The cursor refresh inside update_db_subdir can spill into other
            # dirpaths when it's done with this dirpath, exit if so
            if (not subdirpath.startswith(dirpath)):
                info("stopping before spilling into %s", subdirpath)
                break

            # XXX update_db_subdir could return a set of inserts, updates, and
            #     deletes so it can be threaded and this thread perform the
            #     database updates
            row = self.update_db_subdir(conn, read_cursor, subdirpath, row)
        
            
        read_cursor.close()

        # export to csv
        export_to_csv = False
        if (export_to_csv):
            csv_filepath = os.path.join("_out", "test.csv")
            csv_old_filepath = os.path.join("_out", "test.old.csv")
            if (os.path.exists(csv_filepath)):
                try:
                    os.remove(csv_old_filepath)
                
                except OSError as e:
                    if (e.errno != errno.ENOENT):
                        raise
                os.rename(csv_filepath, csv_old_filepath)

            with open(csv_filepath, "wb") as f:
                csv_writer = csv.writer(f, dialect=csv.excel)
                cursor = conn.execute("SELECT * FROM files ORDER BY path ASC, name ASC;")
                for row in cursor:
                    row = (row[0].encode('utf-8'), row[1].encode('utf-8'), row[2], row[3])
                    csv_writer.writerow(row)

                cursor.close()
            
        conn.close()
        read_conn.close()
    
    def run(self):
        dirpaths = sys.argv[1].split(",")
        for dirpath in dirpaths:
            self.update_db(dirpath)

        self.finished.emit()

def main():
    create_db = False
    if (create_db):
        try:
            os.remove(database_filepath)
        
        except OSError as e:
            if (e.errno != errno.ENOENT):
                raise

    if (not os.path.exists(database_filepath)):
        create_db = True
    
    if (create_db):
        conn = sqlite3.connect(database_filepath)
        # Even with a single writer and multiple readers, WAL mode is necessary
        # because otherwise sqlite will timeout from the write thread if the read
        # thread leaves a cursor open.
        # See https://stackoverflow.com/questions/53270520/how-to-know-which-process-is-responsible-for-a-operationalerror-database-is-lo
        # See https://www.reddit.com/r/Python/comments/yx20w/the_sqlite_lock_timeout_nightmare/
        # See https://beets.io/blog/sqlite-nightmare.html
        # Note this is a persistent setting so it's only necessary at database
        # creation
        # See https://stackoverflow.com/questions/53270520/how-to-know-which-process-is-responsible-for-a-operationalerror-database-is-lo
        # See https://stackoverflow.com/questions/48729795/how-to-run-sqlite3-database-in-wal-mode-in-flask
        # See https://charlesleifer.com/blog/going-fast-with-sqlite-and-python/
        # See http://devdoc.net/database/sqlite-3.0.7.2/pragma.html
        # See https://stackoverflow.com/questions/63099657/sqlite-pragma-journal-mode-statement-persistence
        
        # XXX Note this leaves a huge 4GB WAL file that doesn't get properly deleted?
        #     See https://sqlite-users.sqlite.narkive.com/Vc9ivjzP/persistence-of-wal-and-shm
        #     See https://sqlite.org/wal.html
        # XXX Sometimes it gets deleted just by closing the python app going to
        #     sqlite3 and doing .tables and exit
        # XXX This also causes a long stall if the removal happens at db open time, 
        #     try to checkpoint manually and showing some progress?
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.executescript("""
            CREATE TABLE files(name TEXT NOT NULL, path TEXT NOT NULL, size INTEGER NOT NULL, mtime EPOCH, PRIMARY KEY (path, name));
            CREATE INDEX idx_files_path ON files(path);
            CREATE INDEX idx_files_name ON files(name);
            CREATE INDEX idx_files_size ON files(size);
            CREATE INDEX idx_files_mtime ON files(mtime);
            CREATE INDEX idx_files_path_name ON files(path, name);
            CREATE INDEX idx_files_path_name_size_mtime ON files(path, name, size, mtime);
            CREATE INDEX idx_files_size_path_name_mtime ON files(size, path, name, mtime);
        """)
        conn.commit()
        conn.close()
    
    
    app = QApplication(sys.argv)
    ex = MainWindow()
    ex.show()
    sys.exit(app.exec_())


logger = logging.getLogger(__name__)
setup_logger(logger)
logger.setLevel(logging.INFO)
##logger.setLevel(logging.DEBUG)

if (__name__ == '__main__'):
    main()