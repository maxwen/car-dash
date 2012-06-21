'''
Created on Apr 30, 2012

@author: maxl
'''

import re
from Polygon import Polygon

class GISUtils():
    
    def parseCoords(self, coordsStr):
        coords=list()
        x=re.findall(r'[0-9\.]+|[^0-9\.]+', coordsStr)
        i=0
        while i<len(x)-2:
            coords.append((float(x[i+2]), float(x[i])))
            i=i+4
        return coords
    
    def createCoordsFromPolygonString(self, coordsStr):
        x=coordsStr[:len("MULTIPOLYGON")]
        if x=="MULTIPOLYGON":
            return self.createCoordsFromMultiPolygon(coordsStr[15:-3])
        x=coordsStr[:len("POLYGON")]
        if x=="POLYGON":
            return self.createCoordsFromMultiPolygon(coordsStr[9:-2])
        return None
    
    def createCoordsFromMultiPolygon(self, coordsStr):
        allCoordsList=list()
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

    def createPointFromPointString(self, pointStr):
        pointStr=pointStr[6:-1]
        coordsPairs=pointStr.split(" ")
        lon=float(coordsPairs[0].lstrip().rstrip())
        lat=float(coordsPairs[1].lstrip().rstrip())
        return (lat, lon)
    
    def createCoordsFromLineString(self, lineString):
        coordsStr=lineString[11:-1] # LINESTRING
        coords=self.parseCoords(coordsStr)
        return coords
    
    def createCoordsString(self, coords):
        return ''.join(["%f %f"%(lon, lat)+"," for lat, lon in coords]) 
    
    def createPointStringFromCoords(self, lat, lon):
        pointString="'POINT("
        pointString=pointString+"%f %f"%(lon, lat)
        pointString=pointString+")'"
        return pointString
    
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
    
    def mergeWayRefs(self, allRefs, osmDataImport):
        refRings=list()
        refRingEntry=dict()
        refRing=list()
        wayIdList=list()
                
        while len(allRefs)!=0:
            refEntry=allRefs[0]
            
            wayId=refEntry[0]
            refs=refEntry[1]   
