'''
Created on Dec 13, 2011

@author: maxl
'''
#from osmparser.parser.simple import OSMParser
from osmparser.parser.xml.parser import XMLParser
import sys
import os
import sqlite3
from osmparser.osmutils import OSMUtils
import pickle
import time
import zlib
#from osmparser.dijkstrapygraph import DijkstraWrapperPygraph
#from osmparser.dijkstraigraph import DijkstraWrapperIgraph

from config import Config
from osmparser.osmboarderutils import OSMBoarderUtils
from trsp.trspwrapper import TrspWrapper

class OSMRoute():
    def __init__(self, name="", routingPointList=None):
        self.name=name
        self.routingPointList=routingPointList
        self.edgeList=None
        self.pathCost=0.0
        self.length=0.0
        self.trackList=None
        
    def getName(self):
        return self.name
    
    def getRoutingPointList(self):
        return self.routingPointList
    
    def calcRoute(self, osmParserData):
        if self.edgeList==None:
            self.edgeList, self.pathCost=osmParserData.calcRouteForPoints(self)
    
    def calcRouteTest(self, osmParserData):
        osmParserData.calcRouteForPointsTest(self)
        
    def changeRouteFromPoint(self, currentPoint, osmParserData):        
        self.routingPointList[0]=currentPoint
        self.edgeList=None
        self.trackList=None
        
    def changeRouteFromPointList(self, routingPointList, osmParserData): 
        startPoint=self.routingPointList[0]
        if startPoint.getType()==0:
            del self.routingPointList[0]
            
        tmpList=list()
        tmpList.extend(self.routingPointList)
        for point in tmpList:
            if point.getType()==5:
                self.routingPointList.remove(point)

        i=0  
        for point in routingPointList:
            if point.getType()==5:
                self.routingPointList.insert(0+i, point)
                i=i+1
        self.edgeList=None
        self.trackList=None

    def getEdgeList(self):
        return self.edgeList
    
    def getPathCost(self):
        return self.pathCost
    
    def getLength(self):
        return self.length
    
    def getTrackList(self):
        return self.trackList
    
    def printRoute(self, osmParserData):
        if self.edgeList!=None:
            self.trackList, self.length=osmParserData.printRoute(self)
        
    def resolveRoutingPoints(self, osmParserData):
        for point in self.routingPointList:
            if point.getSource()==0:
                point.resolveFromPos(osmParserData)

    def routingPointValid(self):
        for point in self.routingPointList:
            if point.getSource()==0:
                return False
        return True

    def containsEdge(self, edgeId):
        if self.getEdgeList()!=None:
            return edgeId in self.getEdgeList()
        return False
    
    def saveToConfig(self, config, section, name):    
        routeString="%s:"%(self.name)
        for point in self.routingPointList:
            routeString=routeString+point.toString()+":"
        
        routeString=routeString[:-1]
        config.set(section, name, "%s"%(routeString))

    def readFromConfig(self, value):
        self.routingPointList=list()
        parts=value.split(":")
        self.name=parts[0]
        for i in range(1, len(parts)-1, 4):
            name=parts[i]
            pointType=parts[i+1]
            lat=parts[i+2]
            lon=parts[i+3]
            point=OSMRoutingPoint()
            point.readFromConfig("%s:%s:%s:%s"%(name, pointType, lat, lon))
            self.routingPointList.append(point)
    
    def __repr__(self):
        routeString="%s:"%(self.name)
        for point in self.routingPointList:
            routeString=routeString+point.toString()+":"
        
        routeString=routeString[:-1]
        return routeString

        return "%s:%d:%f:%f"%(self.name, self.type, self.lat, self.lon)

        
class OSMRoutingPoint():
    def __init__(self, name="", pointType=0, pos=(0.0, 0.0)):
        self.lat=pos[0]
        self.lon=pos[1]
        self.target=0
        self.source=0
        # 0 start
        # 1 end
        # 2 way
        # 3 gps
        # 4 favorite
        # 5 temporary
        self.type=pointType
        self.wayId=None
        self.edgeId=None
        self.name=name
        self.usedRefId=0
        self.country=None
        self.targetOneway=0
        
        self.refLat=0.0
        self.refLon=0.0
        self.startRefLat=0.0
        self.startRefLon=0.0
        self.endRefLat=0.0
        self.endRefLon=0.0
        self.startRef=0
        self.endRef=0
    
    def resolveFromPos(self, osmParserData):
        if self.source!=0:
            return
        
        edgeId, wayId, usedRefId, usedPos, country=osmParserData.getEdgeIdOnPos(self.lat, self.lon)
        if edgeId==None:
            print("resolveFromPos not found for %f %f"%(self.lat, self.lon))
            return

        (wayEntryId, tags, refs, streetTypeId, name, nameRef, oneway, roundabout)=osmParserData.getWayEntryForIdAndCountry2(wayId, country)

        (edgeId, startRef, endRef, _, wayId, source, target, _, _, self.startRefLat, self.startRefLon, self.endRefLat, self.endRefLon)=osmParserData.getEdgeEntryForEdgeIdWithCoords(edgeId)
        self.lat=usedPos[0]
        self.lon=usedPos[1]
        self.edgeId=edgeId
        self.target=target
        self.source=source
        if oneway==1 or roundabout==1:
            self.targetOneway=oneway
        self.usedRefId=usedRefId
        
        self.refLat, self.refLon=osmParserData.getCoordsWithRefAndCountry(self.usedRefId, country)

        self.wayId=wayId
        self.country=country
        self.startRef=startRef
        self.endRef=endRef
        
#        print("resolvFromPos: %d %d %d"%(edgeId, wayId, usedRefId))
    
    def getTargetOneway(self):
        return self.targetOneway
    
    def __repr__(self):
        return "%s:%d:%f:%f"%(self.name, self.type, self.lat, self.lon)
    
    def toString(self):
        return self.__repr__()
    
    def __lt__(self, other):
        return self.name < other.name
    
    def getName(self):
        return self.name
    
    def getType(self):
        return self.type
    
    def getPos(self):
        return (self.lat, self.lon)
    
    def getRefPos(self):
        return (self.refLat, self.refLon)
        
    def getStartRefPos(self):
        return (self.startRefLat, self.startRefLon)
    
    def getEndRefPos(self):
        return (self.endRefLat, self.endRefLon)
    
    def getEdgeId(self):
        return self.edgeId
    
    def getWayId(self):
        return self.wayId
    
    def getRefId(self):
        return self.usedRefId
    
    def getStartRef(self):
        return self.startRef
    
    def getEndRef(self):
        return self.endRef
    
    def getSource(self):
        return self.source
        
    def getTarget(self):
        return self.target
    
    def getCountry(self):
        return self.country
    
    def saveToConfig(self, config, section, name):        
        config.set(section, name, "%s"%(self.toString()))
        
    def readFromConfig(self, value):
        name, pointType, lat, lon=value.split(":")
        self.type=int(pointType)
        self.name=name
        self.lat=float(lat)
        self.lon=float(lon)
        
class OSMParserData():
    def __init__(self):
        self.connection=None
        self.cursor=None
        self.connectionEdge=None
        self.cursorEdge=None
        self.connectionAdress=None
        self.cursorAdress=None
        self.connectionCountry=None
        self.cursorCountry=None
        self.connectionCoords=None
        self.cursorCoords=None
        self.edgeId=1
        self.restrictionId=0
        self.trackItemList=list()
        self.nodeId=1
        self.addressId=0
        self.dWrapper=None
        self.dWrapperTrsp=None
        self.osmutils=OSMUtils()
        self.initBoarders()
        self.osmList=self.getOSMDataInfo()
        self.debugCountry=0
        self.wayCount=0
        self.wayRestricitionList=list()
#        self.refIdDB=0
        self.relations = dict()
        self.roundaboutExitNumber=None
        self.roundaboutEnterItem=None
        
    def initCountryData(self):
        self.crossingId=0
        self.relations = dict()
        self.firstWay=False

    def createCountryTables(self):
        self.createRefTable()
        self.createWayTable()
#        self.createAreaTable()
        self.createCrossingsTable()

    def createEdgeTables(self):
        self.createEdgeTable()
        self.createRestrictionTable()
    
    def createGlobalCountryTables(self):
        self.createRefCountryTable()
        self.createNodeWayCountryTable()

    def createAdressTable(self):
        self.createAddressTable()
        
    def openEdgeDB(self):
        self.connectionEdge=sqlite3.connect(self.getEdgeDBFile())
        self.cursorEdge=self.connectionEdge.cursor()
        self.connectionEdge.enable_load_extension(True)
        self.cursorEdge.execute("SELECT load_extension('libspatialite.so')")


    def openAdressDB(self):
        self.connectionAdress=sqlite3.connect(self.getAdressDBFile())
        self.cursorAdress=self.connectionAdress.cursor()

    def openGlobalCountryDB(self):
        self.connectionCountry=sqlite3.connect(self.getGlobalCountryDBFile())
        self.cursorCountry=self.connectionCountry.cursor()

    def openCoordsDB(self):
        self.connectionCoords=sqlite3.connect(self.getCoordsDBFile())
        self.cursorCoords=self.connectionCoords.cursor()
        self.createCoordsTable()

    def closeCountryDB(self, country):
        cursor=self.osmList[country]["cursor"]
        connection=self.osmList[country]["connection"]
        connection.commit()
        cursor.close()
        self.osmList[country]["cursor"]=None
        self.osmList[country]["connection"]=None

    def commitGlobalCountryDB(self):
        self.connectionCountry.commit()

    def commitAdressDB(self):
        self.connectionAdress.commit()
        
    def commitEdgeDB(self):
        self.connectionEdge.commit()

    def commitCoordsDB(self):
        self.connectionCoords.commit()
                
    def commitCountryDB(self, country):
        connection=self.osmList[country]["connection"]
        connection.commit()

    def closeEdgeDB(self):
        if self.connectionEdge!=None:
            self.connectionEdge.commit()        
            self.cursorEdge.close()
            self.connectionEdge=None     
            self.cursorEdge=None
       
    def closeAdressDB(self):
        if self.connectionAdress!=None:
            self.connectionAdress.commit()
            self.cursorAdress.close()
            self.connectionAdress=None
            self.cursorAdress=None
    
    def closeGlobalCountryDB(self):
        if self.connectionCountry!=None:
            self.connectionCountry.commit()
            self.cursorCountry.close()
            self.connectionCountry=None
            self.cursorCountry=None
                
    def closeCoordsDB(self):
        if self.connectionCoords!=None:
            self.connectionCoords.commit()
            self.cursorCoords.close()
            self.connectionCoords=None
            self.cursorCoords=None    
            self.deleteCoordsDBFile()        

    def openAllDB(self):
        self.openEdgeDB()
        self.openAdressDB()
        self.openGlobalCountryDB()
        for country in self.osmList.keys():
            self.openCountryDB(country)
        
    def closeAllDB(self):
        self.closeEdgeDB()
        self.closeAdressDB()
        self.closeGlobalCountryDB()
        for country in self.osmList.keys():
            self.closeCountryDB(country)
            
    def setDBCursorForCountry(self, country):
#        if country!=self.debugCountry:
#            print("switching cursor from %d to %d"%(self.debugCountry, country))
            
        self.connection=self.osmList[country]["connection"]
        self.cursor=self.osmList[country]["cursor"]
        self.debugCountry=country
      
    def getCountryForPolyCountry(self, polyCountry):
        for country, osmData in self.osmList.items():
            if osmData["polyCountry"]==polyCountry:
                return country
        return None
    
    def getCountryNameForId(self, country):
        return self.osmList[country]["country"]
    
    def getCountryIdForName(self, countryName):
        for country, osmData in self.osmList.items():
            if osmData["country"]==countryName:
                return country
        return -1
    
    def getCountryIdForAddrCountry(self, countryCode):
        for country, osmData in self.osmList.items():
            if osmData["countryCode"]==countryCode:
                return country
        return None

    def openCountryDB(self, country):
        self.connection=sqlite3.connect(self.getDBFile(country))
        self.connection.enable_load_extension(True)
        self.cursor=self.connection.cursor()
        self.cursor.execute("SELECT load_extension('libspatialite.so')")

        self.osmList[country]["cursor"]=self.cursor
        self.osmList[country]["connection"]=self.connection

    def createCoordsTable(self):
        self.cursorCoords.execute('CREATE TABLE coordsTable (refId INTEGER PRIMARY KEY, lat REAL, lon REAL)')

    def addToCoordsTable(self, ref, lat, lon):
        if ref==1530718191 or ref==1530718193:
            print("addToCoordsTable: %d"%ref)
        self.cursorCoords.execute('INSERT INTO coordsTable VALUES( ?, ?, ?)', (ref, lat, lon))
    
    def getCoordsEntry(self, ref):
        self.cursorCoords.execute('SELECT * FROM coordsTable WHERE refId=%d'%(ref))
        allentries=self.cursorCoords.fetchall()
        if ref==1530718191:
            print(allentries)
        if len(allentries)==1:
            return(allentries[0][0], allentries[0][1], allentries[0][2])
        return None, None, None
    
    def createRefTable(self):
        self.cursor.execute('CREATE TABLE refTable (refId INTEGER PRIMARY KEY, lat REAL, lon REAL, wayId BLOB, tags BLOB, type INTEGER)')
        self.cursor.execute("CREATE INDEX type_idx ON refTable (type)")

#    def createGeomForRefTable(self, country):
#        print("create geom column for refTable")
#        self.setDBCursorForCountry(country)
#
#        self.cursor.execute("SELECT InitSpatialMetaData()")
#        self.cursor.execute("SELECT AddGeometryColumn('refTable', 'geom', 4326, 'POINT', 2)")
#        
#        print("end create geom column for refTable")

    def createGeomForEdgeTable(self):
        print("create geom column for edgeTable")

        self.cursorEdge.execute("SELECT InitSpatialMetaData()")
        self.cursorEdge.execute("SELECT AddGeometryColumn('edgeTable', 'geom', 4326, 'LINESTRING', 2)")
                        
        print("end create geom column for edgeTable")

#    def createGeomDataForRefTable(self, country):
#        print("create geom column date for refTable")
#        self.setDBCursorForCountry(country)
#
#        self.cursor.execute("SELECT * from refTable")
#        allentries=self.cursor.fetchall()
#        for x in allentries:
#            (refId, lat, lon, _, _)=self.refFromDB(x)
#            self.cursor.execute("UPDATE refTable SET geom=MakePoint(%f, %f, 4326) WHERE refId=%d"%(lon, lat, refId))
#        
#        self.cursor.execute('SELECT CreateSpatialIndex("refTable", "geom")')
#        print("end create geom column date for refTable")

    def createGeomDataForEdgeTable(self):
        print("create geom column date for edgeTable")

        self.cursorEdge.execute("SELECT * from edgeTable")
        allentries=self.cursorEdge.fetchall()
        for x in allentries:
            (edgeId, startRef, endRef, length, wayId, source, target, cost, reverseCost, lat1, lon1, lat2, lon2)=self.edgeFromDBWithCoords(x)
            self.cursorEdge.execute("UPDATE edgeTable SET geom=MakeLine(MakePoint(%f, %f, 4326), MakePoint(%f, %f, 4326)) WHERE id=%d"%(lon1, lat1, lon2, lat2, edgeId))
        
        self.cursorEdge.execute('SELECT CreateSpatialIndex("edgeTable", "geom")')
        print("end create geom column date for edgeTable")
       
    def createRefTableIndexesPost(self, country):
        print("create refTable index for lat and lon")
        self.setDBCursorForCountry(country)
        self.cursor.execute("CREATE INDEX refTableLat_idx ON refTable (lat)")
        self.cursor.execute("CREATE INDEX refTableLon_idx ON refTable (lon)")
        print("end create refTable index for lat and lon")

    def createWayTable(self):
        self.cursor.execute('CREATE TABLE wayTable (wayId INTEGER PRIMARY KEY, tags BLOB, refs BLOB, streetInfo INTEGER, name TEXT, ref TEXT, maxspeed INTEGER)')

