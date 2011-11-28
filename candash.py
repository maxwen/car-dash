#!/usr/bin/env python3

import struct
import sys
import time
import os
from datetime import datetime
import fnmatch
from canutils import CANDecoder, CANSocketWorker

from PyQt4.QtCore import Qt, QAbstractTableModel, SIGNAL, pyqtSlot
from PyQt4.QtGui import QSizePolicy, QRadioButton, QColor, QBrush, QWidget, QPushButton, QCheckBox, QLineEdit, QTableView, QTabWidget, QApplication, QHBoxLayout, QVBoxLayout, QFormLayout, QLCDNumber, QLabel, QMainWindow, QPalette, QHeaderView, QAction, QIcon

from collections import deque
from gaugepng import QtPngDialGauge
import signal
        
NUMBER_COL=0
TIME_COL=1
ID_COL=2
SIZE_COL=3
DATA_COL=4

#class CANMonitorUpateUIWorker(QThread):
#    def __init__(self, parent=None): 
#        QThread.__init__(self, parent)
#        self.exiting = False
#        
#    def __del__(self):
#        self.exiting = True
#        self.wait()
#        
#    def setup(self, canMonitor):
#        self.canMonitor=canMonitor
#        self.start()
#            
#    def run(self):
#        while not self.exiting and True:
#            self.canMonitor.updateValuesDisplay()
#            self.msleep(500) 
                
class CANLogViewTableModel(QAbstractTableModel):
    def __init__(self, canMonitor, logBuffer, canIdList, parent=None):
        QAbstractTableModel.__init__(self, parent)
        self.logBuffer=logBuffer
        self.canIdList=canIdList
        self.canMonitor=canMonitor
        self.redBackground=QBrush(QColor(255, 0, 0))
        self.greenBackground=QBrush(QColor(0, 255, 0))
        self.blackForeground=QBrush(QColor(0, 0, 0))
        
    def rowCount(self, parent): 
        return self.logBuffer.maxlen
    
    def columnCount(self, parent): 
        return DATA_COL+1
      
    def data(self, index, role):
#        if not index.isValid():
#            return None
#        elif role == Qt.TextAlignmentRole:
        if role == Qt.TextAlignmentRole:
            if index.column()==NUMBER_COL:
                return Qt.AlignCenter|Qt.AlignVCenter
            elif index.column()==TIME_COL:
                return Qt.AlignCenter|Qt.AlignVCenter
            elif index.column()==ID_COL:
                return Qt.AlignCenter|Qt.AlignVCenter
            elif index.column()==SIZE_COL:
                return Qt.AlignCenter|Qt.AlignVCenter
            elif index.column()==DATA_COL:
                return Qt.AlignLeft|Qt.AlignVCenter
        elif role==Qt.BackgroundColorRole:
            if index.row() >= len(self.logBuffer):
                return None
            if self.canMonitor.canIdIsInKnownList(self.logBuffer[index.row()][ID_COL]): 
                return self.greenBackground
            return self.redBackground
        elif role==Qt.TextColorRole:
            if index.row() >= len(self.logBuffer):
                return None
            return self.blackForeground
        elif role != Qt.DisplayRole:
            return None
        
        if index.row() >= len(self.logBuffer):
            return ""
        if index.column()==NUMBER_COL:
            return self.logBuffer[index.row()][NUMBER_COL]
        elif index.column()==TIME_COL:  
            return self.logBuffer[index.row()][TIME_COL]
        elif index.column()==ID_COL:
            return hex(self.logBuffer[index.row()][ID_COL])
        elif index.column()==SIZE_COL:
            return self.logBuffer[index.row()][SIZE_COL]
        elif index.column()==DATA_COL:
            return "".join(["0x%02X " % x for x in self.logBuffer[index.row()][DATA_COL]])
    
    def headerData(self, col, orientation, role):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                if col==NUMBER_COL:
                    return "Num"
                elif col==TIME_COL:
                    return "Time"
                elif col==ID_COL:
                    return "Id"
                elif col==SIZE_COL:
                    return "Size"
                elif col==DATA_COL:
                    return "Data"
            elif role == Qt.TextAlignmentRole:
                if col==NUMBER_COL:
                    return Qt.AlignCenter
                elif col==TIME_COL:
                    return Qt.AlignCenter
                elif col==ID_COL:
                    return Qt.AlignCenter
                elif col==SIZE_COL:
                    return Qt.AlignCenter
                elif col==DATA_COL:
                    return Qt.AlignLeft
        return None
    
    def update(self):
        self.reset()

