#!/usr/bin/env python3

import struct
import sys
import time
import os
from datetime import datetime
import fnmatch
from canutils import CANSocketWorker, CANDecoder, canIdleState, canRunState, canStoppedState
from gpsutils import GPSMonitor, GPSMonitorUpateWorker, gpsIdleState, gpsRunState, gpsStoppedState
from config import Config
from log import Log, DebugLogWidget

from PyQt4.QtCore import Qt, QAbstractTableModel, SIGNAL, pyqtSlot
from PyQt4.QtGui import QProgressBar, QIcon, QSizePolicy, QRadioButton, QColor, QBrush, QWidget, QPushButton, QCheckBox, QLineEdit, QTableView, QTabWidget, QApplication, QHBoxLayout, QVBoxLayout, QFormLayout, QLCDNumber, QLabel, QMainWindow, QPalette, QHeaderView

from collections import deque
from gaugepng import QtPngDialGauge
from osmmapviewer import OSMWidget

import signal
import operator
        
NUMBER_COL=0
TIME_COL=1
ID_COL=2
SIZE_COL=3
DATA_COL=4
       
class CANLogViewTableModel(QAbstractTableModel):
    def __init__(self, logBuffer, canIdList, parent):
        QAbstractTableModel.__init__(self, parent)
        self.logBuffer=logBuffer
        self.canIdList=canIdList
        self.canMonitor=parent
#        self.redBackground=QBrush(QColor(255, 0, 0))
#        self.greenBackground=QBrush(QColor(0, 255, 0))
#        self.blackForeground=QBrush(QColor(0, 0, 0))
        
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
#        elif role==Qt.BackgroundColorRole:
#            if index.row() >= len(self.logBuffer):
#                return None
#            if self.canMonitor.canIdIsInKnownList(self.logBuffer[index.row()][ID_COL]): 
#                return self.greenBackground
#            return self.redBackground
#        elif role==Qt.TextColorRole:
#            if index.row() >= len(self.logBuffer):
#                return None
#            return self.blackForeground
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
    
    def update(self, logBuffer, logBufferInit):
        self.reset()

class CANLogViewTableModel2(QAbstractTableModel):
    def __init__(self, canIdList, parent):
        QAbstractTableModel.__init__(self, parent)
        self.logBuffer=list()
        self.canIdList=canIdList
        self.canMonitor=parent
        self.redBackground=QBrush(QColor(255, 0, 0))
        self.blackForeground=QBrush(QColor(0, 0, 0))
        
    def rowCount(self, parent): 
        return len(self.logBuffer)
    
    def columnCount(self, parent): 
        return 10
      
    def data(self, index, role):
#        if not index.isValid():
#            return None
        if role == Qt.TextAlignmentRole:
            if index.column()==0:
                return Qt.AlignCenter|Qt.AlignVCenter
            elif index.column()==1:
                return Qt.AlignCenter|Qt.AlignVCenter
            elif index.column()>=2:
                return Qt.AlignLeft|Qt.AlignVCenter

        elif role==Qt.BackgroundColorRole:
            if index.row() >= len(self.logBuffer):
                return None
            
            if self.dataColChanged(index):
                return self.redBackground
            
            return None
        elif role==Qt.TextColorRole:
            if index.row() >= len(self.logBuffer):
                return None
            if self.dataColChanged(index):
                return self.blackForeground
            
            return None
        elif role != Qt.DisplayRole:
            return None
        
        if index.row() >= len(self.logBuffer):
            return ""
        item=self.logBuffer[index.row()]
        dataLen=item[1]
        if index.column()>=2 and index.column()-2 >= dataLen:
            return ""

        if index.column()==0:
            return hex(item[0])
        elif index.column()==1:
            return item[1]
        elif index.column()==2:
            return hex(item[2][0])
        elif index.column()==3:
            return hex(item[2][1])
        elif index.column()==4:
            return hex(item[2][2])
        elif index.column()==5:
            return hex(item[2][3])
        elif index.column()==6:
            return hex(item[2][4])
        elif index.column()==7:
            return hex(item[2][5])
        elif index.column()==8:
            return hex(item[2][6])
        elif index.column()==9:
            return hex(item[2][7])
    
    def headerData(self, col, orientation, role):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                if col==0:
                    return "Id"
                elif col==1:
                    return "Size"
                elif col>=2:
                    return "Data["+str(col-2)+"]"
            elif role == Qt.TextAlignmentRole:
                if col==0:
                    return Qt.AlignCenter
                elif col==1:
                    return Qt.AlignCenter
                elif col>=2:
                    return Qt.AlignLeft
        return None
    
    def update(self, logBuffer, logBufferInit):
        self.logBuffer=logBuffer
        self.logBufferInit=logBufferInit
        
        self.localSort(0, Qt.AscendingOrder)
        self.reset()
        
    def localSort(self, col, order):
        self.logBuffer = sorted(self.logBuffer, key=operator.itemgetter(col))        
        if order == Qt.DescendingOrder:
            self.logBuffer.reverse()
            
