'''
Created on Dec 7, 2011

@author: maxl
'''

import socket
import signal
import sys
import time
import os
from datetime import datetime


USE_GPSD=True
USE_NMEA=False

try:
    import gpsd
except ImportError:
    USE_GPSD=False

try:
    import nmea.gps
    from nmea.serialport import SerialPort
    from nmea._port import PortError
except ImportError:
    USE_NMEA=False

from PyQt4.QtCore import SIGNAL, QThread, Qt, pyqtSlot
from PyQt4.QtGui import QCheckBox, QPalette, QApplication, QTabWidget, QSizePolicy, QMainWindow, QPushButton, QWidget, QHBoxLayout, QVBoxLayout, QFormLayout, QLCDNumber, QLabel
from gaugecompass import QtPngCompassGauge
from utils.osmutils import OSMUtils
from utils.config import Config

gpsRunState="run"
gpsStoppedState="stopped"


def getGPSUpdateThread(parent):
    if USE_NMEA==True:
        return GPSUpateWorkerNMEA(parent)
    if USE_GPSD==True:
        return GPSUpateWorkerGPSD(parent)
    return None

class GPSData():
    def __init__(self, time=None, lat=None, lon=None, track=None, speed=None, altitude=None, predicted=False):
        self.time=time
        self.lat=lat
        self.lon=lon
        self.track=track
        self.speed=speed
        self.altitude=altitude
        self.predicted=predicted
        
    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.lat==other.lat and self.lon==other.lon and self.track==other.track and self.speed==other.speed and self.altitude==other.altitude
            
    def isValid(self):
        return self.lat!=None and self.lon!=None and self.lat!=0.0 and self.lon!=0.0
    
    def getTime(self):
        return self.time()
    
    def getLat(self):
        return self.lat
    
    def getLon(self):
        return self.lon
    
    def getTrack(self):
        return self.track
    
    def getSpeed(self):
        return self.speed
    
    def getAltitude(self):
        return self.altitude
    
    def fromTrackLogLine(self, line):
        lineParts=line.split(":")
        self.time=time.time()
        if len(lineParts)==6:
            self.lat=float(lineParts[1])
            self.lon=float(lineParts[2])
            self.track=int(lineParts[3])
            self.speed=int(lineParts[4])
            if lineParts[5]!="\n":
                self.altitude=int(lineParts[5])
            else:
                self.altitude=0
        else:
            self.lat=0.0
            self.lon=0.0
            self.track=0
            self.speed=0
            self.altitude=0
            
    def createTimeStamp(self):
        stamp=datetime.fromtimestamp(self.time)
        return "".join(["%02d.%02d.%02d.%06d"%(stamp.hour, stamp.minute, stamp.second, stamp.microsecond)])

    def toLogLine(self):
        return "%s:%f:%f:%d:%d:%d"%(self.createTimeStamp(), self.lat, self.lon, self.track, self.speed, self.altitude)

    def __repr__(self):
        return self.toLogLine()

class GPSUpateWorkerGPSD(QThread):
    def __init__(self, parent): 
        QThread.__init__(self, parent)
        self.exiting = False
        self.connected=False
        self.reconnecting=False
        self.reconnectTry=0
        self.lastGPSData=None
        
    def __del__(self):
        self.exiting = True
        self.wait()
        
    def stop(self):
        if self.connected==True:
            self.disconnectGPS()
        self.exiting = True
        self.wait()
        
    def setup(self, connect):
        self.updateStatusLabel("GPS thread setup")

        self.session=None
        self.exiting = False
        self.connected=False
        self.reconnecting=False
        self.reconnectTry=0
        
        if connect==True:
            self.connectGPS()

        if self.connected==True:
            self.updateStatusLabel("GPS thread started")
            self.start()
                
    def updateStatusLabel(self, text):
        self.emit(SIGNAL("updateStatus(QString)"), text)