class CANMonitor(QMainWindow):
    def __init__(self, app, test):
        super(CANMonitor, self).__init__()
        self.app = app
        self.lcdDict=dict()
        self.logBuffer=deque("", 1000)
        self.logEntryCount=1
        self.maxLogEntryCount=65353
        self.tableUpdateCouter=0
        self.update=False
        self.filter=False
        self.filterValue=""
        self.filterRingIds=True
        self.logFile=None
        self.test=test
        self.logFileName="/tmp/candash.log"
        self.connectEnable=False
        self.replayMode=False
        self.canIdList=[0x353, 0x353, 0x351, 0x351, 0x635, 0x271, 0x371, 0x623, 0x571, 0x3e5]
        self.updateThread=None
        self.initUI()
    
    def clearAllLCD(self):
        for lcdList in self.lcdDict.values():
            for lcd in lcdList:
                if lcd.mode()==QLCDNumber.Bin:
                    lcd.display("00000000")
                else:
                    lcd.display(0)
                    
        self.rpmGauge.setValue(0)
        self.velGauge.setValue(0)
  
    def createLCD(self, mode):
        lcd = QLCDNumber(self)
        lcd.setMode(mode)
        lcd.setMinimumHeight(60)
        lcd.setMinimumWidth(160)
        lcd.setDigitCount(8)
        if mode==QLCDNumber.Bin:
            lcd.display("00000000")
        else:
            lcd.display(0)
        lcd.setSegmentStyle(QLCDNumber.Flat)
        lcd.setAutoFillBackground(True)
        palette = lcd.palette()
        palette.setColor(QPalette.Normal, QPalette.Foreground, Qt.blue)
        palette.setColor(QPalette.Normal, QPalette.Background, Qt.lightGray)
        lcd.setPalette(palette);
        return lcd
    
    def addLCD(self, lcd, canId, subItem):
        if not hex(canId)+":"+subItem in self.lcdDict.keys():
            lcdItemList=list()
            lcdItemList.append(lcd)
            self.lcdDict[hex(canId)+":"+subItem]=lcdItemList
        else:
            self.lcdDict[hex(canId)+":"+subItem].append(lcd)
                
    def createCANIdValueEntry(self, vbox, canId, subId, mode):        
        lcd = self.createLCD(mode)
        
        self.addLCD(lcd, canId, subId)
        
        vbox.addWidget(lcd)          
        
    def createCANIdEntry(self, form, canId, subId, label, mode):
#        hbox = QHBoxLayout()

        lbl = QLabel(self)
        lbl.setMinimumHeight(60)
        font = lbl.font()
        font.setPointSize(20)
        lbl.setFont(font)
        
        if label!=None:
            lbl.setText(label)
#            hbox.addWidget(lbl)
        
        lcd = self.createLCD(mode)
#        hbox.addWidget(lcd)

        form.addRow(lbl, lcd)
        
        self.addLCD(lcd, canId, subId)
        
#        vbox.addLayout(hbox)
        
    def createCANIdEntrySingleLine(self, form, canId, subIdList, label, mode):
#        hbox = QHBoxLayout()

        lbl = QLabel(self)
        lbl.setMinimumHeight(60)
        font = lbl.font()
        font.setPointSize(20)
        lbl.setFont(font)
        if label!=None:
            lbl.setText(label)
#            hbox.addWidget(lbl)

        hbox2=QHBoxLayout();
        
        for i in range(len(subIdList)):
            subId=subIdList[i]
            lcd = self.createLCD(mode)
            hbox2.addWidget(lcd)
            self.addLCD(lcd, canId, subId)

        form.addRow(lbl, hbox2)
#        hbox.addLayout(hbox2)
                        
#        vbox.addLayout(hbox)
        
    def createLogView(self, vbox):
        self.logView=QTableView(self)
        vbox.addWidget(self.logView)
        
        self.logViewModel=CANLogViewTableModel(self, self.logBuffer, self.canIdList)
        self.logView.setModel(self.logViewModel)
        
        header=QHeaderView(Qt.Horizontal, self.logView)
        header.setStretchLastSection(True)
        header.setResizeMode(NUMBER_COL, QHeaderView.Fixed)
        header.setResizeMode(TIME_COL, QHeaderView.Fixed)
        header.setResizeMode(ID_COL, QHeaderView.Fixed)

        self.logView.setHorizontalHeader(header)
        
        self.logView.setColumnWidth(NUMBER_COL, 80)
        self.logView.setColumnWidth(TIME_COL, 150)
        self.logView.setColumnWidth(ID_COL, 80)
        self.logView.setColumnWidth(SIZE_COL, 50)
        
    def initUI(self):  
