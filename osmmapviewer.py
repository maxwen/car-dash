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
import time

from collections import deque, OrderedDict
from utils.env import getTileRoot, getImageRoot, getRoot
from utils.gisutils import GISUtils

from PyQt5.QtCore import QTimer, QMutex, QEvent, QLine, QAbstractTableModel, QRectF, Qt, QPoint, QPointF, QSize, pyqtSlot, pyqtSignal, QRect, QThread, QItemSelectionModel
from PyQt5.QtGui import QDesktopServices, QPainterPath, QBrush, QFontMetrics, QLinearGradient, QPolygonF, QPolygon, QTransform, QColor, QFont, QValidator, QPixmap, QIcon, QPalette, QPainter, QPen
from PyQt5.QtWidgets import QMessageBox, QToolTip, QFileDialog, QFrame, QComboBox, QAbstractItemView, QCommonStyle, QStyle, QProgressBar, QInputDialog, QLineEdit, QHeaderView, QTableView, QDialog, QLabel, QMenu, QAction, QMainWindow, QTabWidget, QCheckBox, QVBoxLayout, QPushButton, QWidget, QSizePolicy, QHBoxLayout, QApplication
from osmparser.osmdataaccess import Constants, OSMDataAccess
from osmstyle import OSMStyle
from routing.osmrouting import OSMRouting, OSMRoutingPoint, OSMRoute

from utils.config import Config
from utils.osmutils import OSMUtils
from dialogs.osmdialogs import *

from tracklog import TrackLog
from Polygon.cPolygon import Polygon

TILESIZE = 256
minWidth = 640
minHeight = 480
MIN_ZOOM = 5
MAX_ZOOM = 18
MAP_SCROLL_STEP = 20
M_LN2 = 0.69314718055994530942  # log_e 2
IMAGE_WIDTH = 64
IMAGE_HEIGHT = 64
IMAGE_WIDTH_MEDIUM = 48
IMAGE_HEIGHT_MEDIUM = 48
IMAGE_WIDTH_SMALL = 32
IMAGE_HEIGHT_SMALL = 32
IMAGE_WIDTH_LARGE = 80
IMAGE_HEIGHT_LARGE = 80
IMAGE_WIDTH_TINY = 24
IMAGE_HEIGHT_TINY = 24

MAX_TILE_CACHE = 1000
TILE_CLEANUP_SIZE = 50
WITH_CROSSING_DEBUG = False
WITH_TIMING_DEBUG = False
SIDEBAR_WIDTH = 80
CONTROL_WIDTH = 80
SCREEN_BORDER_WIDTH = 50
ROUTE_INFO_WIDTH = 110

DEFAULT_SEARCH_MARGIN = 0.0003
SKY_WIDTH = 100

PREDICTION_USE_START_ZOOM = 15

defaultTileHome = os.path.join("Maps", "osm", "tiles")
defaultTileServer = "http://tile.openstreetmap.org"
defaultTileStartZoom = 13
defaultStart3DZoom = 17

osmParserData = OSMDataAccess()
trackLog = TrackLog(False)
osmRouting = OSMRouting(osmParserData)


class OSMRoutingPointAction(QAction):

    def __init__(self, text, routingPoint, style, parent):
        if routingPoint.getType() != OSMRoutingPoint.TYPE_MAP and not routingPoint.isValid():
            text = text + "(unresolved)"

        QAction.__init__(self, text, parent)
        self.routingPoint = routingPoint
        self.style = style

        if self.routingPoint.getType() == OSMRoutingPoint.TYPE_END:
            self.setIcon(QIcon(self.style.getStylePixmap("finishPixmap")))
        if self.routingPoint.getType() == OSMRoutingPoint.TYPE_START:
            self.setIcon(QIcon(self.style.getStylePixmap("startPixmap")))
        if self.routingPoint.getType() == OSMRoutingPoint.TYPE_WAY:
            self.setIcon(QIcon(self.style.getStylePixmap("wayPixmap")))
        if self.routingPoint.getType() == OSMRoutingPoint.TYPE_MAP:
            self.setIcon(QIcon(self.style.getStylePixmap("mapPointPixmap")))
        self.setIconVisibleInMenu(True)

    def getRoutingPoint(self):
        return self.routingPoint


class OSMDownloadTilesWorker(QThread):

    updateMapSignal = pyqtSignal()
    updateStatusSignal = pyqtSignal('QString')

    def __init__(self, parent, tileServer):
        QThread.__init__(self, parent)
        self.exiting = False
        self.forceDownload = False
        self.downloadQueue = deque()
        self.downloadDoneQueue = deque()
        self.tileServer = tileServer

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
        self.tileServer = tileServer
        if fileName in self.downloadDoneQueue:
            return
        if not [tilePath, fileName] in self.downloadQueue:
            self.downloadQueue.append([tilePath, fileName])
        if not self.isRunning():
            self.start()

    def downloadTile(self, tilePath, fileName):
        if fileName in self.downloadDoneQueue:
            return
        if os.path.exists(fileName) and self.forceDownload == False:
            return
        try:
            if not os.path.exists(os.path.dirname(fileName)):
                try:
                    os.makedirs(os.path.dirname(fileName))
                except OSError:
                    self.updateStatusLabel("OSM download OSError makedirs")
            urllib.request.urlretrieve(self.tileServer + tilePath, fileName)
            self.updateMap()

        except urllib.error.URLError:
            self.updateStatusLabel("OSM download error")

    def run(self):
        self.updateStatusLabel("OSM download thread run")
        while not self.exiting and True:
            if len(self.downloadQueue) != 0:
                entry = self.downloadQueue.popleft()
                self.downloadTile(entry[0], entry[1])
                continue

            self.updateStatusLabel("OSM download thread idle")
            self.msleep(1000)
            if len(self.downloadQueue) == 0:
                self.exiting = True

        self.downloadQueue.clear()
        self.downloadDoneQueue.clear()
        self.updateStatusLabel("OSM download thread stopped")
        self.exiting = False


class OSMRouteCalcWorker(QThread):
    updateStatusSignal = pyqtSignal('QString')
    startProgressSignal = pyqtSignal()
    stopProgressSignal = pyqtSignal()
    routeCalculationDoneSignal = pyqtSignal()

    def __init__(self, parent, route):
        QThread.__init__(self, parent)
        self.exiting = False
        self.route = route

    def updateStatusLabel(self, text):
        self.updateStatusSignal.emit(text)

    def routeCalculationDone(self):
        self.routeCalculationDoneSignal.emit()

    def startProgress(self):
        self.startProgressSignal.emit()

    def stopProgress(self):
        self.stopProgressSignal.emit()

    def run(self):
        self.startProgress()
        while not self.exiting and True:
            self.route.calcRoute(osmParserData)
            self.exiting = True

        self.updateStatusLabel("OSM stopped route calculation thread")
        self.routeCalculationDone()
        self.stopProgress()


class QtOSMWidget(QWidget):
    updateStatusSignal = pyqtSignal('QString')
    startProgressSignal = pyqtSignal()
    stopProgressSignal = pyqtSignal()

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.osmWidget = parent
        font = self.font()
        font.setPointSize(14)
        self.setFont(font)

        self.center_x = 0
        self.center_y = 0
        self.map_x = 0
        self.map_y = 0
        self.map_zoom = 9
        self.center_rlat = 0.0
        self.center_rlon = 0.0

        self.lastHeadingLat = 0.0
        self.lastHeadingLon = 0.0

        self.osmutils = OSMUtils()

        self.setContextMenuPolicy(Qt.DefaultContextMenu)
        self.moving = False
        self.mousePressed = False
        self.setMouseTracking(True)
        self.posStr = "+%.4f , +%.4f" % (0.0, 0.0)

        self.tileHome = defaultTileHome
        self.tileServer = defaultTileServer
        self.tileStartZoom = defaultTileStartZoom
        self.startZoom3DView = defaultStart3DZoom

        self.lastMouseMoveX = 0
        self.lastMouseMoveY = 0

        self.selectedEdgeId = None
        self.lastWayId = None
        self.recalcTrigger = 0
        self.mousePos = (0, 0)
        self.startPoint = None
        self.endPoint = None
        self.wayPoints = list()
        self.routeCalculationThread = None

        self.currentRoute = None
        self.routeList = list()
        self.wayInfo = None
        self.currentEdgeIndexList = None
        self.currentCoords = None
        self.distanceToEnd = 0
        self.distanceToCrossing = 0
        self.routeInfo = None, None, None, None
        self.nextEdgeOnRoute = None
        self.wayPOIList = None
        self.speedInfo = None

        self.currentEdgeList = None
        self.currentTrackList = None
        self.currentStartPoint = None
        self.currentTargetPoint = None
        self.currentRoutePart = 0

        self.lastCenterX = None
        self.lastCenterY = None
        self.withShowPOI = False
        self.withShowAreas = False
        self.showSky = False
        self.XAxisRotation = 60
        self.speed = 0
        self.track = None
        self.stop = True
        self.altitude = 0
        self.satelitesInUse = 0
        self.currentDisplayBBox = None
        self.show3D = True

#        self.setAttribute( Qt.WA_OpaquePaintEvent, True )
#        self.setAttribute( Qt.WA_NoSystemBackground, True )

        self.lastWayIdSet = None
        self.wayPolygonCache = dict()
        self.currentRouteOverlayPath = None
        self.areaPolygonCache = dict()
        self.lastOsmIdSet = None
        self.adminPolygonCache = dict()
        self.lastAdminLineIdSet = None
        self.tagLabelWays = None
        self.onewayWays = None

        self.style = OSMStyle()
        self.mapPoint = None
        self.isVirtualZoom = False
        self.virtualZoomValue = 2.0
        self.prefetchBBox = None
        self.sidebarVisible = True

        self.gisUtils = GISUtils()

    def getSidebarWidth(self):
        if self.sidebarVisible == True:
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
        self.routeList = routeList

    def getTileHomeFullPath(self):
        if os.path.isabs(self.tileHome):
            return self.tileHome
        else:
            return os.path.join(getTileRoot(), self.tileHome)

    def getTileFullPath(self, zoom, x, y):
        home = self.getTileHomeFullPath()
        tilePath = os.path.join(str(zoom), str(x), str(y) + ".png")
        fileName = os.path.join(home, tilePath)
        return fileName

    def minimumSizeHint(self):
        return QSize(minWidth, minHeight)

    def init(self):
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def osm_center_map_to_position(self, lat, lon):
        self.osm_center_map_to(self.osmutils.deg2rad(lat), self.osmutils.deg2rad(lon))

    def checkTileDirForZoom(self):
        tileDirForZoom = os.path.join(self.getTileHomeFullPath(), "%s" % self.map_zoom)
        if not os.path.isdir(tileDirForZoom):
            os.makedirs(tileDirForZoom)

    def osm_map_set_zoom (self, zoom):
        self.map_zoom = zoom
        if self.isVirtualZoom == True and zoom != MAX_ZOOM:
            self.isVirtualZoom = False

        self.clearPolygonCache()
        self.checkTileDirForZoom()

        self.osm_map_handle_resize()

    def osm_map_handle_resize (self):
        (self.center_y, self.center_x) = self.getPixelPosForLocationRad(self.center_rlat, self.center_rlon, False)
        self.center_coord_update()

    def getYOffsetForRotationMap(self):
        return self.height() / 3

    def calcMapZeroPos(self):
        map_x = int(self.center_x - self.width() / 2)
        map_y = int(self.center_y - self.height() / 2)
        return (map_x, map_y)

    def getMapZeroPos(self):
        return self.map_x, self.map_y

    def getMapPosition(self):
        return (self.osmutils.rad2deg(self.center_rlat), self.osmutils.rad2deg(self.center_rlon))

    def showTiles (self):
        width = self.width()
        height = self.width()
        map_x, map_y = self.getMapZeroPos()

        offset_x = -map_x % TILESIZE
        if offset_x == 0:
            offset_x = -TILESIZE

        offset_y = -map_y % TILESIZE
        if offset_y == 0:
            offset_y = -TILESIZE

        # print("%d %d %d %d"%(map_x, map_y, offset_x, offset_y))

        if offset_x >= 0:
            offset_x -= TILESIZE * 4
        if offset_y >= 0:
            offset_y -= TILESIZE * 4

#        print("%d %d"%(offset_x, offset_y))

        tiles_nx = int((width - offset_x) / TILESIZE + 1) + 2
        tiles_ny = int((height - offset_y) / TILESIZE + 1) + 2

        tile_x0 = int(math.floor((map_x - TILESIZE) / TILESIZE)) - 2
        tile_y0 = int(math.floor((map_y - TILESIZE) / TILESIZE)) - 2

        i = tile_x0
        j = tile_y0
        offset_y0 = offset_y

#        print("%d %d %d %d"%(tile_x0, tile_y0, tiles_nx, tiles_ny))
        while i < (tile_x0 + tiles_nx):
            while j < (tile_y0 + tiles_ny):
                if j < 0 or i < 0 or i >= math.exp(self.map_zoom * M_LN2) or j >= math.exp(self.map_zoom * M_LN2):
                    pixbuf = self.getEmptyTile()
                else:
                    pixbuf = self.getTile(self.map_zoom, i, j)

#                print("%d %d"%(i, j))
                self.drawPixmap(offset_x, offset_y, TILESIZE, TILESIZE, pixbuf)

                offset_y += TILESIZE
                j = j + 1
            offset_x += TILESIZE
            offset_y = offset_y0
            i = i + 1
            j = tile_y0

    def getTileFromFile(self, fileName):
#        print(fileName)
        pixbuf = QPixmap(fileName)
        return pixbuf

    def getTileForZoomFromFile(self, zoom, x, y):
        fileName = self.getTileFullPath(zoom, x, y)
        if os.path.exists(fileName):
            pixbuf = QPixmap(fileName)
            return pixbuf

        return None

    def drawPixmap(self, x, y, width, height, pixbuf):
        self.painter.drawPixmap(x, y, width, height, pixbuf)

    def getEmptyTile(self):
        emptyPixmap = QPixmap(TILESIZE, TILESIZE)
        emptyPixmap.fill(self.palette().color(QPalette.Normal, QPalette.Background))
        return emptyPixmap

    def findUpscaledTile (self, zoom, x, y):
        while zoom > 0:
            zoom = zoom - 1
            next_x = int(x / 2)
            next_y = int(y / 2)
#            print("search for bigger map for zoom "+str(zoom))

            pixbuf = self.getTileForZoomFromFile(zoom, next_x, next_y)
            if pixbuf != None:
                return (pixbuf, zoom)
            else:
                x = next_x
                y = next_y
        return (None, None)

    def getUpscaledTile(self, zoom, x, y):
#        print("search for bigger map for zoom "+str(zoom))
        (pixbuf, zoom_big) = self.findUpscaledTile(zoom, x, y)
        if pixbuf != None:
#            print("found exisiting tile on zoom "+str(zoom_big))
            zoom_diff = zoom - zoom_big

