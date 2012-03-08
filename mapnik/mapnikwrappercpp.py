'''
Created on Mar 6, 2012

@author: maxl
'''
import os
from ctypes import *


class MapnikWrapperCPP():
    def __init__(self, mapFile):
        if os.path.exists("/usr/lib/libicuuc.so.42"):
            self.lib_mapnik = cdll.LoadLibrary("_mapnik_icu42.so")
        else:
            self.lib_mapnik = cdll.LoadLibrary("_mapnik_icu44.so")
        mapFileC=c_char_p(mapFile.encode(encoding='utf_8', errors='strict'))
        self.lib_mapnik.initC(mapFileC)

    def render_tile(self, tileUri, x, y, z):
        tileUriC=c_char_p(tileUri.encode(encoding='utf_8', errors='strict'))
        xC=c_int(x)
        yC=c_int(y)
        zC=c_int(z)
        self.lib_mapnik.render_tileC(tileUriC, xC, yC, zC)
