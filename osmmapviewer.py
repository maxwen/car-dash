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
from collections import deque, OrderedDict
import time
import env
import cProfile

from PyQt4.QtCore import QAbstractTableModel, QRectF, Qt, QPoint, QPointF, QSize, pyqtSlot, SIGNAL, QRect, QThread
from PyQt4.QtGui import QLinearGradient, QFileDialog, QPolygon, QTransform, QColor, QFont, QFrame, QValidator, QFormLayout, QComboBox, QAbstractItemView, QCommonStyle, QStyle, QProgressBar, QItemSelectionModel, QInputDialog, QLineEdit, QHeaderView, QTableView, QDialog, QIcon, QLabel, QMenu, QAction, QMainWindow, QTabWidget, QCheckBox, QPalette, QVBoxLayout, QPushButton, QWidget, QPixmap, QSizePolicy, QPainter, QPen, QHBoxLayout, QApplication
from osmparser.osmparserdata import Constants, OSMParserData, OSMRoutingPoint, OSMRoute
from osmparser.osmrouting import OSMRouting
from osmstyle import OSMStyle

from config import Config
from osmparser.osmutils import OSMUtils
from gpsutils import GPSMonitorUpateWorker
from gps import gps, misc
from osmdialogs import *
from mapnik.mapnikwrapper import MapnikWrapper
from mapnik.mapnikwrappercpp import MapnikWrapperCPP
from tracklog import TrackLog
from datetime import datetime

TILESIZE=256
minWidth=640
minHeight=480
MIN_ZOOM=5
MAX_ZOOM=18
MAP_SCROLL_STEP=10
M_LN2=0.69314718055994530942    #log_e 2
IMAGE_WIDTH=64
IMAGE_HEIGHT=64
IMAGE_WIDTH_MEDIUM=48
IMAGE_HEIGHT_MEDIUM=48
IMAGE_WIDTH_SMALL=32
IMAGE_HEIGHT_SMALL=32
MAX_TILE_CACHE=1000
TILE_CLEANUP_SIZE=50
WITH_CROSSING_DEBUG=True
ROTATE_X_AXIS=60

DEFAULT_SEARCH_MARGIN=0.0003
# length of tunnel where we expect gps signal failure
MINIMAL_TUNNEL_LENGHTH=50
GPS_SIGNAL_MINIMAL_DIFF=0.5
SKY_WIDTH=100

defaultTileHome=os.path.join("Maps", "osm", "tiles")
defaultTileServer="tile.openstreetmap.org"

idleState="idle"
runState="run"
stoppedState="stopped"

osmParserData = OSMParserData()
trackLog=TrackLog(False)
osmRouting=OSMRouting(osmParserData)
    
class OSMRoutingPointAction(QAction):
    def __init__(self, text, routingPoint, parent):
        QAction.__init__(self, text, parent)
        self.routingPoint=routingPoint
        
    def getRoutingPoint(self):
        return self.routingPoint
    
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
        self.lastBBox=None
        self.currentZoom=None
        self.lastZoom=None
        self.lastBBox=None
        self.lastZoom=None
        self.tileDir=tileDir
        self.mapnikWrapper=MapnikWrapper(tileDir, mapFile)
        self.mapnikWrapperCPP=MapnikWrapperCPP(mapFile)
        self.connect(self.mapnikWrapper, SIGNAL("updateMap()"), self.updateMap)
        self.workQueue=deque()
        self.tileQueue=deque()
        self.updateMapTrigger=0;
        
    def getTileFullPath(self, zoom, x, y):
        if not os.path.exists(os.path.join(self.tileDir, str(zoom))):
            os.mkdir(os.path.join(self.tileDir, str(zoom)))

        if not os.path.exists(os.path.join(self.tileDir, str(zoom), str(x))):
            os.mkdir(os.path.join(self.tileDir, str(zoom), str(x)))
            
        tilePath=os.path.join(str(zoom), str(x), str(y)+".png")
        fileName=os.path.join(self.tileDir, tilePath)
        return fileName
    
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

    def addTile(self, zoom, x, y):
        if not (zoom, x, y) in self.tileQueue:
#            print("call mapnik for %d %d %d"%(zoom, x, y))
            self.tileQueue.append((zoom, x, y))
            
            if not self.isRunning():
                self.updateMapTrigger=0
                self.setup()
            
#    def addBboxAndZoom(self, bbox, zoom):
#        if not (bbox, zoom) in self.workQueue:
#            self.workQueue.append((bbox, zoom))
#            
#            if not self.isRunning():
#                self.setup()
        
    def run(self):
        self.updateMapnikThreadState(runState)
        while not self.exiting and True:
            while len(self.tileQueue)!=0:
                (zoom, x, y)=self.tileQueue[0]
#                start=time.time()
                self.mapnikWrapper.render_tiles3(x, y, zoom)
#                self.mapnikWrapperCPP.render_tile(self.getTileFullPath(zoom, x, y), x, y, zoom)
#                print("%f"%(time.time()-start))
                self.tileQueue.popleft()
                
#                if self.updateMapTrigger==5:
#                    self.updateMap()
#                    self.updateMapTrigger=0
#                else:
#                    self.updateMapTrigger=self.updateMapTrigger+1
                         
            self.updateStatusLabel("OSM mapnik thread idle")
            self.updateMapnikThreadState(idleState)

#            print("longsleep")
            self.msleep(500) 
            if len(self.tileQueue)==0:
                self.exiting=True
                continue

#            if len(self.workQueue)!=0:
#                self.currentBBox, self.currentZoom=self.workQueue[0]
#                
##                print("mapnik renders: %s %d"%(self.currentBBox, self.currentZoom))
##                start=time.time()
#                self.mapnikWrapper.render_tiles2(self.currentBBox, self.currentZoom)
##                print("%f"%(time.time()-start))
#                self.lastZoom=self.currentZoom
#                self.lastBBox=self.currentBBox
#                self.currentBBox=None
#                self.currentZoom=None
#                self.workQueue.popleft()
#                if len(self.workQueue)!=0:
#                    continue
#                
#            self.updateStatusLabel("OSM mapnik thread idle")
#            self.updateMapnikThreadState(idleState)
#
#            self.msleep(1000) 
#            if len(self.workQueue)==0:
#                self.exiting=True
                
#        self.updateMap();
        self.updateStatusLabel("OSM mapnik thread stopped")
        self.updateMapnikThreadState(stoppedState)

class OSMGPSLocationWorker(QThread):
    def __init__(self, parent, tunnelThread): 
        QThread.__init__(self, parent)
        self.exiting = False
        self.currentGPSDataIndex=0
        self.gpsDataLines=None
        self.tunnelThread=tunnelThread
        self.lastGpsData=None
        if self.tunnelThread==True:
            self.timeout=500
        else:
            self.timeout=500
        
    def isTunnelThread(self):
        return self.tunnelThread
    
    def setWidget(self, osmWidget):
        self.osmWidget=osmWidget
        
    def setup(self, gpsDataLines):
        self.exiting = False
        self.gpsDataLines=gpsDataLines
        self.currentGPSDataIndex=0
        self.lastGpsData=None
        self.start()
 
    def stop(self):
        self.exiting = True
        self.wait()
        self.currentGPSDataIndex=0
        self.gpsDataLines=None
        self.lastGpsData=None
 
    def continueReplay(self):
        if self.gpsDataLines!=None:
            self.exiting = False
            self.start()

    def pauseReplay(self):
        self.exiting = True
        self.wait()

    def updateGPSDataDisplay(self, gpsData):
        if self.isTunnelThread():
            self.emit(SIGNAL("updateGPSDataDisplay2(PyQt_PyObject)"), gpsData)
        else:
            self.emit(SIGNAL("updateGPSDataDisplay1(PyQt_PyObject)"), gpsData)
        
    def run(self):
        for gpsData in self.gpsDataLines[self.currentGPSDataIndex:]:
            if self.exiting==True:
                break
            
#            if self.lastGpsData!=None:
#                if self.lastGpsData==gpsData:
#                    continue
#                
#            self.lastGpsData=gpsData
            
            self.updateGPSDataDisplay(gpsData)
            self.msleep(self.timeout)
            self.currentGPSDataIndex=self.currentGPSDataIndex+1

class GPSData():
    def __init__(self, time=None, lat=None, lon=None, track=None, speed=None, altitude=None):
        self.time=time
        self.lat=lat
        self.lon=lon
        self.track=track
        self.speed=speed
        self.altitude=altitude
    
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
            self.route.calcRoute(osmParserData)
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
        self.map_x=0
        self.map_y=0
        self.map_zoom=9
        self.min_zoom=MIN_ZOOM
        self.max_zoom=MAX_ZOOM
        self.center_rlat = 0.0
        self.center_rlon=0.0
        self.gps_rlat=0.0
        self.gps_rlon=0.0
        
        self.lastHeadingLat=0.0
        self.lastHeadingLon=0.0
        
        self.osmutils=OSMUtils()
        self.tileCache=OrderedDict()
        self.withMapnik=False
        self.withDownload=False
        self.autocenterGPS=False
        self.forceDownload=False
        
        self.osmControlImage=QPixmap(os.path.join(env.getImageRoot(), "osm-control.png"))
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
        self.routeCalculationThread=None
                        
        self.currentRoute=None
        self.routeList=list()
        self.wayInfo=None
        self.currentEdgeIndexList=None
        self.currentCoords=None
        self.distanceToEnd=0
        self.distanceToCrossing=0
        self.routeInfo=None, None, None, None
        self.nextEdgeOnRoute=None
        self.wayPOIList=None
        self.speedInfo=None
        
        self.currentEdgeList=None
        self.currentTrackList=None
        self.currentStartPoint=None
        self.currentTargetPoint=None
        self.currentRoutePart=0
        
        self.lastCenterX=None
        self.lastCenterY=None
        self.withMapRotation=True
                
        self.speed=0
        self.track=None
        self.stop=True
        self.isInTunnel=False
        self.altitude=0
        self.currentDisplayBBox=None
        self.show3D=True
        self.showBackgroundTiles=True
        self.refRing=None
        
        self.setAttribute( Qt.WA_OpaquePaintEvent, True )
        self.setAttribute( Qt.WA_NoSystemBackground, True )
        
        self.lastWayIdSet=None
        self.wayPolygonCache=dict()
        self.currentRoutePolygon=None
        self.areaPolygonCache=dict()
        self.lastOsmIdSet=None
        self.adminAreaPolygonCache=dict()
        self.lastAdminAreaIdSet=None       
        
        self.style=OSMStyle()
        self.mapPoint=None
    
    def getRouteList(self):
        return self.routeList
    
    def setRouteList(self, routeList):
        self.routeList=routeList
        
    def getTileHomeFullPath(self):
        if os.path.isabs(self.getTileHomeBase()):
            return self.getTileHomeBase()
        else:
            return os.path.join(env.getTileRoot(), self.getTileHomeBase())
    
    def getTileFullPath(self, zoom, x, y):
        home=self.getTileHomeFullPath()
        tilePath=os.path.join(str(zoom), str(x), str(y)+".png")
        fileName=os.path.join(home, tilePath)
        return fileName

    def getTileHomeBase(self):
        if self.withMapnik==True:
            return self.getTileHome()+"-shape"
        return self.getTileHome()
    
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
        
    def checkTileDirForZoom(self):
        tileDirForZoom=os.path.join(self.getTileHomeFullPath(), "%s"%self.map_zoom)
        if not os.path.isdir(tileDirForZoom):
            os.mkdir(tileDirForZoom)
        
    def osm_map_set_zoom (self, zoom):
        self.map_zoom = self.CLAMP(zoom, self.min_zoom, self.max_zoom)
        self.clearPolygonCache()
        self.checkTileDirForZoom()
        
        self.osm_map_handle_resize()
        
    def osm_map_handle_resize (self):
        (self.center_y, self.center_x)=self.getPixelPosForLocationRad(self.center_rlat, self.center_rlon, False)
        self.center_coord_update()
        
    def CLAMP(self, x, low, high):
        if x>high:
            return high
        elif x<low:
            return low
        return x

    def getYOffsetForRotationMap(self):
        return self.height()/3
    
    def calcMapZeroPos(self):
        map_x=int(self.center_x-self.width()/2)
        if self.withMapRotation==True:
            map_y=int(self.center_y-self.height()/2)-self.getYOffsetForRotationMap()
        else:
            map_y=int(self.center_y-self.height()/2)
        return (map_x, map_y)
    
    def getMapZeroPos(self):
        return self.map_x, self.map_y
    
    def printTilesGeometry(self):
        print("%d %d %d %f %f %s %f %f"%(self.center_x, self.center_y, self.map_zoom, self.osmutils.rad2deg(self.center_rlon), self.osmutils.rad2deg(self.center_rlat), self.getMapZeroPos(), self.osmutils.rad2deg(self.gps_rlon), self.osmutils.rad2deg(self.gps_rlat)))
    
    def showTiles (self):     
        width=self.width()
        height=self.width()
        map_x, map_y=self.getMapZeroPos()
                    
        offset_x = - map_x % TILESIZE;
        if offset_x==0:
            offset_x= - TILESIZE
            
        offset_y = - map_y % TILESIZE;
        if offset_y==0:
            offset_y= - TILESIZE

#        print("%d %d %d %d"%(map_x, map_y, offset_x, offset_y))
        
        if offset_x >= 0:
            offset_x -= TILESIZE*4
        if offset_y >= 0:
            offset_y -= TILESIZE*4