#            print("Upscaling by %d levels into tile %d,%d"%( zoom_diff, x, y))

            area_size = TILESIZE >> zoom_diff
            modulo = 1 << zoom_diff
            area_x = (x % modulo) * area_size
            area_y = (y % modulo) * area_size

            pixmapNew = pixbuf.copy(area_x, area_y, area_size, area_size)
            pixmapNew.scaled(TILESIZE, TILESIZE)
            return pixmapNew
        return None

    def getTile(self, zoom, x, y):
        fileName = self.getTileFullPath(zoom, x, y)

        if os.path.exists(fileName):
            pixbuf = self.getTileFromFile(fileName)
            return pixbuf
        else:
            self.osmWidget.downloadThread.addTile("/" + str(zoom) + "/" + str(x) + "/" + str(y) + ".png", fileName, self.tileServer)
            return self.getTilePlaceholder(zoom, x, y)

    def getTilePlaceholder(self, zoom, x, y):
        # try upscale lower zoom version
        pixbuf = self.getUpscaledTile(zoom, x, y)
        if pixbuf != None:
            return pixbuf
        else:
            return self.getEmptyTile()

    def displayMapPosition(self, mapPoint):
        pixmapWidth, pixmapHeight = self.getPixmapSizeForZoom(IMAGE_WIDTH_SMALL, IMAGE_WIDTH_SMALL)

        y, x = self.getTransformedPixelPosForLocationDeg(mapPoint.getPos()[0], mapPoint.getPos()[1])
        if self.isPointVisibleTransformed(x, y):
            self.orderedNodeList.append((x, y, pixmapWidth, pixmapHeight, None, None, None, self.style.getStylePixmap("mapPointPixmap")))
            self.displayRoutingPointRefPositions(mapPoint)

    def osm_center_map_to(self, lat, lon):
        if lat != 0.0 and lon != 0.0:
            (pixel_y, pixel_x) = self.getPixelPosForLocationRad(lat, lon, False)
            self.center_x = pixel_x
            self.center_y = pixel_y
            self.center_coord_update()
            self.update()

    def osm_map_scroll(self, dx, dy):
        self.stepInDirection(dx, dy)

    # for untransformed coords
    def isPointVisible(self, x, y):
        point = QPoint(x, y)
        skyMargin = 0
        if self.show3DView() == True and self.showSky == True:
            skyMargin = SKY_WIDTH

        point0 = self.transformHeading.map(point)
        rect = QRect(0, 0 + skyMargin, self.width(), self.height())
        return rect.contains(point0)

    # for already transformed coords
    def isPointVisibleTransformed(self, x, y):
        point = QPoint(x, y)
        skyMargin = 0
        if self.show3DView() == True and self.showSky == True:
            skyMargin = SKY_WIDTH

        rect = QRect(0, 0 + skyMargin, self.width(), self.height())
        return rect.contains(point)

    # bbox in deg (left, top, right, bottom)
    # only use if transform active
    def displayBBox(self, bbox, color):
        y, x = self.getPixelPosForLocationDeg(bbox[1], bbox[0], True)
        y1, x1 = self.getPixelPosForLocationDeg(bbox[3], bbox[2], True)

        point0 = QPointF(x, y)
        point1 = QPointF(x1, y1)

        rect = QRectF(point0, point1)

        self.painter.setPen(QPen(color))
        self.painter.drawRect(rect)

    def displayTrack(self, trackList):
        polygon = QPolygon()

        for gpsData in trackList:
            lat = gpsData.getLat()
            lon = gpsData.getLon()
            (y, x) = self.getPixelPosForLocationDeg(lat, lon, True)
            point = QPoint(x, y);
            polygon.append(point)

        pen = self.style.getStylePen("trackPen")
        pen.setWidth(self.style.getStreetPenWidthForZoom(self.map_zoom))
        self.painter.setPen(pen)
        self.painter.drawPolyline(polygon)

    # only use if transform is active
    def displayRoutingEdges(self, edgeList, expectedNextEdge):
        pen = QPen()
        pen.setWidth(3)
        if edgeList != None and len(edgeList) != 0:
            for edge in edgeList:
                _, _, _, _, _, _, _, _, _, _, coords = edge
                if expectedNextEdge != None and edge == expectedNextEdge:
                    pen.setColor(Qt.green)
                else:
                    pen.setColor(Qt.red)

                self.displayCoords(coords, pen)

    def displayExpectedEdge(self, edgeList, expectedNextEdge):
        pen = QPen()
        pen.setWidth(3)
        if edgeList != None and len(edgeList) != 0:
            for edge in edgeList:
                _, _, _, _, _, _, _, _, _, _, coords = edge
                if expectedNextEdge != None and edge == expectedNextEdge:
                    pen.setColor(Qt.green)
                    self.displayCoords(coords, pen)

    # only use if transform is active
    def displayApproachingRef(self, approachingRefPos):
        if approachingRefPos != None:
            pen = QPen()
            pen.setWidth(3)
            lat, lon = approachingRefPos

            y, x = self.getPixelPosForLocationDeg(lat, lon, True)
            if self.isPointVisible(x, y):
                pen.setColor(Qt.red)
                pen.setWidth(self.style.getPenWithForPoints(self.map_zoom))
                pen.setCapStyle(Qt.RoundCap)
                self.painter.setPen(pen)
                self.painter.drawPoint(x, y)
                return True

        return False

    def getVisibleBBoxDeg(self):
        invertedTransform = self.transformHeading.inverted()
        map_x, map_y = self.getMapZeroPos()

        skyMargin = 0
        if self.show3DView() == True and self.showSky == True:
            skyMargin = SKY_WIDTH

        point = QPointF(0, 0 + skyMargin)
        point0 = invertedTransform[0].map(point)
        lat1 = self.osmutils.rad2deg(self.osmutils.pixel2lat(self.map_zoom, map_y + point0.y()))
        lon1 = self.osmutils.rad2deg(self.osmutils.pixel2lon(self.map_zoom, map_x + point0.x()))

        point = QPointF(self.width(), 0 + skyMargin)
        point0 = invertedTransform[0].map(point)
        lat2 = self.osmutils.rad2deg(self.osmutils.pixel2lat(self.map_zoom, map_y + point0.y()))
        lon2 = self.osmutils.rad2deg(self.osmutils.pixel2lon(self.map_zoom, map_x + point0.x()))

        point = QPointF(0, self.height())
        point0 = invertedTransform[0].map(point)
        lat3 = self.osmutils.rad2deg(self.osmutils.pixel2lat(self.map_zoom, map_y + point0.y()))
        lon3 = self.osmutils.rad2deg(self.osmutils.pixel2lon(self.map_zoom, map_x + point0.x()))

        point = QPointF(self.width(), self.height())
        point0 = invertedTransform[0].map(point)
        lat4 = self.osmutils.rad2deg(self.osmutils.pixel2lat(self.map_zoom, map_y + point0.y()))
        lon4 = self.osmutils.rad2deg(self.osmutils.pixel2lon(self.map_zoom, map_x + point0.x()))

        lonList = [lon1, lon2, lon3, lon4]
        latList = [lat1, lat2, lat3, lat4]

        bboxLon1 = min(lonList)
        bboxLat1 = min(latList)
        bboxLon2 = max(lonList)
        bboxLat2 = max(latList)

        return [bboxLon1, bboxLat1, bboxLon2, bboxLat2]

    def show(self, zoom, lat, lon):
        self.osm_center_map_to_position(lat, lon)
        self.osm_map_set_zoom(zoom)
        self.update()

    def zoom(self, zoom):
        self.osmWidget.downloadThread.clearQueue()
        self.osm_map_set_zoom(zoom)
        self.update()

    def resizeEvent(self, event):
        self.clearPolygonCache()
        self.osm_map_handle_resize()

    def getTransform(self):
        transform = QTransform()

        map_x, map_y = self.getMapZeroPos()
        transform.translate(self.center_x - map_x, self.center_y - map_y)

        if self.show3DView() == True:
            transform.rotate(self.XAxisRotation, Qt.XAxis)

        if self.isVirtualZoom == True:
            transform.scale(self.virtualZoomValue, self.virtualZoomValue)

        transform.translate(-(self.center_x - map_x), -(self.center_y - map_y))

        return transform

    def getPrefetchBoxMargin(self):
        if self.map_zoom in range(17, 19):
            return 0.005
        if self.map_zoom in range(14, 17):
            return 0.02

        # approx 10km
        return 0.1

    # x,y in pixels for check if geom is in visible area
    def calcVisiblePolygon(self):
        skyMargin = 0
        if self.show3DView() == True and self.showSky == True:
            skyMargin = SKY_WIDTH

        invertedTransform = self.transformHeading.inverted()
        point = QPoint(0, 0 + skyMargin)
        point0 = invertedTransform[0].map(point)
        point = QPoint(self.width(), 0 + skyMargin)
        point1 = invertedTransform[0].map(point)
        point = QPoint(self.width(), self.height())
        point2 = invertedTransform[0].map(point)
        point = QPoint(0, self.height())
        point3 = invertedTransform[0].map(point)

        cont = [(point0.x(), point0.y()), (point1.x(), point1.y()), (point2.x(), point2.y()), (point3.x(), point3.y())]
        self.visibleCPolygon = Polygon(cont)

    # smaler one without control elements
    # e.g. for way tag positions so that they are not too
    # near to the border and not hidden behind
    def calcVisiblePolygon2(self):
        invertedTransform = self.transformHeading.inverted()
        point = QPoint(SCREEN_BORDER_WIDTH, 0 + SCREEN_BORDER_WIDTH);
        point0 = invertedTransform[0].map(point)
        point = QPoint(self.width() - SCREEN_BORDER_WIDTH, 0 + SCREEN_BORDER_WIDTH);
        point1 = invertedTransform[0].map(point)
        point = QPoint(self.width() - SCREEN_BORDER_WIDTH, self.height() - SCREEN_BORDER_WIDTH);
        point2 = invertedTransform[0].map(point)
        point = QPoint(SCREEN_BORDER_WIDTH, self.height() - SCREEN_BORDER_WIDTH);
        point3 = invertedTransform[0].map(point)

        cont = [(point0.x(), point0.y()), (point1.x(), point1.y()), (point2.x(), point2.y()), (point3.x(), point3.y())]
        self.visibleCPolygon2 = Polygon(cont)

    def calcPrefetchBox(self, bbox):
#        if self.track!=None:
#            self.prefetchBBox=self.calcTrackBasedPrefetchBox(self.track, bbox)
#        else:
        self.prefetchBBox = osmParserData.createBBoxWithMargin(bbox, self.getPrefetchBoxMargin())
        self.prefetchBBoxCPolygon = Polygon([(self.prefetchBBox[0], self.prefetchBBox[3]), (self.prefetchBBox[2], self.prefetchBBox[3]), (self.prefetchBBox[2], self.prefetchBBox[1]), (self.prefetchBBox[0], self.prefetchBBox[1])])

    def calcTrackBasedPrefetchBox(self, track, bbox):
        xmargin1 = 0
        ymargin1 = 0
        xmargin2 = 0
        ymargin2 = 0

        margin = self.getPrefetchBoxMargin()

        if (track > 315 and track <= 359) or (track >= 0 and track <= 45):
            xmargin1 = margin
            xmargin2 = margin
            ymargin2 = margin
        elif track > 45 and track <= 135:
            ymargin1 = margin
            xmargin2 = margin
            ymargin2 = margin
        elif track > 135 and track <= 225:
            xmargin1 = margin
            ymargin1 = margin
            xmargin2 = margin
        elif track > 225 and track <= 315:
            xmargin1 = margin
            ymargin1 = margin
            ymargin2 = margin

        latRangeMax = bbox[3] + ymargin2
        lonRangeMax = bbox[2] + xmargin2
        latRangeMin = bbox[1] - ymargin1
        lonRangeMin = bbox[0] - xmargin1

        return lonRangeMin, latRangeMin, lonRangeMax, latRangeMax

    def isNewBBox(self, bbox):
        bboxCPolyon = Polygon([(bbox[0], bbox[3]), (bbox[2], bbox[3]), (bbox[2], bbox[1]), (bbox[0], bbox[1])])
        if self.prefetchBBox == None:
            self.calcPrefetchBox(bbox)
            return True
        else:
            newBBox = not self.prefetchBBoxCPolygon.covers(bboxCPolyon)
            if newBBox == True:
#                print("newbbox")
                self.calcPrefetchBox(bbox)
                return True

        return False

    def setAntialiasing(self, value):
        if self.map_zoom >= self.style.USE_ANTIALIASING_START_ZOOM:
            self.painter.setRenderHint(QPainter.Antialiasing, value)
        else:
            self.painter.setRenderHint(QPainter.Antialiasing, False)

    def show3DView(self):
        return self.show3D == True and self.map_zoom >= self.startZoom3DView

    def paintEvent(self, event):
#        self.setCursor(Qt.WaitCursor)
        start = time.time()
        self.painter = QPainter(self)
        self.painter.setClipRect(QRectF(0, 0, self.width(), self.height()))

        self.painter.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setAntialiasing(True)

        self.painter.fillRect(0, 0, self.width(), self.height(), self.style.getStyleColor("mapBackgroundColor"))

        self.transformHeading = self.getTransform()

        self.painter.setTransform(self.transformHeading)

#        print(self.map_zoom)

        self.calcVisiblePolygon()
        self.calcVisiblePolygon2()
        bbox = self.getVisibleBBoxDeg()
        newBBox = self.isNewBBox(bbox)

#        countryStart=time.time()
#        countryList=osmParserData.buSimple.countryNameListOfBBox(self.prefetchBBox)
#        print("%s %f"%(countryList, time.time()-countryStart))

        self.numHiddenPolygons = 0
        self.numVisiblePolygons = 0
        self.numHiddenWays = 0
        self.numVisibleWays = 0
        self.numHiddenAdminLiness = 0
        self.numVisibleAdminLines = 0

        self.orderedNodeList = list()

        fetchStart = time.time()
        drawStart = time.time()

        if self.map_zoom > self.tileStartZoom:
            if newBBox == True:
                self.bridgeWays = list()
                self.tunnelWays = list()
                self.otherWays = list()
                self.railwayLines = list()
                self.railwayBridgeLines = list()
                self.railwayTunnelLines = list()
                self.areaList = list()
                self.naturalTunnelLines = list()
                self.buildingList = list()
                self.aerowayLines = list()
                self.tagLabelWays = dict()
                self.adminLineList = list()
                self.onewayWays = dict()

                fetchStart = time.time()

                self.getVisibleWays(self.prefetchBBox)
                self.getVisibleAdminLines(self.prefetchBBox)

            if self.withShowAreas == True:
                if newBBox == True:
                    if self.map_zoom > self.tileStartZoom:
                        self.getVisibleAreas(self.prefetchBBox)

                if WITH_TIMING_DEBUG == True:
                    print("paintEvent fetch polygons:%f" % (time.time() - fetchStart))

                drawStart = time.time()

                self.setAntialiasing(False)
                self.displayTunnelRailways()
                self.displayTunnelNatural()
                self.displayAreas()

            self.displayAdminLines()

            self.setAntialiasing(True)
            self.displayTunnelWays()

            if self.withShowAreas == True:
                self.setAntialiasing(False)
                self.displayBuildings()

            self.setAntialiasing(True)
            self.displayWays()

            if self.withShowAreas == True:
                self.setAntialiasing(False)
                self.displayAeroways()
                self.displayRailways()
                self.displayBridgeRailways()

            self.setAntialiasing(True)
            self.displayBridgeWays()

            if WITH_TIMING_DEBUG == True:
                print("paintEvent draw polygons:%f" % (time.time() - drawStart))

        else:
            self.showTiles()

        if self.currentRoute != None and self.routeCalculationThread != None and not self.routeCalculationThread.isRunning():
            self.displayRoute(self.currentRoute)

        if self.currentCoords != None:
            pen = self.style.getStylePen("edgePen")
            pen.setWidth(self.style.getStreetPenWidthForZoom(self.map_zoom))
            self.displayCoords(self.currentCoords, pen)

        if self.map_zoom >= self.style.SHOW_ONEWAY_START_ZOOM:
            if self.onewayWays != None and len(self.onewayWays) != 0:
                self.displayOnewayOverlays(self.onewayWays)

        self.painter.resetTransform()

        if self.show3DView() == True and self.showSky == True:
            skyRect = QRectF(0, 0, self.width(), SKY_WIDTH)
            gradient = QLinearGradient(skyRect.topLeft(), skyRect.bottomLeft())
            gradient.setColorAt(1, self.style.getStyleColor("mapBackgroundColor"))
            gradient.setColorAt(0, Qt.blue)
            self.painter.fillRect(skyRect, gradient)

        self.painter.setRenderHint(QPainter.Antialiasing)

        if self.withShowPOI == True:
            # not prefetch box!
            self.displayVisibleNodes(bbox)

        if self.mapPoint != None:
            self.displayMapPosition(self.mapPoint)

        self.displayRoutingPoints()

        # sort by y voordinate
        # farthest nodes (smaller y coordinate) are drawn first
        if self.show3DView() == True:
            self.orderedNodeList.sort(key=self.nodeSortByYCoordinate, reverse=False)

        self.displayNodes()

        if self.map_zoom >= self.style.SHOW_REF_LABEL_WAYS_START_ZOOM:
            if self.tagLabelWays != None and len(self.tagLabelWays) != 0:
                tagStart = time.time()
                self.displayWayTags(self.tagLabelWays)

        self.displaySidebar()
        self.showEnforcementInfo()
        self.showTextInfoBackground()

        if self.currentRoute != None and self.currentTrackList != None and not self.currentRoute.isRouteFinished():
            self.displayRouteInfo()

        self.showTextInfo()
        self.showSpeedInfo()

        self.painter.end()

        if WITH_TIMING_DEBUG == True:
            print("displayedPolgons: %d hiddenPolygons: %d" % (self.numVisiblePolygons, self.numHiddenPolygons))
            print("displayedWays: %d hiddenWays: %d" % (self.numVisibleWays, self.numHiddenWays))
            print("displayedAdminLines: %d hiddenAdminLines: %d" % (self.numVisibleAdminLines, self.numHiddenAdminLiness))

            print("paintEvent:%f" % (time.time() - start))

    def displaySidebar(self):
        diff = 40 - 32
        if self.sidebarVisible == True:
            textBackground = QRect(self.width() - SIDEBAR_WIDTH, 0, SIDEBAR_WIDTH, self.height())
            self.painter.fillRect(textBackground, self.style.getStyleColor("backgroundColor"))

            self.painter.drawPixmap(self.width() - SIDEBAR_WIDTH + diff / 2, diff / 2, IMAGE_WIDTH, IMAGE_HEIGHT, self.style.getStylePixmap("minusPixmap"))
            self.minusRect = QRect(self.width() - SIDEBAR_WIDTH + diff / 2, diff / 2, IMAGE_WIDTH, IMAGE_HEIGHT)

            self.painter.drawPixmap(self.width() - SIDEBAR_WIDTH + diff / 2, IMAGE_HEIGHT + diff / 2, IMAGE_WIDTH, IMAGE_HEIGHT, self.style.getStylePixmap("plusPixmap"))
            self.plusRect = QRect(self.width() - SIDEBAR_WIDTH + diff / 2, IMAGE_HEIGHT + diff / 2, IMAGE_WIDTH, IMAGE_HEIGHT)

            self.painter.drawPixmap(self.width() - SIDEBAR_WIDTH + diff / 2, 2 * IMAGE_HEIGHT + diff / 2, IMAGE_WIDTH, IMAGE_HEIGHT, self.style.getStylePixmap("searchPixmap"))
            self.searchRect = QRect(self.width() - SIDEBAR_WIDTH + diff / 2, 2 * IMAGE_HEIGHT + diff / 2, IMAGE_WIDTH, IMAGE_HEIGHT)

            self.painter.drawPixmap(self.width() - SIDEBAR_WIDTH + diff / 2, 3 * IMAGE_HEIGHT + diff / 2, IMAGE_WIDTH, IMAGE_HEIGHT, self.style.getStylePixmap("favoritesPixmap"))
            self.favoriteRect = QRect(self.width() - SIDEBAR_WIDTH + diff / 2, 3 * IMAGE_HEIGHT + diff / 2, IMAGE_WIDTH, IMAGE_HEIGHT)

            self.painter.drawPixmap(self.width() - SIDEBAR_WIDTH + diff / 2, 4 * IMAGE_HEIGHT + diff / 2, IMAGE_WIDTH, IMAGE_HEIGHT, self.style.getStylePixmap("routePixmap"))
            self.routesRect = QRect(self.width() - SIDEBAR_WIDTH + diff / 2, 4 * IMAGE_HEIGHT + diff / 2, IMAGE_WIDTH, IMAGE_HEIGHT)

            self.painter.drawPixmap(self.width() - SIDEBAR_WIDTH + diff / 2, self.height() - 2 * IMAGE_HEIGHT + diff / 2, IMAGE_WIDTH, IMAGE_HEIGHT, self.style.getStylePixmap("settingsPixmap"))
            self.optionsRect = QRect(self.width() - SIDEBAR_WIDTH + diff / 2, self.height() - 2 * IMAGE_HEIGHT + diff / 2, IMAGE_WIDTH, IMAGE_HEIGHT)

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

        elif self.map_zoom in range(self.tileStartZoom + 1, 15):
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

    def getAdminLevelListForZoom(self):
        return Constants.ADMIN_LEVEL_DISPLAY_SET

    def clearPolygonCache(self):
        self.prefetchBBox = None
        self.wayPolygonCache = dict()
        self.areaPolygonCache = dict()
        self.adminPolygonCache = dict()

    def getVisibleAdminLines(self, bbox):
        start = time.time()
        adminLevels = self.getAdminLevelListForZoom()
        adminLineList, adminLineIdSet = osmParserData.getAdminLinesInBboxWithGeom(bbox, 0.0, adminLevels)

        if WITH_TIMING_DEBUG == True:
            print("getAdminLinesInBboxWithGeom: %f" % (time.time() - start))

        if self.lastAdminLineIdSet == None:
            self.lastAdminLineIdSet = adminLineIdSet
        else:
            removedLines = self.lastAdminLineIdSet - adminLineIdSet
            self.lastAdminLineIdSet = adminLineIdSet

            for lineId in removedLines:
                if lineId in self.adminPolygonCache.keys():
                    del self.adminPolygonCache[lineId]

        self.adminLineList = adminLineList

    def displayAdminLines(self):
        pen = self.style.getStylePen("adminArea")
        for line in self.adminLineList:
            adminLevel = line[0]
            lineCoords = line[1]
            if adminLevel == 2:
                pen.setStyle(Qt.SolidLine)
            else:
                pen.setStyle(Qt.DotLine)
            pen.setWidth(self.style.getAdminPenWidthForZoom(self.map_zoom, adminLevel))
            self.displayAdminLineWithCache(lineCoords, pen)

    def getVisibleWays(self, bbox):
        streetTypeList = self.getStreetTypeListForZoom()
        if streetTypeList == None:
            return

        start = time.time()
