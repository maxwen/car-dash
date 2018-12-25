'''
Created on Dec 3, 2011

@author: maxl
'''

import sys
import math
import os
import signal
import urllib.request
import io
from collections import deque, OrderedDict
from utils.env import getTileRoot, getImageRoot, getRoot

from PyQt5.QtCore import QTimer, QMutex, QEvent, QLine, QAbstractTableModel, QRectF, Qt, QPoint, QPointF, QSize, pyqtSlot, pyqtSignal, QRect, QThread, QItemSelectionModel
from PyQt5.QtGui import QDesktopServices, QPainterPath, QBrush, QFontMetrics, QLinearGradient, QPolygonF, QPolygon, QTransform, QColor, QFont, QValidator, QPixmap, QIcon, QPalette, QPainter, QPen
from PyQt5.QtWidgets import QMessageBox,QToolTip, QFileDialog, QFrame, QComboBox, QAbstractItemView, QCommonStyle, QStyle, QProgressBar, QInputDialog, QLineEdit, QHeaderView, QTableView, QDialog, QLabel, QMenu, QAction, QMainWindow, QTabWidget, QCheckBox, QVBoxLayout, QPushButton, QWidget, QSizePolicy, QHBoxLayout, QApplication

from osmstyle import OSMStyle

from utils.config import Config
from utils.osmutils import OSMUtils
from dialogs.osmdialogs import *

from tracklog import TrackLog

TILESIZE=256
minWidth=640
minHeight=480
MIN_ZOOM=5
MAX_ZOOM=18
MAP_SCROLL_STEP=20
M_LN2=0.69314718055994530942    #log_e 2
IMAGE_WIDTH=64
IMAGE_HEIGHT=64

MAX_TILE_CACHE=1000
TILE_CLEANUP_SIZE=50
CONTROL_WIDTH=80
SCREEN_BORDER_WIDTH=50

PREDICTION_USE_START_ZOOM=15

defaultTileHome=os.path.join("Maps", "osm", "tiles")
defaultTileServer="http://tile.openstreetmap.org"

trackLog=TrackLog(False)
    
class OSMDownloadTilesWorker(QThread):

    updateMapSignal = pyqtSignal()
    updateStatusSignal = pyqtSignal('QString')

    def __init__(self, parent, tileServer): 
        QThread.__init__(self, parent)
        self.exiting = False
        self.downloadQueue=deque()
        self.downloadDoneQueue=deque()
        self.tileServer=tileServer

    def updateStatusLabel(self, text):
        self.updateStatusSignal.emit(text)

    def updateMap(self):
        self.updateMapSignal.emit()
 
    def stop(self):
        self.exiting = True
        self.downloadQueue.clear()
        self.downloadDoneQueue.clear()
        self.wait()

    def clearQueue(self):
        self.downloadQueue.clear()
        self.downloadDoneQueue.clear()

    def addTile(self, tilePath, fileName, tileServer):
        self.tileServer=tileServer
        if fileName in self.downloadDoneQueue:
            return

        if not [tilePath, fileName] in self.downloadQueue:
            self.downloadQueue.append([tilePath, fileName])
        if not self.isRunning():
            self.start()

    def downloadTile(self, tilePath, fileName):
        if fileName in self.downloadDoneQueue:
            return
        if os.path.exists(fileName):
            return
        try:
            if not os.path.exists(os.path.dirname(fileName)):
                try:
                    os.makedirs(os.path.dirname(fileName))
                except OSError:
                    self.updateStatusLabel("OSM download OSError makedirs")
            self.updateStatusLabel("OSM downloading")
            urllib.request.urlretrieve(self.tileServer + tilePath, fileName)
            self.updateMap()
        except urllib.error.URLError:
            self.updateStatusLabel("OSM download error")
            #self.exiting=True
                
    def run(self):
        self.updateStatusLabel("OSM download thread run")
        while not self.exiting and True:
            if len(self.downloadQueue)!=0:
                entry=self.downloadQueue.popleft()
                self.downloadTile(entry[0], entry[1])
                continue
            
            self.updateStatusLabel("OSM download thread idle")

            self.msleep(1000) 
            
            if len(self.downloadQueue)==0:
                self.exiting=True
        
        self.downloadQueue.clear()
        self.downloadDoneQueue.clear()
        self.updateStatusLabel("OSM download thread stopped")
        self.exiting=False
        
