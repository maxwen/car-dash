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

from PyQt4.QtCore import QAbstractTableModel, QRectF, Qt, QPoint, QPointF, QSize, pyqtSlot, SIGNAL, QRect, QThread
from PyQt4.QtGui import QTransform, QColor, QFont, QFrame, QValidator, QFormLayout, QComboBox, QAbstractItemView, QCommonStyle, QStyle, QProgressBar, QItemSelectionModel, QInputDialog, QLineEdit, QHeaderView, QTableView, QDialog, QIcon, QLabel, QMenu, QAction, QMainWindow, QTabWidget, QCheckBox, QPalette, QVBoxLayout, QPushButton, QWidget, QPixmap, QSizePolicy, QPainter, QPen, QHBoxLayout, QApplication
from osmparser.osmparserdata import OSMParserData, OSMRoutingPoint, OSMRoute
from config import Config
from osmparser.osmutils import OSMUtils
from gpsutils import GPSMonitorUpateWorker
from gps import gps, misc
from osmdialogs import *
from mapnik.mapnikwrapper import MapnikWrapper

TILESIZE=256
minWidth=640
minHeight=480
MIN_ZOOM=1
MAX_ZOOM=18
MAP_SCROLL_STEP=10
M_LN2=0.69314718055994530942    #log_e 2
IMAGE_WIDTH=64
IMAGE_HEIGHT=64
IMAGE_WIDTH_SMALL=32
IMAGE_HEIGHT_SMALL=32

defaultTileHome=os.path.join("Maps", "osm", "tiles")
defaultTileServer="tile.openstreetmap.org"

idleState="idle"
runState="run"
stoppedState="stopped"

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
        if fileName in self.downloadDoneQueue:
            return
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
                    self.updateMap()
                except IOError:
                    self.updateStatusLabel("OSM download IOError write")
                    
            httpConn.close()
        except socket.error:
            self.updateStatusLabel("OSM download error socket.error")
            self.exiting=True
                
    def run(self):
        self.updateDownloadThreadState(runState)
        while not self.exiting and True:
            if len(self.downloadQueue)!=0:
                entry=self.downloadQueue.popleft()
                self.downloadTile(entry[0], entry[1])
                continue
            
            self.updateStatusLabel("OSM download thread idle")
            self.updateDownloadThreadState(idleState)
            self.osmWidget.setForceDownload(False, False)

            self.msleep(1000) 
            
            if len(self.downloadQueue)==0:
                self.exiting=True
        
        self.forceDownload=False
        self.downloadQueue.clear()
        self.downloadDoneQueue.clear()
#        self.updateMap()
#        self.osmWidget.setForceDownload(False, False)
        self.updateStatusLabel("OSM download thread stopped")
        self.updateDownloadThreadState(stoppedState)


class OSMMapnikTilesWorker(QThread):
    def __init__(self, parent, tileDir, mapFile): 
        QThread.__init__(self, parent)
        self.exiting = False
        self.currentBBox=None
        self.currentZoom=None
        self.lastBBox=None
        self.lastZoom=None
        self.mapnikWrapper=MapnikWrapper(tileDir, mapFile)
        self.connect(self.mapnikWrapper, SIGNAL("updateMap()"), self.updateMap)

    def setWidget(self, osmWidget):
        self.osmWidget=osmWidget
        
    def __del__(self):
        self.exiting = True
        self.wait()
        
    def setup(self):
        self.updateStatusLabel("OSM starting mapnik thread")
        self.exiting = False
        self.start()
            
    def updateStatusLabel(self, text):
        self.emit(SIGNAL("updateStatus(QString)"), text)

    def updateMap(self):
        self.emit(SIGNAL("updateMap()"))
 
    def updateMapnikThreadState(self, state):
        self.emit(SIGNAL("updateMapnikThreadState(QString)"), state)

    def stop(self):
        self.exiting = True
        self.wait()

    def addBboxAndZoom(self, bbox, zoom):
        if self.currentZoom==None and self.currentBBox==None:                    
            self.currentBBox=bbox
            self.currentZoom=zoom
        
        if not self.isRunning():
            self.setup()
                        
    def run(self):
        self.updateMapnikThreadState(runState)
        while not self.exiting and True:
            if self.currentZoom!=None and self.currentBBox!=None:
                self.mapnikWrapper.render_tiles2(self.currentBBox, self.currentZoom)
                self.currentBBox=None
                self.currentZoom=None
            
            self.updateStatusLabel("OSM mapnik thread idle")
            self.updateMapnikThreadState(idleState)

            if self.currentZoom==None and self.currentBBox==None:
                self.msleep(100) 
                self.exiting=True
            else:
                continue
        
        self.updateStatusLabel("OSM mapnik thread stopped")
        self.updateMapnikThreadState(stoppedState)

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
        self.updateRouteCalcThreadState(runState)
        self.startProgress()
        while not self.exiting and True:
            osmParserData.calcRoute(self.route)
            self.exiting=True

        self.updateRouteCalcThreadState(stoppedState)
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

        self.center_x=0
        self.center_y=0
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
        
        self.gpsPointImage=QPixmap("images/gps-move-1.png")
        self.gpsPointImageStop=QPixmap("images/gps-stop-big.png")

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
        
        self.lastEdgeId=None
        self.lastWayId=None
        self.recalcTrigger=0
        self.mousePos=(0, 0)
        self.startPoint=None
        self.endPoint=None
        self.gpsPoint=None
        self.wayPoints=list()
        self.startPointImage=QPixmap("images/source.png")
        self.endPointImage=QPixmap("images/target.png")
        self.wayPointImage=QPixmap("images/waypoint.png")
        self.routeCalculationThread=None
        
        self.turnRightImage=QPixmap("images/directions/right.png")
        self.turnLeftImage=QPixmap("images/directions/left.png")
        self.turnRighHardImage=QPixmap("images/directions/sharply_right.png")
        self.turnLeftHardImage=QPixmap("images/directions/sharply_left.png")
        self.turnRightEasyImage=QPixmap("images/directions/slightly_right.png")
        self.turnLeftEasyImage=QPixmap("images/directions/slightly_left.png")
        self.straightImage=QPixmap("images/directions/forward.png")
        self.uturnImage=QPixmap("images/u-turn.png")
        self.roundaboutImage=QPixmap("images/directions/roundabout.png")
        self.roundabout1Image=QPixmap("images/directions/roundabout_exit1.png")
        self.roundabout2Image=QPixmap("images/directions/roundabout_exit2.png")
        self.roundabout3Image=QPixmap("images/directions/roundabout_exit3.png")
        self.roundabout4Image=QPixmap("images/directions/roundabout_exit4.png")
        self.speedCameraImage=QPixmap("images/speed_camera.png")
        
        self.currentRoute=None
        self.routeList=list()
        self.wayInfo=None
        self.currentEdgeIndexList=None
        self.currentCoords=None
        self.distanceToEnd=0
        self.routeInfo=None
        self.track=None
        self.nextEdgeOnRoute=None
        self.enforcementInfoList=None
        self.speedInfo=None
        self.remainingEdgeList=None
        self.remainingTrackList=None
        
        self.mapnikWrapper=None
        self.lastCenterX=None
        self.lastCenterY=None
        self.withMapRotation=True
        
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
        
    def osm_map_handle_resize (self):
        (self.center_y, self.center_x)=self.getPixelPosForLocationRad(self.center_rlat, self.center_rlon, False)

    def CLAMP(self, x, low, high):
        if x>high:
            return high
        elif x<low:
            return low
        return x

    def getMapZeroPos(self):
        map_x=int(self.center_x-self.width()/2)
        map_y=int(self.center_y-self.height()/2)
        return (map_x, map_y)
    
    def printTilesGeometry(self):
        print("%d %d %d %f %f %s %f %f"%(self.center_x, self.center_y, self.map_zoom, self.osmutils.rad2deg(self.center_rlon), self.osmutils.rad2deg(self.center_rlat), self.getMapZeroPos(), self.osmutils.rad2deg(self.gps_rlon), self.osmutils.rad2deg(self.gps_rlat)))
    
    def showTiles (self):
        
        sizeX=self.width()
        sizeY=self.height()
        
        if sizeX>sizeY:
            maxSize=sizeX
        else:
            maxSize=sizeY
            
        map_x, map_y=self.getMapZeroPos()
        
        offset_x = - map_x % TILESIZE;
        offset_y = - map_y % TILESIZE;
        
        if offset_x > 0:
            offset_x -= TILESIZE
        if offset_y > 0:
            offset_y -= TILESIZE

                
        tiles_nx = int((maxSize  - offset_x) / TILESIZE + 1)
        tiles_ny = int((maxSize - offset_y) / TILESIZE + 1)

        tile_x0 =  int(math.floor(map_x / TILESIZE))
        tile_y0 =  int(math.floor(map_y / TILESIZE))

        i=tile_x0
        j=tile_y0
        offset_y0=offset_y
            
        while i<(tile_x0+tiles_nx):
            while j<(tile_y0+tiles_ny):
                if j<0 or i<0 or i>=math.exp(self.map_zoom * M_LN2) or j>=math.exp(self.map_zoom * M_LN2):
                    pixbuf=self.getEmptyTile()
                else:
                    pixbuf=self.getTile(self.map_zoom, i,j)
                
