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

from PyQt4.QtCore import QAbstractTableModel, Qt, QSize, pyqtSlot, SIGNAL, QRect, QThread
from PyQt4.QtGui import QColor, QLineEdit, QHeaderView, QTableView, QDialog, QIcon, QLabel, QMenu, QAction, QMainWindow, QTabWidget, QCheckBox, QPalette, QVBoxLayout, QPushButton, QWidget, QPixmap, QSizePolicy, QPainter, QPen, QHBoxLayout, QApplication
from osmparser.osmparserdata import OSMParserData
from osmparser.osmutils import OSMUtils

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

#osmFile='/home/maxl/Downloads/salzburg-streets.osm.bz2'
osmFile='/home/maxl/Downloads/salzburg-city-streets.osm.bz2'
#osmFile='/home/maxl/Downloads/austria.osm.bz2'
#osmFile='/home/maxl/workspaces/pydev/car-dash/osmparser/test3.osm'
osmParserData = OSMParserData(osmFile)

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
        
#    def stop(self):
#        self.exiting = True
#        self.wait()
 
    def run(self):
        self.updateDataThreadState("run")
        while not self.exiting and True:
            osmParserData.initDB()
            self.exiting=True

        self.updateDataThreadState("stopped")
        self.updateStatusLabel("OSM stopped data load thread")

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
 
        map_x0 = self.map_x - EXTRA_BORDER
        map_y0 = self.map_y - EXTRA_BORDER
        x = self.osmutils.lon2pixel(self.map_zoom, self.gpsLongitude) - map_x0
        y = self.osmutils.lat2pixel(self.map_zoom, self.gpsLatitude) - map_y0

        if self.stop==True:
            self.painter.drawPixmap(int(x-self.gpsPointImageStop.width()/2), int(y-self.gpsPointImageStop.height()/2), self.gpsPointImageStop)
        else:
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
        
    def osm_center_map_to_GPS(self):
        self.osm_center_map_to(self.gpsLatitude, self.gpsLongitude)
            
    def osm_center_map_to(self, lat, lon):
        if lat!=0.0 and lon!=0.0:
            pixel_x = self.osmutils.lon2pixel(self.map_zoom, lon)
            pixel_y = self.osmutils.lat2pixel(self.map_zoom, lat)
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
        self.painter.end()
              
#    def setRotation(self, r):
#        self.painter.save()
#        self.painter.translate(TILESIZE/2,TILESIZE/2)
#        self.painter.rotate(90)
#        self.painter.translate(-TILESIZE/2,-TILESIZE/2);
    
    def showTrack(self):
        if self.track!=None:
            redPen=QPen()
            redPen.setColor(QColor(255, 0, 0))
            redPen.setWidth(4)
            redPen.setCapStyle(Qt.RoundCap);
            redPen.setJoinStyle(Qt.RoundJoin)
            
            bluePen=QPen()
            bluePen.setColor(QColor(0, 0, 255))
            bluePen.setWidth(self.map_zoom)
            bluePen.setCapStyle(Qt.RoundCap);

            greenPen=QPen()
            greenPen.setColor(QColor(0, 255, 0))
            greenPen.setWidth(self.map_zoom)
            greenPen.setCapStyle(Qt.RoundCap);
            
            motorwayPen=QPen()
            motorwayPen.setColor(QColor(0, 0, 200))
            motorwayPen.setWidth(4)
            motorwayPen.setCapStyle(Qt.RoundCap);
            
            primaryPen=QPen()
            primaryPen.setColor(QColor(100, 0, 0))
            primaryPen.setWidth(4)
            primaryPen.setCapStyle(Qt.RoundCap);
            
            residentialPen=QPen()
            residentialPen.setColor(QColor(0, 100, 0))
            residentialPen.setWidth(4)
            residentialPen.setCapStyle(Qt.RoundCap);
            
            linkPen=QPen()
            linkPen.setColor(QColor(0, 255, 255))
            linkPen.setWidth(4)
            linkPen.setCapStyle(Qt.RoundCap);
            
            for wayid in self.track:
                self.trackStartLon=0.0
                self.trackStartLat=0.0
                lastX=0
                lastY=0
                startNode=deque()
                node=None
                
                map_x0 = self.map_x - EXTRA_BORDER
                map_y0 = self.map_y - EXTRA_BORDER
    
                track= osmParserData.getStreetTrackList(wayid)
                if track==None:
                    print("no track found for %d"%(wayid))
                    continue
                
                for item in track:
                    if "lat" in item:
                        lat=item["lat"]
                    if "lon" in item:
                        lon=item["lon"]
                    if "ref" in item:
                        ref=item["ref"]
                        if ref in osmParserData.nodes:
                            node=osmParserData.nodes[ref]
                            
                    start=False
                    end=False
                    crossing=False
                    oneway=False
                    streetType=""
                    if "start" in item:
                        start=True
                    if "end" in item:
                        end=True
                    if"crossing" in item:
                        crossing=True
                    if"oneway" in item:
                        oneway=item["oneway"]
                    if "type" in item:
                        streetType=item["type"]
                    if not start and not end:
                        x=self.osmutils.lon2pixel(self.map_zoom, self.osmutils.deg2rad(lon)) - map_x0
                        y=self.osmutils.lat2pixel(self.map_zoom, self.osmutils.deg2rad(lat)) - map_y0
        
                        if lastX!=0 and lastY!=0:
                            pen=redPen
                            if streetType=="motorway":
                                pen=motorwayPen
                            elif streetType=="motorway_link":
                                pen=linkPen
                            elif streetType=="primary":
                                pen=primaryPen
                            elif streetType=="primary_link":
                                pen=linkPen
                            elif streetType=="residential":
                                pen=residentialPen
                            self.painter.setPen(pen)
                            self.painter.drawLine(x, y, lastX, lastY)
                            
                            if oneway:
                                self.painter.drawLine(x, y, lastX, lastY)

                        else:
#                            self.painter.setPen(greenPen)
#                            self.painter.drawPoint(x, y)
                            self.trackStartLon=lon
                            self.trackStartLat=lat
    
                        lastX=x
                        lastY=y
                        
                        if crossing:
                            self.painter.setPen(bluePen)
                            self.painter.drawPoint(x, y)
    
    #                    if node!=None:
    #                        tags,coords=node
    #                        if "highway" in tags:
    #                            nodeType=tags["highway"]
    #                            if nodeType=="motorway_junction":
    #                                self.painter.setPen(greenPen)
    #                                self.painter.drawPoint(x, y)
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
#        showTrackOnPosAction = QAction("Show Track", self)
        menu.addAction(forceDownloadAction)
#        menu.addAction(showTrackOnPosAction)
        action = menu.exec_(self.mapToGlobal(event.pos()))
        if action==forceDownloadAction:
            if self.withDownload==True:
                self.setForceDownload(True, True)
        
        self.mousePressed=False
        self.moving=False
        
    def showTrackOnPos(self, actlat, actlon):
        if self.osmWidget.dbLoaded==True:
            waylist=osmParserData.getWayIdListForPos(actlat, actlon)
            if waylist!=None and len(waylist)!=0:
                # TODO multiple ways?
                wayid=waylist[0]
                (name, ref)=osmParserData.getStreetInfoWithWayId(wayid)
                if name!=None:
                    self.emit(SIGNAL("updateTrackDisplay(QString)"), "%s-%s"%(name, ref))

                self.osmWidget.showWay(waylist)
                    
    def showTrackOnMousePos(self, x, y):
        if self.osmWidget.dbLoaded==True:
            (actlat, actlon)=self.getMousePosition(x, y)
            self.showTrackOnPos(actlat, actlon)

    def showTrackOnGPSPos(self, actlat, actlon):
        if self.osmWidget.dbLoaded==True:
            waylist=osmParserData.getWayIdListForPos(actlat, actlon)
            if waylist!=None and len(waylist)!=0:
                # TODO multiple ways?
                wayid=waylist[0]
                (name, ref)=osmParserData.getStreetInfoWithWayId(wayid)
                if name!=None:
                    self.emit(SIGNAL("updateTrackDisplay(QString)"), "%s-%s"%(name, ref))
                self.setTrack(waylist, False)
            
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
         
class OSMWayListTableModel(QAbstractTableModel):
    def __init__(self, parent):
        QAbstractTableModel.__init__(self, parent)
        
    def rowCount(self, parent): 
        return len(self.streetList)
    
    def columnCount(self, parent): 
        return 2
      
    def data(self, index, role):
        if role == Qt.TextAlignmentRole:
            return Qt.AlignLeft|Qt.AlignVCenter
        elif role != Qt.DisplayRole:
            return None
        
        if index.row() >= len(self.streetList):
            return ""
        (name, ref)=self.streetList[index.row()]

        if index.column()==0:
            return name
        elif index.column()==1:
            return ref
    def headerData(self, col, orientation, role):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                if col==0:
                    return "Street"
                elif col==1:
                    return "Ref"
            elif role == Qt.TextAlignmentRole:
                return Qt.AlignLeft
        return None
    
   
    def update(self, streetList):
        self.streetList=streetList
        self.reset()
        
class OSMWaySearchDialog(QDialog):
    def __init__(self, parent):
        QDialog.__init__(self, parent) 

        self.streetList=sorted(osmParserData.getStreetList().keys())
        self.filteredStreetList=self.streetList

        self.initUI()
        self.selectedStreet=None
         
    def nameSort(self, item):
       (name, ref)=item
       return name
   
    def getStreetName(self):
        return self.selectedStreet