class QtOSMWidget(QWidget):
    updateStatusSignal = pyqtSignal('QString')
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
        self.map_zoom=14
        self.center_rlat = 0.0
        self.center_rlon=0.0
        
        self.lastHeadingLat=0.0
        self.lastHeadingLon=0.0
        
        self.osmutils=OSMUtils()
        self.tileCache=OrderedDict()
        
        self.setContextMenuPolicy(Qt.DefaultContextMenu)
        self.moving=False
        self.mousePressed=False
        self.setMouseTracking(True)
        self.posStr="+%.4f , +%.4f" % (0.0, 0.0)
        
        self.tileHome=defaultTileHome
        self.tileServer=defaultTileServer
        
        self.lastMouseMoveX=0
        self.lastMouseMoveY=0
        
        self.recalcTrigger=0
        self.mousePos=(0, 0)
        
        self.lastCenterX=None
        self.lastCenterY=None
        self.XAxisRotation=60
        self.stop=True
        self.currentDisplayBBox=None
        
        self.style=OSMStyle()
        self.mapPoint=None

    def getTileHomeFullPath(self):
        if os.path.isabs(self.tileHome):
            return self.tileHome
        else:
            return os.path.join(getTileRoot(), self.tileHome)
        
    def getTileFullPath(self, zoom, x, y):
        home=self.getTileHomeFullPath()
        tilePath=os.path.join(str(zoom), str(x), str(y)+".png")
        fileName=os.path.join(home, tilePath)
        return fileName
    
    def init(self):
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)        
        
    def osm_center_map_to_position(self, lat, lon):
        self.osm_center_map_to(self.osmutils.deg2rad(lat), self.osmutils.deg2rad(lon))
        
    def osm_map_set_zoom (self, zoom):
        self.map_zoom=zoom        
        self.osm_map_handle_resize()
        
    def osm_map_handle_resize (self):
        (self.center_y, self.center_x)=self.getPixelPosForLocationRad(self.center_rlat, self.center_rlon, False)
        self.center_coord_update()

    def getYOffsetForRotationMap(self):
        return self.height()/3
    
    def calcMapZeroPos(self):
        map_x=int(self.center_x-self.width()/2)
        map_y=int(self.center_y-self.height()/2)
        return (map_x, map_y)
    
    def getMapZeroPos(self):
        return self.map_x, self.map_y
    
    def getMapPosition(self):
        return (self.osmutils.rad2deg(self.center_rlat), self.osmutils.rad2deg(self.center_rlon))
     
    def showTiles (self):     
        width=self.width()
        height=self.width()
        map_x, map_y=self.getMapZeroPos()
                    
        offset_x = - map_x % TILESIZE
        if offset_x==0:
            offset_x= - TILESIZE
            
        offset_y = - map_y % TILESIZE
        if offset_y==0:
            offset_y= - TILESIZE

        #print("%d %d %d %d"%(map_x, map_y, offset_x, offset_y))
        
        if offset_x >= 0:
            offset_x -= TILESIZE*4
        if offset_y >= 0:
            offset_y -= TILESIZE*4

