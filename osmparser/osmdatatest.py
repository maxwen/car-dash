'''
Created on Dec 13, 2011

@author: maxl
'''
import sys
import pickle
import cProfile

from utils.progress import ProgressBar
from osmparser.osmdataaccess import Constants, OSMDataAccess

class OSMDataTest(OSMDataAccess):
    def __init__(self):
        super(OSMDataTest, self).__init__()
        
    def testAddressTable(self):
        self.cursorAdress.execute('SELECT * FROM addressTable')
        allentries=self.cursorAdress.fetchall()
        for x in allentries:
            addressId, refId, country, cityId, postCode, streetName, houseNumber, lat, lon=self.addressFromDB(x)
            self.log( "id: "+str(addressId) + " refId:"+str(refId) +" country: "+str(country)+" cityId: " + str(cityId) + " postCode: " + str(postCode) + " streetName: "+str(streetName) + " houseNumber:"+ str(houseNumber) + " lat:"+str(lat) + " lon:"+str(lon))
        
    def testRestrictionTable(self):
        self.cursorEdge.execute('SELECT * from restrictionTable ORDER by target')
        allentries=self.cursorEdge.fetchall()
        for x in allentries:
            restrictionId, target, viaPath, toCost=self.restrictionFromDB(x)
            self.log("id: "+str(restrictionId)+" target:"+str(target)+" viaPath:"+str(viaPath)+" toCost:"+str(toCost))
                
    def testPOIRefTable(self):
        self.cursorNode.execute('SELECT refId, refType, tags, type, layer, AsText(geom) FROM poiRefTable WHERE refId=382753138')

#        self.cursorNode.execute('SELECT refId, refType, tags, type, layer, country, city, AsText(geom) FROM poiRefTable')
        allentries=self.cursorNode.fetchall()
        for x in allentries:
            print("%s %s %s"%(x[0], x[1], pickle.loads(x[2])))
#            refId, lat, lon, tags, nodeType, layer, country, city=self.poiRefFromDB2(x)
#            self.log("ref: " + str(refId) + "  lat: " + str(lat) + "  lon: " + str(lon) + " tags:"+str(tags) + " nodeType:"+str(nodeType) + " layer:"+str(layer) + " country:"+str(country)+" city:"+str(city))
        
    def testWayTable(self):
        self.cursorWay.execute('SELECT * FROM wayTable WHERE wayId=147462600')
        allentries=self.cursorWay.fetchall()
        for x in allentries:
            wayId, tags, refs, streetTypeId, name, nameRef, oneway, roundabout, maxspeed, poiList=self.wayFromDB(x)
            self.log( "way: " + str(wayId) + " streetType:"+str(streetTypeId)+ " name:" +str(name) + " ref:"+str(nameRef)+" tags: " + str(tags) + "  refs: " + str(refs) + " oneway:"+str(oneway)+ " roundabout:"+str(roundabout) + " maxspeed:"+str(maxspeed)+" poilist:"+str(poiList))

    def testCrossingTable(self):
        self.cursorWay.execute('SELECT * FROM crossingTable')
        allentries=self.cursorWay.fetchall()
        for x in allentries:
            crossingEntryId, wayid, refId, wayIdList=self.crossingFromDB(x)
            self.log( "id: "+ str(crossingEntryId) + " wayid: " + str(wayid) +  " refId: "+ str(refId) + " wayIdList: " + str(wayIdList))
        
    def testEdgeTable(self):
        self.cursorEdge.execute('SELECT id, startRef, endRef, length, wayId, source, target, cost, reverseCost, AsText(geom) FROM edgeTable')
        allentries=self.cursorEdge.fetchall()
        for x in allentries:
            edgeId, startRef, endRef, length, wayId, source, target, cost, reverseCost, streetInfo, coords=self.edgeFromDBWithCoordsString(x)
            self.log( "edgeId: "+str(edgeId) +" startRef: " + str(startRef)+" endRef:"+str(endRef)+ " length:"+str(length)+ " wayId:"+str(wayId) +" source:"+str(source)+" target:"+str(target) + " cost:"+str(cost)+ " reverseCost:"+str(reverseCost)+ "streetInfo:" + str(streetInfo) + " coords:"+str(coords))
            
    def testAreaTable(self):
        self.cursorArea.execute('SELECT osmId, areaId, type, tags, layer, AsText(geom) FROM areaTable WHERE type=%d'%(Constants.AREA_TYPE_NATURAL))
        allentries=self.cursorArea.fetchall()
        for x in allentries:
            tags=self.decodeTags(x[3])
            if "natural" in tags:
                if tags["natural"]=="rock":
                    print("%s %s"%(x[0],tags))

