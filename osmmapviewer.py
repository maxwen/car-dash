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
import time

from PyQt4.QtCore import QAbstractTableModel, Qt, QPoint, QPointF, QSize, pyqtSlot, SIGNAL, QRect, QThread
from PyQt4.QtGui import QFont, QFrame, QValidator, QFormLayout, QComboBox, QAbstractItemView, QCommonStyle, QStyle, QProgressBar, QItemSelectionModel, QInputDialog, QLineEdit, QHeaderView, QTableView, QDialog, QIcon, QLabel, QMenu, QAction, QMainWindow, QTabWidget, QCheckBox, QPalette, QVBoxLayout, QPushButton, QWidget, QPixmap, QSizePolicy, QPainter, QPen, QHBoxLayout, QApplication
from osmparser.osmparserdata import OSMParserData, OSMRoutingPoint, OSMRoute
from config import Config
from osmparser.osmutils import OSMUtils
from gpsutils import GPSMonitorUpateWorker
from gps import gps, misc
from osmdialogs import *

TILESIZE=256
minWidth=640
minHeight=480
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
        self.gps_rlat=0.0
        self.gps_rlon=0.0
        self.osmutils=OSMUtils()
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
        
        self.currentRoute=None
        self.routeList=list()
        self.wayInfo=None
        
    def getRouteList(self):
        return self.routeList
    
    def setRouteList(self, routeList):
        self.routeList=routeList
        
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

    def minimumSizeHint(self):
        return QSize(minWidth, minHeight)
    
    def init(self):
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)        
        
    def osm_center_map_to_position(self, lat, lon):
        self.osm_center_map_to(self.osmutils.deg2rad(lat), self.osmutils.deg2rad(lon))
        
    def osm_map_set_zoom (self, zoom):
        self.map_zoom = self.CLAMP(zoom, self.min_zoom, self.max_zoom)
        self.osm_map_handle_resize()
#        self.emit(SIGNAL("updateZoom(int)"), self.map_zoom)
        
    def osm_map_handle_resize (self):
        width_center  = self.width() / 2
        height_center = self.height() / 2

        (pixel_y, pixel_x)=self.getPixelPosForLocationRad(self.center_rlat, self.center_rlon, False)

        self.map_x = pixel_x - width_center
        self.map_y = pixel_y - height_center

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
        if self.gps_rlon==0.0 and self.gps_rlat==0.0:
            return
         
        (y, x)=self.getPixelPosForLocationRad(self.gps_rlat, self.gps_rlon, True)

        if self.stop==True:
            self.painter.drawPixmap(int(x-self.gpsPointImageStop.width()/2), int(y-self.gpsPointImageStop.height()/2), self.gpsPointImageStop)
        else:
            self.painter.drawPixmap(int(x-self.gpsPointImage.width()/2), int(y-self.gpsPointImage.height()/2), self.gpsPointImage)
        
    def osm_autocenter_map(self):
        if self.gps_rlat!=0.0 and self.gps_rlon!=0.0:
            (pixel_y, pixel_x)=self.getPixelPosForLocationRad(self.gps_rlat, self.gps_rlon, False)

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
        self.osm_center_map_to(self.gps_rlat, self.gps_rlon)
            
    def osm_center_map_to(self, lat, lon):
        if lat!=0.0 and lon!=0.0:
            (pixel_y, pixel_x)=self.getPixelPosForLocationRad(lat, lon, False)
            width = self.width()
            height = self.height()
            self.map_x = pixel_x - width/2;
            self.map_y = pixel_y - height/2;
            self.center_coord_update();
            self.update()
            
    def osm_map_scroll(self, dx, dy):
        self.map_x += dx
        self.map_y += dy
        self.center_coord_update()
        self.update()
    
    def show(self, zoom, lat, lon):
        self.osm_center_map_to_position(lat, lon)
        self.osm_map_set_zoom(zoom)
        self.update()
    
    def zoom(self, zoom):
        self.osm_map_set_zoom(zoom)
        if self.autocenterGPS==True:
            self.osm_autocenter_map()
        self.update()
       
    def resizeEvent(self, event):
        self.osm_map_handle_resize()
             
    def paintEvent(self, event):
#        print("paintEvent %d-%d"%(self.width(), self.height()))
#        print(self.pos())
#        self.updateGeometry()
        self.painter=QPainter(self)
        font=self.font()
        font.setPointSize(16) 
        self.painter.setFont(font)
        self.painter.setRenderHint(QPainter.Antialiasing)
        self.painter.setRenderHint(QPainter.SmoothPixmapTransform)
        self.osm_gps_map_fill_tiles_pixel()
        self.osm_gps_show_location()
        self.displayRoute(self.currentRoute)
        self.showControlOverlay()
        self.showRoutingPoints()
        self.showTextInfo()
        self.painter.end()
              
    def showTextInfo(self):
        pen=QPen()
        pen.setColor(Qt.black)
        self.painter.setPen(pen)
        fm = self.painter.fontMetrics();
                    
        if self.wayInfo!=None:
            textBackground=QRect(5, self.height()-30, fm.width(self.wayInfo)+10, self.font().pointSize()+10)
            self.painter.fillRect(textBackground, Qt.white)

            pen.setColor(Qt.black)
            self.painter.setPen(pen)
            wayPos=QPoint(10, self.height()-10)
            self.painter.drawText(wayPos, self.wayInfo)
            
        zoomPos=QPoint(10, self.controlWidgetRect.height()+20)
        self.painter.drawText(zoomPos, "Zoom:%d"%(self.map_zoom))
        
    def showRoutingPoints(self):
#        showTrackDetails=self.map_zoom>13
        
