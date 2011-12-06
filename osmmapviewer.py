'''
Created on Dec 3, 2011

@author: maxl
'''

import sys
import math
import os
import signal
import http.client
import io
import socket

from PyQt4.QtCore import Qt, QSize, pyqtSlot, SIGNAL, QRect, QPoint
from PyQt4.QtGui import QMainWindow, QTabWidget, QCheckBox, QPalette, QVBoxLayout, QPushButton, QWidget, QPixmap, QSizePolicy, QPainter, QPen, QHBoxLayout, QApplication

TILESIZE=256
M_LN2=0.69314718055994530942    #log_e 2
minWidth=500
minHeight=300
EXTRA_BORDER=0
MIN_ZOOM=1
MAX_ZOOM=18
MAP_SCROLL_STEP=10
tileHome="/Maps/osm/tiles/"
tileServer="tile.openstreetmap.org"

class OSMUtils():
    def deg2rad(self, deg):
        return (deg * math.pi / 180.0)

    def rad2deg(self,  rad):
        return (rad / math.pi * 180.0)

    def lat2pixel(self, zoom, lat):
        lat_m = math.atanh(math.sin(lat))
        # the formula is
        #
        # pixel_y = -(2^zoom * TILESIZE * lat_m) / 2PI + (2^zoom * TILESIZE) / 2
        #
        pixel_y = -(lat_m * TILESIZE * (1 << zoom) ) / (2*math.pi) +((1 << zoom) * (TILESIZE/2) )

        return pixel_y

    def lon2pixel(self, zoom, lon):
        #the formula is
        #
        # pixel_x = (2^zoom * TILESIZE * lon) / 2PI + (2^zoom * TILESIZE) / 2
        #
        pixel_x = ( lon * TILESIZE * (1 << zoom) ) / (2*math.pi) +( (1 << zoom) * (TILESIZE/2) )
        return pixel_x

    def pixel2lon(self, zoom, pixel_x):
        lon = (((pixel_x - ( math.exp(zoom * M_LN2) * (TILESIZE/2) ) ) *2*math.pi) / 
            (TILESIZE * math.exp(zoom * M_LN2) ))
        return lon

    def pixel2lat(self, zoom, pixel_y):
        lat_m = ((-( pixel_y - ( math.exp(zoom * M_LN2) * (TILESIZE/2) ) ) * (2*math.pi)) /
            (TILESIZE * math.exp(zoom * M_LN2)))

        lat = math.asin(math.tanh(lat_m))
        return lat
    
class QtOSMWidget(QWidget):
    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.map_x=0
        self.map_y=0
        self.map_zoom=3
        self.min_zoom=MIN_ZOOM
        self.max_zoom=MAX_ZOOM
        self.center_rlat = 0.0
        self.center_rlon=0.0
        self.gpsLatitude=0.0
        self.gpsLongitude=0.0
        self.osmutils=OSMUtils()
#        self.init()
        self.tileCache=dict()
        self.withMapnik=False
        self.withDownload=False
        self.serverChecked=False
        self.autocenterGPS=False
        self.gpsPointImage=QPixmap("images/gps-point.png")
        self.osmControlImage=QPixmap("images/osm-control.png")
        self.controlWidgetRect=QRect(0, 0, self.osmControlImage.width(), self.osmControlImage.height())
        self.zoomRect=QRect(0, 70, 70, 50)
        self.minusRect=QRect(5, 70, 22, 22)
        self.plusRect=QRect(35, 70, 22, 22)
        self.moveRect=QRect(0, 0, 70, 61)
        self.leftRect=QRect(0, 20, 20, 20)
        self.rightRect=QRect(40, 20, 20, 20)
        self.upRect=QRect(20, 0, 20, 20)
        self.downRect=QRect(20, 40, 20, 20)
        
    def getTileHome(self):
        return os.environ['HOME']+tileHome
    
    def init(self):
        self.setMinimumWidth(minWidth)
        self.setMinimumHeight(minHeight)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)        
        self.updateGeometry()
        #self.update()
        
    def osm_gps_map_set_center(self, latitude, longitude):
        self.center_rlat = self.osmutils.deg2rad(latitude)
        self.center_rlon = self.osmutils.deg2rad(longitude)

#        print("%f %f %d"%(self.center_rlat, self.center_rlon, self.map_zoom))

        pixel_x = self.osmutils.lon2pixel(self.map_zoom, self.center_rlon)
        pixel_y = self.osmutils.lat2pixel(self.map_zoom, self.center_rlat)
#        print("%d %d"%(pixel_x, pixel_y))

        self.map_x = int(pixel_x - self.width()/2)
        self.map_y = int(pixel_y - self.height()/2)
        
