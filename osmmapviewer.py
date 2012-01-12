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
import fnmatch

from PyQt4.QtCore import QAbstractTableModel, Qt, QPoint, QSize, pyqtSlot, SIGNAL, QRect, QThread
from PyQt4.QtGui import QAbstractItemView, QCommonStyle, QStyle, QProgressBar, QItemSelectionModel, QInputDialog, QLineEdit, QHeaderView, QTableView, QDialog, QIcon, QLabel, QMenu, QAction, QMainWindow, QTabWidget, QCheckBox, QPalette, QVBoxLayout, QPushButton, QWidget, QPixmap, QSizePolicy, QPainter, QPen, QHBoxLayout, QApplication
from osmparser.osmparserdata import OSMParserData, OSMRoutingPoint, OSMRoute
from osmparser.osmutils import OSMUtils
from config import Config

TILESIZE=256
minWidth=500
minHeight=300
EXTRA_BORDER=0
MIN_ZOOM=1
MAX_ZOOM=18
MAP_SCROLL_STEP=10
M_LN2=0.69314718055994530942    #log_e 2

defaultTileHome=os.path.join("Maps", "osm", "tiles")
defaultTileServer="tile.openstreetmap.org"

downloadIdleState="idle"
downloadRunState="run"
downloadStoppedState="stopped"

osmParserData = OSMParserData()

class OSMDownloadTilesWorker(QThread):
    def __init__(self, parent): 
        QThread.__init__(self, parent)
        self.exiting = False
        self.forceDownload=False
        self.downloadQueue=deque()
        self.downloadDoneQueue=deque()
        self.tileServer=defaultTileServer
        
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
#        print(text)

    def updateMap(self):
        self.emit(SIGNAL("updateMap()"))
 
    def updateDownloadThreadState(self, state):
        self.emit(SIGNAL("updateDownloadThreadState(QString)"), state)

    def stop(self):
        self.exiting = True
        self.forceDownload=False
        self.downloadQueue.clear()
        self.downloadDoneQueue.clear()
        self.wait()

    def addTile(self, tilePath, fileName, forceDownload, tileServer):
        self.tileServer=tileServer
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
            httpConn = http.client.HTTPConnection(self.tileServer)
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
        self.updateDownloadThreadState(downloadRunState)
        while not self.exiting and True:
            if len(self.downloadQueue)!=0:
                entry=self.downloadQueue.popleft()
                self.downloadTile(entry[0], entry[1])
                continue
            
            self.updateStatusLabel("OSM download thread idle")
            self.updateDownloadThreadState(downloadIdleState)
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
        self.updateDownloadThreadState(downloadStoppedState)


class OSMDataLoadWorker(QThread):
    def __init__(self, parent): 
        QThread.__init__(self, parent)
        self.exiting = False
        
#    def __del__(self):
#        self.exiting = True
#        self.wait()
        
    def setup(self):
        self.updateStatusLabel("OSM starting data load thread")
        self.exiting = False

        self.start()
 
    def updateDataThreadState(self, state):
        self.emit(SIGNAL("updateDataThreadState(QString)"), state)
    
    def updateStatusLabel(self, text):
        self.emit(SIGNAL("updateStatus(QString)"), text)
        
    def startProgress(self):
        self.emit(SIGNAL("startProgress()"))

    def stopProgress(self):
        self.emit(SIGNAL("stopProgress()"))

#    def stop(self):
#        self.exiting = True
#        self.wait()
 
    def run(self):
        self.updateDataThreadState("run")
        self.startProgress()
        while not self.exiting and True:
            self.updateStatusLabel("OSM init DB")
#            osmParserData.initDB()
            self.exiting=True

        self.updateDataThreadState("stopped")
        self.updateStatusLabel("OSM stopped data load thread")
        self.stopProgress()

class OSMRouteCalcWorker(QThread):
    def __init__(self, parent): 
        QThread.__init__(self, parent)
        self.exiting = False
        
#    def __del__(self):
#        self.exiting = True
#        self.wait()
        
    def setup(self, route):
        self.updateStatusLabel("OSM starting route calculation thread")
        self.exiting = False
        self.route=route
        self.startProgress()
        osmParserData.initGraph()
        self.start()
 
    def updateRouteCalcThreadState(self, state):
        self.emit(SIGNAL("updateRouteCalcThreadState(QString)"), state)
    
    def updateStatusLabel(self, text):
        self.emit(SIGNAL("updateStatus(QString)"), text)
    
    def routeCalculationDone(self):
        self.emit(SIGNAL("routeCalculationDone()"))
        
    def startProgress(self):
        self.emit(SIGNAL("startProgress()"))

    def stopProgress(self):
        self.emit(SIGNAL("stopProgress()"))

#    def stop(self):
#        self.exiting = True
#        self.wait()
 
    def run(self):
        self.updateRouteCalcThreadState("run")
        self.startProgress()
        while not self.exiting and True:
            osmParserData.calcRoute(self.route)
            self.exiting=True

        self.updateRouteCalcThreadState("stopped")
        self.updateStatusLabel("OSM stopped route calculation thread")
        self.routeCalculationDone()
        self.stopProgress()
        
class QtOSMWidget(QWidget):
    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.osmWidget=parent
        font = self.font()
        font.setPointSize(14)
        self.setFont(font)

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
        self.gpsPointImageStop=QPixmap("images/gps-point-big-stop.png")

        self.osmControlImage=QPixmap("images/osm-control.png")
        self.controlWidgetRect=QRect(0, 0, self.osmControlImage.width(), self.osmControlImage.height())
        self.zoomRect=QRect(0, 105, 95, 45)
        self.minusRect=QRect(7, 110, 35, 35)
        self.plusRect=QRect(53, 110, 35, 35)
        
        self.moveRect=QRect(0, 0, 95, 95)
        self.leftRect=QRect(5, 35, 25, 25)
        self.rightRect=QRect(65, 35, 25, 25)
        self.upRect=QRect(35, 5, 25, 25)
        self.downRect=QRect(35, 65, 25, 25)
        
        self.setContextMenuPolicy(Qt.DefaultContextMenu)
        self.moving=False
        self.mousePressed=False
        self.setMouseTracking(True)
        self.posStr="+%.4f , +%.4f" % (0.0, 0.0)
        
        self.tileHome=defaultTileHome
        self.tileServer=defaultTileServer
        
        self.track=None
        self.trackStartLat=0.0
        self.trackStartLon=0.0
        self.lastMouseMoveX=0
        self.lastMouseMoveY=0
        
        self.lastWayId=None
        self.mousePos=(0, 0)
        self.startPoint=None
        self.endPoint=None
        self.gpsPoint=None
        self.wayPoints=list()
        self.startPointImage=QPixmap("images/source.png")
        self.endPointImage=QPixmap("images/target.png")
        self.wayPointImage=QPixmap("images/waypoint.png")
        self.routeCalculationThread=None
        
        self.turnRightImage=QPixmap("images/turn-right-icon.png")
        self.turnLeftImage=QPixmap("images/turn-left-icon.png")
        
    def getTileHomeFullPath(self):
        if os.path.isabs(self.getTileHome()):
            return self.getTileHome()
        else:
            return os.path.join(os.environ['HOME'], self.getTileHome())
    
    def getTileFullPath(self, zoom, x, y):
        home=self.getTileHomeFullPath()
        tilePath=os.path.join(str(zoom), str(x), str(y)+".png")
        fileName=os.path.join(home, tilePath)
        return fileName

    def getTileHome(self):
        return self.tileHome
    
    def setTileHome(self, value):
        self.tileHome=value
                
    def getTileServer(self):
        return self.tileServer
    
    def setTileServer(self, value):
        self.tileServer=value

    def setTrack(self, track, update):
        self.track=track
        if update:
            self.update()

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

        (pixel_y, pixel_x)=self.getPixelPosForLocationRad(self.center_rlat, self.center_rlon, False)

#        pixel_x = self.osmutils.lon2pixel(self.map_zoom, self.center_rlon)
#        pixel_y = self.osmutils.lat2pixel(self.map_zoom, self.center_rlat)
#        print("%d %d"%(pixel_x, pixel_y))

        self.map_x = int(pixel_x - self.width()/2)
        self.map_y = int(pixel_y - self.height()/2)
        
#        print("after center %f %f %d %d %d"%(latitude, longitude, self.map_x, self.map_y, self.map_zoom))
        
    def osm_gps_map_set_zoom (self, zoom):
#        width_center  = self.width() / 2
#        height_center = self.height() / 2

        self.map_zoom = self.CLAMP(zoom, self.min_zoom, self.max_zoom)
        self.osm_gps_map_handle_resize()
        
#        (pixel_y, pixel_x)=self.self.getPixelPosForLocationRad(self.center_rlat, self.center_rlon)

#        self.map_x = pixel_x - width_center
#        self.map_y = pixel_y - height_center
        
    def osm_gps_map_handle_resize (self):
        width_center  = self.width() / 2
        height_center = self.height() / 2

        (pixel_y, pixel_x)=self.getPixelPosForLocationRad(self.center_rlat, self.center_rlon, False)

        self.map_x = pixel_x - width_center
        self.map_y = pixel_y - height_center

