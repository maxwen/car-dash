'''
Created on Dec 7, 2011

@author: maxl
'''
import time
from datetime import datetime
from collections import deque

class Log():
    def __init__(self, withPrint):
        self.fileName="debug.log"
        self.logLines=deque("", 100)
        self.withPrint=withPrint
        
    def createTimeStamp(self):
        stamp=datetime.fromtimestamp(time.time())
        return "".join(["%02d:%02d:%02d.%06d"%(stamp.hour, stamp.minute, stamp.second, stamp.microsecond)])

    def addLineToLog(self, line):
        logLine=self.createTimeStamp()+":"+line
        if self.withPrint:
            print(logLine)
        self.logLines.append(logLine)
        
    def writeLogtoFile(self):
        if len(self.logLines)!=0:
            self.logFile=open(self.fileName, 'w')
            for line in self.logLines:
                self.logFile.write(line+"\n")
            self.logFile.close()
    

if __name__ == "__main__":
    c=Log(False)
    c.addLineToLog("foo")
    c.addLineToLog("bar")
    c.writeLogtoFile()
