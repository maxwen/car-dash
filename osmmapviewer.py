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
from utils.env import getTileRoot, getImageRoot, getRoot
from utils.gisutils import GISUtils
import cProfile

from PyQt4.QtCore import QTimer, QMutex, QEvent, QLine, QAbstractTableModel, QRectF, Qt, QPoint, QPointF, QSize, pyqtSlot, SIGNAL, QRect, QThread
from PyQt4.QtGui import QDesktopServices, QMessageBox, QToolTip, QPainterPath, QBrush, QFontMetrics, QLinearGradient, QFileDialog, QPolygonF, QPolygon, QTransform, QColor, QFont, QFrame, QValidator, QFormLayout, QComboBox, QAbstractItemView, QCommonStyle, QStyle, QProgressBar, QItemSelectionModel, QInputDialog, QLineEdit, QHeaderView, QTableView, QDialog, QIcon, QLabel, QMenu, QAction, QMainWindow, QTabWidget, QCheckBox, QPalette, QVBoxLayout, QPushButton, QWidget, QPixmap, QSizePolicy, QPainter, QPen, QHBoxLayout, QApplication
from osmparser.osmdataaccess import Constants, OSMDataAccess
from osmstyle import OSMStyle
from routing.osmrouting import OSMRouting, OSMRoutingPoint, OSMRoute

from utils.config import Config
from utils.osmutils import OSMUtils
from utils.gpsutils import gpsConfig, getGPSUpdateThread, GPSData, gpsRunState, gpsStoppedState
from dialogs.osmdialogs import *

from mapnik.mapnikwrapper import MapnikWrapper, disableMappnik
#from mapnik.mapnikwrappercpp import MapnikWrapperCPP
from tracklog import TrackLog
from Polygon import Polygon

TILESIZE=256
minWidth=640
minHeight=480
MIN_ZOOM=5
MAX_ZOOM=18
MAP_SCROLL_STEP=20
M_LN2=0.69314718055994530942    #log_e 2
IMAGE_WIDTH=64
IMAGE_HEIGHT=64
IMAGE_WIDTH_MEDIUM=48
IMAGE_HEIGHT_MEDIUM=48
IMAGE_WIDTH_SMALL=32
IMAGE_HEIGHT_SMALL=32
IMAGE_WIDTH_LARGE=80
IMAGE_HEIGHT_LARGE=80
IMAGE_WIDTH_TINY=24
IMAGE_HEIGHT_TINY=24

MAX_TILE_CACHE=1000
TILE_CLEANUP_SIZE=50
WITH_CROSSING_DEBUG=True
WITH_TIMING_DEBUG=False
SIDEBAR_WIDTH=80
CONTROL_WIDTH=80
SCREEN_BORDER_WIDTH=50

DEFAULT_SEARCH_MARGIN=0.0003
# length of tunnel where we expect gps signal failure
MINIMAL_TUNNEL_LENGHTH=50
GPS_SIGNAL_MINIMAL_DIFF=0.5
SKY_WIDTH=100

PREDICTION_USE_START_ZOOM=15

defaultTileHome=os.path.join("Maps", "osm", "tiles")
defaultTileServer="tile.openstreetmap.org"
defaultMapnikConfig=os.path.join("mapnik-shape", "osm.xml")
defaultTileStartZoom=15
defaultStart3DZoom=17

idleState="idle"
runState="run"
stoppedState="stopped"

osmParserData = OSMDataAccess()
trackLog=TrackLog(False)
osmRouting=OSMRouting(osmParserData)

class OSMRoutingPointAction(QAction):
    def __init__(self, text, routingPoint, style, parent):
        if routingPoint.getType()!=OSMRoutingPoint.TYPE_MAP and not routingPoint.isValid():
            text=text+"(unresolved)"
            
        QAction.__init__(self, text, parent)
        self.routingPoint=routingPoint
        self.style=style
        
        if self.routingPoint.getType()==OSMRoutingPoint.TYPE_END:
            self.setIcon(QIcon(self.style.getStylePixmap("finishPixmap")))
        if self.routingPoint.getType()==OSMRoutingPoint.TYPE_START:
            self.setIcon(QIcon(self.style.getStylePixmap("startPixmap")))
        if self.routingPoint.getType()==OSMRoutingPoint.TYPE_WAY:
            self.setIcon(QIcon(self.style.getStylePixmap("wayPixmap")))
        if self.routingPoint.getType()==OSMRoutingPoint.TYPE_MAP:
            self.setIcon(QIcon(self.style.getStylePixmap("mapPointPixmap")))
        self.setIconVisibleInMenu(True)
        
    def getRoutingPoint(self):
        return self.routingPoint
    
class OSMDownloadTilesWorker(QThread):
    def __init__(self, parent, tileServer): 
        QThread.__init__(self, parent)
        self.exiting = False
        self.forceDownload=False
        self.downloadQueue=deque()
        self.downloadDoneQueue=deque()
        self.tileServer=tileServer
        
    def setWidget(self, osmWidget):
        self.osmWidget=osmWidget
        
#    def __del__(self):
#        self.exiting = True
#        self.wait()
        
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
        self.updateMap()
#        self.osmWidget.setForceDownload(False, False)
        self.updateStatusLabel("OSM download thread stopped")
        self.updateDownloadThreadState(stoppedState)


class OSMMapnikTilesWorker(QThread):
    def __init__(self, parent, tileDir, mapFile): 
        QThread.__init__(self, parent)
        self.exiting = False
        self.tileDir=tileDir
        self.mapFile=mapFile
#        self.connect(self.mapnikWrapper, SIGNAL("updateMap()"), self.updateMap)
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
        
#    def __del__(self):
#        self.exiting = True
#        self.wait()
        
    def setup(self):
        self.updateStatusLabel("OSM starting mapnik thread")
        if disableMappnik==False:
            self.mapnikWrapper=MapnikWrapper(self.tileDir, self.mapFile)
#        self.mapnikWrapperCPP=MapnikWrapperCPP(self.mapFile)

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
                self.updateMap()
                
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
                
        self.updateMap();
        self.updateStatusLabel("OSM mapnik thread stopped")
        self.updateMapnikThreadState(stoppedState)

class OSMGPSSimulationWorker(QThread):
    def __init__(self, parent): 
        QThread.__init__(self, parent)
        self.exiting = False
        self.currentGPSDataIndex=0
        self.gpsDataLines=None
        self.lastGpsData=None
        self.timeout=1000
    
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
        self.emit(SIGNAL("updateGPSDataDisplaySimulated(PyQt_PyObject)"), gpsData)
        
    def run(self):
        for gpsData in self.gpsDataLines[self.currentGPSDataIndex:]:
            if self.exiting==True:
                break            
            gpsData.time=time.time()
            self.updateGPSDataDisplay(gpsData)
            self.msleep(self.timeout)
            self.currentGPSDataIndex=self.currentGPSDataIndex+1

class OSMUpdateLocationWorker(QThread):
    def __init__(self, parent): 
        QThread.__init__(self, parent)
        self.exiting = False
        self.timeout=100
    
    def setWidget(self, osmWidget):
        self.osmWidget=osmWidget
        
    def setup(self):
        print("starting OSMUpdateLocationWorker")
        self.exiting = False
        self.start()
 
    def stop(self):
        print("stopping OSMUpdateLocationWorker")
        self.exiting = True
        self.wait()
 
    def updateLocation(self):
        self.emit(SIGNAL("updateLocation()"))
        
    def run(self):
        while True:
            if self.exiting==True:
                break
            
            self.updateLocation()
            self.msleep(self.timeout)

    
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
        self.center_rlat = 0.0
        self.center_rlon=0.0
        self.gps_rlat=0.0
        self.gps_rlon=0.0
        
        self.lastHeadingLat=0.0
        self.lastHeadingLon=0.0
        
        self.osmutils=OSMUtils()
        self.tileCache=OrderedDict()
        self.withMapnik=False
        self.withDownload=True
        self.autocenterGPS=False
        self.forceDownload=False
        
#        self.osmControlImage=QPixmap(os.path.join(env.getImageRoot(), "osm-control.png"))
#        self.controlWidgetRect=QRect(0, 0, self.osmControlImage.width(), self.osmControlImage.height())
#        self.zoomRect=QRect(0, 105, 95, 45)
#        self.minusRect=QRect(7, 110, 35, 35)
#        self.plusRect=QRect(53, 110, 35, 35)
        
#        self.moveRect=QRect(0, 0, 95, 95)
#        self.leftRect=QRect(5, 35, 25, 25)
#        self.rightRect=QRect(65, 35, 25, 25)
#        self.upRect=QRect(35, 5, 25, 25)
#        self.downRect=QRect(35, 65, 25, 25)
        
        self.setContextMenuPolicy(Qt.DefaultContextMenu)
        self.moving=False
        self.mousePressed=False
        self.setMouseTracking(True)
        self.posStr="+%.4f , +%.4f" % (0.0, 0.0)
        
        self.tileHome=defaultTileHome
        self.tileServer=defaultTileServer
        self.mapnikConfig=defaultMapnikConfig
        self.tileStartZoom=defaultTileStartZoom
        self.startZoom3DView=defaultStart3DZoom
        
        self.lastMouseMoveX=0
        self.lastMouseMoveY=0
        
        self.selectedEdgeId=None
        self.lastWayId=None
        self.recalcTrigger=0
        self.mousePos=(0, 0)
        self.startPoint=None
        self.endPoint=None
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
        self.drivingMode=False
        self.withShowPOI=False
        self.withShowAreas=False
        self.showSky=False
        self.XAxisRotation=60
        self.speed=0
        self.track=None
        self.stop=True
        self.altitude=0
        self.satelitesInUse=0
        self.currentDisplayBBox=None
        self.show3D=True
        self.nightMode=False
        self.gpsBreadcrumbs=True
        
#        self.setAttribute( Qt.WA_OpaquePaintEvent, True )
#        self.setAttribute( Qt.WA_NoSystemBackground, True )
        
        self.lastWayIdSet=None
        self.wayPolygonCache=dict()
        self.currentRouteOverlayPath=None
        self.areaPolygonCache=dict()
        self.lastOsmIdSet=None
        self.adminPolygonCache=dict()
        self.lastAdminLineIdSet=None      
        self.tagLabelWays=None
        
        self.style=OSMStyle()
        self.mapPoint=None
        self.isVirtualZoom=False
        self.virtualZoomValue=2.0
        self.prefetchBBox=None
        self.sidebarVisible=True

        self.gisUtils=GISUtils()
        self.locationBreadCrumbs=deque("", 10)
        #self.gpsUpdateStartTime=None
        self.routingStarted=False
        self.routeRecalculated=False
    
    def getSidebarWidth(self):
        if self.sidebarVisible==True:
            return SIDEBAR_WIDTH
        return 0
    
    def getDisplayPOITypeList(self):
        return self.style.getDisplayPOITypeList()
    
    def setDisplayPOITypeList(self, displayPOITypeList):
        self.style.setDisplayPOITypeList(displayPOITypeList)
        
    def getDisplayAreaTypeList(self):
        return self.style.getDisplayAreaTypeList()
    
    def setDisplayAreaTypeList(self, displayAreaTypeList):
        self.style.setDisplayAreaTypeList(displayAreaTypeList)
        
    def getRouteList(self):
        return self.routeList
    
    def setRouteList(self, routeList):
        self.routeList=routeList
        
    def getTileHomeFullPath(self):
        if os.path.isabs(self.tileHome):
            return self.tileHome
        else:
            return os.path.join(getTileRoot(), self.tileHome)
    
    def getMapnikConfigFullPath(self):
        if os.path.isabs(self.mapnikConfig):
            return self.mapnikConfig
        else:
            return os.path.join(getTileRoot(), self.mapnikConfig)
        
    def getTileFullPath(self, zoom, x, y):
        home=self.getTileHomeFullPath()
        tilePath=os.path.join(str(zoom), str(x), str(y)+".png")
        fileName=os.path.join(home, tilePath)
        return fileName

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
        self.map_zoom=zoom
        if self.isVirtualZoom==True and zoom!=MAX_ZOOM:
            self.isVirtualZoom=False
            
        self.clearPolygonCache()
        self.checkTileDirForZoom()
        
        self.osm_map_handle_resize()
        
    def osm_map_handle_resize (self):
        (self.center_y, self.center_x)=self.getPixelPosForLocationRad(self.center_rlat, self.center_rlon, False)
        self.center_coord_update()

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
    
    def getMapPosition(self):
        return (self.osmutils.rad2deg(self.center_rlat), self.osmutils.rad2deg(self.center_rlon))

    def getGPSPosition(self):
        if self.gps_rlat!=0.0 and self.gps_rlon!=0.0:
            return (self.osmutils.rad2deg(self.gps_rlat), self.osmutils.rad2deg(self.gps_rlon))
        return None
    
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
            if self.withMapnik==True and disableMappnik==False:
                self.callMapnikForTile(zoom, x, y)
                return self.getTilePlaceholder(zoom, x, y)
            
            elif self.withDownload==True:
                self.osmWidget.downloadThread.addTile("/"+str(zoom)+"/"+str(x)+"/"+str(y)+".png", fileName, self.forceDownload, self.tileServer)
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
        
        if self.show3DView()==True:
            transform.rotate(self.XAxisRotation, Qt.XAxis)    
        
#        if self.isVirtualZoom==True: 
#            transform.scale(self.virtualZoomValue, self.virtualZoomValue)    

        if self.track!=None:
            if self.drivingMode==False or self.withMapRotation==False:
                transform.rotate(self.track)
        
        transform.translate(-(x), -(y))

        return transform
    
    def displayGPSPosition(self):
        if self.gps_rlon==0.0 and self.gps_rlat==0.0:
            return
         
        pixmapWidth, pixmapHeight=self.getPixmapSizeForZoom(IMAGE_WIDTH_MEDIUM, IMAGE_HEIGHT_MEDIUM)
        
        y,x=self.getTransformedPixelPosForLocationRad(self.gps_rlat, self.gps_rlon)
        
        xPos=int(x-pixmapWidth/2)
        yPos=int(y-pixmapHeight/2)

        transform=self.getGPSTransform(x, y)
        self.painter.setTransform(transform)
        
        if self.track!=None:
            self.painter.drawPixmap(xPos, yPos, pixmapWidth, pixmapHeight, self.style.getStylePixmap("gpsPointImage"))
        else:
            self.painter.drawPixmap(xPos, yPos, pixmapWidth, pixmapHeight, self.style.getStylePixmap("gpsPointImageStop"))
                
        self.painter.resetTransform()
 
    def displayMapPosition(self, mapPoint):
        pixmapWidth, pixmapHeight=self.getPixmapSizeForZoom(IMAGE_WIDTH_MEDIUM, IMAGE_HEIGHT_MEDIUM)
        
        y,x=self.getTransformedPixelPosForLocationDeg(mapPoint.getPos()[0], mapPoint.getPos()[1])        
        if self.isPointVisibleTransformed(x, y):
            self.orderedNodeList.append((x, y, pixmapWidth, pixmapHeight, None, None, None, self.style.getStylePixmap("mapPointPixmap")))        
            self.displayRoutingPointRefPositions(mapPoint)
        
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
        skyMargin=0
        if self.show3DView()==True and self.showSky==True:
            skyMargin=SKY_WIDTH

        point0=self.transformHeading.map(point)        
        rect=QRect(0, 0+skyMargin, self.width(), self.height())
        return rect.contains(point0)

    # for already transformed coords
    def isPointVisibleTransformed(self, x, y):
        point=QPoint(x, y)
        skyMargin=0
        if self.show3DView()==True and self.showSky==True:
            skyMargin=SKY_WIDTH
            
        rect=QRect(0, 0+skyMargin, self.width(), self.height())
        return rect.contains(point)    
    
    # bbox in deg (left, top, right, bottom)
    # only use if transform active
    def displayBBox(self, bbox, color):
        y,x=self.getPixelPosForLocationDeg(bbox[1], bbox[0], True)
        y1,x1=self.getPixelPosForLocationDeg(bbox[3], bbox[2], True)
        
        point0=QPointF(x, y)        
        point1=QPointF(x1, y1)        

        rect=QRectF(point0, point1)
        
        self.painter.setPen(QPen(color))
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
    def displayRoutingEdges(self, edgeList, expectedNextEdge):
        pen=QPen()
        pen.setWidth(3)
        if edgeList!=None and len(edgeList)!=0:
            for edge in edgeList:
                _, _, _, _, _, _, _, _, _, _, coords=edge
                if expectedNextEdge!=None and edge==expectedNextEdge:
                    pen.setColor(Qt.green)
                else:
                    pen.setColor(Qt.red)
    
                self.displayCoords(coords, pen)

    def displayExpectedEdge(self, edgeList, expectedNextEdge):
        pen=QPen()
        pen.setWidth(3)
        if edgeList!=None and len(edgeList)!=0:
            for edge in edgeList:
                _, _, _, _, _, _, _, _, _, _, coords=edge
                if expectedNextEdge!=None and edge==expectedNextEdge:
                    pen.setColor(Qt.green)
                    self.displayCoords(coords, pen)

    # only use if transform is active
    def displayApproachingRef(self, approachingRefPos):
        if approachingRefPos!=None:
            pen=QPen()
            pen.setWidth(3)
            lat, lon=approachingRefPos
            
            y,x=self.getPixelPosForLocationDeg(lat, lon, True)
            if self.isPointVisible(x, y):
                pen.setColor(Qt.red)
                pen.setWidth(self.style.getPenWithForPoints(self.map_zoom))  
                pen.setCapStyle(Qt.RoundCap)
                self.painter.setPen(pen)
                self.painter.drawPoint(x, y)
                return True
            
        return False

    def getVisibleBBoxDeg(self):
        invertedTransform=self.transformHeading.inverted()
        map_x, map_y=self.getMapZeroPos()
        
        skyMargin=0
        if self.show3DView()==True and self.showSky==True:
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
        if self.drivingMode==True and self.autocenterGPS==True:
            self.osm_autocenter_map(False)
        self.update()
       
    def resizeEvent(self, event):
        self.clearPolygonCache()
        self.osm_map_handle_resize()
    
    def getTransform(self, withMapRotate, rotateAngle):
        transform=QTransform()
        
        map_x, map_y=self.getMapZeroPos()
        transform.translate( self.center_x-map_x, self.center_y-map_y )
        
        if self.show3DView()==True:
            transform.rotate(self.XAxisRotation, Qt.XAxis)  
        
        if self.isVirtualZoom==True: 
            transform.scale(self.virtualZoomValue, self.virtualZoomValue)    
        
        if self.drivingMode==True:
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
    
    def getPrefetchBoxMargin(self):    
        if self.map_zoom in range(17, 19):
            return 0.005
        if self.map_zoom in range(14, 17):
            return 0.02
        
        #approx 10km
        return 0.1
    
    # x,y in pixels for check if geom is in visible area
    def calcVisiblePolygon(self):
        skyMargin=0
        if self.show3DView()==True and self.showSky==True:
            skyMargin=SKY_WIDTH
            
        invertedTransform=self.transformHeading.inverted()
        point=QPoint(0, 0+skyMargin);
        point0=invertedTransform[0].map(point)
        point=QPoint(self.width(), 0+skyMargin);
        point1=invertedTransform[0].map(point)
        point=QPoint(self.width(), self.height());
        point2=invertedTransform[0].map(point)
        point=QPoint(0, self.height());
        point3=invertedTransform[0].map(point)
        
        cont=[(point0.x(), point0.y()), (point1.x(), point1.y()), (point2.x(), point2.y()), (point3.x(), point3.y())]
        self.visibleCPolygon = Polygon(cont)

    # smaler one without control elements
    # e.g. for way tag positions so that they are not too 
    # near to the border and not hidden behind
    def calcVisiblePolygon2(self):            
        invertedTransform=self.transformHeading.inverted()
        point=QPoint(SCREEN_BORDER_WIDTH, 0+SCREEN_BORDER_WIDTH);
        point0=invertedTransform[0].map(point)
        point=QPoint(self.width()-SCREEN_BORDER_WIDTH, 0+SCREEN_BORDER_WIDTH);
        point1=invertedTransform[0].map(point)
        point=QPoint(self.width()-SCREEN_BORDER_WIDTH, self.height()-SCREEN_BORDER_WIDTH);
        point2=invertedTransform[0].map(point)
        point=QPoint(SCREEN_BORDER_WIDTH, self.height()-SCREEN_BORDER_WIDTH);
        point3=invertedTransform[0].map(point)
        
        cont=[(point0.x(), point0.y()), (point1.x(), point1.y()), (point2.x(), point2.y()), (point3.x(), point3.y())]
        self.visibleCPolygon2 = Polygon(cont)
        
    def calcPrefetchBox(self, bbox):