#        self.logBufferInit = sorted(self.logBufferInit, key=operator.itemgetter(col))        
#        if order == Qt.DescendingOrder:
#            self.logBufferInit.reverse()
#        self.reset()

    def dataColChanged(self, index):
        if index.column()<2:
            return False
            
        item=self.logBuffer[index.row()]
        canId=item[0]
        dataLen=item[1]

        itemInit=self.logBufferInit[canId]

        if index.column()>=2 and index.column()-2 >= dataLen:
            return False
    
        if item[2][index.column()-2]!=itemInit[2][index.column()-2]:
            return True

class CANFilterBox(QWidget):
    def __init__(self, withChanged, parent):
        QWidget.__init__(self, parent)
        self.canMonitor=parent
        self.filter=False
        self.filterValue=""
        self.filterRingIds=False
        self.withChanged=withChanged
        self.filterChanged=False
        
    def addFilterBox(self, layout):
        hbox = QHBoxLayout()
        layout.addLayout(hbox)
#        hbox.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
                
        self.filterButton=QCheckBox("Filter", self.canMonitor)
        self.filterButton.setToolTip('Enable filter')
        self.filterButton.resize(self.filterButton.sizeHint())
        self.filterButton.clicked.connect(self._enableFilter)
        hbox.addWidget(self.filterButton)
        
        self.filterEdit=QLineEdit(self.canMonitor)
        self.filterEdit.setToolTip('Id Filter')
        self.filterEdit.setDisabled(self.filter==False)
        self.filterEdit.returnPressed.connect(self._applyFilter)
        hbox.addWidget(self.filterEdit)
        
        self.applyFilterButton = QPushButton('Apply', self.canMonitor)
        self.applyFilterButton.setToolTip('Use Id filter')
        self.applyFilterButton.resize(self.applyFilterButton.sizeHint())
        self.applyFilterButton.clicked.connect(self._applyFilter)
        self.applyFilterButton.setDisabled(self.filter==False)
        hbox.addWidget(self.applyFilterButton)
        
        self.filterKnown=QRadioButton("Known", self.canMonitor)
        self.filterKnown.clicked.connect(self._applyFilter)
        self.filterKnown.setDisabled(self.filter==False)
        hbox.addWidget(self.filterKnown)
        
        self.filterUnknown=QRadioButton("Unknown", self.canMonitor)
        self.filterUnknown.clicked.connect(self._applyFilter)
        self.filterUnknown.setDisabled(self.filter==False)
        hbox.addWidget(self.filterUnknown)
        
        self.filterAll=QRadioButton("All", self.canMonitor)
        self.filterAll.clicked.connect(self._applyFilter)
        self.filterAll.setDisabled(self.filter==False)
        self.filterAll.setChecked(True)
        hbox.addWidget(self.filterAll)

        self.filterRingIdsButton=QCheckBox("Ring Ids", self.canMonitor)
        self.filterRingIdsButton.resize(self.filterRingIdsButton.sizeHint())
        self.filterRingIdsButton.clicked.connect(self._enableFilterRingIds)
        self.filterRingIdsButton.setDisabled(self.filter==False)
        self.filterRingIdsButton.setChecked(self.filterRingIds)
        hbox.addWidget(self.filterRingIdsButton)
        
        if self.withChanged==True:
            self.filterChangedButton=QCheckBox("Changed", self.canMonitor)
            self.filterChangedButton.resize(self.filterChangedButton.sizeHint())
            self.filterChangedButton.clicked.connect(self._enableFilterChanged)
            self.filterChangedButton.setDisabled(self.filter==False)
            self.filterChangedButton.setChecked(self.filterChanged)
            hbox.addWidget(self.filterChangedButton)
        
    def matchFilter(self, canId, line, lineInit):
        if self.filter==True:
            idMatch=self.matchIdFilter(canId)
            if idMatch==False:
                return False
            
            changedMatched=self.matchChangedFilter(line, lineInit)
            if changedMatched==False:
                return False
            
            if self.filterAll.isChecked():
                return idMatch
            
            isKnownId=self.canMonitor.canIdIsInKnownList(canId)
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
    
    def matchChangedFilter(self, line, lineInit):
        if self.filter==True:
            if self.filterChanged==True:
                if line!=lineInit:
                    return True
                return False
        return True
    
    @pyqtSlot()
    def _applyFilter(self):
        if self.filter==True:
            self.filterValue=self.filterEdit.text()
        else:
            self.filterValue=""
          
                  
    @pyqtSlot()
    def _enableFilter(self):
        self.filter=self.filterButton.isChecked()
        self.filterEdit.setDisabled(self.filter==False)
        self.applyFilterButton.setDisabled(self.filter==False)
        self.filterAll.setDisabled(self.filter==False)
        self.filterKnown.setDisabled(self.filter==False)
        self.filterUnknown.setDisabled(self.filter==False)
        self.filterRingIdsButton.setDisabled(self.filter==False)
        if self.withChanged==True:
            self.filterChangedButton.setDisabled(self.filter==False)
    
    @pyqtSlot()
    def _enableFilterRingIds(self):
        self.filterRingIds=self.filterRingIdsButton.isChecked()

    @pyqtSlot()
    def _enableFilterChanged(self):
        self.filterChanged=self.filterChangedButton.isChecked()
        