#        if self.map_zoom>=14:
#            resultList, wayIdSet=osmParserData.getWaysInBboxWithGeom(bbox, 0.0, streetTypeList)
#        elif self.map_zoom>=12:
#            resultList, wayIdSet=osmParserData.getWaysInBboxWithGeom(bbox, 0.0, streetTypeList, True, 50.0)
#        elif self.map_zoom>self.tileStartZoom:
#            resultList, wayIdSet=osmParserData.getWaysInBboxWithGeom(bbox, 0.0, streetTypeList, True, 100.0)

        if self.map_zoom > self.tileStartZoom:
            resultList, wayIdSet = osmParserData.getWaysInBboxWithGeom(bbox, 0.0, streetTypeList)

        if WITH_TIMING_DEBUG == True:
            print("getWaysInBboxWithGeom: %f" % (time.time() - start))

        if self.lastWayIdSet == None:
            self.lastWayIdSet = wayIdSet
        else:
            removedWays = self.lastWayIdSet - wayIdSet
            self.lastWayIdSet = wayIdSet

            for wayId in removedWays:
                if wayId in self.wayPolygonCache.keys():
                    del self.wayPolygonCache[wayId]

        for way in resultList:
            wayId, _, _, streetInfo, _, _, _, _, _, _ = way
            streetTypeId, oneway, roundabout, tunnel, bridge = osmParserData.decodeStreetInfo2(streetInfo)

            if self.map_zoom >= self.style.SHOW_NAME_LABEL_WAYS_START_ZOOM:
                if streetTypeId in Constants.NAME_LABEL_WAY_SET:
                    self.tagLabelWays[wayId] = way

            elif self.map_zoom >= self.style.SHOW_REF_LABEL_WAYS_START_ZOOM:
                if streetTypeId in Constants.REF_LABEL_WAY_SET:
                    self.tagLabelWays[wayId] = way

            if oneway != 0:
                self.onewayWays[wayId] = way

            if bridge == 1:
                self.bridgeWays.append(way)
                continue

            if tunnel == 1:
                self.tunnelWays.append(way)
                continue

            self.otherWays.append(way)

    def getVisibleNodeForWayTag(self, wayPainterPath):
        for tagLabelPoint in range(1, 9, 1):
            point = wayPainterPath.pointAtPercent(tagLabelPoint / 10)
            if self.visibleCPolygon2.isInside(point.x(), point.y()):
                return point

        return None

    def getWayTagText(self, name, nameRef):
        onlyRefs = False
        if self.map_zoom >= self.style.SHOW_REF_LABEL_WAYS_START_ZOOM and self.map_zoom < self.style.SHOW_NAME_LABEL_WAYS_START_ZOOM:
            onlyRefs = True

        tagText = None
        if onlyRefs == True:
            if nameRef != None:
                tagText = nameRef
        else:
            if name != None:
                tagText = name
                if nameRef != None:
                    tagText = tagText + ":" + nameRef
        return tagText

    def displayOnewayOverlays(self, onewayWays):
        if onewayWays != None and len(onewayWays) != 0:
            for way in onewayWays.values():
                wayId, _, _, streetInfo, name, nameRef, _, _, _, _ = way

                if wayId in self.wayPolygonCache.keys():
                    _, wayPainterPath = self.wayPolygonCache[wayId]

                    streetTypeId, oneway, roundabout, _, _ = osmParserData.decodeStreetInfo2(streetInfo)

                    if roundabout == 1:
                        continue

                    pixmap = None
                    if oneway == 1:
                        pixmap = self.style.getStylePixmap("oneway-right")
                    elif oneway == 2:
                        pixmap = self.style.getStylePixmap("oneway-left")

                    if pixmap != None:
                        self.drawImageOnPainterPath(wayPainterPath, pixmap, 16, 14)

    def drawImageOnPainterPath(self, painterPath, pixmap, width, height):
        map_x, map_y = self.getMapZeroPos()

        for i in range(10, 90, 79):
            percent = i / 100

            point = painterPath.pointAtPercent(percent)
            point0 = QPointF(point.x() - map_x, point.y() - map_y)
            if not self.visibleCPolygon.isInside(point0.x(), point0.y()):
                continue

            angle = painterPath.angleAtPercent(percent)

            self.painter.save()
            self.painter.translate(point0)
            self.painter.rotate(-angle)
            self.painter.drawPixmap(-width / 2, -height / 2, width, height, pixmap)
            self.painter.restore()

    def displayWayTags(self, tagLabelWays):
        if tagLabelWays != None and len(tagLabelWays) != 0:
            font = self.style.getFontForTextDisplay(self.map_zoom, self.isVirtualZoom)
            if font == None:
                return

            numVisibleTags = 0
            numHiddenTags = 0

            map_x, map_y = self.getMapZeroPos()
            brush = self.style.getStyleBrush("placeTag")
            pen = self.style.getStylePen("placePen")

            # painterPathDict=dict()
            visibleWayTagStrings = set()
            for way in tagLabelWays.values():
                wayId, _, _, streetInfo, name, nameRef, _, _, _, _ = way

                streetTypeId, _, _, _, _ = osmParserData.decodeStreetInfo2(streetInfo)
                brush.setColor(self.style.getStyleColor(streetTypeId))

                if wayId in self.wayPolygonCache.keys():
                    _, wayPainterPath = self.wayPolygonCache[wayId]

                    tagText = self.getWayTagText(name, nameRef)

                    if tagText != None:
                        wayPainterPath = wayPainterPath.translated(-map_x, -map_y)
                        point = self.getVisibleNodeForWayTag(wayPainterPath)

                        if point != None:
                            numVisibleTags = numVisibleTags + 1

                            if not tagText in visibleWayTagStrings:
                                visibleWayTagStrings.add(tagText)
                                point0 = self.transformHeading.map(point)
                                painterPath, painterPathText = self.createTextLabel(tagText, font)
                                painterPath, painterPathText = self.moveTextLabelToPos(point0.x(), point0.y(), painterPath, painterPathText)

                                # painterPathDict[wayId]=(painterPath, painterPathText)
                                self.displayTextLabel(painterPath, painterPathText, brush, pen)
                        else:
                            numHiddenTags = numHiddenTags + 1

            # for wayId, (tagPainterPath, tagPainterPathText) in painterPathDict.items():
            #    self.displayTextLabel(tagPainterPath, tagPainterPathText, brush, pen)

            if WITH_TIMING_DEBUG == True:
                print("visible tags:%d hidden tags:%d" % (numVisibleTags, numHiddenTags))

    # find position of tag for driving mode
    # should be as near as possible to the crossing but
    # should not overlap with others
    def calcWayTagPlacement(self, wayPainterPath, reverseRefs, tagPainterPath, tagPainterPathText):
        if reverseRefs == False:
            percent = wayPainterPath.percentAtLength(80)
            point = wayPainterPath.pointAtPercent(percent)
            if self.visibleCPolygon2.isInside(point.x(), point.y()):
                point0 = self.transformHeading.map(point)
                newTagPainterPath, newTagPainterPathText = self.moveTextLabelToPos(point0.x(), point0.y(), tagPainterPath, tagPainterPathText)
                return newTagPainterPath, newTagPainterPathText
        else:
            percent = wayPainterPath.percentAtLength(wayPainterPath.length() - 80)
            point = wayPainterPath.pointAtPercent(percent)
            if self.visibleCPolygon2.isInside(point.x(), point.y()):
                point0 = self.transformHeading.map(point)
                newTagPainterPath, newTagPainterPathText = self.moveTextLabelToPos(point0.x(), point0.y(), tagPainterPath, tagPainterPathText)
                return newTagPainterPath, newTagPainterPathText

        return None, None

    def displayWayTagsForRouting(self, tagLabelWays):
        if tagLabelWays != None and len(tagLabelWays) != 0:
            font = self.style.getFontForTextDisplay(self.map_zoom, self.isVirtualZoom)
            if font == None:
                return

            map_x, map_y = self.getMapZeroPos()
            brush = self.style.getStyleBrush("placeTag")
            pen = self.style.getStylePen("placePen")

            # painterPathDict=dict()
            for way, reverseRefs in tagLabelWays.values():
                wayId, _, _, streetInfo, name, nameRef, _, _, _, _ = way

                streetTypeId, _, _, _, _ = osmParserData.decodeStreetInfo2(streetInfo)
                brush.setColor(self.style.getStyleColor(streetTypeId))

                if wayId in self.wayPolygonCache.keys():
                    _, wayPainterPath = self.wayPolygonCache[wayId]

                    tagText = self.getWayTagText(name, nameRef)

                    if tagText != None:
                        wayPainterPath = wayPainterPath.translated(-map_x, -map_y)
                        tagPainterPath, tagPainterPathText = self.createTextLabel(tagText, font)

                        newTagPainterPath, newTagPainterPathText = self.calcWayTagPlacement(wayPainterPath, reverseRefs, tagPainterPath, tagPainterPathText)

                        if newTagPainterPath != None:
                            # painterPathDict[wayId]=(newTagPainterPath, newTagPainterPathText)
                            self.displayTextLabel(newTagPainterPath, newTagPainterPathText, brush, pen)

            # for wayId, (tagPainterPath, tagPainterPathText) in painterPathDict.items():
            #    self.displayTextLabel(tagPainterPath, tagPainterPathText, brush, pen)

    def displayWays(self):
        showCasing = self.map_zoom in range(OSMStyle.SHOW_CASING_START_ZOOM, 19)
        showStreetOverlays = self.map_zoom in range(OSMStyle.SHOW_STREET_OVERLAY_START_ZOOM, 19)

        # casing
        if showCasing == True:
            for way in self.otherWays:
                _, tags, _, streetInfo, _, _, _, _, _, _ = way
                streetTypeId, oneway, roundabout, _, _ = osmParserData.decodeStreetInfo2(streetInfo)
                pen = self.style.getRoadPen(streetTypeId, self.map_zoom, showCasing, False, True, False, False, False, tags)
                self.displayWayWithCache(way, pen)

        # fill
        for way in self.otherWays:
            _, tags, _, streetInfo, _, _, _, _, _, _ = way
            streetTypeId, oneway, roundabout, _, _ = osmParserData.decodeStreetInfo2(streetInfo)
            pen = self.style.getRoadPen(streetTypeId, self.map_zoom, False, False, False, False, False, False, tags)
            self.displayWayWithCache(way, pen)

            if showStreetOverlays == True:
                if osmParserData.isAccessRestricted(tags):
                    pen = self.style.getRoadPen(streetTypeId, self.map_zoom, False, False, False, False, True, False, tags)
                    self.displayWayWithCache(way, pen)