#        if self.track!=None:
#            self.prefetchBBox=self.calcTrackBasedPrefetchBox(self.track, bbox)
#        else:
        self.prefetchBBox=osmParserData.createBBoxWithMargin(bbox, self.getPrefetchBoxMargin())
        self.prefetchBBoxCPolygon=Polygon([(self.prefetchBBox[0], self.prefetchBBox[3]), (self.prefetchBBox[2], self.prefetchBBox[3]), (self.prefetchBBox[2], self.prefetchBBox[1]), (self.prefetchBBox[0], self.prefetchBBox[1])])
        
    def calcTrackBasedPrefetchBox(self, track, bbox):
        xmargin1=0
        ymargin1=0
        xmargin2=0
        ymargin2=0
        
        margin=self.getPrefetchBoxMargin()
        
        if (track>315 and track<=359) or (track>=0 and track<=45):
            xmargin1=margin
            xmargin2=margin
            ymargin2=margin
        elif track>45 and track<=135:
            ymargin1=margin
            xmargin2=margin
            ymargin2=margin
        elif track>135 and track <=225:
            xmargin1=margin
            ymargin1=margin
            xmargin2=margin
        elif track>225 and track<=315:
            xmargin1=margin
            ymargin1=margin
            ymargin2=margin
        
        latRangeMax=bbox[3]+ymargin2
        lonRangeMax=bbox[2]+xmargin2
        latRangeMin=bbox[1]-ymargin1
        lonRangeMin=bbox[0]-xmargin1 
        
        return lonRangeMin, latRangeMin, lonRangeMax, latRangeMax
        
    def isNewBBox(self, bbox):
        bboxCPolyon=Polygon([(bbox[0], bbox[3]), (bbox[2], bbox[3]), (bbox[2], bbox[1]), (bbox[0], bbox[1])])    
        if self.prefetchBBox==None:
            self.calcPrefetchBox(bbox)
            return True
        else:
            newBBox=not self.prefetchBBoxCPolygon.covers(bboxCPolyon)
            if newBBox==True:
#                print("newbbox")
                self.calcPrefetchBox(bbox)
                return True
            
        return False
    
    def setAntialiasing(self, value):
        if self.map_zoom>=self.style.USE_ANTIALIASING_START_ZOOM:
            self.painter.setRenderHint(QPainter.Antialiasing, value)
        else:
            self.painter.setRenderHint(QPainter.Antialiasing, False)
  
    def show3DView(self):
        return self.show3D==True and self.map_zoom>=self.startZoom3DView
    
    def paintEvent(self, event):
#        self.setCursor(Qt.WaitCursor)
        start=time.time()
        self.painter=QPainter(self)
        self.painter.setClipRect(QRectF(0, 0, self.width(), self.height()))
            
        self.painter.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setAntialiasing(True)
                
        self.painter.fillRect(0, 0, self.width(), self.height(), self.style.getStyleColor("mapBackgroundColor"))

        rotateAngle=None
        if self.track!=None:
            rotateAngle=360-self.track
            
        self.transformHeading=self.getTransform(self.withMapRotation, rotateAngle)
            
        self.painter.setTransform(self.transformHeading)

#        print(self.map_zoom)

        self.calcVisiblePolygon()
        self.calcVisiblePolygon2()
        bbox=self.getVisibleBBoxDeg()    
        newBBox=self.isNewBBox(bbox)

#        countryStart=time.time()
#        countryList=osmParserData.buSimple.countryNameListOfBBox(self.prefetchBBox)
#        print("%s %f"%(countryList, time.time()-countryStart))
              
        self.numHiddenPolygons=0
        self.numVisiblePolygons=0
        self.numHiddenWays=0
        self.numVisibleWays=0
        self.numHiddenAdminLiness=0
        self.numVisibleAdminLines=0
                
        self.orderedNodeList=list()
        
        fetchStart=time.time()
        drawStart=time.time()
        
        if self.map_zoom>self.tileStartZoom:
            if newBBox==True:
                self.bridgeWays=list()
                self.tunnelWays=list()
                self.otherWays=list()
                self.railwayLines=list()
                self.railwayBridgeLines=list()
                self.railwayTunnelLines=list()
                self.areaList=list()
                self.naturalTunnelLines=list()
                self.buildingList=list()
                self.aerowayLines=list()
                self.tagLabelWays=dict()
                self.adminLineList=list()
                
                fetchStart=time.time()

                self.getVisibleWays(self.prefetchBBox)
                self.getVisibleAdminLines(self.prefetchBBox)
                
            if self.withShowAreas==True:
                if newBBox==True:
                    if self.map_zoom>=10:
                        self.getVisibleAreas(self.prefetchBBox)
                
                if WITH_TIMING_DEBUG==True:
                    print("paintEvent fetch polygons:%f"%(time.time()-fetchStart))

                drawStart=time.time()
            
                self.setAntialiasing(False)
                self.displayTunnelRailways()
                self.displayTunnelNatural()            
                self.displayAreas()
 
            self.displayAdminLines()
            
            self.setAntialiasing(True)
            self.displayTunnelWays()
            
            if self.withShowAreas==True:
                self.setAntialiasing(False)
                self.displayBuildings()

            self.setAntialiasing(True)
            self.displayWays()

            if self.withShowAreas==True:
                self.setAntialiasing(False)
                self.displayAeroways()
                self.displayRailways()
                self.displayBridgeRailways()
                
            self.setAntialiasing(True)
            self.displayBridgeWays()
                        
            if WITH_TIMING_DEBUG==True:
                print("paintEvent draw polygons:%f"%(time.time()-drawStart))

        else:
            self.showTiles()
               
        if self.currentRoute!=None and self.routeCalculationThread!=None and not self.routeCalculationThread.isRunning():
            self.displayRoute(self.currentRoute)
            if self.drivingMode==True:
                if self.currentEdgeIndexList!=None:
                    self.displayRouteOverlay(self.currentTrackList, self.currentEdgeIndexList)
        
        if self.currentCoords!=None:
            self.style.getStylePen("edgePen").setWidth(self.style.getStreetPenWidthForZoom(self.map_zoom))
            self.displayCoords(self.currentCoords, self.style.getStylePen("edgePen"))
                        
        approachingRef, approachingRefPos=osmRouting.getApproachingRef()
        nextCrossingVisible=self.displayApproachingRef(approachingRefPos)
                
        if WITH_CROSSING_DEBUG==True:
#            if osmRouting.getCurrentSearchEdgeList()!=None:
#                self.displayRoutingEdges(osmRouting.getCurrentSearchEdgeList(), osmRouting.getExpectedNextEdge())

            if osmRouting.getExpectedNextEdge()!=None and osmRouting.getCurrentSearchEdgeList()!=None:
                self.displayExpectedEdge(osmRouting.getCurrentSearchEdgeList(), osmRouting.getExpectedNextEdge())
    
            if osmParserData.getCurrentSearchBBox()!=None:
                self.displayBBox(osmParserData.getCurrentSearchBBox(), Qt.green)
                
#            if osmParserData.getRoutingWapper().getCurrentRoutingBBox()!=None:
#                self.displayBBox(osmParserData.getRoutingWapper().getCurrentRoutingBBox(), Qt.red)

#        if self.osmWidget.trackLogLines!=None:
#            self.displayTrack(self.osmWidget.trackLogLines)
                    
#        self.displayTestPoints()
                    
        if self.gpsBreadcrumbs==True:
            self.displayLocationBredCrumbs()
            
        self.painter.resetTransform()
        
                
        if self.show3DView()==True and self.showSky==True:
            skyRect=QRectF(0, 0, self.width(), SKY_WIDTH)
            gradient=QLinearGradient(skyRect.topLeft(), skyRect.bottomLeft())
            gradient.setColorAt(1, self.style.getStyleColor("mapBackgroundColor"))
            gradient.setColorAt(0, Qt.blue)
            self.painter.fillRect(skyRect, gradient)
            
        self.painter.setRenderHint(QPainter.Antialiasing)
        
        if self.withShowPOI==True:
            # not prefetch box!
            self.displayVisibleNodes(bbox)
        
        if self.mapPoint!=None:
            self.displayMapPosition(self.mapPoint)

        self.displayRoutingPoints()

        # sort by y voordinate
        # farthest nodes (smaller y coordinate) are drawn first
        if self.show3DView()==True:
            self.orderedNodeList.sort(key=self.nodeSortByYCoordinate, reverse=False)

        self.displayNodes()

        if self.map_zoom>=self.style.SHOW_REF_LABEL_WAYS_START_ZOOM:
            if self.tagLabelWays!=None and len(self.tagLabelWays)!=0:
                tagStart=time.time()
                if self.drivingMode==False:
                    self.displayWayTags(self.tagLabelWays)
                else:
                    if nextCrossingVisible==True:
                        edgeList=osmRouting.getCurrentSearchEdgeList()
                        currentEdge=osmRouting.getCurrentEdge()
                        if edgeList!=None and len(edgeList)>1 and currentEdge!=None:
                            currentTagText=None
                            _, _, _, _, wayId, _, _, _, _, _, _=currentEdge
                            if wayId in self.tagLabelWays.keys():
                                wayId, _, _, _, name, nameRef, _, _, _, _=self.tagLabelWays[wayId] 
                                currentTagText=self.getWayTagText(name, nameRef)
    
                            newTagLabelWays=dict()
                            for edge in edgeList:
                                _, _, endRef, _, wayId, _, _, _, _, _, _=edge

                                if edge==currentEdge:
                                    continue
                                
                                reverseRefs=False
                                if approachingRef==endRef:
                                    reverseRefs=True
                                    
                                if wayId in self.tagLabelWays.keys():
                                    wayId, _, _, _, name, nameRef, _, _, _, _=self.tagLabelWays[wayId] 
    
                                    tagText=self.getWayTagText(name, nameRef)
                                    if tagText!=None:    
                                        if currentTagText!=None and tagText==currentTagText:
                                            continue
                                        
                                        newTagLabelWays[wayId]=(self.tagLabelWays[wayId], reverseRefs)
                            
                            self.displayWayTagsForRouting(newTagLabelWays)
                
                if WITH_TIMING_DEBUG==True:
                    print("paintEvent displayWayTags:%f"%(time.time()-tagStart))
        
        self.displayGPSPosition()
        
        self.displaySidebar()
        self.displayTopbar()
            
#        self.displayControlOverlay()
        self.displayControlOverlay2()

        self.showEnforcementInfo()
        self.showTextInfoBackground()
        
        if self.currentRoute!=None and self.currentTrackList!=None and not self.currentRoute.isRouteFinished():
            self.displayRouteInfo()
            
        self.showTextInfo()
        self.showSpeedInfo()
        self.showTunnelInfo()
        
        if self.nightMode==True:
            self.painter.fillRect(0, 0, self.width(), self.height(), self.style.getStyleColor("nightModeColor"))
        
        self.painter.end()

        if WITH_TIMING_DEBUG==True:
            print("displayedPolgons: %d hiddenPolygons: %d"%(self.numVisiblePolygons, self.numHiddenPolygons))
            print("displayedWays: %d hiddenWays: %d"%(self.numVisibleWays, self.numHiddenWays))
            print("displayedAdminLines: %d hiddenAdminLines: %d"%(self.numVisibleAdminLines, self.numHiddenAdminLiness))
        
            print("paintEvent:%f"%(time.time()-start))
        
    def displayLocationBredCrumbs(self):
        for gpsData in self.locationBreadCrumbs:
            lat=gpsData.lat
            lon=gpsData.lon
            predicted=gpsData.predicted
            
            pen=QPen()
            pen.setWidth(3)
            
            y,x=self.getPixelPosForLocationDeg(lat, lon, True)
            if self.isPointVisible(x, y):
                if predicted==True:
                    pen.setColor(Qt.black)
                else:
                    pen.setColor(Qt.green)
                    
                pen.setWidth(4.0)  
                pen.setCapStyle(Qt.RoundCap)
                self.painter.setPen(pen)
                self.painter.drawPoint(x, y)

    def displaySidebar(self):
        diff =40-32
        if self.sidebarVisible==True:
            textBackground=QRect(self.width()-SIDEBAR_WIDTH, 0, SIDEBAR_WIDTH, self.height())
            self.painter.fillRect(textBackground, self.style.getStyleColor("backgroundColor"))
            self.painter.drawPixmap(self.width()-SIDEBAR_WIDTH+diff/2, 0+diff/2, 32, 32, self.style.getStylePixmap("hideSidebarPixmap"))
            self.sidebarControlRect=QRect(self.width()-SIDEBAR_WIDTH, 0, SIDEBAR_WIDTH, 40)
            self.sidebarRect=QRect(self.width()-SIDEBAR_WIDTH, self.sidebarControlRect.height(), SIDEBAR_WIDTH, self.height()-self.sidebarControlRect.height())
        
            self.painter.drawPixmap(self.width()-SIDEBAR_WIDTH+diff/2, 40+diff/2, IMAGE_WIDTH, IMAGE_HEIGHT, self.style.getStylePixmap("addressesPixmap"))
            self.searchRect=QRect(self.width()-SIDEBAR_WIDTH+diff/2, 40+diff/2, IMAGE_WIDTH, IMAGE_HEIGHT)

            self.painter.drawPixmap(self.width()-SIDEBAR_WIDTH+diff/2, 40+IMAGE_HEIGHT+diff/2, IMAGE_WIDTH, IMAGE_HEIGHT, self.style.getStylePixmap("favoritesPixmap"))
            self.favoriteRect=QRect(self.width()-SIDEBAR_WIDTH+diff/2, 40+IMAGE_HEIGHT+diff/2, IMAGE_WIDTH, IMAGE_HEIGHT)

            self.painter.drawPixmap(self.width()-SIDEBAR_WIDTH+diff/2, 40+2*IMAGE_HEIGHT+diff/2, IMAGE_WIDTH, IMAGE_HEIGHT, self.style.getStylePixmap("routePixmap"))
            self.routesRect=QRect(self.width()-SIDEBAR_WIDTH+diff/2, 40+2*IMAGE_HEIGHT+diff/2, IMAGE_WIDTH, IMAGE_HEIGHT)

            self.painter.drawPixmap(self.width()-SIDEBAR_WIDTH+diff/2, 40+3*IMAGE_HEIGHT+diff/2, IMAGE_WIDTH, IMAGE_HEIGHT, self.style.getStylePixmap("centerGPSPixmap"))
            self.centerGPSRect=QRect(self.width()-SIDEBAR_WIDTH+diff/2, 40+3*IMAGE_HEIGHT+diff/2, IMAGE_WIDTH, IMAGE_HEIGHT)

            self.painter.drawPixmap(self.width()-SIDEBAR_WIDTH+diff/2, 40+5*IMAGE_HEIGHT+diff/2, IMAGE_WIDTH, IMAGE_HEIGHT, self.style.getStylePixmap("settingsPixmap"))
            self.optionsRect=QRect(self.width()-SIDEBAR_WIDTH+diff/2, 40+5*IMAGE_HEIGHT+diff/2, IMAGE_WIDTH, IMAGE_HEIGHT)

        else:
            self.sidebarRect=None
            textBackground=QRect(self.width()-SIDEBAR_WIDTH, CONTROL_WIDTH, SIDEBAR_WIDTH, 40)
            self.painter.fillRect(textBackground, self.style.getStyleColor("backgroundColor"))
            self.painter.drawPixmap(self.width()-SIDEBAR_WIDTH+diff/2, CONTROL_WIDTH+diff/2, 32, 32, self.style.getStylePixmap("showSidebarPixmap"))
            self.sidebarControlRect=textBackground
            
    def displayTopbar(self):
        textBackground=QRect(CONTROL_WIDTH, 0, self.width()-self.getSidebarWidth()-2*CONTROL_WIDTH, 30)
        self.painter.fillRect(textBackground, self.style.getStyleColor("backgroundColor"))
        
        font=self.style.getStyleFont("monoFontTopbar")
        self.painter.setFont(font)
        fm=self.painter.fontMetrics()
        
        lat=self.osmutils.rad2deg(self.gps_rlat)
        lon=self.osmutils.rad2deg(self.gps_rlon)
        track=self.track
        if track==None:
            track=0
        
        self.painter.setPen(self.style.getStylePen("textPen"))
        self.painter.drawText(QPointF(CONTROL_WIDTH+20, fm.height()-2), "%.6f %.6f %3dkm/h %4dm %3d %2d"%(lat, lon, self.speed, self.altitude, track, self.satelitesInUse))
        
    def getStreetTypeListForOneway(self):
        return Constants.ONEWAY_OVERLAY_STREET_SET
        
    def getStreetTypeListForZoom(self):
        if self.map_zoom in range(15, 19):
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
                Constants.STREET_TYPE_RESIDENTIAL,
                Constants.STREET_TYPE_ROAD,
                Constants.STREET_TYPE_UNCLASSIFIED]
            
        elif self.map_zoom in range(self.tileStartZoom, 15):
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
                       
    def clearPolygonCache(self):
        self.prefetchBBox=None
        self.wayPolygonCache=dict()
        self.areaPolygonCache=dict()
        self.adminPolygonCache=dict()
    
    def getVisibleAdminLines(self, bbox):
        start=time.time()
        adminLineList, adminLineIdSet=osmParserData.getAdminLinesInBboxWithGeom(bbox, 0.0, Constants.ADMIN_LEVEL_DISPLAY_SET)
        
        if WITH_TIMING_DEBUG==True:
            print("getAdminLinesInBboxWithGeom: %f"%(time.time()-start))
        
        if self.lastAdminLineIdSet==None:
            self.lastAdminLineIdSet=adminLineIdSet
        else:
            removedLines=self.lastAdminLineIdSet-adminLineIdSet
            self.lastAdminLineIdSet=adminLineIdSet
            
            for lineId in removedLines:
                if lineId in self.adminPolygonCache.keys():
                    del self.adminPolygonCache[lineId]
            
        self.adminLineList=adminLineList

    def displayAdminLines(self):
        pen=QPen()
        pen.setStyle(Qt.DashDotLine)
        pen.setColor(Qt.blue)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        
        if self.map_zoom>17:
            pen.setWidth(4.0)
        elif self.map_zoom>15:
            pen.setWidth(3.0)
        else:
            pen.setWidth(2.0)
            
        
        for line in self.adminLineList:
            self.displayAdminLineWithCache(line, pen)
        
    def getVisibleWays(self, bbox):
        streetTypeList=self.getStreetTypeListForZoom()
        if streetTypeList==None:
            return 
        
        start=time.time()
        if self.map_zoom>=14:
            resultList, wayIdSet=osmParserData.getWaysInBboxWithGeom(bbox, 0.0, streetTypeList)        
        elif self.map_zoom>=12:
            resultList, wayIdSet=osmParserData.getWaysInBboxWithGeom(bbox, 0.0, streetTypeList, True, 50.0)        
        elif self.map_zoom>=10:
            resultList, wayIdSet=osmParserData.getWaysInBboxWithGeom(bbox, 0.0, streetTypeList, True, 100.0)        
        
        if WITH_TIMING_DEBUG==True:
            print("getWaysInBboxWithGeom: %f"%(time.time()-start))
        
        if self.lastWayIdSet==None:
            self.lastWayIdSet=wayIdSet
        else:
            removedWays=self.lastWayIdSet-wayIdSet
            self.lastWayIdSet=wayIdSet
            
            for wayId in removedWays:
                if wayId in self.wayPolygonCache.keys():
                    del self.wayPolygonCache[wayId]
            
        
        for way in resultList:
            wayId, _, _, streetInfo, _, _, _, _, _, _=way
            streetTypeId, _, _, tunnel, bridge=osmParserData.decodeStreetInfo2(streetInfo)
            
            if self.map_zoom>=self.style.SHOW_NAME_LABEL_WAYS_START_ZOOM:
                if streetTypeId in Constants.NAME_LABEL_WAY_SET:
                    self.tagLabelWays[wayId]=way
                    
            elif self.map_zoom>=self.style.SHOW_REF_LABEL_WAYS_START_ZOOM:
                if streetTypeId in Constants.REF_LABEL_WAY_SET:
                    self.tagLabelWays[wayId]=way

            if bridge==1:
                self.bridgeWays.append(way)
                continue
            
            if tunnel==1:
                self.tunnelWays.append(way)
                continue
            

            self.otherWays.append(way)

    def getVisibleNodeForWayTag(self, wayPainterPath):
        for tagLabelPoint in range(1, 9, 1):
            point=wayPainterPath.pointAtPercent(tagLabelPoint/10)
            if self.visibleCPolygon2.isInside(point.x(), point.y()): 
                return point
                        
        return None
    
    def getWayTagText(self, name, nameRef):
        onlyRefs=False
        if self.map_zoom>=self.style.SHOW_REF_LABEL_WAYS_START_ZOOM and self.map_zoom<self.style.SHOW_NAME_LABEL_WAYS_START_ZOOM:
            onlyRefs=True

        tagText=None
        if onlyRefs==True:
            if nameRef!=None:
                tagText=nameRef
        else:
            if name!=None:
                tagText=name
                if nameRef!=None:
                    tagText=tagText+":"+nameRef
        return tagText
    
    def displayWayTags(self, tagLabelWays):
        if tagLabelWays!=None and len(tagLabelWays)!=0:
            font=self.style.getFontForTextDisplay(self.map_zoom, self.isVirtualZoom)
            if font==None:
                return
                                
            numVisibleTags=0
            numHiddenTags=0
            
            map_x, map_y=self.getMapZeroPos()
            brush=self.style.getStyleBrush("placeTag")
            pen=self.style.getStylePen("placePen")
            
            painterPathDict=dict()
            visibleWayTagStrings=set()
            for way in tagLabelWays.values():
                wayId, _, _, _, name, nameRef, _, _, _, _=way 
                
                if wayId in self.wayPolygonCache.keys():
                    _, wayPainterPath=self.wayPolygonCache[wayId]
                    
                    tagText=self.getWayTagText(name, nameRef)
                    
                    if tagText!=None:
                        wayPainterPath=wayPainterPath.translated(-map_x, -map_y)                           
                        point=self.getVisibleNodeForWayTag(wayPainterPath)

                        if point!=None:
                            numVisibleTags=numVisibleTags+1

                            if not tagText in visibleWayTagStrings:
                                visibleWayTagStrings.add(tagText)
                                point0=self.transformHeading.map(point)
                                painterPath, painterPathText=self.createTextLabel(tagText, font)
                                painterPath, painterPathText=self.moveTextLabelToPos(point0.x(), point0.y(), painterPath, painterPathText)
                                rect=painterPath.boundingRect()
                           
                                painterPathDict[wayId]=(painterPath, painterPathText, point0, rect)
                        else:
                            numHiddenTags=numHiddenTags+1


            for wayId, (painterPath, painterPathText, point, rect) in painterPathDict.items():
                self.displayTextLabel(painterPath, painterPathText, brush, pen)
            
            if WITH_TIMING_DEBUG==True:
                print("visible tags:%d hidden tags:%d"%(numVisibleTags, numHiddenTags))

    # find position of tag for driving mode
    # should be as near as possible to the crossing but 
    # should not overlap with others
    def calcWayTagPlacement(self, wayPainterPath, reverseRefs, tagPainterPath, tagPainterPathText, rectList):
        if reverseRefs==False:
#            for tagLabelPoint in range(5, 50, 5):
                percent=wayPainterPath.percentAtLength(80)
                point=wayPainterPath.pointAtPercent(percent)
                if self.visibleCPolygon2.isInside(point.x(), point.y()): 
                    point0=self.transformHeading.map(point)
                    newTagPainterPath, newTagPainterPathText=self.moveTextLabelToPos(point0.x(), point0.y(), tagPainterPath, tagPainterPathText)
                    rect=newTagPainterPath.boundingRect()
                    placeFound=True
#                    for visibleRect in rectList:
#                        if visibleRect.intersects(rect):
#                            placeFound=False
                        
                    if placeFound==True:
                        rectList.append(rect)
                        return newTagPainterPath, newTagPainterPathText
        else:
#            for tagLabelPoint in range(50, 5, -5):
                percent=wayPainterPath.percentAtLength(wayPainterPath.length()-80)
                point=wayPainterPath.pointAtPercent(percent)
                if self.visibleCPolygon2.isInside(point.x(), point.y()):
                    point0=self.transformHeading.map(point)
                    newTagPainterPath, newTagPainterPathText=self.moveTextLabelToPos(point0.x(), point0.y(), tagPainterPath, tagPainterPathText)
                    rect=newTagPainterPath.boundingRect()
                    placeFound=True
#                    for visibleRect in rectList:
#                        if visibleRect.intersects(rect):
#                            placeFound=False
                        
                    if placeFound==True:
                        rectList.append(rect)
                        return newTagPainterPath, newTagPainterPathText

            
        return None, None

    def displayWayTagsForRouting(self, tagLabelWays):
        if tagLabelWays!=None and len(tagLabelWays)!=0:
            font=self.style.getFontForTextDisplay(self.map_zoom, self.isVirtualZoom)
            if font==None:
                return
                                            
            map_x, map_y=self.getMapZeroPos()
            brush=self.style.getStyleBrush("placeTag")
            pen=self.style.getStylePen("placePen")
            
            painterPathDict=dict()
            rectList=list()
            for way, reverseRefs in tagLabelWays.values():
                wayId, _, _, _, name, nameRef, _, _, _, _=way 
                
                if wayId in self.wayPolygonCache.keys():
                    _, wayPainterPath=self.wayPolygonCache[wayId]
                    
                    tagText=self.getWayTagText(name, nameRef)
                    
                    if tagText!=None:
                        wayPainterPath=wayPainterPath.translated(-map_x, -map_y)
                        tagPainterPath, tagPainterPathText=self.createTextLabel(tagText, font)
            
                        newTagPainterPath, newTagPainterPathText=self.calcWayTagPlacement(wayPainterPath, reverseRefs, tagPainterPath, tagPainterPathText, rectList)

                        if newTagPainterPath!=None:
                            painterPathDict[wayId]=(newTagPainterPath, newTagPainterPathText)

            for wayId, (tagPainterPath, tagPainterPathText) in painterPathDict.items():
                self.displayTextLabel(tagPainterPath, tagPainterPathText, brush, pen)
                                
    def displayWays(self):
        showCasing=self.map_zoom in range(OSMStyle.SHOW_CASING_START_ZOOM, 19)
        showStreetOverlays=self.map_zoom in range(OSMStyle.SHOW_STREET_OVERLAY_START_ZOOM, 19)
        
        # casing
        if showCasing==True:
            for way in self.otherWays:   
                _, tags, _, streetInfo, _, _, _, _, _,  _=way
                streetTypeId, oneway, roundabout, _, _=osmParserData.decodeStreetInfo2(streetInfo)
                pen=self.style.getRoadPen(streetTypeId, self.map_zoom, showCasing, False, True, False, False, False, tags)
                self.displayWayWithCache(way, pen)

        # fill
        for way in self.otherWays:   
            _, tags, _, streetInfo, _, _, _, _, _,  _=way
            streetTypeId, oneway, roundabout, _, _=osmParserData.decodeStreetInfo2(streetInfo)
            pen=self.style.getRoadPen(streetTypeId, self.map_zoom, False, False, False, False, False, False, tags)
            self.displayWayWithCache(way, pen)
            
            if showStreetOverlays==True: 
                if osmParserData.isAccessRestricted(tags):
                    pen=self.style.getRoadPen(streetTypeId, self.map_zoom, False, False, False, False, True, False, tags)
                    self.displayWayWithCache(way, pen)
            
                # TODO: mark oneway direction
                elif (oneway!=0 and roundabout==0) and streetTypeId in self.getStreetTypeListForOneway():
                    pen=self.style.getRoadPen(streetTypeId, self.map_zoom, False, True, False, False, False, False, tags)
                    self.displayWayWithCache(way, pen)
                
                elif streetTypeId==Constants.STREET_TYPE_LIVING_STREET:
                    pen=self.style.getRoadPen(streetTypeId, self.map_zoom, False, False, False, False, False, True, tags)
                    self.displayWayWithCache(way, pen)
 
    def displayBridgeWays(self):                    
        if len(self.bridgeWays)!=0:
            showStreetOverlays=self.map_zoom in range(OSMStyle.SHOW_STREET_OVERLAY_START_ZOOM, 19)
            showBridges=self.map_zoom in range(OSMStyle.SHOW_BRIDGES_START_ZOOM, 19)

            # bridges  
            for way in self.bridgeWays:
                _, tags, _, streetInfo, _, _, _, _, _,  _=way
                streetTypeId, _, _, _, _=osmParserData.decodeStreetInfo2(streetInfo)
                if showBridges==True:
                    pen=self.style.getRoadPen(streetTypeId, self.map_zoom, False, False, False, True, False, False, tags)
                    self.displayWayWithCache(way, pen)
    
                pen=self.style.getRoadPen(streetTypeId, self.map_zoom, False, False, False, False, False, False, tags)
                self.displayWayWithCache(way, pen)
                
                if showStreetOverlays==True: 
                    if osmParserData.isAccessRestricted(tags):
                        pen=self.style.getRoadPen(streetTypeId, self.map_zoom, False, False, False, False, True, False, tags)
                        self.displayWayWithCache(way, pen)
            
    def displayTunnelWays(self):                    
        showCasing=True
        if showCasing==True:
            for way in self.tunnelWays:   
                _, tags, _, streetInfo, _, _, _, _, _,  _=way
                streetTypeId, _, _, _, _=osmParserData.decodeStreetInfo2(streetInfo)
                pen=self.style.getRoadPen(streetTypeId, self.map_zoom, showCasing, False, True, False, False, False, tags)
                self.displayWayWithCache(way, pen)
        
        for way in self.tunnelWays:   
            _, tags, _, streetInfo, _, _, _, _, _,  _=way
            streetTypeId, _, _, _, _=osmParserData.decodeStreetInfo2(streetInfo)
            pen=self.style.getRoadPen(streetTypeId, self.map_zoom, False, False, True, False, False, False, tags)
            self.displayWayWithCache(way, pen)

    def getDisplayPOITypeListForZoom(self):
        return self.style.getDisplayPOIListForZoom(self.map_zoom)
    
    def getPixmapForNodeType(self, nodeType):
        return self.style.getPixmapForNodeType(nodeType)
    
    def getPixmapSizeForZoom(self, baseWidth, baseHeight):
        if self.isVirtualZoom==True:
            return (int(baseWidth*self.virtualZoomValue), int(baseHeight*self.virtualZoomValue))
        
        if self.map_zoom==18:
            return (int(baseWidth*1.5), int(baseHeight*1.5))
        elif self.map_zoom==17:
            return (baseWidth, baseHeight)

        return (int(baseWidth*0.8), int(baseHeight*0.8))
    
    # sort by y value        
    def nodeSortByYCoordinate(self, item):
        return item[1]
    
    def getNodeInfoForPos(self, pos):
        pixmapWidth, pixmapHeight=self.getPixmapSizeForZoom(IMAGE_WIDTH_SMALL, IMAGE_HEIGHT_SMALL)

        for  x, y, pixmapWidth, pixmapHeight, refId, tags, _, _ in self.orderedNodeList:
            rect=QRect(int(x-pixmapWidth/2), int(y-pixmapHeight), pixmapWidth, pixmapHeight)
            if rect.contains(pos, proper=False):
                return refId, tags
        
        return None, None
    
    # for debugging
    def getAreaTagsForPos(self, pos):
        # the polygons are transformed
        point0=self.transformHeading.inverted()[0].map(pos)
        map_x, map_y=self.getMapZeroPos()
        
        for osmId, (_, painterPath, geomType) in self.areaPolygonCache.items():
            if geomType==0:
                painterPath=painterPath.translated(-map_x, -map_y)
                if painterPath.contains(point0):                    
                    tags=osmParserData.getAreaTagsWithId(osmId)
                    if tags!=None:
                        print("%d %s"%(osmId, tags))
        
    def event(self, event):
        if event.type()==QEvent.ToolTip:
            mousePos=QPoint(event.x(), event.y())
            if self.sidebarVisible==True:
                if self.searchRect.contains(mousePos):
                    QToolTip.showText(event.globalPos(), "Search")
                    return True
                elif self.favoriteRect.contains(mousePos):
                    QToolTip.showText(event.globalPos(), "Select favorite")
                    return True
                elif self.routesRect.contains(mousePos):
                    QToolTip.showText(event.globalPos(), "Load route")
                    return True
                elif self.centerGPSRect.contains(mousePos):
                    QToolTip.showText(event.globalPos(), "Center map to GPS")
                    return True
                elif self.optionsRect.contains(mousePos):
                    QToolTip.showText(event.globalPos(), "Settings")
                    return True
                
            if self.sidebarControlRect.contains(mousePos):
                if self.sidebarVisible==True:
                    QToolTip.showText(event.globalPos(), "Hide toolbar")
                    return True
                else:
                    QToolTip.showText(event.globalPos(), "Show toolbar")
                    return True
            
            if self.plusRect.contains(mousePos):
                QToolTip.showText(event.globalPos(), "+ Zoom %d"%(self.map_zoom))
                return True

            if self.minusRect.contains(mousePos):
                QToolTip.showText(event.globalPos(), "- Zoom %d"%(self.map_zoom))
                return True
                
            refId, tags=self.getNodeInfoForPos(mousePos)
            if tags!=None:
                if self.osmWidget.test==True:
                    displayString="%s:%d"%(osmParserData.getPOITagString(tags), refId)
                else:
                    displayString=osmParserData.getPOITagString(tags)
                   
                QToolTip.showText(event.globalPos(), displayString)
                    
            else:
                QToolTip.hideText()
                event.ignore()
                
            return True
        
        return super(QtOSMWidget, self).event(event)

    
    def displayVisibleNodes(self, bbox):        
        nodeTypeList=self.getDisplayPOITypeListForZoom()
        if nodeTypeList==None or len(nodeTypeList)==0:
            return
        
        start=time.time()
        resultList=osmParserData.getPOINodesInBBoxWithGeom(bbox, 0.0, nodeTypeList)        
        
        if WITH_TIMING_DEBUG==True:
            print("getPOINodesInBBoxWithGeom: %f"%(time.time()-start))

        pixmapWidth, pixmapHeight=self.getPixmapSizeForZoom(IMAGE_WIDTH_SMALL, IMAGE_HEIGHT_SMALL)
        
        numVisibleNodes=0
        numHiddenNodes=0
        
        for node in resultList:
            refId, lat, lon, tags, nodeType=node
            (y, x)=self.getTransformedPixelPosForLocationDeg(lat, lon)
            if self.isPointVisibleTransformed(x, y):  
                self.orderedNodeList.append((x, y, pixmapWidth, pixmapHeight, refId, tags, nodeType, None))
                numVisibleNodes=numVisibleNodes+1
            else:
                numHiddenNodes=numHiddenNodes+1
        
        if WITH_TIMING_DEBUG==True:
            print("visible nodes: %d hidden nodes:%d"%(numVisibleNodes, numHiddenNodes))
          
    def displayNodes(self):
        start=time.time()
        
        for  x, y, pixmapWidth, pixmapHeight, refId, tags, nodeType, pixmap in self.orderedNodeList:
            if pixmap==None:
                self.displayNode(x, y, pixmapWidth, pixmapHeight, refId, tags, nodeType)
            else:
                self.painter.drawPixmap(int(x-pixmapWidth/2), int(y-pixmapHeight), pixmapWidth, pixmapHeight, pixmap)

        if WITH_TIMING_DEBUG==True:
            print("displayNodes: %f"%(time.time()-start))
            
    def displayNode(self, x, y, pixmapWidth, pixmapHeight, refId, tags, nodeType):
        if nodeType==Constants.POI_TYPE_PLACE:
            if "name" in tags:
