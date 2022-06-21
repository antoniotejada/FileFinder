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
XXX See https://stackoverflow.com/questions/16872700/sqlite-data-change-notification-callbacks-in-python-or-bash-or-cli
       but https://stackoverflow.com/questions/677028/how-do-i-notify-a-process-of-an-sqlite-database-change-done-in-a-different-proce

"""
import csv
import datetime
import errno
import os
import string
import sys
import time

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *


def line_iterator(f):
    """
    Iterator implemented as a generator that returns a file one line per 
    iteration.

    @param f {file} File to iterate over, line by line (opened in binary or text 
        mode)
    @return Line
    
    """
    while True:
        line = f.readline()
        if (line == ""):
            break
        yield line


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
        
    return "%d %s" % (u/d, unit)


class TableModel(QAbstractTableModel):
    """
    TableModel with filtering, sorting and on-demand display

    The on-demand display is done by
    - returning only filtered_row_count in rowCount()
    - returning True in canFetchMore if loaded_row_count < len(data)
    - updating loaded_row_count and filtered_row_count in fetchMoreRows
    - updating the filtered_rows array with the indices to the loaded rows

    Sorting is done by sorting and resetting the model, this causes UI to be
    disturbed (ie row selection/focusing is lost).

    Filtering is done by resetting the model and skipping filtered out rows as
    rows are fetched, building the filtered to array filtered_rows. This also
    causes the UI to be disturbed.

    It's always the case that

        total_row_count >= loaded_row_count >= filtered_row_count
        total_row_count = len(data)
        filtered_row_count = len(filtered_rows)
        0 <= min(filtered_row_count) <= max(filtered_row_count) < loaded_row_count

    XXX Ideally for virtual/infinite data, would like a different mechanism
        where:

        - rowCount() returns total_row_count. This makes the scroll bar size stable
        - a viewport height worth of rows is fetched as the table is scrolled up
          or down, forgetting the rows before or after those (modulo guardband)
        - 

    """

    dataAppendedUnsorted = pyqtSignal()

    def __init__(self, data, headers):
        super(TableModel, self).__init__()
        self.data = data
        self.headers = headers
        self.filter_words = []
        self.last_sort_section_order = (None, None)
        self.last_append_time = time.time()
        self.batch = []
        self.reset()

    def appendData(self, new_data):
        ## print "appendData"
        self.batch.extend(new_data)
        append_batch_size = 200
        if (((time.time() - self.last_append_time) > 5) or (len(new_data) == 0) or (len(self.batch) > append_batch_size)):
            ##print "appending batch", len(self.batch)

            # Append the data without disturbing the UI, in order to do that 
            # - if not all rows have been loaded (canFetchMore is True), there's
            #   no need to notify of the append since there were more rows but
            #   they were not fetched anyway.
            # - if all the rows have been fetched (canFetchMore is False), then
            #   force a fetchMore of the usual count
            # - don't sort the new data (since it would do a model reset) and
            #   just remove the sort indicator

            # XXX This could do a forceful sort (because the sort order doesn't
            #     change) 
            #
            #       self.sort(*self.last_sort_section_order, ignore_redundant = False)
            #
            #     and be done with it, but sort resets the model which causes a
            #     jarring flash, viewport reset and loss of focused and selected
            #     items, which is bad UX

            parent = QModelIndex()
            needs_fetching = not self.canFetchMore(parent)
            self.data.extend(self.batch)

            if (needs_fetching):
                # Data has been appended, load and filter a few more rows
                # starting from the last loaded row (note empirically Qt will
                # fetch more rows on its own after receiving the rowsInserted
                # caused by fetchMore, so we could even just fetch one more row
                # instead of the default ones that fetchMore fetches)
                self.fetchMore(parent)
                
            # The model is now unsorted, notify the view so it can disable the
            # sort indicator
            # XXX Ideally this should sort the batch, insert row by row sorted 
            #     and filtered and advertise via beginInsertRows / endInsertRows
            self.dataAppendedUnsorted.emit()

            self.batch = []
            self.last_append_time = time.time()
            

    def appendDataSorted(self, new_data):
        """
        XXX Work in progress
        """
        assert False, "Work in progess"
        print "appendDataSorted", len(new_data)
        self.batch.extend(new_data)
        if (((time.time() - self.last_append_time) > 10) or 
            ((len(new_data) == 0) and (len(self.batch) > 0))
            ):
            print "processing batch", len(self.batch)
            
            #self.data.extend(self.batch)
            
            # Need to sort the new data (do it forcefully since the sort order is
            # the same), will also invalidate the model and the view
            # XXX sort resets the model which causes a jarring flash, should sort
            #     the batch and do sorted insert, emitting rowsInserted/rowsMoved/
            #     rowsRemoved for each (assuming those don't cause flashing)
            # XXX Another option is to have an unsorted state when data is added?
            # self.sort(*self.last_sort_section_order, ignore_redundant = False)
            sort_section, sort_order = self.last_sort_section_order
            reverse = (sort_order == Qt.DescendingOrder)
            self.batch.sort(
                reverse=reverse, 
                # XXX Use itemgetter instead of cmp since it's supposed to be faster?
                cmp=lambda x,y: cmp(x[sort_section], y[sort_section])
            )
            # Do a sorted insert in batches
            i_batch = 0
            i_data = 0
            prev_cmp = 0
            i_start = 0
            rev = -1 if reverse else 1
            while (i_batch < len(self.batch)):
                # Find an insertion point for the current batch entry
                # XXX This could use a bisect approach, but standard bisect
                #     can't deal with 2D lists, needs to extract the keys first
                #     and work on that list, which is cumbersome
                if (i_data < len(self.data)):
                    this_cmp = cmp(self.batch[i_batch][sort_section], self.data[i_data][sort_section]) * rev
                else:
                    this_cmp = -1
                if (this_cmp < 0):
                    index = self.createIndex(i_data, 0)
                    # Don't bother advertising unloaded rows
                    if (i_data <= self.loaded_row_count):
                        self.beginInsertRows(index, i_data, i_data)
                    # insert this row
                    self.data.insert(i_data, self.batch[i_batch])
                    if (i_data <= self.loaded_row_count):
                        self.endInsertRows()
                        self.loaded_row_count += 1
                        self.filtered_row_count += 1
                        self.filtered_rows.append(len(self.filtered_rows))

                    i_batch += 1

                i_data += 1

            self.batch = []
            self.last_append_time = time.time()
            

    def data(self, ix, role):
        if (role == Qt.DisplayRole):
            ## print "data", ix.row(), ix.column()
            value = self.data[self.filtered_rows[ix.row()]][ix.column()]
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

    def filteredRowCount(self):
        """
        Number of rows filtered from the loaded count <= loadedRowCount
        """
        return self.filtered_row_count

    def loadedRowCount(self):
        """
        Number of rows on-demand loaded <= totalRowCount
        """
        return self.loaded_row_count

    def totalRowCount(self):
        """
        Total number of rows in data
        """
        return len(self.data)

    def canFetchMore(self, parent):
        ## print "canFetchMore", self.loaded_row_count, len(self.data)
        if (parent.isValid()):
            print "parent is valid"
            return False
        
        return self.loaded_row_count < len(self.data)

    def internalGetFilepath(self, row):
        filename = self.data[row][0]
        dirpath = self.data[row][1]
    
        filepath = os.path.join(dirpath, filename)

        return filepath
        

    def filterMoreRows(self, count):
        """
        This updates loaded_row_count and filtered_row_count:
        - Go through the next count not yet loaded rows and update loaded_row_count
        - Check if they pass the filter and update filtered_row_count
        This will cause canFetchMore
        
        """
        print "filterMoreRows", count
        # Find how many filtered in rows there are
        loaded_row_count = self.loaded_row_count
        filtered_row_count = self.filtered_row_count
        filtered_rows = []
        while ((loaded_row_count < len(self.data)) and 
                ((filtered_row_count - self.filtered_row_count) < count)):
            
            # Note this needs to access the data without any remapping, since
            # it's used to check if this row will be filtered out or not below,
            # and the remapping array filtered_rows won't be setup until it's
            # known this row is not filtered out
            filepath = self.internalGetFilepath(loaded_row_count)
            # Do case-insensitive by default by comparing lowercase
            filepath = filepath.lower()

            # Remove filtered out or dummy "." entries 
            if ((self.data[loaded_row_count][2] != -2) and
                ((len(self.filter_words) == 0) or
                all([filter_word in filepath for filter_word in self.filter_words]))):
                filtered_rows.append(loaded_row_count)
                filtered_row_count += 1

            loaded_row_count += 1

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
            #     Would need some kind of async prefetch and block if the
            #     prefetch fails

        self.loaded_row_count = loaded_row_count
        self.filtered_row_count = filtered_row_count
        self.filtered_rows.extend(filtered_rows)


    def fetchMore(self, parent):
        print "fetchMore", self.loaded_row_count, len(self.data), parent.row(), parent.column()
        if (parent.isValid()):
            print "index is valid"
            return False

        filtered_row_count = self.filtered_row_count

        # Don't use too big of a number since Qt will call fetchMore as many times
        # as necessary and using a big number causes to load an skip filtered out
        # rows that could end up outside of the viewport anyway
        fetch_batch_size = 5
        self.filterMoreRows(fetch_batch_size)

        self.beginInsertRows(parent, filtered_row_count, self.filtered_row_count - 1)
        self.endInsertRows()


    def rowCount(self, index):
        if (index.isValid()):
            print "index is valid"
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
        # XXX This rebuilds the filtered rows from scratch, in the normal case
        #     the filter is typed sequentially and the old filter is a superset
        #     of the new filter (less or shorter words), change it to filter
        #     the already filtered rows

        # Do case-insensitive by default by comparing lowercase
        self.filter_words = filter.lower().split()
        self.beginResetModel()
        # XXX This should try to preserve the focused and selected rows
        self.reset()
        self.endResetModel()

    def sort(self, section, sort_order, ignore_redundant = True):
        print "sort", section, sort_order

        last_sort_section_order = (section, sort_order)
        if (section == -1):
            # This can be -1 if called to disable sorting
            self.last_sort_section_order = last_sort_section_order

        else:
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
            
            if ((not ignore_redundant) or (self.last_sort_section_order != last_sort_section_order)):
                # XXX This sort is case-sensitive, should do lowercase comparison for
                #     string fields?
                print "sorting", len(self.data)
                self.data.sort(
                    reverse=(sort_order == Qt.DescendingOrder), 
                    cmp=lambda x,y: cmp(x[section], y[section])
                )
                self.last_sort_section_order = last_sort_section_order
                print "sorted", len(self.data)
            else:
                print "ignoring redundant sort call"
            
            print "resetting model"

            self.beginResetModel()
            # XXX This should try to preserve the focused and selected rows
            self.reset()
            self.endResetModel()
            print "resetted model"
        
        
class Worker(QObject):
    updated = pyqtSignal(list)
    traversing = pyqtSignal(str)
    finished = pyqtSignal()
    started = pyqtSignal(str)
    
    def get_entries_os(self, dirpath, recurse=True, queue = None):
        ## print "get_entries_os", dirpath
        entries = []

        self.traversing.emit(dirpath)

        for entry in os.listdir(dirpath):
            entry_filepath = os.path.join(dirpath, entry)
            try:
                if (os.path.isdir(entry_filepath)):
                    if (recurse):
                        if (queue is not None):
                            queue.put(entry_filepath)

                        else:
                            self.get_entries_os(entry_filepath)
                else:
                    entry_time = os.path.getmtime(entry_filepath)
                    entry_size = os.path.getsize(entry_filepath)
                    entries.append((entry, dirpath, entry_size, str(datetime.datetime.fromtimestamp(entry_time))))
                    
            except OSError as e:
                print(e)
                # This fails for access errors, too long paths
                #if (e.errno != errno.EACCES):
                #    raise
                
            except Exception as e:
                # This fails for files with bad timestamps
                print entry, e

        self.updated.emit(entries)


    def update_entries(self, entries, first_entry, newsubdirpaths, dirpath, dirpath_was_modified):
        """
        Updates entries in place for a given dirpath (without recursion),
        assumes:
        - files inside the same directory appear alphabetically sorted by
          filename and contiguous one after the other.
        - subdirectories contents appear after all the files in the parent
          directory, but not necessarily immediately after (since that would be
          impossible).

        @param entries {list} List of entries to update, including inserting or
           deleting entries. The entries will be returned alphabetically sorted.

        @param first_entry {int}: First entry to sort in case entries is part of
            a bigger list. No need to provide the last entry since it will be
            found as part of the update and the count returned by this
            function.

        @param dirpath_was_modified {bool}: Optimization flag to prevent
            fetching the directory if not needed: - When False, entries will be
            compared against itself

        @param out newsubdirpaths {list}: List of subdirs in this directory so
            update_entries can be called on each of them.

        @return 

        """
        ## print "update_entries", len(entries), repr(dirpath)
        i_filename = 0
        i_entry = first_entry
        entry_count = 0

        try:
            if (dirpath_was_modified):
                ## print "modified subdir, doing listdir"
                # XXX This fails with long paths on Windows, need to use long
                #     path prefix, see
                #     https://stackoverflow.com/questions/18390341/unable-to-locate-files-with-long-names-on-windows-with-python

                filenames = os.listdir(dirpath)
                # Append a dummy entry
                #
                # This simplifies detecting the case where a file is added to an
                # empty directory. Without the dummy entry would need to queue
                # all directories to be visited in case they had been updated,
                # but then would need to guarantee that whatever queue visiting
                # order is done at the same time the csv entries for that
                # directory, if any (which is not doable and one of the reasons
                # that newsubpaths queue only contains new directories, ie that
                # don't have entries in the csv file).
                #
                # Adding a dummy entry guarantees that a directory will always
                # have at least one entry in the csv, and will be visited in
                # csv order in case it switched from empty to non-empty.
                filenames.append(".")

            else:
                ## print "not modified subdir, reusing entries"
                # If dirpath wasn't modified there were no new or removed files
                # in this dir build the file list from entries (faster,
                # especially when dirpath is a network drive)
                filenames = []
                for entry in entries[i_entry:]:
                    if (entry[1] != dirpath):
                        break
                    filenames.append(entry[0])
                i_entry = first_entry

        except OSError as e:
            if (e.errno == errno.ENOENT):
                # If the directory was deleted, listdir will trigger an
                # exception, remove all entries with dirpath (no need to remove
                # subdirs because update_entries will be called for the subdirs
                # eventually, fail listdir, and get removed)
                ## print "deleted subdir, removing all entries"
                while ((i_entry < len(entries)) and (dirpath == entries[i_entry][1])):
                    entry = entries.pop(i_entry)
                    ## print "removed", repr(entry[0])

                return 0
            else:
                raise
            
        filenames.sort()

        while (True):
            
            filenames_done = (i_filename >= len(filenames))
            entries_done = ((i_entry >= len(entries)) or (entries[i_entry][1] != dirpath))

            if (filenames_done and entries_done):
                break

            if (entries_done):
                # There's no existing entry, create one from dirlist
                comp = -1

            elif (filenames_done):
                # There's no existing filename, this and any later entries have
                # to be removed
                comp = 1

            else:
                comp = cmp(filenames[i_filename], entries[i_entry][0])
                ## print "cmp", repr(filenames[i_filename]), "vs", repr(entries[i_entry][0]), comp
            
            if (comp == 0):
                # Common case when updating, matching entries, leave as is
                # XXX This should check both are files or both are dirs? (or
                #     check same dates)
                # XXX This needs to update the size and date, since those don't
                #     cause modifications of the parent dir date
                ## print "ignoring same entry", repr(entries[i_entry][0])
                i_entry += 1
                i_filename += 1

            elif (comp < 0):
                # Common case when creating new, insert entry from dirlist
                # XXX This needs to be made robust wrt deletions between 
                #     os.listdir and here
                filename = filenames[i_filename]
                entry_filepath = os.path.join(dirpath, filename)
                is_subdir = (filename != ".") and os.path.isdir(entry_filepath)
                entry_size = -1 if is_subdir else -2 if (filename == ".") else os.path.getsize(entry_filepath)
                entry_epochms = int(os.path.getmtime(entry_filepath) * 1000.0)
                entry = (filename, dirpath, entry_size, entry_epochms)
                ## print "adding entry", repr(entry[0])
                
                entries.insert(i_entry, entry)
                entry_count += 1
                i_entry += 1
                i_filename += 1

                if (is_subdir):
                    newsubdirpaths.append(os.path.join(dirpath, filename))

            else:
                # Uncommon update case when entry was deleted, remove
                ## print "removing entry", repr(entries[i_entry][0])
                entries.pop(i_entry)
                entry_count -= 1
            
        return entry_count

    
    def get_entries_qt_dirit(self, dirpath, recurse = True):
        """
        - For entryInfoList it blocks on entryInfoList (not much), next and the
          first fileinfo non fileName() attribute, UI is frozen
        - For QDirIterator it blocks when accessing the first fileinfo
          attribute, UI is frozen
        - For os, it blocks on os.path.getmtime, os.path.getsize but UI is ok
        - For os.stat it blocks on stat probably the same amount (getmtime calls
          os.stat), but UI is ok

        """
        
        print "get_entries_qt_dirit", repr(dirpath)
        self.traversing.emit(dirpath)
        emit_batch_size = 200

        entries = []
        d = QDirIterator(dirpath)
        #d = QDir(dirpath)
        #for fileinfo in d.entryInfoList():
        while (d.next() != ""):
            is_last = not d.hasNext()
            #is_last = (fileinfo == d.entryInfoList()[-1])
            
            #print "filename"
            #if (fileinfo.fileName() not in [".", ".."]):
            entry_filename = d.fileName()
            if (entry_filename not in [".", ".."]):
                #print "fileinfo"
                fileinfo = d.fileInfo()

                # Qt blocks during close for 1 second for each file through vpn
                # and it's done without releasing the GIL, so the UI thread freezes

                # Tag directories with -1 size and spill entries before subdirs are
                # traversed. This helps finding updates when later loading the csv
                
                #print "entry_filepath"
                entry_filepath = os.path.join(dirpath, d.fileName())
                #entry_filepath = os.path.join(dirpath, fileinfo.fileName())

                #print "entry stat"
                s = os.stat(entry_filepath)
                
                #print "entry epoch"
                #entry_epoch = fileinfo.lastModified().toMSecsSinceEpoch()
                #entry_epoch = int(os.path.getmtime(entry_filepath) * 1000.0)
                entry_epoch = int(s.st_mtime * 1000.0)

                #print "entry size"
                #entry_size = -1 if fileinfo.isDir() else fileinfo.size()
                #entry_size = -1 if fileinfo.isDir() else os.path.getsize(entry_filepath)
                entry_size = -1 if fileinfo.isDir() else s.st_size

                #print "entry"
                entry = (entry_filename, dirpath, entry_size, entry_epoch)
                #entry = (fileinfo.fileName(), dirpath, entry_size, entry_epoch)
                entries.append(entry)
                #print "csv writer", repr(entry[0])
                if (self.csv_writer is not None):
                    # Store in utf-8
                    row = (entry[0].encode('utf-8'), entry[1].encode('utf-8'), entry[2], entry[3])
                    self.csv_writer.writerow(row)
                #print "isdir"
                if (fileinfo.isDir()):
                    if (recurse):

                        # QT filePath uses forward slashes, use join instead of filePath
                        self.get_entries_qt_dirit(entry_filepath)

                # Sleep some since this thread starves the UI thread's Python code (UI
                # refreshes on window resize, etc but status bar and table fail to
                # dequeue the signals and update). Note that neither
                # QThread.yieldCurrentThread nor setting IdlePriority are enough).
                #
                # This is probably because both threads try to acquire the GIL but the
                # directory listing thread spins too fast for the UI thread to get a
                # chance to acquire it. This doesn't happen with other non-QT directory
                # listing methods like os.listdir which points to either:
                # - Qt directory listing being very efficient so most of the time is
                #   spent in Python methods with the GIL acquired (Eg os.listdir takes
                #   2x-3x the time QDirIterator takes to list the same directory)
                # - Qt not releasing the GIL properly inside the directory listing
                #   methods
                # Don't sleep too often, harms local traversals with lots of dirs, 
                # but needs to be checked at the file and not at the directory level
                # in case of directories with lots of files.
                
                # Sleeping is not necessary when using os.path functions instead
                # of Qt fileinfo functions
                #if (time.time() - self.last_sleep_time > 0.001):
                #print "sleep"
                #time.sleep(0.1)
                #    self.last_sleep_time = time.time()

            if ((len(entries) > emit_batch_size) or is_last):
                print "emit"
                self.updated.emit(entries)
                entries = []
            #print "next"
  
    def run(self):
        self.last_sleep_time = time.time()
        dirpaths = sys.argv[1].split(",")
        #dirpaths = ["."]
        #dirpaths = ["_out\\test"]
        #entries = []
        for dirpath in dirpaths:
            # Make sure dirpath is unicode so os.dirlist, etc return unicode too
            dirpath = unicode(dirpath)
            # Make the path absolute for good measure, note abspath requires 
            # to do expanduser first or it will fail to abspath ~
            dirpath = os.path.abspath(os.path.expanduser(dirpath))
            # Incoming path may have forward slashes and caps on Windows,
            # normalize 
            # XXX Note normcase cannot be just used on filenames because then
            #     os.listdir after normcase has different order than stored in the csv
            # XXX Python doesn't properly case the drive unit, force to uppercase
            #     See https://stackoverflow.com/questions/3692261/in-python-how-can-i-get-the-correctly-cased-path-for-a-file
            dirpath = os.path.normpath(dirpath)
            d = os.path.splitdrive(dirpath)
            dirpath = d[0].lower() + d[1]
            self.started.emit(dirpath)
            print "fetching", dirpath
            safe_dirpath = dirpath
            # Convert the fullpath into a suitable file name for the csv
            # Note this list is not complete on Windows, but the name comes from
            # a directory path so there's no need to validate non-printable
            # chars or invalid entries (CON, etc). Also, the .csv extension will
            # be added to this name. No need to handle unicode specifically for
            # the same reason (the individual segments come from an existing path)
            
            # XXX May still need to handle too long paths?
            
            # XXX Another option would be to hash or base64 the name, but that
            #     prevents easy debugging
            invalid_chars = [ 
                "%", # Used for escaping
                "/", # Not allowed on Linux
                "<", ">", ":", "\"", "\\", "|", "=", "*", # Not allowed on Windows
                ".", # .csv will be added to the name, prevent multiple extensions
            ]
            for c in invalid_chars:
                safe_dirpath = safe_dirpath.replace(c, "%%%02x" % ord(c))

            out_dir = "_out"
            print "Creating %s directory" % out_dir
            try:
                os.makedirs(out_dir)
            except:
                pass
            storage_filepath = os.path.join(out_dir, safe_dirpath) + ".csv"

            row = None
            storage_file = None
            storage_filetime = 0
            csv_reader = None
            csv_writer = None
            if (os.path.exists(storage_filepath)):
                storage_file = open(storage_filepath, "rb")
                storage_filetime = os.path.getmtime(storage_filepath)
                # CSV uses buffered reads when reading from a file, which
                # prevents from using tell() robustly to rewind and go to a
                # previous row in the file. Wrap the file on a line iterator
                # instead, since CSV will use just a single line buffer in that
                # case. 
                # See https://stackoverflow.com/questions/14879428/python-csv-distorts-tell
                csv_reader = csv.reader(line_iterator(storage_file), dialect=csv.excel)
                try:
                    row = next(csv_reader)
                    assert unicode(row[1], 'utf-8') == dirpath, "%s mismatches %s" % (repr(unicode(row[1], 'utf-8')), repr(dirpath))

                except StopIteration:
                    # Exception can trigger if csv file is empty
                    csv_reader = None


            new_storage_filepath = storage_filepath + ".new"
            new_storage_file = None
            new_storage_filetime = time.time()
            
            entries = []
            subdirpaths = []
            subdirpath = dirpath
            storage_file_row_offset = 0
            next_storage_file_row_offset = 0

            while (True):
                subdirpath_was_modified = False
                # Get from subdirpaths first, read csv entries if empty
                if (len(subdirpaths) > 0):
                    # Note it doesn't matter here subdirpath is popped in
                    # reverse order, since it's a new subdir and not present in
                    # the csv it doesn't need to match the csv order
                    subdirpath = subdirpaths.pop()
                    # Subdirpaths are new dirs, but could come from renaming an
                    # existing dir, in which case the dir date is left untouched
                    # make sure the date is ignored in that case
                    subdirpath_was_modified = True
                    # Note subdirpaths are new subdirs that don't exist in the
                    # csv, no need to fetch entries from the csv
                    
                elif (csv_reader is not None):
                    # Note that in the very first iteration this overwrites the
                    # incoming subdirpath, but they should match
                    subdirpath = unicode(row[1], 'utf-8')

                    # Fetch all entries from the current subdirpath
                    try:
                        storage_file_row_offset = next_storage_file_row_offset
                        while (unicode(row[1], 'utf-8') == subdirpath):
                            entries.append((unicode(row[0], 'utf-8'), unicode(row[1], 'utf-8'), int(row[2]), int(row[3])))
                            next_storage_file_row_offset = storage_file.tell()
                            row = next(csv_reader)

                    except StopIteration:
                        csv_reader = None
                    
                if (subdirpath is None):
                    break

                # Getting the directory date from entries is cumbersome, use
                # the csv file date as a proxy for the directory date

                # XXX This means we don't need to store subdirs in entries?
                # XXX Should store the traversal start time and set the csv file
                #     to that time when the traversal is done.
                # XXX We already have subdirpath mtime somewhere, this is redundant
                # XXX This redundant with update_entries, but having it here
                #     allows skipping writing to the csv file, find a better way?
                try:
                    # subdirpath_was_modified will already be set for new/renamed
                    # subdirpaths
                    subdirpath_was_modified = (
                        subdirpath_was_modified or 
                        (storage_filetime < os.path.getmtime(subdirpath))
                    )
                    ## print "modified test", repr(subdirpath), subdirpath_was_modified, storage_filetime, "<", os.path.getmtime(subdirpath)

                except OSError as e:
                    if (e.errno == errno.ENOENT):
                        # subdirpath or some parent was deleted, update_entries
                        # will delete each entry
                        subdirpath_was_modified = True

                    else:
                        raise

                # Don't open the csv writer until we know entries have been
                # modified
                # XXX Note testing the subdirpath mtime is not robust enough,
                #     will fail to update the csv when only file sizes or attributes
                #     have been modified
                # XXX Verify that the following updates cause a newer parent dir
                #     date
                #     - file/subdir created/deleted
                #     - file/subdir modified (name, size or attributes)
                
                # XXX Looks like only creation/deletion modifies the parent
                #     directory date, renames only modify the parent
                #     See https://stackoverflow.com/questions/1025187/rules-for-date-modified-of-folders-in-windows-explorer
                #     See https://web.archive.org/web/20080219020154/http://support.microsoft.com/kb/299648
                if (subdirpath_was_modified):
                    if (csv_writer is None):
                        new_storage_file = open(new_storage_filepath, "wb")
                        if (csv_reader is not None):
                            # This is the first time writing the csv, copy from
                            # the reader to the writer
                            print "first csv write, copying from offset 0 to", storage_file_row_offset
                            
                            with open(storage_filepath, "rb") as f:
                                chunk_size = 128 * (2 ** 10)
                                size_to_copy = storage_file_row_offset

                                while (size_to_copy > 0):
                                    new_storage_file.write(f.read(min(chunk_size, size_to_copy)))
                                    size_to_copy -= chunk_size

                        csv_writer = csv.writer(new_storage_file, dialect=csv.excel)

                self.update_entries(entries, 0, subdirpaths, subdirpath, subdirpath_was_modified)
                    
                # Write to new file, csv_writer can be none if no modifications
                # have been found yet
                if (csv_writer is not None):
                    for entry in entries:
                        # Store in utf-8
                        csv_writer.writerow(
                            (entry[0].encode('utf-8'), entry[1].encode('utf-8'), entry[2], entry[3])
                        )
                    
                # Emit
                # XXX Batch?
                # XXX Batch sizes are small but the csv reader seems to
                #     leave a lot of memory around compared to the path that
                #     lists the directories directly, on the Raspberry Pi
                # del csv_reader and/or gc.collect() don't seem to help:
                # - 198.5MB / 426.5MB VM Size writing to csv
                # - 411.6MB RSS / 640.5 VM Size reading from csv
                # - 413.4MB RSS / 643.4 MB with del and collect
                self.updated.emit(entries)

                entries = []
                subdirpath = None

            if (storage_file is not None):
                print "Closing old csv"
                storage_file.close()
                csv_reader = None
                
            if (new_storage_file is not None):
                if (storage_file is not None):
                    print "Deleting old csv"
                    if (False):
                        try:
                            os.remove(storage_filepath + ".old")
                        except:
                            pass
                        os.rename(storage_filepath, storage_filepath + ".old" )
                    else:
                        os.remove(storage_filepath)
                print "Closing and renaming new csv to old"
                new_storage_file.close()
                csv_writer = None
                os.utime(new_storage_filepath, (new_storage_filetime, new_storage_filetime))
                # XXX Verify the utime remains after renaming
                os.rename(storage_filepath + ".new", storage_filepath)
                

            # Emit empty element to signal end of this dirpath
            self.updated.emit([])

            #entries.extend(new_entries)
            #print "fetched", len(new_entries), dirpath
        self.finished.emit()
        

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
            filepaths = []
            for ix in self.selectedIndexes():
                # Note for each row there's a selection per column, only copy
                # one filepath per row
                if (ix.column() == 0):
                    filepath = self.model().getFilepath(ix)
                    filepaths.append(filepath)
                    
                    self.filepathCopied.emit(filepath)
            clipboard = qApp.clipboard()
            clipboard.setText(string.join(filepaths, "\n"))

      
class VLine(QFrame):
    # a simple VLine, like the one you get from designer
    # See https://stackoverflow.com/questions/57943862/pyqt5-statusbar-separators
    def __init__(self):
        super(VLine, self).__init__()
        self.setFrameShape(self.VLine|self.Sunken)

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
        search_on_enter = False
        if (search_on_enter):
            combo.lineEdit().returnPressed.connect(self.updateFilter)
        else:
            combo.lineEdit().textEdited.connect(self.updateFilter)
        self.combo = combo
        l.addWidget(combo)

        entries = []

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
        # When data is appended, it's done unsorted, remove the indicator
        model.dataAppendedUnsorted.connect(lambda : table.horizontalHeader().setSortIndicator(-1, Qt.DescendingOrder))
        # When data is appended, the total count has changed and it may not have
        # been updated if the number of filtered rows didn't change (because
        # the new batch was filtered out or because the new batch is not part
        # of the loaded rows)
        model.dataAppendedUnsorted.connect(lambda : self.updateStatusBar())
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
        
        self.worker.updated.connect(model.appendData, connection_type)
        self.worker.traversing.connect(lambda s: self.statusBar().showMessage("%s" % s), connection_type)
        # XXX Setting Idle priority doesn't seem to make any difference to the
        #     UI freezes, docs say in Linux priority is not supported?
        self.thread.start(QThread.IdlePriority)
                
        print "done initialization"

    
    def onRowsInserted(self, index, start, end):
        print "onRowsInserted", index.row(), index.column(), start, end
        if (self.resize_table_to_contents):
            # There should be some rows in the table
            # assert (self.table.model().filteredRowCount() > 0)
            print "resizing for rows", self.table.model().filteredRowCount()
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