#                # TODO: mark oneway direction
#                elif (oneway!=0 and roundabout==0) and streetTypeId in self.getStreetTypeListForOneway():
#                    pen=self.style.getRoadPen(streetTypeId, self.map_zoom, False, True, False, False, False, False, tags)
#                    self.displayWayWithCache(way, pen)

                elif streetTypeId == Constants.STREET_TYPE_LIVING_STREET:
                    pen = self.style.getRoadPen(streetTypeId, self.map_zoom, False, False, False, False, False, True, tags)
                    self.displayWayWithCache(way, pen)

    def displayBridgeWays(self):
        if len(self.bridgeWays) != 0:
            showStreetOverlays = self.map_zoom in range(OSMStyle.SHOW_STREET_OVERLAY_START_ZOOM, 19)
            showBridges = self.map_zoom in range(OSMStyle.SHOW_BRIDGES_START_ZOOM, 19)

            # bridges
            for way in self.bridgeWays:
                _, tags, _, streetInfo, _, _, _, _, _, _ = way
                streetTypeId, oneway, _, _, _ = osmParserData.decodeStreetInfo2(streetInfo)
                if showBridges == True:
                    pen = self.style.getRoadPen(streetTypeId, self.map_zoom, False, False, False, True, False, False, tags)
                    self.displayWayWithCache(way, pen)

                pen = self.style.getRoadPen(streetTypeId, self.map_zoom, False, False, False, False, False, False, tags)
                self.displayWayWithCache(way, pen)

                if showStreetOverlays == True:
                    if osmParserData.isAccessRestricted(tags):
                        pen = self.style.getRoadPen(streetTypeId, self.map_zoom, False, False, False, False, True, False, tags)
                        self.displayWayWithCache(way, pen)

    def displayTunnelWays(self):
        showCasing = True
        if showCasing == True:
            for way in self.tunnelWays:
                _, tags, _, streetInfo, _, _, _, _, _, _ = way
                streetTypeId, oneway, _, _, _ = osmParserData.decodeStreetInfo2(streetInfo)
                pen = self.style.getRoadPen(streetTypeId, self.map_zoom, showCasing, False, True, False, False, False, tags)
                self.displayWayWithCache(way, pen)

        for way in self.tunnelWays:
            _, tags, _, streetInfo, _, _, _, _, _, _ = way
            streetTypeId, oneway, _, _, _ = osmParserData.decodeStreetInfo2(streetInfo)
            pen = self.style.getRoadPen(streetTypeId, self.map_zoom, False, False, True, False, False, False, tags)
            self.displayWayWithCache(way, pen)

    def getDisplayPOITypeListForZoom(self):
        if self.map_zoom in range(self.tileStartZoom + 1, 19):
            return self.style.getDisplayPOIListForZoom(self.map_zoom)

    def getPixmapForNodeType(self, nodeType):
        return self.style.getPixmapForNodeType(nodeType)

    def getPixmapSizeForZoom(self, baseWidth, baseHeight):
        if self.isVirtualZoom == True:
            return (int(baseWidth * self.virtualZoomValue), int(baseHeight * self.virtualZoomValue))

        if self.map_zoom == 18:
            return (int(baseWidth * 1.5), int(baseHeight * 1.5))
        elif self.map_zoom == 17:
            return (baseWidth, baseHeight)

        return (int(baseWidth * 0.8), int(baseHeight * 0.8))

    # sort by y value
    def nodeSortByYCoordinate(self, item):
        return item[1]

    def getNodeInfoForPos(self, pos):
        pixmapWidth, pixmapHeight = self.getPixmapSizeForZoom(IMAGE_WIDTH_SMALL, IMAGE_HEIGHT_SMALL)

        for  x, y, pixmapWidth, pixmapHeight, refId, tags, _, _ in self.orderedNodeList:
            rect = QRect(int(x - pixmapWidth / 2), int(y - pixmapHeight), pixmapWidth, pixmapHeight)
            if rect.contains(pos, proper=False):
                return refId, tags

        return None, None

    # for debugging
    def getAreaTagsForPos(self, pos):
        # the polygons are transformed
        point0 = self.transformHeading.inverted()[0].map(pos)
        map_x, map_y = self.getMapZeroPos()

        for osmId, (_, painterPath, geomType) in self.areaPolygonCache.items():
            if geomType == 0:
                painterPath = painterPath.translated(-map_x, -map_y)
                if painterPath.contains(point0):
                    tags = osmParserData.getAreaTagsWithId(osmId)
                    if tags != None:
                        print("%d %s" % (osmId, tags))

    def event(self, event):
        if event.type() == QEvent.ToolTip:
            mousePos = QPoint(event.x(), event.y())
            if self.sidebarVisible == True:
                if self.searchRect.contains(mousePos):
                    QToolTip.showText(event.globalPos(), "Search")
                    return True
                elif self.favoriteRect.contains(mousePos):
                    QToolTip.showText(event.globalPos(), "Select favorite")
                    return True
                elif self.routesRect.contains(mousePos):
                    QToolTip.showText(event.globalPos(), "Load route")
                    return True
                elif self.optionsRect.contains(mousePos):
                    QToolTip.showText(event.globalPos(), "Settings")
                    return True

            if self.plusRect.contains(mousePos):
                QToolTip.showText(event.globalPos(), "+ Zoom %d" % (self.map_zoom))
                return True

            if self.minusRect.contains(mousePos):
                QToolTip.showText(event.globalPos(), "- Zoom %d" % (self.map_zoom))
                return True

            refId, tags = self.getNodeInfoForPos(mousePos)
            if tags != None:
                displayString = osmParserData.getPOITagString(tags)
                QToolTip.showText(event.globalPos(), displayString)

            else:
                QToolTip.hideText()
                event.ignore()

            return True

        return super(QtOSMWidget, self).event(event)

    def displayVisibleNodes(self, bbox):
        nodeTypeList = self.getDisplayPOITypeListForZoom()
        if nodeTypeList == None or len(nodeTypeList) == 0:
            return

        start = time.time()
        resultList = osmParserData.getPOINodesInBBoxWithGeom(bbox, 0.0, nodeTypeList)

        if WITH_TIMING_DEBUG == True:
            print("getPOINodesInBBoxWithGeom: %f" % (time.time() - start))

        pixmapWidth, pixmapHeight = self.getPixmapSizeForZoom(IMAGE_WIDTH_SMALL, IMAGE_HEIGHT_SMALL)

        numVisibleNodes = 0
        numHiddenNodes = 0

        for node in resultList:
            refId, lat, lon, tags, nodeType = node
            (y, x) = self.getTransformedPixelPosForLocationDeg(lat, lon)
            if self.isPointVisibleTransformed(x, y):
                self.orderedNodeList.append((x, y, pixmapWidth, pixmapHeight, refId, tags, nodeType, None))
                numVisibleNodes = numVisibleNodes + 1
            else:
                numHiddenNodes = numHiddenNodes + 1

        if WITH_TIMING_DEBUG == True:
            print("visible nodes: %d hidden nodes:%d" % (numVisibleNodes, numHiddenNodes))

    def displayNodes(self):
        start = time.time()

        for  x, y, pixmapWidth, pixmapHeight, refId, tags, nodeType, pixmap in self.orderedNodeList:
            if pixmap == None:
                self.displayNode(x, y, pixmapWidth, pixmapHeight, refId, tags, nodeType)
            else:
                self.painter.drawPixmap(int(x - pixmapWidth / 2), int(y - pixmapHeight), pixmapWidth, pixmapHeight, pixmap)

        if WITH_TIMING_DEBUG == True:
            print("displayNodes: %f" % (time.time() - start))

    def displayNode(self, x, y, pixmapWidth, pixmapHeight, refId, tags, nodeType):
        if nodeType == Constants.POI_TYPE_PLACE:
            if "name" in tags:
#                print("%d %s"%(refId, tags))
                text = tags["name"]
                placeType = tags["place"]

                if self.style.displayPlaceTypeForZoom(placeType, self.map_zoom):
                    font = self.style.getFontForPlaceTagDisplay(tags, self.map_zoom, self.isVirtualZoom)
                    if font != None:
                        painterPath, painterPathText = self.createTextLabel(text, font)
                        painterPath, painterPathText = self.moveTextLabelToPos(x, y, painterPath, painterPathText)
                        self.displayTextLabel(painterPath, painterPathText, self.style.getStyleBrush("placeTag"), self.style.getStylePen("placePen"))
            return

        if nodeType == Constants.POI_TYPE_MOTORWAY_JUNCTION:
            if "name" in tags:
                text = tags["name"]
                if "ref" in tags:
                    ref = tags["ref"]
                    text = "%s:%s" % (text, ref)

                font = self.style.getFontForTextDisplay(self.map_zoom, self.isVirtualZoom)
                if font != None:
                    painterPath, painterPathText = self.createTextLabel(text, font)
                    painterPath, painterPathText = self.moveTextLabelToPos(x, y, painterPath, painterPathText)
                    self.displayTextLabel(painterPath, painterPathText, self.style.getStyleBrush("placeTag"), self.style.getStylePen("placePen"))
            return

        pixmap = self.getPixmapForNodeType(nodeType)
        if pixmap != None:
            xPos = int(x - pixmapWidth / 2)
            yPos = int(y - pixmapHeight)
            self.painter.drawPixmap(xPos, yPos, pixmapWidth, pixmapHeight, self.getPixmapForNodeType(nodeType))

    def moveTextLabelToPos(self, x, y, painterPath, painterPathText):
        xPosRect = x - painterPath.boundingRect().width() / 2
        yPosRect = y - painterPath.boundingRect().height()

        painterPath = painterPath.translated(xPosRect, yPosRect)
        painterPathText = painterPathText.translated(xPosRect, yPosRect)

        return painterPath, painterPathText

    def createTextLabel(self, text, font):
        fm = QFontMetrics(font)
        width = fm.width(text) + 20
        height = fm.height() + 10
        arrowHeight = 10
        arrowWidth = 5

        painterPath = QPainterPath()

        painterPath.moveTo(QPointF(0, 0))
        painterPath.lineTo(QPointF(width, 0))
        painterPath.lineTo(QPointF(width, height))
        painterPath.lineTo(QPointF(width - width / 2 + arrowWidth, height))
        painterPath.lineTo(QPointF(width - width / 2, height + arrowHeight))
        painterPath.lineTo(QPointF(width - width / 2 - arrowWidth, height))
        painterPath.lineTo(QPointF(0, height))
        painterPath.closeSubpath()

        painterPathText = QPainterPath()
        textPos = QPointF(10, height - 5 - fm.descent())
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
        if self.map_zoom in range(self.tileStartZoom + 1, 19):
            return self.style.getDisplayAreaListForZoom(self.map_zoom)

        return None

    def getVisibleAreas(self, bbox):
        areaTypeList = self.getDisplayAreaTypeListForZoom()
        if areaTypeList == None or len(areaTypeList) == 0:
            return

        start = time.time()
        if self.map_zoom >= 15:
            resultList, osmIdSet = osmParserData.getAreasInBboxWithGeom(areaTypeList, bbox, 0.0)
        elif self.map_zoom >= 14:
            resultList, osmIdSet = osmParserData.getAreasInBboxWithGeom(areaTypeList, bbox, 0.0, True, 50.0)
        elif self.map_zoom > self.tileStartZoom:
            resultList, osmIdSet = osmParserData.getAreasInBboxWithGeom(areaTypeList, bbox, 0.0, True, 100.0)

        if WITH_TIMING_DEBUG == True:
            print("getAreasInBboxWithGeom: %f" % (time.time() - start))

        if self.lastOsmIdSet == None:
            self.lastOsmIdSet = osmIdSet
        else:
            removedAreas = self.lastOsmIdSet - osmIdSet
            self.lastOsmIdSet = osmIdSet

            for osmId in removedAreas:
                if osmId in self.areaPolygonCache.keys():
                    del self.areaPolygonCache[osmId]

        for area in resultList:
            osmId, areaType, tags, _, _, _ = area

            bridge = "bridge" in tags and tags["bridge"] == "yes"
            tunnel = "tunnel" in tags and tags["tunnel"] == "yes"

            if areaType == Constants.AREA_TYPE_RAILWAY:
                if tags["railway"] == "rail":
                    if bridge == True:
                        self.railwayBridgeLines.append(area)
                        continue

                    if tunnel == True:
                        self.railwayTunnelLines.append(area)
                        continue

                    self.railwayLines.append(area)
                    continue

            if areaType == Constants.AREA_TYPE_NATURAL:
                if tunnel == True:
                    self.naturalTunnelLines.append(area)
                    continue

            if areaType == Constants.AREA_TYPE_BUILDING:
                self.buildingList.append(area)
                continue

            if areaType == Constants.AREA_TYPE_AEROWAY:
                if tags["aeroway"] == "runway" or tags["aeroway"] == "taxiway":
                    self.aerowayLines.append(area)
                    continue

            self.areaList.append(area)

    def displayTunnelNatural(self):
        if len(self.naturalTunnelLines) != 0:
            brush = Qt.NoBrush

            for area in self.naturalTunnelLines:
                tags = area[2]
                if "waterway" in tags:
                    pen = self.style.getStylePen("waterwayTunnelPen")
                    pen.setWidth(self.style.getWaterwayPenWidthForZoom(self.map_zoom, tags))
                    self.displayPolygonWithCache(self.areaPolygonCache, area, pen, brush)

    def displayAreas(self):
        for area in self.areaList:
            areaType = area[1]
            tags = area[2]
            brush = Qt.NoBrush
            pen = Qt.NoPen

            if areaType == Constants.AREA_TYPE_LANDUSE:
                brush, pen = self.style.getBrushForLanduseArea(tags, self.map_zoom)

            elif areaType == Constants.AREA_TYPE_NATURAL:
                brush, pen = self.style.getBrushForNaturalArea(tags, self.map_zoom)
                # TODO: natural areas with landuse
                if "landuse" in tags:
                    brush, pen = self.style.getBrushForLanduseArea(tags, self.map_zoom)
                    self.displayPolygonWithCache(self.areaPolygonCache, area, pen, brush)
                    self.painter.setBrush(Qt.NoBrush)
                    continue

            elif areaType == Constants.AREA_TYPE_HIGHWAY_AREA:
                brush = self.style.getStyleBrush("highwayArea")

            elif areaType == Constants.AREA_TYPE_AEROWAY:
                brush = self.style.getStyleBrush("aerowayArea")

            elif areaType == Constants.AREA_TYPE_TOURISM:
                brush, pen = self.style.getBrushForTourismArea(tags, self.map_zoom)

            elif areaType == Constants.AREA_TYPE_AMENITY:
                brush, pen = self.style.getBrushForAmenityArea(tags, self.map_zoom)

            elif areaType == Constants.AREA_TYPE_LEISURE:
                brush, pen = self.style.getBrushForLeisureArea(tags, self.map_zoom)

            else:
                continue

            self.displayPolygonWithCache(self.areaPolygonCache, area, pen, brush)

        self.painter.setBrush(Qt.NoBrush)

    def displayBuildings(self):
        if len(self.buildingList) != 0:
            pen = Qt.NoPen

            for area in self.buildingList:
                brush = self.style.getStyleBrush("building")
                self.displayPolygonWithCache(self.areaPolygonCache, area, pen, brush)

            self.painter.setBrush(Qt.NoBrush)

    def displayBridgeRailways(self):
        if len(self.railwayBridgeLines) != 0:
            brush = Qt.NoBrush
            showBridges = self.map_zoom in range(OSMStyle.SHOW_BRIDGES_START_ZOOM, 19)

            for area in self.railwayBridgeLines:
                tags = area[2]

                width = self.style.getRailwayPenWidthForZoom(self.map_zoom, tags)
                if showBridges == True:
                    pen = self.style.getStylePen("railwayBridge")
                    pen.setWidth(width + 4)
                    self.displayPolygonWithCache(self.areaPolygonCache, area, pen, brush)

                pen = self.style.getStylePen("railway")
                pen.setWidth(width)
                self.displayPolygonWithCache(self.areaPolygonCache, area, pen, brush)

    def displayTunnelRailways(self):
        if len(self.railwayTunnelLines) != 0:
            brush = Qt.NoBrush

            for area in self.railwayTunnelLines:
                tags = area[2]

                width = self.style.getRailwayPenWidthForZoom(self.map_zoom, tags)
                pen = self.style.getStylePen("railwayTunnel")
                pen.setWidth(width + 2)
                self.displayPolygonWithCache(self.areaPolygonCache, area, pen, brush)

    def displayRailways(self):
        if len(self.railwayLines) != 0:
            brush = Qt.NoBrush

            for area in self.railwayLines:
                tags = area[2]

                width = self.style.getRailwayPenWidthForZoom(self.map_zoom, tags)
                pen = self.style.getStylePen("railway")
                pen.setWidth(width)
                self.displayPolygonWithCache(self.areaPolygonCache, area, pen, brush)

    def displayAeroways(self):
        if len(self.aerowayLines) != 0:
            brush = Qt.NoBrush

            for area in self.aerowayLines:
                tags = area[2]

                pen = self.style.getStylePen("aeroway")
                pen.setWidth(self.style.getAerowayPenWidthForZoom(self.map_zoom, tags))
                self.displayPolygonWithCache(self.areaPolygonCache, area, pen, brush)

    def getAdminBoundaries(self, lat, lon):
        resultList = osmParserData.getAdminAreasOnPointWithGeom(lat, lon, 0.0, Constants.ADMIN_LEVEL_SET, True)
        resultList.reverse()

        for area in resultList:
            tags = area[1]
            print(tags)

    def showTextInfoBackground(self):
        textBackground = QRect(0, self.height() - 50, self.width() - self.getSidebarWidth(), 50)
        self.painter.fillRect(textBackground, self.style.getStyleColor("backgroundColor"))

        if self.currentRoute != None and self.currentTrackList != None and not self.currentRoute.isRouteFinished():
            routeInfoBackground = QRect(self.width() - ROUTE_INFO_WIDTH - self.getSidebarWidth(), self.height() - 50 - 200, ROUTE_INFO_WIDTH, 200)
            self.painter.fillRect(routeInfoBackground, self.style.getStyleColor("backgroundColor"))

    def showTextInfo(self):
        if self.wayInfo != None:
            pen = self.style.getStylePen("textPen")
            self.painter.setPen(pen)
            font = self.style.getStyleFont("wayInfoFont")
            self.painter.setFont(font)

            wayPos = QPoint(5, self.height() - 15)
            self.painter.drawText(wayPos, self.wayInfo)

    def getDistanceString(self, value):
        if value > 10000:
            valueStr = "%dkm" % (int(value / 1000))
        elif value > 500:
            valueStr = "%.1fkm" % (value / 1000)
        else:
            valueStr = "%dm" % value

        return valueStr

    def displayRouteInfo(self):
        pen = self.style.getStylePen("textPen")
        self.painter.setPen(pen)

        font = self.style.getStyleFont("monoFontLarge")
        self.painter.setFont(font)
        fm = self.painter.fontMetrics()

        distanceToEndStr = self.getDistanceString(self.distanceToEnd)
        distanceToEndPos = QPoint(self.width() - self.getSidebarWidth() - fm.width(distanceToEndStr) - 2, self.height() - 50 - 100 - 100 + fm.height() + 2)
        self.painter.drawText(distanceToEndPos, "%s" % distanceToEndStr)
        self.painter.drawPixmap(self.width() - self.getSidebarWidth() - ROUTE_INFO_WIDTH, distanceToEndPos.y() - fm.height() + 2, IMAGE_WIDTH_TINY, IMAGE_HEIGHT_TINY, self.style.getStylePixmap("finishPixmap"))

        font = self.style.getStyleFont("monoFontXLarge")
        self.painter.setFont(font)
        fm = self.painter.fontMetrics()

        crossingLengthStr = self.getDistanceString(self.distanceToCrossing)
        crossingDistancePos = QPoint(self.width() - self.getSidebarWidth() - fm.width(crossingLengthStr) - 2, self.height() - 50 - 100)
        self.painter.drawText(crossingDistancePos, "%s" % crossingLengthStr)