#                print("%d %s"%(refId, tags))
                text=tags["name"]
                placeType=tags["place"]
                
                if self.style.displayPlaceTypeForZoom(placeType, self.map_zoom):
                    font=self.style.getFontForPlaceTagDisplay(tags, self.map_zoom, self.isVirtualZoom)
                    if font!=None:
                        painterPath, painterPathText=self.createTextLabel(text, font)
                        painterPath, painterPathText=self.moveTextLabelToPos(x, y, painterPath, painterPathText)
                        self.displayTextLabel(painterPath, painterPathText, self.style.getStyleBrush("placeTag"), self.style.getStylePen("placePen"))
            return
                
        if nodeType==Constants.POI_TYPE_MOTORWAY_JUNCTION:
            if "name" in tags:
                text=tags["name"]
                if "ref" in tags:
                    ref=tags["ref"]
                    text="%s:%s"%(text, ref)
                                    
                font=self.style.getFontForTextDisplay(self.map_zoom, self.isVirtualZoom)
                if font!=None:
                    painterPath, painterPathText=self.createTextLabel(text, font)
                    painterPath, painterPathText=self.moveTextLabelToPos(x, y, painterPath, painterPathText)
                    self.displayTextLabel(painterPath, painterPathText, self.style.getStyleBrush("placeTag"), self.style.getStylePen("placePen"))
            return

        pixmap=self.getPixmapForNodeType(nodeType)
        if pixmap!=None:
            xPos=int(x-pixmapWidth/2)
            yPos=int(y-pixmapHeight)
            self.painter.drawPixmap(xPos, yPos, pixmapWidth, pixmapHeight, self.getPixmapForNodeType(nodeType))

    def moveTextLabelToPos(self, x, y, painterPath, painterPathText):
        xPosRect=x-painterPath.boundingRect().width()/2
        yPosRect=y-painterPath.boundingRect().height()

        painterPath=painterPath.translated(xPosRect, yPosRect)
        painterPathText=painterPathText.translated(xPosRect, yPosRect)
        
        return painterPath, painterPathText

    def createTextLabel(self, text, font):
        fm = QFontMetrics(font)
        width=fm.width(text)+10
        height=fm.height()
        arrowHeight=10
        arrowWidth=5
        
        painterPath=QPainterPath()
        
        painterPath.moveTo(QPointF(0, 0))
        painterPath.lineTo(QPointF(width, 0))
        painterPath.lineTo(QPointF(width, height))
        painterPath.lineTo(QPointF(width-width/2+arrowWidth, height))
        painterPath.lineTo(QPointF(width-width/2, height+arrowHeight))
        painterPath.lineTo(QPointF(width-width/2-arrowWidth, height))
        painterPath.lineTo(QPointF(0, height))
        painterPath.closeSubpath()
                
        painterPathText=QPainterPath()
        textPos=QPointF(5, height-fm.descent())
        painterPathText.addText(textPos, font, text)
        
        return painterPath, painterPathText
    
    # need to do it in two steps
    # not possible to get filled text else - only outlined
    def displayTextLabel(self, painterPath, painterPathText, brush, pen):
        self.painter.setPen(pen)
        self.painter.setBrush(brush)
        self.painter.drawPath(painterPath)

        self.painter.setPen(Qt.NoPen)
        self.painter.setBrush(QBrush(Qt.black))
        self.painter.drawPath(painterPathText)
           
    def getDisplayAreaTypeListForZoom(self):
        if self.map_zoom in range(self.tileStartZoom+1, 19):
            return self.style.getDisplayAreaListForZoom(self.map_zoom)

        return None

    def getVisibleAreas(self, bbox):
        areaTypeList=self.getDisplayAreaTypeListForZoom()
        if areaTypeList==None or len(areaTypeList)==0:
            return
        
        start=time.time()
        if self.map_zoom>=14:
            resultList, osmIdSet=osmParserData.getAreasInBboxWithGeom(areaTypeList, bbox, 0.0)
        elif self.map_zoom>=12:
            resultList, osmIdSet=osmParserData.getAreasInBboxWithGeom(areaTypeList, bbox, 0.0, True, 50.0)
        elif self.map_zoom>=10:
            resultList, osmIdSet=osmParserData.getAreasInBboxWithGeom(areaTypeList, bbox, 0.0, True, 100.0)
        
        if WITH_TIMING_DEBUG==True:
            print("getAreasInBboxWithGeom: %f"%(time.time()-start))

        if self.lastOsmIdSet==None:
            self.lastOsmIdSet=osmIdSet
        else:
            removedAreas=self.lastOsmIdSet-osmIdSet
            self.lastOsmIdSet=osmIdSet
            
            for osmId in removedAreas:
                if osmId in self.areaPolygonCache.keys():
                    del self.areaPolygonCache[osmId]
           
        for area in resultList:
            osmId, areaType, tags, _, _, _=area
                
            bridge="bridge" in tags and tags["bridge"]=="yes"
            tunnel="tunnel" in tags and tags["tunnel"]=="yes"
               
            if areaType==Constants.AREA_TYPE_RAILWAY:
                if tags["railway"]=="rail":
                    if bridge==True:
                        self.railwayBridgeLines.append(area)
                        continue
                    
                    if tunnel==True:
                        self.railwayTunnelLines.append(area)
                        continue
                    
                    self.railwayLines.append(area)
                    continue
                
            if areaType==Constants.AREA_TYPE_NATURAL:
                if tunnel==True:
                    self.naturalTunnelLines.append(area)
                    continue
                
            if areaType==Constants.AREA_TYPE_BUILDING:
                self.buildingList.append(area)
                continue
            
            if areaType==Constants.AREA_TYPE_AEROWAY:
                if tags["aeroway"]=="runway" or tags["aeroway"]=="taxiway":
                    self.aerowayLines.append(area)
                    continue
                
            self.areaList.append(area)
               
    def displayTunnelNatural(self):
        if len(self.naturalTunnelLines)!=0:   
            brush=Qt.NoBrush
        
            for area in self.naturalTunnelLines:
                tags=area[2]
                if "waterway" in tags:         
                    pen=self.style.getStylePen("waterwayTunnelPen")
                    pen.setWidth(self.style.getWaterwayPenWidthForZoom(self.map_zoom, tags))                      
                    self.displayPolygonWithCache(self.areaPolygonCache, area, pen, brush)
        
    def displayAreas(self):           
        for area in self.areaList:
            areaType=area[1]
            tags=area[2]
            brush=Qt.NoBrush
            pen=Qt.NoPen

            if areaType==Constants.AREA_TYPE_LANDUSE:
                brush, pen=self.style.getBrushForLanduseArea(tags, self.map_zoom)

            elif areaType==Constants.AREA_TYPE_NATURAL:
                brush, pen=self.style.getBrushForNaturalArea(tags, self.map_zoom)
                # TODO: natural areas with landuse
                if "landuse" in tags:
                    landuseBrush, landusePen=self.style.getBrushForLanduseArea(tags, self.map_zoom)
                    self.displayPolygonWithCache(self.areaPolygonCache, area, landusePen, landuseBrush)
            
            elif areaType==Constants.AREA_TYPE_HIGHWAY_AREA:
                brush=self.style.getStyleBrush("highwayArea")
                            
            elif areaType==Constants.AREA_TYPE_AEROWAY:
                brush=self.style.getStyleBrush("aerowayArea")
                
            elif areaType==Constants.AREA_TYPE_TOURISM:
                brush, pen=self.style.getBrushForTourismArea(tags, self.map_zoom)

            elif areaType==Constants.AREA_TYPE_AMENITY:
                brush, pen=self.style.getBrushForAmenityArea(tags, self.map_zoom)
            
            elif areaType==Constants.AREA_TYPE_LEISURE:
                brush, pen=self.style.getBrushForLeisureArea(tags, self.map_zoom) 
                             
            else:
                continue
            
            self.displayPolygonWithCache(self.areaPolygonCache, area, pen, brush)

        self.painter.setBrush(Qt.NoBrush)

    def displayBuildings(self):  
        if len(self.buildingList)!=0:    
            pen=Qt.NoPen
            
            for area in self.buildingList:      
                brush=self.style.getStyleBrush("building")
                self.displayPolygonWithCache(self.areaPolygonCache, area, pen, brush)
    
            self.painter.setBrush(Qt.NoBrush)
            
    def displayBridgeRailways(self):
        if len(self.railwayBridgeLines)!=0:
            brush=Qt.NoBrush
            showBridges=self.map_zoom in range(OSMStyle.SHOW_BRIDGES_START_ZOOM, 19)
     
            for area in self.railwayBridgeLines:
                tags=area[2]

                width=self.style.getRailwayPenWidthForZoom(self.map_zoom, tags)
                if showBridges==True:
                    pen=self.style.getStylePen("railwayBridge")
                    pen.setWidth(width+4)                        
                    self.displayPolygonWithCache(self.areaPolygonCache, area, pen, brush)
                
                pen=self.style.getStylePen("railway")
                pen.setWidth(width)                        
                self.displayPolygonWithCache(self.areaPolygonCache, area, pen, brush)

    def displayTunnelRailways(self):
        if len(self.railwayTunnelLines)!=0:
            brush=Qt.NoBrush
     
            for area in self.railwayTunnelLines:
                tags=area[2]

                width=self.style.getRailwayPenWidthForZoom(self.map_zoom, tags)
                pen=self.style.getStylePen("railwayTunnel")
                pen.setWidth(width+2)                        
                self.displayPolygonWithCache(self.areaPolygonCache, area, pen, brush)
            
    def displayRailways(self):
        if len(self.railwayLines)!=0:
            brush=Qt.NoBrush
     
            for area in self.railwayLines:
                tags=area[2]

                width=self.style.getRailwayPenWidthForZoom(self.map_zoom, tags)
                pen=self.style.getStylePen("railway")
                pen.setWidth(width)                        
                self.displayPolygonWithCache(self.areaPolygonCache, area, pen, brush)

    def displayAeroways(self):
        if len(self.aerowayLines)!=0:    
            brush=Qt.NoBrush
            
            for area in self.aerowayLines:
                tags=area[2]
                
                pen=self.style.getStylePen("aeroway")
                pen.setWidth(self.style.getAerowayPenWidthForZoom(self.map_zoom, tags))                                     
                self.displayPolygonWithCache(self.areaPolygonCache, area, pen, brush)

    
    def getAdminBoundaries(self, lat, lon):
        resultList=osmParserData.getAdminAreasOnPointWithGeom(lat, lon, 0.0, Constants.ADMIN_LEVEL_SET, True)
        resultList.reverse()

        for area in resultList:
            tags=area[1]
            print(tags)

    def showTextInfoBackground(self):
        textBackground=QRect(0, self.height()-50, self.width()-self.getSidebarWidth(), 50)
        self.painter.fillRect(textBackground, self.style.getStyleColor("backgroundColor"))
        
        if self.currentRoute!=None and self.currentTrackList!=None and not self.currentRoute.isRouteFinished():
            routeInfoBackground=QRect(self.width()-100-self.getSidebarWidth(), self.height()-50-200, 100, 200)
            self.painter.fillRect(routeInfoBackground, self.style.getStyleColor("backgroundColor"))
            
    def showTextInfo(self):
        if self.wayInfo!=None:
            pen=self.style.getStylePen("textPen")
            self.painter.setPen(pen) 
            font=self.style.getStyleFont("wayInfoFont")
            self.painter.setFont(font)
            
            wayPos=QPoint(5, self.height()-15)
            self.painter.drawText(wayPos, self.wayInfo)
                    
    def getDistanceString(self, value):
        if value>10000:
            valueStr="%dkm"%(int(value/1000))
        elif value>500:
            valueStr="%.1fkm"%(value/1000)
        else:
            valueStr="%dm"%value
        
        return valueStr

    def displayRouteInfo(self):
        pen=self.style.getStylePen("textPen")
        self.painter.setPen(pen)

        font=self.style.getStyleFont("monoFont")
        self.painter.setFont(font)
        fm = self.painter.fontMetrics();

        distanceToEndStr=self.getDistanceString(self.distanceToEnd)
        distanceToEndPos=QPoint(self.width()-self.getSidebarWidth()-fm.width(distanceToEndStr)-2, self.height()-50-100-100+fm.height()+2)
        self.painter.drawText(distanceToEndPos, "%s"%distanceToEndStr)
        self.painter.drawPixmap(self.width()-self.getSidebarWidth()-100, self.height()-50-100-100+2, IMAGE_WIDTH_TINY, IMAGE_HEIGHT_TINY, self.style.getStylePixmap("finishPixmap"))

        crossingLengthStr=self.getDistanceString(self.distanceToCrossing)
        crossingDistancePos=QPoint(self.width()-self.getSidebarWidth()-fm.width(crossingLengthStr)-2, self.height()-50-100-100+2*(fm.height())+2)
        self.painter.drawText(crossingDistancePos, "%s"%crossingLengthStr)
        self.painter.drawPixmap(self.width()-self.getSidebarWidth()-100, self.height()-50-100-100+2+fm.height()+2, IMAGE_WIDTH_TINY, IMAGE_HEIGHT_TINY, self.style.getStylePixmap("crossingPixmap"))

        font=self.style.getStyleFont("wayInfoFont")
        self.painter.setFont(font)
        fm = self.painter.fontMetrics();
        
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
                crossingInfoStr="Continue "+crossingInfoStr[len("stay:"):]
            elif "change:" in crossingInfo:
                crossingInfoStr="Change "+crossingInfoStr[len("change:"):]
            elif "roundabout:enter:" in crossingInfo:
                crossingInfoStr="Enter roundabout. Take exit %d"%(exitNumber)
            elif "roundabout:exit:" in crossingInfo:
                crossingInfoStr="Exit roundabout at %d"%(exitNumber)
            elif "motorway:exit:info:" in crossingInfo:
                crossingInfoStr="Take motorway exit "+crossingInfoStr[len("motorway:exit:info:"):]
            elif "motorway:exit" in crossingInfo:
                crossingInfoStr="Take motorway exit"
            elif crossingInfo=="end":
                crossingInfoStr=""
            
            routeInfoPos1=QPoint(self.width()-self.getSidebarWidth()-fm.width(crossingInfoStr)-10, self.height()-15)
            self.painter.drawText(routeInfoPos1, "%s"%(crossingInfoStr))
                            
            x=self.width()-self.getSidebarWidth()-92
            y=self.height()-50-100+10
            self.displayRouteDirectionImage(direction, exitNumber, IMAGE_WIDTH_LARGE, IMAGE_HEIGHT_LARGE, x, y) 
     
     
    def showEnforcementInfo(self):   
        if self.wayPOIList!=None and len(self.wayPOIList)>=1:  
            nodeType=self.wayPOIList[0]
                   
            wayPOIBackground=QRect(0, self.height()-50-100-100, 100, 100)
            self.painter.fillRect(wayPOIBackground, self.style.getStyleColor("warningBackgroundColor"))
            x=8
            y=self.height()-50-100-100+10
            self.painter.drawPixmap(x, y, IMAGE_WIDTH_LARGE, IMAGE_HEIGHT_LARGE, self.style.getPixmapForNodeType(nodeType))

    def showSpeedInfo(self):   
        if self.speedInfo!=None and self.speedInfo!=0:
            x=8
            y=self.height()-50-100+10
            
            speedBackground=QRect(0, self.height()-50-100, 100, 100)
            # show if speed is larger then maxspeed + 10%
            if self.speed!=None and self.drivingMode==True and self.speed>self.speedInfo*1.1:
                self.painter.fillRect(speedBackground, self.style.getStyleColor("warningBackgroundColor"))
            else:
                self.painter.fillRect(speedBackground, self.style.getStyleColor("backgroundColor"))

            imagePath=os.path.join(getImageRoot(), "speedsigns", "%d.png"%(self.speedInfo))
            if os.path.exists(imagePath):
                speedPixmap=QPixmap(imagePath)
                self.painter.drawPixmap(x, y, IMAGE_WIDTH_LARGE, IMAGE_HEIGHT_LARGE, speedPixmap)
                
    def showTunnelInfo(self):
        if self.osmWidget.isInTunnel==True:
            y=self.height()-50-100-100-100+10
            x=8
            
            tunnelBackground=QRect(0, self.height()-50-100-100-100, 100, 100)
            self.painter.fillRect(tunnelBackground, self.style.getStyleColor("backgroundColor"))
            
            self.painter.drawPixmap(x, y, IMAGE_WIDTH_LARGE, IMAGE_HEIGHT_LARGE, self.style.getStylePixmap("tunnelPixmap"))
            
    def displayRoutingPointRefPositions(self, point):
        if not point.isValid():
            return
        
        y,x=self.getTransformedPixelPosForLocationDeg(point.getClosestRefPos()[0], point.getClosestRefPos()[1])        
        pen=QPen()
        pen.setColor(Qt.green)
        pen.setWidth(self.style.getPenWithForPoints(self.map_zoom))  
        pen.setCapStyle(Qt.RoundCap)
        self.painter.setPen(pen)
        self.painter.drawPoint(x, y)

    def displayRoutingPoints(self):
        pixmapWidth, pixmapHeight=self.getPixmapSizeForZoom(IMAGE_WIDTH_MEDIUM, IMAGE_HEIGHT_MEDIUM)

        if self.startPoint!=None:
            (y, x)=self.getTransformedPixelPosForLocationDeg(self.startPoint.getPos()[0], self.startPoint.getPos()[1])
            if self.isPointVisibleTransformed(x, y):
                self.orderedNodeList.append((x, y, pixmapWidth, pixmapHeight, None, None, None, self.style.getStylePixmap("startPixmap")))
                self.displayRoutingPointRefPositions(self.startPoint)

        if self.endPoint!=None:
            (y, x)=self.getTransformedPixelPosForLocationDeg(self.endPoint.getPos()[0], self.endPoint.getPos()[1])
            if self.isPointVisibleTransformed(x, y):
                self.orderedNodeList.append((x, y, pixmapWidth, pixmapHeight, None, None, None, self.style.getStylePixmap("finishPixmap")))
                self.displayRoutingPointRefPositions(self.endPoint)
            
        for point in self.wayPoints:
            (y, x)=self.getTransformedPixelPosForLocationDeg(point.getPos()[0], point.getPos()[1])
            if self.isPointVisibleTransformed(x, y):
                self.orderedNodeList.append((x, y, pixmapWidth, pixmapHeight, None, None, None, self.style.getStylePixmap("wayPixmap")))
                self.displayRoutingPointRefPositions(point)
            
    
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
        polygon=QPolygonF()
        
        map_x, map_y=self.getMapZeroPos()
        displayCoords=coords