class CANLogTableBox(QWidget):
    def __init__(self, logViewModel, logBuffer, logBufferInit, parent):
        QWidget.__init__(self, parent)
        self.canMonitor=parent
        self.update=False
        self.logViewModel=logViewModel
        self.logBuffer=logBuffer
        self.logBufferInit=logBufferInit
        
    def addTableBox(self, layout):
        hbox = QHBoxLayout()
        layout.addLayout(hbox)
        self.pauseButton = QPushButton('Pause', self.canMonitor)
        self.pauseButton.setToolTip('Toggle live update of Log')
        self.pauseButton.resize(self.pauseButton.sizeHint())
        self.pauseButton.clicked.connect(self._disableUpdate)
        self.pauseButton.setDisabled(self.update==False or self.canMonitor.replayMode==False)
        hbox.addWidget(self.pauseButton)
        
        self.continueButton = QPushButton('Start', self.canMonitor)
        self.continueButton.setToolTip('Continue live update of Log')
        self.continueButton.resize(self.continueButton.sizeHint())
        self.continueButton.clicked.connect(self._enableUpdate)
        self.continueButton.setDisabled(self.update==True or self.canMonitor.replayMode==True)
        hbox.addWidget(self.continueButton)
        
        self.clearTableButton = QPushButton('Clear', self.canMonitor)
        self.clearTableButton.setToolTip('Clear Table')
        self.clearTableButton.resize(self.clearTableButton.sizeHint())
        self.clearTableButton.clicked.connect(self._clearTable)
        hbox.addWidget(self.clearTableButton)
    
    @pyqtSlot()
    def _clearTable(self):
        self.logBuffer.clear();
        if self.logBufferInit!=None:        
            self.logBufferInit.clear()
        self.logViewModel.update(self.logBuffer, self.logBufferInit)
                
    @pyqtSlot()
    def _disableUpdate(self):
        self.update=False
        self.continueButton.setDisabled(self.update==True and self.replayMode==True)
        self.pauseButton.setDisabled(self.update==False or self.replayMode==False)
            
    @pyqtSlot()
    def _enableUpdate(self):
        self.update=True
        self.continueButton.setDisabled(self.update==True or self.replayMode==True)
        self.pauseButton.setDisabled(self.update==False and self.replayMode==False)
        self._clearTable()

class MyTabWidget(QTabWidget):
    def __init__(self, parent):
        QTabWidget.__init__(self, parent)
#        self.setTabShape(QTabWidget.Rounded)
#        self.setTabsClosable(True)
        self.setTabPosition(QTabWidget.East)
        font = self.font()
        font.setPointSize(14)
        self.setFont(font)
        
#    def mousePressEvent(self, event):
#        print("MyTabWidget mousePressEvent")

class CANMonitor(QMainWindow):
    def __init__(self, app, test, parent):
        QMainWindow.__init__(self, parent)
        self.app = app
        self.lcdDict=dict()
        self.logBuffer=deque("", 1000)
        self.logBuffer2=dict()
        self.logBufferInit=dict()
        self.logEntryCount=1
        self.maxLogEntryCount=65353
        self.tableUpdateCouter=0
        self.logFile=None
        self.test=test
        self.logFileName="/tmp/candash.log"
        self.connectCANEnable=True
        self.connectGPSEnable=True
        self.replayMode=False
        self.canIdList=[0x621, 0x353, 0x351, 0x635, 0x271, 0x371, 0x623, 0x571, 0x3e5, 0x591, 0x5d1]
        self.updateGPSThread=None
        self.config=Config()
        self.log=Log(False)
        font = self.font()
        font.setPointSize(14)
        self.setFont(font)
        self.ampelGruen=QIcon("images/ampel-gruen.png")
        self.ampelRot=QIcon("images/ampel-rot.png")
        self.ampelGelb=QIcon("images/ampel-gelb.png")
        self.lastCANState=canStoppedState
        self.lastGPSState=gpsStoppedState
        self.canDecoder=CANDecoder(self)

        self.initUI(parent)
    
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
        lcd.setMinimumHeight(50)
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
        lbl.setMinimumHeight(50)
        font = lbl.font()
        font.setPointSize(14)
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
        lbl.setMinimumHeight(50)
        font = lbl.font()
        font.setPointSize(14)
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
        
        self.logViewModel=CANLogViewTableModel(self.logBuffer, self.canIdList, self)
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
        
    def createLogView2(self, vbox):
        self.logView2=QTableView(self)
        vbox.addWidget(self.logView2)
        
        self.logViewModel2=CANLogViewTableModel2(self.canIdList, self)
        self.logView2.setModel(self.logViewModel2)