#        (self.map_y, self.map_x)=self.self.getPixelPosForLocationRad(self.center_rlat, self.center_rlon)
#
#        self.map_x = self.osmutils.lon2pixel(self.map_zoom, self.center_rlon) - width_center
#        self.map_y = self.osmutils.lat2pixel(self.map_zoom, self.center_rlat) - height_center

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
                    self.drawEmptyTile(offset_xn, offset_yn)
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
        self.drawPixmap(offset_x, offset_y, TILESIZE, TILESIZE, pixbuf)
        
    def drawPixmap(self, x, y, width, height, pixbuf):
        self.painter.drawPixmap(x, y, width, height, pixbuf)

    def getCachedTile(self, fileName):
        if not fileName in self.tileCache:
            pixbuf = QPixmap(fileName)
            self.tileCache[fileName]=pixbuf
        else:
            pixbuf=self.tileCache[fileName]
            
        return pixbuf
    
    def drawEmptyTile(self, x, y):
        pen=QPen()
        palette=QPalette()
        pen.setColor(palette.color(QPalette.Normal, QPalette.Background))
        self.painter.setPen(pen)
        self.painter.drawRect(x, y, TILESIZE, TILESIZE)

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
        fileName=self.getTileFullPath(zoom, x, y)
        if os.path.exists(fileName):
            return self.getCachedTile(fileName)

        return None
    
    def osm_gps_get_tile(self, zoom, x, y, offset_x, offset_y):
        fileName=self.getTileFullPath(zoom, x, y)
        if os.path.exists(fileName) and self.forceDownload==False:
            self.drawTile(fileName, offset_x, offset_y)
        else:
            if self.withDownload==True:
                self.osmWidget.downloadThread.addTile("/"+str(zoom)+"/"+str(x)+"/"+str(y)+".png", fileName, self.forceDownload, self.getTileServer())
                self.drawEmptyTile(offset_x, offset_y)
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
                    self.drawPixmap(offset_x, offset_y, TILESIZE, TILESIZE, pixbuf)
                else:
                    self.drawEmptyTile(offset_x, offset_y)
            
    def osm_gps_show_location(self):
        if self.gpsLongitude==0.0 and self.gpsLatitude==0.0:
            return
 
#        map_x0 = self.map_x - EXTRA_BORDER
#        map_y0 = self.map_y - EXTRA_BORDER
        
        (y, x)=self.getPixelPosForLocationRad(self.gpsLatitude, self.gpsLongitude, True)

#        x = self.osmutils.lon2pixel(self.map_zoom, self.gpsLongitude) - map_x0
#        y = self.osmutils.lat2pixel(self.map_zoom, self.gpsLatitude) - map_y0

        if self.stop==True:
            self.painter.drawPixmap(int(x-self.gpsPointImageStop.width()/2), int(y-self.gpsPointImageStop.height()/2), self.gpsPointImageStop)
        else:
            self.painter.drawPixmap(int(x-self.gpsPointImage.width()/2), int(y-self.gpsPointImage.height()/2), self.gpsPointImage)
#        self.painter.drawPoint(x, y)
        
    def osm_autocenter_map(self):
        if self.gpsLatitude!=0.0 and self.gpsLongitude!=0.0:
            (pixel_y, pixel_x)=self.getPixelPosForLocationRad(self.gpsLatitude, self.gpsLongitude, False)

#            pixel_x = self.osmutils.lon2pixel(self.map_zoom, self.gpsLongitude)
#            pixel_y = self.osmutils.lat2pixel(self.map_zoom, self.gpsLatitude)
            x = pixel_x - self.map_x
            y = pixel_y - self.map_y
            width = self.width()
            height = self.height()
            if x < (width/2 - width/8) or x > (width/2 + width/8) or y < (height/2 - height/8) or y > (height/2 + height/8):
                self.map_x = pixel_x - width/2;
                self.map_y = pixel_y - height/2;
                self.center_coord_update();
            self.update()
        
    def osm_center_map_to_GPS(self):
        self.osm_center_map_to(self.gpsLatitude, self.gpsLongitude)
            
    def osm_center_map_to(self, lat, lon):
        if lat!=0.0 and lon!=0.0:
            (pixel_y, pixel_x)=self.getPixelPosForLocationRad(lat, lon, False)
#            pixel_x = self.osmutils.lon2pixel(self.map_zoom, lon)
#            pixel_y = self.osmutils.lat2pixel(self.map_zoom, lat)
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
        self.painter.setRenderHint(QPainter.Antialiasing)
        self.painter.setRenderHint(QPainter.SmoothPixmapTransform)
        self.osm_gps_map_fill_tiles_pixel()
        self.osm_gps_show_location()
        self.showTrack()
        self.showControlOverlay()
        self.showRoutingPoints()
        self.painter.end()
              
    def showRoutingPoints(self):
        startPointPen=QPen()
        startPointPen.setColor(Qt.darkBlue)
        startPointPen.setWidth(min(self.map_zoom, 10))
        startPointPen.setCapStyle(Qt.RoundCap);
        
        endPointPen=QPen()
        endPointPen.setColor(Qt.red)
        endPointPen.setWidth(min(self.map_zoom, 10))
        endPointPen.setCapStyle(Qt.RoundCap);

        if self.startPoint!=None:
            (y, x)=self.getPixelPosForLocationDeg(self.startPoint.lat, self.startPoint.lon, True)
            self.painter.drawPixmap(int(x-self.startPointImage.width()/2), int(y-self.startPointImage.height()/2), self.startPointImage)

#            self.painter.setPen(startPointPen)
#            self.painter.drawPoint(x, y)

        if self.endPoint!=None:
            (y, x)=self.getPixelPosForLocationDeg(self.endPoint.lat, self.endPoint.lon, True)
            self.painter.drawPixmap(int(x-self.endPointImage.width()/2), int(y-self.endPointImage.height()/2), self.endPointImage)

#            self.painter.setPen(endPointPen)
#            self.painter.drawPoint(x, y)
            
        for point in self.wayPoints:
            (y, x)=self.getPixelPosForLocationDeg(point.lat, point.lon, True)
            self.painter.drawPixmap(int(x-self.wayPointImage.width()/2), int(y-self.wayPointImage.height()/2), self.wayPointImage)
            
    
    def getPixelPosForLocationDeg(self, lat, lon, relativeToEdge):
        return self.getPixelPosForLocationRad(self.osmutils.deg2rad(lat), self.osmutils.deg2rad(lon), relativeToEdge)
     
    def getPixelPosForLocationRad(self, lat, lon, relativeToEdge):

        if relativeToEdge:
            map_x0 = self.map_x - EXTRA_BORDER
            map_y0 = self.map_y - EXTRA_BORDER
            x=self.osmutils.lon2pixel(self.map_zoom, lon) - map_x0
            y=self.osmutils.lat2pixel(self.map_zoom, lat) - map_y0
        else:
            x=self.osmutils.lon2pixel(self.map_zoom, lon)
            y=self.osmutils.lat2pixel(self.map_zoom, lat)
            
        return (y, x)

#    def setRotation(self, r):
#        self.painter.save()
#        self.painter.translate(TILESIZE/2,TILESIZE/2)
#        self.painter.rotate(90)
#        self.painter.translate(-TILESIZE/2,-TILESIZE/2);
    
    def showTrack(self):
#        There are 20 predefined QColors: Qt::white, Qt::black, Qt::red, 
#        Qt::darkRed, Qt::green, Qt::darkGreen, Qt::blue, Qt::darkBlue, 
#        Qt::cyan, Qt::darkCyan, Qt::magenta, Qt::darkMagenta, Qt::yellow, 
#        Qt::darkYellow, Qt::gray, Qt::darkGray, Qt::lightGray, Qt::color0, 
#        Qt::color1, and Qt::transparent.

#        Qt::SolidLine    Qt::DashLine    Qt::DotLine        
#        Qt::DashDotLine    Qt::DashDotDotLine    Qt::CustomDashLine

        if self.track!=None:
            redPen=QPen()
            redPen.setColor(Qt.red)
            redPen.setWidth(4)
            redPen.setCapStyle(Qt.RoundCap);
            redPen.setJoinStyle(Qt.RoundJoin)
            
            blueCrossingPen=QPen()
            blueCrossingPen.setColor(Qt.darkBlue)
            blueCrossingPen.setWidth(min(self.map_zoom, 10))
            blueCrossingPen.setCapStyle(Qt.RoundCap);
            
            redCrossingPen=QPen()
            redCrossingPen.setColor(Qt.red)
            redCrossingPen.setWidth(min(self.map_zoom, 10))
            redCrossingPen.setCapStyle(Qt.RoundCap);
            
            greenCrossingPen=QPen()
            greenCrossingPen.setColor(Qt.green)
            greenCrossingPen.setWidth(min(self.map_zoom, 10))
            greenCrossingPen.setCapStyle(Qt.RoundCap);

            motorwayPen=QPen()
            motorwayPen.setColor(Qt.blue)
            motorwayPen.setWidth(4)
            motorwayPen.setCapStyle(Qt.RoundCap);
            
            primaryPen=QPen()
            primaryPen.setColor(Qt.red)
            primaryPen.setWidth(4)
            primaryPen.setCapStyle(Qt.RoundCap);
            
            residentialPen=QPen()
            residentialPen.setColor(Qt.yellow)
            residentialPen.setWidth(4)
            residentialPen.setCapStyle(Qt.RoundCap);
            
            tertiaryPen=QPen()
            tertiaryPen.setColor(Qt.darkYellow)
            tertiaryPen.setWidth(4)
            tertiaryPen.setCapStyle(Qt.RoundCap);
            
            linkPen=QPen()
            linkPen.setColor(Qt.black)
            linkPen.setWidth(4)
            linkPen.setCapStyle(Qt.RoundCap);
            
            self.trackStartLon=0.0
            self.trackStartLat=0.0
            lastX=0
            lastY=0
            startNode=deque()
            node=None