#        if showTrackDetails==False:
#            return 
        
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
    
    def getPixelPosForLocationDegForZoom(self, lat, lon, relativeToEdge, zoom, centerLat, centerLon):
        return self.getPixelPosForLocationRadForZoom(self.osmutils.deg2rad(lat), self.osmutils.deg2rad(lon), relativeToEdge, zoom, self.osmutils.deg2rad(centerLat), self.osmutils.deg2rad(centerLon))
     
    def getPixelPosForLocationRadForZoom(self, lat, lon, relativeToEdge, zoom, centerLat, centerLon):

        width_center  = self.width() / 2
        height_center = self.height() / 2

        x=self.osmutils.lon2pixel(zoom, centerLon)
        y=self.osmutils.lat2pixel(zoom, centerLat)

        map_x = x - width_center
        map_y = y - height_center
        
        if relativeToEdge:
            map_x0 = map_x - EXTRA_BORDER
            map_y0 = map_y - EXTRA_BORDER
            x=self.osmutils.lon2pixel(zoom, lon) - map_x0
            y=self.osmutils.lat2pixel(zoom, lat) - map_y0
        else:
            x=self.osmutils.lon2pixel(zoom, lon)
            y=self.osmutils.lat2pixel(zoom, lat)
            
        return (y, x)

#    def setRotation(self, r):
#        self.painter.save()
#        self.painter.translate(TILESIZE/2,TILESIZE/2)
#        self.painter.rotate(90)
#        self.painter.translate(-TILESIZE/2,-TILESIZE/2);
    
    def displayRoute(self, route):
#        There are 20 predefined QColors: Qt::white, Qt::black, Qt::red, 
#        Qt::darkRed, Qt::green, Qt::darkGreen, Qt::blue, Qt::darkBlue, 
#        Qt::cyan, Qt::darkCyan, Qt::magenta, Qt::darkMagenta, Qt::yellow, 
#        Qt::darkYellow, Qt::gray, Qt::darkGray, Qt::lightGray, Qt::color0, 
#        Qt::color1, and Qt::transparent.

#        Qt::SolidLine    Qt::DashLine    Qt::DotLine        
#        Qt::DashDotLine    Qt::DashDotDotLine    Qt::CustomDashLine

        if route!=None:
            # before calculation is done
            if route.getTrackList()==None:
                return
            
            showTrackDetails=self.map_zoom>13
            
            redPen=QPen()
            redPen.setColor(Qt.red)
            redPen.setWidth(4)
            redPen.setCapStyle(Qt.RoundCap);
            redPen.setJoinStyle(Qt.RoundJoin)
            
            blueCrossingPen=QPen()
            blueCrossingPen.setColor(Qt.blue)
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

            grayCrossingPen=QPen()
            grayCrossingPen.setColor(Qt.gray)
            grayCrossingPen.setWidth(min(self.map_zoom, 10))
            grayCrossingPen.setCapStyle(Qt.RoundCap);
            
            blackCrossingPen=QPen()
            blackCrossingPen.setColor(Qt.black)
            blackCrossingPen.setWidth(min(self.map_zoom, 10))
            blackCrossingPen.setCapStyle(Qt.RoundCap);
            
            yellowCrossingPen=QPen()
            yellowCrossingPen.setColor(Qt.yellow)
            yellowCrossingPen.setWidth(min(self.map_zoom, 10))
            yellowCrossingPen.setCapStyle(Qt.RoundCap);

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
            
            lastX=0
            lastY=0

            for item in route.getTrackList():
                streetType=item["type"]
                
                for itemRef in item["refs"]:
                    lat, lon=itemRef["coords"]
                        
                    crossing=False
                    direction=None
                    
                    if "crossing" in itemRef:
                        crossing=True
                        crossingList=itemRef["crossing"]
                    if "crossingInfo" in itemRef:
                        crossingInfo=itemRef["crossingInfo"]
                    if "direction" in itemRef:
                        direction=itemRef["direction"]
    
                    (y, x)=self.getPixelPosForLocationDeg(lat, lon, True)
    
                    if lastX!=0 and lastY!=0:
                        if streetType==3 or streetType==5 or streetType==7 or streetType==9 or streetType==11:
                            pen=linkPen
                        elif streetType==2:
                            pen=motorwayPen
                        elif streetType==6:
                            pen=primaryPen
                        elif streetType==12:
                            pen=residentialPen
                        elif streetType==10:
                            pen=tertiaryPen
                        else:
                            pen=redPen
                            
                        pen.setStyle(Qt.SolidLine)
                            
                        self.painter.setPen(pen)
                        self.painter.drawLine(x, y, lastX, lastY)

                    lastX=x
                    lastY=y
                        
                    if crossing:
                        if showTrackDetails==True:
                            if len(crossingList)==1:
                                _, crossingType, crossingInfo, crossingRef=crossingList[0]
                                
                                if crossingType==0:
                                    self.painter.setPen(greenCrossingPen)
                                    self.painter.drawPoint(x, y)
                                elif crossingType==1 or crossingType==6:
                                    # with traffic signs or stop or with oneway
                                    self.painter.setPen(redCrossingPen)
                                    self.painter.drawPoint(x, y)
                                elif crossingType==2 or crossingType==7 or crossingType==8:
                                    # motorway junction or motorway_link
                                    self.painter.setPen(blueCrossingPen)
                                    self.painter.drawPoint(x, y)
                                elif crossingType==3:
                                    # roundabout enter
                                    self.painter.setPen(yellowCrossingPen)
                                    self.painter.drawPoint(x, y)
                                elif crossingType==4:
                                    # roundabout exit
                                    self.painter.setPen(yellowCrossingPen)
                                    self.painter.drawPoint(x, y)
                                elif crossingType==5:
                                    # mini_roundabout
                                    self.painter.setPen(yellowCrossingPen)
                                    self.painter.drawPoint(x, y)
                                elif crossingType==42:
                                    # no enter oneway
                                    self.painter.setPen(blackCrossingPen)
                                    self.painter.drawPoint(x, y)
                                elif crossingType==9:
                                    self.painter.setPen(grayCrossingPen)
                                    self.painter.drawPoint(x, y)
                    if direction!=None:
                        if showTrackDetails==True:
                            (y, x)=self.getPixelPosForLocationDeg(lat, lon, True)
#                            if crossingType==2 and crossingInfo!=None:
#                                if "exit:" in crossingInfo:
#                                    self.painter.drawPixmap(x, y, self.turnRightImage)
#                            else:
                            if direction in range(1, 3, 1):
                                #right
                                self.painter.drawPixmap(x, y, self.turnRightImage)
                            elif direction in range(-1, -3, -1):
                                #left
                                self.painter.drawPixmap(x, y, self.turnLeftImage)
                                
            