#        exitAction = QAction(QIcon(), 'Exit', self)
#        exitAction.setShortcut('Ctrl+Q')
#        exitAction.setStatusTip('Exit application')
#        exitAction.triggered.connectTo(self.close)

        self.statusbar=self.statusBar()

#        menubar = self.menuBar()
#        fileMenu = menubar.addMenu('&File')
#        fileMenu.addAction(exitAction)

        toolbar = self.addToolBar('Exit')
#        toolbar.addAction(exitAction)
                
        self.connectedIcon=QIcon("images/network-connect.png")
        self.disconnectIcon=QIcon("images/network-disconnect.png")
        self.connectAction = QAction(self.disconnectIcon , 'Connect', self)
        self.connectAction.triggered.connect(self._connect1)
        self.connectAction.setCheckable(True)
#        self.connectAction.setChecked(True)
        
        toolbar.addAction(self.connectAction)
        
        mainWidget=QWidget()
        mainWidget.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)

        self.setCentralWidget(mainWidget)
        top=QVBoxLayout(mainWidget)

#        self.setCentralWidget(top)
#        self.setLayout(top)
        
        tabs = QTabWidget(self)
        top.addWidget(tabs)
        
        tab1 = QWidget()
        tab2 = QWidget() 
        tab3=QWidget()
        tab4=QWidget()
        tab5=QWidget()
        
        tab1Layout = QFormLayout(tab1)
#        tab1Layout.setLabelAlignment(Qt.AlignCenter)
        tab2Layout = QFormLayout(tab2)