#            osmId, areaType, tags, layer, polyStr=self.areaFromDBWithCoordsString(x)
#            print(polyStr)
#            self.log("osmId: "+str(osmId)+ " type: "+str(areaType) +" tags: "+str(tags)+ " layer: "+ str(layer)+" polyStr:"+str(polyStr))

#        tolerance=self.osmutils.degToMeter(10.0)
#        print(tolerance)
#        self.cursorArea.execute('SELECT osmId, type, tags, layer, AsText(SimplifyPreserveTopology(geom, %f)) FROM areaTable WHERE osmId=136661'%(tolerance))
#        allentries=self.cursorArea.fetchall()
#        for x in allentries:
#            osmId, areaType, tags, layer, polyStr=self.areaFromDBWithCoordsString(x)
#            print(polyStr)

#        self.cursorArea.execute('SELECT osmId, type, tags, layer, AsText(geom) FROM areaLineTable')
#        allentries=self.cursorArea.fetchall()
#        for x in allentries:
#            osmId, areaType, tags, layer, polyStr=self.areaFromDBWithCoordsString(x)
#            if areaType==Constants.AREA_TYPE_NATURAL and "natural" in tags and tags["natural"]=="cliff":
#                self.log("osmId: "+str(osmId)+ " type: "+str(areaType) +" tags: "+str(tags)+ " layer: "+ str(layer)+" polyStr:"+str(polyStr))

    def testAdminAreaTable(self):
        self.cursorAdmin.execute('SELECT osmId, tags, adminLevel, parent, AsText(geom) FROM adminAreaTable WHERE osmId=941794')
        allentries=self.cursorArea.fetchall()
        for x in allentries:
            osmId, tags, adminLevel, parent=self.adminAreaFromDBWithParent(x)
            self.log("%d %s"%(osmId, tags["name"]))
#            self.log("osmId: "+str(osmId)+ " tags: "+str(tags)+ " adminLevel: "+ str(adminLevel) + " parent:"+str(parent))

    def testCoordsTable(self):
#        self.cursorCoords.execute('SELECT * from coordsTable WHERE refId=98110819')
#        allentries=self.cursorCoords.fetchall()  
#        self.cursorCoords.execute('SELECT * from wayRefTable WHERE wayId=31664992')
#        allentries=self.cursorCoords.fetchall()  
#        self.log(allentries)
        None
                      
    def testEdgeTableGeom(self):
        self.cursorEdge.execute('SELECT AsText(geom) FROM edgeTable')
        allentries=self.cursorEdge.fetchall()
        for x in allentries:
            self.log(x)                 