#                print("%d %d %d %d"%(offset_x, offset_y, i, j))
                self.drawPixmap(offset_x, offset_y, TILESIZE, TILESIZE, pixbuf)                
                offset_y += TILESIZE
                j=j+1
            offset_x += TILESIZE
            offset_y = offset_y0
            i=i+1
            j=tile_y0
        
    def getTileFromFile(self, fileName):
        pixbuf=self.getCachedTile(fileName)
        return pixbuf
       
    def drawPixmap(self, x, y, width, height, pixbuf):
        self.painter.drawPixmap(x, y, width, height, pixbuf)

    def getCachedTile(self, fileName):
        if not fileName in self.tileCache:
            pixbuf = QPixmap(fileName)
            self.tileCache[fileName]=pixbuf
        else:
            pixbuf=self.tileCache[fileName]
            
        return pixbuf
    
    def getEmptyTile(self):
        palette=QPalette()
        emptyPixmap=QPixmap(TILESIZE, TILESIZE)
        emptyPixmap.fill(palette.color(QPalette.Normal, QPalette.Background))
        return emptyPixmap

    def findUpscaledTile (self, zoom, x, y):
        while zoom > 0:
            zoom = zoom - 1
            next_x = int(x / 2)
            next_y = int(y / 2)
#            print("search for bigger map for zoom "+str(zoom))

            pixbuf=self.getExisingTile(zoom, next_x, next_y)
            if pixbuf!=None:
                return (pixbuf, zoom)
            else:
                x=next_x
                y=next_y
        return (None, None)

    def getUpscaledTile(self, zoom, x, y):
#        print("search for bigger map for zoom "+str(zoom))
        (pixbuf, zoom_big)=self.findUpscaledTile(zoom, x, y)
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
            return pixmapNew
        return None
        
    def getExisingTile(self, zoom, x, y):
        fileName=self.getTileFullPath(zoom, x, y)
        if os.path.exists(fileName):
            return self.getCachedTile(fileName)

        return None
    
    def getTile(self, zoom, x, y):
        fileName=self.getTileFullPath(zoom, x, y)
        if os.path.exists(fileName) and self.forceDownload==False:
            return self.getTileFromFile(fileName)
        else:
            if self.withDownload==True:
                self.osmWidget.downloadThread.addTile("/"+str(zoom)+"/"+str(x)+"/"+str(y)+".png", fileName, self.forceDownload, self.getTileServer())
                return self.getTilePlaceholder(zoom, x, y)
                   
            elif self.withMapnik==True:
                self.callMapnikForTile()
                return self.getTilePlaceholder(zoom, x, y)
                    
            return self.getTilePlaceholder(zoom, x, y)
    
    def getTilePlaceholder(self, zoom, x, y):
        # try upscale lower zoom version
        pixbuf=self.getUpscaledTile(zoom, x, y)
        if pixbuf!=None:
            return pixbuf
        else:
            return self.getEmptyTile()

    def drawRotateGPSImageForTrack(self, x, y):
        xPos=int(x-IMAGE_WIDTH/2)
        yPos=int(y-IMAGE_HEIGHT/2)
        self.painter.drawPixmap(xPos, yPos, IMAGE_WIDTH, IMAGE_HEIGHT, self.gpsPointImage)
        
    def osm_gps_show_location(self):
        if self.gps_rlon==0.0 and self.gps_rlat==0.0:
            return
         
        (y, x)=self.getPixelPosForLocationRad(self.gps_rlat, self.gps_rlon, True)

        if self.track==None:
            self.painter.drawPixmap(int(x-self.gpsPointImageStop.width()/2), int(y-self.gpsPointImageStop.height()/2), self.gpsPointImageStop)
        else:
#            print("%f %f"%(self.osmutils.rad2deg(self.gps_rlat), self.osmutils.rad2deg(self.gps_rlon)))
            self.drawRotateGPSImageForTrack(x, y)
        
    def osm_autocenter_map(self, update=True):
        if self.gps_rlat!=0.0 and self.gps_rlon!=0.0:
            (pixel_y, pixel_x)=self.getPixelPosForLocationRad(self.gps_rlat, self.gps_rlon, False)

            x = pixel_x - self.center_x
            y = pixel_y - self.center_y
            width = self.width()
            height = self.height()
            if x < (width/2 - width/8) or x > (width/2 + width/8) or y < (height/2 - height/8) or y > (height/2 + height/8):
                self.center_x=pixel_x
                self.center_y=pixel_y
                self.center_coord_update();
                
            if update==True:
                self.update()
        
    def osm_center_map_to_GPS(self):
        self.osm_center_map_to(self.gps_rlat, self.gps_rlon)
            
    def osm_center_map_to(self, lat, lon):
        if lat!=0.0 and lon!=0.0:
            (pixel_y, pixel_x)=self.getPixelPosForLocationRad(lat, lon, False)
            self.center_x=pixel_x
            self.center_y=pixel_y
            self.center_coord_update();
            self.update()
            
    def osm_map_scroll(self, dx, dy):
        map_x, map_y=self.getMapZeroPos()
        point=QPointF(self.width()/2+dx, self.height()/2+dy)   
        invertedTransform=self.transform0.inverted()
        point0=invertedTransform[0].map(point)
        self.center_y=map_y+point0.y()
        self.center_x=map_x+point0.x()
        self.center_coord_update()
        self.update()
    
    def getVisibleBBox(self):
        return [int(self.center_x-self.width()/2), 
                int(self.center_y+self.height()/2), 
                int(self.center_x+self.width()/2), 
                int(self.center_y-self.height()/2)]

    def getVisibleBBoxDeg(self):
        bbox=self.getVisibleBBox()
        rlon = self.osmutils.pixel2lon(self.map_zoom, bbox[0])
        rlat = self.osmutils.pixel2lat(self.map_zoom, bbox[1])

        rlon2 = self.osmutils.pixel2lon(self.map_zoom, bbox[2])
        rlat2 = self.osmutils.pixel2lat(self.map_zoom, bbox[3])

        return [self.osmutils.rad2deg(rlon), self.osmutils.rad2deg(rlat), self.osmutils.rad2deg(rlon2), self.osmutils.rad2deg(rlat2)]

    # TODO: use track info to create a margin at the right side
    def getVisibleBBoxWithMargin(self):
        bbox=self.getVisibleBBox()
        return [bbox[0]-TILESIZE, bbox[1]+TILESIZE, bbox[2]+TILESIZE, bbox[3]-TILESIZE]
    
    def show(self, zoom, lat, lon):
        self.osm_center_map_to_position(lat, lon)
        self.osm_map_set_zoom(zoom)
        self.update()
    
    def zoom(self, zoom):
        self.osm_map_set_zoom(zoom)
        if self.autocenterGPS==True:
            self.osm_autocenter_map(False)
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
        
        transform = self.painter.worldTransform()
        
        self.transform0=QTransform()
        if self.track!=None and self.withMapRotation==True:
            self.transform0.translate( self.width() / 2, self.height() / 2 )
            self.transform0.rotate(self.track)
            self.transform0.translate( -self.width() / 2, -self.height() / 2 )
            self.painter.setTransform(self.transform0)
            
        self.showTiles()

        if self.currentRoute!=None:
            self.displayRoute(self.currentRoute)
            if self.currentEdgeIndexList!=None:
                self.displayEdgeOfRoute(self.remainingTrackList, self.currentEdgeIndexList)
        
        elif self.currentCoords!=None:
            self.displayEdge(self.currentCoords)
            
        self.showRoutingPoints()            
        self.osm_gps_show_location()
        
        self.painter.setTransform( transform )

        self.showControlOverlay()
        
        self.showTextInfoBackground()
        
        if self.currentRoute!=None and self.remainingTrackList!=None:
            self.showRouteInfo()
            
        self.showTextInfo()
        self.showEnforcementInfo()
        self.showSpeedInfo()
        self.painter.end()
                        