#        print("%d %d"%(offset_x, offset_y))

        tiles_nx = int((width  - offset_x) / TILESIZE + 1)+2
        tiles_ny = int((height - offset_y) / TILESIZE + 1)+2

        tile_x0 =  int(math.floor((map_x-TILESIZE) / TILESIZE))-2
        tile_y0 =  int(math.floor((map_y-TILESIZE) / TILESIZE))-2

        i=tile_x0
        j=tile_y0
        offset_y0=offset_y
            
#        print("%d %d %d %d"%(tile_x0, tile_y0, tiles_nx, tiles_ny))
        while i<(tile_x0+tiles_nx):
            while j<(tile_y0+tiles_ny):
                if j<0 or i<0 or i>=math.exp(self.map_zoom * M_LN2) or j>=math.exp(self.map_zoom * M_LN2):
                    pixbuf=self.getEmptyTile()
                else:
                    pixbuf=self.getTile(self.map_zoom, i,j)
                
#                print("%d %d"%(i, j))
                self.drawPixmap(offset_x, offset_y, TILESIZE, TILESIZE, pixbuf)                
                    
                offset_y += TILESIZE
                j=j+1
            offset_x += TILESIZE
            offset_y = offset_y0
            i=i+1
            j=tile_y0
        
    def getTileFromFile(self, fileName):
#        print(fileName)
        pixbuf = QPixmap(fileName)
        return pixbuf
    
    def getTileForZoomFromFile(self, zoom, x, y):
        fileName=self.getTileFullPath(zoom, x, y)
        if os.path.exists(fileName):
            pixbuf = QPixmap(fileName)
            return pixbuf

        return None

    def getCachedTile(self, fileName):
        if fileName in self.tileCache:
            return self.tileCache[fileName]
        return None
    
    def addTileToCache(self, pixbuf, fileName):
        # limit size of tile cache
        if len(self.tileCache.keys())>MAX_TILE_CACHE:
            print("cleanup image cache %d"%(len(self.tileCache.keys())))
            i=0
            for key in self.tileCache.keys():
                del self.tileCache[key]
                i=i+1
                if i==TILE_CLEANUP_SIZE:
                    break
            print("cleanup image cache done %d"%(len(self.tileCache.keys())))

        self.tileCache[fileName]=pixbuf
        
    def drawPixmap(self, x, y, width, height, pixbuf):
        self.painter.drawPixmap(x, y, width, height, pixbuf)
    
    def getEmptyTile(self):
        emptyPixmap=QPixmap(TILESIZE, TILESIZE)
        emptyPixmap.fill(self.palette().color(QPalette.Normal, QPalette.Background))
        return emptyPixmap

    def findUpscaledTile (self, zoom, x, y):
        while zoom > 0:
            zoom = zoom - 1
            next_x = int(x / 2)
            next_y = int(y / 2)
#            print("search for bigger map for zoom "+str(zoom))

            pixbuf=self.getTileForZoomFromFile(zoom, next_x, next_y)
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
            
    def getTile(self, zoom, x, y):
        fileName=self.getTileFullPath(zoom, x, y)
        pixbuf=self.getCachedTile(fileName)
        if pixbuf!=None:
            return pixbuf
        
        if os.path.exists(fileName) and self.forceDownload==False:
            pixbuf=self.getTileFromFile(fileName)
            self.addTileToCache(pixbuf, fileName)
            return pixbuf
        else:
            if self.withMapnik==True:
#                print(fileName)
#                print("callMapnikForTile from getTile")
#                self.callMapnikForTile()
                self.callMapnikForTile2(zoom, x, y)

                return self.getTilePlaceholder(zoom, x, y)
            elif self.withDownload==True:
                self.osmWidget.downloadThread.addTile("/"+str(zoom)+"/"+str(x)+"/"+str(y)+".png", fileName, self.forceDownload, self.getTileServer())
                return self.getTilePlaceholder(zoom, x, y)     
                    
            return self.getTilePlaceholder(zoom, x, y)
    
    def getTilePlaceholder(self, zoom, x, y):
        # try upscale lower zoom version
        pixbuf=self.getUpscaledTile(zoom, x, y)
        if pixbuf!=None:
            return pixbuf
        else:
            return self.getEmptyTile()
        
    def getGPSTransform(self, x, y):
        transform=QTransform()
        
        transform.translate(x, y)      
        
        if self.show3D==True:
            transform.rotate(ROTATE_X_AXIS, Qt.XAxis)    
            transform.scale(1.2, 1.2)    

        if self.withMapRotation==False:
            transform.rotate(self.track)
        
        transform.translate(-(x), -(y))

        return transform
    
    def displayGPSPosition(self):
        if self.gps_rlon==0.0 and self.gps_rlat==0.0:
            return
         
        imageWidth=IMAGE_WIDTH
        imageHeight=IMAGE_HEIGHT
        
        y,x=self.getTransformedPixelPosForLocationRad(self.gps_rlat, self.gps_rlon)
        
        xPos=int(x-imageWidth/2)
        yPos=int(y-imageHeight/2)
        
        transform=self.getGPSTransform(x, y)
        self.painter.setTransform(transform)
        
        if self.track!=None:
            self.painter.drawPixmap(xPos, yPos, imageWidth, imageHeight, self.style.getStylePixmap("gpsPointImage"))
        else:
            self.painter.drawPixmap(xPos, yPos, imageWidth, imageHeight, self.style.getStylePixmap("gpsPointImageStop"))
                
        self.painter.resetTransform()
 
    def displayMapPosition(self, mapPoint):
        imageWidth=IMAGE_WIDTH
        imageHeight=IMAGE_HEIGHT
        
        y,x=self.getPixelPosForLocationDeg(mapPoint.getPos()[0], mapPoint.getPos()[1], True)
        
        xPos=int(x-imageWidth/2)
        yPos=int(y-imageHeight/2)
        
        self.painter.drawPixmap(xPos, yPos, imageWidth, imageHeight, self.style.getStylePixmap("mapPointPixmap"))
         
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
        self.stepInDirection(dx, dy)
    
    # for untransformed coords
    def isPointVisible(self, x, y):
        point=QPoint(x, y)
        point0=self.transformHeading.map(point)        
        rect=QRect(0, 0, self.width(), self.height())
        return rect.contains(point0)

    # for already transformed coords
    def isPointVisibleTransformed(self, x, y):
        point=QPoint(x, y)
        rect=QRect(0, 0, self.width(), self.height())
        return rect.contains(point)    
    
    # bbox in deg (left, top, right, bottom)
    # only use if transform active
    def displayBBox(self, bbox):
        y,x=self.getPixelPosForLocationDeg(bbox[1], bbox[0], True)
        y1,x1=self.getPixelPosForLocationDeg(bbox[3], bbox[2], True)
        
        point0=QPointF(x, y)        
        point1=QPointF(x1, y1)        

        rect=QRectF(point0, point1)
        
        self.painter.setPen(QPen(Qt.red))
        self.painter.drawRect(rect)
        
    def displayTrack(self, trackList):
        polygon=QPolygon()
        
        for gpsData in trackList:
            lat=gpsData.getLat()
            lon=gpsData.getLon()
            (y, x)=self.getPixelPosForLocationDeg(lat, lon, True)
            point=QPoint(x, y);
            polygon.append( point )
               
        pen=self.style.getStylePen("trackPen")
        pen.setWidth(self.style.getStreetPenWidthForZoom(self.map_zoom))
        self.painter.setPen(pen)
        self.painter.drawPolyline(polygon)

    # only use if transform is active
    def displayRoutingEdges(self, edgeList, expectedNextEdge, approachingRef):
#        print(edgeList)
        pen=QPen()
        pen.setWidth(3)
        if len(edgeList)!=0:
            for edgeId in edgeList:
                edgeId, _, _, _, _, _, _, _, _, _, coords=osmParserData.getEdgeEntryForEdgeIdWithCoords(edgeId)
                if expectedNextEdge!=None and edgeId==expectedNextEdge:
                    pen.setColor(Qt.green)
                else:
                    pen.setColor(Qt.red)
    
                self.displayCoords(coords, pen)
        
        elif expectedNextEdge!=None:
            edgeId, _, _, _, _, _, _, _, _, _, coords=osmParserData.getEdgeEntryForEdgeIdWithCoords(expectedNextEdge)
            pen.setColor(Qt.green)
            self.displayCoords(coords, pen)
        
        if approachingRef!=None:
            lat, lon=osmParserData.getCoordsWithRef(approachingRef)
            y,x=self.getPixelPosForLocationDeg(lat, lon, True)
            if self.isPointVisible(x, y):
                pen.setColor(Qt.red)
                pen.setWidth(self.style.getPenWithForPoints(self.map_zoom))  
                pen.setCapStyle(Qt.RoundCap)
                self.painter.setPen(pen)
                self.painter.drawPoint(x, y)

    def getVisibleBBoxDeg(self):
        invertedTransform=self.transformHeading.inverted()
        map_x, map_y=self.getMapZeroPos()
        
        skyMargin=0
        if self.show3D==True:
            skyMargin=SKY_WIDTH
            
        point=QPointF(0, 0+skyMargin)            
        point0=invertedTransform[0].map(point)   
        lat1 = self.osmutils.rad2deg(self.osmutils.pixel2lat(self.map_zoom, map_y + point0.y()))
        lon1 = self.osmutils.rad2deg(self.osmutils.pixel2lon(self.map_zoom, map_x + point0.x()))

        point=QPointF(self.width(), 0+skyMargin)     
        point0=invertedTransform[0].map(point)        
        lat2 = self.osmutils.rad2deg(self.osmutils.pixel2lat(self.map_zoom, map_y + point0.y()))
        lon2 = self.osmutils.rad2deg(self.osmutils.pixel2lon(self.map_zoom, map_x + point0.x()))
            
        point=QPointF(0, self.height())             
        point0=invertedTransform[0].map(point)        
        lat3 = self.osmutils.rad2deg(self.osmutils.pixel2lat(self.map_zoom, map_y + point0.y()))
        lon3 = self.osmutils.rad2deg(self.osmutils.pixel2lon(self.map_zoom, map_x + point0.x()))

        point=QPointF(self.width(), self.height())        
        point0=invertedTransform[0].map(point)        
        lat4 = self.osmutils.rad2deg(self.osmutils.pixel2lat(self.map_zoom, map_y + point0.y()))
        lon4 = self.osmutils.rad2deg(self.osmutils.pixel2lon(self.map_zoom, map_x + point0.x()))
            
        lonList=[lon1, lon2, lon3, lon4]
        latList=[lat1, lat2, lat3, lat4]
        
        bboxLon1=min(lonList)
        bboxLat1=min(latList)
        bboxLon2=max(lonList)
        bboxLat2=max(latList)
                    
        return [bboxLon1, bboxLat1, bboxLon2, bboxLat2]
    
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
    
    def getTransform(self, withMapRotate, rotateAngle):
        transform=QTransform()
        
        map_x, map_y=self.getMapZeroPos()
        transform.translate( self.center_x-map_x, self.center_y-map_y )
        
        if self.show3D==True:
            transform.rotate(ROTATE_X_AXIS, Qt.XAxis)   
            transform.scale(1.2, 1.2)    
        
        if withMapRotate==True and rotateAngle!=None:
            transform.rotate(rotateAngle)
        
        transform.translate( -(self.center_x-map_x), -(self.center_y-map_y) )

        return transform
    
    def displayTestPoints(self):
        pen=QPen(QColor(255, 0, 0))
        pen.setWidth(20)
        self.painter.setPen(pen)
        self.painter.drawPoint(QPointF(self.width()/2, self.height()/2))
        
        map_x, map_y=self.getMapZeroPos()
        pen=QPen(QColor(0, 255, 0))
        pen.setWidth(15)
        self.painter.setPen(pen)
        self.painter.drawPoint(QPointF(self.center_x-map_x, self.center_y-map_y))
        
        (y, x)=self.getPixelPosForLocationRad(self.center_rlat, self.center_rlon, True)
        pen=QPen(QColor(0, 0, 255))
        pen.setWidth(10)
        self.painter.setPen(pen)
        self.painter.drawPoint(QPointF(x, y))
        
        pen=QPen(QColor(255, 0, 0))
        pen.setWidth(20)
        self.painter.setPen(pen)
        
        map_x, map_y=self.getMapZeroPos()
        point=QPointF(self.width()/2, self.height()/2)   
        invertedTransform=self.transformHeading.inverted()
        point0=invertedTransform[0].map(point)
        self.painter.drawPoint(point0)
        
    def paintEvent(self, event):
        self.painter=QPainter(self)
        self.painter.setClipRect(QRectF(0, 0, self.width(), self.height()))
        font=self.font()
        font.setPointSize(16) 
        self.painter.setFont(font)
        self.painter.setRenderHint(QPainter.Antialiasing)
        self.painter.setRenderHint(QPainter.SmoothPixmapTransform)
                
        if self.showBackgroundTiles==False:
            self.painter.fillRect(0, 0, self.width(), self.height(), self.style.getStyleColor("widgetBackgroundColor"))

        rotateAngle=None
        if self.track!=None:
            rotateAngle=360-self.track
            
        self.transformHeading=self.getTransform(self.withMapRotation, rotateAngle)
            
        self.painter.setTransform(self.transformHeading)

#        print(self.map_zoom)

        bbox=self.getVisibleBBoxDeg()        

