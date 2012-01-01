'''
Created on Dec 31, 2011

@author: maxl
'''

# read poly files
# query if a point lat, lon lies in a specific boarder
# return country name
import os
import sys
from PyQt4.QtCore import QRect, QPoint

class OSMBoarderUtils():
    def __init__(self):
        self.polyData=list()
        self.bbox=list()
    
    def getDataDir(self):
        return os.path.join(os.environ['HOME'], "workspaces", "pydev", "car-dash", "data")

    def getAllPolyFiles(self):
        polyFiles=list()
        dir=self.getDataDir()
        for fileName in os.listdir(dir):
            try:
                basename, extension = fileName.split('.')
                if extension=="poly":
                    polyFiles.append(os.path.join(dir, fileName))
            except ValueError:
                None
        return polyFiles
    
    def getPolygon(self):
        return self.getAllPolyFiles()
    
    # Read a multipolygon from the file
    # First line: name (discarded)
    # Polygon: numeric identifier, list of lon, lat, END
    # Last line: END
    def readMultiPolygon(self, f):
        polygons = []
        self.bbox=list()

        while True:
            dummy = f.readline()
            if not(dummy):
                break
           
            polygon = self.readPolygon(f)
            if polygon != None:
                polygons.extend(polygon)
                               
        return polygons
    
    # Read a polygon from file
    # NB: holes aren't supported yet
    def readPolygon(self, f):
        coords = []
        first_coord = True
        while True:
            line = f.readline()
            if not(line):
                break;
                   
            line = line.strip()
            if line == "END":
                break
           
            # NOTE: needs to happen before not(line).
            # There can be a blank line in the poly file if the centroid wasn't calculated!
            if first_coord:
                first_coord = False
                continue       
           
            if not(line):
                continue
           
            ords = line.split()
            lon=float(ords[0])
            lat=float(ords[1])
            coords.append((lon, lat))
            
            if len(self.bbox)==0:
                self.bbox=[lon, lat, lon, lat]
            else:
                if lat>self.bbox[3]:
                    self.bbox[3]=lat
                if lat<self.bbox[1]:
                    self.bbox[1]=lat
                if lon>self.bbox[2]:
                    self.bbox[2]=lon
                if lon<self.bbox[0]:
                    self.bbox[0]=lon
       
        if len(coords) < 3:
            return None
        
        return coords
    
    def readPolyFile(self, fileName):
        f=open(fileName, "r")
        name = f.readline().strip()
        wkt = self.readMultiPolygon(f)     
        f.close()
        poly=dict()
        poly["name"]=name
        poly["coords"]=wkt
        poly["bbox"]=self.bbox
#        print(name)
#        print(self.bbox)
        self.polyData.append(poly)

    def countryNameOfPoint(self, lat, lon):
        if lat==None or lon==None:
            return None
        
        for poly in self.polyData:
            name=poly["name"]
            coords=poly["coords"]
            bbox=poly["bbox"]
            
#            print(name)
#            print(lat)
#            print(lon)
#            print(bbox)
#            if self.pointInPoly(lon, lat, coords):
#                return name
            
            topLeft=(bbox[0], bbox[1])
            bottomRight=(bbox[2], bbox[3])
            
            # checks to see if bounding box crosses 180 degrees
            if topLeft[0] > bottomRight[0]:
                if topLeft[0] >= lon and bottomRight[0] <= lon and topLeft[1] <= lat and bottomRight[1] >= lat:
                    if self.pointInPoly(lon, lat, coords):
                        return name
            else:
                if topLeft[0] <= lon and bottomRight[0] >= lon and topLeft[1] <= lat and bottomRight[1] >= lat:
                    if self.pointInPoly(lon, lat, coords):
                        return name

        
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
    
    def initData(self):
        for polyFile in self.getAllPolyFiles():
            self.readPolyFile(polyFile)
            
def main(argv):    
    bu=OSMBoarderUtils()
    bu.initData()
    
    lat=47.8205
    lon=13.0170

    print(bu.countryNameOfPoint(lat, lon))  
    
    lat=47.7692939563131    
    lon=12.91818334579633
    
    print(bu.countryNameOfPoint(lat, lon))  

if __name__ == "__main__":
    main(sys.argv)  