#    def minimumSizeHint(self):
#        return QSize(minWidth, minHeight)

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
            gps_rlat_new=self.osmutils.deg2rad(lat)
            gps_rlon_new=self.osmutils.deg2rad(lon)
            

            # TODO: only update if gps position changed at least a specific portion
            if gps_rlat_new!=self.gps_rlat or gps_rlon_new!=self.gps_rlon:     
                self.stop=False
                self.gps_rlat=gps_rlat_new
                self.gps_rlon=gps_rlon_new
                
                self.showTrackOnGPSPos(self.gps_rlat, self.gps_rlon)

                if self.wayInfo!=None:
                    self.gpsPoint=OSMRoutingPoint(self.wayInfo, 3, lat, lon)
                else:
                    self.gpsPoint=None  

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
            self.stop=True
            self.gps_rlat=0.0
            self.gps_rlon=0.0
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
                self.stepLeft(MAP_SCROLL_STEP)
            if self.rightRect.contains(x, y):
                self.stepRight(MAP_SCROLL_STEP)
            if self.upRect.contains(x, y):
                self.stepUp(MAP_SCROLL_STEP)
            if self.downRect.contains(x, y):
                self.stepDown(MAP_SCROLL_STEP)
        
    def pointInsideZoomOverlay(self, x, y):
        if self.zoomRect.contains(x, y):
            if self.minusRect.contains(x, y):
                zoom=self.map_zoom-1
                if zoom<MIN_ZOOM:
                    zoom=MIN_ZOOM
                self.zoom(zoom)
                
            if self.plusRect.contains(x,y):
                zoom=self.map_zoom+1
                if zoom>MAX_ZOOM:
                    zoom=MAX_ZOOM
                self.zoom(zoom)
        
    def showControlOverlay(self):
        self.painter.drawPixmap(0, 0, self.osmControlImage)

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
            self.osm_map_scroll(dx, dy)
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
        saveRouteAction=QAction("Save Current Route", self)
        showRouteAction=QAction("Show Route", self)
        clearRouteAction=QAction("Clear Current Route", self)
        showPosAction=QAction("Show Position", self)
        zoomToCompleteRoute=QAction("Zoom to Route", self)
        recalcRouteAction=QAction("Recalc Route from here", self)
        recalcRouteGPSAction=QAction("Recalc Route from GPS", self)
        
        menu.addAction(forceDownloadAction)
        menu.addSeparator()
        menu.addAction(setStartPointAction)
        menu.addAction(setEndPointAction)
        menu.addAction(setWayPointAction)
        menu.addAction(addFavoriteAction)
        menu.addAction(showPosAction)
        menu.addSeparator()
        menu.addAction(clearAllRoutingPointsAction)
        menu.addAction(clearRoutingPointAction)
        menu.addAction(editRoutingPointAction)
        menu.addAction(saveRouteAction)
        menu.addSeparator()
        menu.addAction(showRouteAction)
        menu.addAction(clearRouteAction)
        menu.addAction(recalcRouteAction)
        menu.addAction(recalcRouteGPSAction)
        menu.addSeparator()
        menu.addAction(zoomToCompleteRoute)

        addPointDisabled=not self.osmWidget.dbLoaded
        routeIncomplete=self.getCompleteRoutingPoints()==None
        setStartPointAction.setDisabled(addPointDisabled)
        setEndPointAction.setDisabled(addPointDisabled)
        setWayPointAction.setDisabled(addPointDisabled)
        addFavoriteAction.setDisabled(addPointDisabled)
        showPosAction.setDisabled(addPointDisabled)
        saveRouteAction.setDisabled(routeIncomplete)
        clearRoutingPointAction.setDisabled(self.getSelectedRoutingPoint(self.mousePos)==None)
        clearAllRoutingPointsAction.setDisabled(addPointDisabled)
        editRoutingPointAction.setDisabled(routeIncomplete)
        zoomToCompleteRoute.setDisabled(routeIncomplete)
        clearRouteAction.setDisabled(self.currentRoute==None)
        
        showRouteDisabled=not self.osmWidget.dbLoaded or (self.routeCalculationThread!=None and self.routeCalculationThread.isRunning()) or routeIncomplete
        showRouteAction.setDisabled(showRouteDisabled)
        recalcRouteAction.setDisabled(showRouteDisabled or self.currentRoute==None)
        recalcRouteGPSAction.setDisabled(showRouteDisabled or self.currentRoute==None or self.gpsPoint==None)

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
            self.showRouteForRoutingPoints(self.getCompleteRoutingPoints())
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
        elif action==showPosAction:
            self.showPosOnMap()
        elif action==saveRouteAction:
            self.saveCurrentRoute()
        elif action==zoomToCompleteRoute:
            self.zoomToCompleteRoute(self.getCompleteRoutingPoints())
        elif action==clearRouteAction:
            self.clearCurrentRoute()
        elif action==recalcRouteAction:
            (lat, lon)=self.getMousePosition(self.mousePos[0], self.mousePos[1])
            currentPoint=OSMRoutingPoint("tmp", 5, lat, lon)                
            self.recalcRouteFromPos(currentPoint)
        elif action==recalcRouteGPSAction:
            self.recalcRouteFromPos(self.gpsPoint)

            
        self.mousePressed=False
        self.moving=False
        self.update()
        
    def clearCurrentRoute(self):
        self.currentRoute=None
        
    def zoomToCompleteRoute(self, routingPointList):
        if len(routingPointList)==0:
            return
#        bbox=osmParserData.createBBox(routingPointList[0].getLat(), routingPointList[0].getLon(), routingPointList[-1].getLat(), routingPointList[-1].getLon())
#        print(bbox)

        width = self.width()
        height = self.height()
        startLat, startLon=routingPointList[0].getPos()
        endLat, endLon=routingPointList[-1].getPos()
        
        centerLat, centerLon=self.osmutils.linepart(endLat, endLon, startLat, startLon, 0.5)
