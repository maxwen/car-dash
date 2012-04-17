'''
Created on Dec 31, 2011

@author: maxl
'''

# read poly files
# query if a point lat, lon lies in a specific boarder
# return country name
import os
import sys
import time
import Polygon

class OSMBoarderUtils():
    def __init__(self, dataDir):
        self.polyData=list()
        self.dataDir=dataDir
        
    def initData(self):
        for polyFile in self.getAllPolyFiles():
            self.readPolyFile(polyFile)        

    def getDataDir(self):
        return self.dataDir

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
        while True:
            dummy = f.readline()
            if not(dummy):
                break
           
            cPolygon = self.readPolygon(f)
            if cPolygon != None:
                polygons.append(cPolygon)
                               
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
       
        if len(coords) < 3:
            return None
        
        return Polygon.Polygon(coords)
    
    def readPolyFile(self, fileName):
        f=open(fileName, "r")
        name = f.readline().strip()
        polygons = self.readMultiPolygon(f)     
        f.close()
        poly=dict()
        poly["name"]=name
        poly["coords"]=polygons
        self.polyData.append(poly)
    
    def countryNameOfPoint(self, lat, lon):
        for poly in self.polyData:
            name=poly["name"]
            polygons=poly["coords"]
            for cPolygon in polygons:
                if cPolygon.isInside(lon, lat):
                    return name
        return None
    
    def countryNameListOfBBox(self, bbox):
        nameList=list()
        print(bbox)
        bboxCPolygon=Polygon.Polygon([(bbox[0], bbox[3]), (bbox[2], bbox[3]), (bbox[2], bbox[1]), (bbox[0], bbox[1])])
        for poly in self.polyData:
            name=poly["name"]
            polygons=poly["coords"]
            for cPolygon in polygons:
                if cPolygon.overlaps(bboxCPolygon):
                    nameList.append(name)
                    
        return nameList
    
def main(argv):        
    bu=OSMBoarderUtils("/home/maxl/workspaces/pydev/car-dash/data3/poly-simple")
    bu.initData()
    
    lat=47.8205
    lon=13.0170

    start=time.time()
    print(bu.countryNameOfPoint(lat, lon))  
    end=time.time()
    print(end-start)
    
    lat=47.7692939563131    
    lon=12.91818334579633
    
    start=time.time()
    print(bu.countryNameOfPoint(lat, lon))  
    end=time.time()
    print(end-start)
    
    lat=47.83561
    lon=12.9949712
    start=time.time()
    print(bu.countryNameOfPoint(lat, lon))  
    end=time.time()
    print(end-start)
    
    lat=47.3488298
    lon=8.4264838
    start=time.time()
    print(bu.countryNameOfPoint(lat, lon))  
    end=time.time()
    print(end-start)

    lat=48.0226404
    lon=10.1370363
    start=time.time()
    print(bu.countryNameOfPoint(lat, lon))  
    end=time.time()
    print(end-start)
    
    lat=49.7012251
    lon=9.7963434
    start=time.time()
    print(bu.countryNameOfPoint(lat, lon))  
    end=time.time()
    print(end-start)
    
    lat=49.7861356
    lon=9.4873953
    start=time.time()
    print(bu.countryNameOfPoint(lat, lon))  
    end=time.time()
    print(end-start)
    
    lat=47.5052856
    lon=12.1236208
    start=time.time()
    print(bu.countryNameOfPoint(lat, lon))  
    end=time.time()
    print(end-start)
    
    lat=47.8365546
    lon=12.494849 
    start=time.time()
    print(bu.countryNameOfPoint(lat, lon))  
    end=time.time()
    print(end-start)
    
    lat=47.1381654
    lon=9.5227332
    start=time.time()
    print(bu.countryNameOfPoint(lat, lon))  
    end=time.time()
    print(end-start)
    
    lat=52.3850137
    lon=9.8277221
    start=time.time()
    print(bu.countryNameOfPoint(lat, lon))  
    end=time.time()
    print(end-start)
    
    lat=52.3864665
    lon=9.8288629
    start=time.time()
    print(bu.countryNameOfPoint(lat, lon))  
    end=time.time()
    print(end-start) 
        
    lat=50.7111547
    lon=7.0521705
    start=time.time()
    print(bu.countryNameOfPoint(lat, lon))  
    end=time.time()
    print(end-start)

    lat=47.835959
    lon=12.9945014
    start=time.time()
    print(bu.countryNameOfPoint(lat, lon))  
    end=time.time()
    print(end-start)
    
    lat=49.6093006
    lon=8.7411465
    start=time.time()
    print(bu.countryNameOfPoint(lat, lon))  
    end=time.time()
    print(end-start)
    
    lat=47.2968614
    lon=9.5550945
    start=time.time()
    print(bu.countryNameOfPoint(lat, lon))  
    end=time.time()
    print(end-start)
    
    lat=47.29675
    lon=9.55553
    start=time.time()
    print(bu.countryNameOfPoint(lat, lon))  
    end=time.time()
    print(end-start)
    
    lat=47.936814
    lon=12.9390762
    start=time.time()
    print(bu.countryNameOfPoint(lat, lon))  
    end=time.time()
    print(end-start)

    lat=48.4109412
    lon=13.4256467
    start=time.time()
    print(bu.countryNameOfPoint(lat, lon))  
    end=time.time()
    
    lat=48.4098733
    lon=13.4266383
    start=time.time()
    print(bu.countryNameOfPoint(lat, lon))  
    end=time.time()
    
    lat=49.4682774
    lon=11.0271253
    start=time.time()
    print(bu.countryNameOfPoint(lat, lon))  
    end=time.time()
    
    lat=49.467988
    lon=11.0278791
    start=time.time()
    print(bu.countryNameOfPoint(lat, lon))  
    end=time.time()
    
if __name__ == "__main__":
    main(sys.argv)  