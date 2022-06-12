#!/usr/bin/env python2.7
"""
filefinder
(c) Antonio Tejada 2022

Simplistic but cross-platform version of Everything https://www.voidtools.com/

XXX Filling the table is slow, should use virtual tables
XXX Filtering is slow, needs indexing
XXX Sorting is slow, needs indexing
XXX Fetching files is slow, needs caching data and doing smart updates
XXX This could even open Everything files?


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

"""

import os
import sys
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

def get_entries_qt_dirit(dirpath, recurse = True):
    # print "get_entries_qt_dirit", dirpath

    entries = []
    d = QDirIterator(dirpath)
    while (d.next() != ""):
        if (d.fileName() in [".", ".."]):
            continue
        
        entry = d.fileInfo()
        if (entry.isDir()):
            if (recurse):
                # QT uses forward slashes, normalize
                entries.extend(get_entries_qt_dirit(os.path.normpath(entry.filePath())))

        else:
            entries.append((entry.fileName(), dirpath, entry.size(), entry.lastModified()))
        
    return entries


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


class TableModel(QAbstractTableModel):

    def __init__(self, data, headers):
        super(TableModel, self).__init__()
        self.data = data
        self.headers = headers
        self.filter_words = []
        self.last_sort_section_order = (None, None)
        self.reset()
        assert len(self.headers) == len(self.data[0])

    def data(self, ix, role):
        if (role == Qt.DisplayRole):
            ## print "data", ix.row(), ix.column()
            return self.data[self.filtered_rows[ix.row()]][ix.column()]

    def filteredRowCount(self):
        return self.filtered_row_count

    def loadedRowCount(self):
        return self.loaded_row_count

    def totalRowCount(self):
        return len(self.data)

    def canFetchMore(self, index):
        print "canFetchMore", self.loaded_row_count, len(self.data)
        if (index.isValid()):
            return False
        
        return self.loaded_row_count < len(self.data)

    def internalGetFilepath(self, row):
        filename = self.data[row][0]
        dirpath = self.data[row][1]
    
        filepath = os.path.join(dirpath, filename)

        return filepath
        

    def filterMoreRows(self, count):
        # Find how many filtered in rows there are
        loaded_row_count = self.loaded_row_count
        filtered_row_count = self.filtered_row_count
        while ((loaded_row_count < len(self.data)) and 
                ((filtered_row_count - self.filtered_row_count) < count)):
            
            # Note this needs to access the data without any remapping, since
            # it's used to check if this row will be filtered out or not below,
            # and the remapping array filtered_rows won't be setup until it's
            # known this row is not filtered out
            filepath = self.internalGetFilepath(loaded_row_count)
            # Do case-insensitive by default by comparing lowercase
            filepath = filepath.lower()

            if ((len(self.filter_words) == 0) or
                all([filter_word in filepath for filter_word in self.filter_words])):
                self.filtered_rows.append(loaded_row_count)
                filtered_row_count += 1

            loaded_row_count += 1

        self.loaded_row_count = loaded_row_count
        self.filtered_row_count = filtered_row_count


    def fetchMore(self, index):
        print "fetchMore", self.loaded_row_count, len(self.data)
        if (index.isValid()):
            return False

        filtered_row_count = self.filtered_row_count

        self.filterMoreRows(25)

        self.beginInsertRows(index, filtered_row_count, self.filtered_row_count - 1)
        self.endInsertRows()
        

    def rowCount(self, index):
        if (index.isValid()):
            return 0

        assert self.filtered_row_count == len(self.filtered_rows)

        # Returning the currently loaded and filtered count causes the vertical
        # scroll bar position to change as new entries are loaded. This is not
        # ideal, would like to return the total count here in order to have a
        # stable vertical scroll bar, but that's not possible with on-demand row
        # loading via canFetchMore/fetchMore. An option would be to move on
        # demand loading to the data() method, but if resizeColumnsToContents()
        # is used, QT will traverse the full rowCount to find the content to 
        # resize to
        return self.filtered_row_count

    def columnCount(self, ix):
        return len(self.headers)

    def headerData(self, section, orientation, role):
        if (role == Qt.DisplayRole):
            if (orientation == Qt.Horizontal):
                return str(self.headers[section])
        return None

    def getFilepath(self, ix):
        return self.internalGetFilepath(self.filtered_rows[ix.row()])
        
    def reset(self):
        self.loaded_row_count = 0
        self.filtered_row_count = 0
        self.filtered_rows = []

    def setFilter(self, filter):
        # Do case-insensitive by default by comparing lowercase
        self.filter_words = filter.lower().split()
        self.beginResetModel()
        self.reset()
        self.endResetModel()

    def sort(self, section, sort_order):
        print "sort", section, sort_order
        # Note this uses .sort which does stable sorting in place, which has two
        # nice properties:
        # - since the sort is in place, it's memory efficient because it doesn't
        #   replicate the data
        # - since the sort is stable, sorting by multiple fields is possible by
        #   repeatedly sorting in reverse importance order (eg for sorting by
        #   size first and by name when sizes match, call sort(name_section) and
        #   then sort(size_section))
        
        # When a header is clicked, QT ends up calling sort twice in a row with
        # the same section and sort order, ignore redundant calls (although this
        # is not that important because .sort is fast ~O(N) for already sorted
        # lists)
        last_sort_section_order = (section, sort_order)
        if (self.last_sort_section_order != last_sort_section_order):
            # XXX This sort is case-sensitive, should do lowercase comparison for
            #     string fields?
            self.data.sort(
                reverse=(sort_order == Qt.DescendingOrder), 
                cmp=lambda x,y: cmp(x[section], y[section])
            )
            self.last_sort_section_order = last_sort_section_order
        else:
            print "ignoring redundant sort call"
        
        self.beginResetModel()
        self.reset()
        self.endResetModel()
        
    