#        self.painter.drawPixmap(self.width()-self.getSidebarWidth()-ROUTE_INFO_WIDTH, self.height()-50-100-100+2+fm.height()+2, IMAGE_WIDTH_TINY, IMAGE_HEIGHT_TINY, self.style.getStylePixmap("crossingPixmap"))

        font = self.style.getStyleFont("wayInfoFont")
        self.painter.setFont(font)
        fm = self.painter.fontMetrics()

        if self.routeInfo[0] != None:
            (direction, crossingInfo, _, _) = self.routeInfo
            crossingInfoStr = crossingInfo

            exitNumber = 0
            if direction == 40 or direction == 41:
                if "roundabout:exit:" in crossingInfo:
                    exitNumber = int(crossingInfo[len("roundabout:exit:"):])
                if "roundabout:enter:" in crossingInfo:
                    exitNumber = int(crossingInfo[len("roundabout:enter:"):])

            if "stay:" in crossingInfo:
                crossingInfoStr = "Continue " + crossingInfoStr[len("stay:"):]
            elif "change:" in crossingInfo:
                crossingInfoStr = "Change " + crossingInfoStr[len("change:"):]
            elif "roundabout:enter:" in crossingInfo:
                crossingInfoStr = "Enter roundabout. Take exit %d" % (exitNumber)
            elif "roundabout:exit:" in crossingInfo:
                crossingInfoStr = "Exit roundabout at %d" % (exitNumber)
            elif "motorway:exit:info:" in crossingInfo:
                crossingInfoStr = "Take motorway exit " + crossingInfoStr[len("motorway:exit:info:"):]
            elif "motorway:exit" in crossingInfo:
                crossingInfoStr = "Take motorway exit"
            elif crossingInfo == "end":
                crossingInfoStr = ""

            routeInfoPos1 = QPoint(self.width() - self.getSidebarWidth() - fm.width(crossingInfoStr) - 10, self.height() - 15)
            self.painter.drawText(routeInfoPos1, "%s" % (crossingInfoStr))

            x = self.width() - self.getSidebarWidth() - ROUTE_INFO_WIDTH + 10
            y = self.height() - 50 - 100 + 10
            self.displayRouteDirectionImage(direction, exitNumber, IMAGE_WIDTH_LARGE, IMAGE_HEIGHT_LARGE, x, y)

    def showEnforcementInfo(self):
        if self.wayPOIList != None and len(self.wayPOIList) >= 1:
            nodeType = self.wayPOIList[0]

            wayPOIBackground = QRect(0, self.height() - 50 - 100 - 100, 100, 100)
            self.painter.fillRect(wayPOIBackground, self.style.getStyleColor("warningBackgroundColor"))
            x = 8
            y = self.height() - 50 - 100 - 100 + 10
            self.painter.drawPixmap(x, y, IMAGE_WIDTH_LARGE, IMAGE_HEIGHT_LARGE, self.style.getPixmapForNodeType(nodeType))

    def showSpeedInfo(self):
        if self.speedInfo != None and self.speedInfo != 0:
            x = 8
            y = self.height() - 50 - 100 + 10

            speedBackground = QRect(0, self.height() - 50 - 100, 100, 100)
            self.painter.fillRect(speedBackground, self.style.getStyleColor("backgroundColor"))

            imagePath = os.path.join(getImageRoot(), "speedsigns", "%d.png" % (self.speedInfo))
            if os.path.exists(imagePath):
                speedPixmap = QPixmap(imagePath)
                self.painter.drawPixmap(x, y, IMAGE_WIDTH_LARGE, IMAGE_HEIGHT_LARGE, speedPixmap)

    def displayRoutingPointRefPositions(self, point):
        if not point.isValid():
            return

        y, x = self.getTransformedPixelPosForLocationDeg(point.getClosestRefPos()[0], point.getClosestRefPos()[1])
        pen = QPen()
        pen.setColor(Qt.green)
        pen.setWidth(self.style.getPenWithForPoints(self.map_zoom))
        pen.setCapStyle(Qt.RoundCap)
        self.painter.setPen(pen)
        self.painter.drawPoint(x, y)

    def displayRoutingPoints(self):
        pixmapWidth, pixmapHeight = self.getPixmapSizeForZoom(IMAGE_WIDTH_SMALL, IMAGE_WIDTH_SMALL)

        if self.startPoint != None:
            (y, x) = self.getTransformedPixelPosForLocationDeg(self.startPoint.getPos()[0], self.startPoint.getPos()[1])
            if self.isPointVisibleTransformed(x, y):
                self.orderedNodeList.append((x, y, pixmapWidth, pixmapHeight, None, None, None, self.style.getStylePixmap("startPixmap")))
                self.displayRoutingPointRefPositions(self.startPoint)

        if self.endPoint != None:
            (y, x) = self.getTransformedPixelPosForLocationDeg(self.endPoint.getPos()[0], self.endPoint.getPos()[1])
            if self.isPointVisibleTransformed(x, y):
                self.orderedNodeList.append((x, y, pixmapWidth, pixmapHeight, None, None, None, self.style.getStylePixmap("finishPixmap")))
                self.displayRoutingPointRefPositions(self.endPoint)

        for point in self.wayPoints:
            (y, x) = self.getTransformedPixelPosForLocationDeg(point.getPos()[0], point.getPos()[1])
            if self.isPointVisibleTransformed(x, y):
                self.orderedNodeList.append((x, y, pixmapWidth, pixmapHeight, None, None, None, self.style.getStylePixmap("wayPixmap")))
                self.displayRoutingPointRefPositions(point)

    def getPixelPosForLocationDeg(self, lat, lon, relativeToEdge):
        return self.getPixelPosForLocationRad(self.osmutils.deg2rad(lat), self.osmutils.deg2rad(lon), relativeToEdge)

    # call this with relativeToEdge==True ONLY inside of a transformed painter
    # e.g. in paintEvent
    def getPixelPosForLocationRad(self, lat, lon, relativeToEdge):
        x = self.osmutils.lon2pixel(self.map_zoom, lon)
        y = self.osmutils.lat2pixel(self.map_zoom, lat)

        if relativeToEdge:
            map_x, map_y = self.getMapZeroPos()
            x = x - map_x
            y = y - map_y

        return (y, x)

    # call this outside of a transformed painter
    # if a specific point on the transformed map is needed
    def getTransformedPixelPosForLocationRad(self, lat, lon):
        x = self.osmutils.lon2pixel(self.map_zoom, lon)
        y = self.osmutils.lat2pixel(self.map_zoom, lat)
        map_x, map_y = self.getMapZeroPos()
        point = QPointF(x - map_x, y - map_y)

        point0 = self.transformHeading.map(point)
        x = point0.x()
        y = point0.y()
        return (y, x)

    def getTransformedPixelPosForLocationDeg(self, lat, lon):
        return self.getTransformedPixelPosForLocationRad(self.osmutils.deg2rad(lat), self.osmutils.deg2rad(lon))

    def getPixelPosForLocationDegForZoom(self, lat, lon, relativeToEdge, zoom, centerLat, centerLon):
        return self.getPixelPosForLocationRadForZoom(self.osmutils.deg2rad(lat), self.osmutils.deg2rad(lon), relativeToEdge, zoom, self.osmutils.deg2rad(centerLat), self.osmutils.deg2rad(centerLon))

    def getPixelPosForLocationRadForZoom(self, lat, lon, relativeToEdge, zoom, centerLat, centerLon):
        width_center = self.width() / 2
        height_center = self.height() / 2

        x = self.osmutils.lon2pixel(zoom, centerLon)
        y = self.osmutils.lat2pixel(zoom, centerLat)

        map_x = x - width_center
        map_y = y - height_center

        if relativeToEdge:
            x = self.osmutils.lon2pixel(zoom, lon) - map_x
            y = self.osmutils.lat2pixel(zoom, lat) - map_y
        else:
            x = self.osmutils.lon2pixel(zoom, lon)
            y = self.osmutils.lat2pixel(zoom, lat)

        return (y, x)

    def displayCoords(self, coords, pen):
        polygon = QPolygonF()

        map_x, map_y = self.getMapZeroPos()
        displayCoords = coords

#        if self.map_zoom<15:
#            if len(coords)>6:
#                displayCoords=coords[1:-2:2]
#                displayCoords[0]=coords[0]
#                displayCoords[-1]=coords[-1]

        for point in displayCoords:
            lat, lon = point
            (y, x) = self.getPixelPosForLocationDeg(lat, lon, False)
            point = QPointF(x, y);
            polygon.append(point)

        polygon.translate(-map_x, -map_y)

        self.painter.setPen(pen)
        self.painter.drawPolyline(polygon)

    def displayWayWithCache(self, way, pen):
        cPolygon = None
        painterPath = None
        wayId = way[0]
        coordsStr = way[9]
        map_x, map_y = self.getMapZeroPos()

        if not wayId in self.wayPolygonCache.keys():
            painterPath = QPainterPath()

            coords = self.gisUtils.createCoordsFromLineString(coordsStr)

            i = 0
            for point in coords:
                lat, lon = point
                (y, x) = self.getPixelPosForLocationDeg(lat, lon, False)
                point = QPointF(x, y);
                if i == 0:
                    painterPath.moveTo(point)
                else:
                    painterPath.lineTo(point)

                i = i + 1

            rect = painterPath.controlPointRect()
            cont = [(rect.x(), rect.y()),
                  (rect.x() + rect.width(), rect.y()),
                  (rect.x() + rect.width(), rect.y() + rect.height()),
                  (rect.x(), rect.y() + rect.height())]

            cPolygon = Polygon(cont)

            self.wayPolygonCache[wayId] = (cPolygon, painterPath)

        else:
            cPolygon, painterPath = self.wayPolygonCache[wayId]

        # only draw visible path
        if cPolygon != None:
            # must create a copy cause shift changes alues intern
            p = Polygon(cPolygon)
            p.shift(-map_x, -map_y)
            if not self.visibleCPolygon.overlaps(p):
                self.numHiddenWays = self.numHiddenWays + 1
                return

        self.numVisibleWays = self.numVisibleWays + 1

        painterPath = painterPath.translated(-map_x, -map_y)
        self.painter.strokePath(painterPath, pen)

    def displayPolygonWithCache(self, cacheDict, area, pen, brush):
        cPolygon = None
        painterPath = None
        osmId = area[0]
        polyStr = area[4]
        geomType = area[5]
        map_x, map_y = self.getMapZeroPos()

        if not osmId in cacheDict.keys():
            painterPath = QPainterPath()
            coordsList = list()
            if geomType == 0:
                coordsList = self.gisUtils.createCoordsFromPolygonString(polyStr)
            else:
                coords = self.gisUtils.createCoordsFromLineString(polyStr)
                coordsList.append((coords, list()))

            for outerCoords, _ in coordsList:
                i = 0
                for point in outerCoords:
                    lat, lon = point
                    (y, x) = self.getPixelPosForLocationDeg(lat, lon, False)
                    point = QPointF(x, y)
                    if i == 0:
                        painterPath.moveTo(point)
                    else:
                        painterPath.lineTo(point)

                    i = i + 1

            if geomType == 0:
                painterPath.closeSubpath()

            rect = painterPath.controlPointRect()
            cont = [(rect.x(), rect.y()),
                  (rect.x() + rect.width(), rect.y()),
                  (rect.x() + rect.width(), rect.y() + rect.height()),
                  (rect.x(), rect.y() + rect.height())]

            cPolygon = Polygon(cont)

            if geomType == 0:
                for _, innerCoordsList in coordsList:
                    for innerCoords in innerCoordsList:
                        innerPainterPath = QPainterPath()
                        i = 0
                        for point in innerCoords:
                            lat, lon = point
                            (y, x) = self.getPixelPosForLocationDeg(lat, lon, False)
                            point = QPointF(x, y)
                            if i == 0:
                                innerPainterPath.moveTo(point)
                            else:
                                innerPainterPath.lineTo(point)

                            i = i + 1

                        innerPainterPath.closeSubpath()
                        painterPath = painterPath.subtracted(innerPainterPath)

            cacheDict[osmId] = (cPolygon, painterPath, geomType)

        else:
            cPolygon, painterPath, _ = cacheDict[osmId]

        if cPolygon != None:
            # must create a copy cause shift changes values intern
            p = Polygon(cPolygon)
            p.shift(-map_x, -map_y)
            if not self.visibleCPolygon.overlaps(p):
                self.numHiddenPolygons = self.numHiddenPolygons + 1
                return

        self.numVisiblePolygons = self.numVisiblePolygons + 1

        painterPath = painterPath.translated(-map_x, -map_y)
        self.painter.setBrush(brush)
        self.painter.setPen(pen)

        if geomType == 0:
            self.painter.drawPath(painterPath)
        else:
            # TODO: building as linestring 100155254
            if pen != Qt.NoPen:
                self.painter.strokePath(painterPath, pen)

    def displayAdminLineWithCache(self, line, pen):
        cPolygon = None
        painterPath = None
        lineId = line[0]
        coordsStr = line[2]
        map_x, map_y = self.getMapZeroPos()

        if not lineId in self.adminPolygonCache.keys():
            painterPath = QPainterPath()

            coords = self.gisUtils.createCoordsFromLineString(coordsStr)

            i = 0
            for point in coords:
                lat, lon = point
                (y, x) = self.getPixelPosForLocationDeg(lat, lon, False)
                point = QPointF(x, y)
                if i == 0:
                    painterPath.moveTo(point)
                else:
                    painterPath.lineTo(point)

                i = i + 1

            rect = painterPath.controlPointRect()
            cont = [(rect.x(), rect.y()),
                  (rect.x() + rect.width(), rect.y()),
                  (rect.x() + rect.width(), rect.y() + rect.height()),
                  (rect.x(), rect.y() + rect.height())]

            cPolygon = Polygon(cont)

            self.adminPolygonCache[lineId] = (cPolygon, painterPath)

        else:
            cPolygon, painterPath = self.adminPolygonCache[lineId]

        if cPolygon != None:
            # must create a copy cause shift changes alues intern
            p = Polygon(cPolygon)
            p.shift(-map_x, -map_y)
            if not self.visibleCPolygon.overlaps(p):
                self.numHiddenAdminLiness = self.numHiddenAdminLiness + 1
                return

        self.numVisibleAdminLines = self.numVisibleAdminLines + 1

        painterPath = painterPath.translated(-map_x, -map_y)
        self.painter.strokePath(painterPath, pen)

    def displayRouteOverlay(self, remainingTrackList, edgeIndexList):
        if remainingTrackList != None:
            polygon = QPolygonF()

            for index in edgeIndexList:
                if index < len(remainingTrackList):
                    item = remainingTrackList[index]

                    for itemRef in item["refs"]:
                        lat, lon = itemRef["coords"]
                        (y, x) = self.getPixelPosForLocationDeg(lat, lon, True)
                        point = QPointF(x, y);
                        polygon.append(point)

            pen = self.style.getStylePen("routeOverlayPen")
            pen.setWidth(self.style.getStreetPenWidthForZoom(self.map_zoom))
            self.painter.setPen(pen)
            self.painter.drawPolyline(polygon)

    def displayRoute(self, route):
        if route != None:
            # before calculation is done
            if not route.complete():
                return

            showTrackDetails = self.map_zoom > 13

            polygon = QPolygonF()
            routeInfo = route.getRouteInfo()
            for routeInfoEntry in routeInfo:
                if not "trackList" in routeInfoEntry:
                    return

                trackList = routeInfoEntry["trackList"]

                for item in trackList:
                    for itemRef in item["refs"]:
                        lat, lon = itemRef["coords"]

                        (y, x) = self.getPixelPosForLocationDeg(lat, lon, True)
                        point = QPointF(x, y);
                        polygon.append(point)

            pen = self.style.getStylePen("routePen")
            pen.setWidth(self.style.getStreetPenWidthForZoom(self.map_zoom))
            self.painter.setPen(pen)
            self.painter.drawPolyline(polygon)

            if showTrackDetails == True:
                for routeInfoEntry in routeInfo:
                    trackList = routeInfoEntry["trackList"]

                    for item in trackList:
                        for itemRef in item["refs"]:
                            lat, lon = itemRef["coords"]

                            crossing = False

                            if "crossingType" in itemRef:
                                crossing = True
                                crossingType = itemRef["crossingType"]

                            if crossing == True:
                                (y, x) = self.getPixelPosForLocationDeg(lat, lon, True)

                                if self.isPointVisible(x, y):
                                    pen = self.style.getPenForCrossingType(crossingType)
                                    pen.setWidth(self.style.getPenWithForPoints(self.map_zoom))

                                    self.painter.setPen(pen)
                                    self.painter.drawPoint(x, y)

    def displayRouteDirectionImage(self, direction, exitNumber, width, height, x, y):
        if direction == 1:
            self.painter.drawPixmap(x, y, width, height, self.style.getStylePixmap("turnRightEasyImage"))
        elif direction == 2:
            self.painter.drawPixmap(x, y, width, height, self.style.getStylePixmap("turnRightImage"))
        elif direction == 3:
            self.painter.drawPixmap(x, y, width, height, self.style.getStylePixmap("turnRighHardImage"))
        elif direction == -1:
            self.painter.drawPixmap(x, y, width, height, self.style.getStylePixmap("turnLeftEasyImage"))
        elif direction == -2:
            self.painter.drawPixmap(x, y, width, height, self.style.getStylePixmap("turnLeftImage"))
        elif direction == -3:
            self.painter.drawPixmap(x, y, width, height, self.style.getStylePixmap("turnLeftHardImage"))
        elif direction == 0:
            self.painter.drawPixmap(x, y, width, height, self.style.getStylePixmap("straightImage"))
        elif direction == 39:
            # TODO: should be a motorway exit image
            self.painter.drawPixmap(x, y, width, height, self.style.getStylePixmap("turnRightEasyImage"))
        elif direction == 42:
            # TODO: is a link enter always right?
            self.painter.drawPixmap(x, y, width, height, self.style.getStylePixmap("turnRightEasyImage"))
        elif direction == 41 or direction == 40:
            if exitNumber == 1:
                self.painter.drawPixmap(x, y, width, height, self.style.getStylePixmap("roundabout1Image"))
            elif exitNumber == 2:
                self.painter.drawPixmap(x, y, width, height, self.style.getStylePixmap("roundabout2Image"))
            elif exitNumber == 3:
                self.painter.drawPixmap(x, y, width, height, self.style.getStylePixmap("roundabout3Image"))
            elif exitNumber == 4:
                self.painter.drawPixmap(x, y, width, height, self.style.getStylePixmap("roundabout4Image"))
            else:
                self.painter.drawPixmap(x, y, width, height, self.style.getStylePixmap("roundaboutImage"))
        elif direction == 98:
            self.painter.drawPixmap(x, y, width, height, self.style.getStylePixmap("uturnImage"))
        elif direction == 99:
            self.painter.drawPixmap(x, y, width, height, self.style.getStylePixmap("finishPixmap"))

