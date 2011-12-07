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
from collections import deque

from PyQt4.QtCore import QEvent, Qt, QSize, pyqtSlot, SIGNAL, QRect, QThread
from PyQt4.QtGui import QToolTip, QMenu, QAction, QMainWindow, QTabWidget, QCheckBox, QPalette, QVBoxLayout, QPushButton, QWidget, QPixmap, QSizePolicy, QPainter, QPen, QHBoxLayout, QApplication

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

class OSMDownloadTilesWorker(QThread):
    def __init__(self, parent=None): 
        QThread.__init__(self, parent)
        self.exiting = False
        self.downloadQueue=deque()
        
    def __del__(self):
        self.exiting = True
        self.wait()
        
    def setup(self):
        self.updateStatusLabel("OSM starting download thread")
        self.exiting = False
        self.start()
            
    def updateStatusLabel(self, text):
        self.emit(SIGNAL("updateStatus(QString)"), text)

    def updateMap(self):
        self.emit(SIGNAL("updateMap()"))
 
    def stop(self):
        self.exiting = True
        self.wait()

    def addTile(self, tilePath, fileName):
        self.downloadQueue.append([tilePath, fileName])
        
    def downloadTile(self, tilePath, fileName):
        try:
            httpConn = http.client.HTTPConnection(tileServer)
            httpConn.connect()
            httpConn.request("GET", tilePath)
            response = httpConn.getresponse()
            if response.status==http.client.OK:
                self.updateStatusLabel("OSM downloaded "+fileName)
                data = response.read()
                try:
                    os.makedirs(os.path.dirname(fileName))
                except OSError:
                    #ignore
                    None
                try:
                    stream=io.open(fileName, "wb")
                    stream.write(data)
                    self.updateMap()
                except IOError:
                    #ignore
                    None
    
            httpConn.close()
        except socket.error:
            self.updateStatusLabel("OSM download error")
                
    def run(self):
        while not self.exiting and True:
            if len(self.downloadQueue)!=0:
                entry=self.downloadQueue.popleft()
                self.downloadTile(entry[0], entry[1])
                continue
            
            self.msleep(500) 
        
        self.updateStatusLabel("OSM stoping download thread")


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
        self.osmWidget=parent
        self.map_x=0
        self.map_y=0
        self.map_zoom=9
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
        self.gpsPointImage=QPixmap("images/gps-point-big.png")
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
        
        self.setContextMenuPolicy(Qt.DefaultContextMenu)
        self.moving=False
        self.setMouseTracking(True)
        self.posStr="+%.4f , +%.4f" % (0.0, 0.0)

        
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

    def drawEmptyTile(self, zoom, x, y, offset_x, offset_y):
        pen=QPen()
        palette=QPalette()
        pen.setColor(palette.color(QPalette.Normal, QPalette.Background))
        self.painter.setPen(pen)
        self.painter.drawRect(offset_x, offset_y, TILESIZE, TILESIZE)

    def osm_gps_get_tile(self, zoom, x, y, offset_x, offset_y):
        fileName=self.getTileHome()+str(zoom)+"/"+str(x)+"/"+str(y)+".png"
        if os.path.exists(fileName):
            self.drawTile(fileName, offset_x, offset_y)
        else:
            if self.withDownload==True:
                self.osmWidget.downloadThread.addTile("/"+str(zoom)+"/"+str(x)+"/"+str(y)+".png", fileName)
                self.drawEmptyTile(zoom, x, y, offset_x, offset_y)
#                self.callDownloadForTile("/"+str(zoom)+"/"+str(x)+"/"+str(y)+".png", fileName)
#                if os.path.exists(fileName):
#                    self.drawTile(fileName, offset_x, offset_y)
                    
            elif self.withMapnik==True:
                self.callMapnikForTile()
                if os.path.exists(fileName):
                    self.drawTile(fileName, offset_x, offset_y)
            else:
                # TODO upscale lower zoom version
                self.drawEmptyTile(zoom, x, y, offset_x, offset_y)
            
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
        
    def osm_centerGPS_map(self):
        if self.gpsLatitude!=0.0 and self.gpsLongitude!=0.0:
            pixel_x = self.osmutils.lon2pixel(self.map_zoom, self.gpsLongitude)
            pixel_y = self.osmutils.lat2pixel(self.map_zoom, self.gpsLatitude)
            width = self.width()
            height = self.height()
            self.map_x = pixel_x - width/2;
            self.map_y = pixel_y - height/2;
            self.center_coord_update();
            self.update()
            
    def osm_gps_map_scroll(self, dx, dy):
        self.map_x += dx
        self.map_y += dy
        self.center_coord_update()
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
            self.updateStatusLabel("OSM download server ok")
        except socket.error:
            self.updateStatusLabel("OSM download server failed. Disabling")
            self.withDownload=False
                
    def setDownloadTiles(self, value):
        self.withDownload=value
        if value==True:
            self.checkDownloadServer()
            self.update()
        
    def setAutocenterGPS(self, value):
        self.autocenterGPS=value
        if value==True:
            self.osm_centerGPS_map()
        
    def updateStatusLabel(self, text):
        self.emit(SIGNAL("updateStatus(QString)"), text)

    def updateMap(self):
#        print("updateMap")
        self.update()
        
    def mouseReleaseEvent(self, event ):
        if self.controlWidgetRect.contains(event.x(), event.y()):
            self.pointInsideMoveOverlay(event.x(), event.y())
            self.pointInsideZoomOverlay(event.x(), event.y())
        self.moving=False
        
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

    def mousePressEvent(self, event):
        if not self.controlWidgetRect.contains(event.x(), event.y()):
            self.moving=True