#        print("%d %d"%(offset_x, offset_y))

        tiles_nx = int((width  - offset_x) / TILESIZE + 1)
        tiles_ny = int((height - offset_y) / TILESIZE + 1)

        tile_x0 =  int(math.floor((map_x-TILESIZE) / TILESIZE))-2
        tile_y0 =  int(math.floor((map_y-TILESIZE) / TILESIZE))-2

        i=tile_x0
        j=tile_y0
        offset_y0=offset_y
            
        #print("%d %d %d %d"%(tile_x0, tile_y0, tiles_nx, tiles_ny))
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

        #pixbuf=self.getCachedTile(fileName)
        #if pixbuf!=None:
        #    return pixbuf

        if os.path.exists(fileName):
            pixbuf=self.getTileFromFile(fileName)
            #self.addTileToCache(pixbuf, fileName)
            return pixbuf
        else:
            self.osmWidget.downloadThread.addTile("/"+str(zoom)+"/"+str(x)+"/"+str(y)+".png", fileName, self.tileServer)
            return self.getTilePlaceholder(zoom, x, y)
    
    def getTilePlaceholder(self, zoom, x, y):
        # try upscale lower zoom version
        pixbuf=self.getUpscaledTile(zoom, x, y)
        if pixbuf!=None:
            return pixbuf
        else:
            return self.getEmptyTile()
            
    def osm_center_map_to(self, lat, lon):
        if lat!=0.0 and lon!=0.0:
            (pixel_y, pixel_x)=self.getPixelPosForLocationRad(lat, lon, False)
            self.center_x=pixel_x
            self.center_y=pixel_y
            self.center_coord_update()
            self.update()
            
    def osm_map_scroll(self, dx, dy):
        self.stepInDirection(dx, dy)
    
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

    # for untransformed coords
    def isPointVisible(self, x, y):
        point=QPoint(x, y)
        skyMargin=0

        point0=self.transformHeading.map(point)        
        rect=QRect(0, 0+skyMargin, self.width(), self.height())
        return rect.contains(point0)

    # for already transformed coords
    def isPointVisibleTransformed(self, x, y):
        point=QPoint(x, y)
        skyMargin=0
            
        rect=QRect(0, 0+skyMargin, self.width(), self.height())
        return rect.contains(point)    

    def show(self, zoom, lat, lon):
        self.osm_center_map_to_position(lat, lon)
        self.osm_map_set_zoom(zoom)
        self.update()
    
    def zoom(self, zoom):
        self.osmWidget.downloadThread.clearQueue()
        self.osm_map_set_zoom(zoom)
        self.update()
       
    def resizeEvent(self, event):
        self.osm_map_handle_resize()
    
    def getTransform(self):
        transform=QTransform()
        
        map_x, map_y=self.getMapZeroPos()
        transform.translate( self.center_x-map_x, self.center_y-map_y )
        
        transform.translate( -(self.center_x-map_x), -(self.center_y-map_y) )

        return transform
    
    def setAntialiasing(self, value):
        if self.map_zoom>=self.style.USE_ANTIALIASING_START_ZOOM:
            self.painter.setRenderHint(QPainter.Antialiasing, value)
        else:
            self.painter.setRenderHint(QPainter.Antialiasing, False)
    
    def paintEvent(self, event):
        self.painter=QPainter(self)
        self.painter.setClipRect(QRectF(0, 0, self.width(), self.height()))
            
        self.painter.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setAntialiasing(True)
                
        self.painter.fillRect(0, 0, self.width(), self.height(), self.style.getStyleColor("mapBackgroundColor"))
            
        self.transformHeading=self.getTransform()
            
        self.painter.setTransform(self.transformHeading)
        
        self.showTiles()
        self.displayControlOverlay2()
        self.painter.resetTransform()
        
        self.painter.setRenderHint(QPainter.Antialiasing)
        
        self.painter.end()

     
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

    def center_coord_update(self):
        self.center_rlon = self.osmutils.pixel2lon(self.map_zoom, self.center_x)
        self.center_rlat = self.osmutils.pixel2lat(self.map_zoom, self.center_y)
            
        self.map_x, self.map_y=self.calcMapZeroPos()
        
    def cleanImageCache(self):
        self.tileCache.clear()
    
    def updateStatusLabel(self, text):
        self.updateStatusSignal.emit(text)

    def updateMap(self):
        self.update()
        
    def mouseReleaseEvent(self, event ):
        self.mousePressed=False

        eventPos=QPoint(event.x(), event.y())
        if not self.moving:
            if self.minusRect.contains(eventPos) or self.plusRect.contains(eventPos):
                self.pointInsideZoomOverlay(event.x(), event.y())
                return
            
            self.lastMouseMoveX=event.x()
            self.lastMouseMoveY=event.y()
            #self.showTrackOnMousePos(event.x(), event.y())
                
        else:
            self.moving=False
        
    def pointInsideZoomOverlay(self, x, y):
#        if self.zoomRect.contains(x, y):
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
        