#        self.printTilesGeometry()
  
    def showTextInfoBackground(self):
        textBackground=QRect(0, self.height()-50, self.width(), 50)
        backgroundColor=QColor(120, 120, 120, 200)
        self.painter.fillRect(textBackground, backgroundColor)
        speedBackground=QRect(0, self.height()-130, 80, 80)
        self.painter.fillRect(speedBackground, backgroundColor)
        
        if self.currentRoute!=None and self.remainingTrackList!=None:
            routeInfoBackground=QRect(self.width()-80, self.height()-210, 80, 160)
            self.painter.fillRect(routeInfoBackground, backgroundColor)
            
    def showTextInfo(self):
        pen=QPen()
        pen.setColor(Qt.white)
        self.painter.setPen(pen)
        fm = self.painter.fontMetrics();
                    
        if self.wayInfo!=None:
            wayPos=QPoint(5, self.height()-15)
            self.painter.drawText(wayPos, self.wayInfo)
                    
    def showRouteInfo(self):
        pen=QPen()
        pen.setColor(Qt.white)
        self.painter.setPen(pen)
        fm = self.painter.fontMetrics();

        if self.distanceToEnd!=0:
            distanceToEndPos=QPoint(self.width()-70, self.height()-180)
            
            if self.distanceToEnd>500:
                distanceToEndStr="%.1f km"%(self.distanceToEnd/1000)
            else:
                distanceToEndStr="%d m"%self.distanceToEnd
                
            self.painter.drawText(distanceToEndPos, "%s"%distanceToEndStr)

        if self.routeInfo!=None:
            (direction, crossingLength, crossingInfo, crossingType, crossingRef)=self.routeInfo
            routeInfoPos=QPoint(self.width()-70, self.height()-60)
            
            if crossingLength>500:
                crossingLengthStr="%.1f km"%(crossingLength/1000)
            else:
                crossingLengthStr="%d m"%crossingLength

            crossingInfoStr=crossingInfo

            exitNumber=0
            if direction==40 or direction==41:
                if "roundabout:exit:" in crossingInfo:
                    exitNumber=int(crossingInfo[len("roundabout:exit:"):])
                if "roundabout:enter:" in crossingInfo:
                    exitNumber=int(crossingInfo[len("roundabout:enter:"):])

            if "stay:" in crossingInfo:
                crossingInfoStr="Continue on "+crossingInfoStr[len("stay:"):]
            elif "change:" in crossingInfo:
                crossingInfoStr="Change to "+crossingInfoStr[len("change:"):]
            elif "roundabout:enter:" in crossingInfo:
                crossingInfoStr="Enter roundabout. Take exit %d"%(exitNumber)
            elif "roundabout:exit:" in crossingInfo:
                crossingInfoStr="Exit roundabout at %d"%(exitNumber)
            elif "motorway:exit:info:" in crossingInfo:
                crossingInfoStr="Take motorway exit "+crossingInfoStr[len("motorway:exit:info:"):]
            elif "motorway:exit" in crossingInfo:
                crossingInfoStr="Take motorway exit"
            self.painter.drawText(routeInfoPos, "%s"%crossingLengthStr)
            
            routeInfoPos1=QPoint(self.width()-fm.width(crossingInfoStr)-10, self.height()-15)
            self.painter.drawText(routeInfoPos1, "%s"%(crossingInfoStr))
                            
            x=self.width()-72
            y=self.height()-150
            self.drawDirectionImage(direction, exitNumber, IMAGE_WIDTH, IMAGE_HEIGHT, x, y) 
     
     
    def showEnforcementInfo(self):   
        if self.enforcementInfoList!=None:
            backgroundColor=QColor(120, 120, 120, 200)
            enforcementBackground=QRect(0, self.height()-210, 80, 80)
            self.painter.fillRect(enforcementBackground, backgroundColor)

            x=8
            y=self.height()-202
            self.painter.drawPixmap(x, y, IMAGE_WIDTH, IMAGE_HEIGHT, self.speedCameraImage)
            
            for enforcement in self.enforcementInfoList:
                lat, lon=enforcement["coords"]
                (y, x)=self.getPixelPosForLocationDeg(lat, lon, True)
                self.painter.drawPixmap(x, y, IMAGE_WIDTH_SMALL, IMAGE_HEIGHT_SMALL, self.speedCameraImage)

    def showSpeedInfo(self):   
        if self.speedInfo!=None and self.speedInfo!=0:
            x=8
            y=self.height()-122
#            self.painter.drawText(x, y, "%d"%(self.speedInfo))
            # TODO: check if file exists
            imagePath="images/speedsigns/%d.png"%(self.speedInfo)
            speedPixmap=QPixmap(imagePath)
            self.painter.drawPixmap(x, y, IMAGE_WIDTH, IMAGE_HEIGHT, speedPixmap)

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
#            print("%f %f"%(self.startPoint.lat, self.startPoint.lon))
            (y, x)=self.getPixelPosForLocationDeg(self.startPoint.lat, self.startPoint.lon, True)
#            print("%d %d"%(int(x-self.startPointImage.width()/2), int(y-self.startPointImage.height()/2)))

            self.painter.drawPixmap(int(x-IMAGE_WIDTH/2), int(y-IMAGE_HEIGHT/2), IMAGE_WIDTH, IMAGE_HEIGHT, self.startPointImage)

#            self.painter.setPen(startPointPen)
#            self.painter.drawPoint(x, y)

        if self.endPoint!=None:
            (y, x)=self.getPixelPosForLocationDeg(self.endPoint.lat, self.endPoint.lon, True)
            self.painter.drawPixmap(int(x-IMAGE_WIDTH/2), int(y-IMAGE_HEIGHT/2), IMAGE_WIDTH, IMAGE_HEIGHT, self.endPointImage)

#            self.painter.setPen(endPointPen)
#            self.painter.drawPoint(x, y)
            
        for point in self.wayPoints:
            (y, x)=self.getPixelPosForLocationDeg(point.lat, point.lon, True)
            self.painter.drawPixmap(int(x-IMAGE_WIDTH/2), int(y-IMAGE_HEIGHT/2), IMAGE_WIDTH, IMAGE_HEIGHT, self.wayPointImage)
            
    
    def getPixelPosForLocationDeg(self, lat, lon, relativeToEdge):
        return self.getPixelPosForLocationRad(self.osmutils.deg2rad(lat), self.osmutils.deg2rad(lon), relativeToEdge)
     
    def getPixelPosForLocationRad(self, lat, lon, relativeToEdge):

        if relativeToEdge:
            x=self.osmutils.lon2pixel(self.map_zoom, lon) - (self.center_x-self.width()/2)
            y=self.osmutils.lat2pixel(self.map_zoom, lat) - (self.center_y-self.height()/2)
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
            x=self.osmutils.lon2pixel(zoom, lon) - map_x
            y=self.osmutils.lat2pixel(zoom, lat) - map_y
        else:
            x=self.osmutils.lon2pixel(zoom, lon)
            y=self.osmutils.lat2pixel(zoom, lat)
            
        return (y, x)
    
    def getPenWidthForZoom(self):