#        if self.map_zoom<15:
#            if len(coords)>6:
#                displayCoords=coords[1:-2:2]
#                displayCoords[0]=coords[0]
#                displayCoords[-1]=coords[-1]
            
        for point in displayCoords:
            lat, lon=point 
            (y, x)=self.getPixelPosForLocationDeg(lat, lon, False)
            point=QPointF(x, y);
            polygon.append( point )
            
        polygon.translate(-map_x, -map_y)
               
        self.painter.setPen(pen)
        self.painter.drawPolyline(polygon)

    def displayWayWithCache(self, way, pen):        
        cPolygon=None
        painterPath=None
        wayId=way[0]
        coordsStr=way[9]
        map_x, map_y=self.getMapZeroPos()
        
        if not wayId in self.wayPolygonCache.keys():
            painterPath=QPainterPath()

            coords=self.gisUtils.createCoordsFromLineString(coordsStr)
                
            i=0
            for point in coords:
                lat, lon=point 
                (y, x)=self.getPixelPosForLocationDeg(lat, lon, False)
                point=QPointF(x, y);
                if i==0:
                    painterPath.moveTo(point)
                else:
                    painterPath.lineTo(point)
                    
                i=i+1
                
            rect=painterPath.controlPointRect()
            cont=[(rect.x(), rect.y()), 
                  (rect.x()+rect.width(), rect.y()), 
                  (rect.x()+rect.width(), rect.y()+rect.height()), 
                  (rect.x(), rect.y()+rect.height())]

            cPolygon=Polygon(cont)

            self.wayPolygonCache[wayId]=(cPolygon, painterPath)
        
        else:
            cPolygon, painterPath=self.wayPolygonCache[wayId]
                    
        if cPolygon!=None:
            # must create a copy cause shift changes alues intern
            p=Polygon(cPolygon)
            p.shift(-map_x, -map_y)
            if not self.visibleCPolygon.overlaps(p):
                self.numHiddenWays=self.numHiddenWays+1
                return 
                    
        self.numVisibleWays=self.numVisibleWays+1

        painterPath=painterPath.translated(-map_x, -map_y)
        self.painter.strokePath(painterPath, pen)
                              
    def displayPolygonWithCache(self, cacheDict, area, pen, brush):        
        cPolygon=None
        painterPath=None
        osmId=area[0]
        polyStr=area[4]
        geomType=area[5]
        map_x, map_y=self.getMapZeroPos()
        
        if not osmId in cacheDict.keys():
            painterPath=QPainterPath()
            coordsList=list()
            if geomType==0:
                coordsList=self.gisUtils.createCoordsFromPolygonString(polyStr)
            else:
                coords=self.gisUtils.createCoordsFromLineString(polyStr)     
                coordsList.append((coords, list()))
            
            for outerCoords, _ in coordsList:
                i=0
                for point in outerCoords:
                    lat, lon=point 
                    (y, x)=self.getPixelPosForLocationDeg(lat, lon, False)
                    point=QPointF(x, y);
                    if i==0:
                        painterPath.moveTo(point)
                    else:
                        painterPath.lineTo(point)
                        
                    i=i+1

            if geomType==0:
                painterPath.closeSubpath()
            
            rect=painterPath.controlPointRect()
            cont=[(rect.x(), rect.y()), 
                  (rect.x()+rect.width(), rect.y()), 
                  (rect.x()+rect.width(), rect.y()+rect.height()), 
                  (rect.x(), rect.y()+rect.height())]

            cPolygon=Polygon(cont)
            
            if geomType==0:
                for _, innerCoordsList in coordsList:
                    for innerCoords in innerCoordsList:
                        innerPainterPath=QPainterPath()
                        i=0
                        for point in innerCoords:
                            lat, lon=point 
                            (y, x)=self.getPixelPosForLocationDeg(lat, lon, False)
                            point=QPointF(x, y);
                            if i==0:
                                innerPainterPath.moveTo(point)
                            else:
                                innerPainterPath.lineTo(point)
                                
                            i=i+1
                        
                        innerPainterPath.closeSubpath()
                        painterPath=painterPath.subtracted(innerPainterPath)

            cacheDict[osmId]=(cPolygon, painterPath, geomType)
        
        else:
            cPolygon, painterPath, _=cacheDict[osmId]
        
        if cPolygon!=None:
            # must create a copy cause shift changes values intern
            p=Polygon(cPolygon)
            p.shift(-map_x, -map_y)
            if not self.visibleCPolygon.overlaps(p):
                self.numHiddenPolygons=self.numHiddenPolygons+1
                return 
        
        self.numVisiblePolygons=self.numVisiblePolygons+1
        
        painterPath=painterPath.translated(-map_x, -map_y)
        self.painter.setBrush(brush)
        self.painter.setPen(pen)
        
        if geomType==0:
            self.painter.drawPath(painterPath)
        else:
            # TODO: building as linestring 100155254
            if pen!=Qt.NoPen:
                self.painter.strokePath(painterPath, pen)
    
    def displayAdminLineWithCache(self, line, pen):        
        cPolygon=None
        painterPath=None
        lineId=line[0]
        coordsStr=line[2]
        map_x, map_y=self.getMapZeroPos()
        
        if not lineId in self.adminPolygonCache.keys():
            painterPath=QPainterPath()

            coords=self.gisUtils.createCoordsFromLineString(coordsStr)
                
            i=0
            for point in coords:
                lat, lon=point 
                (y, x)=self.getPixelPosForLocationDeg(lat, lon, False)
                point=QPointF(x, y);
                if i==0:
                    painterPath.moveTo(point)
                else:
                    painterPath.lineTo(point)
                    
                i=i+1
                
            rect=painterPath.controlPointRect()
            cont=[(rect.x(), rect.y()), 
                  (rect.x()+rect.width(), rect.y()), 
                  (rect.x()+rect.width(), rect.y()+rect.height()), 
                  (rect.x(), rect.y()+rect.height())]

            cPolygon=Polygon(cont)

            self.adminPolygonCache[lineId]=(cPolygon, painterPath)
        
        else:
            cPolygon, painterPath=self.adminPolygonCache[lineId]
                    
        if cPolygon!=None:
            # must create a copy cause shift changes alues intern
            p=Polygon(cPolygon)
            p.shift(-map_x, -map_y)
            if not self.visibleCPolygon.overlaps(p):
                self.numHiddenAdminLiness=self.numHiddenAdminLiness+1
                return 
                    
        self.numVisibleAdminLines=self.numVisibleAdminLines+1

        painterPath=painterPath.translated(-map_x, -map_y)
        self.painter.strokePath(painterPath, pen)
        
    def displayRouteOverlay(self, remainingTrackList, edgeIndexList):
        if remainingTrackList!=None:                        
            polygon=QPolygonF()

            for index in edgeIndexList:
                if index<len(remainingTrackList):
                    item=remainingTrackList[index]
                    
                    for itemRef in item["refs"]:
                        lat, lon=itemRef["coords"]   
                        (y, x)=self.getPixelPosForLocationDeg(lat, lon, True)
                        point=QPointF(x, y);
                        polygon.append( point )

            pen=self.style.getStylePen("routeOverlayPen")
            pen.setWidth(self.style.getStreetPenWidthForZoom(self.map_zoom))
            self.painter.setPen(pen)
            self.painter.drawPolyline(polygon)
        
    def displayRoute(self, route):
        if route!=None:
            # before calculation is done                        
            if not route.complete():
                return 
            
            showTrackDetails=self.map_zoom>13

            polygon=QPolygonF()
            routeInfo=route.getRouteInfo()
            for routeInfoEntry in routeInfo:
                if not "trackList" in routeInfoEntry:
                    return
                
                trackList=routeInfoEntry["trackList"]
                                                   
                for item in trackList:                
                    for itemRef in item["refs"]:
                        lat, lon=itemRef["coords"]
                            
                        (y, x)=self.getPixelPosForLocationDeg(lat, lon, True)
                        point=QPointF(x, y);
                        polygon.append(point)
                                
            pen=self.style.getStylePen("routePen")
            pen.setWidth(self.style.getStreetPenWidthForZoom(self.map_zoom))
            self.painter.setPen(pen)
            self.painter.drawPolyline(polygon)
                        
            if showTrackDetails==True:       
                for routeInfoEntry in routeInfo:                    
                    trackList=routeInfoEntry["trackList"]
                    
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
                            
            
    def displayRouteDirectionImage(self, direction, exitNumber, width, height, x, y):
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
            self.painter.drawPixmap(x, y, width, height, self.style.getStylePixmap("finishPixmap"))
            
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
        if gpsData==None:
            return 
                        
        if gpsData.isValid():    
            lat=gpsData.getLat()
            lon=gpsData.getLon()
            track=gpsData.getTrack()
            self.speed=gpsData.getSpeed()
            self.altitude=gpsData.getAltitude()
            self.satelitesInUse=gpsData.getSatelitesInUse()

            if debug==True:
                self.track=track

            if self.speed==0:
                self.stop=True
            else:
                self.stop=False
                # only set track when moving
                self.track=track

            firstGPSData=False
            if self.gps_rlat==0.0 and self.gps_rlon==0.0:
                firstGPSData=True
                
            gps_rlat_new=self.osmutils.deg2rad(lat)
            gps_rlon_new=self.osmutils.deg2rad(lon)
            
            if gps_rlat_new!=self.gps_rlat or gps_rlon_new!=self.gps_rlon:  
                
                #self.gpsUpdateStartTime=time.time()
                self.locationBreadCrumbs.append(gpsData)

                self.gps_rlat=gps_rlat_new
                self.gps_rlon=gps_rlon_new
                
                if gpsData.predicted==False or self.osmWidget.isInTunnel==True:
                    if debug==False:
                        self.showTrackOnGPSPos(False) 

                if self.drivingMode==True and self.autocenterGPS==True and (self.stop==False or firstGPSData==True):
                    self.osm_autocenter_map()
                else:
                    self.update()  
           
        else:
            self.gps_rlat=0.0
            self.gps_rlon=0.0
            self.stop=True
            self.track=None
            self.update()
        
    def cleanImageCache(self):
        self.tileCache.clear()
                        
    def callMapnikForTile(self, zoom, x, y):   
        if disableMappnik==False:
            self.osmWidget.mapnikThread.addTile(zoom, x, y)

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

        eventPos=QPoint(event.x(), event.y())
        if not self.moving:
            if self.sidebarVisible==True:
                if self.sidebarRect.contains(eventPos):
                    if self.searchRect.contains(eventPos):
                        self.osmWidget._showSearchMenu()
                    elif self.favoriteRect.contains(eventPos):
                        self.osmWidget._showFavorites()
                    elif self.routesRect.contains(eventPos):
                        self.osmWidget._loadRoute()
                    elif self.centerGPSRect.contains(eventPos):
                        self.osmWidget._centerGPS()
                    elif self.optionsRect.contains(eventPos):
                        self.osmWidget._showSettings()
                    return
                
            if self.sidebarControlRect.contains(eventPos):
                if self.sidebarVisible==True:
                    self.sidebarVisible=False
                else:
                    self.sidebarVisible=True
                self.update()
                return
            
            if self.minusRect.contains(eventPos) or self.plusRect.contains(eventPos):
                self.pointInsideZoomOverlay(event.x(), event.y())
                return
            
            self.lastMouseMoveX=event.x()
            self.lastMouseMoveY=event.y()
            self.showTrackOnMousePos(event.x(), event.y())
                
        else:
            self.moving=False


#    def pointInsideMoveOverlay(self, x, y):
#        if self.moveRect.contains(x, y):
#            if self.leftRect.contains(x, y):
#                self.stepLeft(MAP_SCROLL_STEP)
#            if self.rightRect.contains(x, y):
#                self.stepRight(MAP_SCROLL_STEP)
#            if self.upRect.contains(x, y):
#                self.stepUp(MAP_SCROLL_STEP)
#            if self.downRect.contains(x, y):
#                self.stepDown(MAP_SCROLL_STEP)
        
    def pointInsideZoomOverlay(self, x, y):
#        if self.zoomRect.contains(x, y):
            if self.minusRect.contains(x, y):
                if self.isVirtualZoom==True:
                    zoom=MAX_ZOOM
                    self.isVirtualZoom=False
                else:
                    zoom=self.map_zoom-1
                    if zoom<MIN_ZOOM:
                        zoom=MIN_ZOOM
                self.zoom(zoom)
                
            if self.plusRect.contains(x,y):
                zoom=self.map_zoom+1
                if zoom==MAX_ZOOM+1:
                    self.isVirtualZoom=True
                    zoom=MAX_ZOOM
                else:
                    if zoom>MAX_ZOOM:
                        zoom=MAX_ZOOM
                self.zoom(zoom)
        
#    def displayControlOverlay(self):
#        self.painter.drawPixmap(0, 0, self.osmControlImage)

    def displayControlOverlay2(self):
        minusBackground=QRect(0, 0, CONTROL_WIDTH, CONTROL_WIDTH)
        diff=CONTROL_WIDTH-IMAGE_WIDTH
        self.painter.fillRect(minusBackground, self.style.getStyleColor("backgroundColor"))
        self.minusRect=minusBackground
        self.painter.drawPixmap(diff/2, diff/2, IMAGE_WIDTH, IMAGE_HEIGHT, self.style.getStylePixmap("minusPixmap"))

        plusBackground=QRect(self.width()-self.getSidebarWidth()-CONTROL_WIDTH, 0, CONTROL_WIDTH, CONTROL_WIDTH)
        self.painter.fillRect(plusBackground, self.style.getStyleColor("backgroundColor"))
        self.plusRect=plusBackground
        self.painter.drawPixmap(self.width()-self.getSidebarWidth()-CONTROL_WIDTH+diff/2, diff/2, IMAGE_WIDTH, IMAGE_HEIGHT, self.style.getStylePixmap("plusPixmap"))

    def mousePressEvent(self, event):
        self.mousePressed=True
        self.lastMouseMoveX=event.x()
        self.lastMouseMoveY=event.y()
        self.mousePos=(event.x(), event.y())
            
    def mouseMoveEvent(self, event):
        if self.mousePressed==True:
            self.moving=True
            
            dx=self.lastMouseMoveX-event.x()
            dy=self.lastMouseMoveY-event.y()
            self.osm_map_scroll(dx, dy)
            self.lastMouseMoveX=event.x()
            self.lastMouseMoveY=event.y()
                    
    def getMapPointForPos(self, mousePos):
        p=QPoint(mousePos[0], mousePos[1])
        pixmapWidth, pixmapHeight=self.getPixmapSizeForZoom(IMAGE_WIDTH_MEDIUM, IMAGE_HEIGHT_MEDIUM)

        if self.startPoint!=None:
            (y, x)=self.getTransformedPixelPosForLocationDeg(self.startPoint.lat, self.startPoint.lon)
            rect=QRect(int(x-pixmapWidth/2), int(y-pixmapHeight), pixmapWidth, pixmapHeight)
            if rect.contains(p, proper=False):
                return self.startPoint

        if self.endPoint!=None:
            (y, x)=self.getTransformedPixelPosForLocationDeg(self.endPoint.lat, self.endPoint.lon)
            rect=QRect(int(x-pixmapWidth/2), int(y-pixmapHeight), pixmapWidth, pixmapHeight)
            if rect.contains(p, proper=False):
                return self.endPoint

        if self.mapPoint!=None:
            (y, x)=self.getTransformedPixelPosForLocationDeg(self.mapPoint.lat, self.mapPoint.lon)
            rect=QRect(int(x-pixmapWidth/2), int(y-pixmapHeight), pixmapWidth, pixmapHeight)
            if rect.contains(p, proper=False):
                return self.mapPoint

        for point in self.wayPoints:
            (y, x)=self.getTransformedPixelPosForLocationDeg(point.lat, point.lon)
            rect=QRect(int(x-pixmapWidth/2), int(y-pixmapHeight), pixmapWidth, pixmapHeight)
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
        clearAllMapPointsAction = QAction("Clear All Map Points", self)
        clearMapPointAction=QAction("Clear Map Point", self)
        editRoutingPointAction=QAction("Edit Current Route", self)
        saveRouteAction=QAction("Save Current Route", self)
        showRouteAction=QAction("Calc Route", self)
        clearRouteAction=QAction("Clear Current Route", self)
        gotoPosAction=QAction("Goto Position", self)
        showPosAction=QAction("Show Position", self)
        zoomToCompleteRoute=QAction("Zoom to Route", self)
        recalcRouteAction=QAction("Calc Route from here", self)
        recalcRouteGPSAction=QAction("Calc Route from GPS", self)
        
        routingPointSubMenu=QMenu(self)
        routingPointSubMenu.setTitle("Map Points")
        mapPointList=self.getMapPoints()
        mapPointMenuDisabled=len(mapPointList)==0
        for point in mapPointList:
            if point.getType()==OSMRoutingPoint.TYPE_MAP:
                routingPointSubMenu.addSeparator()
            pointAction=OSMRoutingPointAction(point.getName(), point, self.style, self)
            routingPointSubMenu.addAction(pointAction)

        routingPointSubMenu.setDisabled(mapPointMenuDisabled)

        googlePOIAction=QAction("Google this POI by name", self)
        showAdminHierarchy=QAction("Show Admin Info for here", self)
        showAreaTags=QAction("Show Area Info for here", self)
        showWayTags=QAction("Show Way Info", self)

        menu.addAction(forceDownloadAction)
        menu.addSeparator()
        menu.addAction(setStartPointAction)
        menu.addAction(setEndPointAction)
        menu.addAction(setWayPointAction)
        menu.addAction(addFavoriteAction)
        menu.addAction(gotoPosAction)
        menu.addAction(showPosAction)
        menu.addSeparator()
        menu.addAction(clearAllMapPointsAction)
        menu.addAction(clearMapPointAction)
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
        menu.addAction(googlePOIAction)
        menu.addAction(showAdminHierarchy)
        menu.addAction(showAreaTags)
        menu.addAction(showWayTags)

        routingPointList=self.getCompleteRoutingPoints()
        addPointDisabled=False
        routeIncomplete=routingPointList==None
        setStartPointAction.setDisabled(addPointDisabled)
        setEndPointAction.setDisabled(addPointDisabled)
        setWayPointAction.setDisabled(addPointDisabled)
        addFavoriteAction.setDisabled(addPointDisabled)
        showPosAction.setDisabled(addPointDisabled)
        gotoPosAction.setDisabled(addPointDisabled)
        saveRouteAction.setDisabled(routeIncomplete)
        clearMapPointAction.setDisabled(self.getMapPointForPos(self.mousePos)==None)
        clearAllMapPointsAction.setDisabled(mapPointMenuDisabled)
        editRoutingPointAction.setDisabled(routeIncomplete)
        zoomToCompleteRoute.setDisabled(routeIncomplete)
        clearRouteAction.setDisabled(self.currentRoute==None)
        showWayTags.setDisabled(self.lastWayId==None)
        
        showRouteDisabled=(self.routeCalculationThread!=None and self.routeCalculationThread.isRunning()) or routeIncomplete
        showRouteAction.setDisabled(showRouteDisabled)
        
        recalcRouteDisabled=(self.routeCalculationThread!=None and self.routeCalculationThread.isRunning()) or self.endPoint==None
        recalcRouteAction.setDisabled(recalcRouteDisabled)
        recalcRouteGPSAction.setDisabled(recalcRouteDisabled or self.gps_rlat==0.0 or self.gps_rlon==0.0)

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
        elif action==clearAllMapPointsAction:
            self.startPoint=None
            self.endPoint=None
            self.mapPoint=None
            self.wayPoints.clear()
        elif action==addFavoriteAction:
            self.addToFavorite(self.mousePos)
        elif action==clearMapPointAction:
            self.removeMapPoint(self.mousePos)
        elif action==editRoutingPointAction:
            self.editRoutingPoints()
        elif action==gotoPosAction:
            self.showPosOnMapDialog()
        elif action==showPosAction:
            (lat, lon)=self.getPosition(self.mousePos[0], self.mousePos[1])
            self.showMapPosDialog(lat, lon)
        elif action==saveRouteAction:
            self.saveCurrentRoute()
        elif action==zoomToCompleteRoute:
            self.zoomToCompleteRoute(self.getCompleteRoutingPoints())
        elif action==clearRouteAction:
            self.clearCurrentRoute()
        elif action==recalcRouteAction:
            (lat, lon)=self.getPosition(self.mousePos[0], self.mousePos[1])
            currentPoint=OSMRoutingPoint("tmp", OSMRoutingPoint.TYPE_START, (lat, lon))                
            currentPoint.resolveFromPos(osmParserData)
            if currentPoint.isValid():
                _, _, _, _, name, nameRef, _, _=osmParserData.getWayEntryForId(currentPoint.getWayId())
                defaultPointTag=osmParserData.getWayTagString(name, nameRef)
                currentPoint.name=defaultPointTag
                self.startPoint=currentPoint
                    
                self.showRouteForRoutingPoints(self.getCompleteRoutingPoints())
            else:
                self.showError("Error", "Route has invalid routing points")

        elif action==recalcRouteGPSAction:
            lat=self.osmutils.rad2deg(self.gps_rlat)
            lon=self.osmutils.rad2deg(self.gps_rlon)
            gpsPoint=OSMRoutingPoint("gps", OSMRoutingPoint.TYPE_START, (lat, lon))
            gpsPoint.resolveFromPos(osmParserData)
            if gpsPoint.isValid():
                _, _, _, _, name, nameRef, _, _=osmParserData.getWayEntryForId(gpsPoint.getWayId())
                defaultPointTag=osmParserData.getWayTagString(name, nameRef)
                gpsPoint.name=defaultPointTag
                self.startPoint=gpsPoint
                self.showRouteForRoutingPoints(self.getCompleteRoutingPoints())
            else:
                self.showError("Error", "Route has invalid routing points")
                
        elif action==showAdminHierarchy:
            (lat, lon)=self.getPosition(self.mousePos[0], self.mousePos[1])
            self.getAdminBoundaries(lat, lon)
        elif action==showAreaTags:
            pos=QPointF(self.mousePos[0], self.mousePos[1])
            self.getAreaTagsForPos(pos)
        elif action==showWayTags:
            print(osmParserData.getWayEntryForId(self.lastWayId))
            print(osmParserData.getEdgeEntryForId(self.selectedEdgeId))
            osmParserData.printCrossingsForWayId(self.lastWayId)
            restrictionList=osmParserData.getRestrictionEntryForTargetEdge(self.selectedEdgeId)
            if len(restrictionList)!=0:
                for restriction in restrictionList:
                    restrictionId, toEdgeId, viaEdgePath, toCost, osmId=restriction
                    print(restriction)
                    print(osmParserData.resolveRestriction(restriction))
        elif action==googlePOIAction:
            pos=QPoint(self.mousePos[0], self.mousePos[1])
            refId, tags=self.getNodeInfoForPos(pos)
            if tags!=None:
                searchString=osmParserData.getPOITagString(tags)
                if "addr:street" in tags:
                    searchString=searchString+" "+tags["addr:street"]
                QDesktopServices.openUrl(QUrl("http://www.google.com/search?q=%s"%(searchString), QUrl.TolerantMode))

        else:
            if isinstance(action, OSMRoutingPointAction):
                routingPoint=action.getRoutingPoint()
                self.showPointOnMap(routingPoint)
            
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
#                    print(zoom)
                    if zoom!=self.map_zoom:
                        self.osm_map_set_zoom(zoom)
                    
                    if self.withMapRotation==True:
                        y,_=self.getPixelPosForLocationDeg(centerLat, centerLon, False)
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

    def showPosOnMapDialog(self):
        posDialog=OSMPositionDialog(self)
        result=posDialog.exec()
        if result==QDialog.Accepted:
            lat, lon=posDialog.getResult()

            if self.map_zoom<15:
                self.osm_map_set_zoom(15)
    
            self.osm_center_map_to_position(lat, lon)

    def showMapPosDialog(self, lat, lon):
        posDialog=OSMPositionDialog(self, lat, lon)
        posDialog.exec()

    def getCompleteRoutingPoints(self):
        if self.startPoint==None or self.endPoint==None:
            return None
        
        routingPointList=list()
        routingPointList.append(self.startPoint)
        if len(self.wayPoints)!=0:
            routingPointList.extend(self.wayPoints)
        routingPointList.append(self.endPoint)
        return routingPointList

    def getMapPoints(self):        
        routingPointList=list()
        
        if self.startPoint!=None:
            routingPointList.append(self.startPoint)
                    
        if self.wayPoints!=None and len(self.wayPoints)!=0:
            routingPointList.extend(self.wayPoints)
        
        if self.endPoint!=None:
            routingPointList.append(self.endPoint)
            
        if self.mapPoint!=None:
            routingPointList.append(self.mapPoint)

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
            
    def removeMapPoint(self, mousePos):
        selectedPoint=self.getMapPointForPos(mousePos)
        if selectedPoint!=None:
            if selectedPoint==self.startPoint:
                self.startPoint=None
            elif selectedPoint==self.endPoint:
                self.endPoint=None
            elif selectedPoint==self.mapPoint:
                self.mapPoint=None
            else:
                for point in self.wayPoints:
                    if selectedPoint==point:
                        self.wayPoints.remove(selectedPoint)
    
    def addToFavorite(self, mousePos):
        (lat, lon)=self.getPosition(mousePos[0], mousePos[1])
        
        defaultPointTag=None
        edgeId, wayId=osmParserData.getEdgeIdOnPos(lat, lon, OSMRoutingPoint.DEFAULT_RESOLVE_POINT_MARGIN, OSMRoutingPoint.DEFAULT_RESOLVE_MAX_DISTANCE)
        if edgeId!=None:
            wayId, _, _, _, name, nameRef, _, _=osmParserData.getWayEntryForId(wayId)
            defaultPointTag=osmParserData.getWayTagString(name, nameRef)
        
        if defaultPointTag==None:
            defaultPointTag=""
            
        favNameDialog=OSMSaveFavoritesDialog(self, self.osmWidget.favoriteList, defaultPointTag)
        result=favNameDialog.exec()
        if result==QDialog.Accepted:
            favoriteName=favNameDialog.getResult()
            favoritePoint=OSMRoutingPoint(favoriteName, OSMRoutingPoint.TYPE_FAVORITE, (lat, lon))
            self.osmWidget.favoriteList.append(favoritePoint)

    def addRoutingPoint(self, pointType):
        (lat, lon)=self.getPosition(self.mousePos[0], self.mousePos[1])

        defaultPointTag=None
        edgeId, wayId=osmParserData.getEdgeIdOnPos(lat, lon, OSMRoutingPoint.DEFAULT_RESOLVE_POINT_MARGIN, OSMRoutingPoint.DEFAULT_RESOLVE_MAX_DISTANCE)
        if edgeId!=None:
            wayId, _, _, _, name, nameRef, _, _=osmParserData.getWayEntryForId(wayId)
            defaultPointTag=osmParserData.getWayTagString(name, nameRef)

        if pointType==0:
            if defaultPointTag!=None:
                defaultName=defaultPointTag
            else:
                defaultName="start"

            point=OSMRoutingPoint(defaultName, pointType, (lat, lon))
            point.resolveFromPos(osmParserData)
            self.startPoint=point
            if not point.isValid():
                self.showError("Error", "Failed to resolve way for start point")

        elif pointType==1:
            if defaultPointTag!=None:
                defaultName=defaultPointTag
            else:
                defaultName="end"
                
            point=OSMRoutingPoint(defaultName, pointType, (lat, lon))
            point.resolveFromPos(osmParserData)
            self.endPoint=point
            if not point.isValid():
                self.showError("Error", "Failed to resolve way for finish point")

        elif pointType==2:
            if defaultPointTag!=None:
                defaultName=defaultPointTag
            else:
                defaultName="way"

            wayPoint=OSMRoutingPoint(defaultName, pointType, (lat, lon))
            wayPoint.resolveFromPos(osmParserData)
            self.wayPoints.append(wayPoint)
            if not wayPoint.isValid():
                self.showError("Error", "Failed to resolve way for way point")
        
    def showPointOnMap(self, point):
        if self.drivingMode==False:
            if self.map_zoom<15:
                self.osm_map_set_zoom(15)
    
            self.osm_center_map_to_position(point.getPos()[0], point.getPos()[1])       
    
    def recalcRoute(self, lat, lon, edgeId):
        if self.routeCalculationThread!=None and self.routeCalculationThread.isRunning():
            return 
        
        recalcPoint=OSMRoutingPoint("tmp", OSMRoutingPoint.TYPE_TMP, (lat, lon))    
        recalcPoint.resolveFromPos(osmParserData)
        if not recalcPoint.isValid():
            return 
        
        if self.currentRoute!=None and not self.currentRoute.isRouteFinished():
            if self.routeCalculationThread!=None and not self.routeCalculationThread.isRunning():
                self.recalcRouteFromPoint(recalcPoint)
            
    def clearCurrent(self):
        self.currentCoords=None
        self.selectedEdgeId=None
        self.lastWayId=None
        self.speedInfo=None
        self.wayPOIList=None
        self.wayInfo=None
        
        self.distanceToCrossing=0
        self.nextEdgeOnRoute=None
        self.routeInfo=None, None, None, None
        
    def clearAll(self):
        self.clearCurrent()
        osmRouting.clearAll()
        
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
            
    def calcRouteDistances(self, lat, lon, initial=False):
        if initial==True:
            self.distanceToEnd=self.currentRoute.getAllLength()
            self.distanceToCrossing=0
            self.remainingTime=0
        else:
            distanceOnEdge=osmRouting.getDistanceToCrossing()