#        print("%f %f %f %f %f %f"%(startLat, startLon, endLat, endLon, centerLat, centerLon))
        
        for zoom in range(MAX_ZOOM, MIN_ZOOM, -1):
            (pixel_y1, pixel_x1)=self.getPixelPosForLocationDegForZoom(startLat, startLon, True, zoom, centerLat, centerLon)
            (pixel_y2, pixel_x2)=self.getPixelPosForLocationDegForZoom(endLat, endLon, True, zoom, centerLat, centerLon)
        
#            print("%d:%d %d %d %d"%(zoom, pixel_x1, pixel_y1, pixel_x2, pixel_y2))
            if pixel_x1>0 and pixel_x2>0 and pixel_y1>0 and pixel_y2>0:
                if pixel_x1<width and pixel_x2<width and pixel_y1<height and pixel_y2<height:
#                    print("need zoom %d"%(zoom))
                    self.osm_map_set_zoom(zoom)
                    self.osm_center_map_to_position(centerLat, centerLon)
                    break
        
    def saveCurrentRoute(self):
        routeNameDialog=OSMInputDialog(self, "", "Save Route", "Name:")
        result=routeNameDialog.exec()
        if result==QDialog.Accepted:
            name=routeNameDialog.getResult()
            route=OSMRoute(name, self.getCompleteRoutingPoints())
            self.routeList.append(route)

    def showPosOnMap(self):
        posDialog=OSMPositionDialog(self)
        result=posDialog.exec()
        if result==QDialog.Accepted:
            lat, lon=posDialog.getResult()

            if self.map_zoom<15:
                self.osm_map_set_zoom(15)
    
            self.osm_center_map_to_position(lat, lon)

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
        
    def setRoute(self, route):
        self.setRoutingPointsFromList(route.getRoutingPointList())
        
    def setRoutingPointsFromList(self, routingPointList):
        self.setStartPoint(routingPointList[0])            
        self.setEndPoint(routingPointList[-1])            
        self.wayPoints.clear()
        if len(routingPointList)>2:
            for point in routingPointList[1:-1]:
                self.setWayPoint(point)

    def editRoutingPoints(self):
        routingPointList=self.getCompleteRoutingPoints()
        if routingPointList==None:
            return
        
        routeDialog=OSMRouteDialog(self, routingPointList, self.routeList)
        result=routeDialog.exec()
        if result==QDialog.Accepted:
            routingPointList, self.routeList=routeDialog.getResult()
            self.setRoutingPointsFromList(routingPointList)
#            self.showRoutingPointOnMap(self.startPoint)
        elif result==QDialog.Rejected:
            # even in case of cancel we might have save a route
            self.routeList=routeDialog.getRouteList()
            
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
        edgeId, wayId, usedRefId, usedPos, country=osmParserData.getEdgeIdOnPos(lat, lon)
        if edgeId==None:
            return 
        
        wayId, tags, refs, streetTypeId, name, nameRef=osmParserData.getWayEntryForIdAndCountry(wayId, country)
        defaultPointTag=self.getDefaultPositionTag(lat, lon, name, nameRef, country)

        if defaultPointTag!=None:
            defaultName=defaultPointTag
        else:
            defaultName="unknown"
            
        favNameDialog=OSMInputDialog(self, defaultName, "Add Favorite", "Name:")
        result=favNameDialog.exec()
        if result==QDialog.Accepted:
            favoriteName=favNameDialog.getResult()
            favoritePoint=OSMRoutingPoint(favoriteName, 4, lat, lon)
            self.osmWidget.favoriteList.append(favoritePoint)
            
    def addRoutingPoint(self, pointType):
        (lat, lon)=self.getMousePosition(self.mousePos[0], self.mousePos[1])
        edgeId, wayId, usedRefId, usedPos, country=osmParserData.getEdgeIdOnPos(lat, lon)
        if edgeId==None:
            return
        
        wayId, tags, refs, streetTypeId, name, nameRef=osmParserData.getWayEntryForIdAndCountry(wayId, country)
        defaultPointTag=self.getDefaultPositionTag(lat, lon, name, nameRef, country)

        if pointType==0:
            if defaultPointTag!=None:
                defaultName=defaultPointTag
            else:
                defaultName="start"

            point=OSMRoutingPoint(defaultName, pointType, lat, lon)
            point.resolveFromPos(osmParserData)
            if point.getSource()!=0:
                self.startPoint=point
            else:
                print("point not usable for routing")
        elif pointType==1:
            if defaultPointTag!=None:
                defaultName=defaultPointTag
            else:
                defaultName="end"
                
            point=OSMRoutingPoint(defaultName, pointType, lat, lon)
            point.resolveFromPos(osmParserData)
            if point.getSource()!=0:
                self.endPoint=point
            else:
                print("point not usable for routing")

        elif pointType==2:
            if defaultPointTag!=None:
                defaultName=defaultPointTag
            else:
                defaultName="way"

            wayPoint=OSMRoutingPoint(defaultName, pointType, lat, lon)
            wayPoint.resolveFromPos(osmParserData)
            if wayPoint.getSource()!=0:
                self.wayPoints.append(wayPoint)
            else:
                print("point not usable for routing")
        
    def showRoutingPointOnMap(self, routingPoint):
        if self.map_zoom<15:
            self.osm_map_set_zoom(15)

        self.osm_center_map_to_position(routingPoint.getLat(), routingPoint.getLon())

    def showPosPointOnMap(self, lat, lon):
        if self.map_zoom<15:
            self.osm_map_set_zoom(15)

        self.osm_center_map_to_position(lat, lon)

    def getDefaultPositionTag(self, lat, lon, name, nameRef, country):
        if nameRef!=None and name!=None:
            return "%s %s - %s"%(name, nameRef, osmParserData.getCountryNameForId(country))
        elif nameRef==None and name!=None:
            return "%s - %s"%(name, osmParserData.getCountryNameForId(country))
        elif nameRef!=None and name==None:
            return "%s - %s"%(nameRef, osmParserData.getCountryNameForId(country))
        else:
            return "No name - %s"%(osmParserData.getCountryNameForId(country))
        return None

    def showTrackOnPos(self, lat, lon):
        if self.osmWidget.dbLoaded==True:
            edgeId, wayId, usedRefId, usedPos, country=osmParserData.getEdgeIdOnPos(lat, lon)
            if edgeId==None:
#                self.emit(SIGNAL("updateTrackDisplay(QString)"), "Unknown way")
                self.wayInfo=None
            else:   
                if self.currentRoute!=None:
                    self.printRouteInformationForPos(edgeId, lat, lon, self.currentRoute)
                    
                if wayId!=self.lastWayId:
#                    self.lastWayId=wayId
                    wayId, tags, refs, streetTypeId, name, nameRef, oneway, roundabout, maxspeed=osmParserData.getWayEntryForIdAndCountry3(wayId, country)
                    print("%d %d"%(edgeId, wayId))
#                    print(name)
#                    print(oneway)
#                    print(maxspeed)
                    self.wayInfo=self.getDefaultPositionTag(lat, lon, name, nameRef, country)      
                    print(osmParserData.getEdgeEntryForEdgeId(edgeId))                  
#                    print(wayId)
            self.update()
            
#    def setCurrentRoute(self, route):
#        self.setRoutingPointsFromList(route.getRoutingPointList())
#        self.update()
#        
#        self.showRouteForRoutingPoints(route.getRoutingPointList())
        
    def showRouteForRoutingPoints(self, routingPointList):
        if self.osmWidget.dbLoaded==True:  
            # already calculated
            if self.currentRoute!=None:
                if self.currentRoute.getRoutingPointList()==routingPointList:
                    self.routeCalculationDone()
                    return
                  
            # calculate
            self.currentRoute=OSMRoute("current", routingPointList)
            # make sure all are resolved because we cannot access
            # the db from the thread
            self.currentRoute.resolveRoutingPoints(osmParserData)
            if not self.currentRoute.routingPointValid():
                print("route has invalid routing points")
                return

#            self.currentRoute.calcRouteTest(osmParserData)

            self.routeCalculationThread=OSMRouteCalcWorker(self)
            self.connect(self.routeCalculationThread, SIGNAL("routeCalculationDone()"), self.routeCalculationDone)
            self.connect(self.routeCalculationThread, SIGNAL("updateStatus(QString)"), self.updateStatusLabel)
            self.connect(self.routeCalculationThread, SIGNAL("startProgress()"), self.startProgress)
            self.connect(self.routeCalculationThread, SIGNAL("stopProgress()"), self.stopProgress)

            if not self.routeCalculationThread.isRunning():
                self.routeCalculationThread.setup(self.currentRoute)

    def recalcRouteFromPos(self, currentPoint):
        if self.osmWidget.dbLoaded==True:  
            # make sure all are resolved because we cannot access
            # the db from the thread
            self.currentRoute.changeRouteFromPos(currentPoint, osmParserData)
            self.currentRoute.resolveRoutingPoints(osmParserData)
            if not self.currentRoute.routingPointValid():
                print("route has invalid routing points")
                return
            
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
            self.currentRoute.printRoute(osmParserData)
#            print("edgeList=%s"%(self.currentRoute.getEdgeList()))
            print("cost=%f"%(self.currentRoute.getPathCost()))
            print("len=%d"%(self.currentRoute.getLength()))
            self.printRouteDescription(self.currentRoute)
            # show start pos at zoom level 15
#            self.showRoutingPointOnMap(self.currentRoute.getRoutingPointList()[0])
            print(self.currentRoute.getEdgeList())
            self.update()       

    def printRouteInformationForPos(self, edgeId, lat, lon, route):
        edgeList, trackList=route.getTrackListFromEdge(edgeId)
        
        if edgeList==None or trackList==None:
            print("not on route")
            return
        
        (direction, crossingLength, crossingInfo, edgeId)=osmParserData.getNextCrossingInfoFromPos(edgeId, trackList, lat, lon)
        if direction!=None and crossingInfo!=None and crossingLength!=None:
            print("distance to next crossing=%d direction=%s %s"%(crossingLength, self.osmutils.directionName(direction), crossingInfo))

        distanceToEnd=osmParserData.getDistanceToEnd(edgeId, trackList, lat, lon, route)
        print("distance to end=%d"%(distanceToEnd))                        
               
    def getTrackListFromEdge(self, indexEnd, edgeList, trackList):
        if indexEnd < len(edgeList):
            restEdgeList=edgeList[indexEnd:]
            restTrackList=trackList[indexEnd:]
            return restEdgeList, restTrackList
        else:
            return None, None      
               
    def printRouteDescription(self, route):        
        print("start:")
        indexEnd=0
        edgeList=route.getEdgeList()
        trackList=route.getTrackList()
        while True:
            edgeList, trackList=self.getTrackListFromEdge(indexEnd, edgeList, trackList)

            (direction, crossingLength, crossingInfo, crossingType, crossingRef, lastEdgeId)=osmParserData.getNextCrossingInfo(trackList)
            
            if lastEdgeId==None:
                lastEdgeId=edgeList[-1]
            
            indexEnd=edgeList.index(lastEdgeId)+1
            trackListPart=trackList[0:indexEnd]

            name, nameRef=trackListPart[0]["info"]     
            sumLength=0  
            for trackItem in trackListPart:
                length=trackItem["length"]
                sumLength=sumLength+length
            
            print("%s %s %d"%(name, nameRef, sumLength))
            if crossingInfo!=None:
                print("%s %s"%(crossingInfo, self.osmutils.directionName(direction)))

            if indexEnd==len(edgeList):
                break
            
        print("end:")

    def showTrackOnMousePos(self, x, y):
        if self.osmWidget.dbLoaded==True:
            (lat, lon)=self.getMousePosition(x, y)
            self.showTrackOnPos(lat, lon)

    def showTrackOnGPSPos(self, rLat, rLon):
        if self.osmWidget.dbLoaded==True:
            lat=self.osmutils.rad2deg(rLat)
            lon=self.osmutils.rad2deg(rLon)
            self.showTrackOnPos(lat, lon)            
    
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
                    
        section="route"
        self.routeList=list()
        if config.hasSection(section):
            for name, value in config.items(section):
                if name[:5]=="route":
                    route=OSMRoute()
                    route.readFromConfig(value)
                    self.routeList.append(route)

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
        
        section="route"
        config.removeSection(section)
        config.addSection(section)
        i=0
        for route in self.routeList:
            route.saveToConfig(config, section, "route%d"%(i))
            i=i+1

        
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
        