#        print(self.map_zoom)
        if self.map_zoom==18:
            return 16
        if self.map_zoom==17:
            return 14
        if self.map_zoom==16:
            return 10
        if self.map_zoom==15:
            return 8
        if self.map_zoom==13 or self.map_zoom==14:
            return 4
        
        return 0
    
    def getPenWithForOverlay(self):
        return self.getPenWidthForZoom()+4

    def getPenWithForPoints(self):
        return self.getPenWidthForZoom()+4
    
    def displayEdge(self, coords):
        greenPen=QPen()
        greenPen.setColor(QColor(0, 0, 255, 100))
        greenPen.setWidth(self.getPenWithForOverlay())
        greenPen.setCapStyle(Qt.RoundCap);
        greenPen.setJoinStyle(Qt.RoundJoin)
        
        lastX=0
        lastY=0

        for point in coords:
            lat, lon=point 
            (y, x)=self.getPixelPosForLocationDeg(lat, lon, True)

            if lastX!=0 and lastY!=0:
                pen=greenPen
                pen.setStyle(Qt.SolidLine)
                self.painter.setPen(pen)
                self.painter.drawLine(x, y, lastX, lastY)

            lastX=x
            lastY=y

    def displayEdgeOfRoute(self, remainingTrackList, edgeIndexList):
        if remainingTrackList!=None:                        
            redPen=QPen()
            redPen.setColor(QColor(0, 0, 255, 100))
            redPen.setWidth(self.getPenWithForOverlay())
            redPen.setCapStyle(Qt.RoundCap);
            redPen.setJoinStyle(Qt.RoundJoin)
            
            lastX=0
            lastY=0

            for index in edgeIndexList:
                if index<len(remainingTrackList):
                    item=remainingTrackList[index]
                    
                    for itemRef in item["refs"]:
                        lat, lon=itemRef["coords"]   
                        (y, x)=self.getPixelPosForLocationDeg(lat, lon, True)
        
                        if lastX!=0 and lastY!=0:
                            pen=redPen
                            pen.setStyle(Qt.SolidLine)
                            self.painter.setPen(pen)
                            self.painter.drawLine(x, y, lastX, lastY)
    
                        lastX=x
                        lastY=y
                        
        
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
            redPen.setWidth(self.getPenWidthForZoom())
            redPen.setCapStyle(Qt.RoundCap);
            redPen.setJoinStyle(Qt.RoundJoin)
            
            blueCrossingPen=QPen()
            blueCrossingPen.setColor(Qt.blue)
            blueCrossingPen.setWidth(self.getPenWithForPoints())
            blueCrossingPen.setCapStyle(Qt.RoundCap);
            
            redCrossingPen=QPen()
            redCrossingPen.setColor(Qt.red)
            redCrossingPen.setWidth(self.getPenWithForPoints())
            redCrossingPen.setCapStyle(Qt.RoundCap);
            
            greenCrossingPen=QPen()
            greenCrossingPen.setColor(Qt.green)
            greenCrossingPen.setWidth(self.getPenWithForPoints())
            greenCrossingPen.setCapStyle(Qt.RoundCap);

            cyanCrossingPen=QPen()
            cyanCrossingPen.setColor(Qt.cyan)
            cyanCrossingPen.setWidth(self.getPenWithForPoints())
            cyanCrossingPen.setCapStyle(Qt.RoundCap);

            grayCrossingPen=QPen()
            grayCrossingPen.setColor(Qt.gray)
            grayCrossingPen.setWidth(self.getPenWithForPoints())
            grayCrossingPen.setCapStyle(Qt.RoundCap);
            
            blackCrossingPen=QPen()
            blackCrossingPen.setColor(Qt.black)
            blackCrossingPen.setWidth(self.getPenWithForPoints())
            blackCrossingPen.setCapStyle(Qt.RoundCap);
            
            yellowCrossingPen=QPen()
            yellowCrossingPen.setColor(Qt.yellow)
            yellowCrossingPen.setWidth(self.getPenWithForPoints())
            yellowCrossingPen.setCapStyle(Qt.RoundCap);
            
            whiteCrossingPen=QPen()
            whiteCrossingPen.setColor(Qt.white)
            whiteCrossingPen.setWidth(self.getPenWithForPoints())
            whiteCrossingPen.setCapStyle(Qt.RoundCap);
            
            motorwayPen=QPen()
            motorwayPen.setColor(Qt.blue)
            motorwayPen.setWidth(self.getPenWidthForZoom())
            motorwayPen.setCapStyle(Qt.RoundCap);
            
            primaryPen=QPen()
            primaryPen.setColor(Qt.red)
            primaryPen.setWidth(self.getPenWidthForZoom())
            primaryPen.setCapStyle(Qt.RoundCap);
            
            residentialPen=QPen()
            residentialPen.setColor(Qt.yellow)
            residentialPen.setWidth(self.getPenWidthForZoom())
            residentialPen.setCapStyle(Qt.RoundCap);
            
            tertiaryPen=QPen()
            tertiaryPen.setColor(Qt.darkYellow)
            tertiaryPen.setWidth(self.getPenWidthForZoom())
            tertiaryPen.setCapStyle(Qt.RoundCap);
            
            linkPen=QPen()
            linkPen.setColor(Qt.black)
            linkPen.setWidth(self.getPenWidthForZoom())
            linkPen.setCapStyle(Qt.RoundCap);

            for item in route.getTrackList():
                streetType=item["type"]
                
                firstItemRef=item["refs"][0]
                firstLat, firstLon=firstItemRef["coords"]
                (firstY, firstX)=self.getPixelPosForLocationDeg(firstLat, firstLon, True)
                for itemRef in item["refs"][1:]:
                    lat, lon=itemRef["coords"]
                        
                    (y, x)=self.getPixelPosForLocationDeg(lat, lon, True)
    
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
                    self.painter.drawLine(x, y, firstX, firstY)
                        
                    firstX=x
                    firstY=y
                    
            if showTrackDetails==True:                                    
                for item in route.getTrackList():
                    for itemRef in item["refs"]:
                        lat, lon=itemRef["coords"]
                            
                        crossing=False
                        
                        if "crossingType" in itemRef:
                            crossing=True
                            crossingType=itemRef["crossingType"]
                            
                        (y, x)=self.getPixelPosForLocationDeg(lat, lon, True)
                        
                        if crossing==True:
                            if crossingType==0:
                                self.painter.setPen(greenCrossingPen)
                                self.painter.drawPoint(x, y)
                            elif crossingType==9:
                                self.painter.setPen(cyanCrossingPen)
                                self.painter.drawPoint(x, y)
                            elif crossingType==1 or crossingType==6:
                                # with traffic signs or stop
                                self.painter.setPen(redCrossingPen)
                                self.painter.drawPoint(x, y)
                            elif crossingType==2 or crossingType==7 or crossingType==8:
                                # motorway junction or _link
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
                            elif crossingType==10:
                                self.painter.setPen(grayCrossingPen)
                                self.painter.drawPoint(x, y)
                            elif crossingType==-1 or crossingType==98 or crossingType==99 or crossingType==100:
                                self.painter.setPen(whiteCrossingPen)
                                self.painter.drawPoint(x, y)

            
            
    def drawDirectionImage(self, direction, exitNumber, width, height, x, y):
        if direction==1:
            self.painter.drawPixmap(x, y, width, height, self.turnRightEasyImage)
        elif direction==2:
            self.painter.drawPixmap(x, y, width, height, self.turnRightImage)
        elif direction==3:
            self.painter.drawPixmap(x, y, width, height, self.turnRighHardImage)
        elif direction==-1:
            self.painter.drawPixmap(x, y, width, height, self.turnLeftEasyImage)
        elif direction==-2:
            self.painter.drawPixmap(x, y, width, height, self.turnLeftImage)
        elif direction==-3:
            self.painter.drawPixmap(x, y, width, height, self.turnLeftHardImage)
        elif direction==0:
            self.painter.drawPixmap(x, y, width, height, self.straightImage)
        elif direction==39:
            # TODO: should be a motorway exit image
            self.painter.drawPixmap(x, y, width, height, self.turnRightEasyImage)
        elif direction==42:
            # TODO: is a link enter always right?
            self.painter.drawPixmap(x, y, width, height, self.turnRightEasyImage)

