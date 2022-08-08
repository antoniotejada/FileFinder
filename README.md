# FileFinder

Simplistic but cross-platform version of [Everything](https://www.voidtools.com/)

## Screenshots


### Windows 10

#### \windows\system32
![filefinder_win](https://user-images.githubusercontent.com/6446344/173169083-8a026da3-91a8-4024-a697-690355fbd3a6.jpg)

#### \windows\system32 filtering for opengl
![filefinder_win_filtered](https://user-images.githubusercontent.com/6446344/173169086-369313af-d51d-4ffc-be99-fb7b183ad20a.jpg)


### Raspberry Pi LXDE 

#### /etc
![filefinder_rpi](https://user-images.githubusercontent.com/6446344/173169085-efcf3761-d481-43a4-bad4-93387737d468.jpg)

#### /etc filtering for hosts
![filefinder_rpi_filtered](https://user-images.githubusercontent.com/6446344/173169084-8eedf7ea-7673-4ca1-8d0e-80257d043f3c.jpg)

## Running

    filefinder.py [comma separated list of directories to collect]

Eg on Windows, 
    
    filefinder.py \windows\system32

on Linux, 
    
    ./filefinder.py ~/.mozilla,/etc


## Features
- Uses PyQt5, Python 2.7 and sqlite3
- Works on Raspberry Pi 2 with LXDE
- Works on Windows
- On demand row displaying/virtual table for efficency (but note that
  directories are still loaded wholesome at startup, just displayed on demand as
  the table is scrolled to prevent QTableView building startup time)
- Launch associated applications on doubleclick/enter
- Copy all selected paths to clipboard on right click/ctrl+c
- Uses sqlite3 as database, smart updated in the background at app launch

## Todo
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
- Installation instructions/requirements.txt
- Command line help
- Configuration file
- Configuration UI
- Store file-specific metadata (image sizes, video lengths...)
- Open Everything data files?