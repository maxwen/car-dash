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
displayHeight=600
#EXTRA_BORDER=(TILESIZE / 2)
EXTRA_BORDER=0
MIN_ZOOM=1
MAX_ZOOM=18

class QtOSMWidget(QWidget):
    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.init()
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)        
        self.map_x=0
        self.map_y=0
        self.map_zoom=3
        self.min_zoom=1
        self.max_zoom=11
        self.center_rlat = 0.0
        self.center_rlon=0.0
        
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

    def osm_gps_map_set_center(self, latitude, longitude):
        self.center_rlat = self.deg2rad(latitude)
        self.center_rlon = self.deg2rad(longitude)

#        print("%f %f %d"%(self.center_rlat, self.center_rlon, self.map_zoom))

        pixel_x = self.lon2pixel(self.map_zoom, self.center_rlon)
        pixel_y = self.lat2pixel(self.map_zoom, self.center_rlat)
#        print("%d %d"%(pixel_x, pixel_y))

        self.map_x = int(pixel_x - displayWidth/2)
        self.map_y = int(pixel_y - displayHeight/2)
        
        print("after center %f %f %d %d %d"%(latitude, longitude, self.map_x, self.map_y, self.map_zoom))
        
    def osm_gps_map_set_zoom (self, zoom):
        width_center  = displayWidth / 2
        height_center = displayHeight / 2

        self.map_zoom = self.CLAMP(zoom, self.min_zoom, self.max_zoom)
        self.map_x = self.lon2pixel(self.map_zoom, self.center_rlon) - width_center
        self.map_y = self.lat2pixel(self.map_zoom, self.center_rlat) - height_center
        
        print("after zoom %d %d %d"%(self.map_x, self.map_y, self.map_zoom))


    def CLAMP(self, x, low, high):
        if x>high:
            return high
        elif x<low:
            return low
        return x
        
    def init(self):
        self.updateGeometry()
        self.update()        

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
        
        print("%d %d %d %d"%(tile_x0, tile_y0, tiles_nx, tiles_ny))
        while i<(tile_x0+tiles_nx):
            while j<(tile_y0+tiles_ny):
                print("%d %d"%(i, j))
                if j<0 or i<0 or i>=math.exp(self.map_zoom * M_LN2) or j>=math.exp(self.map_zoom * M_LN2):
                    print("else")
                else:
                    print("load tile %d %d %d %d %d"%(self.map_zoom, i, j, offset_xn, offset_yn))

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
            print("draw %s at %d %d"%(fileName, offset_x, offset_y))
            pixbuf = QPixmap(fileName)
            self.painter.drawPixmap(offset_x, offset_y, TILESIZE, TILESIZE, pixbuf)
        else:
            pen=QPen()
            palette=QPalette()
            pen.setColor(palette.color(QPalette.Normal, QPalette.Background))
            self.painter.setPen(pen)
            self.painter.drawRect(offset_x, offset_y, TILESIZE, TILESIZE)
            
    def showTile(self, zoom, lat, lon):
        self.osm_gps_map_set_center(lat, lon)
        self.osm_gps_map_set_zoom(zoom)
#        self.osm_gps_map_fill_tiles_pixel()
        self.update()

    def paintEvent(self, event):
        self.painter=QPainter(self) 

        self.osm_gps_map_fill_tiles_pixel()
        
                    
    def minimumSizeHint(self):
        return QSize(800, 600)

    def sizeHint(self):
        return QSize(800, 600)

class OSMExample(QWidget):
    def __init__(self):
        super(OSMExample, self).__init__()
        self.initUI()
        self.zoom=1
        
    def initUI(self):
        hbox = QHBoxLayout()
        self.mapView=QtOSMWidget(self)
        hbox.addWidget(self.mapView)
        self.zoom=1
        self.mapView.showTile(self.zoom, 47.8, 13.0)

        vbox=QVBoxLayout()
        hbox.addLayout(vbox)
        self.zoomInButton=QPushButton("+", self)
        self.zoomInButton.clicked.connect(self._zoomIn)
        vbox.addWidget(self.zoomInButton)
        
        self.zoomOutButton=QPushButton("-", self)
        self.zoomOutButton.clicked.connect(self._zoomOut)
        vbox.addWidget(self.zoomOutButton)
        
        self.setLayout(hbox)

        self.setGeometry(0, 0, 800, 600)
        self.setWindowTitle('OSM Test')
        self.show()

    @pyqtSlot()
    def _zoomIn(self):
        self.zoom=self.zoom+1
        if self.zoom>MAX_ZOOM:
            self.zoom=MAX_ZOOM
        self.mapView.showTile(self.zoom, 47.8, 13.0)
        
    @pyqtSlot()
    def _zoomOut(self):
        self.zoom=self.zoom-1
        if self.zoom<MIN_ZOOM:
            self.zoom=MIN_ZOOM
        self.mapView.showTile(self.zoom, 47.8, 13.0)

        
def main(argv): 
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    _ = OSMExample()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main(sys.argv)