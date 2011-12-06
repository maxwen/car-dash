#!/usr/bin/env python3

import struct
import sys
import time
import os
from datetime import datetime
import fnmatch
from canutils import CANDecoder, CANSocketWorker
from gps import gps, misc
import socket

from PyQt4.QtCore import Qt, QAbstractTableModel, SIGNAL, pyqtSlot, QThread
from PyQt4.QtGui import QSizePolicy, QRadioButton, QColor, QBrush, QWidget, QPushButton, QCheckBox, QLineEdit, QTableView, QTabWidget, QApplication, QHBoxLayout, QVBoxLayout, QFormLayout, QLCDNumber, QLabel, QMainWindow, QPalette, QHeaderView, QAction, QIcon

from collections import deque
from gaugepng import QtPngDialGauge
from gaugecompass import QtPngCompassGauge
from osmmapviewer import OSMWidget

import signal
import operator
        
NUMBER_COL=0
TIME_COL=1
ID_COL=2
SIZE_COL=3
DATA_COL=4

class GPSMonitorUpateWorker(QThread):
    def __init__(self, parent=None): 
        QThread.__init__(self, parent)
        self.exiting = False
        
    def __del__(self, session):
        self.exiting = True
        self.wait()
        
    def setup(self, canMonitor):
        self.canMonitor=canMonitor
        self.session=None
        self.start()
            
    def updateStatusLabel(self, text):
        self.emit(SIGNAL("updateStatus(QString)"), text)

    def connectToGPS(self):
        try:
            self.session = gps.gps()
            self.updateStatusLabel("GPS connect ok")
            self.session.stream(gps.WATCH_ENABLE)
        except socket.error:
            self.updateStatusLabel("GPS connect error")
            self.session=None
            self.sleep(1)
            
    def reconnectGPS(self):
        if self.session!=None:
            self.session=None
        
    def run(self):
        while not self.exiting and True:
            if self.session==None:
                self.connectToGPS()
                continue
            try:
                self.session.__next__()
                self.canMonitor.updateGPSDisplay(self.session)
            except StopIteration:
                self.updateStatusLabel("GPS connection lost")
                self.session=None
                self.canMonitor.updateGPSDisplay(None)
            
#            self.msleep(500) 
                
class CANLogViewTableModel(QAbstractTableModel):
    def __init__(self, canMonitor, logBuffer, canIdList, parent=None):
        QAbstractTableModel.__init__(self, parent)
        self.logBuffer=logBuffer
        self.canIdList=canIdList
        self.canMonitor=canMonitor
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
    def __init__(self, canMonitor, canIdList, parent=None):
        QAbstractTableModel.__init__(self, parent)
        self.logBuffer=list()
        self.canIdList=canIdList
        self.canMonitor=canMonitor
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

class CANFilterBox():
    def __init__(self, canMonitor, withChanged):
        self.canMonitor=canMonitor
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
        
class CANLogTableBox():
    def __init__(self, canMonitor, logViewModel, logBuffer, logBufferInit):
        self.canMonitor=canMonitor
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
        
class GPSMonitor():
    def __init__(self, canMonitor):
        self.canMonitor=canMonitor
        self.valueLabelList=list()
        
    def createGPSLabel(self, form, key, value):
        lbl = QLabel(self.canMonitor)
        lbl.setMinimumHeight(50)
        font = lbl.font()
        font.setPointSize(14)
        lbl.setFont(font)
        lbl.setText(key)
        
        lbl2 = QLabel(self.canMonitor)
        lbl2.setMinimumHeight(50)
        font = lbl2.font()
        font.setPointSize(14)
        lbl2.setFont(font)
        lbl2.setText(value)
        self.valueLabelList.append(lbl2)

        form.addRow(lbl, lbl2)
        
    def addGPSBox(self, hbox):
        form=QFormLayout()
        hbox.addLayout(form)
        
        self.createGPSLabel(form, "Status", "Not connected")
        self.createGPSLabel(form, "Latitude", "")
        self.createGPSLabel(form, "Longitude", "")
        self.createGPSLabel(form, "Time UTC", "")
        self.createGPSLabel(form, "Altitude", "")
        self.createGPSLabel(form, "Speed", "")
        self.createGPSLabel(form, "Track", "")
        
        vbox=QVBoxLayout()
        self.compassGauge=QtPngCompassGauge(self.canMonitor, "compass", "compass.png")
        self.compassGauge.setValue(0)
        self.compassGauge.setMaximumSize(320, 320)
        vbox.addWidget(self.compassGauge)

        self.speedDisplay=self.canMonitor.createLCD(QLCDNumber.Dec)
        self.speedDisplay.display(0)
        vbox.addWidget(self.speedDisplay)
        
        hbox.addLayout(vbox)
                        
    def update(self, session):
        if session!=None:
            self.valueLabelList[0].setText("Connected ("+str(session.satellites_used)+" satelites)")
            self.valueLabelList[1].setText(str(session.fix.latitude))
            self.valueLabelList[2].setText(str(session.fix.longitude))
            
