#!/usr/bin/env python2.7
"""
Performance measurements for different directory traversal apis, CPUs, 
network/local paths, single/multi threaded

rpi
local SDCARD


local ethernet
get_entries_qt_dirit_recursive 27.7087981701 17372
get_entries_qt_info 56.7669808865 17372
get_entries_qt_dirit 27.5069220066 17372
get_entries_os 56.084321022 17373
get_entries_stat 53.7686400414 17373
get_entries_stat_2 49.4659678936 17373
get_entries_stat_4 60.2334139347 17373
get_entries_stat_6 60.0455489159 17373
get_entries_stat_8 59.7039439678 17373
get_entries_stat_10 59.342031002 17373

vpn ethernet
get_entries_qt_dirit_recursive 534.382560015 4023
get_entries_qt_info 297.601735115 4023
get_entries_qt_dirit 296.197326899 4023
get_entries_os 299.891775846 4023
get_entries_stat 309.415568113 4023
get_entries_stat_2 3081.61595798 4023


get_entries_qt_info 310.180160999 4023
get_entries_qt_dirit 307.173405886 4023
get_entries_os 304.275593996 4023
get_entries_stat 328.50521493 4023


laptop
local SSD
get_entries_qt_dirit_recursive 3.16199994087 189610
get_entries_qt_info 2.78399991989 189610
get_entries_qt_dirit 2.55200004578 189610
get_entries_os 18.7860000134 201652
get_entries_stat 11.9160001278 201652
get_entries_stat_2 6.97699999809 201652
get_entries_stat_4 6.05500006676 201652
get_entries_stat_6 6.93699979782 201652
get_entries_stat_8 7.25300002098 201652
get_entries_stat_10 7.39699983597 201652


local ethernet
get_entries_qt_dirit_recursive 36.3770000935 17371
get_entries_qt_info 32.2300000191 17371
get_entries_qt_dirit 30.6489999294 17371
get_entries_os 99.2750000954 17373
get_entries_stat 95.3429999352 17373
get_entries_stat_2 64.3190000057 17373
get_entries_stat_4 60.114000082 17373
get_entries_stat_6 59.1069998741 17373
get_entries_stat_8 58.1330001354 17373
get_entries_stat_10 57.3350000381 17373


local wifi
get_entries_qt_info 35.9719998837 17371
get_entries_qt_dirit 36.0939998627 17371
get_entries_os 116.139999866 17373
get_entries_stat 110.357000113 17373
get_entries_stat_2 69.2049999237 17373
get_entries_stat_4 65.3960001469 17373
get_entries_stat_6 65.263999939 17373
get_entries_stat_8 78.5710000992 17373
get_entries_stat_10 69.1430001259 17373

vpn ethernet
get_entries_qt_dirit_recursive 144.111000061 4023
get_entries_qt_info 140.535000086 4023
get_entries_qt_dirit 144.129000187 4023
get_entries_os 143.10800004 4023
get_entries_stat 142.032999992 4023
get_entries_stat_2 76.1400001049 4023
get_entries_stat_4 52.7209999561 4023
get_entries_stat_6 46.1699998379 4023
get_entries_stat_8 42.8550000191 4023
get_entries_stat_10 41.5169999599 4023

vpn wifi
get_entries_qt_dirit_recursive 178.072999954 4023
get_entries_qt_info 149.962999821 4023
get_entries_qt_dirit 146.752000093 4023
get_entries_os 148.997999907 4023
get_entries_stat 152.105999947 4023
get_entries_stat_2 91.2840001583 4023
get_entries_stat_4 55.1920001507 4023
get_entries_stat_6 46.6210000515 4023
get_entries_stat_8 43.8139998913 4023
get_entries_stat_10 42.2720000744 4023


dirit vs. dirit_entries

laptop

local SSD
get_entries_qt_dirit elapsed 2.58800005913 189617
get_entries_qt_dirit_entries elapsed 2.40499997139 189617

local ethernet
get_entries_qt_dirit elapsed 23.1849999428 17377
get_entries_qt_dirit_entries elapsed 22.8410000801 17377

vpn ethernet
get_entries_qt_dirit elapsed 132.136999846 4023
get_entries_qt_dirit_entries elapsed 132.345999956 4023


rpi

local SDCARD
get_entries_qt_dirit elapsed 58.2944161892 180016
get_entries_qt_dirit_entries elapsed 45.5200498104 180016


local ethernet
get_entries_qt_dirit elapsed 26.7698559761 17378
get_entries_qt_dirit_entries elapsed 26.8442850113 17378


vpn ethernet
get_entries_qt_dirit elapsed 295.552345037 4023
get_entries_qt_dirit_entries elapsed 296.728530884 4023


dirit vs. dirit_sleep

laptop

local SDD 
get_entries_os elapsed 21.757999897 201708
get_entries_qt_dirit elapsed 2.39999985695 189624
get_entries_qt_dirit_sleep elapsed 232.022000074 189624 # without backoff
get_entries_qt_dirit_sleep elapsed 2.58099985123 189626 # with 0.1ms backoff

local ethernet
get_entries_os elapsed 97.8519999981 17379
get_entries_qt_dirit elapsed 23.2139999866 17377
get_entries_qt_dirit_sleep elapsed 30.9159998894 17377

vpn ethernet
get_entries_os elapsed 97.8519999981 17379
get_entries_qt_dirit elapsed 23.2139999866 17377
get_entries_qt_dirit_sleep elapsed 30.9159998894 17377

rpi

local SDCARD
get_entries_os elapsed elapsed 56.8725090027 180829 (throws errors when link nesting is too deep)
get_entries_qt_dirit elapsed 41.6171770096 180125
get_entries_qt_dirit_sleep elapsed 44.3681790829 180125



vpn ethernet
get_entries_os elapsed 333.285113096 4023
get_entries_qt_dirit elapsed 311.852577925 4023
get_entries_qt_dirit_sleep elapsed 312.922093868 4023


local ethernet

get_entries_os elapsed 55.9796631336 17379
get_entries_qt_dirit elapsed 28.13712883 17378
get_entries_qt_dirit_sleep elapsed 27.4534029961 17378





"""