#    def minimumSizeHint(self):
#        return QSize(minWidth, minHeight)

#    def sizeHint(self):
#        return QSize(800, 300)

    def center_coord_update(self):
        self.center_rlon = self.osmutils.pixel2lon(self.map_zoom, self.center_x)
        self.center_rlat = self.osmutils.pixel2lat(self.map_zoom, self.center_y)

        self.map_x, self.map_y = self.calcMapZeroPos()

    def stepInDirection(self, step_x, step_y):
        map_x, map_y = self.getMapZeroPos()
        point = QPointF(self.center_x - map_x + step_x, self.center_y - map_y + step_y)
        invertedTransform = self.transformHeading.inverted()
        point0 = invertedTransform[0].map(point)
        self.center_y = map_y + point0.y()
        self.center_x = map_x + point0.x()
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

    def updateStatusLabel(self, text):
        self.updateStatusSignal.emit(text)

    @pyqtSlot()
    def updateMap(self):
        self.update()

    def mouseReleaseEvent(self, event):
        self.mousePressed = False

        eventPos = QPoint(event.x(), event.y())
        if not self.moving:
            if self.minusRect.contains(eventPos) or self.plusRect.contains(eventPos):
                self.pointInsideZoomOverlay(event.x(), event.y())
                return

            if self.sidebarVisible == True:
                if self.searchRect.contains(eventPos):
                    self.osmWidget._showSearchMenu()
                    return
                elif self.favoriteRect.contains(eventPos):
                    self.osmWidget._showFavorites()
                    return
                elif self.routesRect.contains(eventPos):
                    self.osmWidget._loadRoute()
                    return
                elif self.optionsRect.contains(eventPos):
                    self.osmWidget._showSettings()
                    return

            self.lastMouseMoveX = event.x()
            self.lastMouseMoveY = event.y()
            self.showTrackOnMousePos(event.x(), event.y())

        else:
            self.moving = False

    def pointInsideZoomOverlay(self, x, y):
        if self.minusRect.contains(x, y):
            if self.isVirtualZoom == True:
                zoom = MAX_ZOOM
                self.isVirtualZoom = False
            else:
                zoom = self.map_zoom - 1
                if zoom < MIN_ZOOM:
                    zoom = MIN_ZOOM
            self.zoom(zoom)

        if self.plusRect.contains(x, y):
            zoom = self.map_zoom + 1
            if zoom == MAX_ZOOM + 1:
                self.isVirtualZoom = True
                zoom = MAX_ZOOM
            else:
                if zoom > MAX_ZOOM:
                    zoom = MAX_ZOOM
            self.zoom(zoom)

    def mousePressEvent(self, event):
        self.mousePressed = True
        self.lastMouseMoveX = event.x()
        self.lastMouseMoveY = event.y()
        self.mousePos = (event.x(), event.y())

    def mouseMoveEvent(self, event):
        if self.mousePressed == True:
            self.moving = True

            dx = self.lastMouseMoveX - event.x()
            dy = self.lastMouseMoveY - event.y()
            self.osm_map_scroll(dx, dy)
            self.lastMouseMoveX = event.x()
            self.lastMouseMoveY = event.y()

    def getMapPointForPos(self, mousePos):
        p = QPoint(mousePos[0], mousePos[1])
        pixmapWidth, pixmapHeight = self.getPixmapSizeForZoom(IMAGE_WIDTH_SMALL, IMAGE_WIDTH_SMALL)

        if self.startPoint != None:
            (y, x) = self.getTransformedPixelPosForLocationDeg(self.startPoint.lat, self.startPoint.lon)
            rect = QRect(int(x - pixmapWidth / 2), int(y - pixmapHeight), pixmapWidth, pixmapHeight)
            if rect.contains(p, proper=False):
                return self.startPoint

        if self.endPoint != None:
            (y, x) = self.getTransformedPixelPosForLocationDeg(self.endPoint.lat, self.endPoint.lon)
            rect = QRect(int(x - pixmapWidth / 2), int(y - pixmapHeight), pixmapWidth, pixmapHeight)
            if rect.contains(p, proper=False):
                return self.endPoint

        if self.mapPoint != None:
            (y, x) = self.getTransformedPixelPosForLocationDeg(self.mapPoint.lat, self.mapPoint.lon)
            rect = QRect(int(x - pixmapWidth / 2), int(y - pixmapHeight), pixmapWidth, pixmapHeight)
            if rect.contains(p, proper=False):
                return self.mapPoint

        for point in self.wayPoints:
            (y, x) = self.getTransformedPixelPosForLocationDeg(point.lat, point.lon)
            rect = QRect(int(x - pixmapWidth / 2), int(y - pixmapHeight), pixmapWidth, pixmapHeight)
            if rect.contains(p, proper=False):
                return point

        return None

    def contextMenuEvent(self, event):
#        print("%d-%d"%(self.mousePos[0], self.mousePos[1]))
        menu = QMenu(self)
        setStartPointAction = QAction("Set Start Point", self)
        setEndPointAction = QAction("Set End Point", self)
        setWayPointAction = QAction("Set Way Point", self)
        addFavoriteAction = QAction("Add to Favorites", self)
        clearAllMapPointsAction = QAction("Clear All Map Points", self)
        clearMapPointAction = QAction("Clear Map Point", self)
        editRoutingPointAction = QAction("Edit Current Route", self)
        saveRouteAction = QAction("Save Current Route", self)
        showRouteAction = QAction("Calc Route", self)
        clearRouteAction = QAction("Clear Current Route", self)
        gotoPosAction = QAction("Goto Position", self)
        showPosAction = QAction("Show Position", self)
        zoomToCompleteRoute = QAction("Zoom to Route", self)
        recalcRouteAction = QAction("Calc Route from here", self)

        routingPointSubMenu = QMenu(self)
        routingPointSubMenu.setTitle("Map Points")
        mapPointList = self.getMapPoints()
        mapPointMenuDisabled = len(mapPointList) == 0
        for point in mapPointList:
            if point.getType() == OSMRoutingPoint.TYPE_MAP:
                routingPointSubMenu.addSeparator()
            pointAction = OSMRoutingPointAction(point.getName(), point, self.style, self)
            routingPointSubMenu.addAction(pointAction)

        routingPointSubMenu.setDisabled(mapPointMenuDisabled)

        googlePOIAction = QAction("Google this POI by name", self)
        showAdminHierarchy = QAction("Show Admin Info for here", self)
        showAreaTags = QAction("Show Area Info for here", self)
        showWayTags = QAction("Show Way Info", self)

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
        menu.addSeparator()
        menu.addAction(zoomToCompleteRoute)
        menu.addAction(googlePOIAction)
        menu.addAction(showAdminHierarchy)
        menu.addAction(showAreaTags)
        menu.addAction(showWayTags)

        routingPointList = self.getCompleteRoutingPoints()
        addPointDisabled = False
        routeIncomplete = routingPointList == None
        setStartPointAction.setDisabled(addPointDisabled)
        setEndPointAction.setDisabled(addPointDisabled)
        setWayPointAction.setDisabled(addPointDisabled)
        addFavoriteAction.setDisabled(addPointDisabled)
        showPosAction.setDisabled(addPointDisabled)
        gotoPosAction.setDisabled(addPointDisabled)
        saveRouteAction.setDisabled(routeIncomplete)
        clearMapPointAction.setDisabled(self.getMapPointForPos(self.mousePos) == None)
        clearAllMapPointsAction.setDisabled(mapPointMenuDisabled)
        editRoutingPointAction.setDisabled(routeIncomplete)
        zoomToCompleteRoute.setDisabled(routeIncomplete)
        clearRouteAction.setDisabled(self.currentRoute == None)
        showWayTags.setDisabled(self.lastWayId == None)

        showRouteDisabled = (self.routeCalculationThread != None and self.routeCalculationThread.isRunning()) or routeIncomplete
        showRouteAction.setDisabled(showRouteDisabled)

        recalcRouteDisabled = (self.routeCalculationThread != None and self.routeCalculationThread.isRunning()) or self.endPoint == None
        recalcRouteAction.setDisabled(recalcRouteDisabled)

        action = menu.exec_(self.mapToGlobal(event.pos()))
#        print(action.text())
        if action == setStartPointAction:
            self.addRoutingPoint(0)
        elif action == setEndPointAction:
            self.addRoutingPoint(1)
        elif action == setWayPointAction:
            self.addRoutingPoint(2)
        elif action == showRouteAction:
            self.showRouteForRoutingPoints(self.getCompleteRoutingPoints())
        elif action == clearAllMapPointsAction:
            self.startPoint = None
            self.endPoint = None
            self.mapPoint = None
            self.wayPoints.clear()
        elif action == addFavoriteAction:
            self.addToFavorite(self.mousePos)
        elif action == clearMapPointAction:
            self.removeMapPoint(self.mousePos)
        elif action == editRoutingPointAction:
            self.editRoutingPoints()
        elif action == gotoPosAction:
            self.showPosOnMapDialog()
        elif action == showPosAction:
            (lat, lon) = self.getPosition(self.mousePos[0], self.mousePos[1])
            self.showMapPosDialog(lat, lon)
        elif action == saveRouteAction:
            self.saveCurrentRoute()
        elif action == zoomToCompleteRoute:
            self.zoomToCompleteRoute(self.getCompleteRoutingPoints())
        elif action == clearRouteAction:
            self.clearCurrentRoute()
        elif action == recalcRouteAction:
            (lat, lon) = self.getPosition(self.mousePos[0], self.mousePos[1])
            currentPoint = OSMRoutingPoint("tmp", OSMRoutingPoint.TYPE_START, (lat, lon))
            currentPoint.resolveFromPos(osmParserData)
            if currentPoint.isValid():
                _, _, _, _, name, nameRef, _, _ = osmParserData.getWayEntryForId(currentPoint.getWayId())
                defaultPointTag = osmParserData.getWayTagString(name, nameRef)
                currentPoint.name = defaultPointTag
                self.startPoint = currentPoint

                self.showRouteForRoutingPoints(self.getCompleteRoutingPoints())
            else:
                self.showError("Error", "Route has invalid routing points")

        elif action == showAdminHierarchy:
            (lat, lon) = self.getPosition(self.mousePos[0], self.mousePos[1])
            self.getAdminBoundaries(lat, lon)
        elif action == showAreaTags:
            pos = QPointF(self.mousePos[0], self.mousePos[1])
            self.getAreaTagsForPos(pos)
        elif action == showWayTags:
            print(osmParserData.getWayEntryForId(self.lastWayId))
            print(osmParserData.getEdgeEntryForId(self.selectedEdgeId))
            osmParserData.printCrossingsForWayId(self.lastWayId)
            restrictionList = osmParserData.getRestrictionEntryForTargetEdge(self.selectedEdgeId)
            if len(restrictionList) != 0:
                for restriction in restrictionList:
                    restrictionId, toEdgeId, viaEdgePath, toCost, osmId = restriction
                    print(restriction)
                    print(osmParserData.resolveRestriction(restriction))
        elif action == googlePOIAction:
            pos = QPoint(self.mousePos[0], self.mousePos[1])
            refId, tags = self.getNodeInfoForPos(pos)
            if tags != None:
                searchString = osmParserData.getPOITagString(tags)
                if searchString != Constants.UNKNOWN_NAME_TAG:
                    if "addr:street" in tags:
                        searchString = searchString + " " + tags["addr:street"]
                    QDesktopServices.openUrl(QUrl("http://www.google.com/search?q=%s" % (searchString), QUrl.TolerantMode))

        else:
            if isinstance(action, OSMRoutingPointAction):
                routingPoint = action.getRoutingPoint()
                self.showPointOnMap(routingPoint)

        self.mousePressed = False
        self.moving = False
        self.update()

    def clearCurrentRoute(self):
        self.currentRoute = None
        self.clearRoute()

    # TODO: should also include way points
    def zoomToCompleteRoute(self, routingPointList):
        if len(routingPointList) == 0:
            return

        width = self.width()
        height = self.height()
        startLat, startLon = routingPointList[0].getPos()
        endLat, endLon = routingPointList[-1].getPos()

        centerLat, centerLon = self.osmutils.linepart(endLat, endLon, startLat, startLon, 0.5)

        for zoom in range(MAX_ZOOM, MIN_ZOOM, -1):
            (pixel_y1, pixel_x1) = self.getPixelPosForLocationDegForZoom(startLat, startLon, True, zoom, centerLat, centerLon)
            (pixel_y2, pixel_x2) = self.getPixelPosForLocationDegForZoom(endLat, endLon, True, zoom, centerLat, centerLon)

            if pixel_x1 > 0 and pixel_x2 > 0 and pixel_y1 > 0 and pixel_y2 > 0:
                if pixel_x1 < width and pixel_x2 < width and pixel_y1 < height and pixel_y2 < height:
#                    print(zoom)
                    if zoom != self.map_zoom:
                        self.osm_map_set_zoom(zoom)

                    self.osm_center_map_to_position(centerLat, centerLon)
                    break

    def saveCurrentRoute(self):
        routeNameDialog = OSMRouteSaveDialog(self, self.routeList)
        result = routeNameDialog.exec()
        if result == QDialog.Accepted:
            name = routeNameDialog.getResult()
            route = OSMRoute(name, self.getCompleteRoutingPoints())
            self.routeList.append(route)

    def showPosOnMapDialog(self):
        posDialog = OSMPositionDialog(self)
        result = posDialog.exec()
        if result == QDialog.Accepted:
            lat, lon = posDialog.getResult()

            if self.map_zoom < 15:
                self.osm_map_set_zoom(15)

            self.osm_center_map_to_position(lat, lon)

    def showMapPosDialog(self, lat, lon):
        posDialog = OSMPositionDialog(self, lat, lon)
        posDialog.exec()

    def getCompleteRoutingPoints(self):
        if self.startPoint == None or self.endPoint == None:
            return None

        routingPointList = list()
        routingPointList.append(self.startPoint)
        if len(self.wayPoints) != 0:
            routingPointList.extend(self.wayPoints)
        routingPointList.append(self.endPoint)
        return routingPointList

    def getMapPoints(self):
        routingPointList = list()

        if self.startPoint != None:
            routingPointList.append(self.startPoint)

        if self.wayPoints != None and len(self.wayPoints) != 0:
            routingPointList.extend(self.wayPoints)

        if self.endPoint != None:
            routingPointList.append(self.endPoint)

        if self.mapPoint != None:
            routingPointList.append(self.mapPoint)

        return routingPointList

    def setRoute(self, route):
        self.setRoutingPointsFromList(route.getRoutingPointList())

    def setRoutingPointsFromList(self, routingPointList):
        self.setStartPoint(routingPointList[0])
        self.setEndPoint(routingPointList[-1])
        self.wayPoints.clear()
        if len(routingPointList) > 2:
            for point in routingPointList[1:-1]:
                self.setWayPoint(point)

    def editRoutingPoints(self):
        routingPointList = self.getCompleteRoutingPoints()
        if routingPointList == None:
            return

        routeDialog = OSMRouteDialog(self, routingPointList, self.routeList)
        result = routeDialog.exec()
        if result == QDialog.Accepted:
            routingPointList, self.routeList = routeDialog.getResult()
            self.setRoutingPointsFromList(routingPointList)
