'''
Created on Dec 7, 2011

@author: maxl
'''

from gps import gps, misc
import socket

from PyQt4.QtCore import SIGNAL, QThread, Qt
from PyQt4.QtGui import QWidget, QVBoxLayout, QFormLayout, QLCDNumber, QLabel
from gaugecompass import QtPngCompassGauge

class GPSMonitorUpateWorker(QThread):
    def __init__(self, parent): 
        QThread.__init__(self, parent)
        self.exiting = False
        self.connected=False
        self.reconnecting=False
        self.reconnectTry=0
        
    def __del__(self):
        self.exiting = True
        self.wait()
        
    def stop(self):
        if self.connected==True:
            self.disconnectGPS()
        self.exiting = True
        self.wait()
        
    def setup(self, canMonitor):
        self.updateStatusLabel("GPS thread setup")

        self.canMonitor=canMonitor
        self.session=None
        self.exiting = False
        self.connected=False
        self.reconnecting=False
        self.reconnectTry=0
        
        if self.canMonitor.connectGPSEnabled()==True:
            self.connectGPS()

        if self.connected==True:
            self.updateStatusLabel("GPS thread started")
            self.start()
                
    def updateStatusLabel(self, text):
        self.emit(SIGNAL("updateStatus(QString)"), text)

    def connectGPS(self):
        if self.session==None:
            try:
                self.session = gps.gps()
                self.updateStatusLabel("GPS connect ok")
                self.canMonitor.connectGPSSuccesful()
                self.session.stream(gps.WATCH_ENABLE)
                self.connected=True
            except socket.error:
                if self.reconnecting==True:
                    self.updateStatusLabel("GPS reconnect try "+str(self.reconnectTry))
                    self.connected=False
                    self.session=None
                else:
                    self.updateStatusLabel("GPS connect error")
                    self.connected=False
                    self.session=None
                    self.canMonitor.connectGPSFailed()
          
    def disconnectGPS(self):
        if self.connected==True:
            self.connected=False
            if self.session!=None:
                self.session.close()
            self.session=None
            self.updateStatusLabel("GPS disconnect ok")
            self.canMonitor.updateGPSDisplay(None)
          
    def reconnectGPS(self):
        self.reconnecting=True
        while self.reconnectTry<42 and self.connected==False and self.exiting==False:
            self.sleep(1)
            self.connectGPS()
            if self.connected==True:
                self.reconnectTry=0
                self.reconnecting=False
                return
            self.reconnectTry=self.reconnectTry+1

        self.connected=False
        self.reconnectTry=0
        self.reconnecting=False
        self.session=None
        self.canMonitor.updateGPSDisplay(None)
        self.canMonitor.connectGPSFailed()
        self.updateStatusLabel("GPS reconnect failed")
        
    def run(self):
        while not self.exiting and True:
            if self.connected==True and self.session!=None:
                try:
                    self.session.__next__()
                    self.canMonitor.updateGPSDisplay(self.session)
                except StopIteration:
                    self.updateStatusLabel("GPS connection lost")
                    self.connected=False
                    self.session=None
                    self.canMonitor.updateGPSDisplay(None)
                    self.reconnectGPS()
                #except socket.timeout:
                #    None
                except socket.error:
                    if self.exiting==True:
                        self.updateStatusLabel("GPS thread stop request")
                        continue
            else:
                self.updateStatusLabel("GPS thread idle")
                self.msleep(1000)
            
        self.updateStatusLabel("GPS thread stopped")
        self.canMonitor.stopGPSSuccesful()
        
class GPSMonitor(QWidget):
    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.canMonitor=parent
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
        
    def addToWidget(self, hbox):
        form=QFormLayout()
        form.setAlignment(Qt.AlignLeft|Qt.AlignTop)

        hbox.addLayout(form)
        
        self.createGPSLabel(form, "Status", "Not connected")
        self.createGPSLabel(form, "Latitude", "")
        self.createGPSLabel(form, "Longitude", "")
        self.createGPSLabel(form, "Time UTC", "")
        self.createGPSLabel(form, "Altitude", "")
        self.createGPSLabel(form, "Speed", "")
        self.createGPSLabel(form, "Track", "")
        
        vbox=QVBoxLayout()
        vbox.setAlignment(Qt.AlignRight|Qt.AlignTop)

        self.compassGauge=QtPngCompassGauge(self.canMonitor, "compass", "compass.png")
        self.compassGauge.setValue(0)
        self.compassGauge.setMaximumSize(300, 300)
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
                
            if not gps.isnan(session.fix.latitude) and not gps.isnan(session.fix.longitude):
                self.canMonitor.osmWidget.updateGPSPosition(session.fix.latitude, session.fix.longitude)
            else:
                self.canMonitor.osmWidget.updateGPSPosition(0.0, 0.0)

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
            self.canMonitor.osmWidget.updateGPSPosition(0.0, 0.0)

    def loadConfig(self, config):
        None
            
    def saveConfig(self, config):
        None