#            print(distanceOnEdge)
            self.distanceToEnd, self.distanceToCrossing=osmParserData.calcRouteDistances(self.currentTrackList, lat, lon, self.currentRoute, distanceOnEdge)
            self.remainingTime=osmParserData.calcRemainingDrivingTime(self.currentTrackList, lat, lon, self.currentRoute, distanceOnEdge, self.speed)
#            print(self.remainingTime)
        
    def showTrackOnPos(self, lat, lon, track, speed, update, fromMouse):
        # TODO:
        if self.routeCalculationThread!=None and self.routeCalculationThread.isRunning():
            return 
        
        edge=osmRouting.getEdgeIdOnPosForRouting(lat, lon, track, self.nextEdgeOnRoute, DEFAULT_SEARCH_MARGIN, fromMouse, speed)        
        if edge==None:
            self.clearCurrent()
        else:   
#            print(edge)
            edgeId=edge[0]
            startRef=edge[1]
            endRef=edge[2]
            length=edge[3]
            wayId=edge[4]
            coords=edge[10]
            
            self.currentCoords=coords
            self.selectedEdgeId=edgeId

            if self.drivingMode==True and self.currentRoute!=None and self.currentEdgeList!=None and not self.currentRoute.isRouteFinished():                                                                       
                if self.routingStarted==True:                    
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
                        if onRoute==False:
                            if self.recalcTrigger==3:
                                self.recalcTrigger=0
                                self.recalcRoute(lat, lon, edgeId)
                                return
                            else:
#                                self.recalcTrigger=self.recalcTrigger+1
#                                self.routeInfo=(98, "Please turn", 98, 0)
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
                            
                        if self.currentTargetPointReached(lat, lon):
                            self.currentRoute.targetPointReached(self.currentRoutePart)
                            self.switchToNextRoutePart()     
                            if self.currentRoute.isRouteFinished():
                                self.clearAll()
                                self.distanceToEnd=0.0
                                self.routingStarted=False
                                print("route finish")
                      
            if wayId!=self.lastWayId:
                self.lastWayId=wayId
                wayId, _, _, streetInfo, name, nameRef, maxspeed, _=osmParserData.getWayEntryForId(wayId)
                    
                self.wayInfo=osmParserData.getWayTagString(name, nameRef)  
                self.speedInfo=maxspeed
                self.wayPOIList=osmParserData.getPOIListOnWay(wayId)

                _, _, _, tunnel, _=osmParserData.decodeStreetInfo2(streetInfo)
                if tunnel==1 and track!=None and speed!=0 and length>MINIMAL_TUNNEL_LENGHTH:
                    self.osmWidget.startTunnelMode()
                else:
                    self.osmWidget.stopTunnelMode()
                    
#            stop=time.time()
#            print("showTrackOnPos:%f"%(stop-start))
        if update==True:
            self.update()
            
#    def calcTunnelData(self, edgeId, ref):
#        
#
#        tunnelSpeed=self.speed        
#        tunnelAltitude=self.altitude
#        tunnelTrack=self.track
#        tmpPointsFrac=tunnelSpeed/3.6
#
#        tunnelTrackLogLines=list()
#        tunnelEdgeList=osmParserData.getEdgesOfTunnel(edgeId, ref)
#        
#        heading=None
#        for tunnelEdgeData in tunnelEdgeList:
#            if "edge" in tunnelEdgeData:
#                edgeId=tunnelEdgeData["edge"]
#            if "startRef"in tunnelEdgeData:
#                startRef=tunnelEdgeData["startRef"]
#            if "endRef"in tunnelEdgeData:
#                endRef=tunnelEdgeData["endRef"]
#            if "heading"in tunnelEdgeData:
#                edgeHeading=tunnelEdgeData["heading"]
#            
#            # for now we cannot support crossings in tunnels so
#            # choose the path where the heading stays the same
#            if heading!=None and self.osmutils.headingDiffAbsolute(heading, edgeHeading)>10:
#                continue
#            
#            (edgeId, _, endRef, _, _, _, _, _, _, _, coords)=osmParserData.getEdgeEntryForEdgeIdWithCoords(edgeId)
#            if startRef==endRef:
#                coords.reverse()
#                
#            offsetOnNextEdge=0
#            lat1, lon1=coords[0]
#            for lat2, lon2 in coords[1:]:
#                distance=self.osmutils.distance(lat1, lon1, lat2, lon2)
#                heading=self.osmutils.headingDegrees(lat1, lon1, lat2, lon2)
#                
#                if distance>tmpPointsFrac:
#                    nodes=self.osmutils.createTemporaryPoints(lat1, lon1, lat2, lon2, frac=tmpPointsFrac, offsetStart=offsetOnNextEdge, offsetEnd=0.0, addStart=False, addEnd=False)
#                    for tmpLat, tmpLon in nodes:
#                        gpsData=GPSData(time.time(), tmpLat, tmpLon, heading, tunnelSpeed, tunnelAltitude)
#                        tunnelTrackLogLines.append(gpsData)
#                        
#                    # calc the offset in the next = remaining from last
#                    numberOfTmpPoints=int(distance/tmpPointsFrac)
#                    remainingOnEdge=distance-(numberOfTmpPoints*tmpPointsFrac)
#                    offsetOnNextEdge=int(tmpPointsFrac-remainingOnEdge)
#
#                else:
#                    gpsData=GPSData(time.time(), lat2, lon2, tunnelTrack, tunnelSpeed, tunnelAltitude)
#                    tunnelTrackLogLines.append(gpsData)
#                    
#                lat1=lat2
#                lon1=lon2
                            
    def showRouteForRoutingPoints(self, routingPointList):              
        # calculate
        self.currentRoute=OSMRoute("current", routingPointList)
        # make sure all are resolved because we cannot access
        # the db from the thread
        self.currentRoute.resolveRoutingPoints(osmParserData)
        
        if not self.currentRoute.isValid():
            self.showError("Error", "Route has invalid routing points")
            return

        self.routeCalculationThread=OSMRouteCalcWorker(self)
        self.connect(self.routeCalculationThread, SIGNAL("routeCalculationDone()"), self.routeCalculationDone)
        self.connect(self.routeCalculationThread, SIGNAL("updateStatus(QString)"), self.updateStatusLabel)
        self.connect(self.routeCalculationThread, SIGNAL("startProgress()"), self.startProgress)
        self.connect(self.routeCalculationThread, SIGNAL("stopProgress()"), self.stopProgress)

        self.routeRecalculated=False
        if not self.routeCalculationThread.isRunning():
            self.routeCalculationThread.setup(self.currentRoute)

    def recalcRouteFromPoint(self, currentPoint):
        # make sure all are resolved because we cannot access
        # the db from the thread
        self.currentRoute.changeRouteFromPoint(currentPoint, osmParserData)
        self.currentRoute.resolveRoutingPoints(osmParserData)
        if not self.currentRoute.isValid():
            self.showError("Error", "Route has invalid routing points")
            return
        
        self.routeCalculationThread=OSMRouteCalcWorker(self)
        self.connect(self.routeCalculationThread, SIGNAL("routeCalculationDone()"), self.routeCalculationDone)
        self.connect(self.routeCalculationThread, SIGNAL("updateStatus(QString)"), self.updateStatusLabel)
        self.connect(self.routeCalculationThread, SIGNAL("startProgress()"), self.startProgress)
        self.connect(self.routeCalculationThread, SIGNAL("stopProgress()"), self.stopProgress)

        self.routeRecalculated=True
        if not self.routeCalculationThread.isRunning():
            self.routeCalculationThread.setup(self.currentRoute)

    def startProgress(self):
        self.emit(SIGNAL("startProgress()"))

    def stopProgress(self):
        self.emit(SIGNAL("stopProgress()"))

    def routeCalculationDone(self):
        if self.currentRoute.getRouteInfo()!=None:
            self.currentRoute.printRoute(osmParserData)
#            self.printRouteDescription(self.currentRoute)
            
            self.clearAll()

            self.currentRoutePart=0
            self.currentEdgeList=self.currentRoute.getEdgeList(self.currentRoutePart)
            self.currentTrackList=self.currentRoute.getTrackList(self.currentRoutePart)
            self.currentStartPoint=self.currentRoute.getStartPoint(self.currentRoutePart)
            self.currentTargetPoint=self.currentRoute.getTargetPoint(self.currentRoutePart)
#            print(self.currentEdgeList)
#            print(self.currentTrackList)
                
            print(self.currentRoute.getAllLength())
            print(self.currentRoute.getAllTime())
            
            # display inital distances
            # simply use start point as ref
            self.calcRouteDistances(self.startPoint.getPos()[0], self.startPoint.getPos()[1], True)
            self.routingStarted=True
            self.update()       

    def switchToNextRoutePart(self):
        if self.currentRoutePart < self.currentRoute.getRouteInfoLength()-1:
#            print("switch to next route part")
            self.currentRoutePart=self.currentRoutePart+1
            self.currentEdgeList=self.currentRoute.getEdgeList(self.currentRoutePart)
            self.currentTrackList=self.currentRoute.getTrackList(self.currentRoutePart)
            self.currentStartPoint=self.currentRoute.getStartPoint(self.currentRoutePart)
            self.currentTargetPoint=self.currentRoute.getTargetPoint(self.currentRoutePart)
#            print(self.currentEdgeList)
        
    def currentTargetPointReached(self, lat, lon):
        targetLat, targetLon=self.currentTargetPoint.getClosestRefPos()
        if self.osmutils.distance(lat, lon, targetLat, targetLon)<15.0:
            return True
        return False

    def currentStartPointReached(self, lat, lon):
        startLat, startLon=self.currentStartPoint.getClosestRefPos()
        if self.osmutils.distance(lat, lon, startLat, startLon)<15.0:
            return True
        return False
    
    def clearRoute(self):
        self.distanceToEnd=0
        self.distanceToCrossing=0
        self.currentEdgeIndexList=None
        self.nextEdgeOnRoute=None
        self.currentEdgeList=None
        self.currentTrackList=None
        self.currentStartPoint=None
        self.currentTargetPoint=None
        self.currentRoutePart=0
        self.routingStarted=False
    
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
        if self.drivingMode==False:
            (lat, lon)=self.getPosition(x, y)
            self.showTrackOnPos(lat, lon, self.track, self.speed, True, True)

    def showTrackOnGPSPos(self, update):
        if self.drivingMode==True:
            gpsPosition=self.getGPSPosition()
            if gpsPosition!=None:
                self.showTrackOnPos(gpsPosition[0], gpsPosition[1], self.track, self.speed, update, False)            
    
    def getPosition(self, x, y):
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
            self.osmWidget.setRoutingModeId(config.getSection(section).getint("routingmode", 0))

            for name, value in config.items(section):
                if name[:5]=="point":
                    point=OSMRoutingPoint()
                    point.readFromConfig(value)
                    point.resolveFromPos(osmParserData)
                    
                    if point.getType()==OSMRoutingPoint.TYPE_START:
                        self.startPoint=point
                    if point.getType()==OSMRoutingPoint.TYPE_END:
                        self.endPoint=point
                    if point.getType()==OSMRoutingPoint.TYPE_WAY:
                        self.wayPoints.append(point)
                    if point.getType()==OSMRoutingPoint.TYPE_MAP:
                        self.mapPoint=point
                            
                    if not point.isValid():
                        print("failed to resolve point %s"%(value))
                    

        section="mapPoints"
        if config.hasSection(section):
            for name, value in config.items(section):
                if name[:5]=="point":
                    point=OSMRoutingPoint()
                    point.readFromConfig(value)
                    if point.getType()==OSMRoutingPoint.TYPE_MAP:
                        self.mapPoint=point
                    
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
        
        config.getSection(section)["routingmode"]=str(self.osmWidget.getRoutingModeId())
        
        i=0
        if self.startPoint!=None:
            self.startPoint.saveToConfig(config, section, "point%d"%(i))
            i=i+1
        
        for point in self.wayPoints:
            point.saveToConfig(config, section, "point%d"%(i))
            i=i+1
        
        if self.endPoint!=None:
            self.endPoint.saveToConfig(config, section, "point%d"%(i))

        section="mapPoints"
        config.removeSection(section)
        config.addSection(section)
        i=0
        if self.mapPoint!=None:
            self.mapPoint.saveToConfig(config, section, "point%d"%(i))
        
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
        
    def showError(self, title, text):
        msgBox=QMessageBox(QMessageBox.Warning, title, text, QMessageBox.Ok, self)
        font = self.font()
        font.setPointSize(14)
        msgBox.setFont(font)
        msgBox.exec()

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
        
#        self.style=OSMStyle()
#        self.favoriteIcon=QIcon(self.style.getStylePixmap("favoritesPixmap"))
#        self.addressIcon=QIcon(self.style.getStylePixmap("addressesPixmap"))
#        self.routesIccon=QIcon(self.style.getStylePixmap("routePixmap"))
#        self.centerGPSIcon=QIcon(self.style.getStylePixmap("centerGPSPixmap"))
#        self.settingsIcon=QIcon(self.style.getStylePixmap("settingsPixmap"))
#        self.gpsIcon=QIcon(self.style.getStylePixmap("gpsDataPixmap"))

        self.incLat=0.0
        self.incLon=0.0
        self.step=0
        self.trackLogLines=None
        self.trackLogLine=None
        self.gpsSignalInvalid=False
        self.test=test
        self.lastGPSData=None
        self.osmUtils=OSMUtils()
        self.gpsPrediction=True
        self.isInTunnel=False
#        self.waitForInvalidGPSSignal=False
        osmParserData.openAllDB()
        
    def addToWidget(self, vbox):     
        hbox1=QHBoxLayout()
        hbox1.addWidget(self.mapWidgetQt)
        
#        buttons=QVBoxLayout()        
#        buttons.setAlignment(Qt.AlignLeft|Qt.AlignTop)
#        buttons.setSpacing(0)