#            self.zoomToCompleteRoute(self.routingPointList)
        elif result == QDialog.Rejected:
            # even in case of cancel we might have save a route
            self.routeList = routeDialog.getRouteList()

    def removeMapPoint(self, mousePos):
        selectedPoint = self.getMapPointForPos(mousePos)
        if selectedPoint != None:
            if selectedPoint == self.startPoint:
                self.startPoint = None
            elif selectedPoint == self.endPoint:
                self.endPoint = None
            elif selectedPoint == self.mapPoint:
                self.mapPoint = None
            else:
                for point in self.wayPoints:
                    if selectedPoint == point:
                        self.wayPoints.remove(selectedPoint)

    def addToFavorite(self, mousePos):
        (lat, lon) = self.getPosition(mousePos[0], mousePos[1])

        defaultPointTag = None
        edgeId, wayId = osmParserData.getEdgeIdOnPos(lat, lon, OSMRoutingPoint.DEFAULT_RESOLVE_POINT_MARGIN, OSMRoutingPoint.DEFAULT_RESOLVE_MAX_DISTANCE)
        if edgeId != None:
            wayId, _, _, _, name, nameRef, _, _ = osmParserData.getWayEntryForId(wayId)
            defaultPointTag = osmParserData.getWayTagString(name, nameRef)

        if defaultPointTag == None:
            defaultPointTag = ""

        favNameDialog = OSMSaveFavoritesDialog(self, self.osmWidget.favoriteList, defaultPointTag)
        result = favNameDialog.exec()
        if result == QDialog.Accepted:
            favoriteName = favNameDialog.getResult()
            favoritePoint = OSMRoutingPoint(favoriteName, OSMRoutingPoint.TYPE_FAVORITE, (lat, lon))
            self.osmWidget.favoriteList.append(favoritePoint)

    def addRoutingPoint(self, pointType):
        (lat, lon) = self.getPosition(self.mousePos[0], self.mousePos[1])

        defaultPointTag = None
        edgeId, wayId = osmParserData.getEdgeIdOnPos(lat, lon, OSMRoutingPoint.DEFAULT_RESOLVE_POINT_MARGIN, OSMRoutingPoint.DEFAULT_RESOLVE_MAX_DISTANCE)
        if edgeId != None:
            wayId, _, _, _, name, nameRef, _, _ = osmParserData.getWayEntryForId(wayId)
            defaultPointTag = osmParserData.getWayTagString(name, nameRef)

        if pointType == 0:
            if defaultPointTag != None:
                defaultName = defaultPointTag
            else:
                defaultName = "start"

            point = OSMRoutingPoint(defaultName, pointType, (lat, lon))
            point.resolveFromPos(osmParserData)
            self.startPoint = point
            if not point.isValid():
                self.showError("Error", "Failed to resolve way for start point")

        elif pointType == 1:
            if defaultPointTag != None:
                defaultName = defaultPointTag
            else:
                defaultName = "end"

            point = OSMRoutingPoint(defaultName, pointType, (lat, lon))
            point.resolveFromPos(osmParserData)
            self.endPoint = point
            if not point.isValid():
                self.showError("Error", "Failed to resolve way for finish point")

        elif pointType == 2:
            if defaultPointTag != None:
                defaultName = defaultPointTag
            else:
                defaultName = "way"

            wayPoint = OSMRoutingPoint(defaultName, pointType, (lat, lon))
            wayPoint.resolveFromPos(osmParserData)
            self.wayPoints.append(wayPoint)
            if not wayPoint.isValid():
                self.showError("Error", "Failed to resolve way for way point")

    def showPointOnMap(self, point):
        if self.map_zoom < 15:
            self.osm_map_set_zoom(15)

        self.osm_center_map_to_position(point.getPos()[0], point.getPos()[1])

    def recalcRoute(self, lat, lon, edgeId):
        if self.routeCalculationThread != None and self.routeCalculationThread.isRunning():
            return

        recalcPoint = OSMRoutingPoint("tmp", OSMRoutingPoint.TYPE_TMP, (lat, lon))
        recalcPoint.resolveFromPos(osmParserData)
        if not recalcPoint.isValid():
            return

        if self.currentRoute != None and not self.currentRoute.isRouteFinished():
            if self.routeCalculationThread != None and not self.routeCalculationThread.isRunning():
                self.recalcRouteFromPoint(recalcPoint)

    def clearCurrent(self):
        self.currentCoords = None
        self.selectedEdgeId = None
        self.lastWayId = None
        self.speedInfo = None
        self.wayPOIList = None
        self.wayInfo = None

        self.distanceToCrossing = 0
        self.nextEdgeOnRoute = None
        self.routeInfo = None, None, None, None

    def clearAll(self):
        self.clearCurrent()
        osmRouting.clearAll()

    def calcNextCrossingInfo(self, lat, lon):
        (direction, crossingInfo, crossingType, crossingRef, crossingEdgeId) = osmParserData.getNextCrossingInfoFromPos(self.currentTrackList, lat, lon)
        self.currentEdgeIndexList = list()
        if crossingEdgeId != None and crossingEdgeId in self.currentEdgeList:
            crossingEdgeIdIndex = self.currentEdgeList.index(crossingEdgeId) + 1
        else:
            crossingEdgeIdIndex = len(self.currentEdgeList) - 1

        for i in range(0, crossingEdgeIdIndex + 1, 1):
            self.currentEdgeIndexList.append(i)

        if direction != None:
            self.routeInfo = (direction, crossingInfo, crossingType, crossingRef)
        else:
            self.routeInfo = None, None, None, None

    def calcRouteDistances(self, lat, lon, initial=False):
        if initial == True:
            self.distanceToEnd = self.currentRoute.getAllLength()
            self.distanceToCrossing = 0
            self.remainingTime = 0
        else:
            distanceOnEdge = osmRouting.getDistanceToCrossing()
#            print(distanceOnEdge)
            self.distanceToEnd, self.distanceToCrossing = osmParserData.calcRouteDistances(self.currentTrackList, lat, lon, self.currentRoute, distanceOnEdge)
            self.remainingTime = osmParserData.calcRemainingDrivingTime(self.currentTrackList, lat, lon, self.currentRoute, distanceOnEdge, self.speed)
#            print(self.remainingTime)

    def showTrackOnPos(self, lat, lon, track, speed, update, fromMouse):
        # TODO:
        if self.routeCalculationThread != None and self.routeCalculationThread.isRunning():
            return

        edge = osmRouting.getEdgeIdOnPosForRouting(lat, lon, track, self.nextEdgeOnRoute, DEFAULT_SEARCH_MARGIN, fromMouse, speed)
        if edge == None:
            self.clearCurrent()
        else:
#            print(edge)
            edgeId = edge[0]
            startRef = edge[1]
            endRef = edge[2]
            length = edge[3]
            wayId = edge[4]
            coords = edge[10]

            self.currentCoords = coords
            self.selectedEdgeId = edgeId

            if wayId != self.lastWayId:
                self.lastWayId = wayId
                wayId, _, _, streetInfo, name, nameRef, maxspeed, _ = osmParserData.getWayEntryForId(wayId)

                self.wayInfo = osmParserData.getWayTagString(name, nameRef)
                self.speedInfo = maxspeed
                self.wayPOIList = osmParserData.getPOIListOnWay(wayId)

#            stop=time.time()
#            print("showTrackOnPos:%f"%(stop-start))
        if update == True:
            self.update()

    def showRouteForRoutingPoints(self, routingPointList):
        # calculate
        self.currentRoute = OSMRoute("current", routingPointList)
        # make sure all are resolved because we cannot access
        # the db from the thread
        self.currentRoute.resolveRoutingPoints(osmParserData)

        if not self.currentRoute.isValid():
            self.showError("Error", "Route has invalid routing points")
            return

        self.routeCalculationThread = OSMRouteCalcWorker(self, self.currentRoute)
        self.routeCalculationThread.routeCalculationDoneSignal.connect(self.routeCalculationDone)
        self.routeCalculationThread.updateStatusSignal.connect(self.updateStatusLabel)
        self.routeCalculationThread.startProgressSignal.connect(self.startProgress)
        self.routeCalculationThread.stopProgressSignal.connect(self.stopProgress)
        self.routeCalculationThread.start()

    def recalcRouteFromPoint(self, currentPoint):
        # make sure all are resolved because we cannot access
        # the db from the thread
        self.currentRoute.changeRouteFromPoint(currentPoint, osmParserData)
        self.currentRoute.resolveRoutingPoints(osmParserData)
        if not self.currentRoute.isValid():
            self.showError("Error", "Route has invalid routing points")
            return

        self.routeCalculationThread = OSMRouteCalcWorker(self, self.currentRoute)
        self.routeCalculationThread.routeCalculationDoneSignal.connect(self.routeCalculationDone)
        self.routeCalculationThread.updateStatusSignal.connect(self.updateStatusLabel)
        self.routeCalculationThread.startProgressSignal.connect(self.startProgress)
        self.routeCalculationThread.stopProgressSignal.connect(self.stopProgress)
        self.routeCalculationThread.start()

    def startProgress(self):
        self.startProgressSignal.emit()

    def stopProgress(self):
        self.stopProgressSignal.emit()

    def routeCalculationDone(self):
        if self.currentRoute.getRouteInfo() != None:
            self.currentRoute.printRoute(osmParserData)
#            self.printRouteDescription(self.currentRoute)

            self.clearAll()

            self.currentRoutePart = 0
            self.currentEdgeList = self.currentRoute.getEdgeList(self.currentRoutePart)
            self.currentTrackList = self.currentRoute.getTrackList(self.currentRoutePart)
            self.currentStartPoint = self.currentRoute.getStartPoint(self.currentRoutePart)
            self.currentTargetPoint = self.currentRoute.getTargetPoint(self.currentRoutePart)
#            print(self.currentEdgeList)
#            print(self.currentTrackList)

            print(self.currentRoute.getAllLength())
            print(self.currentRoute.getAllTime())

            # display inital distances
            # simply use start point as ref
            self.calcRouteDistances(self.startPoint.getPos()[0], self.startPoint.getPos()[1], True)
            self.update()

    def switchToNextRoutePart(self):
        if self.currentRoutePart < self.currentRoute.getRouteInfoLength() - 1:
#            print("switch to next route part")
            self.currentRoutePart = self.currentRoutePart + 1
            self.currentEdgeList = self.currentRoute.getEdgeList(self.currentRoutePart)
            self.currentTrackList = self.currentRoute.getTrackList(self.currentRoutePart)
            self.currentStartPoint = self.currentRoute.getStartPoint(self.currentRoutePart)
            self.currentTargetPoint = self.currentRoute.getTargetPoint(self.currentRoutePart)
#            print(self.currentEdgeList)

    def currentTargetPointReached(self, lat, lon):
        targetLat, targetLon = self.currentTargetPoint.getClosestRefPos()
        if self.osmutils.distance(lat, lon, targetLat, targetLon) < 15.0:
            return True
        return False

    def currentStartPointReached(self, lat, lon):
        startLat, startLon = self.currentStartPoint.getClosestRefPos()
        if self.osmutils.distance(lat, lon, startLat, startLon) < 15.0:
            return True
        return False

    def clearRoute(self):
        self.distanceToEnd = 0
        self.distanceToCrossing = 0
        self.currentEdgeIndexList = None
        self.nextEdgeOnRoute = None
        self.currentEdgeList = None
        self.currentTrackList = None
        self.currentStartPoint = None
        self.currentTargetPoint = None
        self.currentRoutePart = 0

    def getTrackListFromEdge(self, indexEnd, edgeList, trackList):
        if indexEnd < len(edgeList):
            restEdgeList = edgeList[indexEnd:]
            restTrackList = trackList[indexEnd:]
            return restEdgeList, restTrackList
        else:
            return None, None

    def printRouteDescription(self, route):
        print("start:")
        routeInfo = route.getRouteInfo()

        for routeInfoEntry in routeInfo:
            edgeList = routeInfoEntry["edgeList"]
            trackList = routeInfoEntry["trackList"]
            print(trackList)
            indexEnd = 0
            lastEdgeId = None

            while True:
                edgeList, trackList = self.getTrackListFromEdge(indexEnd, edgeList, trackList)

                (direction, _, crossingInfo, _, _, lastEdgeId) = osmParserData.getNextCrossingInfo(trackList)

                if lastEdgeId != None:
                    indexEnd = edgeList.index(lastEdgeId) + 1
                else:
                    indexEnd = len(edgeList)

                trackListPart = trackList[0:indexEnd]

                name, nameRef = trackListPart[0]["info"]
                sumLength = 0
                for trackItem in trackListPart:
                    length = trackItem["length"]
                    sumLength = sumLength + length

                print("%s %s %d" % (name, nameRef, sumLength))
                if crossingInfo != None:
                    print("%s %s" % (crossingInfo, self.osmutils.directionName(direction)))

                if indexEnd == len(edgeList):
                    break

        print("end:")

    def showTrackOnMousePos(self, x, y):
        (lat, lon) = self.getPosition(x, y)
        self.showTrackOnPos(lat, lon, self.track, self.speed, True, True)

    def getPosition(self, x, y):
        point = QPointF(x, y)
        invertedTransform = self.transformHeading.inverted()
        point0 = invertedTransform[0].map(point)
        map_x, map_y = self.getMapZeroPos()
        rlat = self.osmutils.pixel2lat(self.map_zoom, map_y + point0.y());
        rlon = self.osmutils.pixel2lon(self.map_zoom, map_x + point0.x());
        mouseLat = self.osmutils.rad2deg(rlat)
        mouseLon = self.osmutils.rad2deg(rlon)
        return (mouseLat, mouseLon)

    def loadConfig(self, config):
        section = "routing"
        if config.hasSection(section):
            self.osmWidget.setRoutingModeId(config.getSection(section).getint("routingmode", 0))

            for name, value in config.items(section):
                if name[:5] == "point":
                    point = OSMRoutingPoint()
                    point.readFromConfig(value)
                    point.resolveFromPos(osmParserData)

                    if point.getType() == OSMRoutingPoint.TYPE_START:
                        self.startPoint = point
                    if point.getType() == OSMRoutingPoint.TYPE_END:
                        self.endPoint = point
                    if point.getType() == OSMRoutingPoint.TYPE_WAY:
                        self.wayPoints.append(point)
                    if point.getType() == OSMRoutingPoint.TYPE_MAP:
                        self.mapPoint = point

                    if not point.isValid():
                        print("failed to resolve point %s" % (value))

        section = "mapPoints"
        if config.hasSection(section):
            for name, value in config.items(section):
                if name[:5] == "point":
                    point = OSMRoutingPoint()
                    point.readFromConfig(value)
                    if point.getType() == OSMRoutingPoint.TYPE_MAP:
                        self.mapPoint = point

        section = "route"
        self.routeList = list()
        if config.hasSection(section):
            for name, value in config.items(section):
                if name[:5] == "route":
                    route = OSMRoute()
                    route.readFromConfig(value)
                    self.routeList.append(route)

    def saveConfig(self, config):
        section = "routing"
        config.removeSection(section)
        config.addSection(section)

        config.getSection(section)["routingmode"] = str(self.osmWidget.getRoutingModeId())

        i = 0
        if self.startPoint != None:
            self.startPoint.saveToConfig(config, section, "point%d" % (i))
            i = i + 1

        for point in self.wayPoints:
            point.saveToConfig(config, section, "point%d" % (i))
            i = i + 1

        if self.endPoint != None:
            self.endPoint.saveToConfig(config, section, "point%d" % (i))

        section = "mapPoints"
        config.removeSection(section)
        config.addSection(section)
        i = 0
        if self.mapPoint != None:
            self.mapPoint.saveToConfig(config, section, "point%d" % (i))

        section = "route"
        config.removeSection(section)
        config.addSection(section)
        i = 0
        for route in self.routeList:
            route.saveToConfig(config, section, "route%d" % (i))
            i = i + 1

    def setStartPoint(self, point):
        self.startPoint = point
        self.startPoint.type = 0
        self.update()

    def setEndPoint(self, point):
        self.endPoint = point
        self.endPoint.type = 1
        self.update()

    def setWayPoint(self, point):
        point.type = 2
        self.wayPoints.append(point)
        self.update()

    def showError(self, title, text):
        msgBox = QMessageBox(QMessageBox.Warning, title, text, QMessageBox.Ok, self)
        font = self.font()
        font.setPointSize(14)
        msgBox.setFont(font)
        msgBox.exec()

#---------------------