#        self.displayVisibleAdminBoundaries(bbox)

        if self.map_zoom>=15:
            if self.showBackgroundTiles==True:
                self.showTiles()
            
            self.displayVisiblePolygons(bbox)
            self.displayVisibleWays(bbox)
        else:
            self.showTiles()
                    
        if self.currentRoute!=None and not self.currentRoute.isRouteFinished() and not self.routeCalculationThread.isRunning():
            self.displayRoute(self.currentRoute)
            if self.currentEdgeIndexList!=None:
                self.displayEdgeOfRoute(self.currentTrackList, self.currentEdgeIndexList)
        
        elif self.currentCoords!=None:
            self.style.getStylePen("edgePen").setWidth(self.style.getStreetPenWidthForZoom(self.map_zoom))
            self.displayCoords(self.currentCoords, self.style.getStylePen("edgePen"))
            
#        self.showRoutingPoints()            
                    
        if WITH_CROSSING_DEBUG==True:
            if len(osmRouting.getCurrentSearchEdgeList())!=0 or osmRouting.getExpectedNextEdge()!=None or osmRouting.getApproachingRef()!=None:
                self.displayRoutingEdges(osmRouting.getCurrentSearchEdgeList(), osmRouting.getExpectedNextEdge(), osmRouting.getApproachingRef())
    
            if osmParserData.getCurrentSearchBBox()!=None:
                self.displayBBox(osmParserData.getCurrentSearchBBox())

        if self.refRing!=None:   
            pen=self.style.getStylePen("trackPen")
            pen.setWidth(self.style.getStreetPenWidthForZoom(self.map_zoom))   
            self.displayRefs(self.refRing, pen)

#        if self.osmWidget.trackLogLines!=None:
#            self.displayTrack(self.osmWidget.trackLogLines)
                    
#        self.displayTestPoints()
        
        if self.mapPoint!=None:
            self.displayMapPosition(self.mapPoint)
            
        self.painter.resetTransform()
                        
        if self.show3D==True:
            skyRect=QRectF(0, 0, self.width(), SKY_WIDTH)
            gradient=QLinearGradient(skyRect.topLeft(), skyRect.bottomLeft())
            gradient.setColorAt(1, self.style.getStyleColor("widgetBackgroundColor"))
            gradient.setColorAt(0, Qt.blue)
            self.painter.fillRect(skyRect, gradient)
            
        if self.map_zoom>=16:
            self.displayVisibleNodes(bbox)
            
#        if self.gps_rlat!=0.0 and self.gps_rlon!=0.0:
#            osmParserData.getNearestNodeOfType(self.osmutils.rad2deg(self.gps_rlat), self.osmutils.rad2deg(self.gps_rlon), 0.1, Constants.POI_TYPE_GAS_STATION)
#        else:
#            osmParserData.getNearestNodeOfType(self.osmutils.rad2deg(self.center_rlat), self.osmutils.rad2deg(self.center_rlon), 0.1, Constants.POI_TYPE_GAS_STATION)
        
        self.showRoutingPoints2()
        self.displayGPSPosition()

        self.showEnforcementInfo()
        self.showControlOverlay()
        self.showTextInfoBackground()
        
        if self.currentRoute!=None and self.currentTrackList!=None and not self.currentRoute.isRouteFinished():
            self.showRouteInfo()
            
        self.showTextInfo()
        self.showSpeedInfo()
        self.showTunnelInfo()
        
        self.painter.end()
  
    def getStreetTypeListForOneway(self):
        return Constants.ONEWAY_OVERLAY_STREET_SET
        
    def getStreetTypeListForZoom(self):
        if self.map_zoom in range(16, 19):
            # all
            return []
        elif self.map_zoom in range(14, 16):
            return [Constants.STREET_TYPE_MOTORWAY,
                Constants.STREET_TYPE_MOTORWAY_LINK,
                Constants.STREET_TYPE_TRUNK,
                Constants.STREET_TYPE_TRUNK_LINK,
                Constants.STREET_TYPE_PRIMARY,
                Constants.STREET_TYPE_PRIMARY_LINK,
                Constants.STREET_TYPE_SECONDARY,
                Constants.STREET_TYPE_SECONDARY_LINK,
                Constants.STREET_TYPE_TERTIARY,
                Constants.STREET_TYPE_TERTIARY_LINK,
                Constants.STREET_TYPE_RESIDENTIAL]
        if self.map_zoom in range(12, 14):
            return [Constants.STREET_TYPE_MOTORWAY,
                Constants.STREET_TYPE_MOTORWAY_LINK,
                Constants.STREET_TYPE_TRUNK,
                Constants.STREET_TYPE_TRUNK_LINK,
                Constants.STREET_TYPE_PRIMARY,
                Constants.STREET_TYPE_PRIMARY_LINK,
                Constants.STREET_TYPE_SECONDARY,
                Constants.STREET_TYPE_SECONDARY_LINK,
                Constants.STREET_TYPE_TERTIARY,
                Constants.STREET_TYPE_TERTIARY_LINK]
        return None
    
    def getStreetProperties(self, streetTypeId):
        color=self.style.getStyleColor(streetTypeId)
        width=self.style.getStreetWidth(streetTypeId, self.map_zoom)
        return width, color
    
    # sort based on street type id
    def streetTypeIdSort(self, item):
        return item[1]
                   
    def clearPolygonCache(self):
        self.wayPolygonCache=dict()
        self.currentRoutePolygon=None
        self.areaPolygonCache=dict()
        self.adminAreaPolygonCache=dict()
        
    def displayVisibleWays(self, bbox):
        streetTypeList=self.getStreetTypeListForZoom()
        if streetTypeList==None:
            return 
        
        start=time.time()
        resultList, wayIdSet=osmParserData.getWaysInBboxWithGeom(bbox, 0.0, streetTypeList)        
        
        if self.lastWayIdSet==None:
            self.lastWayIdSet=wayIdSet
        else:
            removedWays=self.lastWayIdSet-wayIdSet
            self.lastWayIdSet=wayIdSet
            
            for wayId in removedWays:
                if wayId in self.wayPolygonCache.keys():
                    del self.wayPolygonCache[wayId]
            
        bridgeWays=list()
        tunnelWays=list()
        otherWays=list()
        showBridges=self.map_zoom in range(16, 19)
        showTunnels=self.map_zoom in range(16, 19)
        showCasing=self.map_zoom in range(16, 19)
        showStreetOverlays=self.map_zoom in range(17, 19)
        
        for way in resultList:
            wayId, tags, _, streetInfo, _, _, _, _, _=way
            streetTypeId, oneway, roundabout, tunnel, bridge=osmParserData.decodeStreetInfo2(streetInfo)
            
            if showBridges==True and bridge==1:
                bridgeWays.append((way, streetTypeId))
                continue
            
            if showTunnels==True and tunnel==1:
                tunnelWays.append((way, streetTypeId))
                continue
            
            otherWays.append((way, streetTypeId))
                    
        # tunnel 
        for way, streetTypeId in tunnelWays:   
            wayId, tags, _, streetInfo, _, _, _, _, _=way
            pen=self.style.getRoadPen(streetTypeId, self.map_zoom, False, False, 1, 0, False, False)
            self.displayWayCoordsWithCache(way, pen)

        otherWays=sorted(otherWays, key=self.streetTypeIdSort)
        
        # casing
        if showCasing==True:
            for way, streetTypeId in otherWays:   
                wayId, tags, _, streetInfo, _, _, _, _, _=way
                pen=self.style.getRoadPen(streetTypeId, self.map_zoom, showCasing, False, True, False, False, False)
                self.displayWayCoordsWithCache(way, pen)

        # fill
        for way, streetTypeId in otherWays:   
            wayId, tags, _, streetInfo, _, _, _, _, _=way
            streetTypeId, oneway, roundabout, tunnel, bridge=osmParserData.decodeStreetInfo2(streetInfo)
            pen=self.style.getRoadPen(streetTypeId, self.map_zoom, False, False, False, False, False, False)
            self.displayWayCoordsWithCache(way, pen)
            
            if showStreetOverlays==True: 
                if osmParserData.isAccessRestricted(tags):
                    pen=self.style.getRoadPen(streetTypeId, self.map_zoom, False, False, False, False, True, False)
                    self.displayWayCoordsWithCache(way, pen)
            
                # TODO: mark oneway direction
                elif (oneway!=0 or roundabout==1) and streetTypeId in self.getStreetTypeListForOneway():
                    pen=self.style.getRoadPen(streetTypeId, self.map_zoom, False, True, False, False, False, False)
                    self.displayWayCoordsWithCache(way, pen)
                
                elif streetTypeId==Constants.STREET_TYPE_LIVING_STREET:
                    pen=self.style.getRoadPen(streetTypeId, self.map_zoom, False, False, False, False, False, True)
                    self.displayWayCoordsWithCache(way, pen)
                
        # bridges  
        for way, streetTypeId in bridgeWays:
            wayId, tags, _, streetInfo, _, _, _, _, _=way
            pen=self.style.getRoadPen(streetTypeId, self.map_zoom, False, False, False, True, False, False)
            self.displayWayCoordsWithCache(way, pen)

            pen=self.style.getRoadPen(streetTypeId, self.map_zoom, False, False, False, False, False, False)
            self.displayWayCoordsWithCache(way, pen)

        print("displayVisibleWays: %f"%(time.time()-start))

    def getDisplayNodeTypeList(self):
        return [Constants.POI_TYPE_ENFORCEMENT, 
#                Constants.POI_TYPE_BARRIER, 
                Constants.POI_TYPE_GAS_STATION]
#                Constants.POI_TYPE_PARKING]
    
    def getPixmapForNodeType(self, nodeType):
        return self.style.getPixmapForNodeType(nodeType)
    
    def displayVisibleNodes(self, bbox):
        start=time.time()
        resultList=osmParserData.getNodesInBBoxWithGeom(bbox, 0.0, self.getDisplayNodeTypeList())        

        nodeTyleListSet=set(self.getDisplayNodeTypeList())
        for node in resultList:
            _, lat, lon, tags, nodeTypeList=node
            (y, x)=self.getTransformedPixelPosForLocationDeg(lat, lon)
            if self.isPointVisibleTransformed(x, y):  
                for nodeType in nodeTypeList:  
                    if nodeType in nodeTyleListSet: 
#                        print("node: %s"%(tags))   
                        self.painter.drawPixmap(int(x-IMAGE_WIDTH_SMALL/2), int(y-IMAGE_HEIGHT_SMALL), IMAGE_WIDTH_SMALL, IMAGE_HEIGHT_SMALL, self.getPixmapForNodeType(nodeType))

        print("displayVisibleNodes: %f"%(time.time()-start))


    def getDisplayAreaTypeList(self):
        if self.map_zoom in range(17, 19):
            return [Constants.AREA_TYPE_LANDUSE, 
                    Constants.AREA_TYPE_NATURAL,
                    Constants.AREA_TYPE_BUILDING,
                    Constants.AREA_TYPE_HIGHWAY_AREA]
            
        elif self.map_zoom in range(15, 18):
            return [Constants.AREA_TYPE_LANDUSE, 
                    Constants.AREA_TYPE_NATURAL,
                    Constants.AREA_TYPE_HIGHWAY_AREA]
        else:
            return []
        
    def displayVisiblePolygons(self, bbox):
        start=time.time()     
        resultList, osmIdSet=osmParserData.getAreasInBboxWithGeom(self.getDisplayAreaTypeList(), bbox, 0.0)
        print("displayVisiblePolygons: %f"%(time.time()-start))
        
        if self.lastOsmIdSet==None:
            self.lastOsmIdSet=osmIdSet
        else:
            removedAreas=self.lastOsmIdSet-osmIdSet
            self.lastOsmIdSet=osmIdSet
            
            for osmId in removedAreas:
                if osmId in self.areaPolygonCache.keys():
                    del self.areaPolygonCache[osmId]
                    
        for area in resultList:
            osmId=area[0]
            areaType=area[1]
            tags=area[2]
            brush=Qt.NoBrush
            pen=Qt.NoPen
            if areaType==Constants.AREA_TYPE_NATURAL:
                if "waterway" in tags:         
#                    print("%d %s"%(osmId, tags))  
                    brush=self.style.getStyleBrush("water")
         
                    if tags["waterway"]!="riverbank":
                        pen=self.style.getStylePen("waterwayPen")
                        pen.setWidth(self.style.getWaterwayPenWidthForZoom(self.map_zoom, tags))                      
                    
                elif "natural" in tags:
                    if tags["natural"]=="water":
                        brush=self.style.getStyleBrush("water")
                    else:
                        brush=self.style.getStyleBrush("natural")
            
            elif areaType==Constants.AREA_TYPE_LANDUSE:
                brush=self.style.getStyleBrush("natural")
              
            elif areaType==Constants.AREA_TYPE_BUILDING:
                brush=self.style.getStyleBrush("building")

            elif areaType==Constants.AREA_TYPE_HIGHWAY_AREA:
                brush=self.style.getStyleBrush("highway")
                
            else:
                continue
               
            self.displayPolygonWithCache(self.areaPolygonCache, area, pen, brush)

        self.painter.setBrush(Qt.NoBrush)

    def getAdminLevelList(self):
        return Constants.ADMIN_LEVEL_SET
    
    def displayVisibleAdminBoundaries(self, bbox):
        start=time.time()     
        resultList, adminAreaIdSet=osmParserData.getAdminAreasInBboxWithGeom(bbox, 0.0, self.getAdminLevelList())
        print("displayVisibleAdminBoundaries: %f"%(time.time()-start))
        
        if self.lastAdminAreaIdSet==None:
            self.lastAdminAreaIdSet=adminAreaIdSet
        else:
            removedAreas=self.lastAdminAreaIdSet-adminAreaIdSet
            self.lastAdminAreaIdSet=adminAreaIdSet
            
            for areaId in removedAreas:
                if areaId in self.adminAreaPolygonCache.keys():
                    del self.adminAreaPolygonCache[areaId]