#    def createAreaTable(self):
#        self.cursor.execute('CREATE TABLE areaTable (wayId INTEGER PRIMARY KEY, tags BLOB, refs BLOB')

    def createAddressTable(self):
        self.cursorAdress.execute('CREATE TABLE addressTable (id INTEGER PRIMARY KEY, refId INTEGER, country INTEGER, city TEXT, postCode INTEGER, streetName TEXT, houseNumber TEXT, lat REAL, lon REAL)')
        self.createAddressTableIndex()
        
    def createAddressTableIndex(self):
        self.cursorAdress.execute("CREATE INDEX streetName_idx ON addressTable (streetName)")
        self.cursorAdress.execute("CREATE INDEX country_idx ON addressTable (country)")
        self.cursorAdress.execute("CREATE INDEX city_idx ON addressTable (city)")
        
    def addToAddressTable(self, refId, country, city, postCode, streetName, houseNumber, lat, lon):
        self.cursorAdress.execute('INSERT INTO addressTable VALUES( ?, ?, ?, ?, ?, ?, ?, ?, ?)', (self.addressId, refId, country, city, postCode, streetName, houseNumber, lat, lon))
        self.addressId=self.addressId+1
    
    def replaceInAddressTable(self, addressId, refId, country, city, postCode, streetName, houseNumber, lat, lon):
        self.cursorAdress.execute('REPLACE INTO addressTable VALUES( ?, ?, ?, ?, ?, ?, ?, ?, ?)', (addressId, refId, country, city, postCode, streetName, houseNumber, lat, lon))

    def testAddressTable(self):
        self.cursorAdress.execute('SELECT * FROM addressTable')
        allentries=self.cursorAdress.fetchall()
        for x in allentries:
            addressId, refId, country, city, postCode, streetName, houseNumber, lat, lon=self.addressFromDB(x)
            print( "id: "+str(addressId) + " refId:"+str(refId) +" country: "+str(country)+" city: " + str(city) + " postCode: " + str(postCode) + " streetName: "+str(streetName) + " houseNumber:"+ str(houseNumber) + " lat:"+str(lat) + " lon:"+str(lon))

    def addressFromDB(self, x):
        addressId=x[0]
        refId=x[1]
        country=x[2]
        city=x[3]
        postCode=x[4]
        streetName=x[5]
        houseNumber=x[6]
        lat=x[7]
        lon=x[8]
        return (addressId, refId, country, city, postCode, streetName, houseNumber, lat, lon)
    
    def getLenOfAddressTable(self):
        self.cursorAdress.execute('SELECT COUNT(*) FROM addressTable')
        allentries=self.cursorAdress.fetchall()
        return allentries[0][0]
    
    def createCrossingsTable(self):
        self.cursor.execute('CREATE TABLE crossingTable (id INTEGER PRIMARY KEY, wayId INTEGER, refId INTEGER, nextWayIdList BLOB)')
        self.cursor.execute("CREATE INDEX wayId_idx ON crossingTable (wayId)")
        self.cursor.execute("CREATE INDEX refId_idx ON crossingTable (refId)")

    def createEdgeTable(self):
        self.cursorEdge.execute('CREATE TABLE edgeTable (id INTEGER PRIMARY KEY, startRef INTEGER, endRef INTEGER, length INTEGER, wayId INTEGER, source INTEGER, target INTEGER, cost REAL, reverseCost REAL, lat1 REAL, lon1 REAL, lat2 REAL, lon2 REAL)')
        self.cursorEdge.execute("CREATE INDEX startRef_idx ON edgeTable (startRef)")
        self.cursorEdge.execute("CREATE INDEX endRef_idx ON edgeTable (endRef)")
        self.cursorEdge.execute("CREATE INDEX wayId_idx ON edgeTable (wayId)")
        
    def createEdgeTableIndexesPost(self):
        print("create edgeTable index for source and target")
        self.cursorEdge.execute("CREATE INDEX source_idx ON edgeTable (source)")
        self.cursorEdge.execute("CREATE INDEX target_idx ON edgeTable (target)")
        print("end create edgeTable index for source and target")

    def createRestrictionTable(self):
        self.cursorEdge.execute('CREATE TABLE restrictionTable (id INTEGER PRIMARY KEY, target INTEGER, viaPath TEXT, toCost REAL)')
        
    def addToRestrictionTable(self, target, viaPath, toCost):
        self.cursorEdge.execute('INSERT INTO restrictionTable VALUES( ?, ?, ?, ?)', (self.restrictionId, target, viaPath, toCost))
        self.restrictionId=self.restrictionId+1

    def restrictionFromDB(self, x):
        restrictionId=x[0]
        target=x[1]
        viaPath=x[2]
        toCost=x[3]
        return (restrictionId, target, viaPath, toCost)
    
    def testRestrictionTable(self):
        self.cursorEdge.execute('SELECT * from restrictionTable ORDER by target')
        allentries=self.cursorEdge.fetchall()
        for x in allentries:
            restrictionId, target, viaPath, toCost=self.restrictionFromDB(x)
            print("id: "+str(restrictionId)+" target:"+str(target)+" viaPath:"+str(viaPath)+" toCost:"+str(toCost))

    def createRefCountryTable(self):
        self.cursorCountry.execute('CREATE TABLE refCountryTable (id INTEGER PRIMARY KEY, country INTEGER)')
    
    def getCountryOfPos(self, lat, lon):
        polyCountry=self.countryNameOfPoint(lat, lon)
        return self.getCountryForPolyCountry(polyCountry)
                   
    def getCountryOfPosDeep(self, lat, lon):
        polyCountry=self.countryNameOfPointDeep(lat, lon)
        return self.getCountryForPolyCountry(polyCountry)

    def addToCountryRefTableWithCountry(self, refId, lat, lon, refCountry):            
        self.cursorCountry.execute('INSERT OR IGNORE INTO refCountryTable VALUES( ?, ?)', (refId, refCountry))
 
    def getCountryOfRef(self, refId):
        self.cursorCountry.execute('SELECT id, country FROM refCountryTable where id=%d'%(refId))
        allentries=self.cursorCountry.fetchall()
        if len(allentries)==1:
            return (allentries[0][0], allentries[0][1])
        return (None, None)

    def testCountryRefTable(self):
        self.cursorCountry.execute('SELECT * FROM refCountryTable')
        allentries=self.cursorCountry.fetchall()
        for x in allentries:
            print( "refId: "+str(x[0]) +" country: " + x[1])

    def createNodeWayCountryTable(self):
        self.cursorCountry.execute('CREATE TABLE wayCountryTable (id INTEGER PRIMARY KEY, wayId INTEGER, country INTEGER)')
        self.cursorCountry.execute("CREATE INDEX wayId_idx ON wayCountryTable (wayId)")

    def addToCountryWayTable(self, wayId, country):
        if country==None:
            print("addToCountryTable %d with country==NONE"%(wayId))
            return
        
        resultList=self.getCountrysOfWay(wayId)
        if len(resultList)!=0:
            for result in resultList:
                _, _, storedCountry=result
                if country==storedCountry:
                    return
        
        self.cursorCountry.execute('INSERT INTO wayCountryTable VALUES( ?, ?, ?)', (self.wayCount, wayId, country))
        self.wayCount=self.wayCount+1
        
    def getCountrysOfWay(self, wayId):
        self.cursorCountry.execute('SELECT id, wayId, country FROM wayCountryTable where wayId=%d'%(wayId))
        allentries=self.cursorCountry.fetchall()
        resultList=list()
        for x in allentries:
            resultList.append((x[0], x[1], x[2]))
        return resultList
    
    def isWayInCountry(self, wayId, country):
        resultList=self.getCountrysOfWay(wayId)
        if len(resultList)==0:
            return False
        
        for result in resultList:
            _, _, storedCountry=result
            if storedCountry==country:
                return True

        return False
    
    def testCountryWayTable(self):
        self.cursorCountry.execute('SELECT * FROM wayCountryTable')
        allentries=self.cursorCountry.fetchall()
        for x in allentries:
            print( "id: "+x[0]+ "wayId: "+str(x[1]) +" country: " + x[2])

    def getLenOfCountryWayTable(self):
        self.cursorCountry.execute('SELECT COUNT(*) FROM wayCountryTable')
        allentries=self.cursorCountry.fetchall()
        return allentries[0][0]

    def addToRefTable(self, refid, lat, lon, wayId, country, tags, nodeType):
        self.setDBCursorForCountry(country)
        resultList=self.getRefEntryForIdAndCountry2(refid, country)
        if len(resultList)==1:
            refid, lat, lon, wayIdList, storedTags, storedNodeType=resultList[0]
            # dont override an already "defined" node type
            if storedNodeType!=0 and nodeType==0:
                nodeType=storedNodeType
                
            if wayId!=None:
                if wayIdList==None:
                    wayIdList=list()
                wayIdList.append(wayId)
                tagStr=None
                if storedTags!=None:
                    tagStr=pickle.dumps(storedTags)
                self.cursor.execute('REPLACE INTO refTable VALUES( ?, ?, ?, ?, ?, ?)', (refid, lat, lon, pickle.dumps(wayIdList), tagStr, nodeType))
            elif tags!=None:
                wayIdStr=None
                if wayIdList!=None:
                    wayIdStr=pickle.dumps(wayIdList)
                self.cursor.execute('REPLACE INTO refTable VALUES( ?, ?, ?, ?, ?, ?)', (refid, lat, lon, wayIdStr, pickle.dumps(tags), nodeType))
            return
            
        if wayId!=None:
            wayIdList=list()
            wayIdList.append(wayId)
            self.cursor.execute('INSERT INTO refTable VALUES( ?, ?, ?, ?, ?, ?)', (refid, lat, lon, pickle.dumps(wayIdList), None, nodeType))
        elif tags!=None:
            self.cursor.execute('INSERT INTO refTable VALUES( ?, ?, ?, ?, ?, ?)', (refid, lat, lon, None, pickle.dumps(tags), nodeType))
        
    def updateRefTableEntry(self, refId, tags, nodeType, country):
        self.setDBCursorForCountry(country)
        resultList=self.getRefEntryForIdAndCountry(refId, country)
        if len(resultList)==1:
            refid, lat, lon, wayIdList, storedTags=resultList[0]
            if storedTags!=None:
                print("updateRefTableEntry: ref %d already has stored tags %s"%(refId, storedTags))
            
            self.cursor.execute('REPLACE INTO refTable VALUES( ?, ?, ?, ?, ?, ?)', (refid, lat, lon, pickle.dumps(wayIdList), pickle.dumps(tags), nodeType))

    def addToWayTable(self, wayid, tags, refs, streetTypeId, name, nameRef, oneway, roundabout, maxspeed, country):
        self.setDBCursorForCountry(country)
        streetInfo=self.encodeStreetInfo(streetTypeId, oneway, roundabout)
        self.cursor.execute('INSERT OR IGNORE INTO wayTable VALUES( ?, ?, ?, ?, ?, ?, ?)', (wayid, self.encodeWayTags(tags), pickle.dumps(refs), streetInfo, name, nameRef, maxspeed))
     
    def addToAreaTable(self, wayId, tags, refs, country):
        self.setDBCursorForCountry(country)
        self.cursor.execute('INSERT OR IGNORE INTO areaTable VALUES( ?, ?, ?)', (wayId, self.encodeWayTags(tags), pickle.dumps(refs)))

    def addToCrossingsTable(self, wayid, refId, nextWaysList):
        self.setDBCursorForCountry(self.country)
        self.cursor.execute('INSERT INTO crossingTable VALUES( ?, ?, ?, ?)', (self.crossingId, wayid, refId, pickle.dumps(nextWaysList)))
        self.crossingId=self.crossingId+1

    def addToEdgeTable(self, startRef, endRef, length, wayId, cost, reverseCost, lat1, lon1, lat2, lon2):
        resultList=self.getEdgeEntryForStartAndEndPointAndWayId(startRef, endRef, wayId)
        if len(resultList)==0:
            self.cursorEdge.execute('INSERT INTO edgeTable VALUES( ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (self.edgeId, startRef, endRef, length, wayId, 0, 0, cost, reverseCost, lat1, lon1, lat2, lon2))
            self.edgeId=self.edgeId+1
#        else:
#            print("addToEdgeTable: edge for wayId %d with startRef %d and endRef %d already exists in DB"%(wayId, startRef, endRef))
            
    def clearEdgeTable(self):
        self.cursorEdge.execute('DROP TABLE edgeTable')
        self.edgeId=1
        self.createEdgeTable()
    
    def clearCrosssingsTable(self, country):
        self.setDBCursorForCountry(country)
        self.cursor.execute('DROP table crossingTable')
        self.crossingId=0
        self.createCrossingsTable()
                
    def getLenOfEdgeTable(self):
        self.cursorEdge.execute('SELECT COUNT(id) FROM edgeTable')
        allentries=self.cursorEdge.fetchall()
        return allentries[0][0]
    
    def getLenOfEdgeTableForRouting(self, bbox):
        ymin=bbox[1]-0.1
        xmin=bbox[0]-0.1
        ymax=bbox[3]+0.1
        xmax=bbox[2]+0.1
        
        self.cursorEdge.execute('SELECT COUNT(id) FROM edgeTable WHERE MbrWithin("geom", BuildMbr(%f, %f, %f, %f, 4326))==1'%(xmin, ymin, xmax, ymax))
        allentries=self.cursorEdge.fetchall()
        return allentries[0][0]

    def updateSourceOfEdge(self, edgeId, sourceId):
        existingEdgeId, _, _, _, _, _, _, _, _=self.getEdgeEntryForEdgeId(edgeId)
        if existingEdgeId==None:
            print("no edge with id %d"%(edgeId))
            return
        self.cursorEdge.execute('UPDATE edgeTable SET source=%d WHERE id=%d'%(sourceId, edgeId))

    def updateTargetOfEdge(self, edgeId, targetId):
        existingEdgeId, _, _, _, _, _, _, _, _=self.getEdgeEntryForEdgeId(edgeId)
        if existingEdgeId==None:
            print("no edge with id %d"%(edgeId))
            return
        self.cursorEdge.execute('UPDATE edgeTable SET target=%d WHERE id=%d'%(targetId, edgeId))
        
    def updateCostsOfEdge(self, edgeId, cost, reverseCost):
        existingEdgeId, _, _, _, _, _, _, _, _=self.getEdgeEntryForEdgeId(edgeId)
        if existingEdgeId==None:
            print("no edge with id %d"%(edgeId))
            return
        self.cursorEdge.execute('UPDATE edgeTable SET cost=%d, reverseCost=%d WHERE id=%d'%(cost, reverseCost, edgeId))

    def clearSourceAndTargetOfEdges(self):
        self.cursorEdge.execute('SELECT id FROM edgeTable')
        allentries=self.cursorEdge.fetchall()
        for x in allentries:
            edgeId=x[0]
            self.updateSourceOfEdge(edgeId, 0)
            self.updateTargetOfEdge(edgeId, 0)

    def getEdgeEntryForSource(self, sourceId):
        self.cursorEdge.execute('SELECT * FROM edgeTable where source=%d'%(sourceId))
        resultList=list()
        allentries=self.cursorEdge.fetchall()
        for result in allentries:
            edge=self.edgeFromDB(result)
            resultList.append(edge)
        return resultList      
    
    def getEdgeEntryForTarget(self, targetId):
        self.cursorEdge.execute('SELECT * FROM edgeTable where target=%d'%(targetId))
        resultList=list()
        allentries=self.cursorEdge.fetchall()
        for result in allentries:
            edge=self.edgeFromDB(result)
            resultList.append(edge)
        return resultList      
    
    def getEdgeEntryForSourceAndTarget(self, sourceId, targetId):
        self.cursorEdge.execute('SELECT * FROM edgeTable where source=%d AND target=%d'%(sourceId, targetId))
        resultList=list()
        allentries=self.cursorEdge.fetchall()
        for result in allentries:
            edge=self.edgeFromDB(result)
            resultList.append(edge)
        return resultList   
    
    def getEdgeEntryForEdgeId(self, edgeId):
        self.cursorEdge.execute('SELECT * FROM edgeTable where id=%d'%(edgeId))
        allentries=self.cursorEdge.fetchall()
        if len(allentries)==1:
            edge=self.edgeFromDB(allentries[0])
            return edge
        print("no edge with %d"%(edgeId))
        return (None, None, None, None, None, None, None, None, None)

    def getEdgeEntryForEdgeIdWithCoords(self, edgeId):
        self.cursorEdge.execute('SELECT * FROM edgeTable where id=%d'%(edgeId))
        allentries=self.cursorEdge.fetchall()
        if len(allentries)==1:
            edge=self.edgeFromDBWithCoords(allentries[0])
            return edge
        print("no edge with %d"%(edgeId))
        return (None, None, None, None, None, None, None, None, None, None, None, None, None)
        
    
    def getEdgeEntryForStartPoint(self, startRef, edgeId):
        self.cursorEdge.execute('SELECT * FROM edgeTable where startRef=%d AND id!=%d'%(startRef, edgeId))
        resultList=list()
        allentries=self.cursorEdge.fetchall()
        for result in allentries:
            edge=self.edgeFromDB(result)
            resultList.append(edge)
        return resultList
 
    def getEdgeEntryForEndPoint(self, endRef, edgeId):
        self.cursorEdge.execute('SELECT * FROM edgeTable where endRef=%d AND id!=%d'%(endRef, edgeId))
        resultList=list()
        allentries=self.cursorEdge.fetchall()
        for result in allentries:
            edge=self.edgeFromDB(result)
            resultList.append(edge)
        return resultList
    
    def getEdgeEntryForStartAndEndPointAndWayId(self, startRef, endRef, wayId):
        self.cursorEdge.execute('SELECT * FROM edgeTable where startRef=%d AND endRef=%d AND wayId=%d'%(startRef, endRef, wayId))
        resultList=list()
        allentries=self.cursorEdge.fetchall()
        for result in allentries:
            edge=self.edgeFromDB(result)
            resultList.append(edge)
        return resultList
    
    def getEdgeEntryForStartOrEndPoint(self, ref):
        self.cursorEdge.execute('SELECT * FROM edgeTable where startRef=%d OR endRef=%d'%(ref, ref))
        resultList=list()
        allentries=self.cursorEdge.fetchall()
        for result in allentries:
            edge=self.edgeFromDB(result)
            resultList.append(edge)
        return resultList
        
    def getEdgeEntryForWayId(self, wayId):
        self.cursorEdge.execute('SELECT * FROM edgeTable where wayId=%d'%(wayId))
        resultList=list()
        allentries=self.cursorEdge.fetchall()
        for result in allentries:
            edge=self.edgeFromDB(result)
            resultList.append(edge)
        return resultList
    
    def getRefEntryForIdAndCountry(self, refId, country):
        self.setDBCursorForCountry(country)
        self.cursor.execute('SELECT * FROM refTable where refId=%d'%(refId))
        resultList=list()
        allentries=self.cursor.fetchall()
        for result in allentries:
            refEntry=self.refFromDB(result)
            resultList.append(refEntry)
        return resultList
    
    def getRefEntryForIdAndCountry2(self, refId, country):
        self.setDBCursorForCountry(country)
        self.cursor.execute('SELECT * FROM refTable where refId=%d'%(refId))
        resultList=list()
        allentries=self.cursor.fetchall()
        for result in allentries:
            refEntry=self.refFromDB2(result)
            resultList.append(refEntry)
        return resultList
    
    def getWayEntryForIdAndCountry(self, wayId, country):
        self.setDBCursorForCountry(country)
        self.cursor.execute('SELECT * FROM wayTable where wayId=%d'%(wayId))
        allentries=self.cursor.fetchall()
        if len(allentries)==1:
            return self.wayFromDB(allentries[0])
        
        return (None, None, None, None, None, None)

    def getWayEntryForIdAndCountry2(self, wayId, country):
        self.setDBCursorForCountry(country)
        self.cursor.execute('SELECT * FROM wayTable where wayId=%d'%(wayId))
        allentries=self.cursor.fetchall()
        if len(allentries)==1:
            return self.wayFromDB2(allentries[0])
        
        return (None, None, None, None, None, None, None, None)
    
    def getWayEntryForIdAndCountry3(self, wayId, country):
        self.setDBCursorForCountry(country)
        self.cursor.execute('SELECT * FROM wayTable where wayId=%d'%(wayId))
        allentries=self.cursor.fetchall()
        if len(allentries)==1:
            return self.wayFromDB3(allentries[0])
        
        return (None, None, None, None, None, None, None, None, None)

    def getWayEntryForStreetNameAndCountry(self, streetName, country):
        self.setDBCursorForCountry(country)
        self.cursor.execute('SELECT * FROM wayTable where name=="%s"'%(streetName))
        allentries=self.cursor.fetchall()
        resultList=list()
        nameSet=set()
        for x in allentries:
            (wayId, tags, refs, streetTypeId, name, nameRef)=self.wayFromDB(x)
            if streetTypeId in self.getStreetTypeIdForAddresses():
                if not name in nameSet:
                    resultList.append((name, refs[0]))
                    nameSet.add(name)
        return resultList
    
    def getAllWayEntryForCountry(self, country):
        self.setDBCursorForCountry(country)
        self.cursor.execute('SELECT * FROM wayTable')
        allentries=self.cursor.fetchall()
        resultList=list()
        nameSet=set()
        for x in allentries:
            (wayId, tags, refs, streetTypeId, name, nameRef)=self.wayFromDB(x)
            if streetTypeId in self.getStreetTypeIdForAddresses():
                if not name in nameSet:
                    resultList.append((name, refs[0]))
                    nameSet.add(name)

        return resultList
    
    def getCrossingEntryFor(self, wayid, country):
        self.setDBCursorForCountry(country)
        self.cursor.execute('SELECT * FROM crossingTable where wayId=%d'%(wayid))      
        resultList=list()
        allentries=self.cursor.fetchall()
        for result in allentries:
            crossing=self.crossingFromDB(result)
            resultList.append(crossing)
            
        return resultList
    
    def getCrossingEntryForRefId(self, wayid, refId, country):
        self.setDBCursorForCountry(country)
        self.cursor.execute('SELECT * FROM crossingTable where wayId=%d AND refId=%d'%(wayid, refId))  
        resultList=list()
        allentries=self.cursor.fetchall()
        for result in allentries:
            crossing=self.crossingFromDB(result)
            resultList.append(crossing)
            
        return resultList
    
    def testRefTable(self, country):
        self.setDBCursorForCountry(country)
        self.cursor.execute('SELECT * FROM refTable')
        allentries=self.cursor.fetchall()
        for x in allentries:
            refId, lat, lon, wayIdList, tags=self.refFromDB(x)
            print("ref: " + str(refId) + "  lat: " + str(lat) + "  lon: " + str(lon) + " wayIdList:"+str(wayIdList) + " tags:"+str(tags))
        
    def createTemporaryPoint(self, lat, lon, lat1, lon1, offset=0.0):
        distance=int(self.osmutils.distance(lat, lon, lat1, lon1))
        # create nodes with distance 5m
        frac=5
        if offset!=0.0:
            pointsToIgnore=int(offset/frac)
        else:
            pointsToIgnore=None
        pointsToCreate=int(distance/frac)

        points=list()
        if offset==0.0:
            points.append((lat, lon))
        if distance>frac:
            doneDistance=0
            i=0
            while doneDistance<distance:
                newLat, newLon=self.osmutils.linepart(lat, lon, lat1, lon1, doneDistance/distance)
                if pointsToIgnore!=None:
                    if i>pointsToIgnore and i<pointsToCreate-pointsToIgnore:
                        points.append((newLat, newLon))
                else:
                    points.append((newLat, newLon))
                    
                doneDistance=doneDistance+frac
                i=i+1
        if offset==0.0:
            points.append((lat1, lon1))

#        print("%d %s %d"%(pointsToCreate, str(pointsToIgnore), len(points)))
        return points
          
    def checkForPosOnEdgeId(self, lat, lon, edgeId, maxDistance=10.0, offset=0.0):
        edgeId, startRef, endRef, _, wayId, _, _, _, _=self.getEdgeEntryForEdgeId(edgeId)
        refList=self.getRefListOfEdge(edgeId, wayId, startRef, endRef)
#        print(refList)
        usedEdgeId=None
        usedRefId=None
        usedWayId=None
        usedLat=None
        usedLon=None                            
        usedCountry=None
        
        if len(refList)!=0:
            mindistance=maxDistance
            lastRef=refList[0]
            for ref in refList[1:]: 
                _, refCountry=self.getCountryOfRef(ref)
                onLine, (tmpLat, tmpLon)=self.isOnLineBetweenPoints(lat, lon, ref, lastRef, maxDistance, offset)
                if onLine==True:
                    distance=self.osmutils.distance(lat, lon, tmpLat, tmpLon)
                    if distance<mindistance:
                        mindistance=distance
                        usedEdgeId=edgeId
                        usedRefId=ref
                        usedWayId=wayId
                        usedLat=tmpLat
                        usedLon=tmpLon                            
                        usedCountry=refCountry
#                    print("using edge %d"%(edgeId))

                lastRef=ref  
        return usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry

    def checkForHeadingOnEdgeId(self, edgeId, ref):
        edgeId, startRef, endRef, length, wayId, source, target, cost, reverseCost=self.getEdgeEntryForEdgeId(edgeId)
        refList=self.getRefListOfEdge(edgeId, wayId, startRef, endRef)
        if len(refList)!=0:
            if ref==endRef:
                refList.reverse()
            ref1=refList[0]
            ref2=refList[1]
            heading=self.getHeadingBetweenPoints(ref1, ref2)
            return heading
        return None
    
    def getHeadingBetweenPoints(self, ref1, ref2):
        _, country=self.getCountryOfRef(ref1)
        if country==None:
            return None
        resultList=self.getRefEntryForIdAndCountry(ref1, country)
        if len(resultList)==1:
            _, lat1, lon1, _, _=resultList[0]
        else:
            return None
        _, country=self.getCountryOfRef(ref2)
        if country==None:
            return None
        resultList=self.getRefEntryForIdAndCountry(ref2, country)
        if len(resultList)==1:
            _, lat2, lon2, _, _=resultList[0]
        else:
            return None

        heading=self.osmutils.headingDegrees(lat1, lon1, lat2, lon2)
        return heading
    
    def getEdgeIdOnPosForRouting(self, lat, lon, track, currentEdgeOnRoute, nextEdgeOnRoute):        
        usedEdgeId=None
        usedWayId=None
        usedRefId=None
        usedLat=None
        usedLon=None
        usedCountry=None
        
        # first check current edge
        if currentEdgeOnRoute!=None:
            usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry=self.checkForPosOnEdgeId(lat, lon, currentEdgeOnRoute, maxDistance=5.0, offset=20.0)
            if usedEdgeId!=None:
#                print("use same edge")
                return usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry
#                     
#        # then check next edge on route
#        if nextEdgeOnRoute!=None:
#            usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry=self.checkForPosOnEdgeId(lat, lon, nextEdgeOnRoute, 5.0)
#            if usedEdgeId!=None:
#                return usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry

        # try edges starting or ending with this edge
        # use track information
        if currentEdgeOnRoute!=None:
            possibleEdges=list()
            edgeHeadings=list()
            doneEdges=list()
            currentEdgeOnRoute, startRef, endRef, _, _, _, _, _, _=self.getEdgeEntryForEdgeId(currentEdgeOnRoute)
            resultList=self.getEdgeEntryForStartOrEndPoint(startRef)
            if len(resultList)!=0:
                for result in resultList:
                    nextEdgeId, _, _, _, _, _, _, _, _=result
                    if nextEdgeId in doneEdges:
                        continue
                    if track!=None:
                        heading=self.checkForHeadingOnEdgeId(nextEdgeId, startRef)
                    usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry=self.checkForPosOnEdgeId(lat, lon, nextEdgeId)
                    if usedEdgeId!=None:
                        if track!=None:
                            edgeHeadings.append(heading)
                        possibleEdges.append((usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry))
                        doneEdges.append(usedEdgeId)
            resultList=self.getEdgeEntryForStartOrEndPoint(endRef)
            if len(resultList)!=0:
                for result in resultList:
                    nextEdgeId, _, _, _, _, _, _, _, _=result
                    if nextEdgeId in doneEdges:
                        continue
                    
                    if track!=None:
                        heading=self.checkForHeadingOnEdgeId(nextEdgeId, startRef)

                    usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry=self.checkForPosOnEdgeId(lat, lon, nextEdgeId)
                    if usedEdgeId!=None:
                        if track!=None and heading!=None:
                            edgeHeadings.append(heading)
                        possibleEdges.append((usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry))
                        doneEdges.append(usedEdgeId)

            if len(possibleEdges)!=0:
#                print(possibleEdges)
                if len(possibleEdges)==1:
                    return possibleEdges[0]
                
                maxDistance=10.0
                shortestEntry=None
                if track!=None:
                    i=0
                    for heading in edgeHeadings:
                        if heading!=None:
                            if heading+360 > track+360-10 and heading+360 < track+360+10:
                                print("using edge with heading %d %d"%(track, heading))
                                return possibleEdges[i]
                        i=i+1
                i=0
                for possibleEdge in possibleEdges:
                    usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry=possibleEdge
                    distance=self.osmutils.distance(lat, lon, usedLat, usedLon)
                    if distance<maxDistance:
#                        print(distance)
                        maxDistance=distance
                        shortestEntry=i
                    i=i+1
                if shortestEntry!=None:
                    return possibleEdges[shortestEntry]
            
        # TODO: maybe also try edges of the same wayid

        return self.getEdgeIdOnPos(lat, lon)

    def getEdgeIdOnPos(self, lat, lon):
#        start=time.time()
        usedEdgeId=None
        usedWayId=None
        usedRefId=None
        usedLat=None
        usedLon=None
        usedCountry=None
        usedRefs=None
        usedCheckRefs=None
        maxDistance=1000.0
 
        refCountry=self.getCountryOfPos(lat, lon)
        if refCountry==None:
            return usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry

        nearestFound=False
        nodes=self.getNearNodes(lat, lon, refCountry, maxDistance)
        for refId, lat1, lon1, wayIdList in nodes:
            # first search way which has the nearest ref
            if nearestFound==True:
                break
            for wayId in wayIdList:
                if nearestFound==True:
                    break
                (wayEntryId, tags, refs, streetTypeId, name, nameRef)=self.getWayEntryForIdAndCountry(wayId, refCountry)

                # use the refs before and after to check
                index=refs.index(refId)
                refList=list()
                if index==0:
                    refList.append(refId)
                    refList.append(refs[index+1])
                elif index==len(refs)-1:
                    refList.append(refs[-1])
                    refList.append(refId)
                else:
                    refList.append(refs[index-1])
                    refList.append(refId)
                    refList.append(refs[index+1])
                                    
                lastRef=refList[0]
                for ref in refList[1:]:
                    onLine, (tmpLat, tmpLon)=self.isOnLineBetweenPoints(lat, lon, ref, lastRef, 10.0)
                    if onLine==True:
                        usedRefId=ref
                        usedLat=tmpLat
                        usedLon=tmpLon
                        usedCountry=refCountry
                        usedRefs=refs
                        usedCheckRefs=refList
                        usedWayId=wayId
                        nearestFound=True
                        break
                    lastRef=ref
                        
        if usedWayId!=None:
            usedEdgeId=None
            # search all edges of this way for the nearset ref
            resultList=self.getEdgeEntryForWayId(usedWayId)
            if len(resultList)==1:
                edgeId, startRef, endRef, length, wayId, source, target, cost, reverseCost=resultList[0]
                usedEdgeId=edgeId
            else:
                edgeFound=False
                for edge in resultList:
                    if edgeFound==True:
                        break
                    edgeId, startRef, endRef, length, wayId, source, target, cost, reverseCost=edge
                    edgeRefList=self.getRefListSubset(usedRefs, startRef, endRef)

                    if usedRefId in edgeRefList:
                        lastRef=usedCheckRefs[0]
                        for ref in usedCheckRefs[1:]:
                            onLine, (tmpLat, tmpLon)=self.isOnLineBetweenPoints(lat, lon, ref, lastRef, 10.0)
                            if onLine==True:
                                usedEdgeId=edgeId
                                edgeFound=True
                                break
                            lastRef=ref
                        
#        stop=time.time()
#        print(usedEdgeId)
#        print("getEdgeIdOnPos:%f"%(stop-start))
        return usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry

#    def getEdgeIdOnPosWithGeom(self, lat, lon):       
#        start=time.time()
#        self.cursorEdge.execute('SELECT * FROM edgeTable WHERE MbrIntersects("geom", BuildCircleMbr(%f, %f, %f, 4326))==1'%(lon, lat, 0.001))
#        allentries=self.cursorEdge.fetchall()
#
#        maxDistance=100
#        
#        usedEdge=None
#        usedWayId=None
#        usedRefId=None
#        usedLat=None
#        usedLon=None
#        usedCountry=None
#        
#        refCountry=self.getCountryOfPos(lat, lon)
#        if refCountry==None:
#            return usedEdge, usedWayId, usedRefId, (usedLat, usedLon), usedCountry
#
#        for x in allentries:
#            edgeId, startRef, endRef, length, wayId, source, target, cost, reverseCost=self.edgeFromDB(x)
#            
#            (wayEntryId, tags, refs, _)=self.getWayEntryForIdAndCountry(wayId, refCountry)
#            print("%s %s"%(tags, refs))
#            refList=self.getRefListSubset(refs, startRef, endRef)
#            if len(refList)!=0:
#                lastLat, lastLon=self.getCoordsWithRefAndCountry(startRef, refCountry)
#
#                for ref in refList[1:]:
#                    refLat, refLon=self.getCoordsWithRefAndCountry(ref, refCountry)
#                    if refLat==None or refLon==None:
#                        continue
#                    
#                    if lastLat==None or lastLon==None:
#                        lastLat=refLat
#                        lastLon=refLon
#                        continue
#                    
#                    points=self.createTemporaryPoint(lastLat, lastLon, refLat, refLon)
#                    for tmpLat, tmpLon in points:
#                        distance=self.osmutils.distance(lat, lon, tmpLat, tmpLon)
#                        if distance < maxDistance:
#                            maxDistance=distance
#                            usedEdge=edgeId
#                            usedWayId=wayId
#                            usedRefId=ref
#                            usedLat=refLat
#                            usedLon=refLon
#                            usedCountry=refCountry
#                    
#                    lastLat=refLat
#                    lastLon=refLon
#                    
#        stop=time.time()
#        print(stop-start)
#        return usedEdge, usedWayId, usedRefId, (usedLat, usedLon), usedCountry

#    def getNearNodesWithGeom(self, lat, lon, country, distance):        
#        nodes=list()
#        self.setDBCursorForCountry(country)
#        
#        start=time.time()
#
#        self.cursor.execute('SELECT * FROM refTable WHERE PtDistWithin("geom", MakePoint(%f, %f, 4326), %f, 0)==1'%(lon, lat, distance))
#
#        allentries=self.cursor.fetchall()
#        stop=time.time()
#        print(stop-start)
#        print(len(allentries))
#        for x in allentries:
#            refId, lat1, lon1, wayIdList, _=self.refFromDB(x)
#            nodes.append((refId, lat1, lon1, wayIdList))
#        print(len(nodes))
#        return nodes

    def getNodesInBBox(self, bbox, country, nodeType=None):
        latMin=bbox[1]
        lonMin=bbox[0]
        latMax=bbox[3]
        lonMax=bbox[2]
        
#        start=time.time()
        self.setDBCursorForCountry(country)
        if nodeType!=None:
            self.cursor.execute('SELECT * FROM refTable where lat BETWEEN %f AND %f AND lon BETWEEN %f AND %f AND type=%d'%(latMin, latMax, lonMin, lonMax, nodeType))
        else:
            self.cursor.execute('SELECT * FROM refTable where lat BETWEEN %f AND %f AND lon BETWEEN %f AND %f'%(latMin, latMax, lonMin, lonMax))
        allentries=self.cursor.fetchall()
#        print(len(allentries))
#        stop=time.time()
#        print("getNodesInBBox:%f"%(stop-start))
        return allentries

    def getNearNodes(self, lat, lon, country, maxDistance, nodeType=None):  
        latRangeMax=lat+0.003
        lonRangeMax=lon+0.003
        latRangeMin=lat-0.003
        lonRangeMin=lon-0.003
        
        bbox=[lonRangeMin, latRangeMin, lonRangeMax, latRangeMax]
        nodes=list()
        
        allentries=self.getNodesInBBox(bbox, country, nodeType)
        for x in allentries:
            refId, lat1, lon1, wayIdList, _=self.refFromDB(x)
            if wayIdList==None:
                # node ref not way ref
                continue

            distance=self.osmutils.distance(lat, lon, lat1, lon1)
            if distance>maxDistance:
                continue
            nodes.append((refId, lat1, lon1, wayIdList))
#        print(len(nodes))

        return nodes
    
    def testWayTable(self, country):
        self.setDBCursorForCountry(country)

        self.cursor.execute('SELECT * FROM wayTable')
        allentries=self.cursor.fetchall()
        for x in allentries:
            wayId, tags, refs, streetTypeId, name, nameRef, oneway, roundabout, maxspeed=self.wayFromDB3(x)
            print( "way: " + str(wayId) + " streetType:"+str(streetTypeId)+ " name:" +str(name) + " ref:"+str(nameRef)+" tags: " + str(tags) + "  refs: " + str(refs) + " oneway:"+str(oneway)+ " roundabout:"+str(roundabout) + " maxspeed:"+str(maxspeed))

    def testCrossingTable(self, country):
        self.setDBCursorForCountry(country)

        self.cursor.execute('SELECT * FROM crossingTable')
        allentries=self.cursor.fetchall()
        for x in allentries:
            crossingEntryId, wayid, refId, wayIdList=self.crossingFromDB(x)
            print( "id: "+ str(crossingEntryId) + " wayid: " + str(wayid) +  " refId: "+ str(refId) + " wayIdList: " + str(wayIdList))
        
    def testEdgeTable(self):
        self.cursorEdge.execute('SELECT * FROM edgeTable')
        allentries=self.cursorEdge.fetchall()
        for x in allentries:
            edgeId, startRef, endRef, length, wayId, source, target, cost, reverseCost=self.edgeFromDB(x)
            print( "edgeId: "+str(edgeId) +" startRef: " + str(startRef)+" endRef:"+str(endRef)+ " length:"+str(length)+ " wayId:"+str(wayId) +" source:"+str(source)+" target:"+str(target) + " cost:"+str(cost)+ " reverseCost:"+str(reverseCost))

    def wayFromDB(self, x):
        wayId=x[0]
        refs=pickle.loads(x[2])
        tags=self.decodeWayTags(x[1])
        streetInfo=x[3]
        streetTypeId, oneway, roundabout=self.decodeStreetInfo(streetInfo)
        name=x[4]
        nameRef=x[5]
        return (wayId, tags, refs, streetTypeId, name, nameRef)
    
    def wayFromDB2(self, x):
        wayId=x[0]
        refs=pickle.loads(x[2])
        tags=self.decodeWayTags(x[1])
        streetInfo=x[3]
        streetTypeId, oneway, roundabout=self.decodeStreetInfo(streetInfo)
        name=x[4]
        nameRef=x[5]
        return (wayId, tags, refs, streetTypeId, name, nameRef, oneway, roundabout)

    def wayFromDB3(self, x):
        wayId=x[0]
        refs=pickle.loads(x[2])
        tags=self.decodeWayTags(x[1])
        streetInfo=x[3]
        streetTypeId, oneway, roundabout=self.decodeStreetInfo(streetInfo)
        name=x[4]
        nameRef=x[5]
        maxspeed=x[6]
        return (wayId, tags, refs, streetTypeId, name, nameRef, oneway, roundabout, maxspeed)

    def refFromDB(self, x):
        refId=x[0]
        lat=x[1]
        lon=x[2]
        wayIdList=None
        if x[3]!=None:
            wayIdList=pickle.loads(x[3])
        tags=None
        if x[4]!=None:
            tags=pickle.loads(x[4])
        return (refId, lat, lon, wayIdList, tags)
    
    def refFromDB2(self, x):
        refId=x[0]
        lat=x[1]
        lon=x[2]
        wayIdList=None
        if x[3]!=None:
            wayIdList=pickle.loads(x[3])
        tags=None
        if x[4]!=None:
            tags=pickle.loads(x[4])
        if len(x)==6:
            nodeType=x[5]
        else:
            nodeType=0
        return (refId, lat, lon, wayIdList, tags, nodeType)
    
    def crossingFromDB(self, x):
        crossingEntryId=x[0]
        wayid=x[1]
        refId=x[2]            
        nextWayIdList=pickle.loads(x[3])
        return (crossingEntryId, wayid, refId, nextWayIdList)
    
    def edgeFromDB(self, x):
        edgeId=x[0]
        startRef=x[1]
        endRef=x[2]
        length=x[3]
        wayId=x[4]     
        source=x[5]
        target=x[6]
        cost=x[7]
        reverseCost=x[8]
        return (edgeId, startRef, endRef, length, wayId, source, target, cost, reverseCost)
 
    def edgeFromDBWithCoords(self, x):
        edgeId=x[0]
        startRef=x[1]
        endRef=x[2]
        length=x[3]
        wayId=x[4]     
        source=x[5]
        target=x[6]
        cost=x[7]
        reverseCost=x[8]
        lat1=x[9]
        lon1=x[10]
        lat2=x[11]
        lon2=x[12]
        return (edgeId, startRef, endRef, length, wayId, source, target, cost, reverseCost, lat1, lon1, lat2, lon2)
                   
    def addWayToDB(self, wayId, tags, refs, streetTypeId, name, nameRef, oneway, roundabout, maxspeed, wayCountries):
        if wayId==5210165 or wayId==5111290:
            print(wayCountries)

        if len(wayCountries)==0:
#            print("addWayToDB: skipping way %d because all refs are not in global ref DB"%(wayId))
            return False
        
        for country in wayCountries:
            self.addToWayTable(wayId, tags, refs, streetTypeId, name, nameRef, oneway, roundabout, maxspeed, country)   
            self.addToCountryWayTable(wayId, country)
        
        return True
    
    def isUsableNode(self):
        return ["motorway_junction", "traffic_signals", "mini_roundabout", "stop", "speed_camera"]
    
    def getNodeTypeId(self, nodeTag):
        # 0 is a way ref
        if nodeTag=="speed_camera":
            return 1
        if nodeTag=="motorway_junction":
            return 2
        if nodeTag=="traffic_signals":
            return 3
        if nodeTag=="mini_roundabout":
            return 4
        if nodeTag=="stop":
            return 5
        # 6 is address
        return -1
    
    def parse_nodes(self, node):
        for ref, tags, coords in node:
            # <tag k="highway" v="motorway_junction"/>
            lat=float(coords[1])
            lon=float(coords[0])
            if "highway" in tags:
                if tags["highway"] in self.isUsableNode():
                    nodeType=self.getNodeTypeId(tags["highway"])
                    if nodeType!=-1:
                        refCountry=self.getCountryOfPosDeep(lat, lon)
                        if refCountry!=None:
                            # TODO: speed_camera can have a refId without a way refId
                            self.addToCountryRefTableWithCountry(ref, lat, lon, refCountry)        
                            self.addToRefTable(ref, lat, lon, None, refCountry, tags, nodeType)
                            
            if "addr:street" in tags:
                refCountry=self.getCountryOfPosDeep(lat, lon)
                if refCountry!=None:
                    self.addToCountryRefTableWithCountry(ref, lat, lon, refCountry)
                    self.addToRefTable(ref, lat, lon, None, refCountry, tags, 6)
                    self.parseFullAddress(tags, ref, lat, lon, refCountry)

    def parse_coords(self, coord):
        for osmid, lon, lat in coord:
            self.addToCoordsTable(osmid, float(lat), float(lon))
           
    # only add full specified addresses   
    def parseFullAddress(self, tags, refId, lat, lon, country):  
        #   <node id="652701965" version="2" timestamp="2011-10-03T18:04:48Z" uid="47756" user="tunnelbauer" changeset="9462694" lat="47.8182158" lon="13.0495882">
#    <tag k="addr:city" v="Salzburg"/>
#    <tag k="addr:country" v="AT"/>
#    <tag k="addr:housenumber" v="9"/>
#    <tag k="addr:postcode" v="5020"/>
#    <tag k="addr:street" v="Magazinstraße"/>
#  </node>

        city=None
        postCode=None
        houseNumber=None
        streetName=None
#        countryCode=None
        if "addr:city" in tags:
            city=tags["addr:city"]
        if "addr:housenumber" in tags:
            houseNumber=tags["addr:housenumber"]
        if "addr:postcode" in tags:
            postCode=tags["addr:postcode"]
        if "addr:street" in tags:
            streetName=tags["addr:street"]
#        if "addr:country" in tags:
#            countryCode=tags["addr:country"]
        
        if city==None and postCode==None:
            return
        # TODO: parse postcode for city?
        if streetName==None:
            return
        if houseNumber==None:
            return
        
        self.addToAddressTable(refId, country, city, postCode, streetName, houseNumber, lat, lon)
    
#    # add way names
#    def parsePartAddress(self, tags, streetName, refId, lat, lon, country):  
#        city=None
#        postCode=None
#        houseNumber=None
##        countryCode=None
#        if "addr:city" in tags:
#            city=tags["addr:city"]
#        if "addr:housenumber" in tags:
#            houseNumber=tags["addr:housenumber"]
#        if "addr:postcode" in tags:
#            postCode=tags["addr:postcode"]
#        if "addr:street" in tags:
#            streetName=tags["addr:street"]
##        if "addr:country" in tags:
##            countryCode=tags["addr:country"]
#        
#        # TODO: parse postcode for city?
#        if streetName==None:
#            return
#
##        print("add ref %d with name %s to addresses"%(refId, streetName))
##        if countryCode!=None:
##            country=self.getCountryIdForAddrCountry(countryCode)
##            if country==None:
##                country=self.country
#        
#        self.addToAddressTable(refId, country, city, postCode, streetName, houseNumber, lat, lon)

    def isUsableRoad(self, streetType):
        if streetType=="road":
            return True
        if streetType=="unclassified":
            return True
        if "motorway" in streetType:
            return True
        if "trunk" in streetType:
            return True
        if "primary" in streetType:
            return True
        if "secondary" in streetType:
            return True
        if "tertiary" in streetType:
            return True
        if streetType=="residential":
            return True
        if streetType=="service":
            return True
        return False
    
    def decodeStreetInfo(self, streetInfo):
        oneway=(streetInfo&31)>>4
        roundabout=(streetInfo&63)>>5
        streetTypeId=(streetInfo&15)
        return streetTypeId, oneway, roundabout
    
    def encodeStreetInfo(self, streetTypeId, oneway, roundabout):
        streetInfo=streetTypeId+(oneway<<4)+(roundabout<<5)
        return streetInfo
    
    def getStreetTypeId(self, streetType):
        if streetType=="road":
            return 0
        if streetType=="unclassified":
            return 1
        if streetType=="motorway":
            return 2
        if streetType=="motorway_link":
            return 3
        if streetType=="trunk":
            return 4
        if streetType=="trunk_link":
            return 5
        if streetType=="primary":
            return 6
        if streetType=="primary_link":
            return 7
        if streetType=="secondary":
            return 8
        if streetType=="secondary_link":
            return 9
        if streetType=="tertiary":
            return 10
        if streetType=="tertiary_link":
            return 11
        if streetType=="residential":
            return 12
        if streetType=="service":
            return 13
        return -1
    
    def getStreetTypeIdForAddresses(self):
        return [0, 1, 6, 7, 8, 9, 10, 11, 12, 13]

    def getRequiredWayTags(self):
        return ["motorcar", "motor_vehicle", "access", "vehicle"]

    # TODY encode tags in bitfield?
    def stripUnneededTags(self, tags):
        newTags=dict()
        tagList=self.getRequiredWayTags()
        for key, value in tags.items():
            if key in tagList:
                newTags[key]=value
        return newTags
    
    def encodeWayTags(self, tags):
        if len(tags.keys())==0:
            return None
        pickeledTags=pickle.dumps(tags)
#        compressedTags=zlib.compress(pickeledTags)
        return pickeledTags
        
    def decodeWayTags(self, plainTags):
        if plainTags==None:
            return dict()
#        plainTags=zlib.decompress(compressedTags)
        tags=pickle.loads(plainTags)
        return tags
    
    def parse_ways(self, way):
        # TODO: hack
        if self.firstWay==False:
            self.firstWay=True
            self.commitCoordsDB()
            
        for wayid, tags, refs in way:
            if len(refs)==1:
                print("way with len(ref)==1 %d"%(wayid))
                continue
            if "building" in tags:
                if "addr:street" in tags:
                    # TODO: use first ref as location for addr?
                    storedRef, lat, lon=self.getCoordsEntry(refs[0])
                    if storedRef!=None:
                        if lat!=None and lon!=None:
                            refCountry=self.getCountryOfPosDeep(lat, lon)
                            if refCountry!=None:
                                self.addToCountryRefTableWithCountry(refs[0], lat, lon, refCountry)
                                self.addToRefTable(refs[0], lat, lon, None, refCountry, tags, 6)
                                self.parseFullAddress(tags, refs[0], lat, lon, refCountry)
                        
            if "landuse" in tags:
                None
            
            if "waterway" in tags:
                None
            
            if "natural" in tags:
                None
                
            if "highway" in tags:
                streetType=tags["highway"]
                if not self.isUsableRoad(streetType):
                    continue
                
                if "service" in tags:
                    # <tag k="service" v="parking_aisle"/>
                    if tags["service"]=="parking_aisle":
                        continue
                    if tags["service"]=="driveway":
                        continue
                    
                if "vehicle" in tags:
                    if tags["vehicle"]=="no":
                        continue
                    if tags["vehicle"]=="private":
                        continue
                    
                if "motorcar" in tags:
                    if tags["motorcar"]=="no":
                        continue
                    if tags["motorcar"]=="private":
                        continue
                
                if "motor_vehicle" in tags:
                    if tags["motor_vehicle"]=="no":
                        continue
                    if tags["motor_vehicle"]=="private":
                        continue
                    
                if "access" in tags:
                    if tags["access"]=="no":
                        continue
                    if tags["access"]=="private":
                        continue
                    
                if "addr:" in tags:
                    # TODO: parse address in way tags
                    None
                           
                streetTypeId=self.getStreetTypeId(streetType)
                if streetTypeId==-1:
                    print("unknown streetType %s"%(streetType))
                    continue
                            
                (name, nameRef)=self.getStreetNameInfo(tags, streetTypeId)
                
                oneway=0
                roundabout=0
                if "oneway" in tags:
                    if tags["oneway"]=="yes":
                        oneway=1
                    elif tags["oneway"]=="true":
                        oneway=1
                    elif tags["oneway"]=="1":
                        oneway=1
                if "junction" in tags:
                    if tags["junction"]=="roundabout":
                        roundabout=1
                
                maxspeed=self.getMaxspeed(tags, streetTypeId)

                wayCountries=list()
                
#                if wayid==5210165:
#                    print(refs)
#                if wayid==5111290:
#                    print(refs)
                
#                firstRefCountry=None
#                firstRefLat=None
#                firstRefLon=None
                
                for ref in refs:  
                    storedRef, lat, lon=self.getCoordsEntry(ref)
                    if storedRef==None:
#                        print("no ccords for ref==%d on wayid==%d"%(ref, wayid))
                        continue
                        
                    storedRef, refCountry=self.getCountryOfRef(ref)
                    if storedRef==None:
                        refCountry=self.getCountryOfPosDeep(lat, lon)
                                                
                    if refCountry!=None:
#                        if firstRefCountry==None:
#                            firstRefCountry=refCountry
#                            firstRefLat=lat
#                            firstRefLon=lon
                        
                        wayCountries.append(refCountry)
                        self.addToCountryRefTableWithCountry(ref, lat, lon, refCountry)
                        self.addToRefTable(ref, lat, lon, wayid, refCountry, None, 0)
                    
                requiredTags=self.stripUnneededTags(tags)
                wayAdded=self.addWayToDB(wayid, requiredTags, refs, streetTypeId, name, nameRef, oneway, roundabout, maxspeed, wayCountries)
        
#                if wayAdded==True and firstRefCountry!=None and name!=None:
#                    if streetTypeId in self.getStreetTypeIdForAddresses():
##                        resultList=self.getAdressListForStreetInCountry(name, firstRefCountry)
##                        if len(resultList)==0:
#                        # add street to addresses if no other entry till now
#                        # TODO: use first ref as location for addr?
#                        self.parsePartAddress(tags, name, refs[0], firstRefLat, firstRefLon, firstRefCountry)

    def parse_relations(self, relation):
        for osmid, tags, ways in relation:
            if "type" in tags:     
                if tags["type"]=="restriction":
                    restrictionType=None
                    if "restriction" in tags:
                        restrictionType=tags["restriction"]
                    if "restriction:motorcar" in tags:
                        restrictionType=tags["restriction:motorcar"]
                        
                    if restrictionType!=None:
                        isWay=False
                        isNode=False
                        fromWayId=0
                        toWayId=0
                        viaNode=0
                        viaWay=list()
    
                        for part in ways:
                            roleId=int(part[0])
                            roleType=part[1]
                            roleTag=part[2]
    
                            if roleType=="way":
                                isWay=True
                            elif roleType=="node":
                                isNode=True
                                
                            if roleTag=="from":
                                fromWayId=roleId
                            elif roleTag=="to":
                                toWayId=roleId
                            elif roleTag=="via":
                                if isNode:
                                    viaNode=roleId
                                elif isWay:
                                    print("relation %d with via type way %s"%(int(osmid), str(ways)))
                                    viaWay.append(roleId)
                        if fromWayId!=0 and toWayId!=0:
                            restrictionEntry=dict()
                            restrictionEntry["type"]=restrictionType
                            restrictionEntry["to"]=toWayId
                            restrictionEntry["from"]=fromWayId
                            if viaNode!=None:
                                restrictionEntry["viaNode"]=viaNode
                            elif len(viaWay)!=0:
                                restrictionEntry["viaWay"]=viaWay
    
                            self.wayRestricitionList.append(restrictionEntry)
                        
                elif tags["type"]=="multipolygon":
                    if "boundary" in tags:
                        if tags["boundary"]=="administrative":
#                            print(tags)
                            None
                
                elif tags["type"]=="enforcement":
                    if "enforcement" in tags:
                        if tags["enforcement"]=="maxspeed":
                            if "maxspeed" in tags:
                                for part in ways:
                                    roleId=int(part[0])
                                    roleType=part[1]
                                    roleTag=part[2]
    
                                    if roleType=="node":
                                        if roleTag=="from":
                                            fromRefId=roleId
                                            storedRef, refCountry=self.getCountryOfRef(fromRefId)
                                            if storedRef!=None:
                                                resultList=self.getRefEntryForIdAndCountry(fromRefId, refCountry)
                                                if len(resultList)==1:
                                                    refid, lat, lon, wayIdList, storedTags=resultList[0]
#                                                    print("enforcement at ref %d %s"%(refid, tags))
                                                    self.updateRefTableEntry(refid, tags, 1, refCountry)

#    <member type="way" ref="61014292" role="outer"/>
#    <member type="way" ref="61014415" role="outer"/>
#    <member type="way" ref="61014477" role="outer"/>
#    <member type="way" ref="61796467" role="outer"/>
#    <member type="way" ref="61797702" role="outer"/>
#    <tag k="ref" v="GM"/>
#    <tag k="wikipedia:de" v="Bezirk Gmunden"/>
#    <tag k="admin_level" v="6"/>
#    <tag k="name" v="Bezirk Gmunden"/>
#    <tag k="is_in" v="Oberösterreich, Österreich, Europe"/>
#    <tag k="type" v="multipolygon"/>
#    <tag k="boundary" v="administrative"/>
#    <tag k="ref:at:gkz" v="407"/>

            
    def getStreetNameInfo(self, tags, streetTypeId):

        name=None
        ref=None
        intref=None
        
        if "name" in tags:
            name=tags["name"]
        
        if "ref" in tags:
            ref=tags["ref"]
            
        if "int_ref" in tags:
            intref=tags["int_ref"]
            
        if streetTypeId==2 or streetTypeId==3:
            if ref!=None:
                ref=ref.replace(' ', '')
                if name==None:
                    name=ref    
        elif streetTypeId==6 or streetTypeId==7:
            if ref!=None:
                ref=ref.replace(' ', '')    
                if not ref[0]=="B":
                    ref="B"+ref
                if name==None:
                    name=ref    
        elif streetTypeId==8 or streetTypeId==9:
            if ref!=None:
                ref=ref.replace(' ', '')
                if not ref[0]=="L":
                    ref="L"+ref
                if name==None:
                    name=ref  
        elif streetTypeId==10 or streetTypeId==11:
            if ref!=None:
                ref=ref.replace(' ', '')
                if name==None:
                    name=ref  
        elif streetTypeId==12:
            if ref!=None:
                ref=ref.replace(' ', '')
                if name==None:
                    name=ref  
        elif streetTypeId==4 or streetTypeId==5:
            if ref!=None:
                ref=ref.replace(' ', '')
                if name==None:
                    name=ref  
        elif streetTypeId==1:
            None

        return (name, ref)
    
    def getWaysWithRefAndCountry(self, ref, country):
        wayIdList=list()
        resultList=self.getRefEntryForIdAndCountry(ref, country)
        if len(resultList)==1:
            _, _, _, wayIdList, _=resultList[0]
            return wayIdList
        
        return wayIdList

#    def getStreetInfoWithWayId(self, wayId, country):
#        (streetEntryId, tags, _, streetTypeId, name, nameRef)=self.getWayEntryForIdAndCountry(wayId, country)
#        if streetEntryId!=None:
#            return (name, nameRef)
#        return (None, None)
        
    def getCoordsWithRefAndCountry(self, refId, country):
        resultList=self.getRefEntryForIdAndCountry(refId, country)
        if len(resultList)==1:
            _, lat, lon, _, _=resultList[0]
            return (lat, lon)
        
        return (None, None)
    
    def findWayWithRefInAllWays(self, refId, fromWayId):
        possibleWays=list()
        _, country=self.getCountryOfRef(refId)
        if country==None:
            return possibleWays
        
        wayIdList=self.getWaysWithRefAndCountry(refId, country)
        if wayIdList==None or len(wayIdList)<=1:
            # no crossings at ref if not more then on different wayIds
            return possibleWays
        
        for wayid in wayIdList:
            resultList=self.getCountrysOfWay(wayid)
            if len(resultList)!=0:
                for result in resultList:
                    _, wayid, storedCountry=result
    
                    (wayEntryId, tags, refs, streetTypeId, name, nameRef, oneway, roundabout)=self.getWayEntryForIdAndCountry2(wayid, storedCountry)
                    if wayEntryId==None:
                        print("create crossings: skip crossing for wayId %s at refId %d to wayId %d to country %d"%(fromWayId, refId, wayid, storedCountry))
                        continue
                    
                    for wayRef in refs:
                        if wayRef==refId:
                            possibleWays.append((wayid, tags, refs, streetTypeId, name, nameRef, oneway, roundabout))
            else:
                print("create crossings: skip crossing for wayId %d at refId %d to wayId %s since it is in an unknown country"%(fromWayId, refId, wayid))
        return possibleWays
    
    def findWayWithEndRef(self, ways, endRef, country):
        possibleWays=list()
        for wayId  in ways:
            (actWayId, _, refs, streetTypeId, name, nameRef)=self.getWayEntryForIdAndCountry(wayId, country)
            if refs[-1]==endRef:
                possibleWays.append(actWayId)
        return possibleWays
    
    def findStartWay(self, ways, country):
        for wayId  in ways:
            (actWayId, _, refs, streetTypeId, name, nameRef)=self.getWayEntryForIdAndCountry(wayId, country)
            startRef=refs[0]
            possibleWays=self.findWayWithEndRef(ways, startRef, country)
            if len(possibleWays)==0:
                return actWayId
        return ways[0]
        
    def getAdressCountryList(self):
        return self.osmList.keys()
    
    def getAdressCityList(self, country):
        self.cursorAdress.execute('SELECT DISTINCT city, postCode FROM addressTable WHERE country=%d ORDER by city'%(country))
        allentries=self.cursorAdress.fetchall()
        cityList=list()
        for x in allentries:
            if x[0]!=None:
                cityList.append((x[0], x[1]))
        return cityList

    def getAdressPostCodeList(self, country):
        self.cursorAdress.execute('SELECT postCode FROM addressTable WHERE country=%d'%(country))
        allentries=self.cursorAdress.fetchall()
        postCodeList=set()
        for x in allentries:
            postCode=x[0]
            postCodeList.append(postCode)
        return postCodeList

    def getAdressListForCity(self, country, city):
        self.cursorAdress.execute('SELECT * FROM addressTable WHERE country=%d AND city="%s"'%(country, city))
        allentries=self.cursorAdress.fetchall()
        streetList=list()
        for x in allentries:
            streetList.append(self.addressFromDB(x))
        return streetList
                    
    def getAdressListForPostCode(self, country, postCode):
        self.cursorAdress.execute('SELECT * FROM addressTable WHERE country=%d AND postCode=%d'%(country, postCode))
        allentries=self.cursorAdress.fetchall()
        streetList=list()
        for x in allentries:
            streetList.append(self.addressFromDB(x))
        return streetList
    
    def getAdressListForCountry(self, country):
        self.cursorAdress.execute('SELECT * FROM addressTable WHERE country=%d'%(country))
        allentries=self.cursorAdress.fetchall()
        streetList=list()
        for x in allentries:
            streetList.append(self.addressFromDB(x))
        return streetList
    
    def getAdressListForStreetInCountry(self, streetName, country):
        streetList=list()
        
        try:
            self.cursorAdress.execute('SELECT * FROM addressTable WHERE country=%d AND streetName="%s"'%(country, streetName))
            allentries=self.cursorAdress.fetchall()
            for x in allentries:
                streetList.append(self.addressFromDB(x))
        except sqlite3.OperationalError:
            print("getAdressListForStreetInCountry: failed for %s"%(streetName))
            
        return streetList

    def getExistingAdressListForStreetInCountry(self, streetName, country):
        streetList=list()
        
        try:
            self.cursorAdress.execute('SELECT * FROM addressTable WHERE country=%d AND houseNumber ISNULL AND streetName="%s"'%(country, streetName))
            allentries=self.cursorAdress.fetchall()
            for x in allentries:
                streetList.append(self.addressFromDB(x))
        except sqlite3.OperationalError:
            print("getAdressListForStreetInCountry: failed for %s"%(streetName))
            
        return streetList
    
    def createStartTrackItem(self):
        streetTrackItem=dict()
        streetTrackItem["start"]="start"
        return streetTrackItem
    
    def createEndTrackItem(self):
        streetTrackItem=dict()
        streetTrackItem["end"]="end"
        return streetTrackItem

    def calcRoute(self, route):
        route.calcRoute(self)
        
    def createBBoxForRoute(self, route):
        bbox=[None, None, None, None]
        routingPointList=route.getRoutingPointList()
        for point in routingPointList:
            (lat, lon)=point.getPos()
            if bbox[0]==None:
                bbox[0]=lon
            if bbox[1]==None:
                bbox[1]=lat
            if bbox[2]==None:
                bbox[2]=lon
            if bbox[3]==None:
                bbox[3]=lat
            
            if lon<bbox[0]:
                bbox[0]=lon
            if lon>bbox[2]:
                bbox[2]=lon
            if lat<bbox[1]:
                bbox[1]=lat
            if lat>bbox[3]:
                bbox[3]=lat
                                
        return bbox
            
    def createBBox(self, pos1, pos2):
        bbox=[0.0, 0.0, 0.0, 0.0]
        lat1=pos1[0]
        lon1=pos1[1]
        lat2=pos2[0]
        lon2=pos2[1]
        if lat2>lat1:
            bbox[3]=lat2
            bbox[1]=lat1
        else:
            bbox[3]=lat1
            bbox[1]=lat2
        
        if lon2>lon1:
            bbox[2]=lon2
            bbox[0]=lon1
        else:
            bbox[2]=lon1
            bbox[0]=lon2
            
        return bbox

    def getRoutingForPoint(self, point):
        lat1, lon1=point.getRefPos()
                    
        lat2, lon2=point.getStartRefPos()
        distanceStartRef=self.osmutils.distance(lat1, lon1, lat2, lon2)
        
        lat2, lon2=point.getEndRefPos()
        distanceEndRef=self.osmutils.distance(lat1, lon1, lat2, lon2)

        if distanceStartRef<distanceEndRef:
            return point.getSource()
        else:
            return point.getTarget()
           
    def getRoutingSourceForPointOneway(self, startPoint, targetPoint):
        source=startPoint.getTarget()
        
        if startPoint.getEdgeId()==targetPoint.getEdgeId():
            latStart, lonStart=startPoint.getPos()
            latTarget, lonTarget=targetPoint.getPos()
                      
            latStartRef, lonStartRef=startPoint.getStartRefPos()            
            
            distanceStartToStartRef=self.osmutils.distance(latStart, lonStart, latStartRef, lonStartRef)
            distanceTargetToStartRef=self.osmutils.distance(latTarget, lonTarget, latStartRef, lonStartRef)
            
            if distanceStartToStartRef<distanceTargetToStartRef:
                source=startPoint.getSource()
                print("source=startPoint.getSource()")
              
        return source
    
    def getRoutingTargetForPointOneway(self, startPoint, targetPoint):
        target=targetPoint.getSource()
        
        if startPoint.getEdgeId()==targetPoint.getEdgeId():
            latStart, lonStart=startPoint.getPos()
            latTarget, lonTarget=targetPoint.getPos()
                      
            latEndRef, lonEndRef=targetPoint.getEndRefPos()            
            
            distanceStartToEndRef=self.osmutils.distance(latStart, lonStart, latEndRef, lonEndRef)
            distanceTargetToEndRef=self.osmutils.distance(latTarget, lonTarget, latEndRef, lonEndRef)
            
            if distanceTargetToEndRef<distanceStartToEndRef:
                target=targetPoint.getTarget()
                print("target=targetPoint.getTarget()")
            
        return target
        
   
    def calcRouteForPoints(self, route):  
        routingPointList=route.getRoutingPointList()                
      
        allPathCost=0.0
        allEdgeList=list()
        
        if len(routingPointList)!=0:  
            startEdge=routingPointList[0].getEdgeId()
            endEdge=routingPointList[-1].getEdgeId()

            i=0   
            startPoint=routingPointList[0]
            if startPoint.getSource()==0:
                # should not happen
                print("startPoint NOT resolved in calc route")
                return None, None
            sourceEdge=startPoint.getEdgeId()
            bbox=self.createBBoxForRoute(route)

            # on a onway always start at the end
            if startPoint.getTargetOneway()==1:
#                if sourceEdge!=routingPointList[1].getEdgeId():
#                    source=startPoint.getTarget()
                    source=self.getRoutingSourceForPointOneway(startPoint, routingPointList[1])
#                else:
#                    source=self.getRoutingForPoint(startPoint)
            else:
                # look if target or source is nearer and start from there
                source=self.getRoutingForPoint(startPoint)
                    
            i=1
            for targetPoint in routingPointList[1:]:
                if targetPoint.getTarget()==0:
                    # should not happen
                    print("targetPoint NOT resolved in calc route")
                    return None, None
                
                targetEdge=targetPoint.getEdgeId()

                # make sure we are going through the target if it is
                # on a oneway by routing first to the source
                if targetPoint.getTargetOneway()==1:
#                    if sourceEdge!=targetEdge:
#                        target=targetPoint.getSource()
                        target=self.getRoutingTargetForPointOneway(startPoint, targetPoint)
#                    else:
#                        target=self.getRoutingForPoint(targetPoint)  
                else:
                    # look if source or target is nearer and stop there
                    target=self.getRoutingForPoint(targetPoint)                  
                            
#                print("calcRouteForPoints: source %d %d %d %d"%(source, sourceEdge, startPoint.getWayId(), startPoint.getRefId()))
#                print("calcRouteForPoints: target %d %d %d %d"%(target, targetEdge, targetPoint.getWayId(), targetPoint.getRefId()))
                
                if source==0 and target==0:
                    print("source and target==0!")
                    return None, None

                if source==target:
                    print("source and target equal!")
                    startPoint=targetPoint
                    sourceEdge=startPoint.getEdgeId()
                else:                  
#                    if self.dWrapper!=None:
#                        edgeList, pathCost=self.dWrapper.computeShortestPath(source, target)
#                        allEdgeList.extend(edgeList)
#                        allPathCost=allPathCost+pathCost            
                
                    if self.dWrapperTrsp!=None:
                        edgeList, pathCost=self.dWrapperTrsp.computeShortestPath(source, target, bbox, False)
                        if edgeList==None:
                            return None, None
                                    
                    startPoint=targetPoint
                    
                    # if the point is on a oneway we always
                    # continue at target and add the edge between
                    if startPoint.getTargetOneway()==1:
#                        if sourceEdge!=targetEdge:
                            source=startPoint.getTarget()
#                            source=self.getRoutingSourceForPointOneway(startPoint, )
                            if edgeList[-1]!=targetEdge:
                                edgeList.append(targetEdge) 
#                        else:
#                            source=target
                    else:
                        if startPoint.getType()==2:
                            if sourceEdge!=targetEdge:
                                # look how to continue after a waypoint                                    
                                if edgeList[-1]!=targetEdge:
                                    # make sure we go through waypoint edge
                                    edgeList.append(targetEdge)
                                    # set next source point - continue from the opposite
                                    if target==startPoint.getSource():
                                        source=startPoint.getTarget()
                                    else:
                                        source=startPoint.getSource() 
                                else:
                                    # already passed - go on
                                    source=target
                            else:
                                # special case if both on the same edge
                                # just continue from here
                                source=target        
                        else:
                            # just continue from here
                            source=target
                            
                    allEdgeList.extend(edgeList)
                    allPathCost=allPathCost+pathCost 
                        
                    sourceEdge=startPoint.getEdgeId()
                i=i+1
                
            # always add start and ende edge if needed
            if len(allEdgeList)==0 or not allEdgeList[0]==startEdge:
                allEdgeList.insert(0, startEdge)

            if not allEdgeList[-1]==endEdge:
                allEdgeList.append(endEdge)
                
            return allEdgeList, allPathCost

        return None, None

    def calcRouteForPointsTest(self, route):
        routingPointList=route.getRoutingPointList()                
        if len(routingPointList)!=0:  
            i=0   
            startPoint=routingPointList[0]
            if startPoint.getSource()==0:
                return
            
            bbox=self.createBBoxForRoute(route)
            for targetPoint in routingPointList[1:]:
                if targetPoint.getTarget()==0:
                    return
                            
                print("all edges len:%d"%self.getLenOfEdgeTable())
                print("bbox edges len:%d"%self.getLenOfEdgeTableForRouting(bbox))
                        
                startPoint=targetPoint
                i=i+1
                

#    def calcRouteForNodes(self, source, target):        
#        if source==0 and target==0:
#            print("source and target==0!")
#            return None
#        
#        if self.dWrapper!=None:
#            edgeList, pathCost=self.dWrapper.computeShortestPath(source, target)
#            return edgeList, pathCost
#                                
#        return None

    def calcRouteForNodesTrsp(self, source, target):        
        if source==0 and target==0:
            print("source and target==0!")
            return None
        
        if self.dWrapperTrsp!=None:
            edgeList, pathCost=self.dWrapperTrsp.computeShortestPath(source, target, False)
            return edgeList, pathCost
                                
        return None
            
    def getLastWayOnTrack(self, trackWayList):
        if len(trackWayList)>0:
            return trackWayList[-1]
        return None
    
#    def getRoundaboutEnterRef(self, trackWayList):
#        if len(trackWayList)>0:
#            wayList=list()
#            for trackItem in trackWayList[::-1]:
#                wayId=trackItem["wayId"]
#                if not wayId in wayList:
#                    wayList.append(wayId)
#                trackItemRefs=trackItem["refs"]
#                for trackItemRef in trackItemRefs[::-1]:
#                    if "crossingInfo" in trackItemRef:
#                        crossingInfo=trackItemRef["crossingInfo"]
#                        if "roundabout:enter" in crossingInfo:
#                            return trackItemRef["crossingRef"], wayList
#                
#        return None, None
        
    def getLastCrossingListOnTrack(self, trackWayList):
        if len(trackWayList)>0:
            trackItemRefs=trackWayList[-1]["refs"]
            for trackItemRef in trackItemRefs[::-1]:
                if "crossing" in trackItemRef:
                    return trackItemRef["crossing"]
        return None
    
    def getCrossingInfoTag(self, name, nameRef):
        if nameRef!=None and name!=None:
            return "%s %s"%(name, nameRef)
        elif nameRef==None and name!=None:
            return "%s"%(name)
        elif nameRef!=None and name==None:
            return "%s"%(nameRef)
        return "No name"

    def isPointOnCurrentRouteStart(self, lat, lon, trackList, minDistance):
        (lat1, lon1)=trackList[0]["refs"][0]["coords"]
        
        # only if we just going from the start to the wrog direction
        startDistance=self.osmutils.distance(lat, lon, lat1, lon1)
        # wait for 20m to check if we are on the correct way
        if startDistance<20:
            nodes=list()
            distance=0
            lastLat=lat1
            lastLon=lon1
            # collect refs for at least 30m to check
            for trackItemRef in trackList[0]["refs"][1:]:
                (lat2, lon2)=trackItemRef["coords"]
                nodes.extend(self.createTemporaryPoint(lastLat, lastLon, lat2, lon2))
                distance=distance+self.osmutils.distance(lastLat, lastLon, lat2, lon2)
                if distance>30:
                    break
                lastLat=lat2
                lastLon=lon2
            for tmpLat, tmpLon in nodes:
                distance=self.osmutils.distance(lat, lon, tmpLat, tmpLon)
                if distance<minDistance:
                    return True
            return False
        return True

    def isOnLineBetweenPoints(self, lat, lon, ref1, ref2, minDistance, offset=0.0):
        _, country=self.getCountryOfRef(ref1)
        if country==None:
            return False, (None, None)
        resultList=self.getRefEntryForIdAndCountry(ref1, country)
        if len(resultList)==1:
            _, lat1, lon1, _, _=resultList[0]
        else:
            return False, (None, None)
        _, country=self.getCountryOfRef(ref2)
        if country==None:
            return False, (None, None)
        resultList=self.getRefEntryForIdAndCountry(ref2, country)
        if len(resultList)==1:
            _, lat2, lon2, _, _=resultList[0]
        else:
            return False, (None, None)
        nodes=self.createTemporaryPoint(lat1, lon1, lat2, lon2, offset)
#        print(nodes)
        maxDistance=minDistance
        usedLat=None
        usedLon=None
        for tmpLat, tmpLon in nodes:
            distance=self.osmutils.distance(lat, lon, tmpLat, tmpLon)
            if distance<maxDistance:
                maxDistance=distance
                usedLat=tmpLat
                usedLon=tmpLon
        if usedLat!=None and usedLon!=None:
            return True, (usedLat, usedLon)
        return False, (None, None)
    
    def getEnforcmentsOnWay(self, wayId, refs):
        enforcementList=list()
        for ref in refs:
            _, country=self.getCountryOfRef(ref)
            if country==None:
                continue
            resultList=self.getRefEntryForIdAndCountry2(ref, country)
            if len(resultList)==1:
                ref, lat, lon, _, storedTags, storedNodeType=resultList[0]
                if storedNodeType==1:
                    # enforcement
                    enforcement=dict()
                    enforcement["coords"]=(lat, lon)
                    enforcement["info"]="maxspeed:%s"%(storedTags["maxspeed"])
                    enforcementList.append(enforcement)
                # speed_camera refs can also be "near" this ref           
                speedCameraNodes=self.getNearNodes(lat, lon, country, 1, 10.0)
                for speedCameraRef, _, _, _ in speedCameraNodes:
                    if speedCameraRef!=ref:
                        enforcement=dict()
                        enforcement["coords"]=(lat, lon)
                        enforcement["info"]="maxspeed"
                        enforcementList.append(enforcement)
        
        if len(enforcementList)==0:
            return None
        return enforcementList
    
    def printEdgeForRefList(self, refListPart, edgeId, trackWayList, startPoint, endPoint):
        result=self.getEdgeEntryForEdgeId(edgeId)
        (edgeId, startRef, _, length, wayId, _, _, _, _)=result
            
        latTo=None
        lonTo=None
        latFrom=None
        lonFrom=None
        
        _, country=self.getCountryOfRef(startRef)
        if country==None:
            return
        
        (wayId, tags, _, streetTypeId, name, nameRef)=self.getWayEntryForIdAndCountry(wayId, country)

        trackItem=dict()
        trackItem["type"]=streetTypeId
        trackItem["info"]=(name, nameRef)
        trackItem["wayId"]=wayId
        trackItem["edgeId"]=edgeId

        lastWayId=None
        lastEdgeId=None
        lastName=None
        lastTrackItemRef=None
        
        lastTrackItem=self.getLastWayOnTrack(trackWayList)
        if lastTrackItem!=None:
            if len(lastTrackItem["refs"])!=0:
                lastTrackItemRef=lastTrackItem["refs"][-1]
            lastWayId=lastTrackItem["wayId"]
            lastEdgeId=lastTrackItem["edgeId"]
            if "info" in lastTrackItem:
                (lastName, lastRefName)=lastTrackItem["info"]
            
        routeEndRefId=None
        if endPoint!=None:
            routeEndRefId=endPoint.getRefId()
            if not routeEndRefId in refListPart:
                print("routeEndRef %d not in refListPart %s"%(routeEndRefId, refListPart))
                routeEndRefId=refListPart[0]
            else:
                index=refListPart.index(routeEndRefId)                
                if index!=0:
                    # use one ref before
                    prevRefId=refListPart[index-1]
                else:
                    prevRefId=routeEndRefId
                     
                if prevRefId!=routeEndRefId:
                    lat, lon=endPoint.getPos()
                    onLine, (tmpLat, tmpLon)=self.isOnLineBetweenPoints(lat, lon, routeEndRefId, prevRefId, 10.0)
                    if onLine==True:
                        routeEndRefId=prevRefId
        

        routeStartRefId=None
        if startPoint!=None:
            routeStartRefId=startPoint.getRefId()
            if not routeStartRefId in refListPart:
                print("routeStartRefId %d not in refListPart %s"%(routeStartRefId, refListPart))
                routeStartRefId=refListPart[0]
            else:
                index=refListPart.index(routeStartRefId)
                if index!=len(refListPart)-1:
                    nextRefId=refListPart[index+1]
                else:
                    nextRefId=routeStartRefId
                                    
                if nextRefId!=routeStartRefId:
                    lat, lon=startPoint.getPos()
                    onLine, (tmpLat, tmpLon)=self.isOnLineBetweenPoints(lat, lon, routeStartRefId, nextRefId, 10.0)
                    if onLine==True:
                        routeStartRefId=nextRefId
        
        routeStartRefPassed=False
              
        trackItemRefs=list()
        for ref in refListPart:  
            # TODO: print passed waypoint
            _, country=self.getCountryOfRef(ref)
            if country==None:
                continue
            
            resultList=self.getRefEntryForIdAndCountry2(ref, country)
            if len(resultList)==1:
                ref, lat, lon, _, storedTags, storedNodeType=resultList[0]
            else:
                print("printEdgeForRefList: no node in DB with %d"%(ref))
                continue
      
            if routeStartRefId!=None and routeStartRefPassed==False:
                if ref==routeStartRefId:
                    startLat, startLon=startPoint.getPos()
                    preTrackItemRef=dict()
                    preTrackItemRef["coords"]=(startLat, startLon)
                    preTrackItemRef["ref"]=-1
                    trackItemRefs.append(preTrackItemRef)
                    latFrom=startLat
                    lonFrom=startLon
                    length=self.osmutils.distance(lat, lon, startLat, startLon)
                    routeStartRefPassed=True
                else:
                    continue
            
            if ref!=refListPart[-1]:
                latFrom=lat
                lonFrom=lon
                      
            if ref!=refListPart[0]:
                latTo=lat
                lonTo=lon
                
            trackItemRef=dict()
            trackItemRef["ref"]=ref
            trackItemRef["coords"]=(lat, lon)
#            if storedNodeType==1:
#                # enforcement
#                trackItemRef["enforcement"]="maxspeed:%s"%(storedTags["maxspeed"])
#                trackItemRef["enforcementPos"]=(lat, lon)
            
            # TODO: speed_camera refs can also be "near" this ref
#            speedCameraNodes=self.getNearNodes(lat, lon, country, 1, 50.0)
#            for speedCameraRef, _, _, _ in speedCameraNodes:
#                if speedCameraRef!=ref:
#                    trackItemRef["enforcement"]="maxspeed"

            trackItemRefs.append(trackItemRef)

            if routeEndRefId!=None and ref==routeEndRefId:
                endLat, endLon=endPoint.getPos()
                postTrackItemRef=dict()
                postTrackItemRef["coords"]=(endLat, endLon)
                postTrackItemRef["ref"]=-1
                postTrackItemRef["direction"]=99
                postTrackItemRef["crossingInfo"]="end"
                crossingList=list()
                crossingList.append((wayId, 99, None, ref))                                        
                postTrackItemRef["crossing"]=crossingList
                trackItemRefs.append(postTrackItemRef)
                latTo=endLat
                lonTo=endLon
                if ref==refListPart[0]:
                    length=self.osmutils.distance(lat, lon, endLat, endLon)
                else:
                    length=length+self.osmutils.distance(lat, lon, endLat, endLon)

                     
            if lastTrackItemRef!=None:                     
                if ref==refListPart[0]:   
                    if edgeId==lastEdgeId:
                        # u-turn
                        crossingList=list()
                        crossingList.append((wayId, 98, None, ref))                                        
                        lastTrackItemRef["crossing"]=crossingList
                        lastTrackItemRef["direction"]=98
                        lastTrackItemRef["azimuth"]=360
                        lastTrackItemRef["crossingInfo"]="u-turn"

                        self.latCross=lat
                        self.lonCross=lon
                    else:
                        resultList=self.getCrossingEntryForRefId(lastWayId, ref, country)
                        if len(resultList)!=0:
                            crossingList=list()
                            crossingFound=False
                            for result in resultList:
                                if crossingFound==True:
                                    break
                                (_, _, _, nextWayIdList)=result
#                                print(nextWayIdList)
                                for nextWayId, crossingType, crossingInfo in nextWayIdList:
                                    if wayId==nextWayId:
                                        crossingList.append((nextWayId, crossingType, crossingInfo, ref))                                        
                                        crossingFound=True
                                        break
                                    
                            if len(crossingList)!=0:
                                lastTrackItemRef["crossing"]=crossingList
                                self.latCross=lat
                                self.lonCross=lon                        
                        
                            if self.roundaboutExitNumber!=None:
                                for result in resultList:
                                    (_, _, _, nextWayIdList)=result
                                            
                                    for roundaboutNextWayId, roundaboutCrossingType, _ in nextWayIdList:
                                        if wayId!=roundaboutNextWayId and roundaboutCrossingType==4:
                                            self.roundaboutExitNumber=self.roundaboutExitNumber+1
                                
                if latTo!=None and lonTo!=None and self.latCross!=None and self.lonCross!=None and self.latFrom!=None and self.lonFrom!=None:
                    azimuth=self.osmutils.azimuth((self.latCross, self.lonCross), (self.latFrom, self.lonFrom), (latTo, lonTo))   
                    direction=self.osmutils.direction(azimuth)
                    
                    self.latCross=None
                    self.lonCross=None
                              
                    crossingType=None
                    crossingInfo=None
          
                    crossingList=self.getLastCrossingListOnTrack(trackWayList)
                    if crossingList!=None:
                        if len(crossingList)==1:
                            _, crossingType, crossingInfo, crossingRef=crossingList[0]
                        else:
                            print("printEdgeForRefList: more then one crossing at ref %d"%(ref))
                        
                    if crossingType!=None:   
                        if crossingType!=-1:
                            lastTrackItemRef["direction"]=direction
                            lastTrackItemRef["azimuth"]=azimuth
 
                        if crossingType==1 or crossingType==0 or crossingType==9 or crossingType==10:
                            if lastName!=None:
                                if lastName!=name:
                                    lastTrackItemRef["crossingInfo"]="change:%s"%self.getCrossingInfoTag(name, nameRef)
                                else:
                                    lastTrackItemRef["crossingInfo"]="stay:%s"%self.getCrossingInfoTag(name, nameRef)
                            else:
                                if name!=None:
                                    lastTrackItemRef["crossingInfo"]="change:%s"%self.getCrossingInfoTag(name, nameRef)
                                else:
                                    lastTrackItemRef["crossingInfo"]="stay:%s"%self.getCrossingInfoTag(name, nameRef)
                        elif crossingType==2:
                            # highway junction
                            motorwayExitName=crossingInfo
                            if motorwayExitName!=None:
                                lastTrackItemRef["crossingInfo"]="exit:%s"%(motorwayExitName)
                            else:
                                lastTrackItemRef["crossingInfo"]="exit:"
                            lastTrackItemRef["direction"]=39
#                            print(lastTrackItemRef)
#                                else:
#                                    lastTrackItemRef["crossingInfo"]="stay:%s"%self.getCrossingInfoTag(name, nameRef)
                                    # TODO: direction for motorway
                        elif crossingType==3:
                            # enter roundabout at crossingRef
                            # remember to get the exit number when leaving the roundabout
                            lastTrackItemRef["crossingInfo"]="roundabout:enter"
                            lastTrackItemRef["crossingRef"]=crossingRef
                            lastTrackItemRef["direction"]=40
                            self.roundaboutEnterItem=lastTrackItemRef
                            self.roundaboutExitNumber=0
                                
                        elif crossingType==4:
                            # exit roundabout
                            # find out the number of the exit starting at the last
                            # trackitem with roundabout:enter                            
#                            enterRef, wayListToEnter=self.getRoundaboutEnterRef(trackWayList)
#                            if enterRef==None:
#                                print("enterRef not found")
#                            else:
#                                numExit=self.getRoundaboutExitNumber(wayListToEnter, wayId, enterRef, country)
                            if self.roundaboutExitNumber==None:
                                print("self.roundaboutExitNumber==None")
                            else:
                                numExit=self.roundaboutExitNumber+1
                                if numExit!=0:
                                    lastTrackItemRef["crossingInfo"]="roundabout:exit:%d"%(numExit)
                                    lastTrackItemRef["direction"]=41
                                    if self.roundaboutEnterItem!=None:
                                        self.roundaboutEnterItem["crossingInfo"]="roundabout:exit:%d"%(numExit)
                                        self.roundaboutEnterItem=None
                                        self.roundaboutExitNumber=None
                                        
                        elif crossingType==42:
                            # no enter oneway
                            None
                        
                        elif crossingType==5:
                            # mini-roundabout
                            lastTrackItemRef["crossingInfo"]="mini-roundabout"
                        
                        elif crossingType==7:
                            lastTrackItemRef["crossingInfo"]="motorway_link:enter"

                        elif crossingType==8:
                            lastTrackItemRef["crossingInfo"]="motorway_link:exit"
                        
               
            
            if routeEndRefId!=None and ref==routeEndRefId:
                break
        
#        if routeEndRefId!=None and routeEndRefId in refListPart:
#            print("endedge=%d %d"%(length, self.sumLength))
#        
#        if routeStartRefId!=None and routeStartRefId in refListPart:
#            print("startedge=%d %d"%(length, self.sumLength))
            
        trackItem["length"]=length
        self.sumLength=self.sumLength+length
        trackItem["sumLength"]=self.sumLength

        trackItem["refs"]=trackItemRefs
#        print(trackItem)
        trackWayList.append(trackItem)
        self.latFrom=latFrom
        self.lonFrom=lonFrom
        return length

    def printSingleEdgeForRefList(self, refListPart, edgeId, trackWayList, startPoint, endPoint):
        result=self.getEdgeEntryForEdgeId(edgeId)
        (edgeId, startRef, _, length, wayId, _, _, _, _)=result
                    
        _, country=self.getCountryOfRef(startRef)
        if country==None:
            return
        
        (wayId, tags, _, streetTypeId, name, nameRef)=self.getWayEntryForIdAndCountry(wayId, country)

        trackItem=dict()
        trackItem["type"]=streetTypeId
        trackItem["info"]=(name, nameRef)
        trackItem["wayId"]=wayId
        trackItem["edgeId"]=edgeId        
            
        trackItemRefs=list()
        
        routeStartRefId=startPoint.getRefId()
        routeEndRefId=endPoint.getRefId()
        indexStart=refListPart.index(routeStartRefId)
        indexEnd=refListPart.index(routeEndRefId)

        if indexEnd-indexStart<=1 or len(refListPart)==2:
            startLat, startLon=startPoint.getPos()
            preTrackItemRef=dict()
            preTrackItemRef["coords"]=(startLat, startLon)
            preTrackItemRef["ref"]=-1
            trackItemRefs.append(preTrackItemRef)

            endLat, endLon=endPoint.getPos()
            postTrackItemRef=dict()
            postTrackItemRef["coords"]=(endLat, endLon)
            postTrackItemRef["ref"]=-1
            trackItemRefs.append(postTrackItemRef)

            length=self.osmutils.distance(startLat, startLon, endLat, endLon)       
        else:
            # use one ref before and after
            routeEndRefId=refListPart[indexEnd-1]
            routeStartRefId=refListPart[indexStart+1]
            
            routeStartRefPassed=False

            for ref in refListPart:  
                _, country=self.getCountryOfRef(ref)
                if country==None:
                    continue
                
                resultList=self.getRefEntryForIdAndCountry2(ref, country)
                if len(resultList)==1:
                    ref, lat, lon, wayIdList, storedTags, storedNodeType=resultList[0]
                else:
                    print("printSingleEdgeForRefList: no node in DB with %d"%(ref))
                    continue

          
                if routeStartRefId!=None and routeStartRefPassed==False:
                    if ref==routeStartRefId:
                        startLat, startLon=startPoint.getPos()
                        preTrackItemRef=dict()
                        preTrackItemRef["coords"]=(startLat, startLon)
                        preTrackItemRef["ref"]=-1
                        trackItemRefs.append(preTrackItemRef)
                        length=self.osmutils.distance(lat, lon, startLat, startLon)
                        routeStartRefPassed=True
                    else:
                        continue
               
                trackItemRef=dict()
                trackItemRef["ref"]=ref
                trackItemRef["coords"]=(lat, lon)
                if storedNodeType==1:
                    # enforcement
                    trackItemRef["enforcement"]="maxspeed:%s"%(storedTags["maxspeed"])
               
                # TODO: speed_camera refs can also be "near" this ref
#                speedCameraNodes=self.getNearNodes(lat, lon, country, 1, 50.0)
#                for speedCameraRef, _, _, _ in speedCameraNodes:
#                    if speedCameraRef!=ref:
#                    trackItemRef["enforcement"]="maxspeed"

                trackItemRefs.append(trackItemRef)
                
                if routeEndRefId!=None and ref==routeEndRefId:
                    endLat, endLon=endPoint.getPos()
                    postTrackItemRef=dict()
                    postTrackItemRef["coords"]=(endLat, endLon)
                    postTrackItemRef["ref"]=-1
                    trackItemRefs.append(postTrackItemRef)
                    if ref==refListPart[0]:
                        length=self.osmutils.distance(lat, lon, endLat, endLon)
                    else:
                        length=length+self.osmutils.distance(lat, lon, endLat, endLon)
                    break         
        
            if routeEndRefId!=None and routeEndRefId in refListPart:
                print("endedge=%d %d"%(length, self.sumLength))
            
            if routeStartRefId!=None and routeStartRefId in refListPart:
                print("startedge=%d %d"%(length, self.sumLength))
            
        trackItem["length"]=length
        self.sumLength=self.sumLength+length
        trackItem["sumLength"]=self.sumLength

        trackItem["refs"]=trackItemRefs
#        print(trackItem)
        trackWayList.append(trackItem)
        return length

#    def getRoundaboutExitNumber(self, wayListToEnter, toWayId, enterRef, country):
#        crossingRefList=list()
#        exitRef=None
#        wayListToEnter.reverse()
##        exitRefFound=False
#        for fromWayId in wayListToEnter:
##            if exitRefFound==True:
##                break
#            resultList=self.getCrossingEntryFor(fromWayId, country)
#            for result in resultList:
##                if exitRefFound==True:
##                    break
#                _, _, crossingRef, nextWayIdList=result
#                for crossingWay, crossingType, _ in nextWayIdList:
#                    if crossingType==4 or crossingType==3:
#                        if not crossingRef in crossingRefList:
#                            crossingRefList.append(crossingRef)
#                    if crossingWay==toWayId:
#                        exitRef=crossingRef
##                        exitRefFound=True
##                        break
#        
#        numExit=0;
#        if exitRef==None:
#            print("exitRef not found")
#        else:
#            splittedRefs=list()
#            if not enterRef in crossingRefList:
#                print("enterRef: %d %d %d"%(fromWayId, toWayId, enterRef))
#                return 0
#            indexEnter=crossingRefList.index(enterRef)
#            splittedRefs=crossingRefList[indexEnter:]
#            splittedRefs.extend(crossingRefList[:indexEnter])
#            
#            crossingRefList=self.getRefListSubset(splittedRefs, enterRef, exitRef)
#            numExit=len(crossingRefList)-1
#        
#        return numExit
 
    def getRefListSubset(self, refs, startRef, endRef):
        if not startRef in refs and not endRef in refs:
            return list()
        
        indexStart=refs.index(startRef)
        indexEnd=refs.index(endRef)
        if indexStart>indexEnd:
            refs=refs[indexStart:]
            indexEnd=refs.index(endRef)
            subRefList=refs[:indexEnd+1]
        else:
            subRefList=refs[indexStart:indexEnd+1]
        return subRefList
    
    def getNextCrossingInfo(self, trackList):
        for trackItem in trackList:            
            crossingLength=0
            for trackItemRef in trackItem["refs"]:
                length=trackItem["length"]
                crossingLength=crossingLength+length
                edgeId=trackItem["edgeId"]
#                if "enforcement" in trackItem:
#                    enforcement=trackItem["enforcement"]
                    
                if "direction" in trackItemRef and "crossingInfo" in trackItemRef and "crossing" in trackItemRef:
                    crossingList=trackItemRef["crossing"]
                    direction=trackItemRef["direction"]
                    crossingInfo=trackItemRef["crossingInfo"]
                    for (_, crossingType, _, crossingRef) in crossingList:
                        return (direction, crossingLength, crossingInfo, crossingType, crossingRef, edgeId)
                        
        return (None, None, None, None, None, None)
    
    def getNextCrossingInfoFromPos(self, edgeId, trackList, lat, lon, usedRefId):
        refList=list()
        coordsList=list()
        firstTrackItem=trackList[0]

        for trackItemRef in firstTrackItem["refs"]:
            refList.append(trackItemRef["ref"])
            coordsList.append(trackItemRef["coords"])
           
        crossingLength=self.getRemainingDistanceOnEdge(edgeId, refList, coordsList, lat, lon, usedRefId)
        for trackItemRef in firstTrackItem["refs"]:
            if "direction" in trackItemRef and "crossingInfo" in trackItemRef and "crossing" in trackItemRef:
                crossingList=trackItemRef["crossing"]
                direction=trackItemRef["direction"]
                crossingInfo=trackItemRef["crossingInfo"]
                for (_, crossingType, _, crossingRef) in crossingList:
                    return (direction, crossingLength, crossingInfo, crossingType, crossingRef, edgeId)

        for trackItem in trackList[1:]:            
            length=trackItem["length"]
            edgeId=trackItem["edgeId"]
            crossingLength=crossingLength+length
            for trackItemRef in trackItem["refs"]:
#                print(trackItemRef)
                if "direction" in trackItemRef and "crossingInfo" in trackItemRef and "crossing" in trackItemRef:
                    crossingList=trackItemRef["crossing"]
                    direction=trackItemRef["direction"]
                    crossingInfo=trackItemRef["crossingInfo"]
                    for (_, crossingType, _, crossingRef) in crossingList:
                        return (direction, crossingLength, crossingInfo, crossingType, crossingRef, edgeId)
                        
        return (None, None, None, None, None, None)

    def getDistanceToEnd(self, edgeId, trackList, lat, lon, route, usedRefId):
        refList=list()
        coordsList=list()
        firstTrackItem=trackList[0]
        endLength=0
        sumLength=firstTrackItem["sumLength"]

        for trackItemRef in firstTrackItem["refs"]:
            refList.append(trackItemRef["ref"])
            coordsList.append(trackItemRef["coords"])
           
        distanceToEdge=self.getRemainingDistanceOnEdge(edgeId, refList, coordsList, lat, lon, usedRefId)
        if distanceToEdge!=None:
            endLength=distanceToEdge

        endLength=endLength+route.getLength()-sumLength       
        return endLength
    
    def getRemainingDistanceOnEdge(self, edgeId, refList, coordsList, lat, lon, usedRefId):
        if not usedRefId in refList:
            if refList[0]==-1:
                index=1
            if refList[-1]==-1:
                index=len(refList)-1
        else:
            index=refList.index(usedRefId)
            if index<len(refList)-1:
                index=index+1

        coordsListPart=coordsList[index:]
        distance=0
        lastLat=None
        lastLon=None
        i=0;
        for i in range(len(coordsListPart)):
            refLat, refLon=coordsListPart[i]
            if refLat==None or refLon==None:
                continue
            if lastLat!=None and lastLon!=None:
                distance=distance+int(self.osmutils.distance(refLat, refLon, lastLat, lastLon))
            else:
                # distance to first ref
                distance=int(self.osmutils.distance(lat, lon, refLat, refLon))

            lastLat=refLat
            lastLon=refLon
        return distance
                    
    def getRefListOfEdge(self, edgeId, wayId, startRef, endRef):
        _, country=self.getCountryOfRef(startRef) 
        wayId, _, refs, streetTypeId, name, nameRef=self.getWayEntryForIdAndCountry(wayId, country)
        refList=self.getRefListSubset(refs, startRef, endRef)
        return refList

    def printRoute(self, route):
        edgeList=route.getEdgeList()
        routingPointList=route.getRoutingPointList()
        
        trackWayList=list()
        allLength=0
        self.latFrom=None
        self.lonFrom=None
        self.latCross=None
        self.lonCross=None
        self.sumLength=0
        
        endPoint=routingPointList[-1]
        startPoint=routingPointList[0]
        
        startPointLat, startPointLon=startPoint.getRefPos()
        
        currentRefList=None

        if len(edgeList)==1:
            edgeId=edgeList[0]
            (edgeId, currentStartRef, currentEndRef, _, wayId, source, target, _, _, lat1, lon1, lat2, lon2)=self.getEdgeEntryForEdgeIdWithCoords(edgeId)                       
            refList=self.getRefListOfEdge(edgeId, wayId, currentStartRef, currentEndRef)

            if startPoint.getTargetOneway()!=1:
                # only one edge so we use distances on the same edge
                distanceStartRef=self.osmutils.distance(startPointLat, startPointLon, lat1, lon1)
                distanceEndRef=self.osmutils.distance(startPointLat, startPointLon, lat2, lon2)
                if distanceStartRef>distanceEndRef:
                    refList.reverse()

            # TODO if only one edge draw line correct
            length=self.printSingleEdgeForRefList(refList, edgeId, trackWayList, startPoint, endPoint)
            allLength=allLength+length

        else:
            i=0
            for edgeId in edgeList:
                (edgeId, currentStartRef, currentEndRef, _, wayId, source, target, _, _, lat1, lon1, lat2, lon2)=self.getEdgeEntryForEdgeIdWithCoords(edgeId)                       
                refList=self.getRefListOfEdge(edgeId, wayId, currentStartRef, currentEndRef)
    
                # use last ref to check how to continue the next reflist
                if currentRefList!=None:
                    if len(currentRefList)==0:
                        print("printRoute: if len(currentRefList)==0")
                    if currentRefList[-1]!=refList[0]:
                        refList.reverse()
                else:       
                    # find out the order of refs for the start
                    # we may need to reverse them if the route goes
                    # in the opposite direction   
                    if len(edgeList)>1:
                        nextEdgeId=edgeList[1]
                        (nextEdgeId, nextStartRef, nextEndRef, _, wayId, _, _, _, _)=self.getEdgeEntryForEdgeId(nextEdgeId)                       
        
                        # look how the next edge continues to find the order
                        if nextEdgeId!=edgeId:
                            if nextStartRef==currentStartRef or nextEndRef==currentStartRef:
                                refList.reverse()
#                                print("reverse refs of startEdge:%s"%refList)
    
                        else:
                            if startPoint.getTargetOneway()!=1:
                                # if we have a u-turn we use distances on the same edge
                                distanceStartRef=self.osmutils.distance(startPointLat, startPointLon, lat1, lon1)
                                distanceEndRef=self.osmutils.distance(startPointLat, startPointLon, lat2, lon2)
                                if distanceStartRef>distanceEndRef:
                                    refList.reverse()
#                                    print("reverse refs of startEdge:%s"%refList)
                    else:
                        if startPoint.getTargetOneway()!=1:
                            # only one edge so we use distances on the same edge
                            distanceStartRef=self.osmutils.distance(startPointLat, startPointLon, lat1, lon1)
                            distanceEndRef=self.osmutils.distance(startPointLat, startPointLon, lat2, lon2)
                            if distanceStartRef>distanceEndRef:
                                refList.reverse()
#                                print("reverse refs of startEdge:%s"%refList)
                if i==0:
                    length=self.printEdgeForRefList(refList, edgeId, trackWayList, startPoint, None)
                elif i==len(edgeList)-1:
                    length=self.printEdgeForRefList(refList, edgeId, trackWayList, None, endPoint)
                else:
                    length=self.printEdgeForRefList(refList, edgeId, trackWayList, None, None)
                    
                currentRefList=refList
                allLength=allLength+length
                i=i+1
                                     
        return trackWayList, allLength   

    def createEdgeTableEntries(self, country):
        self.setDBCursorForCountry(country)
        self.cursor.execute('SELECT * FROM wayTable')
        allWays=self.cursor.fetchall()

        for way in allWays:
            self.createEdgeTableEntriesForWay(way, country)

    def createEdgeTableNodeEntries(self):
        self.cursorEdge.execute('SELECT id FROM edgeTable')
        allEdges=self.cursorEdge.fetchall()
        for edgeEntryId in allEdges:                
            edgeId=edgeEntryId[0]
            edge=self.getEdgeEntryForEdgeId(edgeId)
            self.createEdgeTableNodeSameStartEnriesFor(edge)
            
            edge=self.getEdgeEntryForEdgeId(edgeId)
            self.createEdgeTableNodeSameEndEnriesFor(edge)

            edge=self.getEdgeEntryForEdgeId(edgeId)
            self.createEdgeTableNodeSourceEnriesFor(edge)

        self.cursorEdge.execute('SELECT id FROM edgeTable WHERE source==0 OR target==0')
        allEdges=self.cursorEdge.fetchall()

        for edgeEntryId in allEdges:
            edgeId=edgeEntryId[0]
            edge=self.getEdgeEntryForEdgeId(edgeId)
            edgeId, _, _, _, _, source, target, _, _=edge
                        
            if source==0:
                sourceId=self.nodeId
                self.nodeId=self.nodeId+1
                self.updateSourceOfEdge(edgeId, sourceId)
            if target==0:
                targetId=self.nodeId
                self.nodeId=self.nodeId+1
                self.updateTargetOfEdge(edgeId, targetId)
                
   
    def createEdgeTableNodeSameStartEnriesFor(self, edge):
        edgeId, startRef, _, _, _, sourceId, _, _, _=edge
                           
        resultList=self.getEdgeEntryForStartPoint(startRef, edgeId)
        if len(resultList)!=0:
            if sourceId==0:
                sourceId=self.nodeId
                self.nodeId=self.nodeId+1
    
        for result in resultList:
            edgeId1, _, _, _, _, source1, _, _, _=result
            if source1!=0:
                continue

            self.updateSourceOfEdge(edgeId, sourceId)
            self.updateSourceOfEdge(edgeId1, sourceId)

    def createEdgeTableNodeSameEndEnriesFor(self, edge):
        edgeId, _, endRef, _, _, _, targetId, _, _=edge
                           
        resultList=self.getEdgeEntryForEndPoint(endRef, edgeId)
        if len(resultList)!=0:
            if targetId==0:
                targetId=self.nodeId
                self.nodeId=self.nodeId+1
            
        for result in resultList:
            edgeId1, _, _, _, _, _, target1, _, _=result
            if target1!=0:
                continue
            
            self.updateTargetOfEdge(edgeId, targetId)
            self.updateTargetOfEdge(edgeId1, targetId)
            
    def createEdgeTableNodeSourceEnriesFor(self, edge):
        edgeId, _, endRef, _, _, _, targetId, _, _=edge
        
        resultList=self.getEdgeEntryForStartPoint(endRef, edgeId)        
        if len(resultList)!=0:
            if targetId==0:
                targetId=self.nodeId
                self.nodeId=self.nodeId+1

        for result in resultList:
            edgeId1, _, _, _, _, source1, _, _, _=result
            
            if source1==0:
                self.updateSourceOfEdge(edgeId1, targetId)
                self.updateTargetOfEdge(edgeId, targetId)
            else:
                self.updateTargetOfEdge(edgeId, source1)
    
    def createWayRestrictionsDB(self):
        # TODO: left turns should increase costs
        toAddRules=list()
        for wayRestrictionEntry in self.wayRestricitionList:
            fromWayId=int(wayRestrictionEntry["from"])
            toWayId=int(wayRestrictionEntry["to"])
            restrictionType=wayRestrictionEntry["type"]

            resultList=self.getEdgeEntryForWayId(fromWayId)
            for fromWayIdResult in resultList:
                (fromEdgeId, startRefFrom, endRefFrom, _, fromWayId, _, _, _, _)=fromWayIdResult
    
                resultList1=self.getEdgeEntryForWayId(toWayId)
                if len(resultList1)!=0:
                    for toWayIdResult in resultList1:                        
                        (toEdgeId, startRefTo, endRefTo, _, toWayId, _, _, _, _)=toWayIdResult
                                                        
                        crossingRef=None
                        if startRefTo==startRefFrom or endRefTo==startRefFrom:
                            crossingRef=startRefFrom
                        
                        if endRefTo==endRefFrom or startRefTo==endRefFrom:
                            crossingRef=endRefFrom
                                                            
                        if crossingRef==None:
                            continue
                        
                        if restrictionType[:3]=="no_":
                            if not (toEdgeId, fromEdgeId) in toAddRules:
                                toAddRules.append((toEdgeId, fromEdgeId))
                            continue
                        
                        if restrictionType[:5]=="only_":
                            resultList2=self.getEdgeEntryForStartOrEndPoint(crossingRef)

                            if len(resultList2)!=0:
                                for edge in resultList2:
                                    (otherEdgeId, _, _, _, otherWayId, _, _, _, _)=edge
                                    
                                    if otherWayId==fromWayId or otherWayId==toWayId:
                                        continue
                                    if not (otherEdgeId, fromEdgeId) in toAddRules:
                                        toAddRules.append((otherEdgeId, fromEdgeId))

        for toEdgeId, fromEdgeId in toAddRules:
            self.addToRestrictionTable(toEdgeId, str(fromEdgeId), 10000)
            
    def getStreetTypeFactor(self, streetTypeId):
        # motorway
        if streetTypeId==2:
            return 0.6
        # motorway exit
        if streetTypeId==3:
            return 0.8
        # trunk
        if streetTypeId==4:
            return 0.8
        # trunk exit
        if streetTypeId==5:
            return 1.0
        # primary
        if streetTypeId==6 or streetTypeId==7:
            return 1.2
        # secondary
        if streetTypeId==8 or streetTypeId==9:
            return 1.4
        # tertiary
        if streetTypeId==10 or streetTypeId==11:
            return 1.6
        # residential
        if streetTypeId==12:
            return 1.8
        return 2.0
        
    def getMaxspeed(self, tags, streetTypeId):
        maxspeedDefault=50
        maxspeed=0
        if "source:maxspeed" in tags:
            if "urban" in tags["source:maxspeed"]:
                maxspeed=50
            elif "motorway" in tags["source:maxspeed"]:
                maxspeed=130
            elif "rural" in tags["source:maxspeed"]:
                maxspeed=100

        if "zone:traffic" in tags:
            if "urban" in tags["zone:traffic"]:
                maxspeed=50
            elif "rural" in tags["zone:traffic"]:
                maxspeed=100
            elif "DE:30" or "DE:zone:30" in tags["zone:traffic"]:
                maxspeed=30
        
        if "zone:maxspeed" in tags:
            if "urban" in tags["zone:maxspeed"]:
                maxspeed=50
            elif "rural" in tags["zone:maxspeed"]:
                maxspeed=100
            elif "DE:30" or "DE:zone:30" in tags["zone:maxspeed"]:
                maxspeed=30
        
        # no other setting till now
        if maxspeed==0:
            if "maxspeed" in tags:
                if "urban" in tags["maxspeed"]:
                    maxspeed=50
                elif "motorway" in tags["maxspeed"]:
                    maxspeed=130
                elif "rural" in tags["maxspeed"]:
                    maxspeed=100
                elif "walk" in tags["maxspeed"]:
                    maxspeed=10
                else:
                    maxspeedString=tags["maxspeed"]
        
                    if ";" in maxspeedString:
                        try:
                            maxspeed=int(maxspeedString.split(";")[0])
                        except ValueError:
                            maxspeed=int(maxspeedString.split(";")[1])
                    elif "km/h" in maxspeedString:
                        try:
                            maxspeed=int(maxspeedString.split("km/h")[0])
                        except ValueError:
                            maxspeed=0
                    else:
                        if maxspeedString=="city_limit":
                            maxspeed=50
                        elif maxspeedString=="undefined" or maxspeedString=="no" or maxspeedString=="sign" or maxspeedString=="unknown" or maxspeedString=="none" or maxspeedString=="variable" or maxspeedString=="signals" or maxspeedString=="implicit" or maxspeedString=="fixme" or maxspeedString=="<unterschiedlich>":
                            maxspeed=0
                        elif maxspeedString=="DE:30" or maxspeedString=="DE:zone:30" or maxspeedString=="DE:zone30":
                            maxspeed=30        
                        else:
                            try:
                                maxspeed=int(maxspeedString)
                            except ValueError:
                                maxspeed=0
        
        # final fallback if no other value found
        if maxspeed==0:
            print(tags)
            maxspeed=self.getDefaultMaxspeedForStreetType(streetTypeId)
            
        return maxspeed
    
    def getDefaultMaxspeedForStreetType(self, streetTypeId):
        if streetTypeId==12:
            maxspeed=50
        elif streetTypeId==3 or streetTypeId==5 or streetTypeId==7 or streetTypeId==9 or streetTypeId==11:
            maxspeed=80
        elif streetTypeId==4:
            maxspeed=100
        elif streetTypeId==2:
            maxspeed=130
        else:
            maxspeed=50
        return maxspeed
    
    def getAccessFactor(self, tags):
        if "vehicle" in tags:
            if tags["vehicle"]=="destination":
                return 1000
            if tags["vehicle"]=="permissive":
                return 1000

        if "motorcar" in tags:
            if tags["motorcar"]=="destination":
                return 1000
            if tags["motorcar"]=="permissive":
                return 1000
                
        if "motor_vehicle" in tags:
            if tags["motor_vehicle"]=="destination":
                return 1000
            if tags["motor_vehicle"]=="permissive":
                return 1000
            
        if "access" in tags:
            if tags["access"]=="destination":
                return 1000
            if tags["access"]=="permissive":
                return 1000

        return 1
    
    def getCrossingsFactor(self, crossingType):
#        if crossingType==0:
#            return 1.1
#        elif crossingType==1 or crossingType==6:
#            # traffic lights or stop
#            return 1.2
        return 1
    
    def getCostsOfWay(self, wayId, tags, refs, distance, crossingFactor, streetTypeId, oneway, roundabout, maxspeed):
            
        if roundabout==1:
            oneway=1
#        elif refs[0]==refs[-1]:
#            oneway=1
        
        accessFactor=self.getAccessFactor(tags)  
        streetTypeFactor=self.getStreetTypeFactor(streetTypeId)
#        maxspeed=self.getMaxspeed(tags, streetTypeId)
                            
        try:
#            cost=(distance * streetTypeFactor * accessFactor * crossingFactor) / (maxspeed/3.6)
            cost=(distance * streetTypeFactor * accessFactor * crossingFactor)
        except ZeroDivisionError:
            cost=distance
            print(tags)
        except TypeError:
            cost=distance
            print(tags)
            
        if oneway:
            reverseCost=100000
        else:
            reverseCost=cost
        
        return cost, reverseCost

    def createEdgeTableEntriesForWay(self, way, country):        
        wayId, tags, refs, streetTypeId, name, nameRef, oneway, roundabout, maxspeed=self.wayFromDB3(way)
        resultList=self.getCrossingEntryFor(wayId, country)
        
        nextWayDict=dict()
        for result in resultList:
            _, wayId, refId, nextWayIdList=result
            nextWayDict[refId]=nextWayIdList
        
        crossingFactor=1
        
        doneRefs=list()
        for ref in refs:                  
            if ref in nextWayDict:                                                                        
                nextWayIdList=nextWayDict[ref]
                for _, crossingType, _ in nextWayIdList:
                    cf=self.getCrossingsFactor(crossingType)
                    if cf>crossingFactor:
                        crossingFactor=cf
                        
                doneRefs.append(ref)
        
        refNodeList=list()
        distance=0
        lastLat=None
        lastLon=None
        
        for ref in refs:
            storedRef, countryRef=self.getCountryOfRef(ref)
            if storedRef!=None and countryRef!=None:
                lat, lon=self.getCoordsWithRefAndCountry(ref, countryRef)
                
                if lat!=None and lon!=None:
                    if lastLat!=None and lastLon!=None:
                        distance=distance+int(self.osmutils.distance(lat, lon, lastLat, lastLon))
                    
                    lastLat=lat
                    lastLon=lon

            if ref in doneRefs:
                if len(refNodeList)!=0:
                        
                    refNodeList.append(ref)
                    startRef=refNodeList[0]
                    endRef=refNodeList[-1]                 

                    lat1=None
                    lon1=None
                    lat2=None
                    lon2=None
                    storedRef, countryStart=self.getCountryOfRef(startRef)
                    if storedRef!=None and countryStart!=None:
                        lat1, lon1=self.getCoordsWithRefAndCountry(startRef, countryStart)

                    storedRef, countryEnd=self.getCountryOfRef(endRef)
                    if storedRef!=None and countryEnd!=None:
                        lat2, lon2=self.getCoordsWithRefAndCountry(endRef, countryEnd)
                    
                    if lat1!=None and lon1!=None and lat2!=None and lon2!=None:
                        cost, reverseCost=self.getCostsOfWay(wayId, tags, refs, distance, crossingFactor, streetTypeId, oneway, roundabout, maxspeed)                                         
                        self.addToEdgeTable(startRef, endRef, distance, wayId, cost, reverseCost, lat1, lon1, lat2, lon2)
#                    else:
#                        print("createEdgeTableEntriesForWay: skipping wayId %s from starRef %d to endRef %d"%(wayId, startRef, endRef))

                    refNodeList=list()
                    distance=0
           
            refNodeList.append(ref)
        
        # handle last portion
        if not ref in doneRefs:
            if len(refNodeList)!=0:
                startRef=refNodeList[0]
                endRef=refNodeList[-1]
                
                lat1=None
                lon1=None
                lat2=None
                lon2=None
                storedRef, countryStart=self.getCountryOfRef(startRef)
                if storedRef!=None and countryStart!=None:
                    lat1, lon1=self.getCoordsWithRefAndCountry(startRef, countryStart)
                    
                storedRef, countryEnd=self.getCountryOfRef(endRef)
                if storedRef!=None and countryEnd!=None:
                    lat2, lon2=self.getCoordsWithRefAndCountry(endRef, countryEnd)

                if lat1!=None and lon1!=None and lat2!=None and lon2!=None:
                    cost, reverseCost=self.getCostsOfWay(wayId, tags, refs, distance, crossingFactor, streetTypeId, oneway, roundabout, maxspeed)                    
                    self.addToEdgeTable(startRef, endRef, distance, wayId, cost, reverseCost, lat1, lon1, lat2, lon2)
#                else:
#                    print("createEdgeTableEntriesForWay: skipping wayId %s from starRef %d to endRef %d"%(wayId, startRef, endRef))

    def createCrossingEntries(self, country):
        self.setDBCursorForCountry(country)
        self.cursor.execute('SELECT * FROM wayTable')
        allWays=self.cursor.fetchall()
        for way in allWays:
            wayid, tags, refs, streetTypeId, name, nameRef, oneway, roundabout=self.wayFromDB2(way)    
             
            crossingInfo=None   
                        
            for ref in refs:  
                # TODO: traffic signals can not only be on crossings
                # e.g. node 455985572
                majorCrossingType=0
                nextWays=self.findWayWithRefInAllWays(ref, wayid)  
                if len(nextWays)!=0:
                    resultList=self.getRefEntryForIdAndCountry2(ref, country)
                    if len(resultList)==1:
                        _, _, _, _, nodeTags, nodeType=resultList[0]
                        if nodeTags!=None:
                            if nodeType==2:
                                # motorway_junction
                                majorCrossingType=2
                                highwayExitRef=None
                                highwayExitName=None
                                if "ref" in nodeTags:
                                    highwayExitRef=nodeTags["ref"]
                                if "name" in nodeTags:
                                    highwayExitName=nodeTags["name"]
                                crossingInfo="%s:%s"%(highwayExitName, highwayExitRef)
                            elif nodeType==3:
                                # traffic_signals
                                majorCrossingType=1
                            elif nodeType==4:
                                # mini-roundabout
                                majorCrossingType=5
                            elif nodeType==5:
                                # stop
                                majorCrossingType=6
#                            if "highway" in nodeTags:
#                                if nodeTags["highway"]=="traffic_signals":
#                                    majorCrossingType=1
#                                elif nodeTags["highway"]=="motorway_junction":
#                                    majorCrossingType=2
#                                    highwayExitRef=None
#                                    highwayExitName=None
#                                    if "ref" in nodeTags:
#                                        highwayExitRef=nodeTags["ref"]
#                                    if "name" in nodeTags:
#                                        highwayExitName=nodeTags["name"]
#                                    crossingInfo="%s:%s"%(highwayExitName, highwayExitRef)
##                                    print(crossingInfo)
#                                elif nodeTags["highway"]=="mini_roundabout":
#                                    majorCrossingType=5
#                                elif nodeTags["highway"]=="stop":
#                                    majorCrossingType=6
                                   
                                
                    wayList=list()   
                    for (wayid2, tags2, refs2, streetTypeId2, name2, nameRef2, oneway2, roundabout2) in nextWays: 
                        minorCrossingType=0
                        crossingType=0
                          
                        if majorCrossingType==0:
                            if roundabout2==1 and roundabout==0:
                                # roundabout enter
                                minorCrossingType=3
                            elif roundabout==1 and roundabout2==0:
                                if oneway2==1 and ref!=refs2[0]:
                                    # no exit roundabout
                                    minorCrossingType=42
                                else:
                                    # roundabout exit
                                    minorCrossingType=4
                                
                            if minorCrossingType!=3 and minorCrossingType!=4:
                                if streetTypeId!=3 and streetTypeId2==3:
                                    # motorway_link enter
                                    minorCrossingType=7              
                                elif streetTypeId==3 and streetTypeId2!=3:
                                    # motorway_link exit
                                    minorCrossingType=8  
                                elif streetTypeId==3 and streetTypeId2==3:
                                    # motorway_link to motorway_link
                                    minorCrossingType=9
                            
                            if minorCrossingType!=7 and minorCrossingType!=8 and minorCrossingType!=9 and minorCrossingType!=3 and minorCrossingType!=4 and minorCrossingType!=42:
                                if oneway2==1 and roundabout2==0 and wayid2!=wayid:
                                    if ref in refs2[:-1]:
                                        # oneway start or in the middle
                                        minorCrossingType=10
                                    else:
                                        # oneway end - not allowed to enter
                                        minorCrossingType=42                        
                                             
                        if majorCrossingType!=0:
                            crossingType=majorCrossingType
                            if majorCrossingType==2:
                                if streetTypeId2==2:
                                    # not the exit from the motorway
                                    crossingType=-1
#                                    print((wayid2, crossingType, crossingInfo))
#                                else:
#                                    print((wayid2, crossingType, crossingInfo))
                        elif minorCrossingType!=0:
                            crossingType=minorCrossingType
                            if minorCrossingType==10:
                                if oneway==1 and oneway2==1:
                                    crossingType=-1
                            elif minorCrossingType==9:
                                # TODO: 
#                                if wayid==wayid2:
#                                    crossingType=-1
                                if oneway==1 and oneway2==1:
                                    if refs[-1]==refs2[0] and len(nextWays)==2:
                                        crossingType=-1
#                                    elif ref!=refs2[0]:
#                                        crossingType=42
                            elif streetTypeId==2 and streetTypeId2==2:
                                if nameRef==nameRef2:
                                    crossingType=-1
                        else:
                            if wayid2==wayid:     
                                crossingType=-1                  
                            else:
                                if name!=None and name2!=None:  
                                    if name==name2:
                                        crossingType=-1
                                
                        wayList.append((wayid2, crossingType, crossingInfo))
                    
                    if len(wayList)!=0:
                        self.addToCrossingsTable(wayid, ref, wayList)
                
    def parse(self, country):
        p = XMLParser(nodes_callback=self.parse_nodes, 
                  ways_callback=self.parse_ways, 
                  relations_callback=self.parse_relations,
                  coords_callback=self.parse_coords)
        p.parse(self.getOSMFile(country))

    def getOSMFile(self, country):
        return self.osmList[country]["osmFile"]
    
    def getDataDir(self):
        return os.path.join(os.environ['HOME'], "workspaces", "pydev", "car-dash", "data")
    
    def getDBFile(self, country):
        basename=os.path.basename(self.getOSMFile(country))
        basenameParts=basename.split(".")
        basename=basenameParts[0]
        file=os.path.basename(basename)+".db"
        return os.path.join(self.getDataDir(), file)

    def getEdgeDBFile(self):
        file="edge.db"
        return os.path.join(self.getDataDir(), file)
    
    def getAdressDBFile(self):
        file="adress.db"
        return os.path.join(self.getDataDir(), file)
    
    def getGlobalCountryDBFile(self):
        file="country.db"
        return os.path.join(self.getDataDir(), file)

    def getCoordsDBFile(self):
        file="coords.db"
        return os.path.join(self.getDataDir(), file)

    def deleteCoordsDBFile(self):
        if os.path.exists(self.getCoordsDBFile()):
            os.remove(self.getCoordsDBFile())
            
    def dbExists(self, country):
        return os.path.exists(self.getDBFile(country))

    def edgeDBExists(self):
        return os.path.exists(self.getEdgeDBFile())
        
    def globalCountryDBExists(self):
        return os.path.exists(self.getGlobalCountryDBFile())

    def adressDBExists(self):
        return os.path.exists(self.getAdressDBFile())

    def initGraph(self):            
#        if self.dWrapper==None:
##            self.dWrapper=DijkstraWrapperPygraph(self.cursorEdge)
#            self.dWrapper=DijkstraWrapperIgraph(self.cursorEdge, self.getDataDir())
#
#        if not self.dWrapper.isGraphLoaded():
#            print("init graph")
#            self.dWrapper.initGraph()
#            print("init graph done")
            
        if self.dWrapperTrsp==None:
            self.dWrapperTrsp=TrspWrapper(self.getDataDir())

    def initDB(self):
        print(self.getDataDir())
        createEdgeDB=not self.edgeDBExists()
        if createEdgeDB:
            self.openEdgeDB()
            self.createEdgeTables()
        else:
            self.openEdgeDB()
#            print(self.getLenOfEdgeTable())
        
        createAdressDB=not self.adressDBExists()
        if createAdressDB:
            self.openAdressDB()
            self.createAdressTable()
        else:
            self.openAdressDB()
            self.addressId=self.getLenOfAddressTable()
        
        createGlobalCountryDB=not self.globalCountryDBExists()
        if createGlobalCountryDB:
            self.openGlobalCountryDB()
            self.createGlobalCountryTables()
        else:
            self.openGlobalCountryDB()
            self.wayCount=self.getLenOfCountryWayTable()

        countryList=list()
        for country in self.osmList.keys():
            self.country=country
            self.debugCountry=country
            
            createCountryDB=not self.dbExists(country)
            if createCountryDB:
                self.openCountryDB(country)
                self.createCountryTables()
                countryList.append(country)
            else:
                self.openCountryDB(country)

        for country in countryList:
            self.country=country
            self.debugCountry=country
            self.setDBCursorForCountry(country)
            self.openCoordsDB()
            
            print(self.osmList[country])
            self.initCountryData()
            print("start parsing")
            self.parse(country)
            print("end parsing")
                          
            self.createRefTableIndexesPost(country)       
   
            self.commitAdressDB()
            self.commitCountryDB(country)
            self.commitGlobalCountryDB()
            self.closeCoordsDB()
            
#        self.createGeomColumns(countryList)
        
        for country in countryList:
            self.country=country
            self.debugCountry=country
            self.setDBCursorForCountry(country)
            print(self.osmList[country])
            
            print("create crossings")
            self.createCrossingEntries(country)
            print("end create crossings")

            print("create edges")
            self.createEdgeTableEntries(country)
            print("end create edges")   
                                    
            self.commitCountryDB(country)
            self.commitEdgeDB()

        
        if createEdgeDB:            
            self.createEdgeTableIndexesPost()
            print("create edge nodes")
            self.createEdgeTableNodeEntries()
            print("end create edge nodes")
            
            print("create way restrictions")
            self.createWayRestrictionsDB()              
            print("end create way restrictions")

            self.createGeomForEdgeTable()
            self.createGeomDataForEdgeTable()
            self.commitEdgeDB()    
                           
        self.initGraph()   
        self.closeAllDB()

    def initBoarders(self):
        self.bu=OSMBoarderUtils(self.getDataDir())
        self.bu.initData()
        
    def countryNameOfPoint(self, lat, lon):
        country=self.bu.countryNameOfPoint(lat, lon)
        return country
    
    def countryNameOfPointDeep(self, lat, lon):
        country=self.bu.countryNameOfPoint(lat, lon)
        if country==None:
            # TODO: HACK if the point is exactly on the border:(
            country=self.bu.countryNameOfPoint(lat+0.0001, lon+0.0001)
        return country
    
    def getOSMDataInfo(self):
        osmDataList=dict()
        osmData=dict()
        osmData["country"]="Austria"
        osmData["osmFile"]='/home/maxl/Downloads/geofabrik/austria.osm.bz2'
#        osmData["osmFile"]='/home/maxl/Downloads/cloudmade/salzburg.osm'
        osmData["poly"]="austria.poly"
        osmData["polyCountry"]="Europe / Western Europe / Austria"
        osmData["countryCode"]="AT"
        osmDataList[0]=osmData
        
#        osmData=dict()
#        osmData["country"]="switzerland"
#        osmData["osmFile"]='/home/maxl/Downloads/switzerland.osm.bz2'
#        osmData["poly"]="switzerland.poly"
#        osmData["polyCountry"]="Europe / Western Europe / Switzerland"
#        osmData["countryCode"]="CH"
#        osmDataList[1]=osmData
    
        osmData=dict()
        osmData["country"]="Germany"
#        osmData["osmFile"]='/home/maxl/Downloads/cloudmade/bayern-south.osm'
        osmData["osmFile"]='/home/maxl/Downloads/geofabrik/bayern.osm.bz2'
#        osmData["osmFile"]='/home/maxl/Downloads/germany.osm.bz2'
        osmData["poly"]="germany.poly"
        osmData["polyCountry"]="Europe / Western Europe / Germany"
        osmData["countryCode"]="DE"
        osmDataList[2]=osmData
        
#        osmData=dict()
#        osmData["country"]="liechtenstein"
#        osmData["osmFile"]='/home/maxl/Downloads/liechtenstein.osm.bz2'
#        osmData["poly"]="liechtenstein.poly"
#        osmData["polyCountry"]="Europe / Western Europe / Liechtenstein"
#        osmData["countryCode"]="LI"
#        osmDataList[3]=osmData

        return osmDataList

    def test(self):
#        self.cursorCountry.execute('SELECT * FROM refCountryTable WHERE id==1444662052')
#        allentries=self.cursorCountry.fetchall()
#        for x in allentries:
#            print(x)
            
#        self.setDBCursorForCountry(0)
#        self.cursor.execute('SELECT * FROM refTable WHERE type==1')
#        allentries=self.cursor.fetchall()
#        for x in allentries:
#            print(self.refFromDB2(x))
#          
#        self.setDBCursorForCountry(0)
#        self.cursor.execute('SELECT * FROM refTable WHERE type==2')
#        allentries=self.cursor.fetchall()
#        for x in allentries:
#            print(self.refFromDB2(x))
#
#        self.setDBCursorForCountry(0)
#        self.cursor.execute('SELECT * FROM refTable WHERE type==3')
#        allentries=self.cursor.fetchall()
#        for x in allentries:
#            print(self.refFromDB2(x))
#
#        self.setDBCursorForCountry(0)
#        self.cursor.execute('SELECT * FROM refTable WHERE type==4')
#        allentries=self.cursor.fetchall()
#        for x in allentries:
#            print(self.refFromDB2(x))
#
#        self.setDBCursorForCountry(0)
#        self.cursor.execute('SELECT * FROM refTable WHERE type==5')
#        allentries=self.cursor.fetchall()
#        for x in allentries:
#            print(self.refFromDB2(x))

#        self.setDBCursorForCountry(0)
#        self.cursor.execute('SELECT * FROM refTable WHERE type==6')
#        allentries=self.cursor.fetchall()
#        for x in allentries:
#            print(self.refFromDB2(x))


#        self.cursor.execute('SELECT * FROM wayTable WHERE wayId==135928507 OR wayId==25337315 OR wayId==37517449')
#        allentries=self.cursor.fetchall()
#        for x in allentries:
#            print(x)
#            wayId, tags, refs, streetTypeId, name, nameRef=self.wayFromDB(x)
#            print(refs)
        
#        self.cursor.execute('SELECT * from crossingTable WHERE wayId==27206920')
#        allentries=self.cursor.fetchall()
#        for x in allentries:
#            print(self.crossingFromDB(x))

        self.cursorEdge.execute('SELECT id, source, target, length AS cost, CASE WHEN reverseCost IS cost THEN length ELSE reverseCost END FROM edgeTable')
        allentries=self.cursorEdge.fetchall()
        for x in allentries:
            print(x)

    def testDBConistency(self):
        print("test refCountryTable")
        self.cursorCountry.execute('SELECT * FROM refCountryTable')
        allentries=self.cursorCountry.fetchall()
        for x in allentries:
            refId=x[0]
            if x[1]==None:
                print("ref %d in refCountryTable with country==None"%(refId))

        print("test wayCountryTable")
        self.cursorCountry.execute('SELECT * FROM wayCountryTable')
        allentries=self.cursorCountry.fetchall()
        for x in allentries:
            wayId=x[1]
            if x[2]==None:
                print("way %d in wayCountryTable with country==None"%(wayId))

#        for country in self.osmList.keys():
#            self.country=country
#            self.setDBCursorForCountry(country)
#            self.cursor.execute('SELECT * FROM refTable')
#            allentries=self.cursor.fetchall()
#            for x in allentries:
#                (refId, lat, lon, wayIdList, tags)=self.refFromDB(x)
                
        print("test wayTable")
        for country in self.osmList.keys():
            self.country=country
            print(country)
            self.setDBCursorForCountry(country)
            self.cursor.execute('SELECT * FROM wayTable')
            allentries=self.cursor.fetchall()
            for x in allentries:
                wayId, tags, refs, streetTypeId, name, nameRef=self.wayFromDB(x)
                for ref in refs:
                    storedRef, storedCountry=self.getCountryOfRef(ref)
                    if storedRef==None:
                        print("way %d ref %d not in refCountryTable"%(wayId, ref))
                    elif storedCountry==None:
                        print("way %d ref %d country==None in refCountryTable"%(wayId, ref))
                                    
                resultList=self.getEdgeEntryForWayId(wayId)
                if len(resultList)==0:
                    print("way %d not in edge DB"%(wayId))
                
                resultList=self.getCountrysOfWay(wayId)
                if len(resultList)==0:
                    print("way %d not in wayCountryTable"%(wayId))
                                    
    def recreateCrossings(self):
        for country in self.osmList.keys():
            self.country=country
            self.debugCountry=country
            print(self.osmList[country])

            self.clearCrosssingsTable(country)
            
            print("recreate crossings")
            self.createCrossingEntries(country)
            print("end recreate crossings")
                        
            self.commitCountryDB(country)

    def recreateEdges(self):
        self.clearEdgeTable()
        for country in self.osmList.keys():
            self.country=country
            self.debugCountry=country
            print(self.osmList[country])

            print("recreate edges")
            self.createEdgeTableEntries(country)
            print("end recreate edges")   
                        
        print("recreate edge nodes")
        self.createEdgeTableNodeEntries()
        print("end recreate edge nodes")

        self.commitEdgeDB()
                 
    def recreateEdgeNodes(self):
        self.clearSourceAndTargetOfEdges()
                        
        print("recreate edge nodes")
        self.createEdgeTableNodeEntries()
        print("end recreate edge nodes")

        self.commitEdgeDB()  
             
    def testAddress(self):
        start=time.time()
        self.cursorAdress.execute('SELECT * FROM addressTable WHERE country==0 AND city=="Salzburg" AND streetName=="Münchner Bundesstraße"')
        allentries=self.cursorAdress.fetchall()
        for x in allentries:
            print(self.addressFromDB(x))
        print("%f"%(time.time()-start))
          
        start=time.time()
        resultList=self.getWayEntryForStreetNameAndCountry("Münchner Bundesstraße", 0)
        for result in resultList:
            print(result)
        print("%f"%(time.time()-start))

        start=time.time()
        resultList=self.getAllWayEntryForCountry(0)
        for result in resultList:
            print(result)
        print("%f"%(time.time()-start))
            
    def recreateCostsForEdges(self):
        print("recreate costs")
        self.cursorEdge.execute('SELECT * FROM edgeTable')
        allentries=self.cursorEdge.fetchall()
        for x in allentries:
            edgeId, startRef, endRef, length, wayId, source, target, cost, reverseCost=self.edgeFromDB(x)
            resultList=self.getCountrysOfWay(wayId)
            for result in resultList:
                _, _, country=result
                self.getWayEntryForIdAndCountry(wayId, country)
                wayId, tags, refs, streetTypeId, name, nameRef, oneway, roundabout, maxspeed=self.getWayEntryForIdAndCountry3(wayId, country)
                if wayId==None:
                    continue
                cost, reverseCost=self.getCostsOfWay(wayId, tags, refs, length, 1, streetTypeId, oneway, roundabout, maxspeed)
                self.updateCostsOfEdge(edgeId, cost, reverseCost)

        print("end recreate costs")
              
#    def createGeomColumns(self, countryList):
#        for country in countryList:
#            self.country=country
#            self.debugCountry=country
#            print(self.osmList[country])
#
#            self.createGeomForRefTable(country)
#            self.createGeomDataForRefTable(country)
#            self.commitCountryDB(country)
            
    def createAllRefTableIndexesPost(self):
        for country in self.osmList.keys():
            self.country=country
            self.debugCountry=country
            print(self.osmList[country])

            self.createRefTableIndexesPost(country)
            self.commitCountryDB(country)
            
#    def testRefTableGeom(self, country):
#        self.setDBCursorForCountry(country)
#        self.cursor.execute('SELECT AsText(geom) FROM refTable')
##        self.cursor.execute('SELECT HEX(geom) FROM refTable')
#        allentries=self.cursor.fetchall()
#        for x in allentries:
#            print(x)

    def testEdgeTableGeom(self):
        self.cursorEdge.execute('SELECT AsText(geom) FROM edgeTable')
        allentries=self.cursorEdge.fetchall()
        for x in allentries:
            print(x)
                            
#    def testGeomColumns(self, lat, lon, distance):
#        self.setDBCursorForCountry(0)
#        self.cursor.execute('SELECT * FROM refTable WHERE PtDistWithin("geom", MakePoint(%f, %f, 4326), %f, 0)==1'%(lon, lat, distance))
#        allentries=self.cursor.fetchall()
#        for x in allentries:
#            print(self.refFromDB(x))
        
    def testEdgeGeomWithBBox(self):
        ymin=47.820928
        xmin=13.016525
        ymax=47.822
        xmax=13.019
        
        self.cursorEdge.execute('SELECT * FROM edgeTable WHERE MbrWithin("geom", BuildMbr(%f, %f, %f, %f, 4326))==1'%(xmin, ymin, xmax, ymax))
        allentries=self.cursorEdge.fetchall()
        print(len(allentries))
        for x in allentries:
            print(self.edgeFromDB(x))

    def testEdgeGeomWithPoint(self):
        y=47.820928
        x=13.016525
        
        self.cursorEdge.execute('SELECT * FROM edgeTable WHERE MbrContains("geom", MakePoint(%f, %f, 4326))==1'%(x, y))
        allentries=self.cursorEdge.fetchall()
        print(len(allentries))
        for x in allentries:
            print(self.edgeFromDB(x))  
                  
    def testEdgeGeomWithCircle(self):
        y=47.820928
        x=13.016525
        radius=0.0001
        
        self.cursorEdge.execute('SELECT * FROM edgeTable WHERE MbrOverlaps("geom", BuildCircleMbr(%f, %f, %f, 4326))==1'%(x, y, radius))
        allentries=self.cursorEdge.fetchall()
        print(len(allentries))
        for x in allentries:
            print(self.edgeFromDB(x))
               
    def loadTestRoutes(self):    
        config=Config("osmtestroutes.cfg")
                
        section="route"
        routeList=list()
        if config.hasSection(section):
            for name, value in config.items(section):
                if name[:5]=="route":
                    route=OSMRoute()
                    route.readFromConfig(value)
                    routeList.append(route)   
        return routeList
    
    def testRoutes(self):
        routeList=self.loadTestRoutes()
        for route in routeList:
            print(route)
            route.resolveRoutingPoints(self)
            route.calcRoute(self)
            if route.getEdgeList()!=None:
                print(route.getEdgeList())
            else:
                print("routing failed")
            
    def getCoordsOfEdge(self, edgeId, country):
        (edgeId, startRef, endRef, _, wayId, _, _, _, _)=self.getEdgeEntryForEdgeId(edgeId)
        wayId, tags, refs, streetTypeId, name, nameRef, oneway, roundabout, maxspeed=self.getWayEntryForIdAndCountry3(wayId, country)
                    
        refListPart=self.getRefListSubset(refs, startRef, endRef)
        coords=list()
        for ref in refListPart:
            _, country=self.getCountryOfRef(ref)
            if country==None:
                continue

            resultList=self.getRefEntryForIdAndCountry2(ref, country)
            if len(resultList)==1:
                ref, lat, lon, _, _, _=resultList[0]
                coords.append((lat, lon))
                        
        return coords

def main(argv):    
    p = OSMParserData()
    
    p.initDB()
    
    p.openAllDB()
    
#    lat=47.820928
#    lon=13.016525
#    p.testEdgeTableGeom()
#    p.testGeomColumns(lat, lon, 100.0)
#    p.testEdgeGeomWithBBox()
#    p.testEdgeGeomWithPoint()
#    p.testEdgeGeomWithCircle()
#    
#    p.testCountryRefTable()
#    p.testCountryWayTable()
#    p.testStreetTable2()
#    p.testEdgeTable()
#    p.testRefTable(0)
#    p.testRefTable(1)
       

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
#    p.testAddress()
#    p.testRoutes()
#    p.testWayTable(0)
#    p.recreateCostsForEdges()
    p.closeAllDB()


if __name__ == "__main__":
    main(sys.argv)  
    

