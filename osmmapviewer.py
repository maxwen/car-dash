'''
Created on Dec 3, 2011

@author: maxl
'''

import sys
import math
import os
import signal
from PyQt4.QtCore import Qt, QSize, QPoint, QRect, pyqtSlot
from PyQt4.QtGui import QColor, QPalette, QVBoxLayout, QPushButton, QWidget, QPixmap, QSizePolicy, QPainter, QPen, QHBoxLayout, QApplication

TILESIZE=256
M_LN2=0.69314718055994530942    #log_e 2
displayWidth=800
displayHeight=350
#EXTRA_BORDER=(TILESIZE / 2)
EXTRA_BORDER=0
MIN_ZOOM=1
MAX_ZOOM=18
MAP_SCROLL_STEP=10

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
        self.map_x=0
        self.map_y=0
        self.map_zoom=3
        self.min_zoom=MIN_ZOOM
        self.max_zoom=MAX_ZOOM
        self.center_rlat = 0.0
        self.center_rlon=0.0
        self.gpsLatitude=0.0
        self.gpsLongitude=0.0
        self.osmutils=OSMUtils()
        self.init()
        self.tileCache=dict()

    def init(self):
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)        
        self.updateGeometry()
        
    def osm_gps_map_set_center(self, latitude, longitude):
        self.center_rlat = self.osmutils.deg2rad(latitude)
        self.center_rlon = self.osmutils.deg2rad(longitude)

#        print("%f %f %d"%(self.center_rlat, self.center_rlon, self.map_zoom))

        pixel_x = self.osmutils.lon2pixel(self.map_zoom, self.center_rlon)
        pixel_y = self.osmutils.lat2pixel(self.map_zoom, self.center_rlat)
#        print("%d %d"%(pixel_x, pixel_y))

        self.map_x = int(pixel_x - displayWidth/2)
        self.map_y = int(pixel_y - displayHeight/2)
        
#        print("after center %f %f %d %d %d"%(latitude, longitude, self.map_x, self.map_y, self.map_zoom))
        
    def osm_gps_map_set_zoom (self, zoom):
        width_center  = displayWidth / 2
        height_center = displayHeight / 2

        self.map_zoom = self.CLAMP(zoom, self.min_zoom, self.max_zoom)
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
        print("Fill tiles: %d,%d z:%d"% (self.map_x, self.map_y, self.map_zoom))

        offset_x = - self.map_x % TILESIZE;
        offset_y = - self.map_y % TILESIZE;
        
        if offset_x > 0:
            offset_x -= TILESIZE
        if offset_y > 0:
            offset_y -= TILESIZE

        offset_xn = offset_x + EXTRA_BORDER
        offset_yn = offset_y + EXTRA_BORDER
                
        tiles_nx = int((displayWidth  - offset_x) / TILESIZE + 1)
        tiles_ny = int((displayHeight - offset_y) / TILESIZE + 1)

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
    

    def osm_gps_get_tile(self, zoom, x, y, offset_x, offset_y):
        tileHome="/home/maxl/mapnik/tiles/"
        fileName=tileHome+str(zoom)+"/"+str(x)+"/"+str(y)+".png"
        if os.path.exists(fileName):
#            print("draw %s at %d %d"%(fileName, offset_x, offset_y))
            if not fileName in self.tileCache:
                pixbuf = QPixmap(fileName)
                self.tileCache[fileName]=pixbuf
            else:
                pixbuf=self.tileCache[fileName]
                
            self.painter.drawPixmap(offset_x, offset_y, TILESIZE, TILESIZE, pixbuf)
        else:
            pen=QPen()
            palette=QPalette()
            pen.setColor(palette.color(QPalette.Normal, QPalette.Background))
            self.painter.setPen(pen)
            self.painter.drawRect(offset_x, offset_y, TILESIZE, TILESIZE)
            
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

        self.painter.drawPoint(x, y)
        
    def osm_autocenter_map(self):
        pixel_x = self.osmutils.lon2pixel(self.map_zoom, self.gpsLongitude)
        pixel_y = self.osmutils.lat2pixel(self.map_zoom, self.gpsLatitude)
        x = pixel_x - self.map_x
        y = pixel_y - self.map_y
        width = displayWidth
        height = displayHeight
        if x < (width/2 - width/8) or x > (width/2 + width/8) or y < (height/2 - height/8) or y > (height/2 + height/8):
            self.map_x = pixel_x - width/2;
            self.map_y = pixel_y - height/2;
            self.center_coord_update();
            self.update()
        
    def show(self, zoom, lat, lon):
        self.osm_gps_map_set_center(lat, lon)
        self.osm_gps_map_set_zoom(zoom)
        self.update()
       
    def paintEvent(self, event):
        self.painter=QPainter(self) 
        self.osm_gps_map_fill_tiles_pixel()
        self.osm_gps_show_location()
                    
    def minimumSizeHint(self):
        return QSize(displayWidth, displayHeight)

    #def sizeHint(self):
    #    return QSize(displayWidth, displayHeight)

    def center_coord_update(self):
        pixel_x = self.map_x + displayWidth/2
        pixel_y = self.map_y + displayHeight/2

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
#        print(lat)
#        print(lon)
        self.gpsLatitude=self.osmutils.deg2rad(lat)
        self.gpsLongitude=self.osmutils.deg2rad(lon)
    
    def cleanImageCache(self):
        self.tileCache.clear()
        