import datetime
import os
import Queue
import stat
import sys
import time
import threading
import thread

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

def get_entries_qt_info(dirpath, recurse = True):
    print "get_entries_qt_info", dirpath
    entries = []
    d = QDir(dirpath)
    for entry in d.entryInfoList():
        # XXX NoDotDot filter causes to return empty?
        if (entry.fileName() in [".", ".."]):
            continue
        if (entry.isDir()):
            if (recurse):
                entries.extend(get_entries_qt_info(entry.filePath()))

        else:
            entries.append((entry.fileName(), dirpath, entry.size(), entry.lastModified()))

    return entries


def get_entries_qt_dirit(dirpath, recurse = True):
    ## print "get_entries_qt_dirit", dirpath

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


last_sleep_time = time.time()
def get_entries_qt_dirit_sleep(dirpath, recurse = True):
    global last_sleep_time
    ## print "get_entries_qt_dirit", dirpath

    entries = []
    d = QDirIterator(dirpath)
    while (d.next() != ""):
        if (d.fileName() in [".", ".."]):
            continue
        
        entry = d.fileInfo()
        if (entry.isDir()):
            if (recurse):
                entries.extend(get_entries_qt_dirit_sleep(entry.filePath()))

        else:
            entries.append((entry.fileName(), dirpath, entry.size(), entry.lastModified()))

        if (time.time() - last_sleep_time > 0.1):
            QThread.usleep(1)
            last_sleep_time = time.time()
            
    return entries


def get_entries_qt_dirit_entries(entries, dirpath, recurse = True):
    ## print "get_entries_qt_dirit_entries", dirpath
    d = QDirIterator(dirpath)
    while (d.next() != ""):
        if (d.fileName() in [".", ".."]):
            continue
        
        entry = d.fileInfo()
        if (entry.isDir()):
            if (recurse):
                get_entries_qt_dirit_entries(entries, entry.filePath())

        else:
            entries.append((entry.fileName(), dirpath, entry.size(), entry.lastModified()))
        
    return entries