#        self.logView2.setSortingEnabled(True)
        
        header=QHeaderView(Qt.Horizontal, self.logView2)
#        header.setStretchLastSection(True)
#        header.setClickable(True)
        header.setResizeMode(0, QHeaderView.Fixed)
        header.setResizeMode(1, QHeaderView.Fixed)

        self.logView2.setHorizontalHeader(header)
        
        self.logView2.setColumnWidth(0, 80)
        self.logView2.setColumnWidth(1, 50)
        for i in range(2, 10):
            self.logView2.setColumnWidth(i, 60)
        
    def initUI(self, parent):  
#        exitAction = QAction(QIcon(), 'Exit', self)
#        exitAction.setShortcut('Ctrl+Q')
#        exitAction.setStatusTip('Exit application')
#        exitAction.triggered.connectToCAN(self.close)

        self.statusbar=self.statusBar()
        self.progress=QProgressBar()
        self.statusbar.addPermanentWidget(self.progress)

#        menubar = self.menuBar()
#        fileMenu = menubar.addMenu('&File')
#        fileMenu.addAction(exitAction)

#        toolbar = self.addToolBar('Exit')
##        toolbar.addAction(exitAction)
#                
#        self.connectedIcon=QIcon("images/network-connect.png")
#        self.disconnectIcon=QIcon("images/network-disconnect.png")
#        self.connectAction = QAction(self.disconnectIcon , 'Connect', self)
#        self.connectAction.triggered.connect(self._connect1)
#        self.connectAction.setCheckable(True)
#        
#        toolbar.addAction(self.connectAction)
#        
#        self.gpsIcon=QIcon("images/icon_gps.gif")
#        self.reconnectGPSAction = QAction(self.gpsIcon, 'Reconnect GPS', self)
#        self.reconnectGPSAction.triggered.connect(self._reconnectGPS)
#        toolbar.addAction(self.reconnectGPSAction)
        
        mainWidget=QWidget(self)
        mainWidget.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)

        self.setCentralWidget(mainWidget)
        top=QVBoxLayout(mainWidget)
        
        self.tabs = MyTabWidget(self)
        top.addWidget(self.tabs)
        
        mainTab = QWidget(self)
        miscTab = QWidget(self) 
        misc2Tab=QWidget(self)
        canLogTab=QWidget(self)
        dashTab=QWidget(self)
        gpsTab=QWidget(self)
        osmTab=QWidget(self)
        debugLogTab=QWidget(self)
        
        mainTabLayout = QFormLayout(mainTab)
        miscTabLayout = QFormLayout(miscTab)
        misc2TabLayout = QFormLayout(misc2Tab)
        canLogTabLayout = QVBoxLayout(canLogTab)
        dashTabLayout = QHBoxLayout(dashTab)
        gpsTabLayout=QHBoxLayout(gpsTab)
        osmTabLayout=QVBoxLayout(osmTab)
        debugLogTabLayout=QVBoxLayout(debugLogTab)
        
        self.tabs.addTab(dashTab, "Dash") 
        self.tabs.addTab(mainTab, "Main")
        self.tabs.addTab(miscTab, "Misc 1") 
        self.tabs.addTab(misc2Tab, "Misc 2") 
        self.tabs.addTab(canLogTab, "CAN") 
        self.tabs.addTab(gpsTab, "GPS")
        self.tabs.addTab(osmTab, "OSM")
        self.tabs.addTab(debugLogTab, "Log")

        self.tabs.setCurrentIndex(0)
        
        self.debugLogWidget=DebugLogWidget(self)
        debugLogTabLayout.setAlignment(Qt.AlignLeft|Qt.AlignTop)
        self.debugLogWidget.addToWidget(debugLogTabLayout)