#    def poiRefFromDB3(self, x):
#        refId=int(x[0])
#        tags=self.decodeTags(x[1])
#        poiType=int(x[2])      
#        lat, lon=self.getGISUtils().createPointFromPointString(x[3])
#        return (refId, tags, poiType, lat, lon)    
#      
#    # check all pois of refType=node
#    # inside an area with refType=way
#    # with the same tags. If yes remove the entry for the way                             
#    def removeUnnededPOIs(self):
#        nodeTypeList=self.createSQLFilterStringForIN([Constants.POI_TYPE_PARKING, Constants.POI_TYPE_CAMPING, Constants.POI_TYPE_SUPERMARKET, Constants.POI_TYPE_PLACE])
#        self.cursorNode.execute('SELECT refId, tags, type, AsText(geom) FROM poiRefTable WHERE refId=343552101 AND refType=0 AND type in %s'%(nodeTypeList))
#        allPOIRefs=self.cursorNode.fetchall()
#        
#        allRefLength=len(allPOIRefs)
#        allRefsCount=0
#        removeCount=0
#
#        prog = ProgressBar(0, allRefLength, 77)
#        
#        for x in allPOIRefs:
#            print(x)
#            (refId, tags, poiType, lat, lon)=self.poiRefFromDB3(x)
#            prog.updateAmount(allRefsCount)
#            print(prog, end="\r")
#            allRefsCount=allRefsCount+1
#
#            lonRangeMin, latRangeMin, lonRangeMax, latRangeMax=self.createBBoxAroundPoint(lat, lon, 0.0)       
##            self.cursorArea.execute('SELECT osmId FROM areaTable WHERE ROWID IN (SELECT rowid FROM idx_areaTable_geom WHERE rowid MATCH RTreeIntersects(%f, %f, %f, %f)) AND MbrContains(geom, MakePoint(%f, %f, 4236))'%(lonRangeMin, latRangeMin, lonRangeMax, latRangeMax, lon, lat))
#            self.cursorArea.execute('SELECT osmId FROM areaTable WHERE ROWID IN (SELECT rowid FROM idx_areaTable_geom WHERE rowid MATCH RTreeIntersects(%f, %f, %f, %f))'%(lonRangeMin, latRangeMin, lonRangeMax, latRangeMax))
#
#            areaList=self.cursorArea.fetchall()
#            for y in areaList:
#                print(y)
#                # in case of a wayRef polygon this is the wayId
#                areaId=int(y[0])   
#                # check if there is a poi node with this wayId         
#                self.cursorNode.execute('SELECT refId, tags, type, AsText(geom) FROM poiRefTable WHERE refId=%d AND (refType=1 OR refType=2)'%(areaId))
#                allPOIWayRefs=self.cursorNode.fetchall()
#            
#                for z in allPOIWayRefs:
#                    (refId1, tags1, poiType1, lat1, lon1)=self.poiRefFromDB3(z)
#                    # same poi type
#                    if poiType==poiType1:
#                        removeRef=None
#                        # a node POI "overrules" a way POI 
#                        # except it has no tags and the way POI has
##                        print("POI node %d %s is inside of POI area %d %s"%(refId, tags, refId1, tags1))
#                        if len(tags1)==0:
#                            removeRef=refId1
#                        elif len(tags)==0:
#                            removeRef=refId
#                        else:  
#                            if poiType==Constants.POI_TYPE_PLACE:
#                                if "name" in tags and "name" in tags1:
#                                    if tags["place"]==tags1["place"] and tags["name"]==tags1["name"]:
#                                        removeRef=refId1
#
#                            else:
##                                if not "name" in tags and "name" in tags1:
##                                    removeRef=refId
#                                    
#                                removeRef=refId1
#                        
#                        if removeRef!=None:
#                            print("remove %d"%(removeRef))
#                            self.cursorNode.execute("DELETE FROM poiRefTable WHERE refId=%d"%(removeRef))
#                            removeCount=removeCount+1
#                            
#        print("")   

def main(argv):    
    p = OSMDataTest()
      
    p.openAllDB()
#    p.cursorArea.execute("SELECT * FROM sqlite_master WHERE type='table'")
#    allentries=p.cursorArea.fetchall()
#    for x in allentries:
#        self.log(x)

#    p.cursorEdge.execute('SELECT * FROM geometry_columns')
#    allentries=p.cursorEdge.fetchall()
#    for x in allentries:
#        self.log(x)