#        brush=Qt.NoBrush
#        pen=self.style.getStylePen("adminArea")

        for area in resultList:
            tags=area[2]
            adminLevel=area[3]
            print(tags)
#            print("%d %s"%(adminLevel, tags["name"]))
#            self.displayPolygonWithCache(self.adminAreaPolygonCache, area, pen, brush)
        
        self.painter.setBrush(Qt.NoBrush)

    def showTextInfoBackground(self):
        textBackground=QRect(0, self.height()-50, self.width(), 50)
        self.painter.fillRect(textBackground, self.style.getStyleColor("backgroundColor"))
        
        if self.currentRoute!=None and self.currentTrackList!=None and not self.currentRoute.isRouteFinished():
            routeInfoBackground=QRect(self.width()-80, self.height()-210, 80, 160)
            self.painter.fillRect(routeInfoBackground, self.style.getStyleColor("backgroundColor"))
            
    def showTextInfo(self):
        pen=self.style.getStylePen("textPen")
        self.painter.setPen(pen)
                    
        if self.wayInfo!=None:
            wayPos=QPoint(5, self.height()-15)
            self.painter.drawText(wayPos, self.wayInfo)
                    
    def showRouteInfo(self):
        pen=self.style.getStylePen("textPen")
        self.painter.setPen(pen)
        fm = self.painter.fontMetrics();

        if self.distanceToEnd!=0:
            distanceToEndPos=QPoint(self.width()-70, self.height()-180)
            
            if self.distanceToEnd>500:
                distanceToEndStr="%.1f km"%(self.distanceToEnd/1000)
            else:
                distanceToEndStr="%d m"%self.distanceToEnd
                
            self.painter.drawText(distanceToEndPos, "%s"%distanceToEndStr)

        if self.distanceToCrossing!=0:
            routeInfoPos=QPoint(self.width()-70, self.height()-60)
            if self.distanceToCrossing>500:
                crossingLengthStr="%.1f km"%(self.distanceToCrossing/1000)
            else:
                crossingLengthStr="%d m"%self.distanceToCrossing
            self.painter.drawText(routeInfoPos, "%s"%crossingLengthStr)

        if self.routeInfo[0]!=None:
            (direction, crossingInfo, _, _)=self.routeInfo
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
            
            routeInfoPos1=QPoint(self.width()-fm.width(crossingInfoStr)-10, self.height()-15)
            self.painter.drawText(routeInfoPos1, "%s"%(crossingInfoStr))
                            
            x=self.width()-72
            y=self.height()-150
            self.drawDirectionImage(direction, exitNumber, IMAGE_WIDTH, IMAGE_HEIGHT, x, y) 
     
     
    def showEnforcementInfo(self):   
        if self.wayPOIList!=None:  
#            showTrackDetails=self.map_zoom>13
#            if showTrackDetails==True:
#                for enforcement in self.wayPOIList:
#                    if enforcement["type"]=="enforcement":
#                        lat, lon=enforcement["coords"]
#                        (y, x)=self.getTransformedPixelPosForLocationDeg(lat, lon)
#    #                    print("%f %f %f %f"%(lat, lon, x, y))
#                        if self.isPointVisibleTransformed(x, y):           
#                            self.painter.drawPixmap(int(x-IMAGE_WIDTH_SMALL/2), int(y-IMAGE_HEIGHT_SMALL/2), IMAGE_WIDTH_SMALL, IMAGE_HEIGHT_SMALL, self.style.getStylePixmap("speedCameraImage"))

            enforcementBackground=QRect(0, self.height()-210, 80, 80)
            self.painter.fillRect(enforcementBackground, self.style.getStyleColor("warningBackgroundColor"))
            x=8
            y=self.height()-202
            self.painter.drawPixmap(x, y, IMAGE_WIDTH, IMAGE_HEIGHT, self.style.getStylePixmap("speedCameraImage"))

    def showSpeedInfo(self):   
        if self.speedInfo!=None and self.speedInfo!=0:
            x=8
            y=self.height()-122
            
            speedBackground=QRect(0, self.height()-130, 80, 80)
            # show if speed is larger then maxspeed + 10%
            if self.speed>self.speedInfo*1.1:
                self.painter.fillRect(speedBackground, self.style.getStyleColor("warningBackgroundColor"))
            else:
                self.painter.fillRect(speedBackground, self.style.getStyleColor("backgroundColor"))

            imagePath=os.path.join(env.getImageRoot(), "speedsigns", "%d.png"%(self.speedInfo))
            if os.path.exists(imagePath):
                speedPixmap=QPixmap(imagePath)
                self.painter.drawPixmap(x, y, IMAGE_WIDTH, IMAGE_HEIGHT, speedPixmap)
                
    def showTunnelInfo(self):
        if self.isInTunnel==True:
            x=self.width()-72
            y=8
            
            tunnelBackground=QRect(self.width()-80, 0, 80, 80)
            self.painter.fillRect(tunnelBackground, self.style.getStyleColor("backgroundColor"))
            
            self.painter.drawPixmap(x, y, IMAGE_WIDTH, IMAGE_HEIGHT, self.style.getStylePixmap("tunnelPixmap"))
            
#    def showRoutingPoints(self):
##        showTrackDetails=self.map_zoom>13
##        if showTrackDetails==False:
##            return 
#
#        if self.startPoint!=None:
#            (y, x)=self.getPixelPosForLocationDeg(self.startPoint.lat, self.startPoint.lon, True)
#            if self.isPointVisible(x, y):
#                self.painter.drawPixmap(int(x-IMAGE_WIDTH/2), int(y-IMAGE_HEIGHT/2), IMAGE_WIDTH, IMAGE_HEIGHT, self.style.getStylePixmap("startPointImage"))
#
#        if self.endPoint!=None:
#            (y, x)=self.getPixelPosForLocationDeg(self.endPoint.lat, self.endPoint.lon, True)
#            if self.isPointVisible(x, y):
#                self.painter.drawPixmap(int(x-IMAGE_WIDTH/2), int(y-IMAGE_HEIGHT/2), IMAGE_WIDTH, IMAGE_HEIGHT, self.style.getStylePixmap("endPointImage"))
#            
#        for point in self.wayPoints:
#            (y, x)=self.getPixelPosForLocationDeg(point.lat, point.lon, True)
#            if self.isPointVisible(x, y):
#                self.painter.drawPixmap(int(x-IMAGE_WIDTH/2), int(y-IMAGE_HEIGHT/2), IMAGE_WIDTH, IMAGE_HEIGHT, self.style.getStylePixmap("wayPointImage"))

    def showRoutingPoints2(self):
        if self.startPoint!=None:
            (y, x)=self.getTransformedPixelPosForLocationDeg(self.startPoint.lat, self.startPoint.lon)
            if self.isPointVisible(x, y):
                self.painter.drawPixmap(int(x-IMAGE_WIDTH_MEDIUM/2), int(y-IMAGE_HEIGHT_MEDIUM), IMAGE_WIDTH_MEDIUM, IMAGE_HEIGHT_MEDIUM, self.style.getStylePixmap("startPixmap"))

        if self.endPoint!=None:
            (y, x)=self.getTransformedPixelPosForLocationDeg(self.endPoint.lat, self.endPoint.lon)
            if self.isPointVisible(x, y):
                self.painter.drawPixmap(int(x-IMAGE_WIDTH_MEDIUM/2), int(y-IMAGE_HEIGHT_MEDIUM), IMAGE_WIDTH_MEDIUM, IMAGE_HEIGHT_MEDIUM, self.style.getStylePixmap("finishPixmap"))
            
        for point in self.wayPoints:
            (y, x)=self.getTransformedPixelPosForLocationDeg(point.lat, point.lon)
            if self.isPointVisible(x, y):
                self.painter.drawPixmap(int(x-IMAGE_WIDTH_MEDIUM/2), int(y-IMAGE_HEIGHT_MEDIUM), IMAGE_WIDTH_MEDIUM, IMAGE_HEIGHT_MEDIUM, self.style.getStylePixmap("flagPixmap"))
            
    
    def getPixelPosForLocationDeg(self, lat, lon, relativeToEdge):
        return self.getPixelPosForLocationRad(self.osmutils.deg2rad(lat), self.osmutils.deg2rad(lon), relativeToEdge)
     
    # call this with relativeToEdge==True ONLY inside of a transformed painter
    # e.g. in paintEvent
    def getPixelPosForLocationRad(self, lat, lon, relativeToEdge):
        x=self.osmutils.lon2pixel(self.map_zoom, lon)
        y=self.osmutils.lat2pixel(self.map_zoom, lat)

        if relativeToEdge:
            map_x, map_y=self.getMapZeroPos()
            x=x-map_x
            y=y-map_y
                    
        return (y, x)
    
    # call this outside of a transformed painter
    # if a specific point on the transformed map is needed
    def getTransformedPixelPosForLocationRad(self, lat, lon):
        x=self.osmutils.lon2pixel(self.map_zoom, lon)
        y=self.osmutils.lat2pixel(self.map_zoom, lat)
        map_x, map_y=self.getMapZeroPos()
        point=QPointF(x-map_x, y-map_y)

        point0=self.transformHeading.map(point)
        x=point0.x()
        y=point0.y()
        return (y, x)

    def getTransformedPixelPosForLocationDeg(self, lat, lon):
        return self.getTransformedPixelPosForLocationRad(self.osmutils.deg2rad(lat), self.osmutils.deg2rad(lon))
    
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
    
    def displayCoords(self, coords, pen):        
        polygon=QPolygon()
        
        map_x, map_y=self.getMapZeroPos()
        displayCoords=coords
        fullCoords=self.map_zoom>=16
        if fullCoords==False:
            if len(coords)>6:
                displayCoords=coords[1:-2:2]
                displayCoords[0]=coords[0]
                displayCoords[-1]=coords[-1]
            
        for point in displayCoords:
            lat, lon=point 
            (y, x)=self.getPixelPosForLocationDeg(lat, lon, False)
            point=QPoint(x, y);
            polygon.append( point )
            
        polygon.translate(-map_x, -map_y)
               
        self.painter.setPen(pen)
        self.painter.drawPolyline(polygon)

    def displayWayCoordsWithCache(self, way, pen):        
        polygon=None
        wayId=way[0]
        coordsStr=way[8]
        map_x, map_y=self.getMapZeroPos()
        
        if not wayId in self.wayPolygonCache.keys():
            polygon=QPolygon()
            coords=osmParserData.createCoordsFromLineString(coordsStr)

            displayCoords=coords
            fullCoords=self.map_zoom>=15
            if fullCoords==False:
                if len(coords)>6:
                    displayCoords=coords[1:-2:2]
                    displayCoords[0]=coords[0]
                    displayCoords[-1]=coords[-1]
                
            for point in displayCoords:
                lat, lon=point 
                (y, x)=self.getPixelPosForLocationDeg(lat, lon, False)
                point=QPoint(x, y);
                polygon.append( point )
            
            self.wayPolygonCache[wayId]=polygon
        
        else:
            polygon=self.wayPolygonCache[wayId]
            
        displayPolygon=polygon.translated(-map_x, -map_y)
               
        self.painter.setPen(pen)
        self.painter.drawPolyline(displayPolygon)  
              
    def displayPolygon(self, coords, pen):        
        polygon=QPolygon()
        
        displayCoords=coords
        fullCoords=self.map_zoom>=15
        if fullCoords==False:
            if len(coords)>6:
                displayCoords=coords[1:-2:2]
                displayCoords[0]=coords[0]
                displayCoords[-1]=coords[-1]
            
        for point in displayCoords:
            lat, lon=point 
            (y, x)=self.getPixelPosForLocationDeg(lat, lon, True)
            point=QPoint(x, y);
            polygon.append( point )
               
        self.painter.setPen(pen)
        self.painter.drawPolygon(polygon)    

    def displayPolygonWithCache(self, cacheDict, area, pen, brush):        
        polygon=None
        osmId=area[0]
        polyStr=area[4]
        map_x, map_y=self.getMapZeroPos()
        
        if not osmId in cacheDict.keys():
            polygon=QPolygon()
            coords=osmParserData.createCoordsFromMultiPolygon(polyStr)[0]
                        
            displayCoords=coords
            fullCoords=self.map_zoom>=15
            if fullCoords==False:
                if len(coords)>6:
                    displayCoords=coords[1:-2:2]
                    displayCoords[0]=coords[0]
                    displayCoords[-1]=coords[-1]
            
            for point in displayCoords:
                lat, lon=point 
                (y, x)=self.getPixelPosForLocationDeg(lat, lon, False)
                point=QPoint(x, y);
                polygon.append( point )
               
            cacheDict[osmId]=polygon
        
        else:
            polygon=cacheDict[osmId]

        displayPolygon=polygon.translated(-map_x, -map_y)
                
        self.painter.setBrush(brush)
        self.painter.setPen(pen)
            
        if displayPolygon.first()==displayPolygon.last():
            self.painter.drawPolygon(displayPolygon)  
        else:
            self.painter.drawPolyline(displayPolygon)  
        
    def displayRefs(self, refList, pen):        
        polygon=QPolygon()
        
        for ref in refList:
            lat, lon=osmParserData.getCoordsWithRef(ref)
            (y, x)=self.getPixelPosForLocationDeg(lat, lon, True)
            point=QPoint(x, y);
            polygon.append( point )
               
        self.painter.setPen(pen)
        self.painter.drawPolyline(polygon)
        
    def displayEdgeOfRoute(self, remainingTrackList, edgeIndexList):
        if remainingTrackList!=None:                        
            polygon=QPolygon()

            for index in edgeIndexList:
                if index<len(remainingTrackList):
                    item=remainingTrackList[index]
                    
                    for itemRef in item["refs"]:
                        lat, lon=itemRef["coords"]   
                        (y, x)=self.getPixelPosForLocationDeg(lat, lon, True)
                        point=QPoint(x, y);
                        polygon.append( point )

            pen=self.style.getStylePen("routeOverlayPen")
            pen.setWidth(self.style.getStreetPenWidthForZoom(self.map_zoom))
            self.painter.setPen(pen)
            self.painter.drawPolyline(polygon)
        
    def displayRoute(self, route):
        if route!=None:
            # before calculation is done
            trackList=route.getTrackList(self.currentRoutePart)
            if trackList==None:
                return
            
            showTrackDetails=self.map_zoom>13
            
            if self.currentRoutePolygon==None:
                polygon=QPolygon()
               
                for item in trackList:                
                    for itemRef in item["refs"]:
                        lat, lon=itemRef["coords"]
                            
                        (y, x)=self.getPixelPosForLocationDeg(lat, lon, False)
                        point=QPoint(x, y);
                        polygon.append( point )
        
                self.currentRoutePolygon=polygon
            
            map_x, map_y=self.getMapZeroPos()
            displayPolygon=self.currentRoutePolygon.translated(-map_x, -map_y)   
            
            pen=self.style.getStylePen("routePen")
            pen.setWidth(self.style.getStreetPenWidthForZoom(self.map_zoom))
            self.painter.setPen(pen)
            self.painter.drawPolyline(displayPolygon)
                    
            if showTrackDetails==True:                                    
                for item in trackList:
                    for itemRef in item["refs"]:
                        lat, lon=itemRef["coords"]
                            
                        crossing=False
                        
                        if "crossingType" in itemRef:
                            crossing=True
                            crossingType=itemRef["crossingType"]
                            
                        if crossing==True:
                            (y, x)=self.getPixelPosForLocationDeg(lat, lon, True)
                        
                            if self.isPointVisible(x, y):
                                pen=self.style.getPenForCrossingType(crossingType)
                                pen.setWidth(self.style.getPenWithForPoints(self.map_zoom))
                                
                                self.painter.setPen(pen)
                                self.painter.drawPoint(x, y)
                            
            
    def drawDirectionImage(self, direction, exitNumber, width, height, x, y):
        if direction==1:
            self.painter.drawPixmap(x, y, width, height, self.style.getStylePixmap("turnRightEasyImage"))
        elif direction==2:
            self.painter.drawPixmap(x, y, width, height, self.style.getStylePixmap("turnRightImage"))
        elif direction==3:
            self.painter.drawPixmap(x, y, width, height, self.style.getStylePixmap("turnRighHardImage"))
        elif direction==-1:
            self.painter.drawPixmap(x, y, width, height, self.style.getStylePixmap("turnLeftEasyImage"))
        elif direction==-2:
            self.painter.drawPixmap(x, y, width, height, self.style.getStylePixmap("turnLeftImage"))
        elif direction==-3:
            self.painter.drawPixmap(x, y, width, height, self.style.getStylePixmap("turnLeftHardImage"))
        elif direction==0:
            self.painter.drawPixmap(x, y, width, height, self.style.getStylePixmap("straightImage"))
        elif direction==39:
            # TODO: should be a motorway exit image
            self.painter.drawPixmap(x, y, width, height, self.style.getStylePixmap("turnRightEasyImage"))
        elif direction==42:
            # TODO: is a link enter always right?
            self.painter.drawPixmap(x, y, width, height, self.style.getStylePixmap("turnRightEasyImage"))
        elif direction==41 or direction==40:
            if exitNumber==1:
                self.painter.drawPixmap(x, y, width, height, self.style.getStylePixmap("roundabout1Image"))
            elif exitNumber==2:
                self.painter.drawPixmap(x, y, width, height, self.style.getStylePixmap("roundabout2Image"))
            elif exitNumber==3:
                self.painter.drawPixmap(x, y, width, height, self.style.getStylePixmap("roundabout3Image"))
            elif exitNumber==4:
                self.painter.drawPixmap(x, y, width, height, self.style.getStylePixmap("roundabout4Image"))
            else:  
                self.painter.drawPixmap(x, y, width, height, self.style.getStylePixmap("roundaboutImage"))
        elif direction==98:
            self.painter.drawPixmap(x, y, width, height, self.style.getStylePixmap("uturnImage"))
        elif direction==99:
            self.painter.drawPixmap(x, y, width, height, self.style.getStylePixmap("endPointImage"))
            