#        self.debugLogWidget.addLine("test")

        self.createCANIdEntry(mainTabLayout, 0x353, "0", "Drehzahl", QLCDNumber.Dec)
        self.createCANIdEntry(mainTabLayout, 0x353, "1", "Öltemperatur", QLCDNumber.Dec)
        self.createCANIdEntry(mainTabLayout, 0x351, "0", "Geschwindigkeit", QLCDNumber.Dec)
        self.createCANIdEntry(mainTabLayout, 0x351, "1", "Außentemperatur", QLCDNumber.Dec)
        self.createCANIdEntry(miscTabLayout, 0x635, "0", "Licht, Klemme 58d", QLCDNumber.Dec)
        self.createCANIdEntry(miscTabLayout, 0x271, "0", "Zuendung", QLCDNumber.Dec)
        self.createCANIdEntrySingleLine(miscTabLayout, 0x371, ["0", "1"], "Tuerstatus", QLCDNumber.Bin)
        self.createCANIdEntry(miscTabLayout, 0x371, "2", "Blinker, Retoursgang", QLCDNumber.Bin)
        self.createCANIdEntrySingleLine(mainTabLayout, 0x623, ["0", "1", "2"], "Uhrzeit (Stunden)", QLCDNumber.Dec)        
        self.createCANIdEntry(mainTabLayout, 0x571, "0", "Batteriespannung", QLCDNumber.Dec)
        
        self.createCANIdEntry(misc2TabLayout, 0x3e5, "0", "Zuheizer 1", QLCDNumber.Bin)
        self.createCANIdEntry(misc2TabLayout, 0x3e5, "1", "Zuheizer 2", QLCDNumber.Bin)
        self.createCANIdEntry(misc2TabLayout, 0x3e5, "2", "Zuheizer 3", QLCDNumber.Bin)
        self.createCANIdEntry(misc2TabLayout, 0x3e5, "3", "Zuheizer 4", QLCDNumber.Bin)
        self.createCANIdEntry(misc2TabLayout, 0x3e5, "4", "Zuheizer 5", QLCDNumber.Bin)
        
        self.createCANIdEntry(miscTabLayout, 0x3e5, "5", "Zuheizer", QLCDNumber.Dec)
        self.createCANIdEntry(miscTabLayout, 0x591, "0", "ZV", QLCDNumber.Dec)
        self.createCANIdEntry(miscTabLayout, 0x5d1, "0", "Scheibenwischer", QLCDNumber.Dec)

        self.createCANIdEntrySingleLine(mainTabLayout, 0x351, ["2", "3"], "Wegstreckenimpuls", QLCDNumber.Dec)
        self.createCANIdEntrySingleLine(misc2TabLayout, 0x621, ["0"], "0x621", QLCDNumber.Bin)
        self.createCANIdEntrySingleLine(misc2TabLayout, 0x621, ["1", "2"], "0x621", QLCDNumber.Dec)
        
        logTabs = MyTabWidget(self)
        canLogTabLayout.addWidget(logTabs)
        
        logTabWidget1=QWidget()
        logTabWidget2=QWidget()

        logTabs.addTab(logTabWidget1, "Time")
        logTabs.addTab(logTabWidget2, "Change") 
        
        logTab1Layout = QVBoxLayout(logTabWidget1)
        self.createLogView(logTab1Layout)
        
        self.logViewFilerBox1=CANFilterBox(False, self)
        self.logViewFilerBox1.addFilterBox(logTab1Layout)
        
        self.logViewTableBox1=CANLogTableBox(self.logViewModel, self.logBuffer, None, self)
        self.logViewTableBox1.addTableBox(logTab1Layout)
        
        logTab2Layout = QVBoxLayout(logTabWidget2)
        self.createLogView2(logTab2Layout)

        self.logViewFilterBox2=CANFilterBox(True, self)
        self.logViewFilterBox2.addFilterBox(logTab2Layout)
        
        self.logViewTableBox2=CANLogTableBox(self.logViewModel2, self.logBuffer2, self.logBufferInit, self)
        self.logViewTableBox2.addTableBox(logTab2Layout)
        
        logButtonBox = QHBoxLayout()
        canLogTabLayout.addLayout(logButtonBox)
        
        self.logFileButton=QCheckBox("Log to File", self)
        self.logFileButton.setToolTip('Enable file logging')
        self.logFileButton.resize(self.logFileButton.sizeHint())
        self.logFileButton.setDisabled(self.replayMode==True)
        self.logFileButton.clicked.connect(self._enableLogFile)
        logButtonBox.addWidget(self.logFileButton)
        
        self.clearLogButton = QPushButton('Clear Log', self)
        self.clearLogButton.resize(self.clearLogButton.sizeHint())
        self.clearLogButton.setDisabled(not self.logFileAvailable() or self.replayMode==True)
        self.clearLogButton.clicked.connect(self._clearLogFile)
        logButtonBox.addWidget(self.clearLogButton)

        self.replayButton = QPushButton('Replay Log', self)
        self.replayButton.resize(self.replayButton.sizeHint())
        self.replayButton.setDisabled(not self.logFileAvailable() or self.connectCANEnable==True)
        self.replayButton.clicked.connect(self._startReplayMode)
        logButtonBox.addWidget(self.replayButton)

        self.stopReplayButton = QPushButton('Stop Replay', self)
        self.stopReplayButton.resize(self.stopReplayButton.sizeHint())
        self.stopReplayButton.setDisabled(self.replayMode==False)
        self.stopReplayButton.clicked.connect(self._stopReplayMode)
        logButtonBox.addWidget(self.stopReplayButton)
                    
                    
        velBox = QVBoxLayout()
        dashTabLayout.addLayout(velBox)
        dashTabLayout.setAlignment(Qt.AlignCenter|Qt.AlignBottom)
             
        self.velGauge=QtPngDialGauge(self, "tacho3", "tacho31.png")
        self.velGauge.setMinimum(20)
        self.velGauge.setMaximum(220)
        self.velGauge.setStartAngle(135)
        self.velGauge.setValue(0)
