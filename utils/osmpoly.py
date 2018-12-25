'''
Created on Dec 31, 2011

@author: maxl
'''

import os
import sys
import time
from ctypes import *

class point(Structure):
    _fields_ = [("y", c_double),
             ("x", c_double)]

class OSMPoly():
    def __init__(self):
        self.lib_pip = cdll.LoadLibrary("lib/point_in_poly.so")
        self.polyList=list()
        self.bbox=list()
        self.tags=list()
        self.cData=list()

    def getPolyData(self):
        allData=list()
        allData.append(self.polyList)
        allData.append(self.tags)
        allData.append(self.bbox)
        allData.append(self.cData)
        return allData
    
    def addPoly(self, polyData, tags):
        self.polyList.append(polyData)
        self.tags.append(tags)
        self.bbox.append(self.createBBoxForPoly(polyData))
        self.cData.append(self.createCData(polyData))
        
    def createBBoxForPoly(self, polyData):
        bbox=None
        for lon, lat in polyData:
            if bbox==None:
                bbox=[lon, lat, lon, lat]
            else:
                if lat>bbox[3]:
                    bbox[3]=lat
                if lat<bbox[1]:
                    bbox[1]=lat
                if lon>bbox[2]:
                    bbox[2]=lon
                if lon<bbox[0]:
                    bbox[0]=lon
                    
        return bbox
        
    def pointInsideBBox(self, bbox, lat, lon):
        topLeft=(bbox[0], bbox[1])
        bottomRight=(bbox[2], bbox[3])

        if topLeft[0] > bottomRight[0]:
            if topLeft[0] >= lon and bottomRight[0] <= lon and topLeft[1] <= lat and bottomRight[1] >= lat:
                return True
        else:
            if topLeft[0] <= lon and bottomRight[0] >= lon and topLeft[1] <= lat and bottomRight[1] >= lat:
                return True
            
        return False
    
    def resolvePoint(self, lat, lon):
        if lat==None or lon==None:
            return None
        
        i=0
        for i in range(0, len(self.polyList), 1):
            tags=self.tags[i]
            polygon=self.polyList[i]
            bbox=self.bbox[i]
            cPolygonDataList=self.cData[i]

            if self.pointInsideBBox(bbox, lat, lon):
#                print("in bbox of %s"%(tags))
#                if self.pointInPoly(lon, lat, polygon):
#                    return tags
            
                if self.callC(lon, lat, polygon, cPolygonDataList):
                    return tags
        return None
    
    def pointInPoly(self, x, y, poly):
        n = len(poly)
        inside = False
    
        p1x,p1y = poly[0]
        for i in range(n+1):
            p2x,p2y = poly[i % n]
            if y > min(p1y,p2y):
                if y <= max(p1y,p2y):
                    if x <= max(p1x,p2x):
                        if p1y != p2y:
                            xints = (y-p1y)*(p2x-p1x)/(p2y-p1y)+p1x
                        if p1x == p2x or x <= xints:
                            inside = not inside
            p1x,p1y = p2x,p2y
    
        return inside
    
    def createCData(self, polygon):
        pCArrayType=point*len(polygon)
        pCArray=pCArrayType()
        
        i=0
        for p in polygon:
            pCArray[i].x=p[0]
            pCArray[i].y=p[1]
            i=i+1

        return pCArray
            
    def callC(self, lon, lat, poly, cData):
        N=c_int(len(poly))
            
        p=point()
        p.x=lon
        p.y=lat
        ret=self.lib_pip.InsidePolygon(byref(cData), N, p)
        return ret
        
def main(argv):    
    None
    
if __name__ == "__main__":
    main(sys.argv)  