#        tab2Layout.setLabelAlignment(Qt.AlignCenter)
        tab3Layout = QVBoxLayout(tab3)
        tab4Layout = QVBoxLayout(tab4)
        tab5Layout = QFormLayout(tab5)


        tabs.addTab(tab1, "Main")
        tabs.addTab(tab2, "Misc") 
        tabs.addTab(tab3, "Log") 
        tabs.addTab(tab4, "Dash") 
        tabs.addTab(tab5, "Zuheizer") 

        tabs.setCurrentIndex(3)
        

        self.createCANIdEntry(tab1Layout, 0x353, "0", "Drehzahl", QLCDNumber.Dec)
        self.createCANIdEntry(tab1Layout, 0x353, "1", "Öltemperatur", QLCDNumber.Dec)
        self.createCANIdEntry(tab1Layout, 0x351, "0", "Geschwindigkeit", QLCDNumber.Dec)
        self.createCANIdEntry(tab1Layout, 0x351, "1", "Außentemperatur", QLCDNumber.Dec)
        self.createCANIdEntry(tab2Layout, 0x635, "0", "Licht, Klemme 58d", QLCDNumber.Dec)
        self.createCANIdEntry(tab2Layout, 0x271, "0", "Zuendung", QLCDNumber.Dec)
        self.createCANIdEntrySingleLine(tab2Layout, 0x371, ["0", "1"], "Tuerstatus", QLCDNumber.Bin)
        self.createCANIdEntry(tab2Layout, 0x371, "2", "Blinkerstatus", QLCDNumber.Bin)
        self.createCANIdEntrySingleLine(tab1Layout, 0x623, ["0", "1", "2"], "Uhrzeit (Stunden)", QLCDNumber.Dec)        
        self.createCANIdEntry(tab1Layout, 0x571, "0", "Batteriespannung", QLCDNumber.Dec)
        
        self.createCANIdEntry(tab5Layout, 0x3e5, "0", "Zuheizer 1", QLCDNumber.Bin)
        self.createCANIdEntry(tab5Layout, 0x3e5, "1", "Zuheizer 2", QLCDNumber.Bin)
        self.createCANIdEntry(tab5Layout, 0x3e5, "2", "Zuheizer 3", QLCDNumber.Bin)
        self.createCANIdEntry(tab5Layout, 0x3e5, "3", "Zuheizer 4", QLCDNumber.Bin)
        self.createCANIdEntry(tab5Layout, 0x3e5, "4", "Zuheizer 5", QLCDNumber.Bin)
        
        self.createCANIdEntry(tab2Layout, 0x3e5, "5", "Zuheizer", QLCDNumber.Dec)


        self.createLogView(tab3Layout)
        
        hbox = QHBoxLayout()
        tab3Layout.addLayout(hbox)
        hbox.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
                
        self.filterButton=QCheckBox("Filter", self)
        self.filterButton.setToolTip('Enable filter')
        self.filterButton.resize(self.filterButton.sizeHint())
        self.filterButton.clicked.connect(self._enableFilter)
        hbox.addWidget(self.filterButton)
        
        self.filterEdit=QLineEdit(self)
        self.filterEdit.setToolTip('Id Filter')
        self.filterEdit.setDisabled(self.filter==False)
        self.filterEdit.returnPressed.connect(self._applyFilter)
        hbox.addWidget(self.filterEdit)
        
        self.applyFilterButton = QPushButton('Apply', self)
        self.applyFilterButton.setToolTip('Use Id filter')
        self.applyFilterButton.resize(self.applyFilterButton.sizeHint())
        self.applyFilterButton.clicked.connect(self._applyFilter)
        self.applyFilterButton.setDisabled(self.filter==False)
        hbox.addWidget(self.applyFilterButton)
        
        self.filterKnown=QRadioButton("Known", self)
        self.filterKnown.clicked.connect(self._applyFilter)
        self.filterKnown.setDisabled(self.filter==False)
        hbox.addWidget(self.filterKnown)
        
        self.filterUnknown=QRadioButton("Unknown", self)
        self.filterUnknown.clicked.connect(self._applyFilter)
        self.filterUnknown.setDisabled(self.filter==False)
        hbox.addWidget(self.filterUnknown)
        
        self.filterAll=QRadioButton("All", self)
        self.filterAll.clicked.connect(self._applyFilter)
        self.filterAll.setDisabled(self.filter==False)
        self.filterAll.setChecked(True)
        hbox.addWidget(self.filterAll)

        self.filterRingIdsButton=QCheckBox("Filter Ring Ids", self)
        self.filterRingIdsButton.resize(self.filterButton.sizeHint())
        self.filterRingIdsButton.clicked.connect(self._enableFilterRingIds)
        self.filterRingIdsButton.setDisabled(self.filter==False)
        self.filterRingIdsButton.setChecked(self.filterRingIds)
        hbox.addWidget(self.filterRingIdsButton)
        
        hbox2 = QHBoxLayout()
        tab3Layout.addLayout(hbox2)
        hbox2.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        
        self.pauseButton = QPushButton('Pause', self)
        self.pauseButton.setToolTip('Toggle live update of Log')
        self.pauseButton.resize(self.pauseButton.sizeHint())
        self.pauseButton.clicked.connect(self._disableUpdate)
        self.pauseButton.setDisabled(self.update==False or self.replayMode==False)
        hbox2.addWidget(self.pauseButton)
        
        self.continueButton = QPushButton('Start', self)
        self.continueButton.setToolTip('Continue live update of Log')
        self.continueButton.resize(self.continueButton.sizeHint())
        self.continueButton.clicked.connect(self._enableUpdate)
        self.continueButton.setDisabled(self.update==True or self.replayMode==True)
        hbox2.addWidget(self.continueButton)
        
        self.clearTableButton = QPushButton('Clear', self)
        self.clearTableButton.setToolTip('Clear Table')
        self.clearTableButton.resize(self.clearTableButton.sizeHint())
        self.clearTableButton.clicked.connect(self._clearTable)
        hbox2.addWidget(self.clearTableButton)
                
        hbox3 = QHBoxLayout()
        tab3Layout.addLayout(hbox3)
        hbox3.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        
        self.logFileButton=QCheckBox("Log to File", self)
        self.logFileButton.setToolTip('Enable file logging')
        self.logFileButton.resize(self.logFileButton.sizeHint())
        self.logFileButton.setDisabled(self.replayMode==True)
        self.logFileButton.clicked.connect(self._enableLogFile)
        hbox3.addWidget(self.logFileButton)
        
        self.clearLogButton = QPushButton('Clear Log', self)
        self.clearLogButton.resize(self.clearLogButton.sizeHint())
        self.clearLogButton.setDisabled(not self.logFileAvailable() or self.replayMode==True)
        self.clearLogButton.clicked.connect(self._clearLogFile)
        hbox3.addWidget(self.clearLogButton)

        self.replayButton = QPushButton('Replay Log', self)
        self.replayButton.resize(self.replayButton.sizeHint())
        self.replayButton.setDisabled(not self.logFileAvailable() or self.connectEnable==True)
        self.replayButton.clicked.connect(self._startReplayMode)
        hbox3.addWidget(self.replayButton)

        self.stopReplayButton = QPushButton('Stop Replay', self)
        self.stopReplayButton.resize(self.stopReplayButton.sizeHint())
        self.stopReplayButton.setDisabled(self.replayMode==False)
        self.stopReplayButton.clicked.connect(self._stopReplayMode)
        hbox3.addWidget(self.stopReplayButton)
                              
        hbox4 = QHBoxLayout()
        hbox4.setAlignment(Qt.AlignCenter|Qt.AlignBottom)

        tab4Layout.addLayout(hbox4)
        
        vbox = QVBoxLayout()
        hbox4.addLayout(vbox)