#        print(text)
        
    def updateGPSThreadState(self, state):
        self.emit(SIGNAL("updateGPSThreadState(QString)"), state)

    def connectGPSFailed(self):
        self.emit(SIGNAL("connectGPSFailed()"))
    
    def updateGPSDisplay(self, gpsData):
        self.emit(SIGNAL("updateGPSDisplay(PyQt_PyObject)"), gpsData)
        
    def connectGPS(self):
        if self.session==None:
            try:
                self.session = gpsd.gps()
                self.updateStatusLabel("GPS connect ok")
                self.session.stream(gpsd.WATCH_ENABLE)
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
                    self.connectGPSFailed()
          
    def disconnectGPS(self):
        if self.connected==True:
            self.connected=False
            if self.session!=None:
                self.session.close()
            self.session=None
            self.updateStatusLabel("GPS disconnect ok")
          
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
        self.exiting=True
        self.connectGPSFailed()
        self.updateStatusLabel("GPS reconnect failed - exiting thread")
        
    def createGPSData(self, session):
        timeStamp=time.time()

        speed=0
        altitude=0
        track=0
        lat=0.0
        lon=0.0
        
        if not gpsd.isnan(session.fix.track):
            track=int(session.fix.track)
        
        if not gpsd.isnan(session.fix.speed):
            speed=int(session.fix.speed*3.6)
        
        if not gpsd.isnan(session.fix.altitude):
            altitude=session.fix.altitude
     
        if not gpsd.isnan(session.fix.latitude) and not gpsd.isnan(session.fix.longitude):
            lat=session.fix.latitude
            lon=session.fix.longitude
        
        return GPSData(timeStamp, lat, lon, track, speed, altitude)
    
    def run(self):
        self.updateGPSThreadState(gpsRunState)

        while not self.exiting and True:
            if self.connected==True and self.session!=None:
                try:
                    self.session.__next__()
                    gpsData=self.createGPSData(self.session)
                    if gpsData!=self.lastGPSData:
                        self.updateGPSDisplay(gpsData)
                        self.lastGPSData=gpsData
                        self.updateGPSThreadState(gpsRunState)
                except StopIteration:
                    self.updateStatusLabel("GPS connection lost")
                    self.connected=False
                    self.session=None
                    self.reconnectGPS()
                except socket.timeout:
                    self.updateStatusLabel("GPS thread socket.timeout")
                    continue
                except socket.error:
                    if self.exiting==True:
                        self.updateStatusLabel("GPS thread stop request")
                        continue
            else:
                self.msleep(1000)
            
        self.updateStatusLabel("GPS thread stopped")
        self.updateGPSThreadState(gpsStoppedState)
        self.updateGPSDisplay(None)

class GpsObject():
    def __init__(self, port):
        self.gps_device = nmea.gps.Gps(port, callbacks={
            'fix_update': self.__fix_update,
            'transit_update': self.__transit_update,
            'satellite_update': self.__satellite_update,
            'satellite_status_update': self.__satellite_status_update,
            'log_error': self.__log_error

        })
        self.lat=0.0
        self.lon=0.0
        self.track=0
        self.speed=0
        self.altitude=0.0

    def __log_error(self, msg, info):
        pass
        
    def __fix_update(self, gps_device):
        pass

    def __transit_update(self, gps_device):
        self.lat=gps_device.position.get_value()[0]
        self.lon=gps_device.position.get_value()[1]
        self.track=int(gps_device.track)
        self.speed=int(gps_device.speed.kilometers_per_hour())
        self.altitude=gps_device.altitude

    def __satellite_update(self, gps_device):
        pass

    def __satellite_status_update(self, gps_device):
        pass
    
    def createGPSData(self):
        timeStamp=time.time()            
        return GPSData(timeStamp, self.lat, self.lon, self.track, self.speed, self.altitude)
        