#        return "Münchner Bundesstraße"
    
    def initUI(self):
        top=QVBoxLayout()
        top.setAlignment(Qt.AlignTop)
        
        self.filterEdit=QLineEdit(self)
        self.filterEdit.setToolTip('Id Filter')
        self.filterEdit.returnPressed.connect(self._applyFilter)
        self.filterEdit.textChanged.connect(self._applyFilter)
        top.addWidget(self.filterEdit)
        
        self.streetView=QTableView(self)
        top.addWidget(self.streetView)
        
        self.streetViewModel=OSMWayListTableModel(self)
        self.streetViewModel.update(self.filteredStreetList)
        self.streetView.setModel(self.streetViewModel)
        header=QHeaderView(Qt.Horizontal, self.streetView)
        header.setStretchLastSection(True)
        self.streetView.setHorizontalHeader(header)
        self.streetView.setColumnWidth(0, 300)

        buttons=QHBoxLayout()
        buttons.setAlignment(Qt.AlignBottom|Qt.AlignRight)
        
        self.cancelButton=QPushButton("Cancel", self)
        self.cancelButton.clicked.connect(self._cancel)
        buttons.addWidget(self.cancelButton)

        self.okButton=QPushButton("Ok", self)
        self.okButton.clicked.connect(self._ok)
        self.okButton.setEnabled(False)
        self.okButton.setDefault(True)
        buttons.addWidget(self.okButton)
        top.addLayout(buttons)
        
        self.connect(self.streetView.selectionModel(),
                     SIGNAL("selectionChanged(const QItemSelection &, const QItemSelection &)"), self._selectionChanged)

        self.setLayout(top)
        self.setWindowTitle('Way Search')
        self.setGeometry(0, 0, 400, 400)
        
    @pyqtSlot()
    def _selectionChanged(self):
        selmodel = self.streetView.selectionModel()
        current = selmodel.currentIndex()
        self.okButton.setEnabled(current.isValid())
        
    @pyqtSlot()
    def _cancel(self):
        self.done(QDialog.Rejected)
        
    @pyqtSlot()
    def _ok(self):
        selmodel = self.streetView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
#            print(self.filteredStreetList[current.row()])
            self.selectedStreet=self.filteredStreetList[current.row()]
#            print(self.selectedStreet)
        self.done(QDialog.Accepted)
        
    @pyqtSlot()
    def _clearTableSelection(self):
        self.streetView.clearSelection()
        self.okButton.setEnabled(False)
        
    @pyqtSlot()
    def _applyFilter(self):
        self._clearTableSelection()
        self.filterValue=self.filterEdit.text()
        if len(self.filterValue)!=0:
            if self.filterValue[-1]!="*":
                self.filterValue=self.filterValue+"*"
            self.filteredStreetList=list()
            filterValueMod=self.filterValue.replace("ue","ü").replace("ae","ä").replace("oe","ö")
            
            for (name, ref) in self.streetList:
                if not fnmatch.fnmatch(name.upper(), self.filterValue.upper()) and not fnmatch.fnmatch(name.upper(), filterValueMod.upper()):
                    continue
                self.filteredStreetList.append((name, ref))
        else:
            self.filteredStreetList=self.streetList
        
        self.streetViewModel.update(self.filteredStreetList)

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

        self.testTrackButton=QPushButton("Test Track", self)
        self.testTrackButton.clicked.connect(self._testTrack)
        buttons.addWidget(self.testTrackButton)

        self.searchWayButton=QPushButton("Show Way", self)
        self.searchWayButton.clicked.connect(self._showWay)
        self.searchWayButton.setDisabled(True)
        buttons.addWidget(self.searchWayButton)
                
#        self.showAllWayButton=QPushButton("Show All Ways", self)
#        self.showAllWayButton.clicked.connect(self._showAllWay)
#        self.showAllWayButton.setDisabled(True)
#        buttons.addWidget(self.showAllWayButton)
        
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

    @pyqtSlot()
    def _cleanup(self):
        if self.downloadThread.isRunning():
            self.downloadThread.stop()
#        osmParserData.closeDB()
        
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

    def saveConfig(self, config):
        config.getDefaultSection()["zoom"]=str(self.getZoomValue())
        config.getDefaultSection()["autocenterGPS"]=str(self.getAutocenterGPSValue())
        config.getDefaultSection()["withDownload"]=str(self.getWithDownloadValue())
        if self.mapWidgetQt.gpsLatitude!=0.0:
            config.getDefaultSection()["lat"]=str(self.mapWidgetQt.osmutils.rad2deg(self.mapWidgetQt.gpsLatitude))
        if self.mapWidgetQt.gpsLongitude!=0.0:    
            config.getDefaultSection()["lon"]=str(self.mapWidgetQt.osmutils.rad2deg(self.mapWidgetQt.gpsLongitude))

        config.getDefaultSection()["tileHome"]=self.getTileHome()
        config.getDefaultSection()["tileServer"]=self.getTileServer()
        
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
            self.searchWayButton.setDisabled(False)
            self.testTrackButton.setDisabled(False)
