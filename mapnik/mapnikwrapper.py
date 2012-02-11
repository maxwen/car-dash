from math import pi,cos,sin,log,exp,atan
import sys, os, time
import mapnik2
from queue import Queue
import threading
from PyQt4.QtCore import SIGNAL, QObject

DEG_TO_RAD = pi/180
RAD_TO_DEG = 180/pi
MAX_ZOOM=18

def minmax (a,b,c):
    a = max(a,b)
    a = min(a,c)
    return a

class GoogleProjection:
    def __init__(self,levels=18):
        self.Bc = []
        self.Cc = []
        self.zc = []
        self.Ac = []
        c = 256
        for d in range(0,levels):
            e = c/2;
            self.Bc.append(c/360.0)
            self.Cc.append(c/(2 * pi))
            self.zc.append((e,e))
            self.Ac.append(c)
            c *= 2
                
    def fromLLtoPixel(self,ll,zoom):
        d = self.zc[zoom]
        e = round(d[0] + ll[0] * self.Bc[zoom])
        f = minmax(sin(DEG_TO_RAD * ll[1]),-0.9999,0.9999)
        g = round(d[1] + 0.5*log((1+f)/(1-f))*-self.Cc[zoom])
        return (e,g)
     
    def fromPixelToLL(self,px,zoom):
        e = self.zc[zoom]
        f = (px[0] - e[0])/self.Bc[zoom]
        g = (px[1] - e[1])/-self.Cc[zoom]
        h = RAD_TO_DEG * ( 2 * atan(exp(g)) - 0.5 * pi)
        return (f,h)

class RenderThread:
    def __init__(self, m, prj, tileproj):
        self.m=m
        self.prj=prj
        self.tileproj = tileproj

    def render_tile(self, tile_uri, x, y, z):
        # Calculate pixel positions of bottom-left & top-right
        p0 = (x * 256, (y + 1) * 256)
        p1 = ((x + 1) * 256, y * 256)

        # Convert to LatLong (EPSG:4326)
        l0 = self.tileproj.fromPixelToLL(p0, z);
        l1 = self.tileproj.fromPixelToLL(p1, z);

        # Convert to map projection (e.g. mercator co-ords EPSG:900913)
        c0 = self.prj.forward(mapnik2.Coord(l0[0],l0[1]))
        c1 = self.prj.forward(mapnik2.Coord(l1[0],l1[1]))

        # Bounding box for the tile
        if hasattr(mapnik2,'mapnik_version') and mapnik2.mapnik_version() >= 800:
            bbox = mapnik2.Box2d(c0.x,c0.y, c1.x,c1.y)
        else:
            bbox = mapnik2.Envelope(c0.x,c0.y, c1.x,c1.y)
        render_size = 256
        self.m.resize(render_size, render_size)
        self.m.zoom_to_box(bbox)
        self.m.buffer_size = 128

        # Render image with default Agg renderer
        im = mapnik2.Image(render_size, render_size)
        mapnik2.render(self.m, im)
        im.save(tile_uri, 'png256')

class MapnikWrapper(QObject):
    def __init__(self, d, m):
        QObject.__init__(self)
        self.map_file=m
        self.tile_dir=d
        if not self.tile_dir.endswith('/'):
            self.tile_dir = self.tile_dir + '/'
        
        if not os.path.isdir(self.tile_dir):
            os.makedirs(self.tile_dir)

        self.m = mapnik2.Map(256, 256)
        mapnik2.load_map(self.m, self.map_file, True)
        self.prj = mapnik2.Projection(self.m.srs)
        self.tileproj = GoogleProjection(MAX_ZOOM+1)
        self.render_thread = RenderThread(self.m, self.prj, self.tileproj)

    def render_tiles(self, bbox, zoom, name="unknown", tms_scheme=False):
        print(self.tile_dir)
    
        ll0 = (bbox[0],bbox[3])
        ll1 = (bbox[2],bbox[1])
        z=zoom
        
        px0 = self.tileproj.fromLLtoPixel(ll0,z)
        px1 = self.tileproj.fromLLtoPixel(ll1,z)

        # check if we have directories in place
        zoom = "%s" % z
        if not os.path.isdir(self.tile_dir + zoom):
            os.mkdir(self.tile_dir + zoom)
        for x in range(int(px0[0]/256.0),int(px1[0]/256.0)+1):
            # Validate x co-ordinate
            if (x < 0) or (x >= 2**z):
                continue
            # check if we have directories in place
            str_x = "%s" % x
            if not os.path.isdir(self.tile_dir + zoom + '/' + str_x):
                os.mkdir(self.tile_dir + zoom + '/' + str_x)
            for y in range(int(px0[1]/256.0),int(px1[1]/256.0)+1):
                # Validate x co-ordinate
                if (y < 0) or (y >= 2**z):
                    continue
                # flip y to match OSGEO TMS spec
                if tms_scheme:
                    str_y = "%s" % ((2**z-1) - y)
                else:
                    str_y = "%s" % y
                tile_uri = self.tile_dir + zoom + '/' + str_x + '/' + str_y + '.png'
                exists= ""
                if os.path.isfile(tile_uri):
                    exists= "exists"
                else:
                    self.render_thread.render_tile(tile_uri, x, y, z)  
                    self.emit(SIGNAL("updateMap()"))             
                print(name, ":", z, x, y, exists)