#        elif direction==40:
#            self.painter.drawPixmap(x, y, width, height, self.roundaboutImage)
        elif direction==41 or direction==40:
            if exitNumber==1:
                self.painter.drawPixmap(x, y, width, height, self.roundabout1Image)
            elif exitNumber==2:
                self.painter.drawPixmap(x, y, width, height, self.roundabout2Image)
            elif exitNumber==3:
                self.painter.drawPixmap(x, y, width, height, self.roundabout3Image)
            elif exitNumber==4:
                self.painter.drawPixmap(x, y, width, height, self.roundabout4Image)
            else:  
                self.painter.drawPixmap(x, y, width, height, self.roundaboutImage)
        elif direction==98:
            self.painter.drawPixmap(x, y, width, height, self.uturnImage)
        elif direction==99:
            self.painter.drawPixmap(x, y, width, height, self.endPointImage)
            
#    def minimumSizeHint(self):
#        return QSize(minWidth, minHeight)

#    def sizeHint(self):
#        return QSize(800, 300)

    def center_coord_update(self):
        self.center_rlon = self.osmutils.pixel2lon(self.map_zoom, self.center_x)
        self.center_rlat = self.osmutils.pixel2lat(self.map_zoom, self.center_y)
        
        # check if we are near the end of the "tiles area"
        # and call for new tiles e.g. download or mapnik

        if self.lastCenterX!=None and self.lastCenterY!=None:
            if abs(self.lastCenterX-self.center_x)>64 or abs(self.lastCenterY-self.center_y)>64:
                if self.withMapnik==True:
                    self.callMapnikForTile()

                self.lastCenterX=self.center_x
                self.lastCenterY=self.center_y
        else:
            self.lastCenterX=self.center_x
            self.lastCenterY=self.center_y
            
    def stepUp(self, step):
        map_x, map_y=self.getMapZeroPos()
        point=QPointF(self.width()/2, self.height()/2-step)   
        invertedTransform=self.transform0.inverted()
        point0=invertedTransform[0].map(point)
        self.center_y=map_y+point0.y()
        self.center_x=map_x+point0.x()
        self.center_coord_update()
        self.update()


    def stepDown(self, step):
        map_x, map_y=self.getMapZeroPos()
        point=QPointF(self.width()/2, self.height()/2+step)   
        invertedTransform=self.transform0.inverted()
        point0=invertedTransform[0].map(point)
        self.center_y=map_y+point0.y()
        self.center_x=map_x+point0.x()
        self.center_coord_update()
        self.update()

    def stepLeft(self, step):
        map_x, map_y=self.getMapZeroPos()
        point=QPointF(self.width()/2-step, self.height()/2)   
        invertedTransform=self.transform0.inverted()
        point0=invertedTransform[0].map(point)
        self.center_y=map_y+point0.y()
        self.center_x=map_x+point0.x()
        self.center_coord_update()
        self.update()

    def stepRight(self, step):
        map_x, map_y=self.getMapZeroPos()
        point=QPointF(self.width()/2+step, self.height()/2)   
        invertedTransform=self.transform0.inverted()
        point0=invertedTransform[0].map(point)
        self.center_y=map_y+point0.y()
        self.center_x=map_x+point0.x()
        self.center_coord_update()
        self.update()

    def updateGPSLocation(self, lat, lon, altitude, speed, track):
#        print("%f-%f"%(lat,lon))
        if speed==0:
            self.stop=True
        else:
            self.stop=False
            self.track=track
        
        if lat!=0.0 and lon!=0.0:
            gps_rlat_new=self.osmutils.deg2rad(lat)
            gps_rlon_new=self.osmutils.deg2rad(lon)
            
            # TODO: only update if gps position changed at least a specific portion
            if gps_rlat_new!=self.gps_rlat or gps_rlon_new!=self.gps_rlon:     
                self.gps_rlat=gps_rlat_new
                self.gps_rlon=gps_rlon_new
                
                self.showTrackOnGPSPos(self.gps_rlat, self.gps_rlon, False)

                if self.wayInfo!=None:
                    self.gpsPoint=OSMRoutingPoint(self.wayInfo, 3, (lat, lon))
                else:
                    self.gpsPoint=None  

                if self.autocenterGPS==True and self.stop==False:
                    self.osm_autocenter_map()
                else:
                    self.update()   
            else:
                if self.autocenterGPS==True and self.stop==False:
                    self.osm_autocenter_map()
                else:
                    self.update()           
        else:
            self.gps_rlat=0.0
            self.gps_rlon=0.0
            self.gpsPoint=None
            self.update()
            
    def cleanImageCache(self):
        self.tileCache.clear()
                
    def getBBoxDifference(self, bbox1, bbox2):
        None
        
    def callMapnikForTile(self):
        bbox=self.getVisibleBBoxWithMargin()     
#        print(bbox)       
        self.osmWidget.mapnikThread.addBboxAndZoom(bbox, self.map_zoom)
        
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
#        else:
#            self.updateMousePositionDisplay(event.x(), event.y())
#            self.showTrackOnMousePos(event.x(), event.y())

            
#    def updateMousePositionDisplay(self, x, y):
#        (lat, lon)=self.getMousePosition(x, y)
#        self.emit(SIGNAL("updateMousePositionDisplay(float, float)"), lat, lon)
        
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
            currentPoint=OSMRoutingPoint("tmp", 5, (lat, lon))                
            self.recalcRouteFromPoint(currentPoint)
        elif action==recalcRouteGPSAction:
            self.recalcRouteFromPoint(self.gpsPoint)

            
        self.mousePressed=False
        self.moving=False
        self.update()
        
    def clearCurrentRoute(self):
        self.currentRoute=None
        self.clearRoute()
        
    # TODO: should also include way points
    def zoomToCompleteRoute(self, routingPointList):
        if len(routingPointList)==0:
            return

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
        routeNameDialog=OSMRouteSaveDialog(self, self.routeList)
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
        edgeId, wayId, usedRefId, usedPos, country=osmParserData.getEdgeIdOnPos(lat, lon)
        if edgeId==None:
            return 
        
        wayId, tags, refs, streetTypeId, name, nameRef=osmParserData.getWayEntryForIdAndCountry(wayId, country)
        defaultPointTag=self.getDefaultPositionTagWithCountry(name, nameRef, country)
        if defaultPointTag==None:
            defaultPointTag=""
            
        favNameDialog=OSMSaveFavoritesDialog(self, self.osmWidget.favoriteList, defaultPointTag)
        result=favNameDialog.exec()
        if result==QDialog.Accepted:
            favoriteName=favNameDialog.getResult()
            favoritePoint=OSMRoutingPoint(favoriteName, 4, (lat, lon))
            self.osmWidget.favoriteList.append(favoritePoint)
            
    def addRoutingPoint(self, pointType):
        (lat, lon)=self.getMousePosition(self.mousePos[0], self.mousePos[1])
        edgeId, wayId, usedRefId, usedPos, country=osmParserData.getEdgeIdOnPos(lat, lon)
        if edgeId==None:
            return
        
        wayId, tags, refs, streetTypeId, name, nameRef=osmParserData.getWayEntryForIdAndCountry(wayId, country)
        defaultPointTag=self.getDefaultPositionTagWithCountry(name, nameRef, country)

        if pointType==0:
            if defaultPointTag!=None:
                defaultName=defaultPointTag
            else:
                defaultName="start"

            point=OSMRoutingPoint(defaultName, pointType, (lat, lon))
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
                
            point=OSMRoutingPoint(defaultName, pointType, (lat, lon))
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

            wayPoint=OSMRoutingPoint(defaultName, pointType, (lat, lon))
            wayPoint.resolveFromPos(osmParserData)
            if wayPoint.getSource()!=0:
                self.wayPoints.append(wayPoint)
            else:
                print("point not usable for routing")
        
    def showRoutingPointOnMap(self, routingPoint):
        if self.map_zoom<15:
            self.osm_map_set_zoom(15)

        self.osm_center_map_to_position(routingPoint.getPos()[0], routingPoint.getPos()[1])

    def showPosPointOnMap(self, lat, lon):
        if self.map_zoom<15:
            self.osm_map_set_zoom(15)

        self.osm_center_map_to_position(lat, lon)

    def getDefaultPositionTag(self, name, nameRef):
        if nameRef!=None and name!=None:
            return "%s %s"%(name, nameRef)
        elif nameRef==None and name!=None:
            return "%s"%(name)
        elif nameRef!=None and name==None:
            return "%s"%(nameRef)
        else:
            return "No name"
        return None

    def getDefaultPositionTagWithCountry(self, name, nameRef, country):
        if nameRef!=None and name!=None:
            return "%s %s - %s"%(name, nameRef, osmParserData.getCountryNameForId(country))
        elif nameRef==None and name!=None:
            return "%s - %s"%(name, osmParserData.getCountryNameForId(country))
        elif nameRef!=None and name==None:
            return "%s - %s"%(nameRef, osmParserData.getCountryNameForId(country))
        else:
            return "No name - %s"%(osmParserData.getCountryNameForId(country))
        return None
    
    def recalcRoute(self, lat, lon, edgeId):
        if self.routeCalculationThread!=None and self.routeCalculationThread.isRunning():
            return 
        
        # we should recalc from the next crossing 
        # else we always get a u-turn on the current edge
        # add a temporary waypoint at the next crossing