class GPSUpateWorkerNMEA(QThread):
    def __init__(self, parent): 
        QThread.__init__(self, parent)
        self.exiting = False
        self.connected=False
        self.deviceList=["/dev/ttyACM0", 
                         "/dev/ttyACM1", 
                         "/dev/ttyUSB0", 
                         "/dev/ttyUSB1",
                         "/dev/gps"]
        self.timeout=3
        self.baud=9600
        self.port=None
        self.gpsObject=None
        self.lastGPSData=None
        
    def __del__(self):
        self.exiting = True
        self.wait()
        
    def stop(self):
        if self.connected==True:
            self.disconnectGPS()
        self.exiting = True
        self.wait()
        
    def setup(self, connect):
        self.updateStatusLabel("GPS thread setup")

        self.lastGPSData=None
        self.exiting = False
        self.connected=False
        
        if connect==True:
            self.connectGPS()

        if self.connected==True:
            self.updateStatusLabel("GPS thread started")
            self.start()
                
    def updateStatusLabel(self, text):
        self.emit(SIGNAL("updateStatus(QString)"), text)
        
    def updateGPSThreadState(self, state):
        self.emit(SIGNAL("updateGPSThreadState(QString)"), state)

    def connectGPSFailed(self):
        self.emit(SIGNAL("connectGPSFailed()"))
    
    def updateGPSDisplay(self, gpsData):
        self.emit(SIGNAL("updateGPSDisplay(PyQt_PyObject)"), gpsData)
        
    def connectGPS(self):
        for device in self.deviceList:
            print("trying %s"%(device))
            if not os.path.exists(device):
                continue
            try:
                self.port=SerialPort(device, self.baud, self.timeout)
                self.connected=True
                self.gpsObject=GpsObject(self.port)
                print("Found NMEA gps device at %s"%(device))
                return
            except PortError:
                continue
        
        self.connectGPSFailed()
            
    def disconnectGPS(self):
        if self.connected==True:
            self.port.close()
            self.connected=False
            self.updateStatusLabel("GPS disconnect ok")
        
    def run(self):
        self.updateGPSThreadState(gpsRunState)

        while not self.exiting and True:
            if self.connected==True:
                try:
                    self.gpsObject.gps_device.handle_io()
                    gpsData=self.gpsObject.createGPSData()
                    if gpsData!=self.lastGPSData:
                        #print("update gps data")
                        self.updateGPSDisplay(gpsData)
                        self.lastGPSData=gpsData
                        
                except socket.timeout:
                    self.updateStatusLabel("GPS thread socket.timeout")
                    self.disconnectGPS()
                    self.updateGPSThreadState(gpsStoppedState)
                    self.updateGPSDisplay(None)
                    self.connectGPSFailed()
                    self.exiting=True
                    continue
                except socket.error:
                    self.updateStatusLabel("GPS thread socket.error")
                    self.disconnectGPS()
                    self.updateGPSThreadState(gpsStoppedState)
                    self.updateGPSDisplay(None)
                    self.connectGPSFailed()
                    self.exiting=True
                    continue

            else:
                self.msleep(1000)
            
        self.updateStatusLabel("GPS thread stopped")
        self.updateGPSThreadState(gpsStoppedState)
        self.updateGPSDisplay(None)
        
class GPSMonitor(QWidget):
    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.canMonitor=parent
        self.valueLabelList=list()
        self.globalDistance=0
        self.localDistance=0
        self.lastLat=0.0
        self.lastLon=0.0
        self.osmUtils=OSMUtils()
        
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
    
    def addToWidget(self, hbox):
        form=QFormLayout()
        form.setAlignment(Qt.AlignLeft|Qt.AlignTop)

        hbox.addLayout(form)
        
        self.createGPSLabel(form, "Latitude", "")
        self.createGPSLabel(form, "Longitude", "")
        self.createGPSLabel(form, "Altitude", "")
        self.createGPSLabel(form, "Speed", "")
        self.createGPSLabel(form, "Track", "")
        
        vbox=QVBoxLayout()
        vbox.setAlignment(Qt.AlignTop|Qt.AlignRight)

        self.compassGauge=QtPngCompassGauge(self.canMonitor, "compass", "compass1.png")
        self.compassGauge.setValue(0)
        self.compassGauge.setMaximumSize(300, 300)
        vbox.addWidget(self.compassGauge)

        self.speedDisplay=self.createLCD(QLCDNumber.Dec)
        self.speedDisplay.display(0)
        vbox.addWidget(self.speedDisplay)

        distanceBox=QHBoxLayout()