#        vbox.setAlignment(Qt.AlignCenter|Qt.AlignHCenter)
        
        self.velGauge=QtPngDialGauge(self, "tacho3", "tacho3.png")
        self.velGauge.setMinimum(20)
        self.velGauge.setMaximum(220)
        self.velGauge.setStartAngle(135)
        self.velGauge.setValue(0)
        self.velGauge.setMaximumSize(320, 320)
        vbox.addWidget(self.velGauge)

        self.createCANIdValueEntry(vbox, 0x351, "0", QLCDNumber.Dec)
        
        vbox1 = QVBoxLayout()
        vbox1.setAlignment(Qt.AlignCenter|Qt.AlignBottom)

        hbox4.addLayout(vbox1)
        self.createCANIdValueEntry(vbox1, 0x353, "1", QLCDNumber.Dec)
        self.createCANIdValueEntry(vbox1, 0x351, "1", QLCDNumber.Dec)
        self.createCANIdValueEntry(vbox1, 0x571, "0", QLCDNumber.Dec)
 
        vbox2 = QVBoxLayout()
        hbox4.addLayout(vbox2)
#        vbox2.setAlignment(Qt.AlignCenter|Qt.AlignHCenter)
        self.rpmGauge=QtPngDialGauge(self, "rpm", "rpm.png")
        self.rpmGauge.setMinimum(0)
        self.rpmGauge.setMaximum(8000)
        self.rpmGauge.setStartAngle(120)
        self.rpmGauge.setValue(0)
        self.rpmGauge.setMaximumSize(320, 320)
        vbox2.addWidget(self.rpmGauge)     
         
        self.createCANIdValueEntry(vbox2, 0x353, "0", QLCDNumber.Dec)

#        self.connectButton = QCheckBox('Connect')
#        self.connectButton.clicked.connect(self._connect2)
#        top.addWidget(self.connectButton)
        
        self.setGeometry(10, 10, 860, 500)
        self.setWindowTitle("candash")
        self.show()
        
        self.canDecoder = CANDecoder(self)

        self.thread = CANSocketWorker()        
        self.connect(self.thread, SIGNAL("updateStatus(QString)"), self.updateStatusBarLabel)
        self.thread.setup(self.app, self, self.canDecoder, self.test)
        
#        self.updateThread=CANMonitorUpateUIWorker()
#        self.updateThread.setup(self)
               
    def getWidget(self, canId, subId):
        try:
            return self.lcdDict[hex(canId)+":"+subId]
        except KeyError:
            return list()
    
    def setValueDashDisplayRPM(self, value):
        if value!=self.rpmGauge.value():
            self.rpmGauge.setValue(value)

    def setValueDashDisplayVel(self, value):
        if value!=self.velGauge.value():
            self.velGauge.setValue(value)
        
    def displayIntValue(self, canId, subId, value, formatString):
        lcdList=self.getWidget(canId, subId)
        for lcdItem in lcdList:
            if lcdItem.intValue()!=int(value):
                lcdItem.display(formatString % value)
                   
    def displayBinValue(self, canId, subId, value, formatString):
        lcdList=self.getWidget(canId, subId)
        for lcdItem in lcdList:
            if lcdItem.intValue()!=int(value):
                lcdItem.display(formatString % value)
                        
    def displayFloatValue(self, canId, subId, value, formatString):
        lcdList=self.getWidget(canId, subId)
        for lcdItem in lcdList:
            if lcdItem.value()!=value:
                lcdItem.display(formatString % value)
                             