#                track= osmParserData.getStreetTrackList(wayid)
#                if track==None:
#                    print("no track found for %d"%(wayid))
#                    continue
            
            for item in self.track:
                if "lat" in item:
                    lat=item["lat"]
                if "lon" in item:
                    lon=item["lon"]
                if "ref" in item:
                    ref=item["ref"]
#                        if ref in osmParserData.nodes:
#                            node=osmParserData.nodes[ref]
                        
                start=False
                end=False
                crossing=False
                crossingType=0
                oneway=False
                streetType=""
                direction=None
                if "start" in item:
                    start=True
                if "end" in item:
                    end=True
                if "crossing" in item:
                    crossing=True
                    crossingType=item["crossing"][0]
                if "crossingInfo" in item:
                    crossingInfo=item["crossingInfo"]
                if "direction" in item:
                    direction=item["direction"]
                if"oneway" in item:
                    oneway=item["oneway"]=="yes"
                if "type" in item:
                    streetType=item["type"]
                if not start and not end:
                    (y, x)=self.getPixelPosForLocationDeg(lat, lon, True)
#                        x=self.osmutils.lon2pixel(self.map_zoom, self.osmutils.deg2rad(lon)) - map_x0
#                        y=self.osmutils.lat2pixel(self.map_zoom, self.osmutils.deg2rad(lat)) - map_y0
    
                    if lastX!=0 and lastY!=0:
                        if streetType[-5:]=="_link":
                            pen=linkPen
                        elif streetType=="motorway":
                            pen=motorwayPen
                        elif streetType=="primary":
                            pen=primaryPen
                        elif streetType=="residential":
                            pen=residentialPen
                        elif streetType=="tertiary":
                            pen=tertiaryPen
                        else:
                            pen=redPen
                            
                        if oneway:
                            pen.setStyle(Qt.DashLine)
                        else:
                            pen.setStyle(Qt.SolidLine)
                            
                        self.painter.setPen(pen)
                        self.painter.drawLine(x, y, lastX, lastY)
                    else:
                        self.trackStartLon=lon
                        self.trackStartLat=lat

                    lastX=x
                    lastY=y
                        
                    if crossing:
                        if crossingType==0:
                            self.painter.setPen(greenCrossingPen)
                        elif crossingType==1:
                            # with traffic signs
                            self.painter.setPen(redCrossingPen)
                        elif crossingType==2:
                            # motorway junction
                            self.painter.setPen(blueCrossingPen)

                        self.painter.drawPoint(x, y)
                    if direction!=None:
                        (y, x)=self.getPixelPosForLocationDeg(lat, lon, True)
                        if crossingType==2:
                            if "exit:" in crossingInfo:
                                self.painter.drawPixmap(x, y, self.turnRightImage)
                        else:
                            if direction==1:
                                #right
                                self.painter.drawPixmap(x, y, self.turnRightImage)
                            elif direction==-1:
                                #left
                                self.painter.drawPixmap(x, y, self.turnLeftImage)
                                
                elif start:
                    startNode.append((lastX, lastY))
                    lastX=0
                    lastY=0
                elif end:
                    lastX, lastY=startNode.pop()
            if len(startNode)!=0:
                print("unbalanced start-end nodes %s"%str(startNode))
            
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
            
            self.gpsPoint=OSMRoutingPoint("gps", 3, lat, lon)
            self.showTrackOnGPSPos(lat, lon)

            if self.gpsLatitude!=gpsLatitudeNew or self.gpsLongitude!=gpsLongitudeNew:
                self.stop=False
                self.gpsLatitude=gpsLatitudeNew
                self.gpsLongitude=gpsLongitudeNew
                if self.autocenterGPS==True:
                    self.osm_autocenter_map()
                else:
                    self.update()   
            else:
                self.stop=True
                if self.autocenterGPS==True:
                    self.osm_autocenter_map()
                else:
                    self.update()           
        else:
            self.gpsLatitude=0.0
            self.gpsLongitude=0.0
            self.gpsPoint=None
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
            self.osm_center_map_to_GPS()
        
    def updateStatusLabel(self, text):
        self.emit(SIGNAL("updateStatus(QString)"), text)

    def updateMap(self):
#        print("updateMap")
        self.update()
        
    def mouseReleaseEvent(self, event ):
        self.mousePressed=False

        if not self.moving:
            if not self.controlWidgetRect.contains(event.x(), event.y()):
                self.lastMouseMoveX=event.x()
                self.lastMouseMoveY=event.y()
                self.showTrackOnMousePos(event.x(), event.y())

            else:
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
#        self.painter.drawRect(self.zoomRect)
#        self.painter.drawRect(self.minusRect)
#        self.painter.drawRect(self.plusRect)
#        self.painter.drawRect(self.moveRect)
#        self.painter.drawRect(self.leftRect)
#        self.painter.drawRect(self.rightRect)
#        self.painter.drawRect(self.upRect)
#        self.painter.drawRect(self.downRect)

    def mousePressEvent(self, event):
        self.mousePressed=True
#        print("mousePressEvent")
        self.lastMouseMoveX=event.x()
        self.lastMouseMoveY=event.y()
        self.mousePos=(event.x(), event.y())
            
    def mouseMoveEvent(self, event):
        if self.mousePressed==True:
            self.moving=True
            
        if self.moving==True:
#            print("move %d-%d"%(event.x(), event.y()))
            dx=self.lastMouseMoveX-event.x()
            dy=self.lastMouseMoveY-event.y()
            self.osm_gps_map_scroll(dx, dy)
            self.lastMouseMoveX=event.x()
            self.lastMouseMoveY=event.y()
        else:
            self.updateMousePositionDisplay(event.x(), event.y())
#            self.showTrackOnMousePos(event.x(), event.y())

            
    def updateMousePositionDisplay(self, x, y):
        (lat, lon)=self.getMousePosition(x, y)
        self.emit(SIGNAL("updateMousePositionDisplay(float, float)"), lat, lon)
        
    def getRoutingPointForPos(self, mousePos):
        p=QPoint(mousePos[0], mousePos[1])

        if self.startPoint!=None:
            (y, x)=self.getPixelPosForLocationDeg(self.startPoint.lat, self.startPoint.lon, True)
            rect=QRect(x-int(self.startPointImage.width()/2), y-int(self.startPointImage.height()/2), self.startPointImage.width(), self.startPointImage.height())
            if rect.contains(p, proper=False):
                return self.startPoint

        if self.endPoint!=None:
            (y, x)=self.getPixelPosForLocationDeg(self.endPoint.lat, self.endPoint.lon, True)
            rect=QRect(x-int(self.endPointImage.width()/2), y-int(self.endPointImage.height()/2), self.endPointImage.width(), self.endPointImage.height())
            if rect.contains(p, proper=False):
                return self.endPoint

        for point in self.wayPoints:
            (y, x)=self.getPixelPosForLocationDeg(point.lat, point.lon, True)
            rect=QRect(x-int(self.wayPointImage.width()/2), y-int(self.wayPointImage.height()/2), self.wayPointImage.width(), self.wayPointImage.height())
            if rect.contains(p, proper=False):
                return point

        return None
    
    def contextMenuEvent(self, event):