#        print("after center %f %f %d %d %d"%(latitude, longitude, self.map_x, self.map_y, self.map_zoom))
        
    def osm_gps_map_set_zoom (self, zoom):
        width_center  = self.width() / 2
        height_center = self.height() / 2

        self.map_zoom = self.CLAMP(zoom, self.min_zoom, self.max_zoom)
        self.map_x = self.osmutils.lon2pixel(self.map_zoom, self.center_rlon) - width_center
        self.map_y = self.osmutils.lat2pixel(self.map_zoom, self.center_rlat) - height_center
        
    def osm_gps_map_handle_resize (self):
        width_center  = self.width() / 2
        height_center = self.height() / 2

        self.map_x = self.osmutils.lon2pixel(self.map_zoom, self.center_rlon) - width_center
        self.map_y = self.osmutils.lat2pixel(self.map_zoom, self.center_rlat) - height_center

#        print("after zoom %d %d %d"%(self.map_x, self.map_y, self.map_zoom))

    def CLAMP(self, x, low, high):
        if x>high:
            return high
        elif x<low:
            return low
        return x

    def osm_gps_map_fill_tiles_pixel (self):
#        print("Fill tiles: %d,%d z:%d"% (self.map_x, self.map_y, self.map_zoom))
#        print(self.geometry())

        offset_x = - self.map_x % TILESIZE;
        offset_y = - self.map_y % TILESIZE;
        
        if offset_x > 0:
            offset_x -= TILESIZE
        if offset_y > 0:
            offset_y -= TILESIZE

        offset_xn = offset_x + EXTRA_BORDER
        offset_yn = offset_y + EXTRA_BORDER
                
        tiles_nx = int((self.width()  - offset_x) / TILESIZE + 1)
        tiles_ny = int((self.height() - offset_y) / TILESIZE + 1)

        tile_x0 =  int(math.floor(self.map_x / TILESIZE))
        tile_y0 =  int(math.floor(self.map_y / TILESIZE))

        i=tile_x0
        j=tile_y0
        
#        print("%d %d %d %d"%(tile_x0, tile_y0, tiles_nx, tiles_ny))
        while i<(tile_x0+tiles_nx):
            while j<(tile_y0+tiles_ny):
#                print("%d %d"%(i, j))
                if j<0 or i<0 or i>=math.exp(self.map_zoom * M_LN2) or j>=math.exp(self.map_zoom * M_LN2):
#                    print("else")
                    pen=QPen()
                    palette=QPalette()
                    pen.setColor(palette.color(QPalette.Normal, QPalette.Background))
                    self.painter.setPen(pen)
                    self.painter.drawRect(offset_xn, offset_yn, TILESIZE, TILESIZE)
                else:
#                    print("load tile %d %d %d %d %d"%(self.map_zoom, i, j, offset_xn, offset_yn))
                    self.osm_gps_get_tile(self.map_zoom, i,j, offset_xn, offset_yn)
                                      
                offset_yn += TILESIZE
                j=j+1
            offset_xn += TILESIZE
            offset_yn = offset_y+EXTRA_BORDER
            i=i+1
            j=tile_y0
    
    def drawTile(self, fileName, offset_x, offset_y):
#        print("draw %s at %d %d"%(fileName, offset_x, offset_y))

        if not fileName in self.tileCache:
            pixbuf = QPixmap(fileName)
            self.tileCache[fileName]=pixbuf
        else:
            pixbuf=self.tileCache[fileName]
            
        self.painter.drawPixmap(offset_x, offset_y, TILESIZE, TILESIZE, pixbuf)

    def osm_gps_get_tile(self, zoom, x, y, offset_x, offset_y):
        fileName=self.getTileHome()+str(zoom)+"/"+str(x)+"/"+str(y)+".png"
        if os.path.exists(fileName):
            self.drawTile(fileName, offset_x, offset_y)
        else:
            if self.withDownload==True:
                self.callDownloadForTile("/"+str(zoom)+"/"+str(x)+"/"+str(y)+".png", fileName)
                if os.path.exists(fileName):
                    self.drawTile(fileName, offset_x, offset_y)
                    
            elif self.withMapnik==True:
                self.callMapnikForTile()
                if os.path.exists(fileName):
                    self.drawTile(fileName, offset_x, offset_y)
            else:
                pen=QPen()
                palette=QPalette()
                pen.setColor(palette.color(QPalette.Normal, QPalette.Background))
                self.painter.setPen(pen)
                self.painter.drawRect(offset_x, offset_y, TILESIZE, TILESIZE)
            
    def osm_gps_show_location(self):
        if self.gpsLongitude==0.0 and self.gpsLatitude==0.0:
            return
        pen=QPen()
        pen.setColor(Qt.red)
        pen.setWidth(10)
        self.painter.setPen(pen)
 
        map_x0 = self.map_x - EXTRA_BORDER
        map_y0 = self.map_y - EXTRA_BORDER
        x = self.osmutils.lon2pixel(self.map_zoom, self.gpsLongitude) - map_x0
        y = self.osmutils.lat2pixel(self.map_zoom, self.gpsLatitude) - map_y0

        self.painter.drawPixmap(x-self.gpsPointImage.width()/2, y-self.gpsPointImage.height()/2, self.gpsPointImage)