#    def minimumSizeHint(self):
#        return QSize(minWidth, minHeight)

#    def sizeHint(self):
#        return QSize(800, 300)

    def center_coord_update(self):
        self.center_rlon = self.osmutils.pixel2lon(self.map_zoom, self.center_x)
        self.center_rlat = self.osmutils.pixel2lat(self.map_zoom, self.center_y)
            
        self.map_x, self.map_y=self.calcMapZeroPos()
        
    def stepInDirection(self, step_x, step_y):
        map_x, map_y=self.getMapZeroPos()
        point=QPointF(self.center_x-map_x+step_x, self.center_y-map_y+step_y)   
        invertedTransform=self.transformHeading.inverted()
        point0=invertedTransform[0].map(point)
        self.center_y=map_y+point0.y()
        self.center_x=map_x+point0.x()
        self.center_coord_update()
        self.update()

    def stepUp(self, step):
        self.stepInDirection(0, -step)

    def stepDown(self, step):
        self.stepInDirection(0, step)
        
    def stepLeft(self, step):
        self.stepInDirection(-step, 0)

    def stepRight(self, step):
        self.stepInDirection(step, 0)
                
    def updateGPSLocation(self, gpsData, debug):
        lat=gpsData.getLat()
        lon=gpsData.getLon()
        self.speed=gpsData.getSpeed()
        track=gpsData.getTrack()
        self.altitude=gpsData.getAltitude()
        
#        print("%f-%f"%(lat,lon))
        
        if debug==True:
            self.track=track
#            self.heading=self.track

        if lat!=0.0 and lon!=0.0:
            if self.speed==0:
                self.stop=True
            else:
                self.stop=False
                # only set track when moving
                self.track=track
#                self.heading=self.track

            firstGPSData=False
            if self.gps_rlat==0.0 and self.gps_rlon==0.0:
                firstGPSData=True
                
            gps_rlat_new=self.osmutils.deg2rad(lat)
            gps_rlon_new=self.osmutils.deg2rad(lon)
            
            if gps_rlat_new!=self.gps_rlat or gps_rlon_new!=self.gps_rlon:  
#                print("gps update")
#                if self.stop==False:  
#                    self.distanceFromLastPos(lat, lon) 
                        
                self.gps_rlat=gps_rlat_new
                self.gps_rlon=gps_rlon_new
                
                if debug==False:
                    if self.stop==False:  
                        self.showTrackOnGPSPos(lat, lon, False)

                if self.wayInfo!=None:
                    self.gpsPoint=OSMRoutingPoint(self.wayInfo, OSMRoutingPoint.TYPE_GPS, (lat, lon))
                else:
                    self.gpsPoint=None  

                if self.autocenterGPS==True and (self.stop==False or firstGPSData==True):
                    self.osm_autocenter_map()
                else:
                    self.update()   
#            else:
#                if self.autocenterGPS==True and self.stop==False:
#                    self.osm_autocenter_map()
#                else:
#                    self.update()           
        else:
            self.gps_rlat=0.0
            self.gps_rlon=0.0
            self.gpsPoint=None
#            self.heading=None
            self.stop=True
            self.track=None
            self.update()
        
    def cleanImageCache(self):
        self.tileCache.clear()
                
    def getBBoxDifference(self, bbox1, bbox2):
        None
        
#    def callMapnikForTile(self):
#        bbox=self.getVisibleBBoxForMapnik()  
##        print("call mapnik with %s"%bbox)   
##        print(bbox)       
#        self.osmWidget.mapnikThread.addBboxAndZoom(bbox, self.map_zoom)

    def callMapnikForTile2(self, zoom, x, y):   
        self.osmWidget.mapnikThread.addTile(zoom, x, y)
        
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
        self.lastMouseMoveX=event.x()
        self.lastMouseMoveY=event.y()
        self.mousePos=(event.x(), event.y())
            
    def mouseMoveEvent(self, event):
        if self.mousePressed==True:
            self.moving=True
            
        if self.moving==True:
            dx=self.lastMouseMoveX-event.x()
            dy=self.lastMouseMoveY-event.y()
            self.osm_map_scroll(dx, dy)
            self.lastMouseMoveX=event.x()
            self.lastMouseMoveY=event.y()
                    
    def getRoutingPointForPos(self, mousePos):
        p=QPoint(mousePos[0], mousePos[1])

        if self.startPoint!=None:
            (y, x)=self.getTransformedPixelPosForLocationDeg(self.startPoint.lat, self.startPoint.lon)
            rect=QRect(int(x-IMAGE_WIDTH_MEDIUM/2), int(y-IMAGE_HEIGHT_MEDIUM), IMAGE_WIDTH_MEDIUM, IMAGE_HEIGHT_MEDIUM)
            if rect.contains(p, proper=False):
                return self.startPoint

        if self.endPoint!=None:
            (y, x)=self.getTransformedPixelPosForLocationDeg(self.endPoint.lat, self.endPoint.lon)
            rect=QRect(int(x-IMAGE_WIDTH_MEDIUM/2), int(y-IMAGE_HEIGHT_MEDIUM), IMAGE_WIDTH_MEDIUM, IMAGE_HEIGHT_MEDIUM)
            if rect.contains(p, proper=False):
                return self.endPoint

        for point in self.wayPoints:
            (y, x)=self.getTransformedPixelPosForLocationDeg(point.lat, point.lon)
            rect=QRect(int(x-IMAGE_WIDTH_MEDIUM/2), int(y-IMAGE_HEIGHT_MEDIUM), IMAGE_WIDTH_MEDIUM, IMAGE_HEIGHT_MEDIUM)
            if rect.contains(p, proper=False):
                return point

        return None
    
    def contextMenuEvent(self, event):
#        print("%d-%d"%(self.mousePos[0], self.mousePos[1]))
        menu = QMenu(self)
        forceDownloadAction = QAction("Force Download", self)
        forceDownloadAction.setEnabled(self.withDownload==True and self.withMapnik==False)
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
        gotoPosAction=QAction("Goto Position", self)
        showPosAction=QAction("Show Position", self)
        zoomToCompleteRoute=QAction("Zoom to Route", self)
        recalcRouteAction=QAction("Recalc Route from here", self)
        recalcRouteGPSAction=QAction("Recalc Route from GPS", self)
        
        routingPointSubMenu=QMenu(self)
        routingPointSubMenu.setTitle("Map Points")
        routingPointList=self.getCompleteRoutingPoints()
        if routingPointList!=None:
            for point in routingPointList:
                pointAction=OSMRoutingPointAction(point.getName(), point, self)
                routingPointSubMenu.addAction(pointAction)
            if self.mapPoint!=None:
                routingPointSubMenu.addSeparator()
                pointAction=OSMRoutingPointAction(self.mapPoint.getName(), self.mapPoint, self)
                routingPointSubMenu.addAction(pointAction)

        else:
            routingPointSubMenu.setDisabled(True)

        menu.addAction(forceDownloadAction)
        menu.addSeparator()
        menu.addAction(setStartPointAction)
        menu.addAction(setEndPointAction)
        menu.addAction(setWayPointAction)
        menu.addAction(addFavoriteAction)
        menu.addAction(gotoPosAction)
        menu.addAction(showPosAction)
        menu.addSeparator()
        menu.addAction(clearAllRoutingPointsAction)
        menu.addAction(clearRoutingPointAction)
        menu.addAction(editRoutingPointAction)
        menu.addAction(saveRouteAction)
        menu.addMenu(routingPointSubMenu)
        menu.addSeparator()
        menu.addAction(showRouteAction)
        menu.addAction(clearRouteAction)
        menu.addAction(recalcRouteAction)
        menu.addAction(recalcRouteGPSAction)
        menu.addSeparator()
        menu.addAction(zoomToCompleteRoute)

        addPointDisabled=False
        routeIncomplete=routingPointList==None
        setStartPointAction.setDisabled(addPointDisabled)
        setEndPointAction.setDisabled(addPointDisabled)
        setWayPointAction.setDisabled(addPointDisabled)
        addFavoriteAction.setDisabled(addPointDisabled)
        showPosAction.setDisabled(addPointDisabled)
        gotoPosAction.setDisabled(addPointDisabled)
        saveRouteAction.setDisabled(routeIncomplete)
        clearRoutingPointAction.setDisabled(self.getSelectedRoutingPoint(self.mousePos)==None)
        clearAllRoutingPointsAction.setDisabled(addPointDisabled)
        editRoutingPointAction.setDisabled(routeIncomplete)
        zoomToCompleteRoute.setDisabled(routeIncomplete)
        clearRouteAction.setDisabled(self.currentRoute==None)
        
        showRouteDisabled=(self.routeCalculationThread!=None and self.routeCalculationThread.isRunning()) or routeIncomplete
        showRouteAction.setDisabled(showRouteDisabled)
        recalcRouteAction.setDisabled(showRouteDisabled or self.currentRoute==None)
        recalcRouteGPSAction.setDisabled(showRouteDisabled or self.currentRoute==None or self.gpsPoint==None)

        action = menu.exec_(self.mapToGlobal(event.pos()))