#        print("%d-%d"%(self.mousePos[0], self.mousePos[1]))
        menu = QMenu(self)
        forceDownloadAction = QAction("Force Download", self)
        forceDownloadAction.setEnabled(self.withDownload==True)
        setStartPointAction = QAction("Set Start Point", self)
        setEndPointAction = QAction("Set End Point", self)
        setWayPointAction = QAction("Set Way Point", self)
        addFavoriteAction=QAction("Add to Favorites", self)
        clearAllRoutingPointsAction = QAction("Clear All Routing Points", self)
        clearRoutingPointAction=QAction("Clear Routing Point", self)
        editRoutingPointAction=QAction("Edit Current Route", self)
        showRouteAction=QAction("Show Route", self)

        menu.addAction(forceDownloadAction)
        menu.addSeparator()
        menu.addAction(setStartPointAction)
        menu.addAction(setEndPointAction)
        menu.addAction(setWayPointAction)
        menu.addAction(addFavoriteAction)
        menu.addSeparator()
        menu.addAction(clearAllRoutingPointsAction)
        menu.addAction(clearRoutingPointAction)
        menu.addAction(editRoutingPointAction)
        menu.addSeparator()
        menu.addAction(showRouteAction)

        addPointDisabled=not self.osmWidget.dbLoaded
        setStartPointAction.setDisabled(addPointDisabled)
        setEndPointAction.setDisabled(addPointDisabled)
        setWayPointAction.setDisabled(addPointDisabled)
        addFavoriteAction.setDisabled(addPointDisabled)
        clearRoutingPointAction.setDisabled(self.getSelectedRoutingPoint(self.mousePos)==None)
        clearAllRoutingPointsAction.setDisabled(addPointDisabled)
        editRoutingPointAction.setDisabled(self.getCompleteRoutingPoints()==None)
        
        showRouteDisabled=not self.osmWidget.dbLoaded or (self.routeCalculationThread!=None and self.routeCalculationThread.isRunning())
        if self.gpsPoint!=None:
            if self.endPoint==None:
                showRouteDisabled=True
        else:
            if self.startPoint==None or self.endPoint==None:
                showRouteDisabled=True
                
        showRouteAction.setDisabled(showRouteDisabled)
        
        action = menu.exec_(self.mapToGlobal(event.pos()))
        if action==forceDownloadAction:
            if self.withDownload==True:
                self.setForceDownload(True, True)
        elif action==setStartPointAction:
            self.addRoutingPoint(0)
        elif action==setEndPointAction:
            self.addRoutingPoint(1)
        elif action==setWayPointAction:
            self.addRoutingPoint(2)
        elif action==showRouteAction:
            self.showRouteForRoutingPoints()
        elif action==clearAllRoutingPointsAction:
            self.startPoint=None
            self.endPoint=None
            self.wayPoints.clear()
        elif action==addFavoriteAction:
            self.addToFavorite(self.mousePos)
        elif action==clearRoutingPointAction:
            self.removeRoutingPoint(self.mousePos)
        elif action==editRoutingPointAction:
            self.editRoutingPoints()
            
        self.mousePressed=False
        self.moving=False
        
    def getCompleteRoutingPoints(self):
        if self.startPoint==None and self.gpsPoint==None:
            return None
        if self.endPoint==None:
            return None
        
        routingPointList=list()
        if self.startPoint!=None:
            routingPointList.append(self.startPoint)
        else:
            routingPointList.append(self.gpsPoint)
        routingPointList.extend(self.wayPoints)
        routingPointList.append(self.endPoint)
        return routingPointList
        
    def editRoutingPoints(self):
        routingPointList=self.getCompleteRoutingPoints()
        if routingPointList==None:
            return
        
        routeDialog=OSMRouteDialog(self, routingPointList)
        result=routeDialog.exec()
        if result==QDialog.Accepted:
            routingPointList=routeDialog.getResult()
            self.setStartPoint(routingPointList[0])            
            self.setEndPoint(routingPointList[-1])            
            self.wayPoints.clear()
            if len(routingPointList)>2:
                for point in routingPointList[1:-1]:
                    self.setWayPoint(point)
                

    def getSelectedRoutingPoint(self, mousePos):
#        (lat, lon)=self.getMousePosition(mousePos[0], mousePos[1])
        return self.getRoutingPointForPos(mousePos)

    def removeRoutingPoint(self, mousePos):
        selectedPoint=self.getSelectedRoutingPoint(mousePos)
        if selectedPoint!=None:
            if selectedPoint==self.startPoint:
                self.startPoint=None
            elif selectedPoint==self.endPoint:
                self.endPoint=None
            else:
                for point in self.wayPoints:
                    if selectedPoint==point:
                        self.wayPoints.remove(selectedPoint)
    
    def addToFavorite(self, mousePos):
        (lat, lon)=self.getMousePosition(mousePos[0], mousePos[1])
        defaultName="favorite"
        wayId, usedRefId, usedPos, country=osmParserData.getWayIdForPos(lat, lon)
        if wayId==None:
            return 
        
        (defaultName, ref)=osmParserData.getStreetInfoWithWayId(wayId, country)

        favNameDialog=QInputDialog(self)
        favNameDialog.setLabelText("Favorite Name")
        favNameDialog.setTextValue(defaultName)
        favNameDialog.setWindowTitle("Add Favorite")
        font = self.font()
        font.setPointSize(14)
        favNameDialog.setFont(font)

        result=favNameDialog.exec()
        if result==QDialog.Accepted:
            favoriteName=favNameDialog.textValue()
            favoritePoint=OSMRoutingPoint(favoriteName, 4, lat, lon)
            self.osmWidget.favoriteList.append(favoritePoint)
            
    def addRoutingPoint(self, pointType):
        (lat, lon)=self.getMousePosition(self.mousePos[0], self.mousePos[1])
        wayId, usedRefId, usedPos, country=osmParserData.getWayIdForPos(lat, lon)
        if wayId==None:
            return
        
        if pointType==0:
            defaultName="start"
            (defaultName, ref)=osmParserData.getStreetInfoWithWayId(wayId, country)

            point=OSMRoutingPoint(defaultName, pointType, lat, lon)
            point.resolveFromPos(osmParserData)
            if point.getSource()!=0:
                self.startPoint=point
            else:
                print("point not usable for routing")
        elif pointType==1:
            defaultName="end"
            (defaultName, ref)=osmParserData.getStreetInfoWithWayId(wayId, country)
                
            point=OSMRoutingPoint(defaultName, pointType, lat, lon)
            point.resolveFromPos(osmParserData)
            if point.getSource()!=0:
                self.endPoint=point
            else:
                print("point not usable for routing")

        elif pointType==2:
            defaultName="way"
            (defaultName, ref)=osmParserData.getStreetInfoWithWayId(wayId, country)

            wayPoint=OSMRoutingPoint(defaultName, pointType, lat, lon)
            wayPoint.resolveFromPos(osmParserData)
            if wayPoint.getSource()!=0:
                self.wayPoints.append(wayPoint)
            else:
                print("point not usable for routing")
        
    def showTrackOnPos(self, actlat, actlon):
        if self.osmWidget.dbLoaded==True:
            polyCountry=osmParserData.countryNameOfPoint(actlat, actlon)
            country=osmParserData.getCountryForPolyCountry(polyCountry)
            print(country)

            wayId, usedRefId, usedPos, country=osmParserData.getWayIdForPos(actlat, actlon)
            if wayId==None:
                self.emit(SIGNAL("updateTrackDisplay(QString)"), "Unknown")
            else:   
                if wayId!=self.lastWayId:
#                    self.lastWayId=wayId
                    print(osmParserData.getCountrysOfWay(wayId))
                    wayId, tags, refs, distances=osmParserData.getWayEntryForIdAndCountry(wayId, country)
                    print("%d %s %s"%(wayId, str(tags), str(refs)))
                    (name, ref)=osmParserData.getStreetInfoWithWayId(wayId, country)
                    print("%s %s"%(name, ref))
#                    print(osmParserData.getStreetEntryForNameAndCountry((name, ref), country))
                    print(osmParserData.getEdgeEntryForWayId(wayId))

                    self.emit(SIGNAL("updateTrackDisplay(QString)"), "%s %s %s"%(name, ref, osmParserData.getCountryNameForIdCountry(country)))
                    if self.gpsPoint!=None:
                        self.gpsPoint.name=name
                            
    def showRouteForRoutingPoints(self):
        if self.osmWidget.dbLoaded==True:         
            routingPointList=self.getCompleteRoutingPoints()
            if routingPointList==None:
                return
            
            self.currentRoute=OSMRoute("current", routingPointList)
            # make sure all are resolved because we cannot access
            # the db from the thread
            self.currentRoute.resolveRoutingPoints(osmParserData)

            self.routeCalculationThread=OSMRouteCalcWorker(self)
            self.connect(self.routeCalculationThread, SIGNAL("routeCalculationDone()"), self.routeCalculationDone)
            self.connect(self.routeCalculationThread, SIGNAL("updateStatus(QString)"), self.updateStatusLabel)
            self.connect(self.routeCalculationThread, SIGNAL("startProgress()"), self.startProgress)
            self.connect(self.routeCalculationThread, SIGNAL("stopProgress()"), self.stopProgress)

            if not self.routeCalculationThread.isRunning():
                self.routeCalculationThread.setup(self.currentRoute)

    def startProgress(self):
        self.emit(SIGNAL("startProgress()"))

    def stopProgress(self):
        self.emit(SIGNAL("stopProgress()"))

    def routeCalculationDone(self):
        if self.currentRoute.getEdgeList()!=None:
            print("cost=%f"%(self.currentRoute.getPathCost()))
            trackList, length=self.currentRoute.printEdgeList(osmParserData)
            print("len=%d"%(length))
            self.setTrack(trackList, True)
        
    def showTrackOnMousePos(self, x, y):
        if self.osmWidget.dbLoaded==True:
            (actlat, actlon)=self.getMousePosition(x, y)
            self.showTrackOnPos(actlat, actlon)

    def showTrackOnGPSPos(self, actLat, actLon):
        self.showTrackOnPos(actLat, actLon)            
    
    def convert_screen_to_geographic(self, pixel_x, pixel_y):
        rlat = self.osmutils.pixel2lat(self.map_zoom, self.map_y + pixel_y);
        rlon = self.osmutils.pixel2lon(self.map_zoom, self.map_x + pixel_x);
        return (rlat, rlon)
    
    def getMousePosition(self, x, y):
        p=self.convert_screen_to_geographic(x, y)
        mouseLat = self.osmutils.rad2deg(p[0])
        mouseLon = self.osmutils.rad2deg(p[1])
        return (mouseLat, mouseLon)
         
    def loadConfig(self, config):
        section="routing"

        if config.hasSection(section):
            for name, value in config.items(section):
                if name[:5]=="point":
                    point=OSMRoutingPoint()
                    point.readFromConfig(value)
                    if point.getType()==0:
                        self.startPoint=point
                    if point.getType()==1:
                        self.endPoint=point
                    if point.getType()==2:
                        self.wayPoints.append(point)