#        self.velGauge.setMaximumSize(400, 400)
        velBox.addWidget(self.velGauge)

        self.createCANIdValueEntry(velBox, 0x351, "0", QLCDNumber.Dec)
        
        valuesBox = QVBoxLayout()
        valuesBox.setAlignment(Qt.AlignCenter|Qt.AlignBottom)

        dashTabLayout.addLayout(valuesBox)
        self.createCANIdValueEntry(valuesBox, 0x353, "1", QLCDNumber.Dec)
        self.createCANIdValueEntry(valuesBox, 0x351, "1", QLCDNumber.Dec)
        self.createCANIdValueEntry(valuesBox, 0x571, "0", QLCDNumber.Dec)
 
        rpmBox = QVBoxLayout()
        dashTabLayout.addLayout(rpmBox)
#        rpmBox.setAlignment(Qt.AlignCenter|Qt.AlignHCenter)
        self.rpmGauge=QtPngDialGauge(self, "rpm", "rpm1.png")
        self.rpmGauge.setMinimum(0)
        self.rpmGauge.setMaximum(8000)
        self.rpmGauge.setStartAngle(125)
        self.rpmGauge.setValue(2500)
#        self.rpmGauge.setMaximumSize(400, 400)
        rpmBox.addWidget(self.rpmGauge)     
         
        self.createCANIdValueEntry(rpmBox, 0x353, "0", QLCDNumber.Dec)
        
        self.gpsBox=GPSMonitor(self)
        gpsTabLayout.setAlignment(Qt.AlignLeft|Qt.AlignTop)
        self.gpsBox.loadConfig(self.config)

        self.gpsBox.addToWidget(gpsTabLayout)

        self.osmWidget=OSMWidget(self, self.app)
        osmTabLayout.setAlignment(Qt.AlignLeft|Qt.AlignTop)

        self.osmWidget.addToWidget(osmTabLayout)
        self.osmWidget.loadConfig(self.config)
                
        self.connect(self.osmWidget.mapWidgetQt, SIGNAL("updateStatus(QString)"), self.updateStatusBarLabel)
        self.connect(self.osmWidget.downloadThread, SIGNAL("updateStatus(QString)"), self.updateStatusBarLabel)
        self.connect(self.osmWidget, SIGNAL("updateStatus(QString)"), self.updateStatusBarLabel)
        self.connect(self.osmWidget, SIGNAL("startProgress()"), self.startProgress)
        self.connect(self.osmWidget, SIGNAL("stopProgress()"), self.stopProgress)

        self.osmWidget.initHome()
        
        connectBox=QHBoxLayout()
        top.addLayout(connectBox)
        
        self.connectCANButton = QCheckBox('CAN Connect', self)
        self.connectCANButton.clicked.connect(self._connectCAN)
        self.connectCANEnable=self.config.getDefaultSection().getboolean("CANconnect", False)
        self.connectCANButton.setChecked(self.connectCANEnable)
        self.connectCANButton.setIcon(self.ampelRot)
        connectBox.addWidget(self.connectCANButton)

        self.connectGPSButton = QCheckBox('GPS Connect', self)
        self.connectGPSButton.clicked.connect(self._connectGPS)
        self.connectGPSEnable=self.config.getDefaultSection().getboolean("GPSconnect", False)
        self.connectGPSButton.setChecked(self.connectGPSEnable)
        self.connectGPSButton.setIcon(self.ampelRot)
        connectBox.addWidget(self.connectGPSButton)
        
        self.setGeometry(10, 10, 850, 500)
        self.setWindowTitle("candash")
        self.show()
        
        self.updateCANThread = CANSocketWorker(self)        
        self.connect(self.updateCANThread, SIGNAL("updateStatus(QString)"), self.updateStatusBarLabel)
        self.connect(self.updateCANThread, SIGNAL("updateCANThreadState(QString)"), self.updateCANThreadState)
        self.connect(self.updateCANThread, SIGNAL("clearAllLCD()"), self.clearAllLCD)
        self.connect(self.updateCANThread, SIGNAL("connectCANFailed()"), self.connectCANFailed)
        self.connect(self.updateCANThread, SIGNAL("replayModeDone()"), self.replayModeDone)
        self.connect(self.updateCANThread, SIGNAL("processCANData(PyQt_PyObject)"), self.canDecoder.scan_can_frame)
        self._connectCAN()
        
        self.updateGPSThread=GPSMonitorUpateWorker(self)
        self.connect(self.updateGPSThread, SIGNAL("updateStatus(QString)"), self.updateStatusBarLabel)
        self.connect(self.updateGPSThread, SIGNAL("updateGPSThreadState(QString)"), self.updateGPSThreadState)
        self.connect(self.updateGPSThread, SIGNAL("connectGPSFailed()"), self.connectGPSFailed)
        self.connect(self.updateGPSThread, SIGNAL("updateGPSDisplay(PyQt_PyObject)"), self.updateGPSDisplay)
        self._connectGPS()
        
        self.osmWidget.loadData()
    
    #def mousePressEvent(self, event):
    #    print("CANMonitor mousePressEvent")
    #    self.tabs.mousePressEvent(event)

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
                                 
    def addToLogView(self, line):
        tableEntry=[self.logEntryCount, self.createTimeStamp()]
        tableEntry.extend(line[0:])
        
        if self.logFile!=None:
            self.addToLogFile(tableEntry)
            
        if self.logViewTableBox1.update==True:

            canId=line[0]
            if not self.logViewFilerBox1.matchFilter(canId, line, None):
                return
        
            self.logBuffer.appendleft(tableEntry)
            self.logEntryCount=self.logEntryCount+1
            if self.logEntryCount==self.maxLogEntryCount:
                self.logEntryCount=1
        
            self.tableUpdateCouter=self.tableUpdateCouter+1
            if self.tableUpdateCouter==10:
                self.logViewModel.update(self.logBuffer, None)
                self.tableUpdateCouter=0
                
    def addToLogView2(self, line):  
        if self.logViewTableBox2.update==True:
            canId=line[0]    
            if not canId in self.logBufferInit.keys():
                self.logBufferInit[canId]=line
                
            if not self.logViewFilterBox2.matchFilter(canId, line, self.logBufferInit[canId]):
                try:
                    del self.logBuffer2[canId]
                except KeyError:
                    None
            else:
                self.logBuffer2[canId]=line
        
                self.logViewModel2.update(list(self.logBuffer2.values()), self.logBufferInit)
                     
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
        self.osmWidget._cleanup()
        self.gpsBox._cleanup()

        if self.updateCANThread.isRunning():
            self.updateCANThread.stop()
        
        if self.updateGPSThread.isRunning():
            self.updateGPSThread.stop()
            
        self.closeLogFile()
        self.config.getDefaultSection()["canConnect"]=str(self.connectCANEnable)
        self.config.getDefaultSection()["gpsConnect"]=str(self.connectGPSEnable)
        
        self.osmWidget.saveConfig(self.config)
        self.gpsBox.saveConfig(self.config)

        self.config.writeConfig()
        self.log.writeLogtoFile()
        
    @pyqtSlot()
    def _enableLogFile(self):
        if self.logFileButton.isChecked()==True:
            if self.logFile==None:
                self.setupLogFile(self.logFileName)
        else:
            self.closeLogFile()
        self.replayButton.setDisabled(not self.logFileAvailable() or self.connectCANEnable==True)
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
        self.logViewTableBox1._clearTable()
        self.logViewTableBox2._clearTable()
        self.updateCANThread.setup(self.app, self, self.test, True, replayLines)
            
    @pyqtSlot()
    def _stopReplayMode(self):
        self.updateCANThread.stop()
        self.replayModeDone()

    def replayModeDone(self):
        self.replayMode=False
        self.stopReplayButton.setDisabled(self.replayMode==False)
        self.replayButton.setDisabled(not self.logFileAvailable() or self.connectCANEnable==True)
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
    def _connectCAN(self):
        self.connectCANEnable=self.connectCANButton.isChecked()
        if self.replayMode==True:
            self._stopReplayMode()
            
        if self.connectCANEnable==True:
