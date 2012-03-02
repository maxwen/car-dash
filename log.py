'''
Created on Dec 7, 2011

@author: maxl
'''
import time
import sys
import signal
import os
import env
from datetime import datetime
from collections import deque

from PyQt4.QtCore import Qt, pyqtSlot
from PyQt4.QtGui import QPlainTextEdit, QCheckBox, QPalette, QApplication, QTabWidget, QSizePolicy, QMainWindow, QPushButton, QWidget, QHBoxLayout, QVBoxLayout, QFormLayout, QLCDNumber, QLabel

class Log():
    def __init__(self, withPrint, logFile=os.path.join(env.getRoot(), "debug.log"), size=100):
        self.fileName=logFile
        self.logLines=deque("", size)
        self.withPrint=withPrint
        
    def createTimeStamp(self):
        stamp=datetime.fromtimestamp(time.time())
        return "".join(["%02d:%02d:%02d.%06d"%(stamp.hour, stamp.minute, stamp.second, stamp.microsecond)])

    def addLineToLog(self, line):
        logLine=self.createTimeStamp()+":"+line
        if self.withPrint:
            print(logLine)
        self.logLines.append(logLine)
        return logLine
        
    def clear(self):
        self.logLines.clear()
        
    def clearLogFile(self):
        if os.path.exists(self.fileName):
            os.remove(self.fileName)
            
    def writeLogtoFile(self):
        if len(self.logLines)!=0:
            self.logFile=open(self.fileName, 'w')
            for line in self.logLines:
                self.logFile.write(line+"\n")
            self.logFile.close()
    

class DebugLogWidget(QWidget):
    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.canMonitor=parent

    def addToWidget(self, vbox):
        self.text=QPlainTextEdit(self.canMonitor)
        self.text.setReadOnly(True)
        vbox.addWidget(self.text)
        
        hbox=QHBoxLayout()
        hbox.setAlignment(Qt.AlignRight|Qt.AlignBottom)
        self.clearButton=QPushButton("Clear", self.canMonitor)
        self.clearButton.clicked.connect(self._clearText)
        hbox.addWidget(self.clearButton)
        
        vbox.addLayout(hbox)
        
    @pyqtSlot()
    def _clearText(self):
        self.text.clear()
        
    def addLineToLog(self, line):
        self.text.appendPlainText(line)
    
class LogWindow(QMainWindow):
    def __init__(self, parent):
        QMainWindow.__init__(self, parent)
        font = self.font()
        font.setPointSize(14)
        self.setFont(font)
        self.log=Log(True, "logTest.log")
        self.initUI()

    def initUI(self):
        mainWidget=QWidget()
        mainWidget.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)

        self.setCentralWidget(mainWidget)
        top=QVBoxLayout(mainWidget)        
        tabs = QTabWidget(self)
        top.addWidget(tabs)
        
        logTab = QWidget()
        debugLogTabLayout=QVBoxLayout(logTab)
        debugLogTabLayout.setAlignment(Qt.AlignLeft|Qt.AlignTop)

        tabs.addTab(logTab, "Log")

        self.debugLogWidget=DebugLogWidget(self)
        self.debugLogWidget.addToWidget(debugLogTabLayout)

        self.testLogButton=QPushButton("Test Log", self)
        self.testLogButton.clicked.connect(self._testLog)
        top.addWidget(self.testLogButton)
        
        self.setGeometry(0, 0, 800, 400)
        self.setWindowTitle('Log Test')
         
        self.show()
        
    def addLineToLog(self, line):
        logLine=self.log.addLineToLog(line)
        self.debugLogWidget.addLineToLog(logLine)
        
    @pyqtSlot()
    def _testLog(self):
        self.addLineToLog("foo")
        
    @pyqtSlot()
    def _cleanup(self):
        self.log.writeLogtoFile()
        
def main(argv): 
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)

    logWindow = LogWindow(None)
    logWindow.initUI()
    app.aboutToQuit.connect(logWindow._cleanup)

    sys.exit(app.exec_())

if __name__ == "__main__":
    main(sys.argv)    