#                if name=="end":
#                    self.endPoint=OSMRoutingPoint()
#                    self.endPoint.readFromConfig(value)
#                if name[:3]=="way":
#                    wayPoint=OSMRoutingPoint()
#                    wayPoint.readFromConfig(value)
#                    self.wayPoints.append(wayPoint)
                    
    def saveConfig(self, config):
        section="routing"
        config.removeSection(section)
        config.addSection(section)
        
        routingPointList=self.getCompleteRoutingPoints()
        if routingPointList!=None:
            i=0
            for point in routingPointList:
                point.saveToConfig(config, section, "point%d"%(i))
                i=i+1
            
#        if self.startPoint!=None:
#            self.startPoint.saveToConfig(config, section, "start")
#            
#        if self.endPoint!=None:
#            self.endPoint.saveToConfig(config, section, "end")
#        
#        i=0
#        for point in self.wayPoints:
#            point.saveToConfig(config, section, "way%d"%(i))
#            i=i+1
        if self.currentRoute!=None:
            self.currentRoute.saveToConfig(config, section, "route0")

        
    def setStartPoint(self, point):
        self.startPoint=point
        self.startPoint.type=0
        self.update()
        
    def setEndPoint(self, point):
        self.endPoint=point
        self.endPoint.type=1
        self.update()
        
    def setWayPoint(self, point):
        point.type=2
        self.wayPoints.append(point)
        self.update()
        
class OSMAdressTableModel(QAbstractTableModel):
    def __init__(self, parent):
        QAbstractTableModel.__init__(self, parent)
        
    def rowCount(self, parent): 
        return len(self.streetList)
    
    def columnCount(self, parent): 
        return 5
      
    def data(self, index, role):
        if role == Qt.TextAlignmentRole:
            return Qt.AlignLeft|Qt.AlignVCenter
        elif role != Qt.DisplayRole:
            return None
        
        if index.row() >= len(self.streetList):
            return ""
        (addressId, refId, country, city, postCode, streetName, houseNumber, lat, lon)=self.streetList[index.row()]

        if index.column()==0:
            return osmParserData.getCountryNameForIdCountry(country)
        elif index.column()==1:
            return city
        elif index.column()==2:
            return postCode
        elif index.column()==3:
            return streetName
        elif index.column()==4:
            return houseNumber
    def headerData(self, col, orientation, role):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                if col==0:
                    return "Country"
                elif col==1:
                    return "City"
                elif col==2:
                    return "Postcode"
                elif col==3:
                    return "Street"
                elif col==4:
                    return "Number"
            elif role == Qt.TextAlignmentRole:
                return Qt.AlignLeft
        return None
    
   
    def update(self, streetList):
        self.streetList=streetList
        self.reset()
        
class OSMAdressDialog(QDialog):
    def __init__(self, parent):
        QDialog.__init__(self, parent) 

        font = self.font()
        font.setPointSize(14)
        self.setFont(font)

        self.streetList=sorted(osmParserData.getAddressList(), key=self.streetNameSort)
#        sorted(self.streetList, key=self.houseNumberSort)
        self.filteredStreetList=self.streetList
        
        self.pointType=0
        self.startPointIcon=QIcon("images/source.png")
        self.endPointIcon=QIcon("images/target.png")
        self.wayPointIcon=QIcon("images/waypoint.png")
        self.selectedAddress=None
        self.initUI()
         
    def streetNameSort(self, item):
        (addressId, refId, country, city, postCode, streetName, houseNumber, lat, lon)=item
        return item[5]

    def houseNumberSort(self, item):
        (addressId, refId, country, city, postCode, streetName, houseNumber, lat, lon)=item
        return item[6]
   
    def getResult(self):
        return (self.selectedAddress, self.pointType)

    def initUI(self):
        top=QVBoxLayout()
        top.setAlignment(Qt.AlignTop)
        
        self.filterEdit=QLineEdit(self)
        self.filterEdit.returnPressed.connect(self._applyFilter)
        self.filterEdit.textChanged.connect(self._applyFilter)
        top.addWidget(self.filterEdit)
        
        self.streetView=QTableView(self)
        top.addWidget(self.streetView)
        
        self.streetViewModel=OSMAdressTableModel(self)
        self.streetViewModel.update(self.filteredStreetList)
        self.streetView.setModel(self.streetViewModel)
        header=QHeaderView(Qt.Horizontal, self.streetView)
        header.setStretchLastSection(True)
        self.streetView.setHorizontalHeader(header)
        self.streetView.setColumnWidth(3, 300)
        self.streetView.setSelectionBehavior(QAbstractItemView.SelectRows)

        actionButtons=QHBoxLayout()
        actionButtons.setAlignment(Qt.AlignBottom|Qt.AlignRight)
        
        self.showPointButton=QPushButton("Show", self)
        self.showPointButton.clicked.connect(self._showPoint)
        self.showPointButton.setEnabled(False)
        actionButtons.addWidget(self.showPointButton)

        self.setStartPointButton=QPushButton("Start", self)
        self.setStartPointButton.clicked.connect(self._setStartPoint)
        self.setStartPointButton.setIcon(self.startPointIcon)
        self.setStartPointButton.setEnabled(False)
        actionButtons.addWidget(self.setStartPointButton)
        
        self.setEndPointButton=QPushButton("End", self)
        self.setEndPointButton.clicked.connect(self._setEndPoint)
        self.setEndPointButton.setIcon(self.endPointIcon)
        self.setEndPointButton.setEnabled(False)
        actionButtons.addWidget(self.setEndPointButton)
        
        self.setWayPointButton=QPushButton("Way", self)
        self.setWayPointButton.clicked.connect(self._setWayPoint)
        self.setWayPointButton.setIcon(self.wayPointIcon)
        self.setWayPointButton.setEnabled(False)
        actionButtons.addWidget(self.setWayPointButton)

        top.addLayout(actionButtons)

        buttons=QHBoxLayout()
        buttons.setAlignment(Qt.AlignBottom|Qt.AlignRight)
        
        style=QCommonStyle()
                
        self.cancelButton=QPushButton("Close", self)
        self.cancelButton.setIcon(style.standardIcon(QStyle.SP_DialogCloseButton))
        self.cancelButton.clicked.connect(self._cancel)
        buttons.addWidget(self.cancelButton)

#        self.okButton=QPushButton("End Point", self)
#        self.okButton.clicked.connect(self._ok)
#        self.okButton.setIcon(style.standardIcon(QStyle.SP_DialogOkButton))
#        self.okButton.setEnabled(False)
#        self.okButton.setDefault(True)
#        buttons.addWidget(self.okButton)

        top.addLayout(buttons)
        
        self.connect(self.streetView.selectionModel(),
                     SIGNAL("selectionChanged(const QItemSelection &, const QItemSelection &)"), self._selectionChanged)

        self.setLayout(top)
        self.setWindowTitle('Way Search')
        self.setGeometry(0, 0, 700, 400)
        
    @pyqtSlot()
    def _selectionChanged(self):
        selmodel = self.streetView.selectionModel()
        current = selmodel.currentIndex()
#        self.okButton.setEnabled(current.isValid())
        self.setEndPointButton.setEnabled(current.isValid())
        self.setStartPointButton.setEnabled(current.isValid())
        self.setWayPointButton.setEnabled(current.isValid())
        self.showPointButton.setEnabled(current.isValid())

        
    @pyqtSlot()
    def _cancel(self):
        self.done(QDialog.Rejected)
        
    @pyqtSlot()
    def _showPoint(self):
        selmodel = self.streetView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self.selectedAddress=self.filteredStreetList[current.row()]
            self.pointType=-1
        self.done(QDialog.Accepted)

#    def _ok(self):
#        selmodel = self.streetView.selectionModel()
#        current = selmodel.currentIndex()
#        if current.isValid():
##            print(self.filteredStreetList[current.row()])
#            self.selectedAddress=self.filteredStreetList[current.row()]
##            print(self.selectedAddress)
#        self.done(QDialog.Accepted)
        
    @pyqtSlot()
    def _setWayPoint(self):
        selmodel = self.streetView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self.selectedAddress=self.filteredStreetList[current.row()]
            self.pointType=2
        self.done(QDialog.Accepted)

    @pyqtSlot()
    def _setStartPoint(self):
        selmodel = self.streetView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self.selectedAddress=self.filteredStreetList[current.row()]
            self.pointType=0
        self.done(QDialog.Accepted)

    @pyqtSlot()
    def _setEndPoint(self):
        selmodel = self.streetView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self.selectedAddress=self.filteredStreetList[current.row()]
            self.pointType=1
        self.done(QDialog.Accepted)
        
    @pyqtSlot()
    def _clearTableSelection(self):
        self.streetView.clearSelection()