#            self.connectCANButton.setDisabled(True)
            self.logViewTableBox1._clearTable()
            self.logViewTableBox2._clearTable()
            self.updateCANThread.setup(self.app, self.connectCANEnable, self.test, False, None)

        else:
            if self.updateCANThread.isRunning():
#                self.connectCANButton.setDisabled(True)
                self.updateCANThread.stop()
            
        self.replayButton.setDisabled(not self.logFileAvailable() or self.connectCANEnable==True)
        self.connectCANButton.setChecked(self.connectCANEnable==True)
                
    @pyqtSlot()
    def _connectGPS(self):
        self.connectGPSEnable=self.connectGPSButton.isChecked()
        if self.connectGPSEnable==True:
#            self.connectGPSButton.setDisabled(True)
            self.updateGPSThread.setup(self.connectGPSEnable)
        else:
            if self.updateGPSThread.isRunning():
#                self.connectGPSButton.setDisabled(True)
                self.updateGPSThread.stop()

        self.connectGPSButton.setChecked(self.connectGPSEnable==True)
        
    @pyqtSlot()
    def _enableFilterRingIds(self):
        self.filterRingIds=self.filterRingIdsButton.isChecked()
    
    def connectCANEnabled(self):
        return self.connectCANEnable
         
    def connectCANFailed(self):
        self.connectCANEnable=False
        self.connectCANButton.setChecked(False)
