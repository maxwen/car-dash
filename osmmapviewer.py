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
from PyQt4.QtGui import QLabel, QToolTip, QMenu, QAction, QMainWindow, QTabWidget, QCheckBox, QPalette, QVBoxLayout, QPushButton, QWidget, QPixmap, QSizePolicy, QPainter, QPen, QHBoxLayout, QApplication

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
    def __init__(self, parent): 
        QThread.__init__(self, parent)
        self.exiting = False
        self.forceDownload=False
        self.downloadQueue=deque()
        self.downloadDoneQueue=deque()
        
    def setWidget(self, osmWidget):
        self.osmWidget=osmWidget
        
    def __del__(self):
        self.exiting = True
        self.wait()
        
    def setup(self, forceDownload):
        self.updateStatusLabel("OSM starting download thread")
        self.exiting = False
        self.forceDownload=forceDownload
        self.downloadDoneQueue.clear()
        self.start()
            
    def updateStatusLabel(self, text):
        self.emit(SIGNAL("updateStatus(QString)"), text)

    def updateMap(self):
        self.emit(SIGNAL("updateMap()"))
 
    def stop(self):
        self.exiting = True
        self.forceDownload=False
        self.downloadQueue.clear()
        self.downloadDoneQueue.clear()
        self.wait()

    def addTile(self, tilePath, fileName, forceDownload):
        if not [tilePath, fileName] in self.downloadQueue:
            self.downloadQueue.append([tilePath, fileName])
        if not self.isRunning():
            self.setup(forceDownload)
        
    def downloadTile(self, tilePath, fileName):
        if fileName in self.downloadDoneQueue:
            return
        if os.path.exists(fileName) and self.forceDownload==False:
            return
        try:
            httpConn = http.client.HTTPConnection(tileServer)
            httpConn.connect()
            httpConn.request("GET", tilePath)
            response = httpConn.getresponse()
            if response.status==http.client.OK:
                self.updateStatusLabel("OSM downloaded "+fileName)
                data = response.read()
                if not os.path.exists(os.path.dirname(fileName)):
                    try:
                        os.makedirs(os.path.dirname(fileName))
                    except OSError:
                        self.updateStatusLabel("OSM download OSError makedirs")
                try:
                    stream=io.open(fileName, "wb")
                    stream.write(data)
                    self.downloadDoneQueue.append(fileName)
#                    self.updateMap()
                except IOError:
                    self.updateStatusLabel("OSM download IOError write")
                    
            httpConn.close()
        except socket.error:
            self.updateStatusLabel("OSM download error socket.error")
            self.exiting=True
                
    def run(self):
        while not self.exiting and True:
            if len(self.downloadQueue)!=0:
                entry=self.downloadQueue.popleft()
                self.downloadTile(entry[0], entry[1])
                continue
            self.updateStatusLabel("OSM download thread idle")
            self.osmWidget.setForceDownload(False, False)

            self.msleep(1000) 
            
            if len(self.downloadQueue)==0:
                self.exiting=True
        
        self.forceDownload=False
        self.downloadQueue.clear()
        self.downloadDoneQueue.clear()
        self.updateMap()
#        self.osmWidget.setForceDownload(False, False)
        self.updateStatusLabel("OSM download thread stopped")


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
        self.autocenterGPS=False
        self.forceDownload=False
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
        pixbuf=self.getCachedTile(fileName)
        self.painter.drawPixmap(offset_x, offset_y, TILESIZE, TILESIZE, pixbuf)

    def getCachedTile(self, fileName):
        if not fileName in self.tileCache:
            pixbuf = QPixmap(fileName)
            self.tileCache[fileName]=pixbuf
        else:
            pixbuf=self.tileCache[fileName]
            
        return pixbuf
    
    def drawEmptyTile(self, zoom, offset_x, offset_y):
        pen=QPen()
        palette=QPalette()
        pen.setColor(palette.color(QPalette.Normal, QPalette.Background))
        self.painter.setPen(pen)
        self.painter.drawRect(offset_x, offset_y, TILESIZE, TILESIZE)

    def osm_gps_map_find_bigger_tile (self, zoom, x, y):
        while zoom > 0:
            zoom = zoom - 1
            next_x = int(x / 2)
            next_y = int(y / 2)
#            print("search for bigger map for zoom "+str(zoom))

            pixbuf=self.osm_gps_get_exising_tile(zoom, next_x, next_y)
            if pixbuf!=None:
                return (pixbuf, zoom)
            else:
                x=next_x
                y=next_y
        return (None, None)

    def osm_gps_map_render_tile_upscaled(self, zoom, x, y):