#        routingPointList=list()
        recalcPoint=OSMRoutingPoint("tmp", 5, (lat, lon))    
#        routingPointList.append(recalcPoint)
        
        # find the next crossing
        # TODO; use the correct direction
#        (edgeId, startRef, endRef, length, wayId, source, target, cost, reverseCost)=osmParserData.getEdgeEntryForEdgeId(edgeId)
#        country=osmParserData.getCountryOfPos(lat, lon)
#        resultList=osmParserData.getCrossingEntryFor(wayId, country)
#        if len(resultList)!=0:
#            for crossing in resultList:
#                _, wayId, refId, nextWayIdList=crossing
#                lat1, lon1=osmParserData.getCoordsWithRefAndCountry(refId, country)
#                tmpPoint=OSMRoutingPoint("tmpCrossing", 5, (lat1, lon1))    
#                routingPointList.append(tmpPoint)
#                break
        
        if self.currentRoute!=None:
            if self.routeCalculationThread!=None and not self.routeCalculationThread.isRunning():
#                self.recalcRouteFromPointList(routingPointList)
                self.recalcRouteFromPoint(recalcPoint)
                
    def showTrackOnPos(self, lat, lon, update):
        if self.routeCalculationThread!=None and self.routeCalculationThread.isRunning():
            return 
        
#        start=time.time()
        if self.osmWidget.dbLoaded==True:
            edgeId, wayId, usedRefId, usedPos, country=osmParserData.getEdgeIdOnPosForRouting(lat, lon, self.track, self.lastEdgeId, self.nextEdgeOnRoute)
            if edgeId==None:
                self.wayInfo=None
            else:   
                if self.currentRoute!=None:                                               
                    if edgeId!=self.lastEdgeId:
                        if len(self.remainingEdgeList)>1:
                            if edgeId==self.remainingEdgeList[1]: 
                                self.lastEdgeId=edgeId
                                self.recalcTrigger=0
                                self.remainingEdgeList=self.remainingEdgeList[1:]
                                self.remainingTrackList=self.remainingTrackList[1:]
                                if len(self.remainingEdgeList)>1:
                                    self.nextEdgeOnRoute=self.remainingEdgeList[1]
                                else:
                                    self.nextEdgeOnRoute=None
                           
                                self.currentEdgeIndexList=None
                            else:
                                # we are not going to the expected next edge
                                # but way 3 more locations before deciding
                                # to recalculate
                                if self.recalcTrigger==3:
                                    self.recalcTrigger=0
                                    self.recalcRoute(lat, lon, edgeId)
                                    return
                                else:
                                    self.recalcTrigger=self.recalcTrigger+1
                           
                    if edgeId==self.remainingEdgeList[0]:
                        # we can be on the right edge but still the wrong way
                        # check if we are going the right way to the start
#                        heading=osmParserData.getHeadingOnCurrentRouteStart(self.remainingTrackList)
#                        print(heading)
#                        if self.track!=None:
#                            print(self.track)     
                        # look if we are on the tracklist start                   
                        onRoute=osmParserData.checkForPosOnTracklist(lat, lon, self.remainingTrackList)                            
#                        print(onRoute)
                        if onRoute==False:
                            if self.recalcTrigger==3:
                                self.recalcTrigger=0
                                self.recalcRoute(lat, lon, edgeId)
                                return
                            else:
                                self.recalcTrigger=self.recalcTrigger+1
                                self.routeInfo=(98, 0, "Please turn", 98, -1)
                                self.update()
                                return
                            
                        self.recalcTrigger=0
                         
                        self.distanceToEnd=self.getDistanceToEnd(self.remainingEdgeList, self.remainingTrackList, lat, lon, self.currentRoute, usedRefId)
                        (direction, crossingLength, crossingInfo, crossingType, crossingRef, crossingEdgeId)=self.getRouteInformationForPos(self.remainingEdgeList, self.remainingTrackList, lat, lon, self.currentRoute, usedRefId)
                        
                        if crossingEdgeId!=None and crossingEdgeId in self.remainingEdgeList:
                            crossingEdgeIdIndex=self.remainingEdgeList.index(crossingEdgeId)+1
                        else:
                            crossingEdgeIdIndex=len(self.remainingEdgeList)-1
                            
                        self.currentEdgeIndexList=list()
                        for i in range(0, crossingEdgeIdIndex+1, 1):
                            self.currentEdgeIndexList.append(i)
                            
                        if direction!=None:
                            self.routeInfo=(direction, crossingLength, crossingInfo, crossingType, crossingRef)
                        else:
                            self.routeInfo=None
                        
                else:
                    if edgeId!=self.lastEdgeId:
                        self.lastEdgeId=edgeId
                        coords=osmParserData.getCoordsOfEdge(edgeId, country)
                        self.currentCoords=coords
                        self.distanceToEnd=0
                        self.routeInfo=None
                        self.currentEdgeIndexList=None
                        self.nextEdgeOnRoute=None
                          
                if wayId!=self.lastWayId:
                    self.lastWayId=wayId
                    wayId, tags, refs, streetTypeId, name, nameRef, oneway, roundabout, maxspeed=osmParserData.getWayEntryForIdAndCountry3(wayId, country)
                    print("%d %s %s %d %s %s %d %d %d"%(wayId, tags, refs, streetTypeId, name, nameRef, oneway, roundabout, maxspeed))
                    (edgeId, startRef, endRef, length, wayId, source, target, cost, reverseCost)=osmParserData.getEdgeEntryForEdgeId(edgeId)
                    print("%d %d %d %d %d %d %d %f %f"%(edgeId, startRef, endRef, length, wayId, source, target, cost, reverseCost))
                    
#                    osmParserData.printCrossingsForWayId(wayId, country)
                    self.wayInfo=self.getDefaultPositionTagWithCountry(name, nameRef, country)  
                    self.speedInfo=maxspeed
                    # TODO: play sound?
                    self.enforcementInfoList=osmParserData.getEnforcmentsOnWay(wayId, refs)

#            stop=time.time()
#            print("showTrackOnPos:%f"%(stop-start))
            if update==True:
                self.update()
                    
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

    def recalcRouteFromPoint(self, currentPoint):
        if self.osmWidget.dbLoaded==True:  
            # make sure all are resolved because we cannot access
            # the db from the thread
            self.currentRoute.changeRouteFromPoint(currentPoint, osmParserData)
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

    def recalcRouteFromPointList(self, routingPointList):
        if self.osmWidget.dbLoaded==True:  
            # make sure all are resolved because we cannot access
            # the db from the thread
            self.currentRoute.changeRouteFromPointList(routingPointList, osmParserData)
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
#            print("edgeList=%d %s"%(len(self.currentRoute.getEdgeList()), self.currentRoute.getEdgeList()))
#            print("cost=%f"%(self.currentRoute.getPathCost()))
#            print("len=%d"%(self.currentRoute.getLength()))
#            self.printRouteDescription(self.currentRoute)
            # show start pos at zoom level 15