#    si=p.encodeStreetInfo2(0, 1, 1, 1, 1)
#    self.log(p.decodeStreetInfo2(si))
#    si=p.encodeStreetInfo2(0, 1, 0, 1, 1)
#    self.log(p.decodeStreetInfo2(si))
#    si=p.encodeStreetInfo2(0, 0, 0, 1, 1)
#    self.log(p.decodeStreetInfo2(si))
#    si=p.encodeStreetInfo2(0, 0, 1, 0, 0)
#    self.log(p.decodeStreetInfo2(si))
#    si=p.encodeStreetInfo2(0, 2, 0, 0, 1)
#    self.log(p.decodeStreetInfo2(si))
#    si=p.encodeStreetInfo2(0, 2, 1, 1, 0)
#    self.log(p.decodeStreetInfo2(si))
   
#    lat=47.820928
#    lon=13.016525
#    p.testEdgeTableGeom()
#    p.testGeomColumns(lat, lon, 100.0)
#    p.testEdgeGeomWithBBox()
#    p.testEdgeGeomWithPoint()
#    p.testEdgeGeomWithCircle()
#    
#    p.testStreetTable2()
#    p.testEdgeTable()
#    p.testRefTable()
    p.testAreaTable()
       

#    self.log(p.getLenOfEdgeTable())
#    self.log(p.getEdgeEntryForEdgeId(6719))
#    self.log(p.getEdgeEntryForEdgeId(2024))

#    p.test()

#    p.testDBConistency()
#    p.testRestrictionTable()
#    p.recreateEdges()
#    p.recreateEdgeNodes()
#    p.createAllRefTableIndexesPost()

#    p.recreateCrossings()
#    p.recreateEdges()
    
#    p.testRoutes()
#    p.testWayTable()
#    p.recreateCostsForEdges()
#    p.removeOrphanedEdges()
#    p.removeOrphanedWays()
#    p.createGeomDataForEdgeTable()

#    p.createSpatialIndexForEdgeTable()
#    p.createSpatialIndexForGlobalTables()
#    p.createSpatialIndexForAreaTable()
    
#    p.parseAreas()
#    p.parseRelations()
    
#    p.parseAddresses()
#    p.parseAreas()
#    p.parseNodes()
#    p.testAddressTable()
#    p.testCoordsTable()
#    p.vacuumEdgeDB()
#    p.vacuumGlobalDB()
#    p.testPOIRefTable()
#    p.mergeEqualWayEntries()
    
#    p.mergeWayEntries()

#    p.cursorArea.execute("CREATE INDEX areaType_idx ON areaTable (type)")
#    p.cursorArea.execute("CREATE INDEX adminLeel_idx ON areaTable (adminLevel)")        
#    p.cursorArea.execute("CREATE INDEX areaLineType_idx ON areaLineTable (type)")
#    p.vacuumAreaDB()
#    p.resolvePOIRefs()
#    p.resolveAdminAreas()
#    p.resolveAddresses(False)
#    p.testAdminAreaTable()

#    self.log(p.bu.getPolyCountryList())
#    p.cursorArea.execute('DELETE from adminAreaTable WHERE osmId=%d'%(1609521))
#    p.cursorArea.execute('DELETE from adminAreaTable WHERE osmId=%d'%(1000001))
#    p.cursorArea.execute('DELETE from adminAreaTable WHERE osmId=%d'%(1000000))
#    polyString="'MULTIPOLYGON("
#
#    outerCoords=[(20,35), (45, 20), (30, 5), (10, 10), (10, 30), (20, 35)]
#    innerCoordsList=list()
#    innerCoordsList.append([(30,20), (20,25), (20, 15), (30, 20)])
#    polyString=polyString+p.createMultiPolygonPartFromCoordsWithInner(outerCoords, innerCoordsList)
#    polyString=polyString[:-1]
#    polyString=polyString+")'"
#    print(polyString)
#    
#    coords=p.createOuterCoordsFromMultiPolygon(polyString)
#    print(coords)
    
#    p.removeUnnededPOIs()
    p.closeAllDB()


if __name__ == "__main__":
#    cProfile.run('main(sys.argv)')
    main(sys.argv)  
    