#        self.okButton.setEnabled(False)
        self.setWayPointButton.setEnabled(False)
        self.setStartPointButton.setEnabled(False)
        self.setEndPointButton.setEnabled(False)
        self.showPointButton.setEnabled(False)

    @pyqtSlot()
    def _applyFilter(self):
        self._clearTableSelection()
        self.filterValue=self.filterEdit.text()
        if len(self.filterValue)!=0:
            if self.filterValue[-1]!="*":
                self.filterValue=self.filterValue+"*"
            self.filteredStreetList=list()
            filterValueMod=self.filterValue.replace("ue","ü").replace("ae","ä").replace("oe","ö")
            
            for (addressId, refId, country, city, postCode, streetName, houseNumber, lat, lon) in self.streetList:
                if not fnmatch.fnmatch(streetName.upper(), self.filterValue.upper()) and not fnmatch.fnmatch(streetName.upper(), filterValueMod.upper()):
                    continue
                self.filteredStreetList.append((addressId, refId, country, city, postCode, streetName, houseNumber, lat, lon))
        else:
            self.filteredStreetList=self.streetList
        
        self.streetViewModel.update(self.filteredStreetList)

#----------------------------
class OSMFavoriteTableModel(QAbstractTableModel):
    def __init__(self, parent):
        QAbstractTableModel.__init__(self, parent)
        
    def rowCount(self, parent): 
        return len(self.favoriteList)
    
    def columnCount(self, parent): 
        return 1
      
    def data(self, index, role):
        if role == Qt.TextAlignmentRole:
            return Qt.AlignLeft|Qt.AlignVCenter
        elif role != Qt.DisplayRole:
            return None
        
        if index.row() >= len(self.favoriteList):
            return ""
        point=self.favoriteList[index.row()]
        name=point.getName()
        
        if index.column()==0:
            return name
       
    def headerData(self, col, orientation, role):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                if col==0:
                    return "Name"
            elif role == Qt.TextAlignmentRole:
                return Qt.AlignLeft
        return None
    
   
    def update(self, favoriteList):
        self.favoriteList=favoriteList
        self.reset()
        
class OSMFavoritesDialog(QDialog):
    def __init__(self, parent, favoriteList):
        QDialog.__init__(self, parent) 
        font = self.font()
        font.setPointSize(14)
        self.setFont(font)

        self.favoriteList=sorted(favoriteList)
        self.filteredFavoriteList=self.favoriteList

        self.selectedFavorite=None
        self.pointType=0
        self.startPointIcon=QIcon("images/source.png")
        self.endPointIcon=QIcon("images/target.png")
        self.wayPointIcon=QIcon("images/waypoint.png")

        self.initUI()
         
#    def nameSort(self, item):
#       (name, ref)=item
#       return name
   
    def getResult(self):
        return (self.selectedFavorite, self.pointType)
    
    def initUI(self):
        top=QVBoxLayout()
        top.setAlignment(Qt.AlignTop)
        
        self.filterEdit=QLineEdit(self)
        self.filterEdit.setToolTip('Name Filter')
        self.filterEdit.returnPressed.connect(self._applyFilter)
        self.filterEdit.textChanged.connect(self._applyFilter)
        top.addWidget(self.filterEdit)
        
        self.favoriteView=QTableView(self)
        top.addWidget(self.favoriteView)
        
        self.favoriteViewModel=OSMFavoriteTableModel(self)
        self.favoriteViewModel.update(self.filteredFavoriteList)
        self.favoriteView.setModel(self.favoriteViewModel)
        header=QHeaderView(Qt.Horizontal, self.favoriteView)
        header.setStretchLastSection(True)
        self.favoriteView.setHorizontalHeader(header)
        self.favoriteView.setColumnWidth(0, 300)

        actionButtons=QHBoxLayout()
        actionButtons.setAlignment(Qt.AlignBottom|Qt.AlignRight)
        
        self.showPointButton=QPushButton("Show", self)
        self.showPointButton.clicked.connect(self._showPoint)
        self.showPointButton.setEnabled(False)
        actionButtons.addWidget(self.showPointButton)

        self.setStartPointButton=QPushButton("Start", self)
        self.setStartPointButton.clicked.connect(self._setStartPoint)
        self.setStartPointButton.setIcon(self.startPointIcon)
        self.setStartPointButton.setEnabled(False)
        actionButtons.addWidget(self.setStartPointButton)
        
        self.setEndPointButton=QPushButton("End", self)
        self.setEndPointButton.clicked.connect(self._setEndPoint)
        self.setEndPointButton.setIcon(self.endPointIcon)
        self.setEndPointButton.setEnabled(False)
        actionButtons.addWidget(self.setEndPointButton)
        
        self.setWayPointButton=QPushButton("Way", self)
        self.setWayPointButton.clicked.connect(self._setWayPoint)
        self.setWayPointButton.setIcon(self.wayPointIcon)
        self.setWayPointButton.setEnabled(False)
        actionButtons.addWidget(self.setWayPointButton)

        top.addLayout(actionButtons)
        
        buttons=QHBoxLayout()
        buttons.setAlignment(Qt.AlignBottom|Qt.AlignRight)
        
        style=QCommonStyle()

        self.closeButton=QPushButton("Close", self)
        self.closeButton.clicked.connect(self._cancel)
        self.closeButton.setIcon(style.standardIcon(QStyle.SP_DialogCloseButton))
        self.closeButton.setDefault(True)
        buttons.addWidget(self.closeButton)
        top.addLayout(buttons)

        self.connect(self.favoriteView.selectionModel(),
                     SIGNAL("selectionChanged(const QItemSelection &, const QItemSelection &)"), self._selectionChanged)

        self.setLayout(top)
        self.setWindowTitle('Favorites')
        self.setGeometry(0, 0, 400, 400)
        
    @pyqtSlot()
    def _selectionChanged(self):
        selmodel = self.favoriteView.selectionModel()
        current = selmodel.currentIndex()
        self.setEndPointButton.setEnabled(current.isValid())
        self.setStartPointButton.setEnabled(current.isValid())
        self.setWayPointButton.setEnabled(current.isValid())
        self.showPointButton.setEnabled(current.isValid())
        
    @pyqtSlot()
    def _cancel(self):
        self.done(QDialog.Rejected)
        
    @pyqtSlot()
    def _showPoint(self):
        selmodel = self.favoriteView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self.selectedFavorite=self.filteredFavoriteList[current.row()]
            self.pointType=-1
        self.done(QDialog.Accepted)
        
    @pyqtSlot()
    def _setWayPoint(self):
        selmodel = self.favoriteView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self.selectedFavorite=self.filteredFavoriteList[current.row()]
            self.pointType=2
        self.done(QDialog.Accepted)

    @pyqtSlot()
    def _setStartPoint(self):
        selmodel = self.favoriteView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self.selectedFavorite=self.filteredFavoriteList[current.row()]
            self.pointType=0
        self.done(QDialog.Accepted)

    @pyqtSlot()
    def _setEndPoint(self):
        selmodel = self.favoriteView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self.selectedFavorite=self.filteredFavoriteList[current.row()]
            self.pointType=1
        self.done(QDialog.Accepted)
        
    @pyqtSlot()
    def _clearTableSelection(self):
        self.favoriteView.clearSelection()
        self.setWayPointButton.setEnabled(False)
        self.setStartPointButton.setEnabled(False)
        self.setEndPointButton.setEnabled(False)
        self.showPointButton.setEnabled(False)
        
    @pyqtSlot()
    def _applyFilter(self):
        self._clearTableSelection()
        self.filterValue=self.filterEdit.text()
        if len(self.filterValue)!=0:
            if self.filterValue[-1]!="*":
                self.filterValue=self.filterValue+"*"
            self.filteredFavoriteList=list()
            filterValueMod=self.filterValue.replace("ue","ü").replace("ae","ä").replace("oe","ö")
            
            for point in self.favoriteList:
                name=point.getName()
                if not fnmatch.fnmatch(name.upper(), self.filterValue.upper()) and not fnmatch.fnmatch(name.upper(), filterValueMod.upper()):
                    continue
                self.filteredFavoriteList.append(point)
        else:
            self.filteredFavoriteList=self.favoriteList
        
        self.favoriteViewModel.update(self.filteredFavoriteList)
#----------------------------
class OSMRouteTableModel(QAbstractTableModel):
    def __init__(self, parent):
        QAbstractTableModel.__init__(self, parent)
        
    def rowCount(self, parent): 
        return len(self.routingPointList)
    
    def columnCount(self, parent): 
        return 1
      
    def data(self, index, role):
        if role == Qt.TextAlignmentRole:
            return Qt.AlignLeft|Qt.AlignVCenter
        elif role != Qt.DisplayRole:
            return None
        
        if index.row() >= len(self.routingPointList):
            return ""
        point=self.routingPointList[index.row()]
        name=point.getName()
        
        if index.column()==0:
            return name
       
    def headerData(self, col, orientation, role):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                if col==0:
                    return "Routing Point"
            elif role == Qt.TextAlignmentRole:
                return Qt.AlignLeft
        return None
    
   
    def update(self, routingPointList):
        self.routingPointList=routingPointList
        self.reset()
        
