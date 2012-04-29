'''
Created on Apr 30, 2012

@author: maxl
'''

import re

class GISUtils():
    
    def parseCoords(self, coordsStr):
        coords=list()
        x=re.findall(r'[0-9\.]+|[^0-9\.]+', coordsStr)
        i=0
        while i<len(x)-2:
            coords.append((float(x[i+2]), float(x[i])))
            i=i+4
        return coords
    
    def createCoordsFromMultiPolygon(self, coordsStr):
        allCoordsList=list()
        #MULTYPOLYGON(((
        coordsStr=coordsStr[15:-3]
        polyParts=coordsStr.split(")), ((")
        if len(polyParts)==1:
            polyParts2=coordsStr.split("), (")
            poly=polyParts2[0]
            coords=self.parseCoords(poly)

            allInnerCoords=list()
            for poly in polyParts2[1:]:
                innerCoords=self.parseCoords(poly)
                allInnerCoords.append(innerCoords)
                
            allCoordsList.append((coords, allInnerCoords))
        else:
            for poly in polyParts:
                polyParts2=poly.split("), (")                
                poly2=polyParts2[0]
                coords=self.parseCoords(poly2)
                
                allInnerCoords=list()
                for poly2 in polyParts2[1:]:
                    innerCoords=self.parseCoords(poly2)                        
                    allInnerCoords.append(innerCoords)

                allCoordsList.append((coords, allInnerCoords))
        
        return allCoordsList

    def createCoordsFromLineString(self, lineString):
        coordsStr=lineString[11:-1] # LINESTRING
        coords=self.parseCoords(coordsStr)
        return coords

    def createCoordsFromPolygon(self, polyString):
        coordsStr=polyString[9:-2] # POLYGON
        coords=self.parseCoords(coordsStr)
        return coords
    
    def createOuterCoordsFromMultiPolygon(self, coordsStr):
        allCoordsList=list()
        #MULTYPOLYGON(((
        coordsStr=coordsStr[15:-3]
        polyParts=coordsStr.split(")), ((")
        if len(polyParts)==1:
            polyParts2=coordsStr.split("), (")                
            poly=polyParts2[0]
            coords=self.parseCoords(poly)
            allCoordsList.append(coords)
        else:
            for poly in polyParts:
                polyParts2=poly.split("), (")
                poly2=polyParts2[0]
                coords=self.parseCoords(poly2)
                allCoordsList.append(coords)
        
        return allCoordsList
    
    def createCoordsString(self, coords):
        return ''.join(["%f %f"%(lon, lat)+"," for lat, lon in coords]) 
    
    def createLineStringFromCoords(self, coords):
        lineString="'LINESTRING("
        coordString=self.createCoordsString(coords)  
        coordString=coordString[:-1]
        lineString=lineString+coordString+")'"
        return lineString
    
    def createPolygonFromCoords(self, coords):
        polyString="'POLYGON(("
        coordString=self.createCoordsString(coords)  
        coordString=coordString[:-1]
        polyString=polyString+coordString+"))'"        
        return polyString
            
    def createMultiPolygonFromCoords(self, coords):
        polyString="'MULTIPOLYGON((("
        coordString=self.createCoordsString(coords)  
        coordString=coordString[:-1]
        polyString=polyString+coordString+")))'"        
        return polyString

    def createMultiPolygonPartFromCoordsWithInner(self, outerCoords, innerCoordsList):
        polyString="(("
        coordString=self.createCoordsString(outerCoords)  
        coordString=coordString[:-1]
        if len(innerCoordsList)!=0:
            for coords in innerCoordsList:
                polyString=polyString+coordString+"),("   
                coordString=self.createCoordsString(coords)             
                coordString=coordString[:-1]
        
        polyString=polyString+coordString+")),"                
        return polyString