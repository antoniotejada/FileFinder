# FileFinder

Simplistic but cross-platform version of [Everything](https://www.voidtools.com/)

## Screenshots


### Windows 10

#### \windows\system32
![filefinder_win](https://user-images.githubusercontent.com/6446344/173169083-8a026da3-91a8-4024-a697-690355fbd3a6.jpg)

#### \windows\system32 filtering for opengl
![filefinder_win_filtered](https://user-images.githubusercontent.com/6446344/173169086-369313af-d51d-4ffc-be99-fb7b183ad20a.jpg)

### 32-bit Windows XP

#### \windows\system32

![filefinder_winxp](https://user-images.githubusercontent.com/6446344/185817910-d63c645d-09de-41e6-bb5d-d760d213d583.png)

#### \windows\system32 filtering for opengl

![filefinder_winxp_filtered](https://user-images.githubusercontent.com/6446344/185817968-86a7c174-bbdd-43d8-8708-4aa7bd530964.png)


### Raspberry Pi LXDE 

#### /etc
![filefinder_rpi](https://user-images.githubusercontent.com/6446344/173169085-efcf3761-d481-43a4-bad4-93387737d468.jpg)

#### /etc filtering for hosts
![filefinder_rpi_filtered](https://user-images.githubusercontent.com/6446344/173169084-8eedf7ea-7673-4ca1-8d0e-80257d043f3c.jpg)

## Installing

### 32-bit Raspberry OS

1. Install Python 2.7
1. sudo apt install python-pyqt5 (pip install python-qt5 fails with missing egg-info)
1. sudo apt install python-pyqt5.qtsql (optional for the time being)

### 64-bit Windows 10

1. Install Python 2.7
1. pip install python-qt5 (or follow https://github.com/pyqt/python-qt5)

### 32-bit Windows XP

python-qt5 is a 64-bit Windows project so it doesn't work in 32-bit Windows XP,
fortunately some versions of Anaconda do support PyQt5 and 32-bit Windows XP.

1. Install Anaconda 2.2.0 which is the last Anaconda Python 2.7.x version that
   is known to work on XP (2.3.0 also seems to work, but has missing DLL paths
   at runtime). This will install Python 2.7.9 which has sqlite 3.6.21 which
   doesn't support WAL (needs sqlite 3.7.4)
1. Create a conda python 2.7 environment, this will install Python 2.7.13 in
   that environment, which has sqlite 3.8.11, which has WAL support.
1. conda install PyQt5
1. At this point the application should work, but sqlite 3.8.11 is known to have
   ~0.5s stalls on every commit, so ideally copy over a more recent sqlite3.dll
   to the DLLs path of that environment:
   - The sqlite.org current win32 sqlite 3.38.2 is known to work
   - Lower version numbers may work too (eg sqlite version 3.28.0 that comes with
     Python 2.7.18 is known to work ok on 64-bit Windows 10 or on 32-bit ARM
     Linux)
   

## Running

    filefinder.py [comma separated list of directories to collect] [database filepath]

Eg on Windows, 
    
    filefinder.py \windows\system32 _out\files.db

on Linux, 
    
    ./filefinder.py ~/.mozilla,/etc _out/files.db


## Features
- Uses PyQt5, Python 2.7 and sqlite3
- Works on Raspberry Pi 2 with LXDE
- Works on 64-bit Windows 10, 32-bit Windows XP, probably other combinations
- On demand row displaying/virtual table for efficency (but note that
  directories are still loaded wholesome at startup, just displayed on demand as
  the table is scrolled to prevent QTableView building startup time)
- Launch associated applications on doubleclick/enter
- Copy all selected paths to clipboard on right click/ctrl+c
- Copy/cut selected files to clipboard
- Uses sqlite3 as database, smart updated in the background at app launch

## Requirements
- Python 2.7.13 or higher (sqlite >= 3.7.4 for WAL support)
    - For good commit performance you will need some sqlite version higher than
      3.8.11 (exact version unknown, but sqlite 3.28.0 that comes with Python
      2.7.18 is known to be ok, replacing the sqlite dll with the current one at
      sqlite.org 3.39.2 is also known to work, at least on 32-bit Windows XP)
- PyQt5 

## Todo
- Move paths to its own table instead of replicating them on every file (reduces
  database size)
- Try sqlite3 Full Text Search
- Move db update to a different process (prevent GIL UI stalls)
- Server/Client (allow servers to index local filesystems and expose them
  to clients)
- Infinite loop safeguards (don't follow links, mounted drives, etc)
- Pie charts/statistics
- Bookmarks
- Storing file type
- Complex filters (file type, size, date)
- More keyboard shortcuts (delete, go to search box, etc)
- Detailed installation instructions/requirements.txt
- Command line help
- Configuration file
- Configuration UI
- Store file-specific metadata (image sizes, video lengths...)
- Open Everything data files? (the database format looks private,
  but it could open [.efu files](https://www.voidtools.com/support/everything/file_lists/), use the [SDK](https://www.voidtools.com/support/everything/sdk/) or use the command line tool [es.exe](https://www.voidtools.com/support/everything/command_line_interface/) (note the last two methods wouldn't be cross platform)