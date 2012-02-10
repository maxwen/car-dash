from math import pi,cos,sin,log,exp,atan
import sys, os, time
import mapnik2 as mapnik

DEG_TO_RAD = pi/180
RAD_TO_DEG = 180/pi

renderer=None

def minmax (a,b,c):
    a = max(a,b)
    a = min(a,c)
    return a

class GoogleProjection:
    def __init__(self,levels=19):
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
    def __init__(self, tile_dir, mapfile):
        if not tile_dir.endswith('/'):
            tile_dir = tile_dir + '/'
        self.tile_dir = tile_dir
        self.m = mapnik.Map(256, 256)
        # Load style XML
        mapnik.load_map(self.m, mapfile, True)
        # Obtain <Map> projection
        self.prj = mapnik.Projection(self.m.srs)
        # Projects between tile pixel co-ordinates and LatLong (EPSG:4326)
        self.tileproj = GoogleProjection()
        if not os.path.isdir(tile_dir):
            os.makedirs(tile_dir)

    def render_tile(self, tile_uri, x, y, z):
        start=time.time()
        # Calculate pixel positions of bottom-left & top-right
        p0 = (x * 256, (y + 1) * 256)
        p1 = ((x + 1) * 256, y * 256)

        # Convert to LatLong (EPSG:4326)
        l0 = self.tileproj.fromPixelToLL(p0, z);
        l1 = self.tileproj.fromPixelToLL(p1, z);

        # Convert to map projection (e.g. mercator co-ords EPSG:900913)
        c0 = self.prj.forward(mapnik.Coord(l0[0],l0[1]))
        c1 = self.prj.forward(mapnik.Coord(l1[0],l1[1]))

        # Bounding box for the tile
        if hasattr(mapnik,'mapnik_version') and mapnik.mapnik_version() >= 800:
            bbox = mapnik.Box2d(c0.x,c0.y, c1.x,c1.y)
        else:
            bbox = mapnik.Envelope(c0.x,c0.y, c1.x,c1.y)
        render_size = 256
        self.m.resize(render_size, render_size)
        self.m.zoom_to_box(bbox)
        self.m.buffer_size = 128
        print("%f"%(time.time()-start))

        # Render image with default Agg renderer
        im = mapnik.Image(render_size, render_size)
        start=time.time()
        mapnik.render(self.m, im)
        print("%f"%(time.time()-start))
        start=time.time()
        im.save(tile_uri, 'png256')
        print("%f"%(time.time()-start))

    def render_tiles(self, bbox, zoom):
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
                str_y = "%s" % y
                tile_uri = self.tile_dir + zoom + '/' + str_x + '/' + str_y + '.png'
                # Submit tile to be rendered into the queue
                if not os.path.exists(tile_uri):
                    print("render %s, %d %d %d"%(tile_uri, x, y, z))
                    self.render_tile(tile_uri, x, y, z)