#    def displayControlOverlay(self):
#        self.painter.drawPixmap(0, 0, self.osmControlImage)

    def displayControlOverlay2(self):
        minusBackground=QRect(0, 0, CONTROL_WIDTH, CONTROL_WIDTH)
        diff=CONTROL_WIDTH-IMAGE_WIDTH
        self.painter.fillRect(minusBackground, self.style.getStyleColor("backgroundColor"))
        self.minusRect=minusBackground
        self.painter.drawPixmap(diff/2, diff/2, IMAGE_WIDTH, IMAGE_HEIGHT, self.style.getStylePixmap("minusPixmap"))

        plusBackground=QRect(self.width()-CONTROL_WIDTH, 0, CONTROL_WIDTH, CONTROL_WIDTH)
        self.painter.fillRect(plusBackground, self.style.getStyleColor("backgroundColor"))
        self.plusRect=plusBackground
        self.painter.drawPixmap(self.width()-CONTROL_WIDTH+diff/2, diff/2, IMAGE_WIDTH, IMAGE_HEIGHT, self.style.getStylePixmap("plusPixmap"))

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
        self.favoriteList=list()
        self.mapWidgetQt=QtOSMWidget(self)

        self.incLat=0.0
        self.incLon=0.0
        self.step=0
        
    def addToWidget(self, vbox):     
        hbox1=QHBoxLayout()
        hbox1.addWidget(self.mapWidgetQt)
        vbox.addLayout(hbox1)
        
    def initWorkers(self):
        self.downloadThread=OSMDownloadTilesWorker(self, self.getTileServer())
        self.downloadThread.updateMapSignal.connect(self.mapWidgetQt.updateMap)
        self.downloadThread.updateStatusSignal.connect(self.mapWidgetQt.updateStatusLabel)

    def showError(self, title, text):
        msgBox=QMessageBox(QMessageBox.Warning, title, text, QMessageBox.Ok, self)
        font = self.font()
        font.setPointSize(14)
        msgBox.setFont(font)
        msgBox.exec()

    @pyqtSlot()
    def _cleanup(self):
        trackLog.closeLogFile()

        if self.downloadThread.isRunning():
            self.downloadThread.stop()        

    def init(self, lat, lon, zoom):        
        self.mapWidgetQt.init()
        self.mapWidgetQt.show(zoom, lat, lon)  

    def setStartLongitude(self, lon):
        self.startLon=lon
    
    def setStartLatitude(self, lat):
        self.startLat=lat
        
    def initHome(self):                
        self.init(self.startLat, self.startLon, self.getZoomValue())
    
    def getZoomValue(self):
        return self.mapWidgetQt.map_zoom

    def setZoomValue(self, value):
        self.mapWidgetQt.map_zoom=value
    
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

class OSMWindow(QMainWindow):
    def __init__(self, parent):
        QMainWindow.__init__(self, parent)
        font = self.font()
        font.setPointSize(14)
        self.setFont(font)
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

        
        self.osmWidget=OSMWidget(self)
        self.osmWidget.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        self.setCentralWidget(self.osmWidget)

        # 47.820630:13.016850
        #47.8209383, 13.0165364
        self.osmWidget.setStartLatitude(47.8209383)
        self.osmWidget.setStartLongitude(13.0165364)

        top=QVBoxLayout(self.osmWidget)        
        self.osmWidget.addToWidget(top)
        
        self.osmWidget.initWorkers()

        self.osmWidget.initHome()

        self.osmWidget.mapWidgetQt.updateStatusSignal.connect(self.updateStatusLabel)
    
        self.setGeometry(0, 0, 900, 500)
        self.setWindowTitle('OSM')

        self.show()
                
    def updateStatusLabel(self, text):
        print(text)
        self.statusbar.showMessage(text)

    @pyqtSlot()
    def _cleanup(self):
        self.osmWidget._cleanup()

    def showError(self, title, text):
        msgBox=QMessageBox(QMessageBox.Warning, title, text, QMessageBox.Ok, self)
        font = self.font()
        font.setPointSize(14)
        msgBox.setFont(font)
        msgBox.exec()

def main(argv): 
    app = QApplication(sys.argv)
    osmWindow = OSMWindow(None)
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