#            self.showAllWayButton.setDisabled(False)
            osmParserData.openDB()
            self.dbLoaded=True
        if state=="run":
            self.testTrackButton.setDisabled(True)

    def initParser(self):
        self.dataThread=OSMDataLoadWorker(self)
        self.connect(self.dataThread, SIGNAL("updateDataThreadState(QString)"), self.updateDataThreadState)
        self.connect(self.dataThread, SIGNAL("updateStatus(QString)"), self.updateStatusLabel)
        self.dataThread.setup()
        
    @pyqtSlot()
    def _testTrack(self):
        self.initParser()

    @pyqtSlot()
    def _showWay(self):
        searchDialog=OSMWaySearchDialog(self)
        result=searchDialog.exec()
        if result==QDialog.Accepted:
            (name, ref)=searchDialog.getStreetName()           
            waylist=osmParserData.getStreetWayList(name, ref)
            if waylist!=None:
                self.showWay(waylist)
                self.app.processEvents()
        
                # TODO hack
                self.mapWidgetQt.osm_center_map_to(self.mapWidgetQt.osmutils.deg2rad(self.mapWidgetQt.trackStartLat),
                               self.mapWidgetQt.osmutils.deg2rad(self.mapWidgetQt.trackStartLon))
            else:
                print("no waylist for %s-%s"%(name, ref))
                
    def showWay(self, waylist):
#        for wayid in waylist:
#            trackList=osmParserData.streetIndex[wayid]["track"]
##                print(trackList)
#            for trackItem in trackList:
#                if "start" in trackItem:
#                    continue
#                if "end" in trackItem:
#                    continue
#                print("start="+str(trackItem))
#                break
#            for trackItem in trackList[::-1]:
#                if "start" in trackItem:
#                    continue
#                if "end" in trackItem:
#                    continue
#                print("end="+str(trackItem))
#                break
        
        self.mapWidgetQt.setTrack(waylist, True)

#    @pyqtSlot()
#    def _showAllWay(self):
#            allWays=list()
#            for waylist in osmParserData.streetNameIndex.values():
#                allWays.extend(waylist)
#                
#            self.mapWidgetQt.setTrack(allWays)
#            self.app.processEvents()
#                
#            # TODO hack
#            self.mapWidgetQt.osm_center_map_to(self.mapWidgetQt.osmutils.deg2rad(self.mapWidgetQt.trackStartLat),
#                                       self.mapWidgetQt.osmutils.deg2rad(self.mapWidgetQt.trackStartLon))

class OSMWindow(QMainWindow):
    def __init__(self, parent, app):
        QMainWindow.__init__(self, parent)
        font = self.font()
        font.setPointSize(14)
        self.setFont(font)
        self.incLat=0.0
        self.incLon=0.0
        self.initParserDone=False
        self.app=app
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

        self.osmWidget=OSMWidget(self, self.app)
        self.osmWidget.addToWidget(osmTabLayout)

        self.osmWidget.setZoomValue(13)
        self.startLat=47.8
        self.startLon=13.0
        self.osmWidget.initHome()

        self.connect(self.osmWidget.mapWidgetQt, SIGNAL("updateStatus(QString)"), self.updateStatusLabel)
        self.connect(self.osmWidget, SIGNAL("updateStatus(QString)"), self.updateStatusLabel)
        self.connect(self.osmWidget.downloadThread, SIGNAL("updateStatus(QString)"), self.updateStatusLabel)

        buttons=QHBoxLayout()        

        self.testGPSButton=QPushButton("Test GPS", self)
        self.testGPSButton.clicked.connect(self._testGPS)
        buttons.addWidget(self.testGPSButton)
                
        top.addLayout(buttons)
        
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
        self.osmWidget.updateGPSPosition(self.incLat, self.incLon) 
        
        print("%.0f meter"%(self.osmWidget.mapWidgetQt.osmutils.distance(self.startLat, self.startLon, self.incLat, self.incLon)))

    def updateStatusLabel(self, text):
        print(text)

    @pyqtSlot()
    def _cleanup(self):
        self.osmWidget._cleanup()

def main(argv): 
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
#    widget = OSMWidget(None)
#    widget.initUI()

    widget1 = OSMWindow(None, app)
    widget1.initUI()
    app.aboutToQuit.connect(widget1._cleanup)

    sys.exit(app.exec_())

if __name__ == "__main__":
    main(sys.argv)
