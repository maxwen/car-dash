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
            print( "id: "+str(addressId) + " refId:"+str(refId) +" country: "+str(country)+" cityId: " + str(cityId) + " postCode: " + str(postCode) + " streetName: "+str(streetName) + " houseNumber:"+ str(houseNumber) + " lat:"+str(lat) + " lon:"+str(lon))
        
    def testRestrictionTable(self):
        self.cursorEdge.execute('SELECT * from restrictionTable')
        allentries=self.cursorEdge.fetchall()
        for x in allentries:
            restrictionId, target, viaPath, toCost, osmId=self.restrictionFromDB2(x)
            print("id: "+str(restrictionId)+" target:"+str(target)+" viaPath:"+str(viaPath)+" toCost:"+str(toCost) + " osmId:"+str(osmId))
                
    def testPOIRefTable(self):
        self.cursorNode.execute('SELECT refId, refType, tags, type, layer, AsText(geom) FROM poiRefTable WHERE refId=2171468')

#        self.cursorNode.execute('SELECT refId, refType, tags, type, layer, country, city, AsText(geom) FROM poiRefTable')
        allentries=self.cursorNode.fetchall()
        for x in allentries:
            print("%s %s %s"%(x[0], x[1], pickle.loads(x[2])))
#            refId, lat, lon, tags, nodeType, layer, country, city=self.poiRefFromDB2(x)
#            print("ref: " + str(refId) + "  lat: " + str(lat) + "  lon: " + str(lon) + " tags:"+str(tags) + " nodeType:"+str(nodeType) + " layer:"+str(layer) + " country:"+str(country)+" city:"+str(city))
        
    def testWayTable(self):
        self.cursorWay.execute('SELECT * FROM wayTable')
        while True:
            x=self.cursorWay.fetchone()
            if x==None:
                break
            print(x)
#            wayId, tags, refs, streetTypeId, name, nameRef, oneway, roundabout, maxspeed, poiList=self.wayFromDB(x)
#            print( "way: " + str(wayId) + " streetType:"+str(streetTypeId)+ " name:" +str(name) + " ref:"+str(nameRef)+" tags: " + str(tags) + "  refs: " + str(refs) + " oneway:"+str(oneway)+ " roundabout:"+str(roundabout) + " maxspeed:"+str(maxspeed)+" poilist:"+str(poiList))

    def testCrossingTable(self):
        self.cursorWay.execute('SELECT * FROM crossingTable')
        while True:
            x=self.cursorWay.fetchone()
            if x==None:
                break
            crossingEntryId, wayid, refId, wayIdList=self.crossingFromDB(x)
            print( "id: "+ str(crossingEntryId) + " wayid: " + str(wayid) +  " refId: "+ str(refId) + " wayIdList: " + str(wayIdList))
        
    def testEdgeTable(self):
        self.cursorEdge.execute('SELECT id, startRef, endRef, length, wayId, source, target, cost, reverseCost, streetInfo, AsText(geom) FROM edgeTable')
        while True:
            x=self.cursorEdge.fetchone()
            if x==None:
                break
            edgeId, startRef, endRef, length, wayId, source, target, cost, reverseCost, streetInfo, coords=self.edgeFromDBWithCoords(x)
            print( "edgeId: "+str(edgeId) +" startRef: " + str(startRef)+" endRef:"+str(endRef)+ " length:"+str(length)+ " wayId:"+str(wayId) +" source:"+str(source)+" target:"+str(target) + " cost:"+str(cost)+ " reverseCost:"+str(reverseCost)+ "streetInfo:" + str(streetInfo) + " coords:"+str(coords))

#        allentries=self.cursorEdge.fetchall()
#        for x in allentries:
#            edgeId, startRef, endRef, length, wayId, source, target, cost, reverseCost, streetInfo, coords=self.edgeFromDBWithCoords(x)
#            print( "edgeId: "+str(edgeId) +" startRef: " + str(startRef)+" endRef:"+str(endRef)+ " length:"+str(length)+ " wayId:"+str(wayId) +" source:"+str(source)+" target:"+str(target) + " cost:"+str(cost)+ " reverseCost:"+str(reverseCost)+ "streetInfo:" + str(streetInfo) + " coords:"+str(coords))
            
    def testAreaTable(self):