#        print("search for bigger map for zoom "+str(zoom))
        (pixbuf, zoom_big)=self.osm_gps_map_find_bigger_tile(zoom, x, y)
        if pixbuf!=None:
#            print("found exisiting tile on zoom "+str(zoom_big))
            zoom_diff = zoom - zoom_big

#            print("Upscaling by %d levels into tile %d,%d"%( zoom_diff, x, y))

            area_size = TILESIZE >> zoom_diff
            modulo = 1 << zoom_diff
            area_x = (x % modulo) * area_size
            area_y = (y % modulo) * area_size
            
            pixmapNew=pixbuf.copy(area_x, area_y, area_size, area_size)
            pixmapNew.scaled(TILESIZE, TILESIZE)
#            area = gdk_pixbuf_new_subpixbuf (big, area_x, area_y,
#                                     area_size, area_size)
#            pixbuf = gdk_pixbuf_scale_simple (area, TILESIZE, TILESIZE,
#                                      GDK_INTERP_NEAREST)
            return pixmapNew
        return None
        
    def osm_gps_get_exising_tile(self, zoom, x, y):
        fileName=self.getTileHome()+str(zoom)+"/"+str(x)+"/"+str(y)+".png"
        if os.path.exists(fileName):
            return self.getCachedTile(fileName)

        return None
    
    def osm_gps_get_tile(self, zoom, x, y, offset_x, offset_y):
        fileName=self.getTileHome()+str(zoom)+"/"+str(x)+"/"+str(y)+".png"
        if os.path.exists(fileName) and self.forceDownload==False:
            self.drawTile(fileName, offset_x, offset_y)
        else:
            if self.withDownload==True:
                self.osmWidget.downloadThread.addTile("/"+str(zoom)+"/"+str(x)+"/"+str(y)+".png", fileName, self.forceDownload)
                self.drawEmptyTile(zoom, offset_x, offset_y)
#                self.callDownloadForTile("/"+str(zoom)+"/"+str(x)+"/"+str(y)+".png", fileName)
#                if os.path.exists(fileName):
#                    self.drawTile(fileName, offset_x, offset_y)
                    
            elif self.withMapnik==True:
                self.callMapnikForTile()
                if os.path.exists(fileName):
                    self.drawTile(fileName, offset_x, offset_y)
            else:
                # try upscale lower zoom version
                pixbuf=self.osm_gps_map_render_tile_upscaled(zoom, x, y)
                if pixbuf!=None:
                    self.painter.drawPixmap(offset_x, offset_y, TILESIZE, TILESIZE, pixbuf)
                else:
                    self.drawEmptyTile(zoom, offset_x, offset_y)
            
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

        self.painter.drawPixmap(int(x-self.gpsPointImage.width()/2), int(y-self.gpsPointImage.height()/2), self.gpsPointImage)
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
        if self.autocenterGPS==True:
            self.osm_autocenter_map()
        self.update()
        self.emit(SIGNAL("updateZoom(int)"), zoom)
       
    def resizeEvent(self, event):
        self.osm_gps_map_handle_resize()
             
    def paintEvent(self, event):
#        print("paintEvent %d-%d"%(self.width(), self.height()))
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
                
    def setDownloadTiles(self, value):
        self.withDownload=value
        if value==True:
            self.update()

    def setForceDownload(self, value, update):
        self.forceDownload=value
        self.cleanImageCache()
        if self.forceDownload==True and update==True:
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
#        print("mouseReleaseEvent")
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
#        print("mousePressEvent")
        if not self.controlWidgetRect.contains(event.x(), event.y()):
            self.moving=True
#            print("press %d-%d"%(event.x(), event.y()))
            self.lastMouseMoveX=event.x()
            self.lastMouseMoveY=event.y()
        else:
            self.moving=False
            
    def mouseMoveEvent(self, event):
        if self.moving==True:
#            print("move %d-%d"%(event.x(), event.y()))
            dx=self.lastMouseMoveX-event.x()
            dy=self.lastMouseMoveY-event.y()
            self.osm_gps_map_scroll(dx, dy)
            self.lastMouseMoveX=event.x()
            self.lastMouseMoveY=event.y()
        else:
            self.updateMousePositionDisplay(event.x(), event.y())
#            self.posStr=self.showPosition(event.x(), event.y())
#            print(self.posStr)
            
    def updateMousePositionDisplay(self, x, y):
        (lat, lon)=self.getMousePosition(x, y)
        self.emit(SIGNAL("updateMousePositionDisplay(float, float)"), lat, lon)