#        print(action.text())
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
        elif action==gotoPosAction:
            self.showPosOnMap()
        elif action==showPosAction:
            (lat, lon)=self.getMousePosition(self.mousePos[0], self.mousePos[1])
            self.showPos(lat, lon)
        elif action==saveRouteAction:
            self.saveCurrentRoute()
        elif action==zoomToCompleteRoute:
            self.zoomToCompleteRoute(self.getCompleteRoutingPoints())
        elif action==clearRouteAction:
            self.clearCurrentRoute()
        elif action==recalcRouteAction:
            (lat, lon)=self.getMousePosition(self.mousePos[0], self.mousePos[1])
            currentPoint=OSMRoutingPoint("tmp", OSMRoutingPoint.TYPE_TMP, (lat, lon))                
            self.recalcRouteFromPoint(currentPoint)
        elif action==recalcRouteGPSAction:
            self.recalcRouteFromPoint(self.gpsPoint)
        else:
            if isinstance(action, OSMRoutingPointAction):
                routingPoint=action.getRoutingPoint()
                self.showRoutingPointOnMap(routingPoint)
            
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
                
        for zoom in range(MAX_ZOOM, MIN_ZOOM, -1):
            (pixel_y1, pixel_x1)=self.getPixelPosForLocationDegForZoom(startLat, startLon, True, zoom, centerLat, centerLon)
            (pixel_y2, pixel_x2)=self.getPixelPosForLocationDegForZoom(endLat, endLon, True, zoom, centerLat, centerLon)
        
            if pixel_x1>0 and pixel_x2>0 and pixel_y1>0 and pixel_y2>0:
                if pixel_x1<width and pixel_x2<width and pixel_y1<height and pixel_y2<height:
                    print(zoom)
                    if zoom!=self.map_zoom:
                        self.osm_map_set_zoom(zoom)
                    
                    if self.withMapRotation==True:
                        y,x=self.getPixelPosForLocationDeg(centerLat, centerLon, False)
                        y=y+self.getYOffsetForRotationMap()
                        centerLat=self.osmutils.rad2deg(self.osmutils.pixel2lat(zoom, y))

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

    def showPos(self, lat, lon):
        posDialog=OSMPositionDialog(self, lat, lon)
        posDialog.exec()

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
#            self.zoomToCompleteRoute(self.routingPointList)
        elif result==QDialog.Rejected:
            # even in case of cancel we might have save a route
            self.routeList=routeDialog.getRouteList()
            
    def getSelectedRoutingPoint(self, mousePos):
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
        edgeId, wayId=osmParserData.getEdgeIdOnPos(lat, lon, DEFAULT_SEARCH_MARGIN, 30.0)
        if edgeId==None:
            return 
        
        country=osmParserData.getCountryOfPos(lat, lon)
        if country==None:
            return
        
        wayId, _, _, _, name, nameRef=osmParserData.getWayEntryForId(wayId)
        defaultPointTag=self.getDefaultPositionTagWithCountry(name, nameRef, country)
        if defaultPointTag==None:
            defaultPointTag=""
            
        favNameDialog=OSMSaveFavoritesDialog(self, self.osmWidget.favoriteList, defaultPointTag)
        result=favNameDialog.exec()
        if result==QDialog.Accepted:
            favoriteName=favNameDialog.getResult()
            favoritePoint=OSMRoutingPoint(favoriteName, OSMRoutingPoint.TYPE_FAVORITE, (lat, lon))
            self.osmWidget.favoriteList.append(favoritePoint)
            
    def addRoutingPoint(self, pointType):
        (lat, lon)=self.getMousePosition(self.mousePos[0], self.mousePos[1])
        edgeId, wayId=osmParserData.getEdgeIdOnPos(lat, lon, DEFAULT_SEARCH_MARGIN, 30.0)
        if edgeId==None:
            return
        
        country=osmParserData.getCountryOfPos(lat, lon)
        if country==None:
            return

        wayId, _, _, _, name, nameRef=osmParserData.getWayEntryForId(wayId)
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

    def showPointOnMap(self, mapPoint):
        self.mapPoint=mapPoint
        self.showRoutingPointOnMap(mapPoint)        
        
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
        
        recalcPoint=OSMRoutingPoint("tmp", OSMRoutingPoint.TYPE_TMP, (lat, lon))    
        
        if self.currentRoute!=None and not self.currentRoute.isRouteFinished():
            if self.routeCalculationThread!=None and not self.routeCalculationThread.isRunning():
                self.recalcRouteFromPoint(recalcPoint)
            
    def clearLastEdgeInfo(self):
        self.wayInfo=None
        self.currentCoords=None
        self.lastEdgeId=None
        self.lastWayId=None
        self.speedInfo=None
        self.wayPOIList=None
        self.distanceToEnd=0
        self.distanceToCrossing=0
        self.nextEdgeOnRoute=None
        self.routeInfo=None, None, None, None
        self.refRing=None
        
    def calcNextCrossingInfo(self, lat, lon):
        (direction, crossingInfo, crossingType, crossingRef, crossingEdgeId)=osmParserData.getNextCrossingInfoFromPos(self.currentTrackList, lat, lon)
        self.currentEdgeIndexList=list()
        if crossingEdgeId!=None and crossingEdgeId in self.currentEdgeList:
            crossingEdgeIdIndex=self.currentEdgeList.index(crossingEdgeId)+1
        else:
            crossingEdgeIdIndex=len(self.currentEdgeList)-1

        for i in range(0, crossingEdgeIdIndex+1, 1):
            self.currentEdgeIndexList.append(i)
            
        if direction!=None:
            self.routeInfo=(direction, crossingInfo, crossingType, crossingRef)
        else:
            self.routeInfo=None, None, None, None
            
    def calcRouteDistances(self, lat, lon):
        self.distanceToEnd, self.distanceToCrossing=osmParserData.calcRouteDistances(self.currentTrackList, lat, lon, self.currentRoute)

    def showTrackOnPos(self, lat, lon, track, speed, update, fromMouse):
        if self.routeCalculationThread!=None and self.routeCalculationThread.isRunning():
            return 
        
        edgeId, wayId=osmRouting.getEdgeIdOnPosForRouting(lat, lon, track, self.nextEdgeOnRoute, DEFAULT_SEARCH_MARGIN, fromMouse, speed)
        if edgeId==None:
            self.clearLastEdgeInfo()
        else:   
            if self.currentRoute!=None and self.currentEdgeList!=None and not self.currentRoute.isRouteFinished():                                                                       
                if edgeId!=self.currentEdgeList[0]:
                    # it is possible that edges are "skipped"
                    # so we need to synchronize here
                    if edgeId in self.currentEdgeList:
                        index=self.currentEdgeList.index(edgeId)
                        self.recalcTrigger=0
                        self.currentEdgeList=self.currentEdgeList[index:]
                        self.currentTrackList=self.currentTrackList[index:]
                        if len(self.currentEdgeList)>1:
                            self.nextEdgeOnRoute=self.currentEdgeList[1]
                        else:
                            self.nextEdgeOnRoute=None
                   
                        self.calcNextCrossingInfo(lat, lon)      
                        # initial            
                        self.calcRouteDistances(lat, lon)

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
                  
                if edgeId==self.currentEdgeList[0]:                                    
                    # look if we are on the tracklist start                   
                    onRoute=osmRouting.checkForPosOnTracklist(lat, lon, self.currentTrackList)                            
#                        print(onRoute)
                    if onRoute==False:
                        if self.recalcTrigger==3:
                            self.recalcTrigger=0
                            self.recalcRoute(lat, lon, edgeId)
                            return
                        else:
                            self.recalcTrigger=self.recalcTrigger+1
                            self.routeInfo=(98, "Please turn", 98, 0)
                            self.update()
                            return
                        
                    self.recalcTrigger=0
                        
                    # initial
                    if self.nextEdgeOnRoute==None:
                        if len(self.currentEdgeList)>1:
                            self.nextEdgeOnRoute=self.currentEdgeList[1]
                        else:
                            self.nextEdgeOnRoute=None
                    
                    # only distanceToEnd and crossingLength need to 
                    # be recalculated every time
                    # the rest only if the edge changes above                    
                    self.calcRouteDistances(lat, lon)
                          
                    # initial
                    if self.routeInfo[0]==None:
                        self.calcNextCrossingInfo(lat, lon)     
                    
                    # TODO: start route when start point reached
                    if self.currentTargetPointReached(lat, lon):
                        self.currentRoute.targetPointReached(self.currentRoutePart)
                        self.switchToNextRoutePart()     
                        print(self.currentRoute.isRouteFinished())
                        if self.currentRoute.isRouteFinished():
                            self.clearLastEdgeInfo()
            else:
                if edgeId!=self.lastEdgeId:
                    self.lastEdgeId=edgeId
                    coords=osmParserData.getCoordsOfEdge(edgeId)
                    self.currentCoords=coords
                    self.distanceToEnd=0
                    self.distanceToCrossing=0
                    self.routeInfo=None, None, None, None
                    self.currentEdgeIndexList=None
                    self.nextEdgeOnRoute=None
                      
            if wayId!=self.lastWayId:
                country=osmParserData.getCountryOfPos(lat, lon)
                self.lastWayId=wayId
                wayId, _, _, _, name, nameRef, maxspeed, _=osmParserData.getWayEntryForId5(wayId)
#                print(wayId)
                
#                refRings=osmParserData.mergeEqualWayEntries(wayId)
##                print(refRings)
#                if refRings!=None:
#                    for refRingEntry in refRings:
#                        wayIdList=refRingEntry["wayIdList"]
#                        if wayId in wayIdList:
#                            self.refRing=refRingEntry["refs"]
#                            print(wayIdList)
                    
#                osmParserData.printCrossingsForWayId(wayId)
                self.wayInfo=self.getDefaultPositionTagWithCountry(name, nameRef, country)  
                self.speedInfo=maxspeed
                self.wayPOIList=osmParserData.getPOIListOnWay(wayId)

#                _, _, _, tunnel, _=osmParserData.decodeStreetInfo2(streetInfo)
#                if tunnel==1 and track!=None and speed!=0 and length>MINIMAL_TUNNEL_LENGHTH:
#                    if self.isInTunnel==False:
#                        self.isInTunnel=True
##                            ref=osmParserData.getNearerRefToPoint(lat, lon, startRef, endRef)
##                                self.startTunnelMode(edgeId, ref)
#                else:
#                    if self.isInTunnel==True:
#                        self.isInTunnel=False
##                                self.stopTunnelMode()

                    
#            stop=time.time()
#            print("showTrackOnPos:%f"%(stop-start))
        if update==True:
            self.update()
              
    def startTunnelMode(self, edgeId, ref):
        # trigger to stop all further data
        # from those sources until the first valid 
        self.osmWidget.waitForInvalidGPSSignal=True
        self.osmWidget.waitForInvalidGPSSignalReplay=True

        tunnelSpeed=self.speed        
        tunnelAltitude=self.altitude
        tunnelTrack=self.track
        tmpPointsFrac=tunnelSpeed/3.6

        tunnelTrackLogLines=list()
        print("start of tunnel")
        tunnelEdgeList=osmParserData.getEdgesOfTunnel(edgeId, ref)
        print(tunnelEdgeList)
        
        heading=None
        for tunnelEdgeData in tunnelEdgeList:
            if "edge" in tunnelEdgeData:
                edgeId=tunnelEdgeData["edge"]
            if "startRef"in tunnelEdgeData:
                startRef=tunnelEdgeData["startRef"]
            if "endRef"in tunnelEdgeData:
                endRef=tunnelEdgeData["endRef"]
            if "heading"in tunnelEdgeData:
                edgeHeading=tunnelEdgeData["heading"]
            
            # for now we cannot support crossings in tunnels so
            # choose the path where the heading stays the same
            if heading!=None and self.osmutils.headingDiffAbsolute(heading, edgeHeading)>10:
                continue
            
            (edgeId, _, endRef, _, _, _, _, _, _, _, coords)=osmParserData.getEdgeEntryForEdgeIdWithCoords(edgeId)
            if startRef==endRef:
                coords.reverse()
                
            offsetOnNextEdge=0
            lat1, lon1=coords[0]
            for lat2, lon2 in coords[1:]:
                distance=self.osmutils.distance(lat1, lon1, lat2, lon2)
                heading=self.osmutils.headingDegrees(lat1, lon1, lat2, lon2)
                
                if distance>tmpPointsFrac:
                    nodes=self.osmutils.createTemporaryPoints(lat1, lon1, lat2, lon2, frac=tmpPointsFrac, offsetStart=offsetOnNextEdge, offsetEnd=0.0, addStart=False, addEnd=False)
                    for tmpLat, tmpLon in nodes:
                        gpsData=GPSData(time.time(), tmpLat, tmpLon, heading, tunnelSpeed, tunnelAltitude)
                        tunnelTrackLogLines.append(gpsData)
                        
                    # calc the offset in the next = remaining from last
                    numberOfTmpPoints=int(distance/tmpPointsFrac)
                    remainingOnEdge=distance-(numberOfTmpPoints*tmpPointsFrac)
                    offsetOnNextEdge=int(tmpPointsFrac-remainingOnEdge)

                else:
                    gpsData=GPSData(time.time(), lat2, lon2, tunnelTrack, tunnelSpeed, tunnelAltitude)
                    tunnelTrackLogLines.append(gpsData)
                    
                lat1=lat2
                lon1=lon2
                            
        if self.osmWidget.tunnelModeThread.isRunning():
            self.osmWidget.tunnelModeThread.stop()
                
        self.osmWidget.tunnelModeThread.setup(tunnelTrackLogLines)
      
    def stopTunnelMode(self):
        print("end of tunnel")
        self.osmWidget.waitForInvalidGPSSignal=False
        self.osmWidget.waitForInvalidGPSSignalReplay=False
        
        if self.osmWidget.tunnelModeThread.isRunning():
            self.osmWidget.tunnelModeThread.stop()

    def showRouteForRoutingPoints(self, routingPointList):
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

    def startProgress(self):
        self.emit(SIGNAL("startProgress()"))

    def stopProgress(self):
        self.emit(SIGNAL("stopProgress()"))

    def routeCalculationDone(self):
        if self.currentRoute.getRouteInfo()!=None:
            self.currentRoute.printRoute(osmParserData)
            self.printRouteDescription(self.currentRoute)
            
            self.clearLastEdgeInfo()

            self.currentRoutePart=0
            self.currentEdgeList=self.currentRoute.getEdgeList(self.currentRoutePart)
            self.currentTrackList=self.currentRoute.getTrackList(self.currentRoutePart)
            self.currentStartPoint=self.currentRoute.getStartPoint(self.currentRoutePart)
            self.currentTargetPoint=self.currentRoute.getTargetPoint(self.currentRoutePart)
            self.currentRoutePolygon=None
            self.update()       

    def switchToNextRoutePart(self):
        if self.currentRoutePart < self.currentRoute.getRouteInfoLength()-1:
