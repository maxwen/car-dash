'''
Created on Dec 7, 2011

@author: maxl
'''

from gps import gps, misc
import socket
import signal
import sys

from PyQt4.QtCore import SIGNAL, QThread, Qt, pyqtSlot
from PyQt4.QtGui import QCheckBox, QPalette, QApplication, QTabWidget, QSizePolicy, QMainWindow, QPushButton, QWidget, QHBoxLayout, QVBoxLayout, QFormLayout, QLCDNumber, QLabel
from gaugecompass import QtPngCompassGauge
from osmparser.osmutils import OSMUtils
from config import Config

gpsIdleState="idle"
gpsRunState="run"
gpsStoppedState="stopped"

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
    
    def updateGPSDisplay(self, session):
        self.emit(SIGNAL("updateGPSDisplay(PyQt_PyObject)"), session)
        
    def connectGPS(self):
        if self.session==None:
            try:
                self.session = gps.gps()
                self.updateStatusLabel("GPS connect ok")
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
        
    def run(self):
        self.updateGPSThreadState(gpsRunState)

        while not self.exiting and True:
            if self.connected==True and self.session!=None:
                try:
                    self.session.__next__()
                    self.updateGPSDisplay(self.session)
                    self.updateGPSThreadState(gpsRunState)
                except StopIteration:
                    self.updateStatusLabel("GPS connection lost")
                    self.updateGPSThreadState(gpsIdleState)
                    self.connected=False
                    self.session=None
                    self.reconnectGPS()
                except socket.timeout:
                    self.updateStatusLabel("GPS thread socket.timeout")
                    self.updateGPSThreadState(gpsIdleState)
                    continue
                except socket.error:
                    if self.exiting==True:
                        self.updateStatusLabel("GPS thread stop request")
                        continue
            else:
                self.updateStatusLabel("GPS thread idle")
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
        
        self.createGPSLabel(form, "Status", "Not connected")
        self.createGPSLabel(form, "Latitude", "")
        self.createGPSLabel(form, "Longitude", "")
        self.createGPSLabel(form, "Time UTC", "")
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
        self.valueLabelList[0].setText("Connected test")
        self.valueLabelList[1].setText(str(lat))
        self.valueLabelList[2].setText(str(lon))
   
        if not gps.isnan(lat) and not gps.isnan(lon):
            self.updateDistanceDisplay(lat, lon)

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
            
            speed=0
            altitude=0
            track=0
            self.valueLabelList[3].setText(timeString)
            self.valueLabelList[4].setText(str(session.fix.altitude))
            self.valueLabelList[5].setText(str(session.fix.speed))
            #self.valueLabelList[6].setText(str(session.fix.climb))
            self.valueLabelList[6].setText(str(session.fix.track))
            
            if not gps.isnan(session.fix.track):
                track=int(session.fix.track)
            
            self.compassGauge.setValue(track)
                
            if not gps.isnan(session.fix.speed):
                speed=int(session.fix.speed*3.6)
            
            self.speedDisplay.display(speed)

            if not gps.isnan(session.fix.altitude):
                altitude=session.fix.altitude
                
            if self.canMonitor.hasOSMWidget():
                if not gps.isnan(session.fix.latitude) and not gps.isnan(session.fix.longitude):
                    self.canMonitor.osmWidget.updateGPSDataDisplay(session.fix.latitude, session.fix.longitude, altitude, speed, track)
                else:
                    self.canMonitor.osmWidget.updateGPSDataDisplay(0.0, 0.0, altitude, speed, track)

            if not gps.isnan(session.fix.latitude) and not gps.isnan(session.fix.longitude):
                self.updateDistanceDisplay(session.fix.latitude, session.fix.longitude)
#            else:
#                self.distanceDisplay.setValue(0)

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
            
            if self.canMonitor.hasOSMWidget():
                self.canMonitor.osmWidget.updateGPSDataDisplay(0.0, 0.0, 0, 0, 0)

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
        
        self.createGPSLabel(form, "Status", "Not connected")
        self.createGPSLabel(form, "Latitude", "")
        self.createGPSLabel(form, "Longitude", "")
        self.createGPSLabel(form, "Time UTC", "")
        self.createGPSLabel(form, "Altitude", "")
        self.createGPSLabel(form, "Speed", "")
        self.createGPSLabel(form, "Track", "")
        
    def update(self, session):
        if session!=None:
            self.valueLabelList[0].setText("Connected ("+str(session.satellites_used)+" satelites)")
            self.valueLabelList[1].setText(str(session.fix.latitude))
            self.valueLabelList[2].setText(str(session.fix.longitude))
            
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
            self.valueLabelList[6].setText(str(session.fix.track))
                
        else:
            self.valueLabelList[0].setText("Not connected")
            self.valueLabelList[1].setText("")
            self.valueLabelList[2].setText("")
            self.valueLabelList[3].setText("")
            self.valueLabelList[4].setText("")
            self.valueLabelList[5].setText("")
            self.valueLabelList[6].setText("")
        
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
        
        self.updateGPSThread=GPSMonitorUpateWorker(self)
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
                
    def updateGPSDisplay(self, session):
        self.osmWidget.update(session)
        
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