#        distanceBox.setAlignment(Qt.AlignLeft|Qt.AlignTop)

        resetDistanceButton=QPushButton("Reset", self.canMonitor)
        resetDistanceButton.clicked.connect(self._resetDistance)
        distanceBox.addWidget(resetDistanceButton)

        self.distanceLocalDisplay=self.createLCD(QLCDNumber.Dec)
        self.distanceLocalDisplay.display(self.localDistance)
        distanceBox.addWidget(self.distanceLocalDisplay)
        
        vbox.addLayout(distanceBox)

        self.distanceGlobalDisplay=self.createLCD(QLCDNumber.Dec)
        self.distanceGlobalDisplay.display(self.globalDistance)
        vbox.addWidget(self.distanceGlobalDisplay)
        hbox.addLayout(vbox)
    
    def updateDistanceDisplay(self, lat, lon):
        #print(self.distance)
        if self.lastLat==0.0 and self.lastLon==0.0:
            self.lastLat=lat
            self.lastLon=lon
            return
        if lat==0.0 or lon==0.0:
            return
            
        #print("%f-%f:%f-%f"%(self.lastLat, self.lastLon, lat, lon))      
        distance=self.osmUtils.distance(self.lastLat, self.lastLon, lat, lon)
        self.globalDistance=self.globalDistance+int(distance)
        self.distanceGlobalDisplay.display("%d"%(self.globalDistance))

        self.localDistance=self.localDistance+int(distance)
        self.distanceLocalDisplay.display("%d"%(self.localDistance))

        self.lastLat=lat
        self.lastLon=lon
        
    def updateGPSPositionTest(self, lat,lon):
        self.valueLabelList[0].setText(str(lat))
        self.valueLabelList[1].setText(str(lon))
   
        if not gps.isnan(lat) and not gps.isnan(lon):
            self.updateDistanceDisplay(lat, lon)

    def update(self, gpsData):
        if gpsData!=None:
            self.valueLabelList[0].setText(str(gpsData.lat))
            self.valueLabelList[1].setText(str(gpsData.lon))
            self.valueLabelList[2].setText(str(gpsData.altitude))
            self.valueLabelList[3].setText(str(gpsData.speed))
            self.valueLabelList[4].setText(str(gpsData.track))
            
            track=int(gpsData.track)
            self.compassGauge.setValue(track)
            
            speed=int(gpsData.speed)
            self.speedDisplay.display(speed)
                
            self.updateDistanceDisplay(gpsData.lat, gpsData.lon)
                
        else:
            self.valueLabelList[0].setText("")
            self.valueLabelList[1].setText("")
            self.valueLabelList[2].setText("")
            self.valueLabelList[3].setText("")
            self.valueLabelList[4].setText("")
            self.compassGauge.setValue(0)
            self.speedDisplay.display(0)
            
        if self.canMonitor.hasOSMWidget():
            self.canMonitor.osmWidget.updateGPSDataDisplay(gpsData, False)

    def loadConfig(self, config):
        self.globalDistance=config.getDefaultSection().getint("globalDistance", 0)
        self.localDistance=config.getDefaultSection().getint("localDistance", 0)
            
    def saveConfig(self, config):
        config.getDefaultSection()["globalDistance"]=str(self.globalDistance)
        config.getDefaultSection()["localDistance"]=str(self.localDistance)

    @pyqtSlot()
    def _resetDistance(self):
        self.lastLat=0.0
        self.lastLon=0.0
        self.localDistance=0
        self.distanceLocalDisplay.display("%d"%(self.localDistance))
        
    def _cleanup(self):
        None

class GPSSimpleMonitor(QWidget):
    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.valueLabelList=list()
        
    def createGPSLabel(self, form, key, value):
        lbl = QLabel(self)
        lbl.setMinimumHeight(50)
        font = lbl.font()
        font.setPointSize(14)
        lbl.setFont(font)
        lbl.setText(key)
        
        lbl2 = QLabel(self)
        lbl2.setMinimumHeight(50)
        font = lbl2.font()
        font.setPointSize(14)
        lbl2.setFont(font)
        lbl2.setText(value)
        self.valueLabelList.append(lbl2)

        form.addRow(lbl, lbl2)
        
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
    
    def addToWidget(self, hbox):
        form=QFormLayout()
        form.setAlignment(Qt.AlignLeft|Qt.AlignTop)

        hbox.addLayout(form)
        
        self.createGPSLabel(form, "Latitude", "")
        self.createGPSLabel(form, "Longitude", "")
        self.createGPSLabel(form, "Altitude", "")
        self.createGPSLabel(form, "Speed", "")
        self.createGPSLabel(form, "Track", "")
        
    def update(self, gpsData):
        if gpsData!=None:
            self.valueLabelList[0].setText(str(gpsData.lat))
            self.valueLabelList[1].setText(str(gpsData.lon))
            self.valueLabelList[2].setText(str(gpsData.altitude))
            self.valueLabelList[3].setText(str(gpsData.speed))
            self.valueLabelList[4].setText(str(gpsData.track))
                
        else:
            self.valueLabelList[0].setText("")
            self.valueLabelList[1].setText("")
            self.valueLabelList[2].setText("")
            self.valueLabelList[3].setText("")
            self.valueLabelList[4].setText("")
        