def get_entries_qt_dirit_recursive(dirpath, recurse = True):
    print "get_entries_qt_dirit_recursive", dirpath
    entries = []
    
    flags = QDirIterator.Subdirectories if recurse else 0
    d = QDirIterator(dirpath, flags)
    while (d.next() != ""):
        if (d.fileName() in [".", ".."]):
            continue
        
        entry = d.fileInfo()
        if (not entry.isDir()):
            entries.append((entry.fileName(), dirpath, entry.size(), entry.lastModified()))
        
    return entries

def get_entries_stat(dirpath, recurse=True, queue = None):
    print "get_entries_stat", dirpath
    entries = []
    
    for entry in os.listdir(dirpath):
        entry_filepath = os.path.join(dirpath, entry)
        try:
            s = os.stat(entry_filepath)
            if (stat.S_ISDIR(s.st_mode)):
                if (recurse):
                    if (queue is not None):
                        queue.put(entry_filepath)

                    else:
                        entries.extend(get_entries_stat(entry_filepath))
            else:
                entry_time = s.st_mtime
                entry_size = s.st_size
                entries.append((entry, dirpath, entry_size, str(datetime.datetime.fromtimestamp(entry_time))))
                
        except OSError as e:
            print(e)
            # This fails for access errors, too long paths
            #if (e.errno != errno.EACCES):
            #    raise

        except Exception as e:
            # This fails for files with bad timestamps
            print entry, e

    return entries

def get_entries_os(dirpath, recurse=True, queue = None):
    #print "get_entries_os", dirpath

    entries = []
    
    for entry in os.listdir(dirpath):
        entry_filepath = os.path.join(dirpath, entry)
        try:
            # Don't recurse links to avoid infinite loops
            # XXX This is too conservative wrt dirit, should check realpaths and
            #     do proper infinite loop finding?
            if (os.path.isdir(entry_filepath)):
                if (recurse and not(os.path.islink(entry_filepath))):
                    if (queue is not None):
                        queue.put(entry_filepath)

                    else:
                        entries.extend(get_entries_os(entry_filepath))
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

    return entries


dirpath = unicode(sys.argv[1])
print repr(dirpath)

print "get_entries_os", 
t = time.time()
g_entries = get_entries_os(dirpath)
print "elapsed", time.time() - t, len(g_entries)
print "get_entries_qt_dirit", 
t = time.time() 
g_entries = get_entries_qt_dirit(dirpath)
print "elapsed", time.time() - t, len(g_entries)
print "get_entries_qt_dirit_sleep", 
t = time.time() 
g_entries = get_entries_qt_dirit_sleep(dirpath)
print "elapsed", time.time() - t, len(g_entries)

sys.exit()
print "get_entries_qt_dirit_entries", 
t = time.time()
g_entries = get_entries_qt_dirit_entries([], dirpath)
print "elapsed", time.time() - t, len(g_entries)
print "get_entries_qt_dirit_recursive", 
t = time.time() 
g_entries = get_entries_qt_dirit_recursive(dirpath)
print "elapsed", time.time() - t, len(g_entries)
print "get_entries_qt_info", 
t = time.time() 
g_entries = get_entries_qt_info(dirpath)
print "elapsed", time.time() - t, len(g_entries)
print "get_entries_stat", 
t = time.time() 
g_entries = get_entries_stat(dirpath)
print "elapsed", time.time() - t, len(g_entries)

def worker(queue):
    print thread.get_ident(), "starting worker"
    while True:
        try:
            print thread.get_ident(), "getting from queue"
            dirpath = queue.get()
            print thread.get_ident(), "got", dirpath
            if (dirpath == ""):
                print thread.get_ident(), "done"
                queue.task_done()
                break
            g_entries.extend(get_entries_stat(dirpath, True, queue))
            print thread.get_ident(), "done with", dirpath
        except Exception as e:
            print e

        queue.task_done()
    print thread.get_ident(), "exiting worker"

for i in xrange(5):
    g_entries = []
    dirpath_queue = Queue.Queue()
    num_threads = 2 * (i + 1)
    print "get_entries_stat_%d" % num_threads, 
    
    for i in range(num_threads):
        t = threading.Thread(target=worker, args=(dirpath_queue,) )
        t.daemon = True
        t.start()

    t = time.time() 
    dirpath_queue.put(dirpath)
    dirpath_queue.join()
    print "elapsed", time.time() - t, len(g_entries)

    for i in range(num_threads):
        dirpath_queue.put("")