class OSMWidget(QWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.startLat = 47.8
        self.startLon = 13.0
        self.favoriteList = list()
        self.mapWidgetQt = QtOSMWidget(self)

        self.incLat = 0.0
        self.incLon = 0.0
        self.step = 0
        self.trackLogLines = None
        self.trackLogLine = None
        self.osmUtils = OSMUtils()
        osmParserData.openAllDB()

    def addToWidget(self, vbox):
        hbox1 = QHBoxLayout()
        hbox1.addWidget(self.mapWidgetQt)
        vbox.addLayout(hbox1)

    def initWorkers(self):
        self.downloadThread = OSMDownloadTilesWorker(self, self.getTileServer())
        self.downloadThread.updateMapSignal.connect(self.mapWidgetQt.updateMap)
        self.downloadThread.updateStatusSignal.connect(self.mapWidgetQt.updateStatusLabel)

    @pyqtSlot()
    def _searchPOIName(self):
        self.searchPOI(False)

    @pyqtSlot()
    def _searchPOINearest(self):
        self.searchPOI(True)

    def searchPOI(self, nearest):
        mapPosition = self.mapWidgetQt.getMapPosition()

        # we always use map position for country pre selection
        defaultCountryId = osmParserData.getCountryOnPointWithGeom(mapPosition[0], mapPosition[1])
        poiDialog = OSMPOISearchDialog(self, osmParserData, mapPosition, defaultCountryId, nearest)
        result = poiDialog.exec()
        if result == QDialog.Accepted:
#            poiEntry, pointType=poiDialog.getResult()
            pointDict = poiDialog.getResult2()
            for pointType, poiEntry in pointDict.items():
                (refId, lat, lon, tags, nodeType, cityId, distance, displayString) = poiEntry
                displayString = osmParserData.getPOITagString(tags)
                self.setPoint(displayString, pointType, lat, lon)

    def showError(self, title, text):
        msgBox = QMessageBox(QMessageBox.Warning, title, text, QMessageBox.Ok, self)
        font = self.font()
        font.setPointSize(14)
        msgBox.setFont(font)
        msgBox.exec()

    def getOptionsConfig(self, optionsConfig):
        optionsConfig["withShow3D"] = self.getShow3DValue()
        optionsConfig["withShowAreas"] = self.getShowAreas()
        optionsConfig["withShowPOI"] = self.getShowPOI()
        optionsConfig["withShowSky"] = self.getShowSky()
        optionsConfig["XAxisRotation"] = self.getXAxisRotation()
        optionsConfig["tileServer"] = self.getTileServer()
        optionsConfig["tileHome"] = self.getTileHome()
        optionsConfig["routingModes"] = self.getRoutingModes()
        optionsConfig["routingModeId"] = self.getRoutingModeId()
        optionsConfig["tileStartZoom"] = self.getTileStartZoom()
        optionsConfig["displayPOITypeList"] = list(self.getDisplayPOITypeList())
        optionsConfig["displayAreaTypeList"] = list(self.getDisplayAreaTypeList())
        optionsConfig["startZoom3D"] = self.getStartZoom3DView()

        return optionsConfig

    def setFromOptionsConfig(self, optionsConfig):
        self.setShow3DValue(optionsConfig["withShow3D"])
        self.setShowAreas(optionsConfig["withShowAreas"])
        self.setShowPOI(optionsConfig["withShowPOI"])
        self.setShowSky(optionsConfig["withShowSky"])
        self.setXAxisRotation(optionsConfig["XAxisRotation"])
        self.setTileServer(optionsConfig["tileServer"])
        self.setTileHome(optionsConfig["tileHome"])
        self.setTileStartZoom(optionsConfig["tileStartZoom"])
        self.setDisplayPOITypeList(optionsConfig["displayPOITypeList"])
        self.setDisplayAreaTypeList(optionsConfig["displayAreaTypeList"])
        self.setStartZoom3DView(optionsConfig["startZoom3D"])
        self.setRoutingMode(optionsConfig["routingMode"])

    @pyqtSlot()
    def _showSettings(self):
        optionsDialog = OSMOptionsDialog(self.getOptionsConfig(dict()), self)
        result = optionsDialog.exec()
        if result == QDialog.Accepted:
            self.setFromOptionsConfig(optionsDialog.getOptionsConfig())

            self.mapWidgetQt.clearPolygonCache()
            self.update()

    @pyqtSlot()
    def _cleanup(self):
        trackLog.closeLogFile()

        if self.downloadThread.isRunning():
            self.downloadThread.stop()

        osmParserData.closeAllDB()

    def init(self, lat, lon, zoom):
        self.mapWidgetQt.init()
        self.mapWidgetQt.show(zoom, lat, lon)

    def setStartLongitude(self, lon):
        self.startLon = lon

    def setStartLatitude(self, lat):
        self.startLat = lat

    def initHome(self):
        self.init(self.startLat, self.startLon, self.getZoomValue())

    # def checkDownloadServer(self):
    #    try:
    #        socket.gethostbyname(self.getTileServer())
    #        self.updateStatusLabel("OSM download server ok")
    #        return True
    #    except socket.error:
    #       self.updateStatusLabel("OSM download server failed. Disabling")
    #        self.setWithDownloadValue(False)
    #        return False

    def getZoomValue(self):
        return self.mapWidgetQt.map_zoom

    def setZoomValue(self, value):
        self.mapWidgetQt.map_zoom = value

    def getShow3DValue(self):
        return self.mapWidgetQt.show3D

    def setShow3DValue(self, value):
        self.mapWidgetQt.show3D = value

    def getShowAreas(self):
        return self.mapWidgetQt.withShowAreas

    def setShowAreas(self, value):
        self.mapWidgetQt.withShowAreas = value

    def getShowPOI(self):
        return self.mapWidgetQt.withShowPOI

    def setShowPOI(self, value):
        self.mapWidgetQt.withShowPOI = value

    def getShowSky(self):
        return self.mapWidgetQt.showSky

    def setShowSky(self, value):
        self.mapWidgetQt.showSky = value

    def getXAxisRotation(self):
        return self.mapWidgetQt.XAxisRotation

    def setXAxisRotation(self, value):
        self.mapWidgetQt.XAxisRotation = value

    def getTileHome(self):
        return self.mapWidgetQt.tileHome

    def setTileHome(self, value):
        self.mapWidgetQt.tileHome = value

    def getTileServer(self):
        return self.mapWidgetQt.tileServer

    def setTileServer(self, value):
        self.mapWidgetQt.tileServer = value

    def getTileStartZoom(self):
        return self.mapWidgetQt.tileStartZoom

    def setTileStartZoom(self, value):
        self.mapWidgetQt.tileStartZoom = value

    def getVirtualZoom(self):
        return self.mapWidgetQt.isVirtualZoom

    def setVirtualZoom(self, value):
        self.mapWidgetQt.isVirtualZoom = value

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
        self.mapWidgetQt.startZoom3DView = value

    def getSidebarVisible(self):
        return self.mapWidgetQt.sidebarVisible

    def setSidebarVisible(self, value):
        self.mapWidgetQt.sidebarVisible = value

    def getRoutingModes(self):
        return osmParserData.getRoutingModes()

    def getRoutingModeId(self):
        return osmParserData.getRoutingModeId()

    def setRoutingMode(self, mode):
        return osmParserData.setRoutingMode(mode)

    def setRoutingModeId(self, modeId):
        return osmParserData.setRoutingModeId(modeId)

    def loadConfig(self, config):
        section = "display"
        self.setZoomValue(config.getSection(section).getint("zoom", 9))
        self.setStartLatitude(config.getSection(section).getfloat("lat", self.startLat))
        self.setStartLongitude(config.getSection(section).getfloat("lon", self.startLon))
        self.setTileHome(config.getSection(section).get("tileHome", defaultTileHome))
        self.setTileServer(config.getSection(section).get("tileServer", defaultTileServer))
        self.setShow3DValue(config.getSection(section).getboolean("with3DView", False))
        self.setShowAreas(config.getSection(section).getboolean("showAreas", False))
        self.setShowPOI(config.getSection(section).getboolean("showPOI", False))
        self.setShowSky(config.getSection(section).getboolean("showSky", False))
        self.setXAxisRotation(config.getSection(section).getint("XAxisRotation", 60))
        self.setTileStartZoom(config.getSection(section).getint("tileStartZoom", defaultTileStartZoom))
        self.setVirtualZoom(config.getSection(section).getboolean("virtualZoom", False))
        self.setStartZoom3DView(config.getSection(section).getint("startZoom3D", defaultStart3DZoom))
        self.setSidebarVisible(config.getSection(section).getboolean("sidebarVisible", True))

        section = "poi"
        if config.hasSection(section):
            poiTypeList = list()
            for name, value in config.items(section):
                if name[:7] == "poitype":
                    poiTypeList.append(int(value))
            self.setDisplayPOITypeList(poiTypeList)

        section = "area"
        if config.hasSection(section):
            areaTypeList = list()
            for name, value in config.items(section):
                if name[:8] == "areatype":
                    areaTypeList.append(int(value))
            self.setDisplayAreaTypeList(areaTypeList)

        section = "favorites"
        self.favoriteList = list()
        if config.hasSection(section):
            for name, value in config.items(section):
                if name[:8] == "favorite":
                    favoritePoint = OSMRoutingPoint()
                    favoritePoint.readFromConfig(value)
                    self.favoriteList.append(favoritePoint)

        self.mapWidgetQt.loadConfig(config)
        loadDialogSettings(config)

    def saveConfig(self, config):
        section = "display"
        config.removeSection(section)
        config.addSection(section)

#        print("withDownload: %s"%(self.getWithDownloadValue()))
        config.getSection(section)["zoom"] = str(self.getZoomValue())
        config.getSection(section)["with3DView"] = str(self.getShow3DValue())
#        config.getSection(section)["showBackgroundTiles"]=str(self.getShowBackgroundTiles())
        config.getSection(section)["showAreas"] = str(self.getShowAreas())
        config.getSection(section)["showPOI"] = str(self.getShowPOI())
        config.getSection(section)["showSky"] = str(self.getShowSky())
        config.getSection(section)["XAxisRotation"] = str(self.getXAxisRotation())
        config.getSection(section)["tileStartZoom"] = str(self.getTileStartZoom())
        config.getSection(section)["virtualZoom"] = str(self.getVirtualZoom())
        config.getSection(section)["startZoom3D"] = str(self.getStartZoom3DView())
        config.getSection(section)["sidebarVisible"] = str(self.getSidebarVisible())

        config.getSection(section)["lat"] = "%.6f" % self.mapWidgetQt.osmutils.rad2deg(self.mapWidgetQt.center_rlat)
        config.getSection(section)["lon"] = "%.6f" % self.mapWidgetQt.osmutils.rad2deg(self.mapWidgetQt.center_rlon)

        config.getSection(section)["tileHome"] = self.getTileHome()
        config.getSection(section)["tileServer"] = self.getTileServer()

        section = "poi"
        config.removeSection(section)
        config.addSection(section)
        i = 0
        self.getDisplayPOITypeList().sort()
        for poiType in self.getDisplayPOITypeList():
            config.set(section, "poiType%d" % (i), str(poiType))
            i = i + 1

        section = "area"
        config.removeSection(section)
        config.addSection(section)
        i = 0
        self.getDisplayAreaTypeList().sort()
        for areaType in self.getDisplayAreaTypeList():
            config.set(section, "areaType%d" % (i), str(areaType))
            i = i + 1

        section = "favorites"
        config.removeSection(section)
        config.addSection(section)
        i = 0
        for point in self.favoriteList:
            point.saveToConfig(config, section, "favorite%d" % (i))
            i = i + 1

        self.mapWidgetQt.saveConfig(config)

        saveDialogSettings(config)

    def _showSearchMenu(self):
        menu = QMenu(self)
        searchAddressAction = QAction("Address", self)
        searchPOINameAction = QAction("POI by Name", self)
        searchPOINearestAction = QAction("Nearest POI", self)

        menu.addAction(searchAddressAction)
        menu.addAction(searchPOINameAction)
        menu.addAction(searchPOINearestAction)

        action = menu.exec_(self.mapToGlobal(self.mapWidgetQt.searchRect.center()))
        if action == searchAddressAction:
            self.searchAddress()
        elif action == searchPOINameAction:
            self._searchPOIName()
        elif action == searchPOINearestAction:
            self._searchPOINearest()

    def setPoint(self, name, pointType, lat, lon):
        point = OSMRoutingPoint(name, pointType, (lat, lon))
        if pointType == OSMRoutingPoint.TYPE_START:
            point.resolveFromPos(osmParserData)
            self.mapWidgetQt.setStartPoint(point)
            self.mapWidgetQt.showPointOnMap(point)
            if not point.isValid():
                self.showError("Error", "Point not usable for routing.\nFailed to resolve way for point.")

        elif pointType == OSMRoutingPoint.TYPE_END:
            point.resolveFromPos(osmParserData)
            self.mapWidgetQt.setEndPoint(point)
            self.mapWidgetQt.showPointOnMap(point)
            if not point.isValid():
                self.showError("Error", "Point not usable for routing.\nFailed to resolve way for point.")

        elif pointType == OSMRoutingPoint.TYPE_WAY:
            point.resolveFromPos(osmParserData)
            self.mapWidgetQt.setWayPoint(point)
            self.mapWidgetQt.showPointOnMap(point)
            if not point.isValid():
                self.showError("Error", "Point not usable for routing.\nFailed to resolve way for point.")

        elif pointType == OSMRoutingPoint.TYPE_MAP:
            self.mapWidgetQt.mapPoint = point
            self.mapWidgetQt.showPointOnMap(point)

        elif pointType == OSMRoutingPoint.TYPE_TMP:
            self.mapWidgetQt.showPointOnMap(point)

        elif pointType == OSMRoutingPoint.TYPE_FAVORITE:
            self.favoriteList.append(point)

    def searchAddress(self):
        # we always use map position for country pre selection
        mapPosition = self.mapWidgetQt.getMapPosition()
        defaultCountryId = osmParserData.getCountryOnPointWithGeom(mapPosition[0], mapPosition[1])

        searchDialog = OSMAdressDialog(self, osmParserData, defaultCountryId)
        result = searchDialog.exec()
        if result == QDialog.Accepted:
#            address, pointType=searchDialog.getResult()
            pointDict = searchDialog.getResult2()
            for pointType, address in pointDict.items():
                name = osmParserData.getAddressTagString(address)
                (_, _, _, _, _, _, _, lat, lon) = address
                self.setPoint(name, pointType, lat, lon)

    @pyqtSlot()
    def _showFavorites(self):
        favoritesDialog = OSMFavoritesDialog(self, self.favoriteList)
        result = favoritesDialog.exec()
        if result == QDialog.Accepted:
#            point, pointType, favoriteList=favoritesDialog.getResult()
            pointDict, favoriteList = favoritesDialog.getResult2()
            self.favoriteList = favoriteList
            for pointType, point in pointDict.items():
                self.setPoint(point.getName(), pointType, point.getPos()[0], point.getPos()[1])

    @pyqtSlot()
    def _loadRoute(self):
        routeList = self.mapWidgetQt.getRouteList()
        loadRouteDialog = OSMRouteListDialog(self, routeList, True, True)
        result = loadRouteDialog.exec()
        if result == QDialog.Accepted:
            route, routeList = loadRouteDialog.getResult()
            self.mapWidgetQt.setRouteList(routeList)
            if route != None:
                self.mapWidgetQt.setRoute(route)
                route.resolveRoutingPoints(osmParserData)
                if not route.isValid():
                    self.showError("Error", "Route has invalid routing points")

                # zoom to route
                self.mapWidgetQt.zoomToCompleteRoute(route.getRoutingPointList())


class OSMWindow(QMainWindow):

    def __init__(self, parent):
        QMainWindow.__init__(self, parent)
        font = self.font()
        font.setPointSize(14)
        self.setFont(font)
        self.config = Config("osmmapviewer.cfg")
        self.initUI()

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
        self.statusbar = self.statusBar()
        self.progress = QProgressBar()
        self.statusbar.addPermanentWidget(self.progress)

        self.osmWidget = OSMWidget(self)
        self.osmWidget.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        self.setCentralWidget(self.osmWidget)

        # 47.820630:13.016850
        # 47.8209383, 13.0165364
        self.osmWidget.setStartLatitude(47.8209383)
        self.osmWidget.setStartLongitude(13.0165364)

        top = QVBoxLayout(self.osmWidget)
        self.osmWidget.addToWidget(top)
        self.osmWidget.loadConfig(self.config)

        self.osmWidget.initWorkers()

        self.osmWidget.initHome()

        self.osmWidget.mapWidgetQt.startProgressSignal.connect(self.startProgress)
        self.osmWidget.mapWidgetQt.stopProgressSignal.connect(self.stopProgress)
        self.osmWidget.mapWidgetQt.updateStatusSignal.connect(self.updateStatusLabel)

        self.setGeometry(0, 0, 1280, 1040)
        self.setWindowTitle('OSM')

        self.show()

    def updateStatusLabel(self, text):
        self.statusbar.showMessage(text)

    @pyqtSlot()
    def _cleanup(self):
        self.saveConfig()
        self.osmWidget._cleanup()

    def saveConfig(self):
        self.osmWidget.saveConfig(self.config)
        self.config.writeConfig()

    def showError(self, title, text):
        msgBox = QMessageBox(QMessageBox.Warning, title, text, QMessageBox.Ok, self)
        font = self.font()
        font.setPointSize(14)
        msgBox.setFont(font)
        msgBox.exec()


def main(argv):
    app = QApplication(sys.argv)
    osmWindow = OSMWindow(None)
    app.aboutToQuit.connect(osmWindow._cleanup)
    # signal.signal(signal.SIGUSR1, osmWindow.signal_handler)
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # timer = QTimer()
    # timer.start(2000)  # You may change this if you wish.
    # timer.timeout.connect(lambda: None)  # Let the interpreter run each 2000 ms.

    sys.exit(app.exec_())

if __name__ == "__main__":
#    cProfile.run('main(sys.argv)')
    main(sys.argv)