class GPSWindow(QMainWindow):
    def __init__(self, parent):
        QMainWindow.__init__(self, parent)
        font = self.font()
        font.setPointSize(14)
        self.setFont(font)
        self.incLat=0.0
        self.incLon=0.0
        self.connectGPSEnable=False
        self.config=Config()

        self.initUI()

    def initUI(self):
        mainWidget=QWidget()
        mainWidget.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)

        self.setCentralWidget(mainWidget)
        top=QVBoxLayout(mainWidget)        
        tabs = QTabWidget(self)
        top.addWidget(tabs)
        
        gpsTab = QWidget()
        gpsTabLayout=QHBoxLayout(gpsTab)
        gpsTabLayout.setAlignment(Qt.AlignLeft|Qt.AlignTop)

        tabs.addTab(gpsTab, "GSM")

        self.osmWidget=GPSMonitor(self)
        self.osmWidget.loadConfig(self.config)

        self.osmWidget.addToWidget(gpsTabLayout)
        
        self.zoom=9
        self.startLat=47.8
        self.startLon=13.0

        self.testGPSButton=QPushButton("Test GPS", self)
        self.testGPSButton.clicked.connect(self._testGPS)
        top.addWidget(self.testGPSButton)

        connectBox=QHBoxLayout()
        top.addLayout(connectBox)
 
        self.connectGPSButton = QCheckBox('GPS Connect', self)
        self.connectGPSButton.clicked.connect(self._connectGPS)
        self.connectGPSButton.setChecked(self.connectGPSEnable)
        connectBox.addWidget(self.connectGPSButton)
        self.setGeometry(0, 0, 800, 400)
        self.setWindowTitle('GPS Test')
        
        self.updateGPSThread=GPSUpateWorkerGPSD(self)
        self.connect(self.updateGPSThread, SIGNAL("updateStatus(QString)"), self.updateStatusLabel)
        self.connect(self.updateGPSThread, SIGNAL("connectGPSFailed()"), self.connectGPSFailed)
        self.connect(self.updateGPSThread, SIGNAL("updateGPSDisplay(PyQt_PyObject)"), self.updateGPSDisplay)
        self._connectGPS()
        
        self.show()
        
    @pyqtSlot()
    def _testGPS(self):
        if self.incLat==0.0:
            self.incLat=self.startLat
        if self.incLon==0.0:
            self.incLon=self.startLon
            
        self.incLat=self.incLat+0.001
        self.incLon=self.incLon+0.001
        self.osmWidget.updateGPSPositionTest(self.incLat, self.incLon) 
        
    def updateStatusLabel(self, text):
        print(text)

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
                
    def updateGPSDisplay(self, gpsData):
        self.osmWidget.update(gpsData)
        
    def connectGPSFailed(self):
        self.connectGPSButton.setChecked(False)
        self.connectGPSEnable=False
#        self.connectGPSButton.setDisabled(False)
    
    def connectGPSSuccesful(self):
        self.connectGPSButton.setChecked(True)
        self.connectGPSEnable=True
#        self.connectGPSButton.setDisabled(False)
        
    def connectGPSEnabled(self):
        return self.connectGPSEnable
    
#    def stopGPSSuccesful(self):
#        self.connectGPSButton.setDisabled(False)

    def hasOSMWidget(self):
        return False
        
    @pyqtSlot()
    def _cleanup(self):
        if self.updateGPSThread.isRunning():
            self.updateGPSThread.stop()
            
        self.osmWidget.saveConfig(self.config)
        self.config.writeConfig()

def main(argv): 
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)

    widget1 = GPSWindow(None)
    app.aboutToQuit.connect(widget1._cleanup)

    sys.exit(app.exec_())

if __name__ == "__main__":
    main(sys.argv)
