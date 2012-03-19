'''
Created on Mar 17, 2012

@author: maxl
'''

import math

EPSILON=1e-12
GEOM_UNITSINDEGREE=10000000
GEOM_UNITSINMETER=100

GEOM_MINLON=(-180 * GEOM_UNITSINDEGREE)
GEOM_MAXLON=( 180 * GEOM_UNITSINDEGREE)
GEOM_MINLAT=(-90 * GEOM_UNITSINDEGREE)
GEOM_MAXLAT=( 90 * GEOM_UNITSINDEGREE)

GEOM_LONSPAN=(360 * GEOM_UNITSINDEGREE)
GEOM_LATSPAN=(180 * GEOM_UNITSINDEGREE)

GEOM_MERCATOR_MINLAT=(-85 * GEOM_UNITSINDEGREE)
GEOM_MERCATOR_MAXLAT=( 85 * GEOM_UNITSINDEGREE)

GEOM_DEG_TO_RAD=(math.pi / (180 * GEOM_UNITSINDEGREE))
GEOM_RAD_TO_DEG=((180 * GEOM_UNITSINDEGREE) / math.pi)

WGS84_EARTH_EQ_RADIUS=6378137.0
WGS84_EARTH_EQ_LENGTH=(math.pi * 2.0 * WGS84_EARTH_EQ_RADIUS)

class Vector():
    def __init__(self, x, y):
        self.x=x
        self.y=y
    
    def crossProduct(self, other):
        return Vector(self.x*other.y - self.y*other.x, self.x*other.y - self.y*other.x)
        
    def dotProduct(self, other):
        return self.x*other.x+ self.y*other.y
    
    def length(self):
        return math.sqrt(self.x*self.x + self.y*self.y)
    
    def normalize(self):
        length = self.length()
        if length == 0:
            return

        self.x /= length
        self.y /= length

    def normalized(self):
        length = self.length()
        if length == 0:
            return Vector(0.0, 0.0)

        return Vector(self.x / length, self.y / length)
    
    def __mul__(self, v):
        return Vector(self.x * v, self.y * v)
    
    def __div__(self, v):
        return Vector(self.x / v, self.y / v)

    def __truediv__(self, v):
        return Vector(self.x / v, self.y / v)
    
    def __add__(self, other):
        return Vector(self.x + other.x, self.y + other.y)
    
    def __sub__(self, other):
        return Vector(self.x - other.x, self.y - other.y)

    def __neg__(self):
        return Vector(-self.x, -self.y)

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y
    
    def __ne__(self, other):
        return self.x != other.x or self.y != other.y

    def __repr__(self):
        return "%f %f"%(self.x, self.y)
    
def toLocalMetric(what, ref):
    coslat = math.cos(ref.y * GEOM_DEG_TO_RAD)

    dx = (what.x - ref.x) / GEOM_LONSPAN * WGS84_EARTH_EQ_LENGTH * coslat;
    dy = (what.y - ref.y) / GEOM_LONSPAN * WGS84_EARTH_EQ_LENGTH;

    return Vector(dx, dy)

def fromLocalMetric(what, ref):
    coslat = math.cos(ref.y * GEOM_DEG_TO_RAD)

    x = ref.x;
    if coslat > EPSILON:
        x += round(what.x * GEOM_LONSPAN / WGS84_EARTH_EQ_LENGTH / coslat)

    y = ref.y + round(what.y * GEOM_LONSPAN / WGS84_EARTH_EQ_LENGTH)

    return Vector(x, y)