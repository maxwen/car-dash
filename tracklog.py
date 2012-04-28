'''
Created on Dec 7, 2011

@author: maxl
'''
import os
from utils.env import getRoot
from utils.filelog import FileLog

class TrackLog(FileLog):
    def __init__(self, withPrint):
        FileLog.__init__(self, withPrint, os.path.join(getRoot(), "tracks"), "track")
              