#---------------------

class OSMWidget(QWidget):
    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.startLat=47.8
        self.startLon=13.0
        self.lastDownloadState=downloadStoppedState
        self.dbLoaded=False
        self.favoriteList=list()
        self.mapWidgetQt=QtOSMWidget(self)
        self.favoriteIcon=QIcon("images/favorites.png")
        self.addressIcon=QIcon("images/addresses.png")
        self.routesIccon=QIcon("images/route.png")
        self.centerGPSIcon=QIcon("images/map-gps.png")
        self.settingsIcon=QIcon("images/settings.png")
        self.gpsIcon=QIcon("images/gps.png")
        
    def addToWidget(self, vbox):   
            
        hbox1=QHBoxLayout()
        hbox1.addWidget(self.mapWidgetQt)
        
        buttons=QVBoxLayout()        
        buttons.setAlignment(Qt.AlignLeft|Qt.AlignTop)
        buttons.setSpacing(0)

        iconSize=QSize(48, 48)
        self.adressButton=QPushButton("", self)
        self.adressButton.setIcon(self.addressIcon)
        self.adressButton.setToolTip("Addresses")
        self.adressButton.clicked.connect(self._showAdress)
        self.adressButton.setDisabled(True)
        self.adressButton.setIconSize(iconSize)        
        buttons.addWidget(self.adressButton)
                
        self.favoritesButton=QPushButton("", self)
        self.favoritesButton.setIcon(self.favoriteIcon)
        self.favoritesButton.setToolTip("Favorites")
        self.favoritesButton.clicked.connect(self._showFavorites)
        self.favoritesButton.setDisabled(True)
        self.favoritesButton.setIconSize(iconSize)        
        buttons.addWidget(self.favoritesButton)
        
        self.routesButton=QPushButton("", self)
        self.routesButton.setIcon(self.routesIccon)
        self.routesButton.setToolTip("Routes")
        self.routesButton.clicked.connect(self._loadRoute)
        self.routesButton.setDisabled(True)
        self.routesButton.setIconSize(iconSize)        
        buttons.addWidget(self.routesButton)

        self.centerGPSButton=QPushButton("", self)
        self.centerGPSButton.setToolTip("Center map to GPS")
        self.centerGPSButton.setIcon(self.centerGPSIcon)
        self.centerGPSButton.setIconSize(iconSize)        
        self.centerGPSButton.clicked.connect(self._centerGPS)
        buttons.addWidget(self.centerGPSButton)
        
        self.showGPSDataButton=QPushButton("", self)
        self.showGPSDataButton.setToolTip("Show data from GPS")
        self.showGPSDataButton.setIcon(self.gpsIcon)
        self.showGPSDataButton.setIconSize(iconSize)        
        self.showGPSDataButton.clicked.connect(self._showGPSData)
        buttons.addWidget(self.showGPSDataButton)

        self.optionsButton=QPushButton("", self)
        self.optionsButton.setToolTip("Settings")
        self.optionsButton.setIcon(self.settingsIcon)
        self.optionsButton.setIconSize(iconSize)        
        self.optionsButton.clicked.connect(self._showSettings)
        buttons.addWidget(self.optionsButton)  
              
#        tab=QTabWidget(self)
#        tab.setMaximumSize(QSize(100, 100))
#        buttons.addWidget(tab)
        
        font = QFont("Mono")
        font.setPointSize(14)
        font.setStyleHint(QFont.TypeWriter)

        coords=QVBoxLayout()        
        coords.setAlignment(Qt.AlignLeft|Qt.AlignTop)
        coords.setSpacing(0)
#        coords.setContentsMargins(0, 0, 0, 0)

        buttons.addLayout(coords)

#        gpsTab=QWidget(self)
#        formLayoutGPS=QFormLayout()
#        formLayoutGPS.setAlignment(Qt.AlignRight|Qt.AlignTop)
#        formLayoutGPS.setContentsMargins(0, 0, 0, 0)
#        formLayoutGPS.setSpacing(1)

#        tab.addTab(gpsTab, "GPS") 

#        self.gpsPosLabelLat=QLabel("", self)
        self.gpsPosValueLat=QLabel("%.5f"%(0.0), self)
        self.gpsPosValueLat.setFont(font)
        self.gpsPosValueLat.setAlignment(Qt.AlignRight)
        coords.addWidget(self.gpsPosValueLat)
#        formLayoutGPS.addRow(self.gpsPosLabelLat, self.gpsPosValueLat)

#        self.gpsPosLabelLon=QLabel("", self)
        self.gpsPosValueLon=QLabel("%.5f"%(0.0), self)
        self.gpsPosValueLon.setFont(font)
        self.gpsPosValueLon.setAlignment(Qt.AlignRight)
        coords.addWidget(self.gpsPosValueLon)
#        formLayoutGPS.addRow(self.gpsPosLabelLon, self.gpsPosValueLon)
        
#        self.gpsAltitudeLabel=QLabel("", self)
        self.gpsAltitudeValue=QLabel("%.1f"%(0.0), self)
        self.gpsAltitudeValue.setFont(font)
        self.gpsAltitudeValue.setAlignment(Qt.AlignRight)
        coords.addWidget(self.gpsAltitudeValue)

#        formLayoutGPS.addRow(self.gpsAltitudeLabel, self.gpsAltitudeValue)

#        buttons.addLayout(formLayoutGPS)

#        line = QFrame()
#        line.setFrameShape(QFrame.HLine)
#        line.setFrameShadow(QFrame.Sunken)
#        formLayout.addWidget(line)
    