#        self.cursorArea.execute('SELECT osmId, areaId, type, tags, layer, AsText(geom) FROM areaTable WHERE type=%d'%(Constants.AREA_TYPE_NATURAL))
#        allentries=self.cursorArea.fetchall()
#        for x in allentries:
#            tags=self.decodeTags(x[3])
#            if "natural" in tags:
#                if tags["natural"]=="rock":
#                    print("%s %s"%(x[0],tags))

#            osmId, areaType, tags, layer, polyStr=self.areaFromDBWithCoordsString(x)
#            print(polyStr)
#            print("osmId: "+str(osmId)+ " type: "+str(areaType) +" tags: "+str(tags)+ " layer: "+ str(layer)+" polyStr:"+str(polyStr))

#        tolerance=self.osmutils.degToMeter(10.0)
#        print(tolerance)
#        self.cursorArea.execute('SELECT osmId, type, tags, layer, AsText(SimplifyPreserveTopology(geom, %f)) FROM areaTable WHERE osmId=136661'%(tolerance))
#        allentries=self.cursorArea.fetchall()
#        for x in allentries:
#            osmId, areaType, tags, layer, polyStr=self.areaFromDBWithCoordsString(x)
#            print(polyStr)

        self.cursorArea.execute('SELECT osmId, type, tags, layer, AsText(geom) FROM areaTable WHERE osmId=1848611')
        allentries=self.cursorArea.fetchall()
        for x in allentries:
            print(x)
#            tags=self.decodeTags(x[2])
#            if "name" in tags:
#                print("%d %s"%(int(x[0]), tags["name"]))

#        self.cursorArea.execute('SELECT osmId, type, tags, layer, AsText(geom) FROM areaLineTable WHERE type=10')
#        allentries=self.cursorArea.fetchall()
#        for x in allentries:
#            print(x)

    def testAdminAreaTable(self):
        self.cursorAdmin.execute('SELECT osmId, tags, adminLevel, parent, AsText(geom) FROM adminAreaTable WHERE adminLevel=2')
        allentries=self.cursorAdmin.fetchall()
        for x in allentries:
            osmId, tags, adminLevel, parent=self.adminAreaFromDBWithParent(x)
            print("%d %s"%(osmId, tags["name"]))
#            print("osmId: "+str(osmId)+ " tags: "+str(tags)+ " adminLevel: "+ str(adminLevel) + " parent:"+str(parent))

    def testAdminLineTable(self):
        self.cursorAdmin.execute('SELECT osmId, adminLevel, AsText(geom) FROM adminLineTable')
        allentries=self.cursorAdmin.fetchall()
        for x in allentries:
            print(x)
            osmId, adminLevel, polyString=self.adminLineFromDBWithCoordsString(x)


    def testCoordsTable(self):