#            print("switch to next route part")
            self.currentRoutePart=self.currentRoutePart+1
            self.currentEdgeList=self.currentRoute.getEdgeList(self.currentRoutePart)
            self.currentTrackList=self.currentRoute.getTrackList(self.currentRoutePart)
            self.currentStartPoint=self.currentRoute.getStartPoint(self.currentRoutePart)
            self.currentTargetPoint=self.currentRoute.getTargetPoint(self.currentRoutePart)
        
    def currentTargetPointReached(self, lat, lon):
        targetLat, targetLon=self.currentTargetPoint.getPos()
        if self.osmutils.distance(lat, lon, targetLat, targetLon)<10:
            return True
        return False
    
    def clearRoute(self):
        self.distanceToEnd=0
        self.currentEdgeIndexList=None
        self.nextEdgeOnRoute=None
        self.wayInfo=None
        self.lastEdgeId=None
        self.lastWayId=None
        self.currentEdgeList=None
        self.currentTrackList=None
        self.currentStartPoint=None
        self.currentTargetPoint=None
        self.currentRoutePart=0
    
    def getTrackListFromEdge(self, indexEnd, edgeList, trackList):
        if indexEnd < len(edgeList):
            restEdgeList=edgeList[indexEnd:]
            restTrackList=trackList[indexEnd:]
            return restEdgeList, restTrackList
        else:
            return None, None      
               
    def printRouteDescription(self, route):        
        print("start:")
        routeInfo=route.getRouteInfo()
        
        for routeInfoEntry in routeInfo:
            edgeList=routeInfoEntry["edgeList"]   
            trackList=routeInfoEntry["trackList"] 
            print(trackList)
            indexEnd=0
            lastEdgeId=None
            
            while True:
                edgeList, trackList=self.getTrackListFromEdge(indexEnd, edgeList, trackList)
    
                (direction, _, crossingInfo, _, _, lastEdgeId)=osmParserData.getNextCrossingInfo(trackList)
                
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
        (lat, lon)=self.getMousePosition(x, y)
        self.showTrackOnPos(lat, lon, self.track, self.speed, True, True)

    def showTrackOnGPSPos(self, lat, lon, update):
        self.showTrackOnPos(lat, lon, self.track, self.speed, update, False)            
    
    def getMousePosition(self, x, y):
        point=QPointF(x, y)        
        invertedTransform=self.transformHeading.inverted()
        point0=invertedTransform[0].map(point)    
        map_x, map_y=self.getMapZeroPos()
        rlat = self.osmutils.pixel2lat(self.map_zoom, map_y + point0.y());
        rlon = self.osmutils.pixel2lon(self.map_zoom, map_x + point0.x());
        mouseLat = self.osmutils.rad2deg(rlat)
        mouseLon = self.osmutils.rad2deg(rlon)
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
    def __init__(self, parent=None, test=None):
        QWidget.__init__(self, parent)
        self.startLat=47.8
        self.startLon=13.0
        self.lastDownloadState=stoppedState
        self.lastMapnikState=stoppedState
        self.favoriteList=list()
        self.mapWidgetQt=QtOSMWidget(self)
        
        self.style=OSMStyle()
        self.favoriteIcon=QIcon(self.style.getStylePixmap("favoritesPixmap"))
        self.addressIcon=QIcon(self.style.getStylePixmap("addressesPixmap"))
        self.routesIccon=QIcon(self.style.getStylePixmap("routePixmap"))
        self.centerGPSIcon=QIcon(self.style.getStylePixmap("centerGPSPixmap"))
        self.settingsIcon=QIcon(self.style.getStylePixmap("settingsPixmap"))
        self.gpsIcon=QIcon(self.style.getStylePixmap("gpsDataPixmap"))

        self.incLat=0.0
        self.incLon=0.0
        self.step=0
        self.trackLogLines=None
        self.trackLogLine=None
        self.gpsSignalInvalid=False
        self.waitForInvalidGPSSignal=False
        self.waitForInvalidGPSSignalReplay=False
#        self.lastGpsData=None
        self.lastGPSDataTime=None
        self.test=test
        osmParserData.openAllDB()

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
        self.adressButton.setIconSize(iconSize)        
        buttons.addWidget(self.adressButton)
                
        self.favoritesButton=QPushButton("", self)
        self.favoritesButton.setIcon(self.favoriteIcon)
        self.favoritesButton.setToolTip("Favorites")
        self.favoritesButton.clicked.connect(self._showFavorites)
        self.favoritesButton.setIconSize(iconSize)        
        buttons.addWidget(self.favoritesButton)
        
        self.routesButton=QPushButton("", self)
        self.routesButton.setIcon(self.routesIccon)
        self.routesButton.setToolTip("Routes")
        self.routesButton.clicked.connect(self._loadRoute)
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
        
        font = QFont("Mono")
        font.setPointSize(14)
        font.setStyleHint(QFont.TypeWriter)

        coords=QVBoxLayout()        
        coords.setAlignment(Qt.AlignLeft|Qt.AlignTop)
        coords.setSpacing(0)

        buttons.addLayout(coords)

        self.gpsPosValueLat=QLabel("%.5f"%(0.0), self)
        self.gpsPosValueLat.setFont(font)
        self.gpsPosValueLat.setAlignment(Qt.AlignRight)
        coords.addWidget(self.gpsPosValueLat)

        self.gpsPosValueLon=QLabel("%.5f"%(0.0), self)
        self.gpsPosValueLon.setFont(font)
        self.gpsPosValueLon.setAlignment(Qt.AlignRight)
        coords.addWidget(self.gpsPosValueLon)
        
        self.gpsAltitudeValue=QLabel("%d"%(0), self)
        self.gpsAltitudeValue.setFont(font)
        self.gpsAltitudeValue.setAlignment(Qt.AlignRight)
        coords.addWidget(self.gpsAltitudeValue)

        self.gpsSpeedValue=QLabel("%d"%(0), self)
        self.gpsSpeedValue.setFont(font)
        self.gpsSpeedValue.setAlignment(Qt.AlignRight)
        coords.addWidget(self.gpsSpeedValue)
        
        hbox1.addLayout(buttons)

        vbox.addLayout(hbox1)
        
        if self.test==True:
            self.addTestButtons(vbox)

    def addTestButtons(self, vbox):
        buttons=QHBoxLayout()        

        self.testGPSButton=QPushButton("Test GPS", self)
        self.testGPSButton.clicked.connect(self._testGPS)
        buttons.addWidget(self.testGPSButton)
        
#        self.stepRouteButton=QPushButton("Step", self)
#        self.stepRouteButton.clicked.connect(self._stepRoute)
#        buttons.addWidget(self.stepRouteButton)
#        
#        self.resetStepRouteButton=QPushButton("Reset Step", self)
#        self.resetStepRouteButton.clicked.connect(self._resetStepRoute)
#        buttons.addWidget(self.resetStepRouteButton)

        self.loadTrackLogButton=QPushButton("Load Tracklog", self)
        self.loadTrackLogButton.clicked.connect(self._loadTrackLog)
        buttons.addWidget(self.loadTrackLogButton)
        
        self.stepTrackLogButton=QPushButton("Step", self)
        self.stepTrackLogButton.clicked.connect(self._stepTrackLog)
        buttons.addWidget(self.stepTrackLogButton)

        self.stepTrackLogBackButton=QPushButton("Step Back", self)
        self.stepTrackLogBackButton.clicked.connect(self._stepTrackLogBack)
        buttons.addWidget(self.stepTrackLogBackButton)
        
        self.resetStepTrackLogButton=QPushButton("Reset Tracklog", self)
        self.resetStepTrackLogButton.clicked.connect(self._resetTrackLogStep)
        buttons.addWidget(self.resetStepTrackLogButton)

        self.replayTrackLogBackButton=QPushButton("Replay", self)
        self.replayTrackLogBackButton.clicked.connect(self._replayLog)
        buttons.addWidget(self.replayTrackLogBackButton)
        
        self.pauseReplayTrackLogBackButton=QPushButton("Pause", self)
        self.pauseReplayTrackLogBackButton.clicked.connect(self._pauseReplayLog)
        buttons.addWidget(self.pauseReplayTrackLogBackButton)

        self.continueReplayTrackLogBackButton=QPushButton("Continue", self)
        self.continueReplayTrackLogBackButton.clicked.connect(self._continueReplayLog)
        buttons.addWidget(self.continueReplayTrackLogBackButton)

        self.stopReplayTrackLogButton=QPushButton("Stop", self)
        self.stopReplayTrackLogButton.clicked.connect(self._stopReplayLog)
        buttons.addWidget(self.stopReplayTrackLogButton)

        vbox.addLayout(buttons)
        
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
        self.connect(self.mapnikThread, SIGNAL("updateMapnikThreadState(QString)"), self.updateMapnikThreadState)
#        self.connect(self.mapWidgetQt, SIGNAL("updateTrackDisplay(QString)"), self.updateTrackDisplay)
        self.connect(self.mapnikThread, SIGNAL("startProgress()"), self.startProgress)
        self.connect(self.mapnikThread, SIGNAL("stopProgress()"), self.stopProgress)

        self.trackLogReplayThread=OSMGPSLocationWorker(self, False)
        self.trackLogReplayThread.setWidget(self)
        self.connect(self.trackLogReplayThread, SIGNAL("updateGPSDataDisplay1(PyQt_PyObject)"), self.updateGPSDataDisplay1)

        self.tunnelModeThread=OSMGPSLocationWorker(self, True)
        self.tunnelModeThread.setWidget(self)
        self.connect(self.tunnelModeThread, SIGNAL("updateGPSDataDisplay2(PyQt_PyObject)"), self.updateGPSDataDisplay2)
       
    def startProgress(self):
        self.emit(SIGNAL("startProgress()"))

    def stopProgress(self):
        self.emit(SIGNAL("stopProgress()"))

    @pyqtSlot()
    def _showGPSData(self):
        gpsDataDialog=OSMGPSDataDialog(self)
        gpsDataDialog.exec()
        
    @pyqtSlot()
    def _showSettings(self):
        optionsDialog=OSMOptionsDialog(self)
        result=optionsDialog.exec()
        if result==QDialog.Accepted:
            oldMapnikValue=self.getWithMapnikValue()
            oldShow3DValue=self.getShow3DValue()
            oldShowBackgroundTiles=self.getShowBackgroundTiles()
            self.setWithDownloadValue(optionsDialog.withDownload)
            self.setAutocenterGPSValue(optionsDialog.followGPS)
            self.setWithMapnikValue(optionsDialog.withMapnik)
            self.setWithMapRotationValue(optionsDialog.withMapRotation)
            if optionsDialog.withMapnik!=oldMapnikValue:
                self.mapWidgetQt.cleanImageCache()
                self.mapWidgetQt.update()
            self.setShow3DValue(optionsDialog.withShow3D)
            self.setShowBackgroundTiles(optionsDialog.withShowBackgroundTiles)
            if optionsDialog.withShow3D!=oldShow3DValue or optionsDialog.withShowBackgroundTiles!=oldShowBackgroundTiles:
                self.mapWidgetQt.update()
            
            
    @pyqtSlot()
    def _cleanup(self):
        trackLog.closeLogFile()

        if self.downloadThread.isRunning():
            self.downloadThread.stop()        
        
        if self.mapnikThread.isRunning():
            self.mapnikThread.stop()
            
        if self.tunnelModeThread.isRunning():
            self.tunnelModeThread.stop()

        if self.trackLogReplayThread.isRunning():
            self.trackLogReplayThread.stop()
 
        osmParserData.closeAllDB()

    def handleMissingGPSSignal(self):
        osmRouting.cleanAll()
        self.mapWidgetQt.clearLastEdgeInfo()
        self.mapWidgetQt.update()
    
    def updateGPSDisplay(self, session):
        if session!=None:   
            timeStamp=time.time()
            
            #print(session)
            speed=0
            altitude=0
            track=0
            lat=0.0
            lon=0.0
            
            if not gps.isnan(session.fix.track):
                track=int(session.fix.track)
            
            if not gps.isnan(session.fix.speed):
                speed=int(session.fix.speed*3.6)
            
            if not gps.isnan(session.fix.altitude):
                altitude=session.fix.altitude
         
            if not gps.isnan(session.fix.latitude) and not gps.isnan(session.fix.longitude):
                lat=session.fix.latitude
                lon=session.fix.longitude
                
            gpsData=GPSData(timeStamp, lat, lon, track, speed, altitude)
                
            if gpsData.isValid():
                self.gpsSignalInvalid=False
                if self.waitForInvalidGPSSignal==True:
                    # ignore all further until first invalid
                    return
                
                if self.tunnelModeThread.isRunning():
                    self.tunnelModeThread.stop()
                    self.mapWidgetQt.clearLastEdgeInfo()
                    
                self.updateGPSDataDisplay(gpsData, False)
            else:
                self.gpsSignalInvalid=True
                self.waitForInvalidGPSSignal=False
                
                self.handleMissingGPSSignal()

            if self.lastGPSDataTime!=None:
                # 500msec
                if timeStamp-self.lastGPSDataTime<GPS_SIGNAL_MINIMAL_DIFF:
                    return

            self.lastGPSDataTime=timeStamp
            trackLog.addTrackLogLine2(gpsData.toLogLine())

    def updateGPSDataDisplay1(self, gpsData):        
        if gpsData.isValid():
            if self.waitForInvalidGPSSignalReplay==True:
                # ignore all further until first invalid
                return
            