class OSMWidget(QWidget):
    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.zoom=1
        self.startLat=0.0
        self.startLon=0.0
        
    def init(self):
        self.mapView.show(self.zoom, self.startLat, self.startLon)

    def addToWidget(self, parent):
        self.mapView=QtOSMWidget(self)
        parent.addWidget(self.mapView)
        
        hbox=QHBoxLayout()
        parent.addLayout(hbox)
        self.zoomInButton=QPushButton("+", self)
        self.zoomInButton.clicked.connect(self._zoomIn)
        hbox.addWidget(self.zoomInButton)
        
        self.zoomOutButton=QPushButton("-", self)
        self.zoomOutButton.clicked.connect(self._zoomOut)
        hbox.addWidget(self.zoomOutButton)
        
        self.stepUpButton=QPushButton("Up", self)
        self.stepUpButton.clicked.connect(self._stepUp)
        hbox.addWidget(self.stepUpButton)
        
        self.stepDownButton=QPushButton("Down", self)
        self.stepDownButton.clicked.connect(self._stepDown)
        hbox.addWidget(self.stepDownButton)
        
        self.stepLeftButton=QPushButton("Left", self)
        self.stepLeftButton.clicked.connect(self._stepLeft)
        hbox.addWidget(self.stepLeftButton)
        
        self.stepRightButton=QPushButton("Right", self)
        self.stepRightButton.clicked.connect(self._stepRight)
        hbox.addWidget(self.stepRightButton)
        
        self.centerGPSButton=QPushButton("GPS", self)
        self.centerGPSButton.clicked.connect(self._centerGPS)
        hbox.addWidget(self.centerGPSButton)
        
    def initUI(self):
        vbox = QVBoxLayout()
        vbox.setAlignment(Qt.AlignCenter)

        self.addToWidget(vbox)
        self.setLayout(vbox)
        
        self.zoom=1
        self.startLat=47.8
        self.startLon=13.0
        self.mapView.updateGPSLocation(self.startLat, self.startLon)
        self.mapView.show(self.zoom, self.startLat, self.startLon)

#        self.setGeometry(0, 0, 860, 500)
        self.setWindowTitle('OSM Test')
        self.show()

    @pyqtSlot()
    def _zoomIn(self):
        self.zoom=self.zoom+1
        if self.zoom>MAX_ZOOM:
            self.zoom=MAX_ZOOM
        self.mapView.show(self.zoom, self.startLat, self.startLon)
        
    @pyqtSlot()
    def _zoomOut(self):
        self.zoom=self.zoom-1
        if self.zoom<MIN_ZOOM:
            self.zoom=MIN_ZOOM
        self.mapView.show(self.zoom, self.startLat, self.startLon)

    @pyqtSlot()
    def _stepUp(self):
        self.mapView.stepUp(MAP_SCROLL_STEP)

    @pyqtSlot()
    def _stepDown(self):
        self.mapView.stepDown(MAP_SCROLL_STEP)
        
    @pyqtSlot()
    def _stepLeft(self):
        self.mapView.stepLeft(MAP_SCROLL_STEP)
        
    @pyqtSlot()
    def _stepRight(self):
        self.mapView.stepRight(MAP_SCROLL_STEP)  
    
    @pyqtSlot()
    def _centerGPS(self):
        self.mapView.updateGPSLocation(self.startLat, self.startLon)
        self.mapView.osm_autocenter_map()   
    
    def updateGPSPosition(self, lat, lon):
        self.mapView.updateGPSLocation(lat, lon)
        self.mapView.osm_autocenter_map()   
          
def main(argv): 
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    widget = OSMWidget(None)
    widget.initUI()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main(sys.argv)