#    def addContectMenu(self, menu):
#        testAction = QAction("Force Download", self)
#        testAction.triggered.connect(self._fAction)
#        menu.addAction(testAction)        
            
#    @pyqtSlot()
#    def _forceDownAction(self, x, y):
#        print("foo")
##        self.showPosition(x, y)
        
    def contextMenuEvent(self, event):
#        print("%d-%d"%(event.x(), event.y()))
        menu = QMenu(self)
        forceDownloadAction = QAction("Force Download", self)
        forceDownloadAction.setEnabled(self.withDownload==True)
        menu.addAction(forceDownloadAction)
        action = menu.exec_(self.mapToGlobal(event.pos()))
        if action==forceDownloadAction:
            if self.withDownload==True:
                self.setForceDownload(True, True)
        
        self.moving=False
        
#    def point_new_degrees(self, lat, lon):
#        rlat = self.osmutils.deg2rad(lat);
#        rlon = self.osmutils.deg2rad(lon);
#        return (rlat, rlon)
    
    def convert_screen_to_geographic(self, pixel_x, pixel_y):
        rlat = self.osmutils.pixel2lat(self.map_zoom, self.map_y + pixel_y);
        rlon = self.osmutils.pixel2lon(self.map_zoom, self.map_x + pixel_x);
        return (rlat, rlon)
    
    def getMousePosition(self, x, y):
        p=self.convert_screen_to_geographic(x, y)
        mouseLat = self.osmutils.rad2deg(p[0])
        mouseLon = self.osmutils.rad2deg(p[1])
        return (mouseLat, mouseLon)
       
#    def event(self, event):
#        if event.type() == QEvent.ToolTip:
##            print(self.posStr)
#            QToolTip.showText(event.globalPos(), self.posStr)
##            event.ignore()
#            return True
#     
#        return super(QtOSMWidget, self).event(event)
         
class OSMWidget(QWidget):
    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.startLat=47.8
        self.startLon=13.0
        #self.serverChecked=False
        
    def addToWidget(self, vbox):       
        self.mapWidgetQt=QtOSMWidget(self)
        vbox.addWidget(self.mapWidgetQt)
        
        hbox=QHBoxLayout()
        hbox.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        vbox.addLayout(hbox)
        
        self.centerGPSButton=QPushButton("Center GPS", self)
        self.centerGPSButton.clicked.connect(self._centerGPS)
        hbox.addWidget(self.centerGPSButton)
        
        self.followGPSButton=QCheckBox("Follow GPS", self)
        self.followGPSButton.clicked.connect(self._followGPS)
        hbox.addWidget(self.followGPSButton)
        
        self.downloadTilesButton=QCheckBox("Download", self)
        self.downloadTilesButton.clicked.connect(self._downloadTiles)
        hbox.addWidget(self.downloadTilesButton)
        
#        self.forceDownloadTilesButton=QPushButton("Force Download", self)
#        self.forceDownloadTilesButton.clicked.connect(self._forceDownloadTiles)
#        hbox.addWidget(self.forceDownloadTilesButton)

        self.zoomLabel=QLabel("", self)
        self.zoomLabel.setText("z=%d"%(self.getZoomValue()))
        hbox.addWidget(self.zoomLabel)
        
        self.gpsPosLabelLat=QLabel("", self)
        self.gpsPosLabelLat.setText("+%2.4f"%(0.0))
        hbox.addWidget(self.gpsPosLabelLat)

        self.gpsPosLabelLon=QLabel("", self)
        self.gpsPosLabelLon.setText("+%2.4f"%(0.0))
        hbox.addWidget(self.gpsPosLabelLon)
        
        self.mousePosLabelLat=QLabel("", self)
        self.mousePosLabelLat.setText("+%2.4f"%(0.0))
        hbox.addWidget(self.mousePosLabelLat)

        self.mousePosLabelLon=QLabel("", self)
        self.mousePosLabelLon.setText("+%2.4f"%(0.0))
        hbox.addWidget(self.mousePosLabelLon)
        
        self.downloadThread=OSMDownloadTilesWorker(self)
        self.downloadThread.setWidget(self.mapWidgetQt)
        self.connect(self.downloadThread, SIGNAL("updateMap()"), self.mapWidgetQt.updateMap)
        self.connect(self.mapWidgetQt, SIGNAL("updateMousePositionDisplay(float, float)"), self.updateMousePositionDisplay)
        self.connect(self.mapWidgetQt, SIGNAL("updateZoom(int)"), self.updateZoom)

    def updateMousePositionDisplay(self, lat, lon):
        self.mousePosLabelLat.setText("+%.4f"%(lat))
        self.mousePosLabelLon.setText("+%.4f"%(lon)) 
 
    def updateGPSPositionDisplay(self, lat, lon):
        self.gpsPosLabelLat.setText("+%.4f"%(lat))
        self.gpsPosLabelLon.setText("+%.4f"%(lon))   
            
    def updateZoom(self, zoom):
        self.zoomLabel.setText("z=%d"%(zoom))
            
    def init(self, lat, lon, zoom):        
        self.mapWidgetQt.init()
        self.mapWidgetQt.show(zoom, lat, lon)  
        self._downloadTiles()

    def setStartLongitude(self, lon):
        self.startLon=lon
    
    def setStartLatitude(self, lat):
        self.startLat=lat
        
    def initHome(self):                
        self.init(self.startLat, self.startLon, self.getZoomValue())
        
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
        self.updateGPSPositionDisplay(lat, lon)

    def checkDownloadServer(self):
        #if self.serverChecked==False:
        #   self.serverChecked=True
        try:
            socket.gethostbyname(tileServer)
            self.updateStatusLabel("OSM download server ok")
            return True
        except socket.error:
            self.updateStatusLabel("OSM download server failed. Disabling")
            self.downloadTilesButton.setChecked(False)
            return False
            
    @pyqtSlot()
    def _downloadTiles(self):
        withDownload=self.downloadTilesButton.isChecked()