#        self.cursorCoords.execute('SELECT * from coordsTable WHERE refId=98110819')
#        allentries=self.cursorCoords.fetchall()  
#        self.cursorCoords.execute('SELECT * from wayRefTable WHERE wayId=31664992')
#        allentries=self.cursorCoords.fetchall()  
#        print(allentries)
        None
                      
    def testEdgeTableGeom(self):
        self.cursorEdge.execute('SELECT AsText(geom) FROM edgeTable')
        allentries=self.cursorEdge.fetchall()
        for x in allentries:
            print(x)                 
    
    def createSimpleWayDBTables(self):
        self.cursorWaySimple.execute("SELECT InitSpatialMetaData()")
        self.cursorWaySimple.execute('CREATE TABLE wayTable (wayId INTEGER PRIMARY KEY, tags BLOB, refs BLOB, streetInfo INTEGER, name TEXT, ref TEXT, maxspeed INTEGER, poiList BLOB, streetTypeId INTEGER, layer INTEGER)')
        self.cursorWaySimple.execute("CREATE INDEX streetTypeId_idx ON wayTable (streetTypeId)")
        self.cursorWaySimple.execute("SELECT AddGeometryColumn('wayTable', 'geom', 4326, 'LINESTRING', 2)")

    def createSpatialIndexForSimpleWayTables(self):
        self.cursorWaySimple.execute('SELECT CreateSpatialIndex("wayTable", "geom")')

    def addToSimpleWayTable(self, wayId, tags, refs, streetInfo, name, nameRef, maxspeed, streetTypeId, layer, lineString):
        self.cursorWaySimple.execute("INSERT INTO wayTable VALUES( ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, LineFromText('%s', 4326))"%(lineString), (wayId, self.encodeTags(tags), pickle.dumps(refs), streetInfo, name, nameRef, maxspeed, None, streetTypeId, layer))

    def wayFromDBWithCoordsStringAll(self, x):
        wayId=int(x[0])
        tags=self.decodeTags(x[1])
        refs=pickle.loads(x[2])
        streetInfo=int(x[3])
        name=x[4]
        nameRef=x[5]
        maxspeed=int(x[6])
        streetTypeId=int(x[8])
        layer=int(x[9])
        coordsStr=x[10]            
        return (wayId, tags, refs, streetInfo, name, nameRef, maxspeed, streetTypeId, layer, coordsStr)   

    def fillSimpleWayDB(self):
        self.createSimpleWayDBTables()
        
        tolerance=self.osmutils.degToMeter(100.0)

        self.cursorWay.execute('SELECT wayId, tags, refs, streetInfo, name, ref, maxspeed, poiList, streetTypeId, layer, AsText(Simplify(geom, %f)) FROM wayTable'%(tolerance))
        allWays=self.cursorWay.fetchall()
        for x in allWays:
            (wayId, tags, refs, streetInfo, name, nameRef, maxspeed, streetTypeId, layer, coordsStr)=self.wayFromDBWithCoordsStringAll(x)
            self.addToSimpleWayTable(wayId, tags, refs, streetInfo, name, nameRef, maxspeed, streetTypeId, layer, coordsStr)
        
        self.createSpatialIndexForSimpleWayTables()
        self.closeSimpleWayDB()
        
def main(argv):    
    p = OSMDataTest()
      
    p.openAllDB()
    
    print(p.getLenOfEdgeTable())
    print(p.getLenOfWayTable())

#    p.fillSimpleWayDB()
#    p.cursorArea.execute("SELECT * FROM sqlite_master WHERE type='table'")
#    allentries=p.cursorArea.fetchall()
#    for x in allentries:
#        print(x)

#    p.cursorEdge.execute('SELECT * FROM geometry_columns')
#    allentries=p.cursorEdge.fetchall()
#    for x in allentries:
#        print(x)

#    si=p.encodeStreetInfo2(0, 1, 1, 1, 1)
#    print(p.decodeStreetInfo2(si))
#    si=p.encodeStreetInfo2(0, 1, 0, 1, 1)
#    print(p.decodeStreetInfo2(si))
#    si=p.encodeStreetInfo2(0, 0, 0, 1, 1)
#    print(p.decodeStreetInfo2(si))
#    si=p.encodeStreetInfo2(0, 0, 1, 0, 0)
#    print(p.decodeStreetInfo2(si))
#    si=p.encodeStreetInfo2(0, 2, 0, 0, 1)
#    print(p.decodeStreetInfo2(si))
#    si=p.encodeStreetInfo2(0, 2, 1, 1, 0)
#    print(p.decodeStreetInfo2(si))
   
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
#    p.testAreaTable()
       

#    print(p.getLenOfEdgeTable())
#    print(p.getEdgeEntryForEdgeId(6719))
#    print(p.getEdgeEntryForEdgeId(2024))

#    p.test()

#    p.testDBConistency()
#    p.testRestrictionTable()
#    p.recreateEdges()
#    p.recreateEdgeNodes()
#    p.createAllRefTableIndexesPost()

#    p.recreateCrossings()
#    p.recreateEdges()
    
#    p.testRoutes()
    p.testWayTable()
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
#    p.testAreaTable()
#    p.mergeWayEntries()

#    p.cursorArea.execute("CREATE INDEX areaType_idx ON areaTable (type)")
#    p.cursorArea.execute("CREATE INDEX adminLeel_idx ON areaTable (adminLevel)")        
#    p.cursorArea.execute("CREATE INDEX areaLineType_idx ON areaLineTable (type)")
#    p.vacuumAreaDB()
#    p.resolvePOIRefs()
#    p.resolveAdminAreas()
#    p.resolveAddresses(False)
#    p.testAdminAreaTable()
#    p.testAdminLineTable()

#    print(p.bu.getPolyCountryList())
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
    