#            print(session.utc)
            if type(session.utc)==type(1.0):
                try:
                    timeString=misc.isotime(session.utc)
                except IndexError:
                    timeString=""
                except ValueError:
                    timeString=""
            else:
                timeString=str(session.utc)
                
            self.valueLabelList[3].setText(timeString)
            self.valueLabelList[4].setText(str(session.fix.altitude))
            self.valueLabelList[5].setText(str(session.fix.speed))
            #self.valueLabelList[6].setText(str(session.fix.climb))
            self.valueLabelList[6].setText(str(session.fix.track))
            if not gps.isnan(session.fix.track):
                self.compassGauge.setValue(int(session.fix.track))
            else:
                self.compassGauge.setValue(0)
            if not gps.isnan(session.fix.speed):
                self.speedDisplay.display(int(session.fix.speed*3.6))
            else:
                self.speedDisplay.display(0)
                
            self.canMonitor.osmWidget.updateGPSPosition(session.fix.latitude, session.fix.longitude)

        else:
            self.valueLabelList[0].setText("Not connected")
            self.valueLabelList[1].setText("")
            self.valueLabelList[2].setText("")
            self.valueLabelList[3].setText("")
            self.valueLabelList[4].setText("")
            self.valueLabelList[5].setText("")
            self.valueLabelList[6].setText("")
            self.compassGauge.setValue(0)
            self.speedDisplay.display(0)

        
class CANMonitor(QMainWindow):
    def __init__(self, app, test):
        super(CANMonitor, self).__init__()
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
        self.connectEnable=False
        self.replayMode=False
        self.canIdList=[0x353, 0x351, 0x635, 0x271, 0x371, 0x623, 0x571, 0x3e5, 0x591, 0x5d1]
        self.updateGPSThread=None
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
        
    def createLogView2(self, vbox):
        self.logView2=QTableView(self)
        vbox.addWidget(self.logView2)
        
        self.logViewModel2=CANLogViewTableModel2(self, self.canIdList)
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
        
        toolbar.addAction(self.connectAction)
        
        self.gpsIcon=QIcon("images/icon_gps.gif")
        self.reconnectGPSAction = QAction(self.gpsIcon, 'Reconnect GPS', self)
        self.reconnectGPSAction.triggered.connect(self._reconnectGPS)
        toolbar.addAction(self.reconnectGPSAction)
        
        mainWidget=QWidget()
        mainWidget.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)

        self.setCentralWidget(mainWidget)
        top=QVBoxLayout(mainWidget)
        
        tabs = QTabWidget(self)
        top.addWidget(tabs)
        
        mainTab = QWidget()
        miscTab = QWidget() 
        zuheizerTab=QWidget()
        logTab=QWidget()
        dashTab=QWidget()
        gpsTab=QWidget()
        osmTab=QWidget()
        
        mainTabLayout = QFormLayout(mainTab)
        miscTabLayout = QFormLayout(miscTab)
        zuheizerTabLayout = QFormLayout(zuheizerTab)
        logTabLayout = QVBoxLayout(logTab)
        dashTabLayout = QHBoxLayout(dashTab)
        gpsTabLayout=QHBoxLayout(gpsTab)
        osmTabLayout=QVBoxLayout(osmTab)

        tabs.addTab(dashTab, "Dash") 
        tabs.addTab(mainTab, "Main")
        tabs.addTab(miscTab, "Misc") 
        tabs.addTab(zuheizerTab, "Zuheizer") 
        tabs.addTab(logTab, "Log") 
        tabs.addTab(gpsTab, "GPS")
        tabs.addTab(osmTab, "OSM")