#        if withDownload==True:
#            withDownload=self.checkDownloadServer()
#            if  withDownload==True:
#                self.downloadThread.setup()
#        else:
#            if self.downloadThread.isRunning():
#                self.downloadThread.stop()
        self.mapWidgetQt.setDownloadTiles(withDownload)   
#        self.forceDownloadTilesButton.setDisabled(withDownload==False)

#    @pyqtSlot()
#    def _forceDownloadTiles(self):
#        self.mapWidgetQt.setForceDownload(True, True)
        
    def updateStatusLabel(self, text):
        self.emit(SIGNAL("updateStatus(QString)"), text)
        
    def getZoomValue(self):
        return self.mapWidgetQt.map_zoom

    def setZoomValue(self, value):
        self.mapWidgetQt.map_zoom=value
        self.updateZoom(value)

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
        
    def loadConfig(self, config):
        self.setZoomValue(config.getDefaultSection().getint("zoom", 9))
        self.setAutocenterGPSValue(config.getDefaultSection().getboolean("autocenterGPS", False))
        self.setWithDownloadValue(config.getDefaultSection().getboolean("withDownload", False))
        self.setStartLatitude(config.getDefaultSection().getfloat("lat", self.startLat))
        self.setStartLongitude(config.getDefaultSection().getfloat("lon", self.startLon))

    def saveConfig(self, config):
        config.getDefaultSection()["zoom"]=str(self.getZoomValue())
        config.getDefaultSection()["autocenterGPS"]=str(self.getAutocenterGPSValue())
        config.getDefaultSection()["withDownload"]=str(self.getWithDownloadValue())
        if self.mapWidgetQt.gpsLatitude!=0.0:
            config.getDefaultSection()["lat"]=str(self.mapWidgetQt.osmutils.rad2deg(self.mapWidgetQt.gpsLatitude))
        if self.mapWidgetQt.gpsLongitude!=0.0:    
            config.getDefaultSection()["lon"]=str(self.mapWidgetQt.osmutils.rad2deg(self.mapWidgetQt.gpsLongitude))

class OSMWindow(QMainWindow):
    def __init__(self, parent):
        QMainWindow.__init__(self, parent)
        self.initUI()
        self.incLat=0.0
        self.incLon=0.0

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
        self.connect(self.mapWidget.downloadThread, SIGNAL("updateStatus(QString)"), self.updateStatusLabel)

        self.testGPSButton=QPushButton("Test GPS", self)
        self.testGPSButton.clicked.connect(self._testGPS)
        top.addWidget(self.testGPSButton)

#        self.setGeometry(0, 0, 800, 400)
        self.setWindowTitle('OSM Test')
        self.show()
        
    @pyqtSlot()
    def _testGPS(self):
        if self.incLat==0.0:
            self.incLat=self.startLat
        if self.incLon==0.0:
            self.incLon=self.startLon
            
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

    widget1 = OSMWindow(None)
    widget1.initUI()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main(sys.argv)