#        self.connectCANButton.setDisabled(False)
        self.connectCANButton.setIcon(self.ampelRot)

    def updateStatusBarLabel(self, text):
        self.statusbar.showMessage(text)
        logLine=self.log.addLineToLog(text)
        self.debugLogWidget.addLineToLog(logLine)
        
    def stopProgress(self):
        self.progress.setMinimum(0)
        self.progress.setMaximum(1)
        self.progress.reset()
    
    def startProgress(self):
        self.progress.setMinimum(0)
        self.progress.setMaximum(0)

#    def connectCANSuccessful(self):
#        self.connectCANEnable=True
##        self.connectCANButton.setChecked(True)
##        self.connectCANButton.setDisabled(False)
#        self.connectCANButton.setIcon(self.ampelGruen)

#    def stopCANSuccesful(self):
#        self.connectCANButton.setDisabled(False)
#        self.connectCANButton.setIcon(self.ampelRot)

    def canIdIsInKnownList(self, canId):
        return canId in self.canIdList

    def updateGPSDisplay(self, session):
        self.gpsBox.update(session)
        
    def connectGPSFailed(self):
        self.connectGPSButton.setChecked(False)
        self.connectGPSEnable=False
#        self.connectGPSButton.setDisabled(False)
        self.connectGPSButton.setIcon(self.ampelRot)
    
#    def connectGPSSuccesful(self):
##        self.connectGPSButton.setChecked(True)
#        self.connectGPSEnable=True
##        self.connectGPSButton.setDisabled(False)
#        self.connectGPSButton.setIcon(self.ampelGruen)
        
    def connectGPSEnabled(self):
        return self.connectGPSEnable
    
#    def stopGPSSuccesful(self):
#        self.connectGPSButton.setDisabled(False)
#        self.connectGPSButton.setIcon(self.ampelRot)

    def updateCANThreadState(self, state):
        if state!=self.lastCANState:
            if state==canIdleState:
                self.connectCANButton.setIcon(self.ampelGelb)
            elif state==canRunState:
                self.connectCANButton.setIcon(self.ampelGruen)
            elif state==canStoppedState:
                self.connectCANButton.setIcon(self.ampelRot)
                self.connectCANEnable=False
            self.lastCANState=state
            
    def updateGPSThreadState(self, state):
        if state!=self.lastGPSState:
            if state==gpsIdleState:
                self.connectGPSButton.setIcon(self.ampelGelb)
            elif state==gpsRunState:
                self.connectGPSButton.setIcon(self.ampelGruen)
            elif state==gpsStoppedState:
                self.connectGPSButton.setIcon(self.ampelRot)
                self.connectGPSnable=False
            self.lastGPSState=state

    def hasOSMWidget(self):
        return self.osmWidget!=None
    
def main(argv): 
    test=False
    try:
        if argv[1]=="test":
            test=True
    except IndexError:
        test=False

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    
    ex = CANMonitor(app, test, None)
    app.aboutToQuit.connect(ex._cleanup)

    sys.exit(app.exec_())

if __name__ == "__main__":
    main(sys.argv)
