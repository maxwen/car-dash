'''
Created on Dec 7, 2011

@author: maxl
'''
import time
import os
from datetime import datetime

class FileLog():
    def __init__(self, withPrint, logDir, filePrefix):
        self.logDir=logDir
        self.filePrefix=filePrefix
        self.withPrint=withPrint
        if not os.path.exists(os.path.dirname(self.getLogFileName())):
            os.makedirs(os.path.dirname(self.getLogFileName()))
        self.logFile=open(self.getLogFileName(), 'a')
        
    def getLogFileName(self):
        stamp=datetime.fromtimestamp(time.time())
        timeStamp="%04d%02d%02d"%(stamp.year,stamp.month,stamp.day)
        return os.path.join(self.logDir, self.filePrefix+timeStamp+".log")

    def addTrackLogLine(self, line):
        if self.withPrint:
            print(line)
        self.logFile.write(line+"\n")     
                   
    def removeLogFile(self):
        if os.path.exists(self.getLogFileName()):
            os.remove(self.getLogFileName())
            
    def closeLogFile(self):
        self.logFile.close()
      