#        tabs.setCurrentIndex(4)
        
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
        
        self.createCANIdEntry(zuheizerTabLayout, 0x3e5, "0", "Zuheizer 1", QLCDNumber.Bin)
        self.createCANIdEntry(zuheizerTabLayout, 0x3e5, "1", "Zuheizer 2", QLCDNumber.Bin)
        self.createCANIdEntry(zuheizerTabLayout, 0x3e5, "2", "Zuheizer 3", QLCDNumber.Bin)
        self.createCANIdEntry(zuheizerTabLayout, 0x3e5, "3", "Zuheizer 4", QLCDNumber.Bin)
        self.createCANIdEntry(zuheizerTabLayout, 0x3e5, "4", "Zuheizer 5", QLCDNumber.Bin)
        
        self.createCANIdEntry(miscTabLayout, 0x3e5, "5", "Zuheizer", QLCDNumber.Dec)
        self.createCANIdEntry(miscTabLayout, 0x591, "0", "ZV", QLCDNumber.Dec)
        self.createCANIdEntry(miscTabLayout, 0x5d1, "0", "Scheibenwischer", QLCDNumber.Dec)

        
        logTabs = QTabWidget(self)
        logTabLayout.addWidget(logTabs)
        
        logTabWidget1=QWidget()
        logTabWidget2=QWidget()

        logTabs.addTab(logTabWidget1, "Time")
        logTabs.addTab(logTabWidget2, "Change") 
        
        logTab1Layout = QVBoxLayout(logTabWidget1)
        self.createLogView(logTab1Layout)
        
        self.logViewFilerBox1=CANFilterBox(self, False)
        self.logViewFilerBox1.addFilterBox(logTab1Layout)
        
        self.logViewTableBox1=CANLogTableBox(self, self.logViewModel, self.logBuffer, None)
        self.logViewTableBox1.addTableBox(logTab1Layout)
        
        logTab2Layout = QVBoxLayout(logTabWidget2)
        self.createLogView2(logTab2Layout)

        self.logViewFilterBox2=CANFilterBox(self, True)
        self.logViewFilterBox2.addFilterBox(logTab2Layout)
        
        self.logViewTableBox2=CANLogTableBox(self, self.logViewModel2, self.logBuffer2, self.logBufferInit)
        self.logViewTableBox2.addTableBox(logTab2Layout)
        
        logButtonBox = QHBoxLayout()
        logTabLayout.addLayout(logButtonBox)
        
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
        self.replayButton.setDisabled(not self.logFileAvailable() or self.connectEnable==True)
        self.replayButton.clicked.connect(self._startReplayMode)
        logButtonBox.addWidget(self.replayButton)

        self.stopReplayButton = QPushButton('Stop Replay', self)
        self.stopReplayButton.resize(self.stopReplayButton.sizeHint())
        self.stopReplayButton.setDisabled(self.replayMode==False)
        self.stopReplayButton.clicked.connect(self._stopReplayMode)
        logButtonBox.addWidget(self.stopReplayButton)
                    
                    
        velBox = QVBoxLayout()
        dashTabLayout.addLayout(velBox)
                                  
        self.velGauge=QtPngDialGauge(self, "tacho3", "tacho3.png")
        self.velGauge.setMinimum(20)
        self.velGauge.setMaximum(220)
        self.velGauge.setStartAngle(135)
        self.velGauge.setValue(0)
        self.velGauge.setMaximumSize(320, 320)
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
        self.rpmGauge=QtPngDialGauge(self, "rpm", "rpm.png")
        self.rpmGauge.setMinimum(0)
        self.rpmGauge.setMaximum(8000)
        self.rpmGauge.setStartAngle(120)
        self.rpmGauge.setValue(0)
        self.rpmGauge.setMaximumSize(320, 320)
        rpmBox.addWidget(self.rpmGauge)     
         
        self.createCANIdValueEntry(rpmBox, 0x353, "0", QLCDNumber.Dec)

        
#        self.connectButton = QCheckBox('Connect')
#        self.connectButton.clicked.connect(self._connect2)
#        top.addWidget(self.connectButton)
        
        self.gpsBox=GPSMonitor(self)
        self.gpsBox.addGPSBox(gpsTabLayout)
        
        self.osmWidget=OSMWidget(self)
        osmTabLayout.setAlignment(Qt.AlignLeft|Qt.AlignTop)

        self.osmWidget.addToWidget(osmTabLayout)
        self.osmWidget.initHome()
        
        self.connect(self.osmWidget.mapWidgetQt, SIGNAL("updateStatus(QString)"), self.updateStatusBarLabel)

        self.setGeometry(10, 10, 860, 500)
        self.setWindowTitle("candash")
        self.show()
        
        self.canDecoder = CANDecoder(self)

        self.thread = CANSocketWorker()        
        self.connect(self.thread, SIGNAL("updateStatus(QString)"), self.updateStatusBarLabel)
        self.thread.setup(self.app, self, self.canDecoder, self.test)
        
        self.updateGPSThread=GPSMonitorUpateWorker()
        self.updateGPSThread.setup(self)
        self.connect(self.updateGPSThread, SIGNAL("updateStatus(QString)"), self.updateStatusBarLabel)

               
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
        self.logViewTableBox1._clearTable()
        self.logViewTableBox2._clearTable()
        self.thread.startReplayMode(replayLines)
#        self._enableUpdate()
            
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
            self.logViewTableBox1._clearTable()
            self.logViewTableBox2._clearTable()

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

    def updateGPSDisplay(self, session):
        self.gpsBox.update(session)
        
    @pyqtSlot()
    def _reconnectGPS(self):
        self.updateGPSThread.reconnectGPS()
        
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
#    print(ex.canDecoder.hex2binary(0x04))
#
#    print(int(ex.canDecoder.getBit(0x02, 0)))
#    print(int(ex.canDecoder.getBit(0x02, 1)))
#    print(int(ex.canDecoder.getBit(0x02, 2)))
#    print(int(ex.canDecoder.getBit(0x04, 0)))
#    print(int(ex.canDecoder.getBit(0x04, 1)))
#    print(int(ex.canDecoder.getBit(0x04, 2)))
#    print(int(ex.canDecoder.getBit(0x04, 1) + ex.canDecoder.getBit(0x04, 2)))
#    print(int(ex.canDecoder.getBit(0x02, 1) + ex.canDecoder.getBit(0x02, 2)))

#    print(int(ex.canDecoder.getBit(0x04, 3)))

    sys.exit(app.exec_())

if __name__ == "__main__":
    main(sys.argv)