#        self.painter.drawPoint(x, y)
        
    def osm_autocenter_map(self):
        if self.gpsLatitude!=0.0 and self.gpsLongitude!=0.0:
            pixel_x = self.osmutils.lon2pixel(self.map_zoom, self.gpsLongitude)
            pixel_y = self.osmutils.lat2pixel(self.map_zoom, self.gpsLatitude)
            x = pixel_x - self.map_x
            y = pixel_y - self.map_y
            width = self.width()
            height = self.height()
            if x < (width/2 - width/8) or x > (width/2 + width/8) or y < (height/2 - height/8) or y > (height/2 + height/8):
                self.map_x = pixel_x - width/2;
                self.map_y = pixel_y - height/2;
                self.center_coord_update();
            self.update()
        
    def show(self, zoom, lat, lon):
        self.osm_gps_map_set_center(lat, lon)
        self.osm_gps_map_set_zoom(zoom)
        self.update()
    
    def zoom(self, zoom):
        self.osm_gps_map_set_zoom(zoom)
        self.update()
       
    def resizeEvent(self, event):
        self.osm_gps_map_handle_resize()
             
    def paintEvent(self, event):
#        print("%d-%d"%(self.width(), self.height()))
#        print(self.pos())
#        self.updateGeometry()
        self.painter=QPainter(self) 
        self.osm_gps_map_fill_tiles_pixel()
        self.osm_gps_show_location()
        self.showControlOverlay()
        self.painter.end()
                    
    def minimumSizeHint(self):
        return QSize(minWidth, minHeight)

#    def sizeHint(self):
#        return QSize(800, 300)

    def center_coord_update(self):
        pixel_x = self.map_x + self.width()/2
        pixel_y = self.map_y + self.height()/2

        self.center_rlon = self.osmutils.pixel2lon(self.map_zoom, pixel_x)
        self.center_rlat = self.osmutils.pixel2lat(self.map_zoom, pixel_y)

    def stepUp(self, step):
        self.map_y -= step
        self.center_coord_update()
        self.update()

    def stepDown(self, step):
        self.map_y += step
        self.center_coord_update()
        self.update()

    def stepLeft(self, step):
        self.map_x -= step
        self.center_coord_update()
        self.update()

    def stepRight(self, step):
        self.map_x += step
        self.center_coord_update()
        self.update()

    def updateGPSLocation(self, lat, lon):
#        print("%f-%f"%(lat,lon))
        if lat!=0.0 and lon!=0.0:
            gpsLatitudeNew=self.osmutils.deg2rad(lat)
            gpsLongitudeNew=self.osmutils.deg2rad(lon)
            
            if self.gpsLatitude!=gpsLatitudeNew or self.gpsLongitude!=gpsLongitudeNew:
                self.gpsLatitude=gpsLatitudeNew
                self.gpsLongitude=gpsLongitudeNew
                if self.autocenterGPS==True:
                    self.osm_autocenter_map()
                else:
                    self.update()   
    
    def cleanImageCache(self):
        self.tileCache.clear()
            
    def callMapnikForTile(self):
        lat=self.osmutils.rad2deg(self.center_rlat)
        lon=self.osmutils.rad2deg(self.center_rlon)

        exexStr=os.getcwd()+"/mapnik_wrapper.sh "+ str(lon-0.005)+ " "+str(lat-0.005)+" "+str(lon+0.005)+" "+str(lat+0.005)+" "+str(self.map_zoom)
        print(exexStr)
        os.system(exexStr)
        
    def checkDownloadServer(self):
        self.serverChecked=True
        try:
            x=socket.gethostbyname(tileServer)