#            self.showRoutingPointOnMap(self.currentRoute.getRoutingPointList()[0])
            
            self.currentCoords=None
            self.distanceToEnd=0
            self.currentEdgeIndexList=None
            self.wayInfo=None
            self.lastEdgeId=self.currentRoute.getEdgeList()[0]
            self.nextEdgeOnRoute=None
            self.lastWayId=None
            self.remainingEdgeList=self.currentRoute.getEdgeList()
            self.remainingTrackList=self.currentRoute.getTrackList()
            self.update()       

    def clearRoute(self):
        self.distanceToEnd=0
        self.currentEdgeIndexList=None
        self.nextEdgeOnRoute=None
        self.wayInfo=None
        self.lastEdgeId=None
        self.lastWayId=None
        self.remainingEdgeList=None
        self.remainingTrackList=None
        
    def printRouteInformationForStep(self, stepNumber, route):
        if route==None or route.getEdgeList()==None:
            self.currentEdgeIndexList=None
            return
        
        if stepNumber>=len(route.getEdgeList()):
            print("no more steps")
            self.currentEdgeIndexList=None
            return

        self.currentCoords=None
        self.currentEdgeIndexList=list()
        self.currentEdgeIndexList.append(stepNumber)
        trackItem=route.getTrackList()[stepNumber]
        self.update()
        print(trackItem)

    def getRouteInformationForPos(self, edgeList, trackList, lat, lon, route, usedRefId):
#        edgeList, trackList=self.getTrackListFromEdge(edgeListIndex, route.getEdgeList(), route.getTrackList())     
#        if edgeList==None or trackList==None:
#            return
#        
        edgeId=edgeList[0]
        (direction, crossingLength, crossingInfo, crossingType, crossingRef, edgeId)=osmParserData.getNextCrossingInfoFromPos(edgeId, trackList, lat, lon, usedRefId)
        if direction!=None and crossingInfo!=None and crossingLength!=None:
            return (direction, crossingLength, crossingInfo, crossingType, crossingRef, edgeId)
             
        return (None, None, None, None, None, None)
      
    def getDistanceToEnd(self, edgeList, trackList, lat, lon, route, usedRefId):
#        edgeList, trackList=self.getTrackListFromEdge(edgeListIndex, route.getEdgeList(), route.getTrackList())
#        if edgeList==None or trackList==None:
#            return
        
        edgeId=edgeList[0]
        distance=osmParserData.getDistanceToEnd(edgeId, trackList, lat, lon, route, usedRefId)
        return distance
    
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
            
            if lastEdgeId!=None:
                indexEnd=edgeList.index(lastEdgeId)+1
            else:
                indexEnd=len(edgeList)
                
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
            self.showTrackOnPos(lat, lon, True)

    def showTrackOnGPSPos(self, rLat, rLon, update):
        if self.osmWidget.dbLoaded==True:
            lat=self.osmutils.rad2deg(rLat)
            lon=self.osmutils.rad2deg(rLon)
            self.showTrackOnPos(lat, lon, update)            
    
    def convert_screen_to_geographic(self, pixel_x, pixel_y):
        point=QPointF(pixel_x, pixel_y)        
        invertedTransform=self.transform0.inverted()
        point0=invertedTransform[0].map(point)        
        map_x, map_y=self.getMapZeroPos()
        rlat = self.osmutils.pixel2lat(self.map_zoom, map_y + point0.y());
        rlon = self.osmutils.pixel2lon(self.map_zoom, map_x + point0.x());
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
        
        i=0
        if self.startPoint!=None:
            self.startPoint.saveToConfig(config, section, "point%d"%(i))
            i=i+1
        
        for point in self.wayPoints:
            point.saveToConfig(config, section, "point%d"%(i))
            i=i+1
        
        if self.endPoint!=None:
            self.endPoint.saveToConfig(config, section, "point%d"%(i))
        
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
        self.lastDownloadState=stoppedState
        self.lastMapnikState=stoppedState
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

        self.gpsSpeedValue=QLabel("%d"%(0), self)
        self.gpsSpeedValue.setFont(font)
        self.gpsSpeedValue.setAlignment(Qt.AlignRight)
        coords.addWidget(self.gpsSpeedValue)

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
#        self.mousePosValueLat=QLabel("%.5f"%(0.0), self)
#        self.mousePosValueLat.setFont(font)
#        self.mousePosValueLat.setAlignment(Qt.AlignRight)
#        coords.addWidget(self.mousePosValueLat)

#        formLayoutMouse.addRow(self.mousePosLabelLat, self.mousePosValueLat)

#        self.mousePosLabelLon=QLabel("", self)
#        self.mousePosValueLon=QLabel("%.5f"%(0.0), self)
#        self.mousePosValueLon.setFont(font)
#        self.mousePosValueLon.setAlignment(Qt.AlignRight)
#        coords.addWidget(self.mousePosValueLon)

#        formLayoutMouse.addRow(self.mousePosLabelLon, self.mousePosValueLon)
        
#        buttons.addLayout(formLayoutMouse)
        
        hbox1.addLayout(buttons)

        vbox.addLayout(hbox1)

    def initWorkers(self):
        self.downloadThread=OSMDownloadTilesWorker(self)
        self.downloadThread.setWidget(self.mapWidgetQt)
        self.connect(self.downloadThread, SIGNAL("updateMap()"), self.mapWidgetQt.updateMap)
#        self.connect(self.mapWidgetQt, SIGNAL("updateMousePositionDisplay(float, float)"), self.updateMousePositionDisplay)
#        self.connect(self.mapWidgetQt, SIGNAL("updateZoom(int)"), self.updateZoom)
        self.connect(self.downloadThread, SIGNAL("updateDownloadThreadState(QString)"), self.updateDownloadThreadState)
#        self.connect(self.mapWidgetQt, SIGNAL("updateTrackDisplay(QString)"), self.updateTrackDisplay)
        self.connect(self.mapWidgetQt, SIGNAL("startProgress()"), self.startProgress)
        self.connect(self.mapWidgetQt, SIGNAL("stopProgress()"), self.stopProgress)

        self.mapnikThread=OSMMapnikTilesWorker(self, self.mapWidgetQt.getTileHomeFullPath(), "/home/maxl/mapnik-shape/osm.xml")
        self.mapnikThread.setWidget(self.mapWidgetQt)
        self.connect(self.mapnikThread, SIGNAL("updateMap()"), self.mapWidgetQt.updateMap)
#        self.connect(self.mapWidgetQt, SIGNAL("updateMousePositionDisplay(float, float)"), self.updateMousePositionDisplay)
#        self.connect(self.mapWidgetQt, SIGNAL("updateZoom(int)"), self.updateZoom)
        self.connect(self.mapnikThread, SIGNAL("updateMapnikThreadState(QString)"), self.updateDownloadThreadState)
#        self.connect(self.mapWidgetQt, SIGNAL("updateTrackDisplay(QString)"), self.updateTrackDisplay)
        self.connect(self.mapnikThread, SIGNAL("startProgress()"), self.startProgress)
        self.connect(self.mapnikThread, SIGNAL("stopProgress()"), self.stopProgress)

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
            self.setWithMapnikValue(optionsDialog.withMapnik)
            self.setWithMapRotationValue(optionsDialog.withMapRotation)
            
    @pyqtSlot()
    def _cleanup(self):
        if self.downloadThread.isRunning():
            self.downloadThread.stop()        
        
        if self.mapnikThread.isRunning():
            self.mapnikThread.stop()
            