#        iconSize=QSize(48, 48)
#        self.adressButton=QPushButton("", self)
#        self.adressButton.setIcon(self.addressIcon)
#        self.adressButton.setToolTip("Addresses")
#        self.adressButton.clicked.connect(self._showSearchMenu)
#        self.adressButton.setIconSize(iconSize)        
#        buttons.addWidget(self.adressButton)
#                
#        self.favoritesButton=QPushButton("", self)
#        self.favoritesButton.setIcon(self.favoriteIcon)
#        self.favoritesButton.setToolTip("Favorites")
#        self.favoritesButton.clicked.connect(self._showFavorites)
#        self.favoritesButton.setIconSize(iconSize)        
#        buttons.addWidget(self.favoritesButton)
#        
#        self.routesButton=QPushButton("", self)
#        self.routesButton.setIcon(self.routesIccon)
#        self.routesButton.setToolTip("Routes")
#        self.routesButton.clicked.connect(self._loadRoute)
#        self.routesButton.setIconSize(iconSize)        
#        buttons.addWidget(self.routesButton)
#
#        self.centerGPSButton=QPushButton("", self)
#        self.centerGPSButton.setToolTip("Center map to GPS")
#        self.centerGPSButton.setIcon(self.centerGPSIcon)
#        self.centerGPSButton.setIconSize(iconSize)        
#        self.centerGPSButton.clicked.connect(self._centerGPS)
#        buttons.addWidget(self.centerGPSButton)
#        
#        self.showGPSDataButton=QPushButton("", self)
#        self.showGPSDataButton.setToolTip("Show data from GPS")
#        self.showGPSDataButton.setIcon(self.gpsIcon)
#        self.showGPSDataButton.setIconSize(iconSize)        
#        self.showGPSDataButton.clicked.connect(self._showGPSData)
#        buttons.addWidget(self.showGPSDataButton)
#
#        self.optionsButton=QPushButton("", self)
#        self.optionsButton.setToolTip("Settings")
#        self.optionsButton.setIcon(self.settingsIcon)
#        self.optionsButton.setIconSize(iconSize)        
#        self.optionsButton.clicked.connect(self._showSettings)
#        buttons.addWidget(self.optionsButton)  
        
#        font = QFont("Mono")
#        font.setPointSize(14)
#        font.setStyleHint(QFont.TypeWriter)
#
#        coords=QVBoxLayout()        
#        coords.setAlignment(Qt.AlignLeft|Qt.AlignTop)
#        coords.setSpacing(0)
#
#        buttons.addLayout(coords)
#
#        self.gpsPosValueLat=QLabel("%.5f"%(0.0), self)
#        self.gpsPosValueLat.setFont(font)
#        self.gpsPosValueLat.setAlignment(Qt.AlignRight)
#        coords.addWidget(self.gpsPosValueLat)
#
#        self.gpsPosValueLon=QLabel("%.5f"%(0.0), self)
#        self.gpsPosValueLon.setFont(font)
#        self.gpsPosValueLon.setAlignment(Qt.AlignRight)
#        coords.addWidget(self.gpsPosValueLon)
#        
#        self.gpsAltitudeValue=QLabel("%d"%(0), self)
#        self.gpsAltitudeValue.setFont(font)
#        self.gpsAltitudeValue.setAlignment(Qt.AlignRight)
#        coords.addWidget(self.gpsAltitudeValue)
#
#        self.gpsSpeedValue=QLabel("%d"%(0), self)
#        self.gpsSpeedValue.setFont(font)
#        self.gpsSpeedValue.setAlignment(Qt.AlignRight)
#        coords.addWidget(self.gpsSpeedValue)
#        
#        hbox1.addLayout(buttons)

        vbox.addLayout(hbox1)
        
        if self.test==True:
            self.addTestButtons(vbox)

    def addTestButtons(self, vbox):
        self.testButtons=QHBoxLayout()        

        self.testGPSButton=QPushButton("Test GPS", self)
        self.testGPSButton.clicked.connect(self._testGPS)
        self.testButtons.addWidget(self.testGPSButton)
        
#        self.stepRouteButton=QPushButton("Step", self)
#        self.stepRouteButton.clicked.connect(self._stepRoute)
#        buttons.addWidget(self.stepRouteButton)
#        
#        self.resetStepRouteButton=QPushButton("Reset Step", self)
#        self.resetStepRouteButton.clicked.connect(self._resetStepRoute)
#        buttons.addWidget(self.resetStepRouteButton)

        self.loadTrackLogButton=QPushButton("Load Tracklog", self)
        self.loadTrackLogButton.clicked.connect(self._loadTrackLog)
        self.testButtons.addWidget(self.loadTrackLogButton)
        
        self.stepTrackLogButton=QPushButton("Step", self)
        self.stepTrackLogButton.clicked.connect(self._stepTrackLog)
        self.testButtons.addWidget(self.stepTrackLogButton)

        self.stepTrackLogBackButton=QPushButton("Step Back", self)
        self.stepTrackLogBackButton.clicked.connect(self._stepTrackLogBack)
        self.testButtons.addWidget(self.stepTrackLogBackButton)
        
        self.resetStepTrackLogButton=QPushButton("Reset Tracklog", self)
        self.resetStepTrackLogButton.clicked.connect(self._resetTrackLogStep)
        self.testButtons.addWidget(self.resetStepTrackLogButton)

        self.replayTrackLogBackButton=QPushButton("Replay", self)
        self.replayTrackLogBackButton.clicked.connect(self._replayLog)
        self.testButtons.addWidget(self.replayTrackLogBackButton)
        
        self.pauseReplayTrackLogBackButton=QPushButton("Pause", self)
        self.pauseReplayTrackLogBackButton.clicked.connect(self._pauseReplayLog)
        self.testButtons.addWidget(self.pauseReplayTrackLogBackButton)

        self.continueReplayTrackLogBackButton=QPushButton("Continue", self)
        self.continueReplayTrackLogBackButton.clicked.connect(self._continueReplayLog)
        self.testButtons.addWidget(self.continueReplayTrackLogBackButton)

        self.stopReplayTrackLogButton=QPushButton("Stop", self)
        self.stopReplayTrackLogButton.clicked.connect(self._stopReplayLog)
        self.testButtons.addWidget(self.stopReplayTrackLogButton)

        vbox.addLayout(self.testButtons)
        
    def disableTestButtons(self):
        self.testGPSButton.setEnabled(False)
        self.loadTrackLogButton.setEnabled(False)
        self.stepTrackLogButton.setEnabled(False)
        self.stepTrackLogBackButton.setEnabled(False)
        self.resetStepTrackLogButton.setEnabled(False)
        self.replayTrackLogBackButton.setEnabled(False)
        self.pauseReplayTrackLogBackButton.setEnabled(False)
        self.continueReplayTrackLogBackButton.setEnabled(False)
        self.stopReplayTrackLogButton.setEnabled(False)

    def enableTestButtons(self):
        self.testGPSButton.setEnabled(True)
        self.loadTrackLogButton.setEnabled(True)
        self.stepTrackLogButton.setEnabled(True)
        self.stepTrackLogBackButton.setEnabled(True)
        self.resetStepTrackLogButton.setEnabled(True)
        self.replayTrackLogBackButton.setEnabled(True)
        self.pauseReplayTrackLogBackButton.setEnabled(True)
        self.continueReplayTrackLogBackButton.setEnabled(True)
        self.stopReplayTrackLogButton.setEnabled(True)
        
    def initWorkers(self):
        self.downloadThread=OSMDownloadTilesWorker(self, self.getTileServer())
        self.downloadThread.setWidget(self.mapWidgetQt)
        self.connect(self.downloadThread, SIGNAL("updateMap()"), self.mapWidgetQt.updateMap)
        self.connect(self.downloadThread, SIGNAL("updateDownloadThreadState(QString)"), self.updateDownloadThreadState)

        if disableMappnik==False:
            self.mapnikThread=OSMMapnikTilesWorker(self, self.mapWidgetQt.getTileHomeFullPath(), self.mapWidgetQt.getMapnikConfigFullPath())
            self.mapnikThread.setWidget(self.mapWidgetQt)
            self.connect(self.mapnikThread, SIGNAL("updateMap()"), self.mapWidgetQt.updateMap)
            self.connect(self.mapnikThread, SIGNAL("updateMapnikThreadState(QString)"), self.updateMapnikThreadState)
        else:
            self.mapnikThread=None
            
        self.trackLogReplayThread=OSMGPSSimulationWorker(self)
        self.trackLogReplayThread.setWidget(self)
        self.connect(self.trackLogReplayThread, SIGNAL("updateGPSDataDisplaySimulated(PyQt_PyObject)"), self.updateGPSDataDisplaySimulated)
       
        self.updateLocationThread=OSMUpdateLocationWorker(self)
        self.updateLocationThread.setWidget(self)
        self.connect(self.updateLocationThread, SIGNAL("updateLocation()"), self.createPredictedLocation)
                        
    def startProgress(self):
        self.emit(SIGNAL("startProgress()"))

    def stopProgress(self):
        self.emit(SIGNAL("stopProgress()"))

    @pyqtSlot()
    def _searchPOIName(self):
        self.searchPOI(False)

    @pyqtSlot()
    def _searchPOINearest(self):
        self.searchPOI(True)
        
    def searchPOI(self, nearest):
        mapPosition=self.mapWidgetQt.getMapPosition()
        gpsPosition=self.mapWidgetQt.getGPSPosition()

        # we always use map position for country pre selection
        defaultCountryId=osmParserData.getCountryOnPointWithGeom(mapPosition[0], mapPosition[1])
        poiDialog=OSMPOISearchDialog(self, osmParserData, mapPosition, gpsPosition, defaultCountryId, nearest)
        result=poiDialog.exec()
        if result==QDialog.Accepted:
#            poiEntry, pointType=poiDialog.getResult()
            pointDict=poiDialog.getResult2()
            for pointType, poiEntry in pointDict.items():
                (refId, lat, lon, tags, nodeType, cityId, distance, displayString)=poiEntry
                displayString=osmParserData.getPOITagString(tags)
                self.setPoint(displayString, pointType, lat, lon)

    def showError(self, title, text):
        msgBox=QMessageBox(QMessageBox.Warning, title, text, QMessageBox.Ok, self)
        font = self.font()
        font.setPointSize(14)
        msgBox.setFont(font)
        msgBox.exec()
        
    def getOptionsConfig(self, optionsConfig):
        optionsConfig["followGPS"]=self.getAutocenterGPSValue()
        optionsConfig["withDownload"]=self.getWithDownloadValue()
        optionsConfig["withMapRotation"]=self.getWithMapRotationValue()
        optionsConfig["withShow3D"]=self.getShow3DValue()
        optionsConfig["withShowAreas"]=self.getShowAreas()
        optionsConfig["withShowPOI"]=self.getShowPOI()
        optionsConfig["withShowSky"]=self.getShowSky()
        optionsConfig["XAxisRotation"]=self.getXAxisRotation()
        optionsConfig["tileServer"]=self.getTileServer()
        optionsConfig["tileHome"]=self.getTileHome()
        optionsConfig["routingModes"]=self.getRoutingModes()
        optionsConfig["routingModeId"]=self.getRoutingModeId()
        
        if disableMappnik==False:
            optionsConfig["mapnikConfig"]=self.getMapnikConfig()
            optionsConfig["withMapnik"]=self.getWithMapnikValue()
            
        optionsConfig["tileStartZoom"]=self.getTileStartZoom()
        optionsConfig["displayPOITypeList"]=list(self.getDisplayPOITypeList())
        optionsConfig["displayAreaTypeList"]=list(self.getDisplayAreaTypeList())
        optionsConfig["startZoom3D"]=self.getStartZoom3DView()
        optionsConfig["withNmea"]=True
        optionsConfig["withGpsd"]=False
        optionsConfig["withGPSPrediction"]=self.getGPSPrediction()
        optionsConfig["withGPSBreadcrumbs"]=self.getGPSBreadcrumbs()
        
        gpsConfig.getOptionsConfig(optionsConfig)
        return optionsConfig

    def setFromOptionsConfig(self, optionsConfig):
        self.setWithDownloadValue(optionsConfig["withDownload"])
        self.setAutocenterGPSValue(optionsConfig["followGPS"])
        self.setWithMapRotationValue(optionsConfig["withMapRotation"])
        self.setShow3DValue(optionsConfig["withShow3D"])
        self.setShowAreas(optionsConfig["withShowAreas"])
        self.setShowPOI(optionsConfig["withShowPOI"])
        self.setShowSky(optionsConfig["withShowSky"])
        self.setXAxisRotation(optionsConfig["XAxisRotation"])
        self.setTileServer(optionsConfig["tileServer"])
        self.setTileHome(optionsConfig["tileHome"])
        
        if disableMappnik==False:
            oldMapnikValue=self.getWithMapnikValue()
            self.setMapnikConfig(optionsConfig["mapnikConfig"])
            self.setWithMapnikValue(optionsConfig["withMapnik"])
            if self.getWithMapnikValue()!=oldMapnikValue:
                self.mapWidgetQt.cleanImageCache()
            
        self.setTileStartZoom(optionsConfig["tileStartZoom"])
        self.setDisplayPOITypeList(optionsConfig["displayPOITypeList"])
        self.setDisplayAreaTypeList(optionsConfig["displayAreaTypeList"])
        self.setStartZoom3DView(optionsConfig["startZoom3D"])
        self.setRoutingMode(optionsConfig["routingMode"])
        self.setGPSPrediction(optionsConfig["withGPSPrediction"])
        self.setGPSBreadcrumbs(optionsConfig["withGPSBreadcrumbs"])
        
        gpsConfig.setFromOptionsConfig(optionsConfig)
        
    @pyqtSlot()
    def _showSettings(self):
        optionsDialog=OSMOptionsDialog(self.getOptionsConfig(dict()), self)
        result=optionsDialog.exec()
        if result==QDialog.Accepted:
            self.setFromOptionsConfig(optionsDialog.getOptionsConfig())
            
            self.mapWidgetQt.clearPolygonCache()
            self.update()
             
    @pyqtSlot()
    def _cleanup(self):
        trackLog.closeLogFile()

        if self.downloadThread.isRunning():
            self.downloadThread.stop()        
        
        if disableMappnik==False:
            if self.mapnikThread.isRunning():
                self.mapnikThread.stop()

        if self.trackLogReplayThread.isRunning():
            self.trackLogReplayThread.stop()
            
        if self.updateLocationThread.isRunning():
            self.updateLocationThread.stop()
 
        osmParserData.closeAllDB()

    def handleMissingGPSSignal(self):
        self.mapWidgetQt.clearAll()
        self.update()
    
    def startTunnelMode(self):
        if self.isInTunnel==False:
            self.isInTunnel=True
            # ignore all gps signals until the first invalid
            # since the gps data maybe wrong or incorrect
            # before completely missing
            # and this is influencing the tunnel prediction
            # which is based on the last data before the tunnel
#            self.waitForInvalidGPSSignal=True     
               
    def stopTunnelMode(self):
        if self.isInTunnel==True:
            self.isInTunnel=False
#            self.waitForInvalidGPSSignal=False
    
    # called from gps update thread
    # only for different gps data
    def updateGPSDisplay(self, gpsData, addToLog=True):
        if gpsData!=None:   
            if gpsData.isValid():
                # after tunnel enter wait until signal
                # becomes invalid
#                if self.waitForInvalidGPSSignal==True:
#                    return
                
                self.gpsSignalInvalid=False                                    
                self.updateGPSDataDisplay(gpsData, False)
            else:
#                self.waitForInvalidGPSSignal=False
                
                self.gpsSignalInvalid=True 
                
                if self.isInTunnel==False:
                    self.handleMissingGPSSignal()

            if addToLog==True and self.test==False:
                trackLog.addTrackLogLine(gpsData.toLogLine())

    # called from tracklog worker
    def updateGPSDataDisplaySimulated(self, gpsData):    
        self.updateGPSDisplay(gpsData, False)    
        
    def createPredictedLocation(self):
        # use predicition only in higher zooms
        if self.mapWidgetQt.map_zoom<PREDICTION_USE_START_ZOOM:
            return 
        
        if self.getDrivingMode()==False:
            return
        
        if self.lastGPSData!=None:
            timeStamp=time.time()
            # update only after a max time of 500ms
            # try to get it right in the middle between 2 "real" gps signals
            if timeStamp-self.lastGPSData.time<0.5:
                return
            
            # only use location worker if in tunnel
            # just use last track and speed
            if self.isInTunnel==False:
                if self.gpsSignalInvalid==True: 
                    return 
    
            if self.lastGPSData.speed==0:
                return

            distance=(self.lastGPSData.speed/3.6)*(timeStamp-self.lastGPSData.time)
            if distance<3.0:
                return

            track=self.lastGPSData.track
            lat=self.lastGPSData.lat
            lon=self.lastGPSData.lon

            # make sure the prediction is on the edge of the tunnel
            # if the edge makes a curve inside the tunnel
            if self.isInTunnel==True and self.mapWidgetQt.currentCoords!=None:
                refPoint, point, distances=osmParserData.getClosestPointOnEdge(lat, lon, self.mapWidgetQt.currentCoords, 30.0)
                if point!=None:
                    lat=point[0]
                    lon=point[1]
                
            lat1, lon1=self.osmUtils.getPosInDistanceAndTrack(lat, lon, distance, track)
            tmpGPSData=GPSData(timeStamp, lat1, lon1, track, self.lastGPSData.speed, self.lastGPSData.altitude, True, self.lastGPSData.satellitesInUse)
#            print("predictedLocation %f %f %f"%(tmpGPSData.time, lat1, lon1))
            self.updateGPSDataDisplay(tmpGPSData, False)

    def updateGPSDataDisplay(self, gpsData, debug): 
        self.lastGPSData=gpsData                   
        self.mapWidgetQt.updateGPSLocation(gpsData, debug)
            
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

    def getAutocenterGPSValue(self):
        return self.mapWidgetQt.autocenterGPS

    def setAutocenterGPSValue(self, value):
        self.mapWidgetQt.autocenterGPS=value

    def getShow3DValue(self):
        return self.mapWidgetQt.show3D
    
    def setShow3DValue(self, value):
        self.mapWidgetQt.show3D=value
             
