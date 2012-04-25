from math import pi,cos,sin,log,exp,atan, tan, radians, sinh, degrees
import sys, os, time
from queue import Queue
import threading
from PyQt4.QtCore import SIGNAL, QObject

disableMappnik=False
try:
    import mapnik2
except ImportError:
    print("mapnik is disabled")
    disableMappnik=True

DEG_TO_RAD = pi/180
RAD_TO_DEG = 180/pi
MAX_ZOOM=18
TILESIZE=256

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
        c = TILESIZE
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

def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - log(tan(lat_rad) + (1 / cos(lat_rad))) / pi) / 2.0 * n)
    return (xtile, ytile)

def num2deg(xtile, ytile, zoom):
    n = 2.0 ** zoom
    lon_deg = xtile / n * 360.0 - 180.0
    lat_rad = atan(sinh(pi * (1 - 2 * ytile / n)))
    lat_deg = degrees(lat_rad)
    return (lat_deg, lon_deg)

class RenderThread:
    def __init__(self, m, prj, tileproj):
        self.m=m
        self.prj=prj
        self.tileproj = tileproj

    def render_tile(self, tile_uri, x, y, z):
        # Calculate pixel positions of bottom-left & top-right
#        start=time.time()
#        p0 = (x * TILESIZE, (y + 1) * TILESIZE)
#        p1 = ((x + 1) * TILESIZE, y * TILESIZE)
#
#        # Convert to LatLong (EPSG:4326)
#        l0 = self.tileproj.fromPixelToLL(p0, z);
#        l1 = self.tileproj.fromPixelToLL(p1, z);
#
#        # Convert to map projection (e.g. mercator co-ords EPSG:900913)
#        c0 = self.prj.forward(mapnik2.Coord(l0[0],l0[1]))
#        c1 = self.prj.forward(mapnik2.Coord(l1[0],l1[1]))

        l0y, l0x=num2deg(x, y+1, z)
        l1y, l1x=num2deg(x+1, y, z)
        
        # Convert to map projection (e.g. mercator co-ords EPSG:900913)
        c0 = self.prj.forward(mapnik2.Coord(l0x,l0y))
        c1 = self.prj.forward(mapnik2.Coord(l1x,l1y))

        # Bounding box for the tile
        if hasattr(mapnik2,'mapnik_version') and mapnik2.mapnik_version() >= 800:
            bbox = mapnik2.Box2d(c0.x,c0.y, c1.x,c1.y)
        else:
            bbox = mapnik2.Envelope(c0.x,c0.y, c1.x,c1.y)
        render_size = TILESIZE
        self.m.resize(render_size, render_size)
        self.m.zoom_to_box(bbox)
        self.m.buffer_size = 128

        # Render image with default Agg renderer
        im = mapnik2.Image(render_size, render_size)
#        print("%f"%(time.time()-start))
#        start=time.time()
        mapnik2.render(self.m, im)
#        print("%f"%(time.time()-start))
#        start=time.time()
        im.save(tile_uri, 'png256')
#        print("%f"%(time.time()-start))

class MapnikWrapper(QObject):
    def __init__(self, d, m):
        QObject.__init__(self)
        self.map_file=m
        self.tile_dir=d
        if not self.tile_dir.endswith('/'):
            self.tile_dir = self.tile_dir + '/'
        
        if not os.path.isdir(self.tile_dir):
            os.makedirs(self.tile_dir)

        self.m = mapnik2.Map(TILESIZE, TILESIZE)
        mapnik2.load_map(self.m, self.map_file, True)
        self.prj = mapnik2.Projection(self.m.srs)
        self.tileproj = GoogleProjection(MAX_ZOOM+1)
        self.render_thread = RenderThread(self.m, self.prj, self.tileproj)

    def render_tiles(self, bbox, zoom, name="unknown", tms_scheme=False):
#        print(self.tile_dir)
    
        ll0 = (bbox[0],bbox[3])
        ll1 = (bbox[2],bbox[1])
        z=zoom
        
        px0 = self.tileproj.fromLLtoPixel(ll0,z)
        px1 = self.tileproj.fromLLtoPixel(ll1,z)

        # check if we have directories in place
        zoom = "%s" % z
#        if not os.path.isdir(self.tile_dir + zoom):
#            os.mkdir(self.tile_dir + zoom)
        for x in range(int(px0[0]/TILESIZE),int(px1[0]/TILESIZE)+1):
            # Validate x co-ordinate
            if (x < 0) or (x >= 2**z):
                continue
            # check if we have directories in place
            str_x = "%s" % x
            if not os.path.isdir(self.tile_dir + zoom + '/' + str_x):
                os.mkdir(self.tile_dir + zoom + '/' + str_x)
            for y in range(int(px0[1]/TILESIZE),int(px1[1]/TILESIZE)+1):
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
#                    self.emit(SIGNAL("updateMap()"))             
#                    print(name, ":", z, x, y, exists)

    def render_tiles2(self, bbox, zoom, name="unknown", tms_scheme=False):
#        print(self.tile_dir)
    
        px0 = (bbox[0],bbox[3])
        px1 = (bbox[2],bbox[1])
        z=zoom
        
#        px0 = self.tileproj.fromLLtoPixel(ll0,z)
#        px1 = self.tileproj.fromLLtoPixel(ll1,z)

        # check if we have directories in place
        zoom = "%s" % z
#        if not os.path.isdir(self.tile_dir + zoom):
#            os.mkdir(self.tile_dir + zoom)
        for x in range(int(px0[0]/TILESIZE),int(px1[0]/TILESIZE)+1):
            # Validate x co-ordinate
            if (x < 0) or (x >= 2**z):
                continue
            # check if we have directories in place
            str_x = "%s" % x
            if not os.path.isdir(self.tile_dir + zoom + '/' + str_x):
                os.mkdir(self.tile_dir + zoom + '/' + str_x)
            for y in range(int(px0[1]/TILESIZE),int(px1[1]/TILESIZE)+1):
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
#                    self.emit(SIGNAL("updateMap()"))             
#                    print(name, ":", z, x, y, exists)

    def render_tiles3(self, x, y, zoom, name="unknown", tms_scheme=False):
#        print(self.tile_dir)
    
        z=zoom

        # check if we have directories in place
        zoom = "%s" % z
#        if not os.path.isdir(self.tile_dir + zoom):
#            os.mkdir(self.tile_dir + zoom)
            
        # Validate x co-ordinate
        if (x < 0) or (x >= 2**z):
            return
        
        # check if we have directories in place
        str_x = "%s" % x
        if not os.path.isdir(self.tile_dir + zoom + '/' + str_x):
            os.mkdir(self.tile_dir + zoom + '/' + str_x)

        # Validate x co-ordinate
        if (y < 0) or (y >= 2**z):
            return
        
        # flip y to match OSGEO TMS spec
        if tms_scheme:
            str_y = "%s" % ((2**z-1) - y)
        else:
            str_y = "%s" % y
        tile_uri = self.tile_dir + zoom + '/' + str_x + '/' + str_y + '.png'
#        exists= ""
#        if os.path.isfile(tile_uri):
#            exists= "exists"
#        else:
        self.render_thread.render_tile(tile_uri, x, y, z)  
#        self.emit(SIGNAL("updateMap()"))  
#        print(z, x, y)           
