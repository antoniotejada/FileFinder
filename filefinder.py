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
                entries.extend(get_entries_qt_dirit(entry.filePath()))

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

    def data(self, ix, role):
        if (role == Qt.DisplayRole):
            return self.data[ix.row()][ix.column()]

    def rowCount(self, ix):
        return len(self.data)

    def columnCount(self, ix):
        return len(self.data[0])

    def headerData(self, section, orientation, role):
        if (role == Qt.DisplayRole):
            if (orientation == Qt.Horizontal):
                return str(self.headers[section])
        return None

    def getFilepath(self, ix):
        filename = ix.sibling(ix.row(), 0).data()
        dirpath = ix.sibling(ix.row(), 1).data()
    
        # os.path.join uses backslash, needs normalizing to forward to match
        # what QDirIterator produces
        filepath = os.path.normpath(os.path.join(dirpath, filename))

        return filepath
        

class SortFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, *args, **kwargs):
        super(SortFilterProxyModel, self).__init__(*args, **kwargs)
        self.filter_words = []

    def setFilter(self, filter):
        # Do case-insensitive by default by comparing lowercase
        self.filter_words = filter.lower().split()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        
        ix = self.sourceModel().createIndex(source_row, 0, source_parent)
        
        # Do case-insensitive by default by comparing lowercase
        filepath = self.sourceModel().getFilepath(ix)
        filepath = filepath.lower()

        return all([filter_word in filepath for filter_word in self.filter_words])

    def getFilepath(self, ix):
        ix = self.mapToSource(ix)
        
        return self.sourceModel().getFilepath(ix)


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
        combo.lineEdit().returnPressed.connect(self.updateFilter)
        self.combo = combo
        l.addWidget(combo)

        assert len(sys.argv) > 1

        dirpaths = sys.argv[1].split(",")
        entries = []
        for dirpath in dirpaths:
            # Make sure dirpath is unicode so os.dirlist, etc return unicode too
            dirpath = unicode(dirpath)
            # Incoming path may have backslashes, normalize since Qt5 will generate
            # with forward slashes
            dirpath = os.path.normpath(dirpath)
            # Make the path absolute for good measure
            dirpath = os.path.abspath(dirpath)
            print "fetching", dirpath
            new_entries = get_entries_qt_dirit(dirpath)
            entries.extend(new_entries)
            print "fetched", len(new_entries), dirpath
        
        model = TableModel(entries, ["Name", "Path", "Size", "Date"])
        proxy = SortFilterProxyModel(self)
        proxy.setSourceModel(model)
        self.proxy = proxy
        self.model = model

        table = MyTableView()
        # Table font is a bit larger than regular, use the same as in the
        # combobox
        font = QFont(table.font().family(), combo.font().pointSize())
        table.setFont(font)
        table.setModel(proxy)
        table.sortByColumn(2, Qt.DescendingOrder)
        table.setSortingEnabled(True)
        table.resizeColumnsToContents()
        table.resizeRowsToContents()
        table.setSelectionBehavior(QTableView.SelectRows)
        # Set the name column to stretch if the wider is larger than the table
        # Note this prevents resizing the name column, but other columns can be
        # resized and the name column will pick up the slack
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.doubleClicked.connect(table.launchWithPreferredApp)
        table.filepathCopied.connect(lambda s: self.statusBar().showMessage("Copied path %s" % s, 2000))
        table.defaultAppLaunched.connect(lambda s: self.statusBar().showMessage("Launched %s" % s, 2000))
        self.table = table

        l.addWidget(table)
        
        self.status_count_widget = QLabel()
        self.statusBar().addPermanentWidget(self.status_count_widget)

        self.updateStatusBar()
        
        print "done initialization"

    
    def updateStatusBar(self):
        ix = QModelIndex()
        self.status_count_widget.setText("%d/%d" % (
            self.proxy.rowCount(ix), self.model.rowCount(ix)
        ))

    def updateFilter(self):
        filter = self.combo.lineEdit().text()
        self.statusBar().showMessage("Filtering...")
        self.proxy.setFilter(filter)
        self.statusBar().clearMessage()
        self.updateStatusBar()

def main():
    app = QApplication(sys.argv)
    ex = MainWindow()
    ex.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()