#    def updateMousePositionDisplay(self, lat, lon):
#        self.mousePosValueLat.setText("%.5f"%(lat))
#        self.mousePosValueLon.setText("%.5f"%(lon)) 
 
    def updateGPSDataDisplay(self, lat, lon, altitude, speed, track):
        self.mapWidgetQt.updateGPSLocation(lat, lon, altitude, speed, track)

        self.gpsPosValueLat.setText("%.5f"%(lat))
        self.gpsPosValueLon.setText("%.5f"%(lon))   
        self.gpsAltitudeValue.setText("%.1f"%(altitude))
        self.gpsSpeedValue.setText("%d"%(speed))
            
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
        #self.centerGPSButton.setDisabled(value==True)
           
    def getWithDownloadValue(self):
        return self.mapWidgetQt.withDownload

    def getWithMapRotationValue(self):
        return self.mapWidgetQt.withMapRotation
 
    def getWithMapnikValue(self):
        return self.mapWidgetQt.withMapnik

    def setWithDownloadValue(self, value):
        self.mapWidgetQt.withDownload=value
        if value==True:
            self.checkDownloadServer()
            
    def setWithMapRotationValue(self, value):
        self.mapWidgetQt.withMapRotation=value
 
    def setWithMapnikValue(self, value):
        self.mapWidgetQt.withMapnik=value
    
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
        self.setWithMapnikValue(config.getDefaultSection().getboolean("withMapnik", False))
        self.setWithMapRotationValue(config.getDefaultSection().getboolean("withMapRotation", False))

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
        config.getDefaultSection()["withMapnik"]=str(self.getWithMapnikValue())
        config.getDefaultSection()["withMapRotation"]=str(self.getWithMapRotationValue())
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

    def updateMapnikThreadState(self, state):
        if state!=self.lastMapnikState:
            self.lastMapnikState=state
                      
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
            (addressId, refId, country, city, postCode, streetName, houseNumber, lat, lon)=address
            print(refId)
            if houseNumber!=None:
                name=streetName+" "+houseNumber+" - "+osmParserData.getCountryNameForId(country)
            else:
                name=streetName+" - "+osmParserData.getCountryNameForId(country)
            if pointType==0:
                routingPoint=OSMRoutingPoint(name, pointType, (lat, lon))  
                self.mapWidgetQt.setStartPoint(routingPoint) 
                self.mapWidgetQt.showRoutingPointOnMap(routingPoint)
            elif pointType==1:
                routingPoint=OSMRoutingPoint(name, pointType, (lat, lon))  
                self.mapWidgetQt.setEndPoint(routingPoint) 
                self.mapWidgetQt.showRoutingPointOnMap(routingPoint)
            elif pointType==2:
                routingPoint=OSMRoutingPoint(name, pointType, (lat, lon))  
                self.mapWidgetQt.setWayPoint(routingPoint) 
                self.mapWidgetQt.showRoutingPointOnMap(routingPoint)
            elif pointType==-1:
                self.mapWidgetQt.showPosPointOnMap(lat, lon)
  
    @pyqtSlot()
    def _showFavorites(self):
        favoritesDialog=OSMFavoritesDialog(self, self.favoriteList)
        result=favoritesDialog.exec()
        if result==QDialog.Accepted:
            point, pointType, favoriteList=favoritesDialog.getResult()
            self.favoriteList=favoriteList
            if point!=None:
                if pointType==0:
                    routingPoint=OSMRoutingPoint(point.getName(), pointType, point.getPos())  
                    self.mapWidgetQt.setStartPoint(routingPoint) 
                    self.mapWidgetQt.showRoutingPointOnMap(routingPoint)
                elif pointType==1:
                    routingPoint=OSMRoutingPoint(point.getName(), pointType, point.getPos())  
                    self.mapWidgetQt.setEndPoint(routingPoint) 
                    self.mapWidgetQt.showRoutingPointOnMap(routingPoint)
                elif pointType==2:
                    routingPoint=OSMRoutingPoint(point.getName(), pointType, point.getPos())  
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
                self.mapWidgetQt.zoomToCompleteRoute(route.getRoutingPointList())
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
        self.step=0
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
        # 47.820630:13.016850
        self.osmWidget.setStartLatitude(47.820630)
        self.osmWidget.setStartLongitude(13.016850)

        self.osmWidget.addToWidget(top)
        self.osmWidget.loadConfig(self.config)
        
        self.osmWidget.initWorkers()

        self.osmWidget.initHome()

        self.connect(self.osmWidget.mapWidgetQt, SIGNAL("updateStatus(QString)"), self.updateStatusLabel)
        self.connect(self.osmWidget, SIGNAL("updateStatus(QString)"), self.updateStatusLabel)
        self.connect(self.osmWidget.downloadThread, SIGNAL("updateStatus(QString)"), self.updateStatusLabel)
        self.connect(self.osmWidget.mapnikThread, SIGNAL("updateStatus(QString)"), self.updateStatusLabel)
        self.connect(self.osmWidget, SIGNAL("startProgress()"), self.startProgress)
        self.connect(self.osmWidget, SIGNAL("stopProgress()"), self.stopProgress)

        self.osmWidget.loadData()
        
        buttons=QHBoxLayout()        
#
        self.testGPSButton=QPushButton("Test GPS", self)
        self.testGPSButton.clicked.connect(self._testGPS)
        buttons.addWidget(self.testGPSButton)
        
        self.stepRouteButton=QPushButton("Step", self)
        self.stepRouteButton.clicked.connect(self._stepRoute)
        buttons.addWidget(self.stepRouteButton)
        
        self.resetStepRouteButton=QPushButton("Reset Step", self)
        self.resetStepRouteButton.clicked.connect(self._resetStepRoute)
        buttons.addWidget(self.resetStepRouteButton)
        
        self.connectPSButton=QCheckBox("Connect GPS", self)
        self.connectPSButton.clicked.connect(self._connectGPS)
#        buttons.addWidget(self.connectPSButton)
                
        top.addLayout(buttons)
        
        self.statusbar.addPermanentWidget(self.connectPSButton)

        self.setGeometry(0, 0, 900, 500)
        self.setWindowTitle('OSM')
        
        self.updateGPSThread=GPSMonitorUpateWorker(self)
        self.connect(self.updateGPSThread, SIGNAL("updateStatus(QString)"), self.updateStatusLabel)
        self.connect(self.updateGPSThread, SIGNAL("updateGPSThreadState(QString)"), self.updateGPSThreadState)
        self.connect(self.updateGPSThread, SIGNAL("connectGPSFailed()"), self.connectGPSFailed)
        self.connect(self.updateGPSThread, SIGNAL("updateGPSDisplay(PyQt_PyObject)"), self.updateGPSDisplay)

        self.show()
        
    @pyqtSlot()
    def _stepRoute(self):
        self.osmWidget.mapWidgetQt.printRouteInformationForStep(self.step, self.osmWidget.mapWidgetQt.currentRoute)
        self.step=self.step+1
        
    @pyqtSlot()
    def _resetStepRoute(self):
        self.step=0
        
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
            speed=0
            altitude=0
            track=0
             
            if not gps.isnan(session.fix.track):
                track=int(session.fix.track)
            
            if not gps.isnan(session.fix.speed):
                speed=int(session.fix.speed*3.6)
            
            if not gps.isnan(session.fix.altitude):
                altitude=session.fix.altitude
         
            if not gps.isnan(session.fix.latitude) and not gps.isnan(session.fix.longitude):
                self.osmWidget.updateGPSDataDisplay(session.fix.latitude, session.fix.longitude, altitude, speed, track)
            else:
                self.osmWidget.updateGPSDataDisplay(0.0, 0.0, 0.0, 0, None)
        else:            
            self.osmWidget.updateGPSDataDisplay(0.0, 0.0, 0.0, 0, None)

    @pyqtSlot()
    def _testGPS(self):
        if self.incLat==0.0:
            self.incLat=self.osmWidget.startLat
            self.incLon=self.osmWidget.startLon
            self.incTrack=0
        else:
#            self.incLat=self.incLat+0.0001
#            self.incLon=self.incLon+0.0001
            self.incTrack+=5
            if self.incTrack>360:
                self.incTrack=0
        
        osmutils=OSMUtils()
        print(osmutils.headingDegrees(self.osmWidget.startLat, self.osmWidget.startLon, self.incLat, self.incLon))

        self.osmWidget.updateGPSDataDisplay(self.incLat, self.incLon, 42, 1, self.incTrack) 
        
        print("%.0f meter"%(self.osmWidget.mapWidgetQt.osmutils.distance(self.osmWidget.startLat, self.osmWidget.startLon, self.incLat, self.incLon)))

    def updateStatusLabel(self, text):
        self.statusbar.showMessage(text)
#        print(text)

    @pyqtSlot()
    def _cleanup(self):
        if self.updateGPSThread.isRunning():
            self.updateGPSThread.stop()
        
        self.saveConfig()

        self.osmWidget._cleanup()

    def saveConfig(self):
        self.osmWidget.saveConfig(self.config)
        self.config.writeConfig()
        
def main(argv): 
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)

    osmWindow = OSMWindow(None)
    app.aboutToQuit.connect(osmWindow._cleanup)

    sys.exit(app.exec_())

if __name__ == "__main__":
    main(sys.argv)