#            oneway=refEntry[2]  
            roundAbout=refEntry[3]
            wayIdList.append(wayId)
            refRingEntry["wayId"]=wayId
            
            if roundAbout==1 and refs[-1]==refs[0]:
                refRingEntry["refs"]=refs
                refRingEntry["wayIdList"]=wayIdList
                coords, newRefList=osmDataImport.createRefsCoords(refs)
                if len(coords)>=3:
                    cPolygon=Polygon(coords)
                    refRingEntry["polygon"]=cPolygon
                else:
                    refRingEntry["polygon"]=None
                refRingEntry["coords"]=coords
                refRingEntry["newRefs"]=newRefList
                
                refRings.append(refRingEntry)
                allRefs.remove(refEntry)
                refRingEntry=dict()
                refRing=list()
                wayIdList=list()
                continue
            
            refRing.extend(refs)
            allRefs.remove(refEntry)

            roundAboutClosed=False
            while True and roundAboutClosed==False:
                removedRefs=list()

                for refEntry in allRefs:
                    wayId=refEntry[0]
                    refs=refEntry[1]   
                    oneway=refEntry[2] 
                    newRoundAbout=refEntry[3]
                    
                    if roundAbout==1 and newRoundAbout==0:
                        continue
                    
                    if roundAbout==0 and newRoundAbout==1:
                        continue
                    
                    if roundAbout==1 and refRing[-1]==refRing[0]:
                        removedRefs.append(refEntry)
                        roundAboutClosed=True
                        break
                    
                    if refRing[-1]==refs[0]:
                        wayIdList.append(wayId)
                        refRing.extend(refs[1:])
                        removedRefs.append(refEntry)
                        continue
                    
                    if refRing[0]==refs[-1]:
                        wayIdList.append(wayId)
                        removedRefs.append(refEntry)
                        newRefRing=list()
                        newRefRing.extend(refs[:-1])
                        newRefRing.extend(refRing)
                        refRing=newRefRing
                        continue
                            
                    if (oneway==0 or oneway==2) and roundAbout==0:        
                        reversedRefs=list()
                        reversedRefs.extend(refs)
                        reversedRefs.reverse()
                        if refRing[-1]==reversedRefs[0]:
                            wayIdList.append(wayId)
                            refRing.extend(reversedRefs[1:])
                            removedRefs.append(refEntry)
                            continue
                        
                        if refRing[0]==reversedRefs[-1]:
                            wayIdList.append(wayId)
                            removedRefs.append(refEntry)
                            newRefRing=list()
                            newRefRing.extend(reversedRefs[:-1])
                            newRefRing.extend(refRing)
                            refRing=newRefRing
                            continue

                if len(removedRefs)==0:
                    break
                
                for refEntry in removedRefs:
                    allRefs.remove(refEntry)
                
            if len(refRing)!=0:
                refRingEntry["refs"]=refRing
                refRingEntry["wayIdList"]=wayIdList
                coords, newRefList=osmDataImport.createRefsCoords(refRing)
                if len(coords)>=3:
                    cPolygon=Polygon(coords)
                    refRingEntry["polygon"]=cPolygon
                else:
                    refRingEntry["polygon"]=None
                    
                refRingEntry["coords"]=coords
                refRingEntry["newRefs"]=newRefList
                refRings.append(refRingEntry)
            
            refRingEntry=dict()
            refRing=list()
            wayIdList=list()
            
        return refRings

    def mergeRelationRefs(self, osmid, allRefs, osmDataImport):
        refRings=list()
        refRingEntry=dict()
        refRing=list()
        wayIdList=list()
                
        while len(allRefs)!=0:
            refEntry=allRefs[0]
            
            wayId=refEntry[0]
            refs=refEntry[1]   
            wayIdList.append(wayId)
            refRingEntry["wayId"]=wayId
            
            refRing.extend(refs)
            allRefs.remove(refEntry)

            while True:
                removedRefs=list()

                for refEntry in allRefs:
                    wayId=refEntry[0]
                    refs=refEntry[1]   
                    
                    if refRing[-1]==refs[0]:
                        wayIdList.append(wayId)
                        refRing.extend(refs[1:])
                        removedRefs.append(refEntry)
                        continue
                    
                    if refRing[0]==refs[-1]:
                        wayIdList.append(wayId)
                        removedRefs.append(refEntry)
                        newRefRing=list()
                        newRefRing.extend(refs[:-1])
                        newRefRing.extend(refRing)
                        refRing=newRefRing
                        continue
                            
                    reversedRefs=list()
                    reversedRefs.extend(refs)
                    reversedRefs.reverse()
                    if refRing[-1]==reversedRefs[0]:
                        wayIdList.append(wayId)
                        refRing.extend(reversedRefs[1:])
                        removedRefs.append(refEntry)
                        continue
                    
                    if refRing[0]==reversedRefs[-1]:
                        wayIdList.append(wayId)
                        removedRefs.append(refEntry)
                        newRefRing=list()
                        newRefRing.extend(reversedRefs[:-1])
                        newRefRing.extend(refRing)
                        refRing=newRefRing
                        continue

                if len(removedRefs)==0:
                    break
                
                for refEntry in removedRefs:
                    allRefs.remove(refEntry)
                
            # only add complete rings
            if len(refRing)!=0 and refRing[0]==refRing[-1]:
                refRingEntry["refs"]=refRing
                refRingEntry["wayIdList"]=wayIdList
                coords, newRefList=osmDataImport.createRefsCoords(refRing)
                if len(coords)>=3:
                    cPolygon=Polygon(coords)
                    refRingEntry["polygon"]=cPolygon
                else:
                    refRingEntry["polygon"]=None
                    
                refRingEntry["coords"]=coords
                refRingEntry["newRefs"]=newRefList
                refRings.append(refRingEntry)
#            else:
#                osmDataImport.log("failed to create a closed ring for %s %s"%(osmid, refRing))
                
            refRingEntry=dict()
            refRing=list()
            wayIdList=list()
            
        return refRings