#            print(x)
        except socket.error:
            print("Check tile download server failed. Disabling")
            self.withDownload=True
    
    
    def callDownloadForTile(self, tilePath, fileName):
        if self.serverChecked==False:
            self.checkDownloadServer()
            
        if self.withDownload==True:
            try:
                httpConn = http.client.HTTPConnection(tileServer)
                httpConn.connect()
                httpConn.request("GET", tilePath)
                response = httpConn.getresponse()
                if response.status==http.client.OK:
                    self.updateStatusLabel("downloaded "+fileName)
                    data = response.read()
                    try:
                        os.makedirs(os.path.dirname(fileName))
                    except OSError:
                        #ignore
                        None
                    try:
                        stream=io.open(fileName, "wb")
                        stream.write(data)
                    except IOError:
                        #ignore
                        None
        
                httpConn.close()
            except socket.error:
                print("disable download")
                self.withDownload=False
                
    def setDownloadTiles(self, value):
        self.withDownload=value
        if value==True:
            self.update()
        
    def setAutocenterGPS(self, value):
        self.autocenterGPS=value
        if value==True:
            self.osm_autocenter_map()
        
    def updateStatusLabel(self, text):
        self.emit(SIGNAL("updateStatus(QString)"), text)

    def mouseReleaseEvent(self, event ):
        if self.controlWidgetRect.contains(event.x(), event.y()):
            self.pointInsideMoveOverlay(event.x(), event.y())
            self.pointInsideZoomOverlay(event.x(), event.y())
#        else:
#            print("outside control")
            
    def pointInsideMoveOverlay(self, x, y):
        if self.moveRect.contains(x, y):
            if self.leftRect.contains(x, y):
#                print("left")
                self.stepLeft(MAP_SCROLL_STEP)
            if self.rightRect.contains(x, y):
#                print("right")
                self.stepRight(MAP_SCROLL_STEP)
            if self.upRect.contains(x, y):
#                print("up")
                self.stepUp(MAP_SCROLL_STEP)
            if self.downRect.contains(x, y):
#                print("down")
                self.stepDown(MAP_SCROLL_STEP)
        
    def pointInsideZoomOverlay(self, x, y):
        if self.zoomRect.contains(x, y):
            if self.minusRect.contains(x, y):
#                print("zoom -")
                zoom=self.map_zoom-1
                if zoom<MIN_ZOOM:
                    zoom=MIN_ZOOM
                self.zoom(zoom)
                
            if self.plusRect.contains(x,y):
#                print("zoom +")
                zoom=self.map_zoom+1
                if zoom>MAX_ZOOM:
                    zoom=MAX_ZOOM
                self.zoom(zoom)
        
    def showControlOverlay(self):
        self.painter.drawPixmap(0, 0, self.osmControlImage)


class OSMWidget(QWidget):
    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.zoom=1
        self.startLat=0.0
        self.startLon=0.0
        self.autocenterGPS=False
        self.withDownload=False
        
    def addToWidget(self, parent):       
        self.mapWidgetQt=QtOSMWidget(self)
        parent.addWidget(self.mapWidgetQt)
        
        vbox=QHBoxLayout()
        vbox.setAlignment(Qt.AlignLeft)
        parent.addLayout(vbox)
 
#        self.zoomInButton=QPushButton("+", self)
#        self.zoomInButton.clicked.connect(self._zoomIn)
#        vbox.addWidget(self.zoomInButton)
#        
#        self.zoomOutButton=QPushButton("-", self)
#        self.zoomOutButton.clicked.connect(self._zoomOut)
#        vbox.addWidget(self.zoomOutButton)
#        
#        self.stepUpButton=QPushButton("Up", self)
#        self.stepUpButton.clicked.connect(self._stepUp)
#        vbox.addWidget(self.stepUpButton)
#        
#        self.stepDownButton=QPushButton("Down", self)
#        self.stepDownButton.clicked.connect(self._stepDown)
#        vbox.addWidget(self.stepDownButton)
#        
#        self.stepLeftButton=QPushButton("Left", self)
#        self.stepLeftButton.clicked.connect(self._stepLeft)
#        vbox.addWidget(self.stepLeftButton)
#        
#        self.stepRightButton=QPushButton("Right", self)
#        self.stepRightButton.clicked.connect(self._stepRight)
#        vbox.addWidget(self.stepRightButton)
        
        self.centerGPSButton=QPushButton("Center GPS", self)
        self.centerGPSButton.clicked.connect(self._centerGPS)
        vbox.addWidget(self.centerGPSButton)
        
        self.followGPSButton=QCheckBox("Follow GPS", self)
        self.followGPSButton.clicked.connect(self._followGPS)
        vbox.addWidget(self.followGPSButton)
        
        self.downloadTilesButton=QCheckBox("Download", self)
        self.downloadTilesButton.clicked.connect(self._downloadTiles)
        vbox.addWidget(self.downloadTilesButton)


    def init(self, lat, lon, zoom):        
        self.zoom=zoom
        self.startLat=lat
        self.startLon=lon
        
        self.mapWidgetQt.init()
        self.mapWidgetQt.updateGPSLocation(self.startLat, self.startLon)
        self.mapWidgetQt.show(self.zoom, self.startLat, self.startLon)

    def initHome(self):        
        self.zoom=9
        self.startLat=47.8
        self.startLon=13.0
        
        self.mapWidgetQt.init()
        self.mapWidgetQt.updateGPSLocation(self.startLat, self.startLon)
        self.mapWidgetQt.show(self.zoom, self.startLat, self.startLon)

    def initUI(self):
        hbox = QVBoxLayout()

        self.addToWidget(hbox)
        self.setLayout(hbox)
        
        self.initHome()