#        mouseTab=QWidget(self)
#        formLayoutMouse=QFormLayout()
#        formLayoutMouse.setAlignment(Qt.AlignRight|Qt.AlignTop)
#        formLayoutMouse.setContentsMargins(0, 0, 0, 0)
#        formLayoutMouse.setSpacing(1)

#        tab.addTab(mouseTab, "Map") 

#        self.mousePosLabelLat=QLabel("", self)
        self.mousePosValueLat=QLabel("%.5f"%(0.0), self)
        self.mousePosValueLat.setFont(font)
        self.mousePosValueLat.setAlignment(Qt.AlignRight)
        coords.addWidget(self.mousePosValueLat)

#        formLayoutMouse.addRow(self.mousePosLabelLat, self.mousePosValueLat)

#        self.mousePosLabelLon=QLabel("", self)
        self.mousePosValueLon=QLabel("%.5f"%(0.0), self)
        self.mousePosValueLon.setFont(font)
        self.mousePosValueLon.setAlignment(Qt.AlignRight)
        coords.addWidget(self.mousePosValueLon)

#        formLayoutMouse.addRow(self.mousePosLabelLon, self.mousePosValueLon)
        
#        buttons.addLayout(formLayoutMouse)
        
        hbox1.addLayout(buttons)

        vbox.addLayout(hbox1)

        self.downloadThread=OSMDownloadTilesWorker(self)
        self.downloadThread.setWidget(self.mapWidgetQt)
        self.connect(self.downloadThread, SIGNAL("updateMap()"), self.mapWidgetQt.updateMap)
        self.connect(self.mapWidgetQt, SIGNAL("updateMousePositionDisplay(float, float)"), self.updateMousePositionDisplay)
#        self.connect(self.mapWidgetQt, SIGNAL("updateZoom(int)"), self.updateZoom)
        self.connect(self.downloadThread, SIGNAL("updateDownloadThreadState(QString)"), self.updateDownloadThreadState)
#        self.connect(self.mapWidgetQt, SIGNAL("updateTrackDisplay(QString)"), self.updateTrackDisplay)
        self.connect(self.mapWidgetQt, SIGNAL("startProgress()"), self.startProgress)
        self.connect(self.mapWidgetQt, SIGNAL("stopProgress()"), self.stopProgress)

    def startProgress(self):
        self.emit(SIGNAL("startProgress()"))

    def stopProgress(self):
        self.emit(SIGNAL("stopProgress()"))

    @pyqtSlot()
    def _showGPSData(self):
        gpsDataDialog=OSMGPSDataDialog(self)
        result=gpsDataDialog.exec()
        
    @pyqtSlot()
    def _showSettings(self):
        optionsDialog=OSMOptionsDialog(self)
        result=optionsDialog.exec()
        if result==QDialog.Accepted:
            self.setWithDownloadValue(optionsDialog.withDownload)
            self.setAutocenterGPSValue(optionsDialog.followGPS)
            
    @pyqtSlot()
    def _cleanup(self):
        if self.downloadThread.isRunning():
            self.downloadThread.stop()        
        
    def updateMousePositionDisplay(self, lat, lon):
        self.mousePosValueLat.setText("%.5f"%(lat))
        self.mousePosValueLon.setText("%.5f"%(lon)) 
 
    def updateGPSDataDisplay(self, lat, lon, altitude):
        self.mapWidgetQt.updateGPSLocation(lat, lon)

        self.gpsPosValueLat.setText("%.5f"%(lat))
        self.gpsPosValueLon.setText("%.5f"%(lon))   
        self.gpsAltitudeValue.setText("%.1f"%(altitude))
            
    def init(self, lat, lon, zoom):        
        self.mapWidgetQt.init()
        self.mapWidgetQt.show(zoom, lat, lon)  

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
                        
    def checkDownloadServer(self):
        try:
            socket.gethostbyname(self.getTileServer())
            self.updateStatusLabel("OSM download server ok")
            return True
        except socket.error:
            self.updateStatusLabel("OSM download server failed. Disabling")
            self.setWithDownloadValue(False)
            return False
                    
    def updateStatusLabel(self, text):
        self.emit(SIGNAL("updateStatus(QString)"), text)
        
    def getZoomValue(self):
        return self.mapWidgetQt.map_zoom

    def setZoomValue(self, value):
        self.mapWidgetQt.map_zoom=value