#    def updateValuesDisplay(self):
#        self.app.processEvents()
#        print("ui update")
        
    def matchFilter(self, canId, line):
        if self.filter==True:
            idMatch=self.matchIdFilter(canId)
            
            if idMatch==False:
                return False
            
            if self.filterAll.isChecked():
                return idMatch
            
            isKnownId=self.canIdIsInKnownList(canId)
            if self.filterKnown.isChecked():
                return isKnownId==False
            if self.filterUnknown.isChecked():
                return isKnownId==True
        return True
    
    def matchIdFilter(self, canId):     
        if self.filter==True:
            # filter ring ids
            if self.filterRingIds==True:
                if canId>=0x400 and canId <=0x43F:
                    return False
              
            if len(self.filterValue)!=0:
                if not fnmatch.fnmatch(hex(canId), self.filterValue):
                    return False
        
        return True
    
    def addToLogView(self, line):
        if self.update==True:
            tableEntry=[self.logEntryCount, self.createTimeStamp()]
            tableEntry.extend(line[0:])
        
            if self.logFile!=None:
                self.addToLogFile(tableEntry)

            if not self.matchFilter(line[0], line):
                return
        
            self.logBuffer.appendleft(tableEntry)
            self.logEntryCount=self.logEntryCount+1
            if self.logEntryCount==self.maxLogEntryCount:
                self.logEntryCount=1
        
            self.tableUpdateCouter=self.tableUpdateCouter+1
            if self.tableUpdateCouter==10:
                self.logViewModel.update()
                self.tableUpdateCouter=0
                
        
    def createTimeStamp(self):
        stamp=datetime.fromtimestamp(time.time())
        return "".join(["%02d:%02d:%02d.%06d"%(stamp.hour, stamp.minute, stamp.second, stamp.microsecond)])
    
    def dumpLogLine(self, line):
        logLine="%s %s %s"% (line[1], hex(line[2]), line[3])
        dataLine="".join(["0x%02X " % x for x in line[4]])
        return logLine+" "+dataLine   
         
    def addToLogFile(self, line):
        if self.logFile!=None:
            self.logFile.write(self.dumpLogLine(line)+"\n")
        
    def setupLogFile(self, filePath):
        if self.logFile==None:
            self.logFile=open(filePath,"a")
            self.logFile.write("# Log started: "+time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.localtime())+"\n")
            self.logFile.write("# -------------------------------------------------------\n")

    def closeLogFile(self):
        if self.logFile!=None:
            self.logFile.write("# Log stoped: "+time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.localtime())+"\n")
            self.logFile.write("# -------------------------------------------------------\n")
            self.logFile.close()
            self.logFile=None

    def logFileAvailable(self):
        try:
            open(self.logFileName, "r")
            return True
        except IOError:
            return False
    def readLogFile(self):
        try:
            logFileEntries=list()
            readLogFile=open(self.logFileName, "r")
            while True:
                line=readLogFile.readline()
                if not line:
                    break
                if line[0]=="#":
                    continue
                lineParts=line.split(" ")
                strippedLen=len(lineParts)-1
                neededLineParts=lineParts[1:strippedLen]
                addLen=8-len(neededLineParts[2:])
                for _ in range(addLen):
                    neededLineParts.append("%s" % "0x00")
                logFileEntries.append(struct.pack("IIBBBBBBBB", int(neededLineParts[0], 16), int(neededLineParts[1], 10), int(neededLineParts[2], 16),
                   int(neededLineParts[3], 16),int(neededLineParts[4], 16),int(neededLineParts[5], 16),int(neededLineParts[6], 16), 
                   int(neededLineParts[7], 16), int(neededLineParts[8], 16), int(neededLineParts[9], 16)))              
            return logFileEntries
        except IOError:
            return list()
                
    @pyqtSlot()
    def _clearTable(self):
        self.logBuffer.clear();
        self.logEntryCount=1
        self.tableUpdateCouter=0
        self.logViewModel.update()
        
    @pyqtSlot()
    def _disableUpdate(self):
        self.update=False
        self.continueButton.setDisabled(self.update==True and self.replayMode==True)
        self.pauseButton.setDisabled(self.update==False or self.replayMode==False)
            
    @pyqtSlot()
    def _enableUpdate(self):
        self.update=True
        self.logViewModel.update()
        self.continueButton.setDisabled(self.update==True or self.replayMode==True)
        self.pauseButton.setDisabled(self.update==False and self.replayMode==False)
        
    @pyqtSlot()
    def _enableFilter(self):
        self.filter=self.filterButton.isChecked()
            
        self.filterEdit.setDisabled(self.filter==False)
        self.applyFilterButton.setDisabled(self.filter==False)
        self.filterAll.setDisabled(self.filter==False)
        self.filterKnown.setDisabled(self.filter==False)
        self.filterUnknown.setDisabled(self.filter==False)
        self.filterRingIdsButton.setDisabled(self.filter==False)

    @pyqtSlot()
    def _applyFilter(self):
        if self.filter==True:
            self.filterValue=self.filterEdit.text()
        else:
            self.filterValue=""

    @pyqtSlot()
    def _cleanup(self):
        self.closeLogFile()
        
    @pyqtSlot()
    def _enableLogFile(self):
        if self.logFileButton.isChecked()==True:
            if self.logFile==None:
                self.setupLogFile(self.logFileName)
        else:
            self.closeLogFile()
        self.replayButton.setDisabled(not self.logFileAvailable() or self.connectEnable==True)
        self.clearLogButton.setDisabled(not self.logFileAvailable() or self.replayMode==True)
        
    @pyqtSlot()
    def _startReplayMode(self):
        self.closeLogFile()
        self.logFileButton.setChecked(False)
        self.replayButton.setDisabled(True)
        self.replayMode=True
        
        self.stopReplayButton.setDisabled(self.replayMode==False)
        self.logFileButton.setDisabled(self.replayMode==True)
        self.clearLogButton.setDisabled(not self.logFileAvailable() or self.replayMode==True)
        
        replayLines=self.readLogFile()
        self._clearTable()
        self.thread.startReplayMode(replayLines)
        self._enableUpdate()
            
    @pyqtSlot()
    def _stopReplayMode(self):
        self.thread.stopReplayMode()
        self.replayModeDone()

    def replayModeDone(self):
        self.replayMode=False
        self.stopReplayButton.setDisabled(self.replayMode==False)
        self.replayButton.setDisabled(not self.logFileAvailable() or self.connectEnable==True)
        self.logFileButton.setDisabled(self.replayMode==True)
        self.clearLogButton.setDisabled(not self.logFileAvailable() or self.replayMode==True)
        
    @pyqtSlot()
    def _clearLogFile(self):
        if self.logFileAvailable():                        
            self.closeLogFile()
            os.remove(self.logFileName)
            self.logFile=None
        self._enableLogFile()
    
    @pyqtSlot()
    def _connect1(self):
        self.connectEnable=self.connectAction.isChecked()
        self.connectTo()
        
    @pyqtSlot()
    def _enableFilterRingIds(self):
        self.filterRingIds=self.filterRingIdsButton.isChecked()
    
    def connectTo(self):
        if self.replayMode==True:
            self._stopReplayMode()
            
        if self.connectEnable==True:
            self._clearTable()
            self.thread.connectCANDevice()
        else:
            self.thread.disconnectCANDevice()
            self.connectAction.setIcon(self.disconnectIcon)
            
        self.replayButton.setDisabled(not self.logFileAvailable() or self.connectEnable==True)
        self.updateConnectButtons()
    
    def connectEnabled(self):
        return self.connectEnable
    
    def updateConnectButtons(self):
        self.connectAction.setChecked(self.connectEnable==True)
#        self.connectButton.setChecked(self.connectEnable==True)
        
    def connectFailed(self):
        self.connectEnable=False
        self.connectAction.setIcon(self.disconnectIcon)
        self.updateConnectButtons()
        
    def updateStatusBarLabel(self, text):
        self.statusbar.showMessage(text)
        
    def connectSuccessful(self):
        self.connectEnable=True
        self.connectAction.setIcon(self.connectedIcon)
        self.updateConnectButtons()

        
    def canIdIsInKnownList(self, canId):
        return canId in self.canIdList

def main(argv): 
    test=False
    try:
        if argv[1]=="test":
            test=True
    except IndexError:
        test=False

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    
    ex = CANMonitor(app, test)
    app.aboutToQuit.connect(ex._cleanup)
    
#    print(ex.canDecoder.hex2binary(0x02))
#    print(int(ex.canDecoder.hex2binary(0x02)[:-1]))

    sys.exit(app.exec_())

if __name__ == "__main__":
    main(sys.argv)