#        self.setGeometry(0, 0, 860, 500)
        self.setWindowTitle('OSM Test')
        self.show()
        
#    @pyqtSlot()
#    def _zoomIn(self):
#        self.zoom=self.zoom+1
#        if self.zoom>MAX_ZOOM:
#            self.zoom=MAX_ZOOM
#        self.mapWidgetQt.zoom(self.zoom)
#        
#    @pyqtSlot()
#    def _zoomOut(self):
#        self.zoom=self.zoom-1
#        if self.zoom<MIN_ZOOM:
#            self.zoom=MIN_ZOOM
#        self.mapWidgetQt.zoom(self.zoom)
#
#    @pyqtSlot()
#    def _stepUp(self):
#        self.mapWidgetQt.stepUp(MAP_SCROLL_STEP)
#
#    @pyqtSlot()
#    def _stepDown(self):
#        self.mapWidgetQt.stepDown(MAP_SCROLL_STEP)
#        
#    @pyqtSlot()
#    def _stepLeft(self):
#        self.mapWidgetQt.stepLeft(MAP_SCROLL_STEP)
#        
#    @pyqtSlot()
#    def _stepRight(self):
#        self.mapWidgetQt.stepRight(MAP_SCROLL_STEP)  
    
    @pyqtSlot()
    def _centerGPS(self):
        self.mapWidgetQt.osm_autocenter_map()   
    
    @pyqtSlot()
    def _followGPS(self):
        self.autocenterGPS=self.followGPSButton.isChecked()
        self.mapWidgetQt.setAutocenterGPS(self.autocenterGPS)   
                    
    def updateGPSPosition(self, lat, lon):
        self.mapWidgetQt.updateGPSLocation(lat, lon)

    @pyqtSlot()
    def _downloadTiles(self):
        self.withDownload=self.downloadTilesButton.isChecked()
        self.mapWidgetQt.setDownloadTiles(self.withDownload)   

        
class OSMWindow(QMainWindow):
    def __init__(self):
        super(OSMWindow, self).__init__()
        self.initUI()

    def initUI(self):
        mainWidget=QWidget()
        mainWidget.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)

        self.setCentralWidget(mainWidget)
        top=QVBoxLayout(mainWidget)        
        tabs = QTabWidget(self)
        top.addWidget(tabs)
        
        osmTab = QWidget()
        osmTabLayout=QVBoxLayout(osmTab)
        osmTabLayout.setAlignment(Qt.AlignLeft|Qt.AlignTop)

        tabs.addTab(osmTab, "OSM")

        self.mapWidget=OSMWidget(self)
        self.mapWidget.addToWidget(osmTabLayout)
        self.connect(self.mapWidget.mapWidgetQt, SIGNAL("updateStatus(QString)"), self.updateStatusBarLabel)

        
        self.zoom=9
        self.startLat=47.8
        self.startLon=13.0
        self.mapWidget.initHome()

        self.incLat=47.8
        self.incLon=13.0
        self.testGPSButton=QPushButton("Test GPS", self)
        self.testGPSButton.clicked.connect(self._testGPS)
        top.addWidget(self.testGPSButton)

#        self.setGeometry(0, 0, 800, 400)
        self.setWindowTitle('OSM Test')
        self.show()
        
    @pyqtSlot()
    def _testGPS(self):
        self.incLat=self.incLat+0.001
        self.incLon=self.incLon+0.001
        self.mapWidget.updateGPSPosition(self.incLat, self.incLon)   

    def updateStatusBarLabel(self, text):
        print(text)

#        os.execl(os.getcwd()+"/mapnik_wrapper.sh", "9", "46", "17", "49", "2")

def main(argv): 
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
#    widget = OSMWidget(None)
#    widget.initUI()

    widget1 = OSMWindow()
    widget1.initUI()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main(sys.argv)