class OSMRouteDialog(QDialog):
    def __init__(self, parent, routingPointList):
        QDialog.__init__(self, parent) 
        font = self.font()
        font.setPointSize(14)
        self.setFont(font)

        self.routingPointList=list()
        self.routingPointList.extend(routingPointList)
        self.selectedRoutePoint=None

        self.initUI()
      
    def getResult(self):
        return self.routingPointList
    
    def initUI(self):
        top=QVBoxLayout()
        top.setAlignment(Qt.AlignTop)
                
        self.routeView=QTableView(self)
        top.addWidget(self.routeView)
        
        self.routeViewModel=OSMRouteTableModel(self)
        self.routeViewModel.update(self.routingPointList)
        self.routeView.setModel(self.routeViewModel)
        header=QHeaderView(Qt.Horizontal, self.routeView)
        header.setStretchLastSection(True)
        self.routeView.setHorizontalHeader(header)
        self.routeView.setColumnWidth(0, 300)

        editButtons=QHBoxLayout()
        editButtons.setAlignment(Qt.AlignBottom|Qt.AlignRight)

        style=QCommonStyle()

        self.removePointButton=QPushButton("Remove", self)
        self.removePointButton.clicked.connect(self._removePoint)
        self.removePointButton.setEnabled(False)
        editButtons.addWidget(self.removePointButton)
        
        self.upPointButton=QPushButton("Up", self)
        self.upPointButton.clicked.connect(self._upPoint)
        self.upPointButton.setIcon(style.standardIcon(QStyle.SP_ArrowUp))
        self.upPointButton.setEnabled(False)
        editButtons.addWidget(self.upPointButton)
        
        self.downPointButton=QPushButton("Down", self)
        self.downPointButton.clicked.connect(self._downPoint)
        self.downPointButton.setIcon(style.standardIcon(QStyle.SP_ArrowDown))
        self.downPointButton.setEnabled(False)
        editButtons.addWidget(self.downPointButton)

        self.revertPointsButton=QPushButton("Revert", self)
        self.revertPointsButton.clicked.connect(self._revertRoute)
        self.revertPointsButton.setEnabled(True)
        editButtons.addWidget(self.revertPointsButton)

        top.addLayout(editButtons)

        buttons=QHBoxLayout()
        buttons.setAlignment(Qt.AlignBottom|Qt.AlignRight)
        
        self.cancelButton=QPushButton("Cancel", self)
        self.cancelButton.clicked.connect(self._cancel)
        self.cancelButton.setIcon(style.standardIcon(QStyle.SP_DialogCancelButton))
        buttons.addWidget(self.cancelButton)

        self.okButton=QPushButton("Ok", self)
        self.okButton.clicked.connect(self._ok)
        self.okButton.setDefault(True)
        self.okButton.setIcon(style.standardIcon(QStyle.SP_DialogOkButton))
        buttons.addWidget(self.okButton)
        top.addLayout(buttons)
                
        self.connect(self.routeView.selectionModel(),
                     SIGNAL("selectionChanged(const QItemSelection &, const QItemSelection &)"), self._selectionChanged)

        self.setLayout(top)
        self.setWindowTitle('Routing Point')
        self.setGeometry(0, 0, 400, 400)
        
    @pyqtSlot()
    def _revertRoute(self):
        self.routingPointList.reverse()
        self.routeViewModel.update(self.routingPointList)
        self._selectionChanged()
        
    @pyqtSlot()
    def _ok(self):
        self.done(QDialog.Accepted)

    @pyqtSlot()
    def _selectionChanged(self):
        selmodel = self.routeView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            routingPoint=self.routingPointList[current.row()]
            self.removePointButton.setEnabled(len(self.routingPointList)>2)
            index=self.routingPointList.index(routingPoint)
            self.downPointButton.setEnabled(index>=0 and index<=len(self.routingPointList)-2)                
            self.upPointButton.setEnabled(index<=len(self.routingPointList)-1 and index>=1)
        else:
            self.removePointButton.setEnabled(current.isValid())
            self.upPointButton.setEnabled(current.isValid())
            self.downPointButton.setEnabled(current.isValid())
        
    @pyqtSlot()
    def _cancel(self):
        self.done(QDialog.Rejected)
        
    @pyqtSlot()
    def _removePoint(self):
        selmodel = self.routeView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            routingPoint=self.routingPointList[current.row()]
            self.routingPointList.remove(routingPoint)
            self.routeViewModel.update(self.routingPointList)
            self._selectionChanged()

    @pyqtSlot()
    def _upPoint(self):
        selmodel = self.routeView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            routingPoint=self.routingPointList[current.row()]
            index=self.routingPointList.index(routingPoint)
            if index<=len(self.routingPointList)-1 and index>=1:
                self.routingPointList.remove(routingPoint)
                self.routingPointList.insert(index-1, routingPoint)
            self.routeViewModel.update(self.routingPointList)
            selmodel.setCurrentIndex(self.routeViewModel.index(current.row()-1, current.column()), QItemSelectionModel.ClearAndSelect)


    @pyqtSlot()
    def _downPoint(self):
        selmodel = self.routeView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            routingPoint=self.routingPointList[current.row()]
            index=self.routingPointList.index(routingPoint)
            if index>=0 and index<=len(self.routingPointList)-2:
                self.routingPointList.remove(routingPoint)
                self.routingPointList.insert(index+1, routingPoint)

            self.routeViewModel.update(self.routingPointList)
            selmodel.setCurrentIndex(self.routeViewModel.index(current.row()+1, current.column()), QItemSelectionModel.ClearAndSelect)

    @pyqtSlot()
    def _clearTableSelection(self):
        self.routeView.clearSelection()
        self.removePointButton.setEnabled(False)
        self.upPointButton.setEnabled(False)
        self.downPointButton.setEnabled(False)
        self.revertPointsButton.setEnabled(False)
        
#---------------------

class OSMWidget(QWidget):
    def __init__(self, parent, app):
        QWidget.__init__(self, parent)
        self.startLat=47.8
        self.startLon=13.0
        self.ampelGruen=QIcon("images/ampel-gruen.png")
        self.ampelRot=QIcon("images/ampel-rot.png")
        self.ampelGelb=QIcon("images/ampel-gelb.png")
        self.lastDownloadState=downloadStoppedState
        self.app=app
        self.dbLoaded=False
        self.favoriteList=list()
        self.mapWidgetQt=QtOSMWidget(self)
        
    def addToWidget(self, vbox):       
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
        self.downloadTilesButton.setIcon(self.ampelRot)
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
        
        buttons=QHBoxLayout()        

#        self.testTrackButton=QPushButton("Test Track", self)
#        self.testTrackButton.clicked.connect(self._testTrack)
#        buttons.addWidget(self.testTrackButton)

        self.adressButton=QPushButton("Addresses", self)
        self.adressButton.clicked.connect(self._showAdress)
        self.adressButton.setDisabled(True)
        buttons.addWidget(self.adressButton)
                
        self.favoritesButton=QPushButton("Favorites", self)
        self.favoritesButton.clicked.connect(self._showFavorites)
        self.favoritesButton.setDisabled(True)
        buttons.addWidget(self.favoritesButton)
        
        self.trackLabel=QLabel("", self)
        self.trackLabel.setText("")
        buttons.addWidget(self.trackLabel)
        
        vbox.addLayout(buttons)
        
        self.downloadThread=OSMDownloadTilesWorker(self)
        self.downloadThread.setWidget(self.mapWidgetQt)
        self.connect(self.downloadThread, SIGNAL("updateMap()"), self.mapWidgetQt.updateMap)
        self.connect(self.mapWidgetQt, SIGNAL("updateMousePositionDisplay(float, float)"), self.updateMousePositionDisplay)
        self.connect(self.mapWidgetQt, SIGNAL("updateZoom(int)"), self.updateZoom)
        self.connect(self.downloadThread, SIGNAL("updateDownloadThreadState(QString)"), self.updateDownloadThreadState)
        self.connect(self.mapWidgetQt, SIGNAL("updateTrackDisplay(QString)"), self.updateTrackDisplay)
        self.connect(self.mapWidgetQt, SIGNAL("startProgress()"), self.startProgress)
        self.connect(self.mapWidgetQt, SIGNAL("stopProgress()"), self.stopProgress)

    def startProgress(self):
        self.emit(SIGNAL("startProgress()"))

    def stopProgress(self):
        self.emit(SIGNAL("stopProgress()"))

    @pyqtSlot()
    def _cleanup(self):
        if self.downloadThread.isRunning():
            self.downloadThread.stop()        
        
    def updateTrackDisplay(self, track):
        self.trackLabel.setText(track)
        
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
        self.mapWidgetQt.osm_center_map_to_GPS()   
    
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
            socket.gethostbyname(self.getTileServer())
            self.updateStatusLabel("OSM download server ok")
            return True
        except socket.error:
            self.updateStatusLabel("OSM download server failed. Disabling")
            self.downloadTilesButton.setChecked(False)
            return False
            
    @pyqtSlot()
    def _downloadTiles(self):
        withDownload=self.downloadTilesButton.isChecked()
        if withDownload==True:
            withDownload=self.checkDownloadServer()
