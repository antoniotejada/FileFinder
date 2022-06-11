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
- Uses PyQt5
- Works on Raspberry Pi 3 with LXDE
- Works on Windows
- Launch associated applications on doubleclick/enter
- Copy full path to clipboard on right click

## Todo
- Filling the table is slow, should use virtual tables
- Filtering is slow, needs indexing
- Sorting is slow, needs indexing
- Fetching files is slow, needs storing directory data to disk and doing periodic smart updates
- More keyboard shortcuts (delete, go to search box, etc)
- Installation instructions/requirements.txt
- Command line help
- Configuration file
- Configuration UI
- Open Everything data files?