#        self.updateZoom(value)

    def getAutocenterGPSValue(self):
        return self.mapWidgetQt.autocenterGPS

    def setAutocenterGPSValue(self, value):
        self.mapWidgetQt.autocenterGPS=value
        self.centerGPSButton.setDisabled(value==True)
           
    def getWithDownloadValue(self):
        return self.mapWidgetQt.withDownload
 
    def setWithDownloadValue(self, value):
        self.mapWidgetQt.withDownload=value
        if value==True:
            self.checkDownloadServer()
        
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
        if self.mapWidgetQt.gps_rlat!=0.0:
            config.getDefaultSection()["lat"]=str(self.mapWidgetQt.osmutils.rad2deg(self.mapWidgetQt.gps_rlat))
        else:
            config.getDefaultSection()["lat"]=str(self.mapWidgetQt.osmutils.rad2deg(self.mapWidgetQt.center_rlat))
            
        if self.mapWidgetQt.gps_rlon!=0.0:    
            config.getDefaultSection()["lon"]=str(self.mapWidgetQt.osmutils.rad2deg(self.mapWidgetQt.gps_rlon))
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
            self.lastDownloadState=state
          
    def updateDataThreadState(self, state):
        if state=="stopped":
            self.adressButton.setDisabled(False)
            self.favoritesButton.setDisabled(False)
            self.routesButton.setDisabled(False)
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
        searchDialog=OSMAdressDialog(self, osmParserData)
        result=searchDialog.exec()
        if result==QDialog.Accepted:
            address, pointType=searchDialog.getResult()
            (refId, country, city, postCode, streetName, houseNumber, lat, lon)=address
            print(refId)
            name=streetName+" "+houseNumber+" - "+osmParserData.getCountryNameForId(country)
            if pointType==0:
                routingPoint=OSMRoutingPoint(name, pointType, lat, lon)  
                self.mapWidgetQt.setStartPoint(routingPoint) 
                self.mapWidgetQt.showRoutingPointOnMap(routingPoint)
            elif pointType==1:
                routingPoint=OSMRoutingPoint(name, pointType, lat, lon)  
                self.mapWidgetQt.setEndPoint(routingPoint) 
                self.mapWidgetQt.showRoutingPointOnMap(routingPoint)
            elif pointType==2:
                routingPoint=OSMRoutingPoint(name, pointType, lat, lon)  
                self.mapWidgetQt.setWayPoint(routingPoint) 
                self.mapWidgetQt.showRoutingPointOnMap(routingPoint)
            elif pointType==-1:
                self.mapWidgetQt.showPosPointOnMap(lat, lon)
  
    @pyqtSlot()
    def _showFavorites(self):
        favoritesDialog=OSMFavoritesDialog(self, self.favoriteList)
        result=favoritesDialog.exec()
        if result==QDialog.Accepted:
            point, pointType=favoritesDialog.getResult()
            if pointType==0:
                routingPoint=OSMRoutingPoint(point.getName(), pointType, point.getLat(), point.getLon())  
                self.mapWidgetQt.setStartPoint(routingPoint) 
                self.mapWidgetQt.showRoutingPointOnMap(routingPoint)
            elif pointType==1:
                routingPoint=OSMRoutingPoint(point.getName(), pointType, point.getLat(), point.getLon())  
                self.mapWidgetQt.setEndPoint(routingPoint) 
                self.mapWidgetQt.showRoutingPointOnMap(routingPoint)
            elif pointType==2:
                routingPoint=OSMRoutingPoint(point.getName(), pointType, point.getLat(), point.getLon())  
                self.mapWidgetQt.setWayPoint(routingPoint) 
                self.mapWidgetQt.showRoutingPointOnMap(routingPoint)
            elif pointType==-1:
                self.mapWidgetQt.showRoutingPointOnMap(point)


    @pyqtSlot()
    def _loadRoute(self):
        routeList=self.mapWidgetQt.getRouteList()
        loadRouteDialog=OSMRouteListDialog(self, routeList, True, True)
        result=loadRouteDialog.exec()
        if result==QDialog.Accepted:
            route, routeList=loadRouteDialog.getResult()
            self.mapWidgetQt.setRouteList(routeList)
            if route!=None:
                self.mapWidgetQt.setRoute(route)
                # show start pos at zoom level 15
#                self.mapWidgetQt.showRoutingPointOnMap(self.mapWidgetQt.startPoint)
                

class OSMWindow(QMainWindow):
    def __init__(self, parent):
        QMainWindow.__init__(self, parent)
        font = self.font()
        font.setPointSize(14)
        self.setFont(font)
        self.incLat=0.0
        self.incLon=0.0
        self.config=Config("osmmapviewer.cfg")
        self.updateGPSThread=None
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
#        mainWidget.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        mainWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)        

        self.setCentralWidget(mainWidget)
        top=QVBoxLayout(mainWidget)        
        
        self.osmWidget=OSMWidget(self)
        self.osmWidget.setStartLatitude(47.8205)
        self.osmWidget.setStartLongitude(13.0170)

        self.osmWidget.addToWidget(top)
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

        self.connectPSButton=QCheckBox("Connect GPS", self)
        self.connectPSButton.clicked.connect(self._connectGPS)
#        buttons.addWidget(self.connectPSButton)
                
        top.addLayout(buttons)
        
        self.statusbar.addPermanentWidget(self.connectPSButton)

        self.setGeometry(0, 0, 900, 500)
        self.setWindowTitle('OSM Test')
        
        self.updateGPSThread=GPSMonitorUpateWorker(self)
        self.connect(self.updateGPSThread, SIGNAL("updateStatus(QString)"), self.updateStatusLabel)
        self.connect(self.updateGPSThread, SIGNAL("updateGPSThreadState(QString)"), self.updateGPSThreadState)
        self.connect(self.updateGPSThread, SIGNAL("connectGPSFailed()"), self.connectGPSFailed)
        self.connect(self.updateGPSThread, SIGNAL("updateGPSDisplay(PyQt_PyObject)"), self.updateGPSDisplay)

        self.show()
        
    @pyqtSlot()
    def _connectGPS(self):
        value=self.connectPSButton.isChecked()
        if value==True:
            self.updateGPSThread.setup(True)
        else:
            self.disconnectGPS()
        
    def disconnectGPS(self):
        if self.updateGPSThread.isRunning():
            self.updateGPSThread.stop()
        
    def updateGPSThreadState(self, state):
#        print("updateGPSThreadState:%s"%(state))
        None
    
    def connectGPSFailed(self):
        self.connectPSButton.setChecked(False)
    
    def updateGPSDisplay(self, session):
#        print("OSMWindow:updateGPSDisplay")

        if session!=None:            
            if not gps.isnan(session.fix.latitude) and not gps.isnan(session.fix.longitude):
                altitude=session.fix.altitude
                self.osmWidget.updateGPSDataDisplay(session.fix.latitude, session.fix.longitude, altitude)
            else:
                self.osmWidget.updateGPSDataDisplay(0.0, 0.0, 0.0)
        else:            
            self.osmWidget.updateGPSDataDisplay(0.0, 0.0, 0.0)

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

        self.osmWidget.updateGPSDataDisplay(self.incLat, self.incLon, 42.01) 
        
        print("%.0f meter"%(self.osmWidget.mapWidgetQt.osmutils.distance(self.osmWidget.startLat, self.osmWidget.startLon, self.incLat, self.incLon)))

    def updateStatusLabel(self, text):
        self.statusbar.showMessage(text)
        print(text)

    @pyqtSlot()
    def _cleanup(self):
        if self.updateGPSThread.isRunning():
            self.updateGPSThread.stop()
        
        self.osmWidget.saveConfig(self.config)
        self.config.writeConfig()

        self.osmWidget._cleanup()

def main(argv): 
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)

    osmWindow = OSMWindow(None)
    app.aboutToQuit.connect(osmWindow._cleanup)

    sys.exit(app.exec_())

if __name__ == "__main__":
    main(sys.argv)