#            if  withDownload==False:
#                self.downloadThread.setup()
#        else:
#            if self.downloadThread.isRunning():
#                self.downloadThread.stop()
        self.mapWidgetQt.setDownloadTiles(withDownload)   
        self.downloadTilesButton.setChecked(withDownload==True)

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
        
    def getTileHome(self):
        return self.mapWidgetQt.getTileHome()
    
    def setTileHome(self, value):
        self.mapWidgetQt.setTileHome(value)
                
    def getTileServer(self):
        return self.mapWidgetQt.getTileServer()
    
    def setTileServer(self, value):
        self.mapWidgetQt.setTileServer(value)
        
    def loadConfig(self, config):
        self.setZoomValue(config.getDefaultSection().getint("zoom", 9))
        self.setAutocenterGPSValue(config.getDefaultSection().getboolean("autocenterGPS", False))
        self.setWithDownloadValue(config.getDefaultSection().getboolean("withDownload", False))
        self.setStartLatitude(config.getDefaultSection().getfloat("lat", self.startLat))
        self.setStartLongitude(config.getDefaultSection().getfloat("lon", self.startLon))
        self.setTileHome(config.getDefaultSection().get("tileHome", defaultTileHome))
        self.setTileServer(config.getDefaultSection().get("tileServer", defaultTileServer))

        section="favorites"
        self.favoriteList=list()
        if config.hasSection(section):
            for name, value in config.items(section):
                if name[:8]=="favorite":
                    favoritePoint=OSMRoutingPoint()
                    favoritePoint.readFromConfig(value)
                    self.favoriteList.append(favoritePoint)

        self.mapWidgetQt.loadConfig(config)
        
    def saveConfig(self, config):
        config.getDefaultSection()["zoom"]=str(self.getZoomValue())
        config.getDefaultSection()["autocenterGPS"]=str(self.getAutocenterGPSValue())
        config.getDefaultSection()["withDownload"]=str(self.getWithDownloadValue())
        if self.mapWidgetQt.gpsLatitude!=0.0:
            config.getDefaultSection()["lat"]=str(self.mapWidgetQt.osmutils.rad2deg(self.mapWidgetQt.gpsLatitude))
        else:
            config.getDefaultSection()["lat"]=str(self.mapWidgetQt.osmutils.rad2deg(self.mapWidgetQt.center_rlat))
            
        if self.mapWidgetQt.gpsLongitude!=0.0:    
            config.getDefaultSection()["lon"]=str(self.mapWidgetQt.osmutils.rad2deg(self.mapWidgetQt.gpsLongitude))
        else:
            config.getDefaultSection()["lon"]=str(self.mapWidgetQt.osmutils.rad2deg(self.mapWidgetQt.center_rlon))
            
        config.getDefaultSection()["tileHome"]=self.getTileHome()
        config.getDefaultSection()["tileServer"]=self.getTileServer()
        
        section="favorites"
        config.removeSection(section)
        config.addSection(section)
        i=0
        for point in self.favoriteList:
            point.saveToConfig(config, section, "favorite%d"%(i))
            i=i+1
        
            
        self.mapWidgetQt.saveConfig(config)
        
    def updateDownloadThreadState(self, state):
        if state!=self.lastDownloadState:
            if state==downloadIdleState:
                self.downloadTilesButton.setIcon(self.ampelGelb)
            elif state==downloadRunState:
                self.downloadTilesButton.setIcon(self.ampelGruen)
            elif state==downloadStoppedState:
                self.downloadTilesButton.setIcon(self.ampelRot)
            self.lastDownloadState=state
          
    def updateDataThreadState(self, state):
        if state=="stopped":
            self.adressButton.setDisabled(False)
            self.favoritesButton.setDisabled(False)
            osmParserData.openAllDB()
            self.dbLoaded=True

    def loadData(self):
        self.dataThread=OSMDataLoadWorker(self)
        self.connect(self.dataThread, SIGNAL("updateDataThreadState(QString)"), self.updateDataThreadState)
        self.connect(self.dataThread, SIGNAL("updateStatus(QString)"), self.updateStatusLabel)
        self.connect(self.dataThread, SIGNAL("startProgress()"), self.startProgress)
        self.connect(self.dataThread, SIGNAL("stopProgress()"), self.stopProgress)

        self.dataThread.setup()
        
    @pyqtSlot()
    def _showAdress(self):
        searchDialog=OSMAdressDialog(self)
        result=searchDialog.exec()
        if result==QDialog.Accepted:
            address, pointType=searchDialog.getResult()
            (addressId, refId, country, city, postCode, streetName, houseNumber, lat, lon)=address
            
            if pointType==0:
                routingPoint=OSMRoutingPoint(streetName, pointType, lat, lon)  
                self.mapWidgetQt.setStartPoint(routingPoint) 
            elif pointType==1:
                routingPoint=OSMRoutingPoint(streetName, pointType, lat, lon)  
                self.mapWidgetQt.setEndPoint(routingPoint) 
            elif pointType==2:
                routingPoint=OSMRoutingPoint(streetName, pointType, lat, lon)  
                self.mapWidgetQt.setWayPoint(routingPoint) 
            elif pointType==-1:
                self.mapWidgetQt.osm_center_map_to(self.mapWidgetQt.osmutils.deg2rad(lat),
                               self.mapWidgetQt.osmutils.deg2rad(lon))
  
    @pyqtSlot()
    def _showFavorites(self):
        favoritesDialog=OSMFavoritesDialog(self, self.favoriteList)
        result=favoritesDialog.exec()
        if result==QDialog.Accepted:
            point, pointType=favoritesDialog.getResult()
            if pointType==0:
                routingPoint=OSMRoutingPoint(point.getName(), pointType, point.getLat(), point.getLon())  
                self.mapWidgetQt.setStartPoint(routingPoint) 
            elif pointType==1:
                routingPoint=OSMRoutingPoint(point.getName(), pointType, point.getLat(), point.getLon())  
                self.mapWidgetQt.setEndPoint(routingPoint) 
            elif pointType==2:
                routingPoint=OSMRoutingPoint(point.getName(), pointType, point.getLat(), point.getLon())  
                self.mapWidgetQt.setWayPoint(routingPoint) 
            elif pointType==-1:
                self.mapWidgetQt.osm_center_map_to(self.mapWidgetQt.osmutils.deg2rad(point.getLat()),
                               self.mapWidgetQt.osmutils.deg2rad(point.getLon()))


class OSMWindow(QMainWindow):
    def __init__(self, parent, app):
        QMainWindow.__init__(self, parent)
        font = self.font()
        font.setPointSize(14)
        self.setFont(font)
        self.incLat=0.0
        self.incLon=0.0
        self.app=app
        self.config=Config("osmmapviewer.cfg")
        self.initUI()

    def stopProgress(self):
        self.progress.setMinimum(0)
        self.progress.setMaximum(1)
        self.progress.reset()
    
    def startProgress(self):
        self.progress.setMinimum(0)
        self.progress.setMaximum(0)
        
    def initUI(self):
        self.statusbar=self.statusBar()
        self.progress=QProgressBar()
        self.statusbar.addPermanentWidget(self.progress)

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

        self.osmWidget=OSMWidget(self, self.app)
        self.osmWidget.setStartLatitude(47.8205)
        self.osmWidget.setStartLongitude(13.0170)

        self.osmWidget.addToWidget(osmTabLayout)
        self.osmWidget.loadConfig(self.config)

        self.osmWidget.initHome()

        self.connect(self.osmWidget.mapWidgetQt, SIGNAL("updateStatus(QString)"), self.updateStatusLabel)
        self.connect(self.osmWidget, SIGNAL("updateStatus(QString)"), self.updateStatusLabel)
        self.connect(self.osmWidget.downloadThread, SIGNAL("updateStatus(QString)"), self.updateStatusLabel)
        self.connect(self.osmWidget, SIGNAL("startProgress()"), self.startProgress)
        self.connect(self.osmWidget, SIGNAL("stopProgress()"), self.stopProgress)

        self.osmWidget.loadData()
        
        buttons=QHBoxLayout()        

        self.testGPSButton=QPushButton("Test GPS", self)
        self.testGPSButton.clicked.connect(self._testGPS)
        buttons.addWidget(self.testGPSButton)
                
        top.addLayout(buttons)
        
        self.setGeometry(0, 0, 900, 690)
        self.setWindowTitle('OSM Test')
        self.show()
        
    @pyqtSlot()
    def _testGPS(self):
        if self.incLat==0.0:
            self.incLat=self.osmWidget.startLat
            self.incLon=self.osmWidget.startLon
        else:
            self.incLat=self.incLat+0.001
            self.incLon=self.incLon+0.001
        
        osmutils=OSMUtils()
        print(osmutils.headingDegrees(self.osmWidget.startLat, self.osmWidget.startLon, self.incLat, self.incLon))

        self.osmWidget.updateGPSPosition(self.incLat, self.incLon) 
        
        print("%.0f meter"%(self.osmWidget.mapWidgetQt.osmutils.distance(self.osmWidget.startLat, self.osmWidget.startLon, self.incLat, self.incLon)))

    def updateStatusLabel(self, text):
        self.statusbar.showMessage(text)
        print(text)

    @pyqtSlot()
    def _cleanup(self):
        self.osmWidget.saveConfig(self.config)
        self.config.writeConfig()

        self.osmWidget._cleanup()

def main(argv): 
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
#    widget = OSMWidget(None)
#    widget.initUI()

    widget1 = OSMWindow(None, app)
    app.aboutToQuit.connect(widget1._cleanup)

    sys.exit(app.exec_())

if __name__ == "__main__":
    main(sys.argv)