#    def getShowBackgroundTiles(self):
#        return self.mapWidgetQt.showBackgroundTiles
#         
#    def setShowBackgroundTiles(self, value):
#        self.mapWidgetQt.showBackgroundTiles=value
         
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
        if disableMappnik==False:
            self.mapWidgetQt.withMapnik=value
    
    def setNightMode(self, value):
        self.mapWidgetQt.nightMode=value
        self.update()
    
    def getNightMode(self):
        return self.mapWidgetQt.nightMode
    
    def setConnectGPS(self, value):
        self.gpsConnected=value
                        
    def getConnectGPS(self):
        return self.gpsConnected
    
    def setDrivingMode(self, value):
        self.mapWidgetQt.drivingMode=value
        if value==True:
            self.mapWidgetQt.showTrackOnGPSPos(False)
        
            if self.getAutocenterGPSValue()==True:
                self.mapWidgetQt.osm_autocenter_map()
            else:
                self.update()
        else:
            self.mapWidgetQt.clearAll()
            self.update()
        
    def getDrivingMode(self):
        return self.mapWidgetQt.drivingMode
    
    def getShowAreas(self):
        return self.mapWidgetQt.withShowAreas

    def setShowAreas(self, value):
        self.mapWidgetQt.withShowAreas=value
        
    def getShowPOI(self):
        return self.mapWidgetQt.withShowPOI

    def setShowPOI(self, value):
        self.mapWidgetQt.withShowPOI=value
        
    def getShowSky(self):
        return self.mapWidgetQt.showSky
    
    def setShowSky(self, value):
        self.mapWidgetQt.showSky=value
        
    def getXAxisRotation(self):
        return self.mapWidgetQt.XAxisRotation
    
    def setXAxisRotation(self, value):
        self.mapWidgetQt.XAxisRotation=value
        
    def getTileHome(self):
        return self.mapWidgetQt.tileHome
    
    def setTileHome(self, value):
        self.mapWidgetQt.tileHome=value
                
    def getTileServer(self):
        return self.mapWidgetQt.tileServer
    
    def setTileServer(self, value):
        self.mapWidgetQt.tileServer=value

    def getMapnikConfig(self):
        return self.mapWidgetQt.mapnikConfig
    
    def setMapnikConfig(self, value):
        if disableMappnik==False:
            self.mapWidgetQt.mapnikConfig=value  
              
    def getTileStartZoom(self):
        return self.mapWidgetQt.tileStartZoom
    
    def setTileStartZoom(self, value):
        self.mapWidgetQt.tileStartZoom=value
        
    def getVirtualZoom(self):
        return self.mapWidgetQt.isVirtualZoom
    
    def setVirtualZoom(self, value):
        self.mapWidgetQt.isVirtualZoom=value
        
    def getDisplayPOITypeList(self):
        return self.mapWidgetQt.getDisplayPOITypeList()
    
    def setDisplayPOITypeList(self, poiTypeList):
        self.mapWidgetQt.setDisplayPOITypeList(poiTypeList)
        
    def getDisplayAreaTypeList(self):
        return self.mapWidgetQt.getDisplayAreaTypeList()
    
    def setDisplayAreaTypeList(self, areaTypeList):
        self.mapWidgetQt.setDisplayAreaTypeList(areaTypeList)
        
    def getStartZoom3DView(self):
        return self.mapWidgetQt.startZoom3DView
    
    def setStartZoom3DView(self, value):
        self.mapWidgetQt.startZoom3DView=value
        
    def getSidebarVisible(self):
        return self.mapWidgetQt.sidebarVisible
    
    def setSidebarVisible(self, value):
        self.mapWidgetQt.sidebarVisible=value
    
    def getRoutingModes(self):
        return osmParserData.getRoutingModes()

    def getRoutingModeId(self):
        return osmParserData.getRoutingModeId()

    def setRoutingMode(self, mode):
        return osmParserData.setRoutingMode(mode)
        
    def setRoutingModeId(self, modeId):
        return osmParserData.setRoutingModeId(modeId)
    
    def getGPSPrediction(self):
        return self.gpsPrediction
    
    def setGPSPrediction(self, value):
        self.gpsPrediction=value

    def getGPSBreadcrumbs(self):
        return self.mapWidgetQt.gpsBreadcrumbs
    
    def setGPSBreadcrumbs(self, value):
        self.mapWidgetQt.gpsBreadcrumbs=value
                
    def loadConfig(self, config):
        section="display"
        self.setZoomValue(config.getSection(section).getint("zoom", 9))
        self.setAutocenterGPSValue(config.getSection(section).getboolean("autocenterGPS", False))
        self.setWithDownloadValue(config.getSection(section).getboolean("withDownload", True))
        self.setStartLatitude(config.getSection(section).getfloat("lat", self.startLat))
        self.setStartLongitude(config.getSection(section).getfloat("lon", self.startLon))
        self.setTileHome(config.getSection(section).get("tileHome", defaultTileHome))
        self.setTileServer(config.getSection(section).get("tileServer", defaultTileServer))
        
        if disableMappnik==False:
            self.setWithMapnikValue(config.getSection(section).getboolean("withMapnik", False))
            self.setMapnikConfig(config.getSection(section).get("mapnikConfig", defaultMapnikConfig))
        
        self.setWithMapRotationValue(config.getSection(section).getboolean("withMapRotation", False))
        self.setShow3DValue(config.getSection(section).getboolean("with3DView", False))
#        self.setShowBackgroundTiles(config.getSection(section).getboolean("showBackgroundTiles", False))
        self.setShowAreas(config.getSection(section).getboolean("showAreas", False))
        self.setShowPOI(config.getSection(section).getboolean("showPOI", False))
        self.setShowSky(config.getSection(section).getboolean("showSky", False))
        self.setXAxisRotation(config.getSection(section).getint("XAxisRotation", 60))
        self.setTileStartZoom(config.getSection(section).getint("tileStartZoom", defaultTileStartZoom))
        self.setVirtualZoom(config.getSection(section).getboolean("virtualZoom", False))
        self.setStartZoom3DView(config.getSection(section).getint("startZoom3D", defaultStart3DZoom))
        self.setSidebarVisible(config.getSection(section).getboolean("sidebarVisible", True))
        self.setGPSPrediction(config.getSection(section).getboolean("withGPSPrediction", True))
        self.setGPSBreadcrumbs(config.getSection(section).getboolean("withGPSBreadcrumbs", True))
        
        section="poi"
        if config.hasSection(section):
            poiTypeList=list()
            for name, value in config.items(section):
                if name[:7]=="poitype":
                    poiTypeList.append(int(value))
            self.setDisplayPOITypeList(poiTypeList)
                    
        section="area"
        if config.hasSection(section):
            areaTypeList=list()
            for name, value in config.items(section):
                if name[:8]=="areatype":
                    areaTypeList.append(int(value))
            self.setDisplayAreaTypeList(areaTypeList)
        
        section="favorites"
        self.favoriteList=list()
        if config.hasSection(section):
            for name, value in config.items(section):
                if name[:8]=="favorite":
                    favoritePoint=OSMRoutingPoint()
                    favoritePoint.readFromConfig(value)
                    self.favoriteList.append(favoritePoint)

        self.mapWidgetQt.loadConfig(config)
        gpsConfig.loadConfig(config)
        loadDialogSettings(config)        
        
    def saveConfig(self, config):
        section="display"
        config.removeSection(section)
        config.addSection(section)
        
#        print("withDownload: %s"%(self.getWithDownloadValue()))
        config.getSection(section)["zoom"]=str(self.getZoomValue())
        config.getSection(section)["autocenterGPS"]=str(self.getAutocenterGPSValue())
        config.getSection(section)["withDownload"]=str(self.getWithDownloadValue())
        config.getSection(section)["withMapnik"]=str(self.getWithMapnikValue())
        config.getSection(section)["withMapRotation"]=str(self.getWithMapRotationValue())
        config.getSection(section)["with3DView"]=str(self.getShow3DValue())
#        config.getSection(section)["showBackgroundTiles"]=str(self.getShowBackgroundTiles())
        config.getSection(section)["showAreas"]=str(self.getShowAreas())
        config.getSection(section)["showPOI"]=str(self.getShowPOI())
        config.getSection(section)["showSky"]=str(self.getShowSky())
        config.getSection(section)["XAxisRotation"]=str(self.getXAxisRotation())
        config.getSection(section)["tileStartZoom"]=str(self.getTileStartZoom())
        config.getSection(section)["virtualZoom"]=str(self.getVirtualZoom())
        config.getSection(section)["startZoom3D"]=str(self.getStartZoom3DView())
        config.getSection(section)["sidebarVisible"]=str(self.getSidebarVisible())
        
        if self.mapWidgetQt.gps_rlat!=0.0:
            config.getSection(section)["lat"]="%.6f"%self.mapWidgetQt.osmutils.rad2deg(self.mapWidgetQt.gps_rlat)
        else:
            config.getSection(section)["lat"]="%.6f"%self.mapWidgetQt.osmutils.rad2deg(self.mapWidgetQt.center_rlat)
            
        if self.mapWidgetQt.gps_rlon!=0.0:    
            config.getSection(section)["lon"]="%.6f"%self.mapWidgetQt.osmutils.rad2deg(self.mapWidgetQt.gps_rlon)
        else:
            config.getSection(section)["lon"]="%.6f"%self.mapWidgetQt.osmutils.rad2deg(self.mapWidgetQt.center_rlon)
            
        config.getSection(section)["tileHome"]=self.getTileHome()
        config.getSection(section)["tileServer"]=self.getTileServer()
        config.getSection(section)["mapnikConfig"]=self.getMapnikConfig()
        config.getSection(section)["withGPSPrediction"]=str(self.getGPSPrediction())
        config.getSection(section)["withGPSBreadcrumbs"]=str(self.getGPSBreadcrumbs())
        
        section="poi"
        config.removeSection(section)
        config.addSection(section)
        i=0
        self.getDisplayPOITypeList().sort()
        for poiType in self.getDisplayPOITypeList():
            config.set(section, "poiType%d"%(i), str(poiType))
            i=i+1

        section="area"
        config.removeSection(section)
        config.addSection(section)
        i=0
        self.getDisplayAreaTypeList().sort()
        for areaType in self.getDisplayAreaTypeList():
            config.set(section, "areaType%d"%(i), str(areaType))
            i=i+1
            
        section="favorites"
        config.removeSection(section)
        config.addSection(section)
        i=0
        for point in self.favoriteList:
            point.saveToConfig(config, section, "favorite%d"%(i))
            i=i+1
        
        self.mapWidgetQt.saveConfig(config)
        
        gpsConfig.saveConfig(config)
        saveDialogSettings(config)
        
    def updateDownloadThreadState(self, state):
        if state!=self.lastDownloadState:
            self.lastDownloadState=state

    def updateMapnikThreadState(self, state):
        if state!=self.lastMapnikState:
            self.lastMapnikState=state
        
    def _showSearchMenu(self):
        menu = QMenu(self)
        searchAddressAction = QAction("Address", self)
        searchPOINameAction = QAction("POI by Name", self)
        searchPOINearestAction = QAction("Nearest POI", self)

        menu.addAction(searchAddressAction)
        menu.addAction(searchPOINameAction)
        menu.addAction(searchPOINearestAction)

        action = menu.exec_(self.mapToGlobal(self.mapWidgetQt.searchRect.center()))
        if action==searchAddressAction:
            self.searchAddress()
        elif action==searchPOINameAction:
            self._searchPOIName()
        elif action==searchPOINearestAction:
            self._searchPOINearest()
        
    def setPoint(self, name, pointType, lat, lon):
        point=OSMRoutingPoint(name, pointType, (lat, lon))
        if pointType==OSMRoutingPoint.TYPE_START:
            point.resolveFromPos(osmParserData)
            self.mapWidgetQt.setStartPoint(point) 
            self.mapWidgetQt.showPointOnMap(point)
            if not point.isValid():
                self.showError("Error", "Point not usable for routing.\nFailed to resolve way for point.")
                
        elif pointType==OSMRoutingPoint.TYPE_END:
            point.resolveFromPos(osmParserData)
            self.mapWidgetQt.setEndPoint(point) 
            self.mapWidgetQt.showPointOnMap(point)
            if not point.isValid():
                self.showError("Error", "Point not usable for routing.\nFailed to resolve way for point.")
                
        elif pointType==OSMRoutingPoint.TYPE_WAY:
            point.resolveFromPos(osmParserData)
            self.mapWidgetQt.setWayPoint(point) 
            self.mapWidgetQt.showPointOnMap(point)
            if not point.isValid():
                self.showError("Error", "Point not usable for routing.\nFailed to resolve way for point.")
        
        elif pointType==OSMRoutingPoint.TYPE_MAP:
            self.mapWidgetQt.mapPoint=point
            self.mapWidgetQt.showPointOnMap(point)

        elif pointType==OSMRoutingPoint.TYPE_TMP:
            self.mapWidgetQt.showPointOnMap(point)
        
        elif pointType==OSMRoutingPoint.TYPE_FAVORITE:
            self.favoriteList.append(point)

    def searchAddress(self):
        # we always use map position for country pre selection
        mapPosition=self.mapWidgetQt.getMapPosition()
        defaultCountryId=osmParserData.getCountryOnPointWithGeom(mapPosition[0], mapPosition[1])

        searchDialog=OSMAdressDialog(self, osmParserData, defaultCountryId)
        result=searchDialog.exec()
        if result==QDialog.Accepted:
#            address, pointType=searchDialog.getResult()
            pointDict=searchDialog.getResult2()
            for pointType, address in pointDict.items():
                name=osmParserData.getAddressTagString(address)
                (_, _, _, _, _, _, _, lat, lon)=address
                self.setPoint(name, pointType, lat, lon)
  
    @pyqtSlot()
    def _showFavorites(self):
        favoritesDialog=OSMFavoritesDialog(self, self.favoriteList)
        result=favoritesDialog.exec()
        if result==QDialog.Accepted:
#            point, pointType, favoriteList=favoritesDialog.getResult()
            pointDict, favoriteList=favoritesDialog.getResult2()
            self.favoriteList=favoriteList
            for pointType, point in pointDict.items():
                self.setPoint(point.getName(), pointType, point.getPos()[0], point.getPos()[1])

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
                route.resolveRoutingPoints(osmParserData)
                if not route.isValid():
                    self.showError("Error", "Route has invalid routing points")

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
        
        gpsData=GPSData(time.time(), self.incLat, self.incLon, self.incTrack, 0, 42)
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
                                                 os.path.join(getRoot(), "tracks"),
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
        
        # init
        self.mapWidgetQt.clearAll()
        self.update()        
        
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
            if self.getGPSPrediction()==True:
                self.updateLocationThread.setup()

    @pyqtSlot()
    def _stopReplayLog(self):
        if self.trackLogReplayThread.isRunning():
            self.trackLogReplayThread.stop()
            
        if self.updateLocationThread.isRunning():
            self.updateLocationThread.stop()
        
    @pyqtSlot()
    def _pauseReplayLog(self):
        if self.trackLogReplayThread.isRunning():
            self.trackLogReplayThread.pauseReplay()

        if self.updateLocationThread.isRunning():
            self.updateLocationThread.stop()

    @pyqtSlot()
    def _continueReplayLog(self):
        if not self.trackLogReplayThread.isRunning():
            self.trackLogReplayThread.continueReplay()
            if self.getGPSPrediction()==True:
                self.updateLocationThread.setup()

    def updateGPSThreadState(self, state):
        if state==gpsRunState:            
            if self.test==True:
                self.disableTestButtons()
                
            if self.getGPSPrediction()==True and not self.updateLocationThread.isRunning():
                self.updateLocationThread.setup()
                
        if state==gpsStoppedState:            
            if self.test==True:
                self.enableTestButtons()
                
            if self.updateLocationThread.isRunning():
                self.updateLocationThread.stop()

class OSMWindow(QMainWindow):
    def __init__(self, parent, test):
        QMainWindow.__init__(self, parent)
        font = self.font()
        font.setPointSize(14)
        self.setFont(font)
        self.config=Config("osmmapviewer.cfg")
        self.updateGPSThread=None
        self.test=test
        self.initUI()
        self.gpsConnected=False

#    def paintEvent(self, event):
#        print("OSMWindow:paintEvent")
#        super(OSMWindow, self).paintEvent(event)

    def stopProgress(self):
        print("stopProgress")
        self.progress.setMinimum(0)
        self.progress.setMaximum(1)
        self.progress.reset()
    
    def startProgress(self):
        print("startProgress")
        self.progress.setMinimum(0)
        self.progress.setMaximum(0)
        
    def initUI(self):
        self.statusbar=self.statusBar()
        self.progress=QProgressBar()
        self.statusbar.addPermanentWidget(self.progress)

        
        self.osmWidget=OSMWidget(self, self.test)
        self.osmWidget.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        self.setCentralWidget(self.osmWidget)

        # 47.820630:13.016850
        #47.8209383, 13.0165364
        self.osmWidget.setStartLatitude(47.8209383)
        self.osmWidget.setStartLongitude(13.0165364)

        top=QVBoxLayout(self.osmWidget)        
        self.osmWidget.addToWidget(top)
        self.osmWidget.loadConfig(self.config)
        
        self.osmWidget.initWorkers()

        self.osmWidget.initHome()

        self.connect(self.osmWidget.mapWidgetQt, SIGNAL("updateStatus(QString)"), self.updateStatusLabel)
        self.connect(self.osmWidget, SIGNAL("updateStatus(QString)"), self.updateStatusLabel)
        self.connect(self.osmWidget.downloadThread, SIGNAL("updateStatus(QString)"), self.updateStatusLabel)
        if disableMappnik==False:
            self.connect(self.osmWidget.mapnikThread, SIGNAL("updateStatus(QString)"), self.updateStatusLabel)
        
        self.connect(self.osmWidget.mapWidgetQt, SIGNAL("startProgress()"), self.startProgress)
        self.connect(self.osmWidget.mapWidgetQt, SIGNAL("stopProgress()"), self.stopProgress)
        
        self.nightModeButton=QCheckBox("Night Mode", self)
        self.nightModeButton.clicked.connect(self._nightMode)        
        self.statusbar.addPermanentWidget(self.nightModeButton)

        self.drivingModeButton=QCheckBox("Driving Mode", self)
        self.drivingModeButton.clicked.connect(self._drivingMode)        
        self.statusbar.addPermanentWidget(self.drivingModeButton)
        
        self.connectGPSButton=QCheckBox("Connect GPS", self)
        self.connectGPSButton.clicked.connect(self._connectGPS)        
        self.statusbar.addPermanentWidget(self.connectGPSButton)

        self.setGeometry(0, 0, 900, 500)
        self.setWindowTitle('OSM')
        
        self.updateGPSThread=getGPSUpdateThread(self)
        if self.updateGPSThread!=None:
            self.connect(self.updateGPSThread, SIGNAL("updateStatus(QString)"), self.updateStatusLabel)
            self.connect(self.updateGPSThread, SIGNAL("updateGPSThreadState(QString)"), self.updateGPSThreadState)
            self.connect(self.updateGPSThread, SIGNAL("connectGPSFailed()"), self.connectGPSFailed)
            self.connect(self.updateGPSThread, SIGNAL("updateGPSDisplay(PyQt_PyObject)"), self.osmWidget.updateGPSDisplay)

        self.show()
        
    @pyqtSlot()
    def _connectGPS(self):
        value=self.connectGPSButton.isChecked()
        if value==True:
            if not self.updateGPSThread.isRunning():
                self.updateGPSThread.setup(True)
            
        else:
            self.disconnectGPS()

        self.osmWidget.setConnectGPS(value)
        
    @pyqtSlot()
    def _nightMode(self):
        value=self.nightModeButton.isChecked()
        self.osmWidget.setNightMode(value)

    @pyqtSlot()
    def _drivingMode(self):
        value=self.drivingModeButton.isChecked()
        self.osmWidget.setDrivingMode(value)
        
    def disconnectGPS(self):
        if self.updateGPSThread.isRunning():
            self.updateGPSThread.stop()
                    
    def updateGPSThreadState(self, state):
        self.osmWidget.updateGPSThreadState(state)
    
    def connectGPSFailed(self):
        self.connectGPSButton.setChecked(False)
        self.showError("GPS Error", "Error connecing to GPS")
                
    def updateStatusLabel(self, text):
        self.statusbar.showMessage(text)
        print(text)

    @pyqtSlot()
    def _cleanup(self):
        if self.updateGPSThread.isRunning():
            self.updateGPSThread.stop()
        
        self.saveConfig()

        self.osmWidget._cleanup()

    def saveConfig(self):
        self.osmWidget.saveConfig(self.config)
        self.config.writeConfig()
        
    def showError(self, title, text):
        msgBox=QMessageBox(QMessageBox.Warning, title, text, QMessageBox.Ok, self)
        font = self.font()
        font.setPointSize(14)
        msgBox.setFont(font)
        msgBox.exec()

#    def signal_handler(self, signal, frame):
#        print("signal_handler %d"%(signal))
#        if self.updateGPSThread.isRunning():
#            self.updateGPSThread.disconnectGPS()
#            self.updateGPSThread.reconnectGPS()
        
def main(argv): 
    test=False
    try:
        if argv[1]=="osmtest":
            test=True
    except IndexError:
        test=False

    app = QApplication(sys.argv)
    osmWindow = OSMWindow(None, test)
    app.aboutToQuit.connect(osmWindow._cleanup)
    #signal.signal(signal.SIGUSR1, osmWindow.signal_handler)
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    #timer = QTimer()
    #timer.start(2000)  # You may change this if you wish.
    #timer.timeout.connect(lambda: None)  # Let the interpreter run each 2000 ms.

    sys.exit(app.exec_())

if __name__ == "__main__":
#    cProfile.run('main(sys.argv)')
    main(sys.argv)