class MyTableView(QTableView):
    
    filepathCopied = pyqtSignal(str)
    defaultAppLaunched = pyqtSignal(str)

    def __init__(self, *args, **kwargs):
        super(MyTableView, self).__init__(*args, **kwargs)

    def launchWithPreferredApp(self, ix):
        print "launchWithPreferredApp"
        filepath = self.model().getFilepath(ix)
        
        launch_with_preferred_app(filepath)

        self.defaultAppLaunched.emit(filepath)

    def copyFilepath(self, ix):
        print "copyFilepath"
        filepath = self.model().getFilepath(ix)
        clipboard = qApp.clipboard()
        clipboard.setText(filepath)

        self.filepathCopied.emit(filepath)


    def keyPressEvent(self, event):
        key = event.key()

        if ((key == Qt.Key_Return) or (key == Qt.Key_Enter)):
            ix = self.currentIndex()
            self.launchWithPreferredApp(ix)

        else:
            super(MyTableView, self).keyPressEvent(event)

    def mousePressEvent(self, event):
        super(MyTableView, self).mousePressEvent(event)
        if (event.button() == Qt.RightButton):
            # Copy the filepath once the row has been selected by calling super
            # above
            ix = self.currentIndex()
            self.copyFilepath(ix)

      
class MainWindow(QMainWindow):
    def __init__(self, parent = None):
        super(MainWindow, self).__init__(parent)
        self.resize(1000, 500)
        self.setWindowTitle("FileFinder")
        wid = QWidget(self)
        self.setCentralWidget(wid)

        l = QVBoxLayout()
        wid.setLayout(l)

        combo = QComboBox()
        combo.setEditable(True)
        #combo.lineEdit().returnPressed.connect(self.updateFilter)
        combo.lineEdit().textEdited.connect(self.updateFilter)
        self.combo = combo
        l.addWidget(combo)

        #sys.argv = [sys.argv[0], u"\\windows\\system32\\"]
        assert len(sys.argv) > 1

        dirpaths = sys.argv[1].split(",")
        entries = []
        for dirpath in dirpaths:
            # Make sure dirpath is unicode so os.dirlist, etc return unicode too
            dirpath = unicode(dirpath)
            # Make the path absolute for good measure, note abspath requires 
            # to do expanduser first or it will fail to abspath ~
            dirpath = os.path.abspath(os.path.expanduser(dirpath))
            # Incoming path may have forward slashes on Windows, normalize 
            dirpath = os.path.normpath(dirpath)
            print "fetching", dirpath
            new_entries = get_entries_qt_dirit(dirpath)
            entries.extend(new_entries)
            print "fetched", len(new_entries), dirpath
        
        model = TableModel(entries, ["Name", "Path", "Size", "Date"])
        self.model = model

        table = MyTableView()
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
        
        self.status_count_widget = QLabel()
        self.statusBar().addPermanentWidget(self.status_count_widget)

        self.updateStatusBar()
        
        print "done initialization"

    
    def onRowsInserted(self, *args, **kwargs):
        if (self.resize_table_to_contents):
            self.table.resizeColumnsToContents()
            self.table.resizeRowsToContents()
            self.resize_table_to_contents = False
        self.updateStatusBar()

    def sortModel(self, *args, **kwargs):
        self.statusBar().showMessage("Sorting...")
        self.model.sort(*args, **kwargs)
        self.statusBar().clearMessage()
        self.updateStatusBar()

    def updateStatusBar(self):
        # Display a "?" indicator if there are still rows to load
        c = "" if (self.model.loadedRowCount() == self.model.totalRowCount()) else "?"
        self.status_count_widget.setText("%d%s/%d" % (
            self.model.filteredRowCount(), 
            c,
            self.model.totalRowCount()
        ))

    def updateFilter(self):
        filter = self.combo.lineEdit().text()
        self.statusBar().showMessage("Filtering...")
        self.model.setFilter(filter)
        self.statusBar().clearMessage()
        self.updateStatusBar()

def main():
    app = QApplication(sys.argv)
    ex = MainWindow()
    ex.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()