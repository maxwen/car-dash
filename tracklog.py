'''
Created on Dec 7, 2011

@author: maxl
'''
import time
import os
import env
from datetime import datetime

class TrackLog():
    def __init__(self, withPrint, logDir=os.path.join(env.getRoot(), "tracks")):
        self.logDir=logDir
        self.withPrint=withPrint
        self.logFile=open(self.getLogFileName(), 'a')
        
    def getLogFileName(self):
        stamp=datetime.fromtimestamp(time.time())
        timeStamp="%04d%02d%02d"%(stamp.year,stamp.month,stamp.day)
        return os.path.join(self.logDir, "track"+timeStamp+".log")

    def createTimeStamp(self):
        stamp=datetime.fromtimestamp(time.time())
        return "".join(["%02d.%02d.%02d.%06d"%(stamp.hour, stamp.minute, stamp.second, stamp.microsecond)])

    def addTrackLogLine(self, lat, lon, track, speed, altitude):
        logLine="%s:%f:%f:%d:%d:%d"%(self.createTimeStamp(), lat, lon, track, speed, altitude)
        if self.withPrint:
            print(logLine)
        self.logFile.write(logLine+"\n")

    def addTrackLogLine2(self, line):
        if self.withPrint:
            print(line)
        self.logFile.write(line+"\n")     
                   
    def removeLogFile(self):
        if os.path.exists(self.getLogFileName()):
            os.remove(self.getLogFileName())
            
    def closeLogFile(self):
        self.logFile.close()
      