#            print("GPS data from replay thread %s"%gpsData)
            if self.tunnelModeThread.isRunning():
                self.tunnelModeThread.stop()
                self.mapWidgetQt.clearLastEdgeInfo()
                
            self.updateGPSDataDisplay(gpsData, False)
        else:
            self.waitForInvalidGPSSignalReplay=False
            self.handleMissingGPSSignal()
            
    def updateGPSDataDisplay2(self, gpsData):
        if gpsData.isValid():
            print("GPS data from tunnel thread %s"%gpsData)
            self.updateGPSDataDisplay(gpsData, False)
        
    def updateGPSDataDisplay(self, gpsData, debug):                
        lat=gpsData.getLat()
        lon=gpsData.getLon()
        altitude=gpsData.getAltitude()
        speed=gpsData.getSpeed()
        
        start=time.time()
        self.mapWidgetQt.updateGPSLocation(gpsData, debug)
        print("updateGPSLocation %f"%(time.time()-start))
        
        self.gpsPosValueLat.setText("%.5f"%(lat))
        self.gpsPosValueLon.setText("%.5f"%(lon))   
        self.gpsAltitudeValue.setText("%d"%(altitude))
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

    def getShow3DValue(self):
        return self.mapWidgetQt.show3D
    
    def setShow3DValue(self, value):
        self.mapWidgetQt.show3D=value
             
    def getShowBackgroundTiles(self):
        return self.mapWidgetQt.showBackgroundTiles
         
    def setShowBackgroundTiles(self, value):
        self.mapWidgetQt.showBackgroundTiles=value
         
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
        self.setShow3DValue(config.getDefaultSection().getboolean("with3DView", False))
        self.setShowBackgroundTiles(config.getDefaultSection().getboolean("showBackgroundTiles", False))

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
        config.getDefaultSection()["with3DView"]=str(self.getShow3DValue())
        config.getDefaultSection()["showBackgroundTiles"]=str(self.getShowBackgroundTiles())
        if self.mapWidgetQt.gps_rlat!=0.0:
            config.getDefaultSection()["lat"]="%.6f"%self.mapWidgetQt.osmutils.rad2deg(self.mapWidgetQt.gps_rlat)
        else:
            config.getDefaultSection()["lat"]="%.6f"%self.mapWidgetQt.osmutils.rad2deg(self.mapWidgetQt.center_rlat)
            
        if self.mapWidgetQt.gps_rlon!=0.0:    
            config.getDefaultSection()["lon"]="%.6f"%self.mapWidgetQt.osmutils.rad2deg(self.mapWidgetQt.gps_rlon)
        else:
            config.getDefaultSection()["lon"]="%.6f"%self.mapWidgetQt.osmutils.rad2deg(self.mapWidgetQt.center_rlon)
            
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
        
    @pyqtSlot()
    def _showAdress(self):
        searchDialog=OSMAdressDialog(self, osmParserData)
        result=searchDialog.exec()
        if result==QDialog.Accepted:
            address, pointType=searchDialog.getResult()
            (_, refId, country, _, _, streetName, houseNumber, lat, lon)=address
            print(refId)
            if houseNumber!=None:
                name=streetName+" "+houseNumber+" - "+osmParserData.getCountryNameForId(country)
            else:
                name=streetName+" - "+osmParserData.getCountryNameForId(country)
            if pointType==OSMRoutingPoint.TYPE_START:
                routingPoint=OSMRoutingPoint(name, pointType, (lat, lon))  
                self.mapWidgetQt.setStartPoint(routingPoint) 
            elif pointType==OSMRoutingPoint.TYPE_END:
                routingPoint=OSMRoutingPoint(name, pointType, (lat, lon))  
                self.mapWidgetQt.setEndPoint(routingPoint) 
            elif pointType==OSMRoutingPoint.TYPE_WAY:
                routingPoint=OSMRoutingPoint(name, pointType, (lat, lon))  
                self.mapWidgetQt.setWayPoint(routingPoint) 
            elif pointType==pointType:
                mapPoint=OSMRoutingPoint(name, pointType, (lat, lon))  
                self.mapWidgetQt.showPointOnMap(mapPoint)
  
    @pyqtSlot()
    def _showFavorites(self):
        favoritesDialog=OSMFavoritesDialog(self, self.favoriteList)
        result=favoritesDialog.exec()
        if result==QDialog.Accepted:
            point, pointType, favoriteList=favoritesDialog.getResult()
            self.favoriteList=favoriteList
            if point!=None:
                if pointType==OSMRoutingPoint.TYPE_START:
                    routingPoint=OSMRoutingPoint(point.getName(), pointType, point.getPos())  
                    self.mapWidgetQt.setStartPoint(routingPoint) 
                elif pointType==OSMRoutingPoint.TYPE_END:
                    routingPoint=OSMRoutingPoint(point.getName(), pointType, point.getPos())  
                    self.mapWidgetQt.setEndPoint(routingPoint) 
                elif pointType==OSMRoutingPoint.TYPE_WAY:
                    routingPoint=OSMRoutingPoint(point.getName(), pointType, point.getPos())  
                    self.mapWidgetQt.setWayPoint(routingPoint) 
                elif pointType==OSMRoutingPoint.TYPE_MAP:
                    mapPoint=OSMRoutingPoint(point.getName(), pointType, point.getPos())  
                    self.mapWidgetQt.showPointOnMap(mapPoint)

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
                # zoom to route
                self.mapWidgetQt.zoomToCompleteRoute(route.getRoutingPointList())
                
#    def paintEvent(self, event):
#        print("OSMWidget:paintEvent")
#        super(OSMWidget, self).paintEvent(event)
        
    @pyqtSlot()
    def _testGPS(self):
        if self.incLat==0.0:
            self.incLat=self.startLat
            self.incLon=self.startLon
            self.incTrack=0
            self.i=0
#            self.osmWidget.mapWidgetQt.heading=0
        else:
            self.incLat=self.incLat+0.00001
            self.incLon=self.incLon+0.00001
#            self.i=self.i+1
            self.incTrack+=15
            if self.incTrack>360:
                self.incTrack=0
#            self.osmWidget.mapWidgetQt.heading=self.osmWidget.mapWidgetQt.heading+5
        
        print("%.0f meter"%(self.mapWidgetQt.osmutils.distance(self.startLat, self.startLon, self.incLat, self.incLon)))
        gpsData=GPSData(time.time(), self.incLat, self.incLon, self.incTrack, 0, 42)
        print(gpsData)
        self.updateGPSDataDisplay(gpsData, True) 
    
#    @pyqtSlot()
#    def _stepRoute(self):
#        self.mapWidgetQt.printRouteInformationForStep(self.step, self.mapWidgetQt.currentRoute)
#        self.step=self.step+1
#        
#    @pyqtSlot()
#    def _resetStepRoute(self):
#        self.step=0
        
    @pyqtSlot()
    def _loadTrackLog(self):
        fileName = QFileDialog.getOpenFileName(self, "Select Tracklog",
                                                 os.path.join(env.getRoot(), "tracks"),
                                                 "Tracklogs (*.log)")
        if len(fileName)==0:
            return

        lines=list()
        logFile=open(fileName, 'r')
        for line in logFile:
            lines.append(line)
        logFile.close()
        self.trackLogLines=list()
        for line in lines:
            if (len(line)==0 or line=="\n"):
                continue

            gpsData=GPSData()
            gpsData.fromTrackLogLine(line)
            self.trackLogLines.append(gpsData)
        
        self.trackLogLine=0
        
        self.handleMissingGPSSignal()
        
        self._stepTrackLog()

    @pyqtSlot()
    def _stepTrackLog(self):
        if self.trackLogLines!=None:
            if self.trackLogLine<len(self.trackLogLines):
                gpsData=self.trackLogLines[self.trackLogLine]
                self.updateGPSDataDisplay(gpsData, False)
                self.trackLogLine=self.trackLogLine+1
                
    @pyqtSlot()
    def _stepTrackLogBack(self):
        if self.trackLogLines!=None:
            if self.trackLogLine>0:
                self.trackLogLine=self.trackLogLine-1
                gpsData=self.trackLogLines[self.trackLogLine]
                self.updateGPSDataDisplay(gpsData, False)
    
    @pyqtSlot()
    def _resetTrackLogStep(self):
        if self.trackLogLine!=None:
            self.trackLogLine=0
    
    @pyqtSlot()
    def _replayLog(self):
        if self.trackLogLines!=None:
            if self.trackLogReplayThread.isRunning():
                self._stopReplayLog()
                
            self.trackLogReplayThread.setup(self.trackLogLines)

    @pyqtSlot()
    def _stopReplayLog(self):
        if self.trackLogReplayThread.isRunning():
            self.trackLogReplayThread.stop()
        
    @pyqtSlot()
    def _pauseReplayLog(self):
        if self.trackLogReplayThread.isRunning():
            self.trackLogReplayThread.pauseReplay()

    @pyqtSlot()
    def _continueReplayLog(self):
        if not self.trackLogReplayThread.isRunning():
            self.trackLogReplayThread.continueReplay()
            
class OSMWindow(QMainWindow):
    def __init__(self, parent, test):
        QMainWindow.__init__(self, parent)
        font = self.font()
        font.setPointSize(14)
        self.setFont(font)
        self.config=Config("osmmapviewer.cfg")
        self.updateGPSThread=None
        self.initUI(test)

#    def paintEvent(self, event):
#        print("OSMWindow:paintEvent")
#        super(OSMWindow, self).paintEvent(event)

    def stopProgress(self):
        self.progress.setMinimum(0)
        self.progress.setMaximum(1)
        self.progress.reset()
    
    def startProgress(self):
        self.progress.setMinimum(0)
        self.progress.setMaximum(0)
        
    def initUI(self, test):
        self.statusbar=self.statusBar()
        self.progress=QProgressBar()
        self.statusbar.addPermanentWidget(self.progress)

        
        self.osmWidget=OSMWidget(self, test)
        self.osmWidget.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        self.setCentralWidget(self.osmWidget)

        # 47.820630:13.016850
        self.osmWidget.setStartLatitude(47.820154)
        self.osmWidget.setStartLongitude(13.020982)

        top=QVBoxLayout(self.osmWidget)        
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
        
        self.connectPSButton=QCheckBox("Connect GPS", self)
        self.connectPSButton.clicked.connect(self._connectGPS)        
        self.statusbar.addPermanentWidget(self.connectPSButton)

        self.setGeometry(0, 0, 900, 500)
        self.setWindowTitle('OSM')
        
        self.updateGPSThread=GPSMonitorUpateWorker(self)
        self.connect(self.updateGPSThread, SIGNAL("updateStatus(QString)"), self.updateStatusLabel)
        self.connect(self.updateGPSThread, SIGNAL("updateGPSThreadState(QString)"), self.updateGPSThreadState)
        self.connect(self.updateGPSThread, SIGNAL("connectGPSFailed()"), self.connectGPSFailed)
        self.connect(self.updateGPSThread, SIGNAL("updateGPSDisplay(PyQt_PyObject)"), self.osmWidget.updateGPSDisplay)

        self.show()
        
    @pyqtSlot()
    def _connectGPS(self):
        value=self.connectPSButton.isChecked()
        if value==True:
            if not self.updateGPSThread.isRunning():
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
    test=False
    try:
        if argv[1]=="osmtest":
            test=True
    except IndexError:
        test=False
        
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)

    osmWindow = OSMWindow(None, test)
    app.aboutToQuit.connect(osmWindow._cleanup)

    sys.exit(app.exec_())

if __name__ == "__main__":
#    cProfile.run('main(sys.argv)')
    main(sys.argv)
