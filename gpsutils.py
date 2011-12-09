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
from osmmapviewer import OSMUtils

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
                except socket.timeout:
                    self.updateStatusLabel("GPS thread socket.timeout")
                    continue
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
        self.distance=0.0
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
        vbox.setAlignment(Qt.AlignRight|Qt.AlignTop)

        self.compassGauge=QtPngCompassGauge(self.canMonitor, "compass", "compass.png")
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

        self.distanceDisplay=self.createLCD(QLCDNumber.Dec)
        self.distanceDisplay.display(self.distance)
        distanceBox.addWidget(self.distanceDisplay)
        
        vbox.addLayout(distanceBox)

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
        self.distance=self.distance+self.osmUtils.distance(self.lastLat, self.lastLon, lat, lon)
        self.distanceDisplay.display("%.0f"%(self.distance))

        self.lastLat=lat
        self.lastLon=lon
    
    def distance(self):
        return self.distance
              
    def setDistance(self, distance):
        print(distance)
        self.distanceDisplay.display(distance)
        
    def updateGPSPosition(self, lat,lon):
            self.valueLabelList[0].setText("Connected test")
            self.valueLabelList[1].setText(str(lat))
            self.valueLabelList[2].setText(str(lon))
       
            if not gps.isnan(lat) and not gps.isnan(lon):
                self.updateDistanceDisplay(lat, lon)
#            else:
#                self.distanceDisplay.setValue(0)

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
            self.canMonitor.osmWidget.updateGPSPosition(0.0, 0.0)

    def loadConfig(self, config):
        self.distance=config.getDefaultSection().getfloat("distance", 0.0)
            
    def saveConfig(self, config):
        config.getDefaultSection()["distance"]=str(self.distance)

    @pyqtSlot()
    def _resetDistance(self):
        self.lastLat=0.0
        self.lastLon=0.0
        self.distance=0.0
        self.distanceDisplay.display("%.0f"%(self.distance))
        
class GPSWindow(QMainWindow):
    def __init__(self, parent):
        QMainWindow.__init__(self, parent)
        font = self.font()
        font.setPointSize(14)
        self.setFont(font)
        self.incLat=0.0
        self.incLon=0.0
        self.connectGPSEnable=False
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

        self.gpsWidget=GPSMonitor(self)
        self.gpsWidget.addToWidget(gpsTabLayout)

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
#        self.setGeometry(0, 0, 800, 400)
        self.setWindowTitle('GPS Test')
        self.updateGPSThread=GPSMonitorUpateWorker(self)
        self.connect(self.updateGPSThread, SIGNAL("updateStatus(QString)"), self.updateStatusLabel)
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
        self.gpsWidget.updateGPSPosition(self.incLat, self.incLon) 
        
    def updateStatusLabel(self, text):
        print(text)

    @pyqtSlot()
    def _connectGPS(self):
        self.connectGPSEnable=self.connectGPSButton.isChecked()
        if self.connectGPSEnable==True:
            self.connectGPSButton.setDisabled(True)
            self.updateGPSThread.setup(self)
        else:
            if self.updateGPSThread.isRunning():
                self.connectGPSButton.setDisabled(True)
                self.updateGPSThread.stop()
                
    def updateGPSDisplay(self, session):
        self.gpsWidget.update(session)
        
    def connectGPSFailed(self):
        self.connectGPSButton.setChecked(False)
        self.connectGPSEnable=False
        self.connectGPSButton.setDisabled(False)
    
    def connectGPSSuccesful(self):
        self.connectGPSButton.setChecked(True)
        self.connectGPSEnable=True
        self.connectGPSButton.setDisabled(False)
        
    def connectGPSEnabled(self):
        return self.connectGPSEnable
    
    def stopGPSSuccesful(self):
        self.connectGPSButton.setDisabled(False)
#        os.execl(os.getcwd()+"/mapnik_wrapper.sh", "9", "46", "17", "49", "2")

def main(argv): 
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
#    widget = OSMWidget(None)
#    widget.initUI()

    widget1 = GPSWindow(None)
    widget1.initUI()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main(sys.argv)