#            print("press %d-%d"%(event.x(), event.y()))
            self.lastMouseMoveX=event.x()
            self.lastMouseMoveY=event.y()
            
    def mouseMoveEvent(self, event):
        if self.moving==True:
#            print("move %d-%d"%(event.x(), event.y()))
            dx=self.lastMouseMoveX-event.x()
            dy=self.lastMouseMoveY-event.y()
            self.osm_gps_map_scroll(dx, dy)
            self.lastMouseMoveX=event.x()
            self.lastMouseMoveY=event.y()
        else:
            self.posStr=self.showPosition(event.x(), event.y())
#            print(self.posStr)
            
    def addContectMenu(self, menu):
        testAction = QAction("Test", self)
        testAction.triggered.connect(self._testAction)
        menu.addAction(testAction)        
            
    @pyqtSlot()
    def _testAction(self, x, y):
        print("foo")
        self.showPosition(x, y)
        
    def contextMenuEvent(self, event):
        print("%d-%d"%(event.x(), event.y()))
        menu = QMenu(self)
        testAction = QAction("Test", self)
        menu.addAction(testAction)
        action = menu.exec_(self.mapToGlobal(event.pos()))
        if action==testAction:
            self._testAction(event.x(), event.y())
        
#    def point_new_degrees(self, lat, lon):
#        rlat = self.osmutils.deg2rad(lat);
#        rlon = self.osmutils.deg2rad(lon);
#        return (rlat, rlon)
    
    def convert_screen_to_geographic(self, pixel_x, pixel_y):
        rlat = self.osmutils.pixel2lat(self.map_zoom, self.map_y + pixel_y);
        rlon = self.osmutils.pixel2lon(self.map_zoom, self.map_x + pixel_x);
        return (rlat, rlon)
    
    def showPosition(self, x, y):
        p=self.convert_screen_to_geographic(x, y)
        mouseLat = self.osmutils.rad2deg(p[0])
        mouseLon = self.osmutils.rad2deg(p[1])
        return "+%.4f , +%.4f" % (mouseLat, mouseLon)
       
    def event(self, event):
        if event.type() == QEvent.ToolTip:
#            print(self.posStr)
            QToolTip.showText(event.globalPos(), self.posStr)
#            event.ignore()
            return True
     
        return super(QtOSMWidget, self).event(event)
         
class OSMWidget(QWidget):
    def __init__(self, parent):
        QWidget.__init__(self, parent)
        
    def addToWidget(self, parent):       
        self.mapWidgetQt=QtOSMWidget(self)
        parent.addWidget(self.mapWidgetQt)
        
        vbox=QHBoxLayout()
        vbox.setAlignment(Qt.AlignLeft)
        parent.addLayout(vbox)
        
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
        self.mapWidgetQt.init()
        self.mapWidgetQt.updateGPSLocation(lat, lon)
        self.mapWidgetQt.show(zoom, lat, lon)
        
        self.downloadThread=OSMDownloadTilesWorker(self)
        self.connect(self.downloadThread, SIGNAL("updateMap()"), self.mapWidgetQt.updateMap)
        self.connect(self.downloadThread, SIGNAL("updateStatus(QString)"), self.updateStatusLabel)

    def initHome(self):                
        self.init(47.8, 13.0, self.getZoomValue())
        
    def initUI(self):
        hbox = QVBoxLayout()

        self.addToWidget(hbox)
        self.setLayout(hbox)
        
        self.initHome()

#        self.setGeometry(0, 0, 860, 500)
        self.setWindowTitle('OSM Test')
        self.show()
    
    @pyqtSlot()
    def _centerGPS(self):
        self.mapWidgetQt.osm_centerGPS_map()   
    
    @pyqtSlot()
    def _followGPS(self):
        self.mapWidgetQt.setAutocenterGPS(self.followGPSButton.isChecked())   
                    
    def updateGPSPosition(self, lat, lon):
        self.mapWidgetQt.updateGPSLocation(lat, lon)

    @pyqtSlot()
    def _downloadTiles(self):
        withDownload=self.downloadTilesButton.isChecked()
        if withDownload==True:
            self.downloadThread.setup()
        elif self.downloadThread!=None:
            self.downloadThread.stop()
        self.mapWidgetQt.setDownloadTiles(withDownload)   

    def updateStatusLabel(self, text):
        self.emit(SIGNAL("updateStatus(QString)"), text)
        
    def getZoomValue(self):
        return self.mapWidgetQt.map_zoom

    def setZoomValue(self, value):
        self.mapWidgetQt.map_zoom=value

    def getAutocenterGPSValue(self):
        return self.mapWidgetQt.autocenterGPS

    def setAutocenterGPSValue(self, value):
        self.mapWidgetQt.autocenterGPS=value
        self.followGPSButton.setChecked(value)
           
    def getWithDownloadValue(self):
        return self.mapWidgetQt.withDownload
 
    def setWithDownloadValue(self, value):
        self.mapWidgetQt.withDownload=value
        self.downloadTilesButton.setChecked(value)
        
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

        self.zoom=9
        self.startLat=47.8
        self.startLon=13.0
        self.mapWidget.initHome()

        self.connect(self.mapWidget.mapWidgetQt, SIGNAL("updateStatus(QString)"), self.updateStatusLabel)
        self.connect(self.mapWidget, SIGNAL("updateStatus(QString)"), self.updateStatusLabel)

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

    def updateStatusLabel(self, text):
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
