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
import env
#from pygraph-routing.dijkstrapygraph import DijkstraWrapperPygraph
#from igraph.dijkstraigraph import DijkstraWrapperIgraph

from config import Config
from osmparser.osmboarderutils import OSMBoarderUtils
from trsp.trspwrapper import TrspWrapper
from osmparser.osmpoly import OSMPoly

HEADING_CALC_LENGTH=20.0
DEFAULT_SEARCH_MARGIN=0.0003

class Constants():
    STREET_TYPE_SERVICE=0
    STREET_TYPE_TERTIARY_LINK=1
    STREET_TYPE_SECONDARY_LINK=2
    STREET_TYPE_PRIMARY_LINK=3
    STREET_TYPE_TRUNK_LINK=4
    STREET_TYPE_MOTORWAY_LINK=5
    STREET_TYPE_ROAD=6
    STREET_TYPE_UNCLASSIFIED=7
    STREET_TYPE_LIVING_STREET=8
    STREET_TYPE_RESIDENTIAL=9
    STREET_TYPE_TERTIARY=10
    STREET_TYPE_SECONDARY=11
    STREET_TYPE_PRIMARY=12
    STREET_TYPE_TRUNK=13
    STREET_TYPE_MOTORWAY=14
    
#    STREET_TYPE_TERTIARY_LINK=0
#    STREET_TYPE_SECONDARY_LINK=1
#    STREET_TYPE_PRIMARY_LINK=2
#    STREET_TYPE_TRUNK_LINK=3
#    STREET_TYPE_MOTORWAY_LINK=4
#    STREET_TYPE_SERVICE=5
#    STREET_TYPE_ROAD=6
#    STREET_TYPE_UNCLASSIFIED=7
#    STREET_TYPE_LIVING_STREET=8
#    STREET_TYPE_RESIDENTIAL=9
#    STREET_TYPE_TERTIARY=10
#    STREET_TYPE_SECONDARY=11
#    STREET_TYPE_PRIMARY=12
#    STREET_TYPE_TRUNK=13
#    STREET_TYPE_MOTORWAY=14

    CROSSING_TYPE_NONE=-1
    CROSSING_TYPE_NORMAL=0
    CROSSING_TYPE_MOTORWAY_EXIT=2
    CROSSING_TYPE_ROUNDABOUT_ENTER=3
    CROSSING_TYPE_ROUNDABOUT_EXIT=4
    CROSSING_TYPE_LINK_START=7
    CROSSING_TYPE_LINK_END=8
    CROSSING_TYPE_LINK_LINK=9
    CROSSING_TYPE_FORBIDDEN=42
    CROSSING_TYPE_START=98
    CROSSING_TYPE_END=99
    
    POI_TYPE_ADDRESS=6
    POI_TYPE_ENFORCEMENT=1
    POI_TYPE_MOTORWAY_JUNCTION=2

class OSMRoute():
    def __init__(self, name="", routingPointList=None):
        self.name=name
        self.routingPointList=routingPointList
        self.routeInfo=None
        self.routeFinished=False
        
    def isRouteFinished(self):
        return self.routeFinished
    
    def getName(self):
        return self.name
    
    def getRoutingPointList(self):
        return self.routingPointList
    
    def calcRoute(self, osmParserData):
        if self.routeInfo==None:
            print(self.routingPointList)
            self.routeInfo=osmParserData.calcRoute(self)
            self.routeFinished=False
            
    def changeRouteFromPoint(self, currentPoint, osmParserData):        
        self.routingPointList[0]=currentPoint
        self.routeInfo=None

    def getRouteInfo(self):
        return self.routeInfo

    def getRouteInfoLength(self):
        return len(self.routeInfo)
    
    def getStartPoint(self, index):
        if self.routeInfo!=None:
            if len(self.routeInfo)>index:
                return self.routeInfo[index]["startPoint"]
        return None 

    def getTargetPoint(self, index):
        if self.routeInfo!=None:
            if len(self.routeInfo)>index:
                return self.routeInfo[index]["targetPoint"]
        return None 
    
    def getEdgeList(self, index):
        if self.routeInfo!=None:
            if len(self.routeInfo)>index:
                return self.routeInfo[index]["edgeList"]
        return None   
      
    def getLength(self, index):
        if self.routeInfo!=None:
            if len(self.routeInfo)>index:
                return self.routeInfo[index]["length"]
        return 0
    
    def getAllLength(self):
        if self.routeInfo!=None:
            i=0
            length=0
            while i<len(self.routeInfo):
                length=length+self.routeInfo[i]["length"]
                i=i+1
            return length
        return 0
        
    def getTrackList(self, index):
        if self.routeInfo!=None:
            if len(self.routeInfo)>index:
                return self.routeInfo[index]["trackList"]
        return None
    
    def printRoute(self, osmParserData):
        if self.routeInfo!=None:
            osmParserData.printRoute(self)
            
    def resolveRoutingPoints(self, osmParserData):
        for point in self.routingPointList:
            if point.getSource()==0:
                point.resolveFromPos(osmParserData)

    def routingPointValid(self):
        for point in self.routingPointList:
            if point.getSource()==0:
                return False
        return True
    
    def targetPointReached(self, index):
        if self.routeInfo!=None:
            if len(self.routeInfo)>index:
                routeInfoEntry=self.routeInfo[index]
                startPoint=routeInfoEntry["startPoint"]
                self.routingPointList.remove(startPoint)
                if index==len(self.routeInfo)-1:
                    self.routeFinished=True
        
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
        self.posOnEdge=0.0
    
    def resolveFromPos(self, osmParserData):
        edgeId, _=osmParserData.getEdgeIdOnPos(self.lat, self.lon, DEFAULT_SEARCH_MARGIN, 30.0)
        if edgeId==None:
            print("resolveFromPos not found for %f %f"%(self.lat, self.lon))
            return

        (edgeId, startRef, endRef, length, wayId, source, target, _, _, _, coords)=osmParserData.getEdgeEntryForEdgeIdWithCoords(edgeId)
        country=osmParserData.getCountryOfPos(self.lat, self.lon)
        (_, _, refs, _, _, _, _, _)=osmParserData.getWayEntryForId2(wayId)

        refList=osmParserData.getRefListSubset(refs, startRef, endRef)
        ref, point=osmParserData.getClosestRefOnEdge(self.lat, self.lon, refList, coords, 30.0)

        self.lat=point[0]
        self.lon=point[1]
        self.edgeId=edgeId
        self.target=target
        self.source=source
        self.usedRefId=ref
        self.wayId=wayId
        self.country=country
        
        self.posOnEdge=osmParserData.getPosOnOnEdge(self.lat, self.lon, coords, length)

    def getPosOnEdge(self):
        return self.posOnEdge
    
    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.lat==other.lat and self.lon==other.lon and self.type==other.type

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
    
    def getEdgeId(self):
        return self.edgeId
    
    def getWayId(self):
        return self.wayId
    
    def getRefId(self):
        return self.usedRefId
    
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
        self.connectionEdge=None
        self.cursorEdge=None
        self.connectionArea=None
        self.cursorArea=None
        self.connectionAdress=None
        self.cursorAdress=None
        self.connectionCoords=None
        self.cursorCoords=None
        self.cursorGlobal=None
        self.connectionGlobal=None
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
        self.wayCount=0
        self.wayRestricitionList=list()
        self.roundaboutExitNumber=None
        self.roundaboutEnterItem=None
        self.currentSearchBBox=None
        self.currentPossibleEdgeList=list()
        self.expectedNextEdgeId=None
        self.expectedHeading=None
        self.crosingWithoutExpected=False
        self.checkExpectedEdge=False
        self.approachingRef=None
        self.getPosTrigger=0
        self.crossingId=0
        self.firstWay=False
        self.firstRelation=False
        self.firstNode=False
#        self.wayCache=None
        self.skipNodes=False
        self.skipWays=False
        self.skipRelations=False

    def createEdgeTables(self):
        self.createEdgeTable(True)
        self.createRestrictionTable()

    def createAdressTable(self):
        self.createAddressTable()
        
    def openEdgeDB(self):
        self.connectionEdge=sqlite3.connect(self.getEdgeDBFile())
        self.cursorEdge=self.connectionEdge.cursor()
        self.connectionEdge.enable_load_extension(True)
        self.cursorEdge.execute("SELECT load_extension('libspatialite.so')")

    def openAreaDB(self):
        self.connectionArea=sqlite3.connect(self.getAreaDBFile())
        self.cursorArea=self.connectionArea.cursor()
        self.connectionArea.enable_load_extension(True)
        self.cursorArea.execute("SELECT load_extension('libspatialite.so')")

    def openGlobalDB(self):
        self.connectionGlobal=sqlite3.connect(self.getGlobalDBFile())
        self.cursorGlobal=self.connectionGlobal.cursor()
        self.connectionGlobal.enable_load_extension(True)
        self.cursorGlobal.execute("SELECT load_extension('libspatialite.so')")
        
    def openAdressDB(self):
        self.connectionAdress=sqlite3.connect(self.getAdressDBFile())
        self.cursorAdress=self.connectionAdress.cursor()

    def openCoordsDB(self):
        self.connectionCoords=sqlite3.connect(self.getCoordsDBFile())
        self.cursorCoords=self.connectionCoords.cursor()
        
    def createCoordsDBTables(self):
        self.createCoordsTable()
        self.createWayRefTable()
        self.creatRefWayTable()

    def commitAdressDB(self):
        self.connectionAdress.commit()
        
    def commitEdgeDB(self):
        self.connectionEdge.commit()

    def commitCoordsDB(self):
        self.connectionCoords.commit()

    def commitGlobalDB(self):
        self.connectionGlobal.commit()

    def commitAreaDB(self):
        self.connectionArea.commit()
        
    def closeEdgeDB(self):
        if self.connectionEdge!=None:
            self.connectionEdge.commit()        
            self.cursorEdge.close()
            self.connectionEdge=None     
            self.cursorEdge=None

    def closeAreaDB(self):
        if self.connectionArea!=None:
            self.connectionArea.commit()        
            self.cursorArea.close()
            self.connectionArea=None     
            self.cursorArea=None
           
    def closeGlobalDB(self):
        if self.connectionGlobal!=None:
            self.connectionGlobal.commit()        
            self.cursorGlobal.close()
            self.connectionGlobal=None     
            self.cursorGlobal=None

    def closeAdressDB(self):
        if self.connectionAdress!=None:
            self.connectionAdress.commit()
            self.cursorAdress.close()
            self.connectionAdress=None
            self.cursorAdress=None
                
    def closeCoordsDB(self, delete):
        if self.connectionCoords!=None:
            self.connectionCoords.commit()
            self.cursorCoords.close()
            self.connectionCoords=None
            self.cursorCoords=None   
            if delete==True: 
                self.deleteCoordsDBFile()        

    def openAllDB(self):
        self.openGlobalDB()
        self.openEdgeDB()
        self.openAreaDB()
        self.openAdressDB()
        
    def closeAllDB(self):
        self.closeGlobalDB()
        self.closeEdgeDB()
        self.closeAreaDB()
        self.closeAdressDB()
      
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

    def createCoordsTable(self):
        self.cursorCoords.execute('CREATE TABLE coordsTable (refId INTEGER PRIMARY KEY, lat REAL, lon REAL)')

    def createWayRefTable(self):
        self.cursorCoords.execute('CREATE TABLE wayRefTable (wayId INTEGER PRIMARY KEY, refList BLOB)')

    def creatRefWayTable(self):
        self.cursorCoords.execute('CREATE TABLE refWayTable (refId INTEGER PRIMARY KEY, wayIdList BLOB)')

    def addToCoordsTable(self, ref, lat, lon):
        self.cursorCoords.execute('INSERT OR IGNORE INTO coordsTable VALUES( ?, ?, ?)', (ref, lat, lon))
    
    def addToWayRefTable(self, wayId, refs):
        self.cursorCoords.execute('INSERT OR IGNORE INTO wayRefTable VALUES( ?, ?)', (wayId, pickle.dumps(refs)))
        
    def addToRefWayTable(self, refid, wayId):
        storedRef, wayIdList=self.getRefWayEntryForId(refid)
        if storedRef!=None:                            
            if wayIdList==None:
                wayIdList=list()
            if not wayId in wayIdList:
                wayIdList.append(wayId)
            self.cursorCoords.execute('REPLACE INTO refWayTable VALUES( ?, ?)', (refid, pickle.dumps(wayIdList)))
            return
            
        wayIdList=list()
        wayIdList.append(wayId)
        self.cursorCoords.execute('INSERT INTO refWayTable VALUES( ?, ?)', (refid, pickle.dumps(wayIdList)))

    def getCoordsEntry(self, ref):
        self.cursorCoords.execute('SELECT * FROM coordsTable WHERE refId=%d'%(ref))
        allentries=self.cursorCoords.fetchall()
        if len(allentries)==1:
            return(allentries[0][0], allentries[0][1], allentries[0][2])
        return None, None, None

    def getWayRefEntry(self, wayId):
        self.cursorCoords.execute('SELECT * FROM wayRefTable WHERE wayId=%d'%(wayId))
        allentries=self.cursorCoords.fetchall()
        if len(allentries)==1:
            return(allentries[0][0], pickle.loads(allentries[0][1]))
        return None, None    
    
    def getRefWayEntryForId(self, ref):
        self.cursorCoords.execute('SELECT * FROM refWayTable WHERE refId=%d'%(ref))
        allentries=self.cursorCoords.fetchall()
        if len(allentries)==1:
            return(allentries[0][0], pickle.loads(allentries[0][1]))
        return None, None    
        
    def createGlobalDBTables(self):
        self.cursorGlobal.execute("SELECT InitSpatialMetaData()")
        
        self.cursorGlobal.execute('CREATE TABLE refTable (refId INTEGER PRIMARY KEY, tags BLOB, type BLOB)')
        self.cursorGlobal.execute("CREATE INDEX type_idx ON refTable (type)")
        self.cursorGlobal.execute("SELECT AddGeometryColumn('refTable', 'geom', 4326, 'POINT', 2)")
        
        self.cursorGlobal.execute('CREATE TABLE wayTable (wayId INTEGER PRIMARY KEY, tags BLOB, refs BLOB, streetInfo INTEGER, name TEXT, ref TEXT, maxspeed INTEGER, poiList BLOB, streetTypeId INTEGER)')
        self.cursorGlobal.execute("CREATE INDEX streetTypeId_idx ON wayTable (streetTypeId)")
        self.cursorGlobal.execute("CREATE INDEX name_idx ON wayTable (name)")
        self.cursorGlobal.execute("SELECT AddGeometryColumn('wayTable', 'geom', 4326, 'LINESTRING', 2)")

        self.cursorGlobal.execute('CREATE TABLE crossingTable (id INTEGER PRIMARY KEY, wayId INTEGER, refId INTEGER, nextWayIdList BLOB)')
        self.cursorGlobal.execute("CREATE INDEX wayId_idx ON crossingTable (wayId)")
        self.cursorGlobal.execute("CREATE INDEX refId_idx ON crossingTable (refId)")

    def createAddressTable(self):
        self.cursorAdress.execute('CREATE TABLE addressTable (id INTEGER PRIMARY KEY, refId INTEGER, country INTEGER, city TEXT, postCode INTEGER, streetName TEXT, houseNumber TEXT, lat REAL, lon REAL)')
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
    
    def createEdgeTable(self, initSpatia):
        self.cursorEdge.execute('CREATE TABLE edgeTable (id INTEGER PRIMARY KEY, startRef INTEGER, endRef INTEGER, length INTEGER, wayId INTEGER, source INTEGER, target INTEGER, cost REAL, reverseCost REAL, streetInfo INTEGER)')
        self.cursorEdge.execute("CREATE INDEX startRef_idx ON edgeTable (startRef)")
        self.cursorEdge.execute("CREATE INDEX endRef_idx ON edgeTable (endRef)")
        self.cursorEdge.execute("CREATE INDEX wayId_idx ON edgeTable (wayId)")
        self.cursorEdge.execute("CREATE INDEX source_idx ON edgeTable (source)")
        self.cursorEdge.execute("CREATE INDEX target_idx ON edgeTable (target)")
        
        if initSpatia==True:
            self.cursorEdge.execute("SELECT InitSpatialMetaData()")
        
        self.cursorEdge.execute("SELECT AddGeometryColumn('edgeTable', 'geom', 4326, 'LINESTRING', 2)")

    def createAreaTable(self):
        self.cursorArea.execute("SELECT InitSpatialMetaData()")
        self.cursorArea.execute('CREATE TABLE areaTable (id INTEGER PRIMARY KEY, tags BLOB)')
        self.cursorArea.execute("SELECT AddGeometryColumn('areaTable', 'geom', 4326, 'MULTIPOLYGON', 2)")

    def createRestrictionTable(self):
        self.cursorEdge.execute('CREATE TABLE restrictionTable (id INTEGER PRIMARY KEY, target INTEGER, viaPath TEXT, toCost REAL)')
        self.cursorEdge.execute("CREATE INDEX restrictionTarget_idx ON restrictionTable (target)")
        
    def addToRestrictionTable(self, target, viaPath, toCost):
        self.cursorEdge.execute('INSERT INTO restrictionTable VALUES( ?, ?, ?, ?)', (self.restrictionId, target, viaPath, toCost))
        self.restrictionId=self.restrictionId+1

    def getRestrictionEntryForTargetEdge(self, toEdgeId):
        self.cursorEdge.execute('SELECT * FROM restrictionTable WHERE target=%d'%(toEdgeId))
        resultList=list()
        allentries=self.cursorEdge.fetchall()
        for x in allentries:
            resultList.append(self.restrictionFromDB(x))
        return resultList
    
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
    
    def getCountryOfPos(self, lat, lon):
        polyCountry=self.countryNameOfPointDeep(lat, lon)
        return self.getCountryForPolyCountry(polyCountry)

    # nodeType of 0 will NOT be stored
    def addToRefTable(self, refid, lat, lon, tags, nodeType):   
        # make complete point
        pointString="'POINT("
        pointString=pointString+"%f %f"%(lon, lat)
        pointString=pointString+")'"

        storedRefId, lat, lon, _, storedNodeTypeList=self.getRefEntryForId(refid)
        tagsString=None
        if tags!=None:
            tagsString=pickle.dumps(tags)
            
        if storedRefId!=None:            
            # add to list if !=0
            if storedNodeTypeList!=None:
                if nodeType!=0:
                    storedNodeTypeList.append(nodeType)
            else:
                if nodeType!=0:
                    storedNodeTypeList=list()
                    storedNodeTypeList.append(nodeType)
            
            nodeTypeListStr=None
            if storedNodeTypeList!=None:
                nodeTypeListStr=pickle.dumps(storedNodeTypeList)
                
            self.cursorGlobal.execute('REPLACE INTO refTable VALUES( ?, ?, ?, PointFromText(%s, 4326))'%(pointString), (refid, tagsString, nodeTypeListStr))
            return
            
        storedNodeTypeList=None
        if nodeType!=0:
            storedNodeTypeList=list()
            storedNodeTypeList.append(nodeType)
        
        nodeTypeListStr=None
        if storedNodeTypeList!=None:
            nodeTypeListStr=pickle.dumps(storedNodeTypeList)

        self.cursorGlobal.execute('INSERT INTO refTable VALUES( ?, ?, ?, PointFromText(%s, 4326))'%(pointString), (refid, tagsString, nodeTypeListStr))
        
    def updateWayTableEntryPOIList(self, wayId, poiList):
        wayId, tags, refs, streetInfo, name, nameRef, maxspeed, _, coords=self.getWayEntryForIdWithCoords(wayId)
        if wayId!=None:
            streetTypeId, oneway, roundabout=self.decodeStreetInfo(streetInfo)
            lineString=self.createLineStringFromCoords(coords)
            self.cursorGlobal.execute('REPLACE INTO wayTable VALUES( ?, ?, ?, ?, ?, ?, ?, ?, ?, LineFromText(%s, 4326))'%(lineString), (wayId, self.encodeWayTags(tags), pickle.dumps(refs), streetInfo, name, nameRef, maxspeed, pickle.dumps(poiList), streetTypeId))
        
    def updateRefTableEntry(self, refId, tags, nodeType):
        storedRefId, lat, lon, storedTags, storedNodeTypeList=self.getRefEntryForId(refId)
        if storedRefId!=None:
            tagsChanged=False
            if tags!=None:
                if storedTags!=None:
                    if tags!=storedTags:
                        tagsChanged=True
                        # merge tags
                        for key, value in tags.items():
                            storedTags[key]=value
                else:
                    storedTags=tags
                    tagsChanged=True
                
            nodeTypeListChanged=False
            if nodeType!=None:
                # add to list if !=0
                if storedNodeTypeList!=None:
                    if nodeType!=0:
                        if not nodeType in storedNodeTypeList:
                            nodeTypeListChanged=True
                            storedNodeTypeList.append(nodeType)
                else:
                    if nodeType!=0:
                        nodeTypeListChanged=True
                        storedNodeTypeList=list()
                        storedNodeTypeList.append(nodeType)
            
            if nodeTypeListChanged==True or tagsChanged==True:
                nodeTypeListStr=None
                if storedNodeTypeList!=None:
                    nodeTypeListStr=pickle.dumps(storedNodeTypeList)
                
                tagsString=None
                if storedTags!=None:
                    tagsString=pickle.dumps(storedTags)
                
                # make complete point
                pointString="'POINT("
                pointString=pointString+"%f %f"%(lon, lat)
                pointString=pointString+")'"
    
                self.cursorGlobal.execute('REPLACE INTO refTable VALUES( ?, ?, ?, PointFromText(%s, 4326))'%(pointString), (refId, tagsString, nodeTypeListStr))

    def addToWayTable(self, wayid, tags, refs, streetTypeId, name, nameRef, oneway, roundabout, maxspeed, tunnel, bridge, coords):
        streetInfo=self.encodeStreetInfo2(streetTypeId, oneway, roundabout, tunnel, bridge)
        lineString=self.createLineStringFromCoords(coords)

        self.cursorGlobal.execute('INSERT OR IGNORE INTO wayTable VALUES( ?, ?, ?, ?, ?, ?, ?, ?, ?, LineFromText(%s, 4326))'%(lineString), (wayid, self.encodeWayTags(tags), pickle.dumps(refs), streetInfo, name, nameRef, maxspeed, None, streetTypeId))
     
    def addToCrossingsTable(self, wayid, refId, nextWaysList):
        self.cursorGlobal.execute('INSERT INTO crossingTable VALUES( ?, ?, ?, ?)', (self.crossingId, wayid, refId, pickle.dumps(nextWaysList)))
        self.crossingId=self.crossingId+1

    def addToEdgeTable(self, startRef, endRef, length, wayId, cost, reverseCost, streetInfo, coords):
        resultList=self.getEdgeEntryForStartAndEndPointAndWayId(startRef, endRef, wayId)
        if len(resultList)==0:
            lineString=self.createLineStringFromCoords(coords)
            
            self.cursorEdge.execute('INSERT INTO edgeTable VALUES( ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, LineFromText(%s, 4326))'%(lineString), (self.edgeId, startRef, endRef, length, wayId, 0, 0, cost, reverseCost, streetInfo))
            self.edgeId=self.edgeId+1
        
    def addToAreaTable(self, osmId, tags, polyString):
        self.cursorArea.execute('INSERT INTO areaTable VALUES( ?, ?, MultiPolygonFromText(%s, 4326))'%(polyString), (osmId, pickle.dumps(tags)))
    
    def clearEdgeTable(self):
        print("DiscardGeometryColumn")
        self.cursorEdge.execute('SELECT DiscardGeometryColumn("edgeTable", "geom")')
        print("DROP edge table")
        self.cursorEdge.execute('DROP TABLE edgeTable')
        self.edgeId=1
        print("CREATE edge table")
        self.createEdgeTable(False)
    
    def createSpatialIndexForEdgeTable(self):
        self.cursorEdge.execute('SELECT CreateSpatialIndex("edgeTable", "geom")')

    def createSpatialIndexForAreaTable(self):
        self.cursorArea.execute('SELECT CreateSpatialIndex("areaTable", "geom")')

    def createSpatialIndexForGlobalTables(self):
        self.cursorGlobal.execute('SELECT CreateSpatialIndex("refTable", "geom")')
        self.cursorGlobal.execute('SELECT CreateSpatialIndex("wayTable", "geom")')

    def clearCrosssingsTable(self):
        self.cursorGlobal.execute('DROP table crossingTable')
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
        self.cursorEdge.execute('SELECT id, startRef, endRef, length, wayId, source, target, cost, reverseCost, streetInfo, AsText(geom) FROM edgeTable where id=%d'%(edgeId))
        allentries=self.cursorEdge.fetchall()
        if len(allentries)==1:
            edge=self.edgeFromDBWithCoords(allentries[0])
            return edge
        print("no edge with %d"%(edgeId))
        return (None, None, None, None, None, None, None, None, None, None, None)
        
    
    def getEdgeEntryForStartPoint(self, startRef, edgeId):
        if edgeId!=None:
            self.cursorEdge.execute('SELECT * FROM edgeTable where startRef=%d AND id!=%d'%(startRef, edgeId))
        else:
            self.cursorEdge.execute('SELECT * FROM edgeTable where startRef=%d'%(startRef))
            
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

    def getEdgeEntryForStartPointAndWayId(self, startRef, wayId):
        self.cursorEdge.execute('SELECT * FROM edgeTable where startRef=%d AND wayId=%d'%(startRef, wayId))
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
    
    def getDifferentEdgeEntryForStartOrEndPoint(self, ref, edgeId):
        self.cursorEdge.execute('SELECT * FROM edgeTable where id!=%d AND (startRef=%d OR endRef=%d)'%(edgeId, ref, ref))
        resultList=list()
        allentries=self.cursorEdge.fetchall()
        for result in allentries:
            edge=self.edgeFromDB(result)
            resultList.append(edge)
        return resultList

    def getDifferentEdgeEntryForStartOrEndPointWithCoords(self, ref, edgeId):
        self.cursorEdge.execute('SELECT id, startRef, endRef, length, wayId, source, target, cost, reverseCost, streetInfo, AsText(geom) FROM edgeTable where id!=%d AND (startRef=%d OR endRef=%d)'%(edgeId, ref, ref))
        resultList=list()
        allentries=self.cursorEdge.fetchall()
        for result in allentries:
            edge=self.edgeFromDBWithCoords(result)
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
    
    def getRefEntryForId(self, refId):
        self.cursorGlobal.execute('SELECT refId, tags, type, AsText(geom) FROM refTable where refId=%d'%(refId))
        allentries=self.cursorGlobal.fetchall()
        if len(allentries)==1:
            return self.refFromDB(allentries[0])

        return None, None, None, None, None
    
    def getWayEntryForId(self, wayId):
        self.cursorGlobal.execute('SELECT * FROM wayTable where wayId=%d'%(wayId))
        allentries=self.cursorGlobal.fetchall()
        if len(allentries)==1:
            return self.wayFromDB(allentries[0])
        
        return (None, None, None, None, None, None)

    def getWayEntryForId2(self, wayId):
        self.cursorGlobal.execute('SELECT * FROM wayTable where wayId=%d'%(wayId))
        allentries=self.cursorGlobal.fetchall()
        if len(allentries)==1:
            return self.wayFromDB2(allentries[0])
        
        return (None, None, None, None, None, None, None, None)
    
    def getTagsForWayEntry(self, wayId):
        self.cursorGlobal.execute('SELECT tags FROM wayTable where wayId=%d'%(wayId))
        allentries=self.cursorGlobal.fetchall()
        if len(allentries)==1:
            return self.decodeWayTags(allentries[0][0])
        
        return None

    def getRefsForWayEntry(self, wayId):
        self.cursorGlobal.execute('SELECT refs FROM wayTable where wayId=%d'%(wayId))
        allentries=self.cursorGlobal.fetchall()
        if len(allentries)==1:
            return pickle.loads(allentries[0][0])
        
        return None
    
    def getWayEntryForId3(self, wayId):
        self.cursorGlobal.execute('SELECT * FROM wayTable where wayId=%d'%(wayId))
        allentries=self.cursorGlobal.fetchall()
        if len(allentries)==1:
            return self.wayFromDB3(allentries[0])
        
        return (None, None, None, None, None, None, None, None, None)

    def getWayEntryForId4(self, wayId):
        self.cursorGlobal.execute('SELECT * FROM wayTable where wayId=%d'%(wayId))
        allentries=self.cursorGlobal.fetchall()
        if len(allentries)==1:
            return self.wayFromDB4(allentries[0])
        
        return (None, None, None, None, None, None, None, None, None, None)

    def getWayEntryForId5(self, wayId):
        self.cursorGlobal.execute('SELECT * FROM wayTable where wayId=%d'%(wayId))
        allentries=self.cursorGlobal.fetchall()
        if len(allentries)==1:
            return self.wayFromDB5(allentries[0])
        
        return (None, None, None, None, None, None, None, None)

    def getWayEntryForIdWithCoords(self, wayId):
        self.cursorGlobal.execute('SELECT wayId, tags, refs, streetInfo, name, ref, maxspeed, poiList, AsText(geom) FROM wayTable where wayId=%d'%(wayId))
        allentries=self.cursorGlobal.fetchall()
        if len(allentries)==1:
            return self.wayFromDBWithCoords(allentries[0])
        
        return (None, None, None, None, None, None, None, None, None)
    
    def getWayEntryForStreetName(self, streetName):
        self.cursorGlobal.execute('SELECT wayId, tags, refs, streetInfo, name, ref, maxspeed, poiList, AsText(geom) FROM wayTable WHERE name="%s"'%(streetName))
        allentries=self.cursorGlobal.fetchall()
        resultList=list()
        for x in allentries:
            resultList.append(self.wayFromDBWithCoords(x))
        return resultList
    
    def getCrossingEntryFor(self, wayid):
        self.cursorGlobal.execute('SELECT * FROM crossingTable where wayId=%d'%(wayid))      
        resultList=list()
        allentries=self.cursorGlobal.fetchall()
        for result in allentries:
            crossing=self.crossingFromDB(result)
            resultList.append(crossing)
            
        return resultList
    
    def getCrossingEntryForRefId(self, wayid, refId):
        self.cursorGlobal.execute('SELECT * FROM crossingTable where wayId=%d AND refId=%d'%(wayid, refId))  
        resultList=list()
        allentries=self.cursorGlobal.fetchall()
        for result in allentries:
            crossing=self.crossingFromDB(result)
            resultList.append(crossing)
            
        return resultList
    
    def testRefTable(self):
        self.cursorGlobal.execute('SELECT refId, tags, type, AsText(geom) FROM refTable')
        allentries=self.cursorGlobal.fetchall()
        for x in allentries:
            refId, lat, lon, tags, nodeTypelist=self.refFromDB(x)
            print("ref: " + str(refId) + "  lat: " + str(lat) + "  lon: " + str(lon) + " tags:"+str(tags) + " nodeTypes:"+str(nodeTypelist))

    def getEdgeIdOnPos(self, lat, lon, margin, maxDistance):  
        resultList=self.getEdgesInBboxWithGeom(lat, lon, margin)  
        usedEdgeId=None
        usedWayId=None
        minDistance=maxDistance
        
        for edge in resultList:
            edgeId, _, _, _, wayId, _, _, _, _, _, coords=edge

            lat1, lon1=coords[0]
            for lat2, lon2 in coords[1:]:
                onLine, distance, point=self.isMinimalDistanceOnLineBetweenPoints(lat, lon, lat1, lon1, lat2, lon2, maxDistance)
                if onLine==True:
                    if distance<minDistance:
                        minDistance=distance
                        usedEdgeId=edgeId
                        usedWayId=wayId
                    
                lat1=lat2
                lon1=lon2
                     
        return usedEdgeId, usedWayId
    
    def getEdgeOnPos(self, lat, lon, margin, maxDistance):  
        resultList=self.getEdgesInBboxWithGeom(lat, lon, margin)  
        usedEdge=None
        minDistance=maxDistance
        
        for edge in resultList:
            edgeId, _, _, _, wayId, _, _, _, _, _, coords=edge

            lat1, lon1=coords[0]
            for lat2, lon2 in coords[1:]:
                onLine, distance, point=self.isMinimalDistanceOnLineBetweenPoints(lat, lon, lat1, lon1, lat2, lon2, maxDistance)
                if onLine==True:
                    if distance<minDistance:
                        minDistance=distance
                        usedEdge=edge
                    
                lat1=lat2
                lon1=lon2
                     
        return usedEdge

    def getCurrentSearchBBox(self):
        return self.currentSearchBBox
    
    def getCurrentSearchEdgeList(self):
        return self.currentPossibleEdgeList
    
    def getExpectedNextEdge(self):
        return self.expectedNextEdgeId
    
    def testWayTable(self):
        self.cursorGlobal.execute('SELECT * FROM wayTable')
        allentries=self.cursorGlobal.fetchall()
        for x in allentries:
            wayId, tags, refs, streetTypeId, name, nameRef, oneway, roundabout, maxspeed=self.wayFromDB3(x)
            print( "way: " + str(wayId) + " streetType:"+str(streetTypeId)+ " name:" +str(name) + " ref:"+str(nameRef)+" tags: " + str(tags) + "  refs: " + str(refs) + " oneway:"+str(oneway)+ " roundabout:"+str(roundabout) + " maxspeed:"+str(maxspeed))

    def testCrossingTable(self):
        self.cursorGlobal.execute('SELECT * FROM crossingTable')
        allentries=self.cursorGlobal.fetchall()
        for x in allentries:
            crossingEntryId, wayid, refId, wayIdList=self.crossingFromDB(x)
            print( "id: "+ str(crossingEntryId) + " wayid: " + str(wayid) +  " refId: "+ str(refId) + " wayIdList: " + str(wayIdList))
        
    def testEdgeTable(self):
        self.cursorEdge.execute('SELECT id, startRef, endRef, length, wayId, source, target, cost, reverseCost, AsText(geom) FROM edgeTable')
        allentries=self.cursorEdge.fetchall()
        for x in allentries:
            edgeId, startRef, endRef, length, wayId, source, target, cost, reverseCost, streetInfo, coords=self.edgeFromDBWithCoords(x)
            print( "edgeId: "+str(edgeId) +" startRef: " + str(startRef)+" endRef:"+str(endRef)+ " length:"+str(length)+ " wayId:"+str(wayId) +" source:"+str(source)+" target:"+str(target) + " cost:"+str(cost)+ " reverseCost:"+str(reverseCost)+ "streetInfo:" + str(streetInfo) + " coords:"+str(coords))

    def testAreaTable(self):
        self.cursorArea.execute('SELECT id, tags, endRef, AsText(geom) FROM edgeTable')
        allentries=self.cursorArea.fetchall()
        for x in allentries:
            osmId, tags, coords=self.areaFromDB(x)
            print("id: "+str(osmId)+" tags: "+str(tags)+" coords: "+str(coords))

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

    def wayFromDB4(self, x):
        wayId=x[0]
        refs=pickle.loads(x[2])
        tags=self.decodeWayTags(x[1])
        streetInfo=x[3]
        streetTypeId, oneway, roundabout=self.decodeStreetInfo(streetInfo)
        name=x[4]
        nameRef=x[5]
        maxspeed=x[6]
        poiList=None
        if x[7]!=None:
            poiList=pickle.loads(x[7])
        return (wayId, tags, refs, streetTypeId, name, nameRef, oneway, roundabout, maxspeed, poiList)

    def wayFromDB5(self, x):
        wayId=x[0]
        refs=pickle.loads(x[2])
        tags=self.decodeWayTags(x[1])
        streetInfo=x[3]
        name=x[4]
        nameRef=x[5]
        maxspeed=x[6]
        poiList=None
        if x[7]!=None:
            poiList=pickle.loads(x[7])
        return (wayId, tags, refs, streetInfo, name, nameRef, maxspeed, poiList)
 
    def wayFromDBWithCoords(self, x):
        wayId=x[0]
        refs=pickle.loads(x[2])
        tags=self.decodeWayTags(x[1])
        streetInfo=x[3]
        name=x[4]
        nameRef=x[5]
        maxspeed=x[6]
        poiList=None
        if x[7]!=None:
            poiList=pickle.loads(x[7])    
        if len(x)==10:    
            coordsStr=x[9]
        else:
            coordsStr=x[8]
        coords=self.createCoordsFromLineString(coordsStr)
        
        return (wayId, tags, refs, streetInfo, name, nameRef, maxspeed, poiList, coords)   
    
    def refFromDB(self, x):
        refId=x[0]
        
        tags=None
        if x[1]!=None:
            tags=pickle.loads(x[1])
        
        nodeTypeList=None
        if x[2]!=None:
            nodeTypeList=pickle.loads(x[2])
            
        pointStr=x[3]
        pointStr=pointStr[6:-1]
        coordsPairs=pointStr.split(" ")
        lon=float(coordsPairs[0].lstrip().rstrip())
        lat=float(coordsPairs[1].lstrip().rstrip())

        return (refId, lat, lon, tags, nodeTypeList)
    
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
        streetInfo=x[9]
        coordsStr=x[10]
        coords=self.createCoordsFromLineString(coordsStr)
        return (edgeId, startRef, endRef, length, wayId, source, target, cost, reverseCost, streetInfo, coords)
            
    def areaFromDB(self, x):
        osmId=x[0]
        tags=pickle.loads(x[1])  
        coordsStr=x[2]
        coords=list()
        coordsStr=coordsStr[8:-1]
        coordsPairs=coordsStr.split(",")
        for coordPair in coordsPairs:
            coordPair=coordPair.lstrip().rstrip()
            lon, lat=coordPair.split(" ")
            coords.append((float(lat), float(lon)))
        return (osmId, tags, coords)
    
    def isUsableNode(self):
        return ["motorway_junction", "traffic_signals", "mini_roundabout", "stop", "speed_camera"]
    
    def getNodeTypeId(self, nodeTag):
        # 0 is a way ref
        if nodeTag=="speed_camera":
            return Constants.POI_TYPE_ENFORCEMENT
        if nodeTag=="motorway_junction":
            return Constants.POI_TYPE_MOTORWAY_JUNCTION
        # 6 is address
        return -1
    
    def parse_nodes(self, node):
        if self.skipNodes==True:
            return
        
        if self.firstNode==False:
            self.firstNode=True
            print("Parsing nodes...")

        for ref, tags, coords in node:
            # <tag k="highway" v="motorway_junction"/>
            lat=float(coords[1])
            lon=float(coords[0])
            if "highway" in tags:
                if tags["highway"] in self.isUsableNode():
                    nodeType=self.getNodeTypeId(tags["highway"])
                    if nodeType!=-1:
#                        refCountry=self.getCountryOfPos(lat, lon)
#                        if refCountry!=None:
                        self.addToRefTable(ref, lat, lon, tags, nodeType)
                            
            if "addr:street" in tags:
                self.addToRefTable(ref, lat, lon, tags, Constants.POI_TYPE_ADDRESS)
                refCountry=self.getCountryOfPos(lat, lon)
                if refCountry!=None:
                    self.parseFullAddress(tags, ref, lat, lon, refCountry)

    def parse_coords(self, coord):
        if self.skipNodes==True:
            return
        
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
        if streetType=="living_street":
            return True
        return False
    
    def decodeStreetInfo(self, streetInfo):
        oneway=(streetInfo&63)>>4
        roundabout=(streetInfo&127)>>6
        streetTypeId=(streetInfo&15)
        return streetTypeId, oneway, roundabout
    
#    def encodeStreetInfo(self, streetTypeId, oneway, roundabout):
#        streetInfo=streetTypeId+(oneway<<4)+(roundabout<<6)
#        return streetInfo
    
    def decodeStreetInfo2(self, streetInfo):
        oneway=(streetInfo&63)>>4
        roundabout=(streetInfo&127)>>6
        tunnel=(streetInfo&255)>>7
        bridge=(streetInfo&511)>>8
        streetTypeId=(streetInfo&15)
        return streetTypeId, oneway, roundabout, tunnel, bridge
    
    def encodeStreetInfo2(self, streetTypeId, oneway, roundabout, tunnel, bridge):
        streetInfo=streetTypeId+(oneway<<4)+(roundabout<<6)+(tunnel<<7)+(bridge<<8)
        return streetInfo
    
    def isValidOnewayEnter(self, oneway, ref, startRef, endRef):
        # in the middle of a oneway
        if ref!=startRef and ref!=endRef:
            return True
        
        if oneway==1:
            if ref==startRef:
                return True
        elif oneway==2:
            if ref==endRef:
                return True
        return False
    
    def isValidWay2WayCrossing(self, refs, refs2):
        return (refs[-1]==refs2[0] 
                or refs[0]==refs2[-1] 
                or refs[0]==refs2[0] 
                or refs[-1]==refs2[-1])

    def getStreetTypeId(self, streetType):
        if streetType=="road":
            return Constants.STREET_TYPE_ROAD
        if streetType=="unclassified":
            return Constants.STREET_TYPE_UNCLASSIFIED
        if streetType=="motorway":
            return Constants.STREET_TYPE_MOTORWAY
        if streetType=="motorway_link":
            return Constants.STREET_TYPE_MOTORWAY_LINK
        if streetType=="trunk":
            return Constants.STREET_TYPE_TRUNK
        if streetType=="trunk_link":
            return Constants.STREET_TYPE_TRUNK_LINK
        if streetType=="primary":
            return Constants.STREET_TYPE_PRIMARY
        if streetType=="primary_link":
            return Constants.STREET_TYPE_PRIMARY_LINK
        if streetType=="secondary":
            return Constants.STREET_TYPE_SECONDARY
        if streetType=="secondary_link":
            return Constants.STREET_TYPE_SECONDARY_LINK
        if streetType=="tertiary":
            return Constants.STREET_TYPE_TERTIARY
        if streetType=="tertiary_link":
            return Constants.STREET_TYPE_TERTIARY_LINK
        if streetType=="residential":
            return Constants.STREET_TYPE_RESIDENTIAL
        if streetType=="service":
            return Constants.STREET_TYPE_SERVICE
        if streetType=="living_street":
            return Constants.STREET_TYPE_LIVING_STREET
        return -1
    
    def getStreetTypeIdForAddresses(self):
        return [Constants.STREET_TYPE_UNCLASSIFIED, 
                Constants.STREET_TYPE_ROAD, 
                Constants.STREET_TYPE_PRIMARY, 
                Constants.STREET_TYPE_SECONDARY,
                Constants.STREET_TYPE_TERTIARY, 
                Constants.STREET_TYPE_RESIDENTIAL, 
                Constants.STREET_TYPE_SERVICE,
                Constants.STREET_TYPE_LIVING_STREET]

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
    
#    def addToWayCache(self, wayId, tags, refs, name):
#        if self.wayCache==None:
#            self.wayCache=dict()  
#                          
#        entryFound=self.findInWayCache(tags, name)
#        if entryFound!=None:
#            storedRefs=entryFound["refs"]
#                
#        if entryFound==None:
#            cacheEntryList=list()
#            cacheEntry=dict()
#            cacheEntry["wayId"]=wayId
#            cacheEntry["tags"]=tags
#            cacheEntry["refs"]=refs
#
#            cacheEntryList.append(cacheEntry)
#            self.wayCache[name]=cacheEntryList
#        
#    def findInWayCache(self, tags, name):
#        if self.wayCache==None:
#            return None
#                
#        if name in self.wayCache:
#            cacheEntryList=self.wayCache[name]
#            for cacheEntry in cacheEntryList:
#                if cacheEntry["tags"]["highway"]==tags["highway"] and len(cacheEntry["tags"])==len(tags):
#                    if cacheEntry["tags"]==tags:
#                        return cacheEntry
#
#        return None
        
    def parse_ways(self, way):
        if self.skipWays==True:
            return 
        
        if self.firstWay==False:
            self.firstWay=True
            print("Parsing ways...")
            
        for wayid, tags, refs in way:
            if len(refs)==1:
                print("way with len(ref)==1 %d"%(wayid))
                continue
            
            if not "highway" in tags and "boundary" in tags:
                if tags["boundary"]=="administrative":
                    self.addToWayRefTable(wayid, refs)
            
            if "building" in tags:
                if "addr:street" in tags:
                    # TODO: use first ref as location for addr?
                    storedRef, lat, lon=self.getCoordsEntry(refs[0])
                    if storedRef!=None:
                        if lat!=None and lon!=None:
                            self.addToRefTable(refs[0], lat, lon, tags, Constants.POI_TYPE_ADDRESS)
                            refCountry=self.getCountryOfPos(lat, lon)
                            if refCountry!=None:
                                self.parseFullAddress(tags, refs[0], lat, lon, refCountry)

            if "area" in tags:        
                if tags["area"]=="yes":
                    # TODO: store in area table as polygon
                    # or if startRef==endref and !=roundabout
                    None
                        
                if "landuse" in tags:
                    None
                
                if "waterway" in tags:
                    None
                
                if "natural" in tags:
                    None
                
                continue
                
            if "highway" in tags:
                streetType=tags["highway"]
                if not self.isUsableRoad(streetType):
                    continue
                
                if "area" in tags:
                    if tags["area"]=="yes":
                        continue
                    
                if "service" in tags:
                    if "access" in tags:
                        if tags["access"]=="no":
                            continue
                                               
                streetTypeId=self.getStreetTypeId(streetType)
                if streetTypeId==-1:
                    print("unknown streetType %d %s"%(wayid, streetType))
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
                    elif tags["oneway"]=="-1":
#                        print("way %d has oneway==-1"%(wayid))
                        oneway=2
                if "junction" in tags:
                    if tags["junction"]=="roundabout":
                        roundabout=1
                
                tunnel=0
                if "tunnel" in tags:
                    if tags["tunnel"]=="yes":
                        tunnel=1
                
                bridge=0
                if "bridge" in tags:
                    if tags["bridge"]=="yes":
                        bridge=1
                        
                maxspeed=self.getMaxspeed(tags, streetTypeId)
                
#                if refs[0]==refs[-1] and roundabout==0:
#                    print("way %d has same start and endref"%(wayid))
                    
                missingRefCount=0
                for ref in refs:  
                    storedRef, lat, lon=self.getCoordsEntry(ref)
                    if storedRef==None:
                        missingRefCount=missingRefCount+1
                        continue

#                    refCountry=self.getCountryOfPos(lat, lon)
#                    if refCountry!=None:
                    self.addToRefTable(ref, lat, lon, None, 0)
                    self.addToRefWayTable(ref, wayid)
#                    else:
#                        missingRefCount=missingRefCount+1
                        
                if missingRefCount==len(refs):
                    print("skipping way %d - all refs are undefined"%(wayid))
                    continue
                
                requiredTags=self.stripUnneededTags(tags)
                coords, newRefList=self.createRefsCoords(refs)
                if len(coords)!=0:
                    self.addToWayTable(wayid, requiredTags, newRefList, streetTypeId, name, nameRef, oneway, roundabout, maxspeed, tunnel, bridge, coords)   
                else:
                    print("parse_ways: skipping wayId %d because of missing coords"%(wayid))

    def parse_relations(self, relation):
        if self.skipRelations==True:
            return
        
        if self.firstRelation==False:
            self.firstRelation=True
            print("Parsing relations...")

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
                        viaNode=None
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
                                if isNode==True:
                                    viaNode=roleId
                                elif isWay==True:
                                    viaWay.append(roleId)
                        if fromWayId!=0 and toWayId!=0:
                            restrictionEntry=dict()
                            restrictionEntry["id"]=osmid
                            restrictionEntry["type"]=restrictionType
                            restrictionEntry["to"]=toWayId
                            restrictionEntry["from"]=fromWayId
                            if viaNode!=None:
                                restrictionEntry["viaNode"]=viaNode
                            if len(viaWay)!=0:
                                restrictionEntry["viaWay"]=viaWay
    
                            self.wayRestricitionList.append(restrictionEntry)
                        
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
                elif tags["type"]=="multipolygon":
                    if "boundary" in tags:
                        if tags["boundary"]=="administrative":
                            # (59178604, 'way', 'outer')
                            None
#                            allRefs=list()
#
#                            for way in ways:
#                                memberType=way[1]
#                                ref=int(way[0])
#                                role=way[2]
#                                
#                                if role=="outer" and memberType=="way":
#                                    wayId=ref
#                                    # from boundary way table
#                                    refs=self.getWayRefEntry(wayId)
#                                    if refs!=None:
#                                        allRefs.append(refs)
#                                    else:
#                                        # from "real" way table
#                                        refs=self.getRefsForWayEntry(wayId)
#                                        if refs!=None:
#                                            allRefs.append(refs)
#                            
#                            if len(allRefs)!=0:
#                                refsDictStart=dict()
#                                for refs in allRefs:
#                                    refsDictStart[refs[0]]=refs
#
#                                refRings=self.resolveRefRings(allRefs, refsDictStart)
#                                
#                                if len(refRings)!=0:
#                                    # convert to multipolygon
#                                    polyString="'MULTIPOLYGON("
#                                    for refRing in refRings:
#                                        polyString=polyString+'(('
#                                        for ref in refRing:
#                                            ref, lat, lon=self.getCoordsEntry(ref)
#                                            if ref!=None:
#                                                polyString=polyString+"%f %f"%(lon, lat)+","
#                                        polyString=polyString[:-1]
#                                        polyString=polyString+')),'
#                                    polyString=polyString[:-1]
#                                    polyString=polyString+')'
#                                    print("%s %s"%(tags, polyString))
##                                    self.addToAreaTable(osmid, tags, polyString)
#                                           
                elif tags["type"]=="enforcement":
                    if "enforcement" in tags:
                        if tags["enforcement"]=="maxspeed":
                            if "maxspeed" in tags:
                                deviceRef=None
                                fromRefId=None
                                for part in ways:
                                    roleId=int(part[0])
                                    roleType=part[1]
                                    roleTag=part[2]
    
                                    if roleType=="node":
                                        if roleTag=="from":
                                            fromRefId=roleId
                                            
                                        elif roleTag=="device":
                                            deviceRef=roleId
                                            
                                if deviceRef!=None and fromRefId!=None:
                                    storedRefId, lat, lon, storedTags, storedNodeTypeList=self.getRefEntryForId(fromRefId)
                                    if storedRefId!=None:
                                        tags["deviceRef"]=deviceRef
                                        self.updateRefTableEntry(storedRefId, tags, Constants.POI_TYPE_ENFORCEMENT)
           
    def resolveRefRings(self, allRefs, refsDictStart):
        refRings=list()
        refRing=list()
        
        refs=allRefs[0]
        refRing.extend(refs)
        allRefs.remove(refs)
        del refsDictStart[refRing[0]]
        lastRef=refs[-1]
        while len(allRefs)!=0:
            if lastRef in refsDictStart.keys():
                refRing.extend(refsDictStart[lastRef][1:])
                newLastRef=refsDictStart[lastRef][-1]
                allRefs.remove(refsDictStart[lastRef])
                del refsDictStart[lastRef]
                lastRef=newLastRef
            else:
                if refRing[0]==refRing[-1]:
                    refRings.append(refRing)
                refRing=list()
                refRing.extend(allRefs[0])
                allRefs.remove(allRefs[0])
        
        if len(refRing)!=0:
            if refRing[0]==refRing[-1]:
                refRings.append(refRing)
                
        return refRings
    
    def mergeWayRefs(self, allRefs):
        refRings=list()
        refRingEntry=dict()
        refRing=list()
        wayIdList=list()
        
#        print(len(allRefs))  
        
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
                refRings.append(refRingEntry)
            
            refRingEntry=dict()
            refRing=list()
            wayIdList=list()
                        
#        print(len(refRings))
#        for refRingEntry in refRings:
#            print(refRingEntry["wayId"])
#            print("%d-%d"%(refRingEntry["refs"][0], refRingEntry["refs"][-1]))
#            print(refRingEntry["wayIdList"])
            
        return refRings
    
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
            
        if streetTypeId==Constants.STREET_TYPE_MOTORWAY or streetTypeId==Constants.STREET_TYPE_MOTORWAY_LINK:
            if ref!=None:
                ref=ref.replace(' ', '')
                if name==None:
                    name=ref    
        elif streetTypeId==Constants.STREET_TYPE_PRIMARY or streetTypeId==Constants.STREET_TYPE_PRIMARY_LINK:
            if ref!=None:
                ref=ref.replace(' ', '')    
                if not ref[0]=="B":
                    ref="B"+ref
                if name==None:
                    name=ref    
        elif streetTypeId==Constants.STREET_TYPE_SECONDARY or streetTypeId==Constants.STREET_TYPE_SECONDARY_LINK:
            if ref!=None:
                ref=ref.replace(' ', '')
                if not ref[0]=="L":
                    ref="L"+ref
                if name==None:
                    name=ref  
        elif streetTypeId==Constants.STREET_TYPE_TERTIARY or streetTypeId==Constants.STREET_TYPE_TERTIARY_LINK:
            if ref!=None:
                ref=ref.replace(' ', '')
                if name==None:
                    name=ref  
        elif streetTypeId==Constants.STREET_TYPE_RESIDENTIAL:
            if ref!=None:
                ref=ref.replace(' ', '')
                if name==None:
                    name=ref  
        elif streetTypeId==Constants.STREET_TYPE_TRUNK or streetTypeId==Constants.STREET_TYPE_TRUNK_LINK:
            if ref!=None:
                ref=ref.replace(' ', '')
                if name==None:
                    name=ref  

        return (name, ref)
    
    def getWaysForRef(self, ref):
        storedRef, wayIdList=self.getRefWayEntryForId(ref)
        if storedRef!=None:
            return wayIdList
        
        return None
        
    def getCoordsWithRef(self, refId):
        storedRefId, lat, lon, tags, nodeTypeList=self.getRefEntryForId(refId)
        if storedRefId!=None:
            return (lat, lon)
        
        return (None, None)
    
    def findWayWithRefInAllWays(self, refId, fromWayId):
        possibleWays=list()
        
        wayIdList=self.getWaysForRef(refId)
        if wayIdList==None or len(wayIdList)<=1:
            # no crossings at ref if not more then on different wayIds
            return possibleWays
        
        for wayid in wayIdList:    
            (wayEntryId, tags, refs, streetTypeId, name, nameRef, oneway, roundabout)=self.getWayEntryForId2(wayid)
            if wayEntryId==None:
                print("create crossings: skip crossing for wayId %s at refId %d to wayId %d"%(fromWayId, refId, wayid))
                continue
            
            for wayRef in refs:
                if wayRef==refId:
                    # dont add same wayid if at beginning or end
                    if fromWayId==wayid:
                        if refId==refs[0] or refId==refs[-1]:
                            continue
                    possibleWays.append((wayid, tags, refs, streetTypeId, name, nameRef, oneway, roundabout))
        return possibleWays
        
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
        
    # bbox for spatial DB (left, top, right, bottom)
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
            
    def createBBox(self, pos1, pos2, margin=None):
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
            
        if margin!=None:
            latRangeMax=bbox[3]+margin
            lonRangeMax=bbox[2]+margin*1.4
            latRangeMin=bbox[1]-margin
            lonRangeMin=bbox[0]-margin*1.4            
            bbox=[lonRangeMin, latRangeMin, lonRangeMax, latRangeMax]

        return bbox
    
    def calcRoute(self, route):  
        routingPointList=route.getRoutingPointList()                
      
        routeInfo=list()
        
        if len(routingPointList)!=0:  
            startPoint=routingPointList[0]
            if startPoint.getSource()==0:
                # should not happen
                print("startPoint NOT resolved in calc route")
                return None
            
            sourceEdge=startPoint.getEdgeId()
            sourcePos=startPoint.getPosOnEdge()
            
            bbox=self.createBBoxForRoute(route)
                    
            for targetPoint in routingPointList[1:]:
                if targetPoint.getTarget()==0:
                    # should not happen
                    print("targetPoint NOT resolved in calc route")
                    return None
                
                targetEdge=targetPoint.getEdgeId()
                targetPos=targetPoint.getPosOnEdge()
                       
                if self.dWrapperTrsp!=None:
                    edgeList, pathCost=self.dWrapperTrsp.computeShortestPath(sourceEdge, targetEdge, sourcePos, targetPos, bbox, False)
                    if edgeList==None:
                        return None
 
                routeInfoEntry=dict()
                routeInfoEntry["startPoint"]=startPoint
                routeInfoEntry["targetPoint"]=targetPoint
                routeInfoEntry["edgeList"]=edgeList
                routeInfoEntry["pathCost"]=pathCost   
                routeInfo.append(routeInfoEntry)                                      
                                   
                startPoint=targetPoint                       
                sourceEdge=startPoint.getEdgeId()
                sourcePos=startPoint.getPosOnEdge()

        return routeInfo
    
    def calcRouteForEdges(self, startEdge, endEdge, startPos, endPos):                                                                                         
        if self.dWrapperTrsp!=None:
            edgeList, pathCost=self.dWrapperTrsp.computeShortestPath(startEdge, endEdge, startPos, endPos, None, False)
            if edgeList==None:
                return None, None
            return edgeList, pathCost

        return None, None
        
    def getLastWayOnTrack(self, trackWayList):
        if len(trackWayList)>0:
            return trackWayList[-1]
        return None
        
    def getLastCrossingListOnTrack(self, trackWayList):
        if len(trackWayList)>0:
            for trackItem in trackWayList[::-1]:
                trackItemRefs=trackItem["refs"]
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

    def isOnLineBetweenPoints(self, lat, lon, lat1, lon1, lat2, lon2, maxDistance):
        nodes=self.osmutils.createTemporaryPoints(lat1, lon1, lat2, lon2)
        minDistance=maxDistance
        for tmpLat, tmpLon in nodes:
            distance=self.osmutils.distance(lat, lon, tmpLat, tmpLon)
            if distance<minDistance:
                return True
        
        return False
    
    # true if any point is closer then maxDistance
    def isOnLineBetweenRefs(self, lat, lon, ref1, ref2, maxDistance):
        storedRefId, lat1, lon1, storedTags, storedNodeTypeList=self.getRefEntryForId(ref1)
        if storedRefId==None:
            return False
        storedRefId, lat2, lon2, storedTags, storedNodeTypeList=self.getRefEntryForId(ref2)
        if storedRefId==None:
            return False
        
        return self.isOnLineBetweenPoints(lat, lon, lat1, lon1, lat2, lon2, maxDistance)
    
    def isMinimalDistanceOnLineBetweenPoints(self, lat, lon, lat1, lon1, lat2, lon2, maxDistance):        
        nodes=self.osmutils.createTemporaryPoints(lat1, lon1, lat2, lon2)
        minDistance=maxDistance
        onLine=False
        point=None
        for tmpLat, tmpLon in nodes:
            distance=self.osmutils.distance(lat, lon, tmpLat, tmpLon)
            if distance<minDistance:
                onLine=True
                minDistance=distance
                point=(tmpLat, tmpLon)
                        
        return onLine, minDistance, point
    
    def getEnforcmentsOnWay(self, wayId, refs):
        enforcementList=list()
        
        wayId, _, _, _, _, _, _, _, _, poiList=self.getWayEntryForId4(wayId)
        if wayId!=None:
            if poiList!=None:
                for ref, deviceRef, nodeType in poiList:
                    # enforcement
                    if nodeType==Constants.POI_TYPE_ENFORCEMENT:
                        deviceRef, lat, lon, storedTags, storedNodeTypeList=self.getRefEntryForId(deviceRef)
                        if deviceRef!=None:
                            enforcement=dict()
                            enforcement["coords"]=(lat, lon)
                            if storedTags!=None and "maxspeed" in storedTags:
                                enforcement["info"]="maxspeed:%s"%(storedTags["maxspeed"])
                            enforcementList.append(enforcement)
        
        if len(enforcementList)==0:
            return None
        return enforcementList
    
    def printEdgeForRefList(self, edge, trackWayList, startPoint, endPoint, currentStartRef):
        (edgeId, startRef, endRef, length, wayId, _, _, _, _, _, coords)=edge        
            
        latTo=None
        lonTo=None
        latFrom=None
        lonFrom=None
        
        (wayId, _, refs, streetTypeId, name, nameRef)=self.getWayEntryForId(wayId)
        refListPart=self.getRefListSubset(refs, startRef, endRef)
        if currentStartRef==endRef:
            refListPart.reverse()
            coords.reverse()

        nextStartRef=refListPart[-1]
        
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
                    onLine=self.isOnLineBetweenRefs(lat, lon, routeEndRefId, prevRefId, 10.0)
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
                    onLine=self.isOnLineBetweenRefs(lat, lon, routeStartRefId, nextRefId, 10.0)
                    if onLine==True:
                        routeStartRefId=nextRefId
        
        routeStartRefPassed=False
              
        trackItemRefs=list()
        i=0
        for ref in refListPart:        
            lat, lon=coords[i]
            
            if routeStartRefId!=None and routeStartRefPassed==False:
                if ref==routeStartRefId:
                    startLat, startLon=startPoint.getPos()
                    preTrackItemRef=dict()
                    preTrackItemRef["coords"]=(startLat, startLon)
                    trackItemRefs.append(preTrackItemRef)
                    latFrom=startLat
                    lonFrom=startLon
                    remaining=length-self.getLengthOnEdge(startLat, startLon, coords)
                    length=remaining
                    routeStartRefPassed=True
                else:
                    i=i+1
                    continue
            
            if ref!=refListPart[-1]:
                latFrom=lat
                lonFrom=lon
                      
            if ref!=refListPart[0]:
                latTo=lat
                lonTo=lon
                
            trackItemRef=dict()
            trackItemRef["coords"]=(lat, lon)

            trackItemRefs.append(trackItemRef)

            if routeEndRefId!=None and ref==routeEndRefId:
                endLat, endLon=endPoint.getPos()
                postTrackItemRef=dict()
                postTrackItemRef["coords"]=(endLat, endLon)
                postTrackItemRef["direction"]=99
                postTrackItemRef["crossingInfo"]="end"
                crossingList=list()
                crossingList.append((wayId, 99, None, ref))                                        
                postTrackItemRef["crossing"]=crossingList
                postTrackItemRef["crossingType"]=Constants.CROSSING_TYPE_END
                trackItemRefs.append(postTrackItemRef)
                latTo=endLat
                lonTo=endLon
                length=self.getLengthOnEdge(endLat, endLon, coords)
                     
            if lastTrackItemRef!=None:                     
                if ref==refListPart[0]:   
                    if edgeId==lastEdgeId:
                        # u-turn
                        crossingList=list()
                        crossingList.append((wayId, 98, None, ref))                                        
                        lastTrackItemRef["crossing"]=crossingList
                        lastTrackItemRef["crossingType"]=Constants.CROSSING_TYPE_START
                        lastTrackItemRef["direction"]=98
                        lastTrackItemRef["azimuth"]=360
                        lastTrackItemRef["crossingInfo"]="u-turn"

                        self.latCross=lat
                        self.lonCross=lon
                    else:
                        crossingEntries=self.getCrossingEntryForRefId(lastWayId, ref)
                        if len(crossingEntries)==1:
                            crossingCount=0
                            otherPossibleCrossingCount=0
                                     
                            edgeStartList=self.getEdgeEntryForStartOrEndPoint(ref)
                            if len(edgeStartList)!=0:
                                for edgeStart in edgeStartList:
                                    edgeStartId, edgeStartRef, edgeEndRef, _, edgeWayId, _, _, _, _=edgeStart
                                    if edgeStartId==lastEdgeId:
                                        continue
                                    
                                    (_, _, _, streetTypeId, _, _, oneway, roundabout)=self.getWayEntryForId2(edgeWayId)
    
                                    if edgeStartId==edgeId:
                                        crossingCount=crossingCount+1
                                        # crossings we always show
                                        if roundabout==1:
                                            otherPossibleCrossingCount=otherPossibleCrossingCount+1
                                        if streetTypeId==Constants.STREET_TYPE_MOTORWAY:
                                            otherPossibleCrossingCount=otherPossibleCrossingCount+1                                        
                                    else:
                                        # also use turn restriction info to
                                        # filter imppossible ways
                                        if self.isActiveTurnRestriction(lastEdgeId, edgeStartId, ref):
                                            continue
                                        
                                        # show no crossings with street of type service
                                        if streetTypeId==Constants.STREET_TYPE_SERVICE:
                                            continue
                                        # show no crossings with onways that make no sense
                                        if oneway!=0:
                                            if self.isValidOnewayEnter(oneway, ref, edgeStartRef, edgeEndRef):
                                                otherPossibleCrossingCount=otherPossibleCrossingCount+1
                                        else:
                                            otherPossibleCrossingCount=otherPossibleCrossingCount+1
                        
                            crossingList=list()

                            for crossing in crossingEntries:     
                                (_, _, _, nextWayIdList)=crossing
                                for nextWayId, crossingType, crossingInfo in nextWayIdList:
                                    (nextWayId, _, _, _, _, _, oneway, _)=self.getWayEntryForId2(nextWayId)

                                    if wayId==nextWayId:
                                        # always show those crossings e.g. name change
                                        # or link ends
                                        if crossingType==Constants.CROSSING_TYPE_NORMAL or crossingType==Constants.CROSSING_TYPE_LINK_END:
                                            otherPossibleCrossingCount=otherPossibleCrossingCount+1
                                            
                                        crossingList.append((nextWayId, crossingType, crossingInfo, ref))                                        
                            
                                
                                # only add crossing if there is no other possible way or 
                                # it is the only way
                                if crossingCount!=0 and otherPossibleCrossingCount!=0:
                                    lastTrackItemRef["crossing"]=crossingList
                                    self.latCross=lat
                                    self.lonCross=lon                        
                                                            
                                if self.roundaboutExitNumber!=None:
                                    for crossing in crossingEntries:
                                        (_, _, _, nextWayIdList)=crossing
                                                
                                        for roundaboutNextWayId, roundaboutCrossingType, _ in nextWayIdList:
                                            if wayId!=roundaboutNextWayId and roundaboutCrossingType==4:
                                                self.roundaboutExitNumber=self.roundaboutExitNumber+1
                                
                if latTo!=None and lonTo!=None and self.latCross!=None and self.lonCross!=None and self.latFrom!=None and self.lonFrom!=None:
                    azimuth=self.osmutils.azimuth((self.latCross, self.lonCross), (self.latFrom, self.lonFrom), (latTo, lonTo))   
                    direction=self.osmutils.direction(azimuth)
#                    print(azimuth)
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
                            print(crossingList)
                                
                    if crossingType!=None:   
                        if crossingType!=Constants.CROSSING_TYPE_NONE:
                            lastTrackItemRef["direction"]=direction
                            lastTrackItemRef["azimuth"]=azimuth
                            lastTrackItemRef["crossingType"]=crossingType
 
                        if crossingType==Constants.CROSSING_TYPE_NORMAL or crossingType==Constants.CROSSING_TYPE_LINK_START or crossingType==Constants.CROSSING_TYPE_LINK_LINK or crossingType==Constants.CROSSING_TYPE_LINK_END:
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
                        elif crossingType==Constants.CROSSING_TYPE_MOTORWAY_EXIT:
                            # highway junction
                            motorwayExitName=crossingInfo
                            if motorwayExitName!=None:
                                lastTrackItemRef["crossingInfo"]="motorway:exit:info:%s"%(motorwayExitName)
                            else:
                                lastTrackItemRef["crossingInfo"]="motorway:exit"
                            lastTrackItemRef["direction"]=39
                        elif crossingType==Constants.CROSSING_TYPE_ROUNDABOUT_ENTER:
                            # enter roundabout at crossingRef
                            # remember to get the exit number when leaving the roundabout
                            lastTrackItemRef["crossingInfo"]="roundabout:enter"
                            lastTrackItemRef["crossingRef"]=crossingRef
                            lastTrackItemRef["direction"]=40
                            self.roundaboutEnterItem=lastTrackItemRef
                            self.roundaboutExitNumber=0
                                
                        elif crossingType==Constants.CROSSING_TYPE_ROUNDABOUT_EXIT:
                            # exit roundabout
                            if self.roundaboutExitNumber==None:
                                print("self.roundaboutExitNumber==None")
                            else:
                                numExit=self.roundaboutExitNumber+1
                                if numExit!=0:
                                    lastTrackItemRef["crossingInfo"]="roundabout:exit:%d"%(numExit)
                                    lastTrackItemRef["direction"]=41
                                    if self.roundaboutEnterItem!=None:
                                        self.roundaboutEnterItem["crossingInfo"]=self.roundaboutEnterItem["crossingInfo"]+":%d"%(numExit)
                                        self.roundaboutEnterItem=None
                                        self.roundaboutExitNumber=None                      
            
            if routeEndRefId!=None and ref==routeEndRefId:
                break
            
            i=i+1
                
        trackItem["length"]=length
        self.sumLength=self.sumLength+length
        trackItem["sumLength"]=self.sumLength
        # TODO: calc time for edge

        trackItem["refs"]=trackItemRefs
        trackWayList.append(trackItem)
        self.latFrom=latFrom
        self.lonFrom=lonFrom
        return length, nextStartRef

    def printSingleEdgeForRefList(self, edge, trackWayList, startPoint, endPoint, currentStartRef):
        (edgeId, startRef, endRef, length, wayId, _, _, _, _, _, coords)=edge        
        
        (wayId, _, refs, streetTypeId, name, nameRef)=self.getWayEntryForId(wayId)
        refListPart=self.getRefListSubset(refs, startRef, endRef)
        if currentStartRef==endRef:
            refListPart.reverse()
            coords.reverse()

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
            trackItemRefs.append(preTrackItemRef)

            endLat, endLon=endPoint.getPos()
            postTrackItemRef=dict()
            postTrackItemRef["coords"]=(endLat, endLon)
            trackItemRefs.append(postTrackItemRef)

            length=self.osmutils.distance(startLat, startLon, endLat, endLon)       
        else:
            # use one ref before and after
            if indexEnd!=0:
                # use one ref before
                prevRefId=refListPart[indexEnd-1]
            else:
                prevRefId=routeEndRefId
                 
            if prevRefId!=routeEndRefId:
                lat, lon=endPoint.getPos()
                onLine=self.isOnLineBetweenRefs(lat, lon, routeEndRefId, prevRefId, 10.0)
                if onLine==True:
                    routeEndRefId=prevRefId
                        
            if indexStart!=len(refListPart)-1:
                nextRefId=refListPart[indexStart+1]
            else:
                nextRefId=routeStartRefId
                                
            if nextRefId!=routeStartRefId:
                lat, lon=startPoint.getPos()
                onLine=self.isOnLineBetweenRefs(lat, lon, routeStartRefId, nextRefId, 10.0)
                if onLine==True:
                    routeStartRefId=nextRefId
                        
            
            routeStartRefPassed=False

            i=0
            for ref in refListPart:  
                lat, lon=coords[i]
          
                if routeStartRefId!=None and routeStartRefPassed==False:
                    if ref==routeStartRefId:
                        startLat, startLon=startPoint.getPos()
                        preTrackItemRef=dict()
                        preTrackItemRef["coords"]=(startLat, startLon)
                        trackItemRefs.append(preTrackItemRef)
                        remaining=length-self.getLengthOnEdge(startLat, startLon, coords)
                        length=remaining
                        routeStartRefPassed=True
                    else:
                        i=i+1
                        continue
               
                trackItemRef=dict()
                trackItemRef["coords"]=(lat, lon)

                trackItemRefs.append(trackItemRef)
                
                if routeEndRefId!=None and ref==routeEndRefId:
                    endLat, endLon=endPoint.getPos()
                    postTrackItemRef=dict()
                    postTrackItemRef["coords"]=(endLat, endLon)
                    trackItemRefs.append(postTrackItemRef)
                    length=self.getLengthOnEdge(endLat, endLon, coords)
                    break         
        
                i=i+1
            
        trackItem["length"]=length
        self.sumLength=self.sumLength+length
        trackItem["sumLength"]=self.sumLength

        trackItem["refs"]=trackItemRefs
        trackWayList.append(trackItem)
        return length
 
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
            length=trackItem["length"]
            edgeId=trackItem["edgeId"]
            crossingLength=crossingLength+length
            
            for trackItemRef in trackItem["refs"]:        
                if "direction" in trackItemRef and "crossingInfo" in trackItemRef and "crossing" in trackItemRef:
                    crossingList=trackItemRef["crossing"]
                    direction=trackItemRef["direction"]
                    crossingInfo=trackItemRef["crossingInfo"]
                    for (_, crossingType, _, crossingRef) in crossingList:
                        return (direction, crossingLength, crossingInfo, crossingType, crossingRef, edgeId)
                        
        return (None, None, None, None, None, None)
    
    def getNextCrossingInfoFromPos(self, trackList, lat, lon):
        coordsList=list()
        firstTrackItem=trackList[0]

        for trackItemRef in firstTrackItem["refs"]:
            coordsList.append(trackItemRef["coords"])
           
        for trackItem in trackList:            
            edgeId=trackItem["edgeId"]
            for trackItemRef in trackItem["refs"]:
                if "direction" in trackItemRef and "crossingInfo" in trackItemRef and "crossing" in trackItemRef:
                    crossingList=trackItemRef["crossing"]
                    direction=trackItemRef["direction"]
                    crossingInfo=trackItemRef["crossingInfo"]
                    for (_, crossingType, _, crossingRef) in crossingList:
                        return (direction, crossingInfo, crossingType, crossingRef, edgeId)
                        
        return (None, None, None, None, None)

    def getClosestRefOnEdge(self, lat, lon, refs, coords, maxDistance):
        closestRef=None
        closestPoint=None
        
        minDistance=maxDistance
        i=0
        lat1, lon1=coords[0]
        for lat2, lon2 in coords[1:]:
            onLine, distance, point=self.isMinimalDistanceOnLineBetweenPoints(lat, lon, lat1, lon1, lat2, lon2, maxDistance)
            if onLine==True:
                if distance<minDistance:
                    minDistance=distance
                    distance1=self.osmutils.distance(lat, lon, lat1, lon1)
                    distance2=self.osmutils.distance(lat, lon, lat2, lon2)
                    if distance1<distance2:
                        closestRef=refs[i]
                    else:
                        if i<len(refs)-1:
                            closestRef=refs[i+1]
                        else:
                            closestRef=refs[-1]
                            
                    closestPoint=point
                
            lat1=lat2
            lon1=lon2
            i=i+1

        return closestRef, closestPoint
    
    def getPosOnOnEdge(self, lat, lon, coords, edgeLength):
        length=self.getLengthOnEdge(lat, lon, coords)
        if length==0:
            return edgeLength
        return length/edgeLength
    
    def getLengthOnEdge(self, lat, lon, coords, withOutside=False):
        length=0
        lat1, lon1=coords[0]
        for lat2, lon2 in coords[1:]:
            distance=self.osmutils.distance(lat1, lon1, lat2, lon2)

            if self.isOnLineBetweenPoints(lat, lon, lat1, lon1, lat2, lon2, distance):
                distance1=self.osmutils.distance(lat, lon, lat1, lon1)
                length=length+distance1
                return length

            length=length+distance
                                                                
            lat1=lat2
            lon1=lon2

        if withOutside==True:
            # add length from last coord
            length=length+self.osmutils.distance(lat, lon, lat2, lon2)
        return length
    
    def calcRouteDistances(self, trackList, lat, lon, route):
        coordsList=list()
        firstTrackItem=trackList[0]
        endLength=0
        crossingLength=0
        sumLength=firstTrackItem["sumLength"]
        length=firstTrackItem["length"]
        crossingFound=False
        
        for trackItemRef in firstTrackItem["refs"]:
            coordsList.append(trackItemRef["coords"])
            if "direction" in trackItemRef and "crossingInfo" in trackItemRef and "crossing" in trackItemRef:
                crossingFound=True
           
        distanceToEdge=self.getRemainingDistanceOnEdge(coordsList, lat, lon, length)
        if distanceToEdge!=None:
            endLength=distanceToEdge
            crossingLength=distanceToEdge

        endLength=endLength+route.getAllLength()-sumLength  
        
        if crossingFound==True:
            return endLength, crossingLength

        crossingFound=False
        for trackItem in trackList[1:]:     
            if crossingFound==True:
                break       
            length=trackItem["length"]
            crossingLength=crossingLength+length
            for trackItemRef in trackItem["refs"]:
                if "direction" in trackItemRef and "crossingInfo" in trackItemRef and "crossing" in trackItemRef:
                    crossingFound=True
                    break
           
        return endLength, crossingLength

    def getRemainingDistanceOnEdge(self, coords, lat, lon, edgeLength):
        length=self.getLengthOnEdge(lat, lon, coords, True)
        remaining=edgeLength-length
        return remaining
                    
    def getRefListOfEdge(self, edgeId, wayId, startRef, endRef):
        wayId, _, refs, _, _, _=self.getWayEntryForId(wayId)
        refList=self.getRefListSubset(refs, startRef, endRef)
        return refList

    def printRoute(self, route):
        routeInfo=route.getRouteInfo()
        
        for routeInfoEntry in routeInfo:
            endPoint=routeInfoEntry["targetPoint"]
            startPoint=routeInfoEntry["startPoint"]
            edgeList=routeInfoEntry["edgeList"]    
                
            trackWayList=list()
            allLength=0
            self.latFrom=None
            self.lonFrom=None
            self.latCross=None
            self.lonCross=None
            self.sumLength=0

            if len(edgeList)==0:
                continue
            
            if len(edgeList)==1:
                edge=self.getEdgeEntryForEdgeIdWithCoords(edgeList[0])                       
                (edgeId, startRef, endRef, _, _, _, _, _, _, _, _)=edge
                currentStartRef=startRef   
                if startPoint.getPosOnEdge()>0.5 and endPoint.getPosOnEdge()<startPoint.getPosOnEdge():
                    currentStartRef=endRef
                         
                length=self.printSingleEdgeForRefList(edge, trackWayList, startPoint, endPoint, currentStartRef)
                allLength=allLength+length
    
            else:
                i=0
                currentStartRef=None
                for edgeId in edgeList:
                    edge=self.getEdgeEntryForEdgeIdWithCoords(edgeId)                       
                    (edgeId, startRef, endRef, _, _, _, _, _, _, _, _)=edge        
    
                    if currentStartRef==None:
                        currentStartRef=startRef
                        # find out the order of refs for the start
                        # we may need to reverse them if the route goes
                        # in the opposite direction   
                        nextEdgeId=edgeList[1]
                        (nextEdgeId, nextStartRef, nextEndRef, _, _, _, _, _, _)=self.getEdgeEntryForEdgeId(nextEdgeId)                       
            
                        # look how the next edge continues to find the order
                        if nextEdgeId!=edgeId:
                            if nextStartRef==startRef or nextEndRef==startRef:
                                currentStartRef=endRef
                        
                    if i==0:
                        length, currentStartRef=self.printEdgeForRefList(edge, trackWayList, startPoint, None, currentStartRef)
                    elif i==len(edgeList)-1:
                        length, currentStartRef=self.printEdgeForRefList(edge, trackWayList, None, endPoint, currentStartRef)
                    else:
                        length, currentStartRef=self.printEdgeForRefList(edge, trackWayList, None, None, currentStartRef)
                        
                    allLength=allLength+length
                    i=i+1
                           
            routeInfoEntry["trackList"]=trackWayList
            routeInfoEntry["length"]=allLength

    def createEdgeTableEntries(self):
        self.cursorGlobal.execute('SELECT * FROM wayTable')
        allWays=self.cursorGlobal.fetchall()

        for way in allWays:
            self.createEdgeTableEntriesForWay(way)

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
        toAddRules=list()
        for wayRestrictionEntry in self.wayRestricitionList:
            fromWayId=int(wayRestrictionEntry["from"])
            toWayId=int(wayRestrictionEntry["to"])
            restrictionType=wayRestrictionEntry["type"]

            if "viaWay" in wayRestrictionEntry:
                print("relation with via type way %s"%(wayRestrictionEntry))
                continue

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
            # TODO: add viaNode
            self.addToRestrictionTable(toEdgeId, str(fromEdgeId), 10000)
            
    def getStreetTypeFactor(self, streetTypeId):
        # motorway
        if streetTypeId==Constants.STREET_TYPE_MOTORWAY:
            return 0.6
        # motorway exit
        if streetTypeId==Constants.STREET_TYPE_MOTORWAY_LINK:
            return 0.8
        # trunk
        if streetTypeId==Constants.STREET_TYPE_TRUNK:
            return 0.8
        # trunk exit
        if streetTypeId==Constants.STREET_TYPE_TRUNK_LINK:
            return 1.0
        # primary
        if streetTypeId==Constants.STREET_TYPE_PRIMARY or streetTypeId==Constants.STREET_TYPE_PRIMARY_LINK:
            return 1.2
        # secondary
        if streetTypeId==Constants.STREET_TYPE_SECONDARY or streetTypeId==Constants.STREET_TYPE_SECONDARY_LINK:
            return 1.4
        # tertiary
        if streetTypeId==Constants.STREET_TYPE_TERTIARY or streetTypeId==Constants.STREET_TYPE_TERTIARY_LINK:
            return 1.6
        # residential
        if streetTypeId==Constants.STREET_TYPE_RESIDENTIAL:
            return 1.8
        return 2.0
        
    def getMaxspeed(self, tags, streetTypeId):
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
        
        # TODO: if no valid maxspeed tag found use 0
        # final fallback if no other value found
#        if maxspeed==0:
##            print(tags)
#            maxspeed=self.getDefaultMaxspeedForStreetType(streetTypeId)
            
        return maxspeed
    
    def getDefaultMaxspeedForStreetType(self, streetTypeId):
        if streetTypeId==Constants.STREET_TYPE_RESIDENTIAL:
            maxspeed=50
        elif streetTypeId==Constants.STREET_TYPE_MOTORWAY_LINK or streetTypeId==Constants.STREET_TYPE_TRUNK_LINK or streetTypeId==Constants.STREET_TYPE_PRIMARY_LINK or streetTypeId==Constants.STREET_TYPE_SECONDARY_LINK or streetTypeId==Constants.STREET_TYPE_TERTIARY_LINK:
            maxspeed=80
        elif streetTypeId==Constants.STREET_TYPE_TRUNK:
            maxspeed=100
        elif streetTypeId==Constants.STREET_TYPE_MOTORWAY:
            maxspeed=130
        else:
            maxspeed=50
        return maxspeed
    
    def getAccessFactor(self, tags, streetTypeId):
        if "vehicle" in tags:
            if tags["vehicle"]=="destination":
                return 1000
            if tags["vehicle"]=="permissive":
                return 1000
            if tags["vehicle"]=="private":
                return 10000
            if tags["vehicle"]=="no":
                return 10000

        if "motorcar" in tags:
            if tags["motorcar"]=="destination":
                return 1000
            if tags["motorcar"]=="permissive":
                return 1000
            if tags["motorcar"]=="private":
                return 10000
            if tags["motorcar"]=="no":
                return 10000
                
        if "motor_vehicle" in tags:
            if tags["motor_vehicle"]=="destination":
                return 1000
            if tags["motor_vehicle"]=="permissive":
                return 1000
            if tags["motor_vehicle"]=="private":
                return 10000
            if tags["motor_vehicle"]=="no":
                return 10000
            
        if "access" in tags:
            if tags["access"]=="destination":
                return 1000
            if tags["access"]=="permissive":
                return 1000
            if tags["access"]=="private":
                return 10000
            if tags["access"]=="no":
                return 10000

        if streetTypeId==Constants.STREET_TYPE_LIVING_STREET:
            # living_street
            return 1000
        
        return 1
    
    def getCostsOfWay(self, wayId, tags, refs, distance, crossingFactor, streetInfo, maxspeed):
            
        streetTypeId, oneway, roundabout=self.decodeStreetInfo(streetInfo)
        if roundabout==1:
            oneway=1
        
        accessFactor=self.getAccessFactor(tags, streetTypeId)  
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
            
        if oneway==1:
            reverseCost=100000
        elif oneway==2:
            reverseCost=cost
            cost=100000
        else:
            reverseCost=cost
        
        return cost, reverseCost

    def createEdgeTableEntriesForWay(self, way):        
        wayId, tags, refs, streetInfo, name, nameRef, maxspeed, poiList=self.wayFromDB5(way)
        resultList=self.getCrossingEntryFor(wayId)
                
        nextWayDict=dict()
        for result in resultList:
            _, wayId, refId, nextWayIdList=result
            nextWayDict[refId]=nextWayIdList
        
        crossingFactor=1
        
        doneRefs=list()
        for ref in refs:                  
            if ref in nextWayDict:                                                                        
                doneRefs.append(ref)
        
        refNodeList=list()
        distance=0
        lastLat=None
        lastLon=None
        
        for ref in refs:
            storedRef, lat, lon=self.getCoordsEntry(ref)
            if storedRef!=None:                
                if lastLat!=None and lastLon!=None:
                    distance=distance+self.osmutils.distance(lat, lon, lastLat, lastLon)
                
                lastLat=lat
                lastLon=lon

            if ref in doneRefs:
                if len(refNodeList)!=0:
                        
                    refNodeList.append(ref)
                    startRef=refNodeList[0]
                    endRef=refNodeList[-1]                 

                    refList=self.getRefListSubset(refs, startRef, endRef)
                    coords, newRefList=self.createRefsCoords(refList)
                    if len(coords)!=0:
                        cost, reverseCost=self.getCostsOfWay(wayId, tags, refs, distance, crossingFactor, streetInfo, maxspeed)                                         
                        self.addToEdgeTable(startRef, endRef, distance, wayId, cost, reverseCost, streetInfo, coords)
                    else:
                        print("createEdgeTableEntriesForWay: skipping wayId %d from starRef %d to endRef %d because of missing coords"%(wayId, startRef, endRef))

                    refNodeList=list()
                    distance=0
           
            refNodeList.append(ref)
        
        # handle last portion
        if not ref in doneRefs:
            if len(refNodeList)!=0:
                startRef=refNodeList[0]
                endRef=refNodeList[-1]
                
                refList=self.getRefListSubset(refs, startRef, endRef)
                coords, newRefList=self.createRefsCoords(refList)                
                if len(coords)!=0:
                    cost, reverseCost=self.getCostsOfWay(wayId, tags, refs, distance, crossingFactor, streetInfo, maxspeed)                    
                    self.addToEdgeTable(startRef, endRef, distance, wayId, cost, reverseCost, streetInfo, coords)
                else:
                    print("createEdgeTableEntriesForWay: skipping wayId %d from starRef %d to endRef %d because of missing coords"%(wayId, startRef, endRef))

    def createRefsCoords(self, refList):
        coords=list()
        newRefList=list()
        for ref in refList:
            storedRef, lat, lon=self.getCoordsEntry(ref)
            if storedRef!=None:
                coords.append((lat, lon))
                newRefList.append(ref)
            else:
                # it is possible that we dont have these coords
                continue
            
        return coords, newRefList
    
    def createLineStringFromCoords(self, coords):
        lineString="'LINESTRING("
        for lat, lon in coords:
            lineString=lineString+"%f %f"%(lon, lat)+","
            
        lineString=lineString[:-1]
        lineString=lineString+")'"
        return lineString
    
    def createCoordsFromLineString(self, lineString):
        coords=list()
        coordsStr=lineString[11:-1]
        coordsPairs=coordsStr.split(",")
        for coordPair in coordsPairs:
            coordPair=coordPair.lstrip().rstrip()
            lon, lat=coordPair.split(" ")
            coords.append((float(lat), float(lon)))
            
        return coords

    def isLinkToLink(self, streetTypeId, streetTypeId2):
        return (streetTypeId==Constants.STREET_TYPE_MOTORWAY_LINK and streetTypeId2==Constants.STREET_TYPE_MOTORWAY_LINK) or (streetTypeId==Constants.STREET_TYPE_TRUNK_LINK and streetTypeId2==Constants.STREET_TYPE_TRUNK_LINK) or (streetTypeId==Constants.STREET_TYPE_PRIMARY_LINK and streetTypeId2==Constants.STREET_TYPE_PRIMARY_LINK) or (streetTypeId==Constants.STREET_TYPE_SECONDARY_LINK and streetTypeId2==Constants.STREET_TYPE_SECONDARY_LINK) or (streetTypeId==Constants.STREET_TYPE_TERTIARY_LINK and streetTypeId2==Constants.STREET_TYPE_TERTIARY_LINK)

    def isLinkEnter(self, streetTypeId, streetTypeId2):
        return (streetTypeId!=Constants.STREET_TYPE_MOTORWAY_LINK and streetTypeId2==Constants.STREET_TYPE_MOTORWAY_LINK) or (streetTypeId!=Constants.STREET_TYPE_TRUNK_LINK and streetTypeId2==Constants.STREET_TYPE_TRUNK_LINK) or (streetTypeId!=Constants.STREET_TYPE_PRIMARY_LINK and streetTypeId2==Constants.STREET_TYPE_PRIMARY_LINK) or (streetTypeId!=Constants.STREET_TYPE_SECONDARY_LINK and streetTypeId2==Constants.STREET_TYPE_SECONDARY_LINK) or (streetTypeId!=Constants.STREET_TYPE_TERTIARY_LINK and streetTypeId2==Constants.STREET_TYPE_TERTIARY_LINK)

    def isLinkExit(self, streetTypeId, streetTypeId2):
        return (streetTypeId==Constants.STREET_TYPE_MOTORWAY_LINK and streetTypeId2!=Constants.STREET_TYPE_MOTORWAY_LINK) or (streetTypeId==Constants.STREET_TYPE_TRUNK_LINK and streetTypeId2!=Constants.STREET_TYPE_TRUNK_LINK) or (streetTypeId==Constants.STREET_TYPE_PRIMARY_LINK and streetTypeId2!=Constants.STREET_TYPE_PRIMARY_LINK) or (streetTypeId==Constants.STREET_TYPE_SECONDARY_LINK and streetTypeId2!=Constants.STREET_TYPE_SECONDARY_LINK) or (streetTypeId==Constants.STREET_TYPE_TERTIARY_LINK and streetTypeId2!=Constants.STREET_TYPE_TERTIARY_LINK)

    def createCrossingEntries(self):
        self.cursorGlobal.execute('SELECT * FROM wayTable')
        allWays=self.cursorGlobal.fetchall()
        for way in allWays:
            wayid, tags, refs, streetTypeId, name, nameRef, oneway, roundabout=self.wayFromDB2(way)    
  
            for ref in refs:  
                majorCrossingType=Constants.CROSSING_TYPE_NORMAL
                majorCrossingInfo=None  
                nextWays=self.findWayWithRefInAllWays(ref, wayid)  
                if len(nextWays)!=0:                   
                    storedRefId, lat, lon, nodeTags, storedNodeTypeList=self.getRefEntryForId(ref)
                    if storedRefId!=None:
                        if nodeTags!=None and storedNodeTypeList!=None:
                            if Constants.POI_TYPE_MOTORWAY_JUNCTION in storedNodeTypeList:
                                majorCrossingType=Constants.CROSSING_TYPE_MOTORWAY_EXIT
                                highwayExitRef=None
                                highwayExitName=None
                                if "ref" in nodeTags:
                                    highwayExitRef=nodeTags["ref"]
                                if "name" in nodeTags:
                                    highwayExitName=nodeTags["name"]
                                majorCrossingInfo="%s:%s"%(highwayExitName, highwayExitRef)                             
                                
                    wayList=list()   
                    for (wayid2, tags2, refs2, streetTypeId2, name2, nameRef2, oneway2, roundabout2) in nextWays: 
                        minorCrossingType=Constants.CROSSING_TYPE_NORMAL
                        crossingType=Constants.CROSSING_TYPE_NORMAL
                        crossingInfo=None                 
                        if majorCrossingType==Constants.CROSSING_TYPE_NORMAL:
                            if minorCrossingType==Constants.CROSSING_TYPE_NORMAL:
                                if roundabout2==1 and roundabout==0:
                                    # roundabout enter
                                    minorCrossingType=Constants.CROSSING_TYPE_ROUNDABOUT_ENTER
                                elif roundabout==1 and roundabout2==0:
                                    # roundabout exit
                                    minorCrossingType=Constants.CROSSING_TYPE_ROUNDABOUT_EXIT
                                    if oneway2!=0:
                                        if not self.isValidOnewayEnter(oneway2, ref, refs2[0], refs2[-1]):
                                            # no exit roundabout
                                            minorCrossingType=Constants.CROSSING_TYPE_FORBIDDEN

                                elif roundabout==1 and roundabout2==1:
                                    # inside a roundabout there are no crossings
                                    minorCrossingType=Constants.CROSSING_TYPE_NONE
                                
                            if minorCrossingType==Constants.CROSSING_TYPE_NORMAL:
                                if self.isLinkToLink(streetTypeId, streetTypeId2):
                                    # _link to _link
                                    if wayid2==wayid:
                                        minorCrossingType=Constants.CROSSING_TYPE_NONE
                                    else:
                                        minorCrossingType=Constants.CROSSING_TYPE_LINK_LINK
                                        if len(nextWays)==1:
                                            if oneway!=0 and oneway2!=0:
                                                onewayValid=self.isValidOnewayEnter(oneway, ref, refs[0], refs[-1])
                                                oneway2Valid=self.isValidOnewayEnter(oneway2, ref, refs2[0], refs2[-1])
                                                if (oneway2Valid and not onewayValid) or (not oneway2Valid and onewayValid):
                                                    minorCrossingType=Constants.CROSSING_TYPE_NONE
                                            else:
                                                # way 2 way with no other possibilty
                                                if self.isValidWay2WayCrossing(refs, refs2):
                                                    minorCrossingType=Constants.CROSSING_TYPE_NONE
                                
                                elif self.isLinkEnter(streetTypeId, streetTypeId2):
                                    # _link enter
                                    minorCrossingType=Constants.CROSSING_TYPE_LINK_START
                                elif self.isLinkExit(streetTypeId, streetTypeId2):          
                                    # _link exit
                                    minorCrossingType=Constants.CROSSING_TYPE_LINK_END 
                                
                                if minorCrossingType==Constants.CROSSING_TYPE_NORMAL:
                                    if oneway2!=0 and roundabout2==0 and wayid2!=wayid:
                                        # mark no enter oneways - but not in the middle
                                        if ref==refs2[0] or ref==refs2[-1]:
                                            if not self.isValidOnewayEnter(oneway2, ref, refs2[0], refs2[-1]):
                                                # oneway end - not allowed to enter
                                                minorCrossingType=Constants.CROSSING_TYPE_FORBIDDEN    
                                        # TODO: do we need it?                   
#                                        else:
#                                            minorCrossingType=10

                        if majorCrossingType!=Constants.CROSSING_TYPE_NORMAL:
                            crossingType=majorCrossingType
                            crossingInfo=majorCrossingInfo
                            if majorCrossingType==Constants.CROSSING_TYPE_MOTORWAY_EXIT:
                                if streetTypeId2==Constants.STREET_TYPE_MOTORWAY:
                                    # not the exit from the motorway
                                    crossingType=Constants.CROSSING_TYPE_NONE
                                    crossingInfo=None

                        elif minorCrossingType!=Constants.CROSSING_TYPE_NORMAL:
                            crossingType=minorCrossingType
                        else:
                            if wayid2==wayid:     
                                crossingType=Constants.CROSSING_TYPE_NONE
                            # those streets dont have normal crossings
                            elif (streetTypeId==Constants.STREET_TYPE_MOTORWAY and streetTypeId2==Constants.STREET_TYPE_MOTORWAY) or (streetTypeId==Constants.STREET_TYPE_TRUNK and streetTypeId2==Constants.STREET_TYPE_TRUNK):
                                if oneway!=0 and oneway2!=0:
                                    onewayValid=self.isValidOnewayEnter(oneway, ref, refs[0], refs[-1])
                                    oneway2Valid=self.isValidOnewayEnter(oneway2, ref, refs2[0], refs2[-1])
                                    if (oneway2Valid and not onewayValid) or (not oneway2Valid and onewayValid):
                                        crossingType=Constants.CROSSING_TYPE_NONE
                                else:
                                    # way 2 way with no other possibilty
                                    if self.isValidWay2WayCrossing(refs, refs2):
                                        crossingType=Constants.CROSSING_TYPE_NONE

                            # ways can end not only on crossings
                            # e.g. 62074040 to 62074088 vs 62074609 to 30525406
                            else:
                                # any missing name will create a crossing
                                if name!=None and name2!=None:  
                                    # any name change will create a crossing 
                                    if name==name2:
                                        if self.isValidWay2WayCrossing(refs, refs2):
                                            crossingType=Constants.CROSSING_TYPE_NONE
                                    # TODO: dont use ref for matching
                                    # ref matching should only be done outside of citys :(
#                                    elif nameRef!=None and nameRef2!=None:
#                                        if nameRef==nameRef2:
#                                            if self.isValidWay2WayCrossing(refs, refs2):
#                                                crossingType=-1
                                                
                        if not (wayid2, crossingType, crossingInfo) in wayList:
                            wayList.append((wayid2, crossingType, crossingInfo))
                    
                    if len(wayList)!=0:
                        self.addToCrossingsTable(wayid, ref, wayList)
             
    def createPOIEntriesForWays(self):
        self.cursorGlobal.execute('SELECT * FROM wayTable')
        allWays=self.cursorGlobal.fetchall()
        for way in allWays:
            wayId, _, refs, _, _, _, _, _, _, poiList=self.wayFromDB4(way)    
            
            if poiList==None:
                poiList=list()
            
            for ref in refs:
                storedRefId, _, _, tags, nodeTypeList=self.getRefEntryForId(ref)
                if storedRefId!=None:
                    if nodeTypeList!=None and Constants.POI_TYPE_ENFORCEMENT in nodeTypeList:
                        # enforcement
                        if tags!=None and "deviceRef" in tags:
                            deviceRef=tags["deviceRef"]
                            if not (ref, deviceRef, Constants.POI_TYPE_ENFORCEMENT) in poiList:
                                poiList.append((ref, deviceRef, Constants.POI_TYPE_ENFORCEMENT))
                        else:
                            deviceRef=ref
                            if not (ref, deviceRef, Constants.POI_TYPE_ENFORCEMENT) in poiList:
                                poiList.append((ref, deviceRef, Constants.POI_TYPE_ENFORCEMENT))
                            
            if len(poiList)!=0:
                self.updateWayTableEntryPOIList(wayId, poiList)
            
    def parse(self, country):
        p = XMLParser(nodes_callback=self.parse_nodes, 
                  ways_callback=self.parse_ways, 
                  relations_callback=self.parse_relations,
                  coords_callback=self.parse_coords)
        p.parse(self.getOSMFile(country))

    def getOSMFile(self, country):
        return self.osmList[country]["osmFile"]
    
    # TODO: should be relativ to this dir by default
    def getDataDir(self):
        return os.path.join(env.getDataRoot(), "data")

    def getEdgeDBFile(self):
        file="edge.db"
        return os.path.join(self.getDataDir(), file)

    def getAreaDBFile(self):
        file="area.db"
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

    def getGlobalDBFile(self):
        file="global.db"
        return os.path.join(self.getDataDir(), file)
    
    def deleteCoordsDBFile(self):
        if os.path.exists(self.getCoordsDBFile()):
            os.remove(self.getCoordsDBFile())

    def coordsDBExists(self):
        return os.path.exists(self.getCoordsDBFile())

    def edgeDBExists(self):
        return os.path.exists(self.getEdgeDBFile())

    def areaDBExists(self):
        return os.path.exists(self.getAreaDBFile())

    def globalDBExists(self):
        return os.path.exists(self.getGlobalDBFile())
                
    def globalCountryDBExists(self):
        return os.path.exists(self.getGlobalCountryDBFile())

    def adressDBExists(self):
        return os.path.exists(self.getAdressDBFile())

    def initGraph(self):                     
        if self.dWrapperTrsp==None:
            self.dWrapperTrsp=TrspWrapper(self.getDataDir())

    def initDB(self):
        print(self.getDataDir())
        
        createCoordsDB=not self.coordsDBExists()
        if createCoordsDB:
            self.openCoordsDB()
            self.createCoordsDBTables()
        else:
            self.openCoordsDB()

        createEdgeDB=not self.edgeDBExists()
        if createEdgeDB:
            self.openEdgeDB()
            self.createEdgeTables()
        else:
            self.openEdgeDB()

        createAreaDB=not self.areaDBExists()
        if createAreaDB:
            self.openAreaDB()
            self.createAreaTable()
        else:
            self.openAreaDB()
        
        createAdressDB=not self.adressDBExists()
        if createAdressDB:
            self.openAdressDB()
            self.createAdressTable()
        else:
            self.openAdressDB()

        createGlobalDB=not self.globalDBExists()
        if createGlobalDB:
            self.openGlobalDB()
            self.createGlobalDBTables()
        else:
            self.openGlobalDB()

        if createGlobalDB==True:
            countryList=self.osmList.keys()
            for country in countryList:       
                self.firstWay=False
                self.firstRelation=False
                self.firstNode=False   
                self.skipNodes=False
                self.skipWays=False
                self.skipRelations=False
  
                print(self.osmList[country])
                print("start parsing")
                self.parse(country)
                print("end parsing")
                self.commitGlobalDB()
                self.commitAdressDB()
            
            self.commitCoordsDB()
                                                                     
            print("create POI entries")
            self.createPOIEntriesForWays()
            print("end create POI entries")
         
            print("create crossings")
            self.createCrossingEntries()
            print("end create crossings")
            
            self.commitGlobalDB()
            
            print("vacuum global DB")
            self.vacuumGlobalDB()
            print("end vacuum global DB")
            
        if createEdgeDB:            
            print("create edges")
            self.createEdgeTableEntries()
            print("end create edges")   

            print("create edge nodes")
            self.createEdgeTableNodeEntries()
            print("end create edge nodes")
                        
            print("create way restrictions")
            self.createWayRestrictionsDB()              
            print("end create way restrictions")

            print("remove orphaned edges")
            self.removeOrphanedEdges()
            print("end remove orphaned edges")
            
            self.commitEdgeDB()
            
            print("vacuum edge DB")
            self.vacuumEdgeDB()
            print("end vacuum edge DB")
        
        if createGlobalDB==True:
            print("create spatial index for global table")
            self.createSpatialIndexForGlobalTables()
            print("end create spatial index for global table")

        if createAreaDB==True:
            print("create spatial index for area table")
            self.createSpatialIndexForAreaTable()
            print("end create spatial index for area table")

        if createEdgeDB==True:
            print("create spatial index for edge table")
            self.createSpatialIndexForEdgeTable()
            print("end create spatial index for edge table")

        self.initGraph() 
        self.closeCoordsDB(False)
        self.closeAllDB()

    def parseAreaRelations(self):
        self.skipWays=True
        self.skipNodes=True
        self.skipRelations=False
        
        countryList=self.osmList.keys()
        for country in countryList:       
            self.firstRelation=False
  
            print(self.osmList[country])
            print("start parsing")
            self.parse(country)
            print("end parsing")
                
            self.commitAreaDB()

        
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
#        osmData["osmFile"]='/home/maxl/Downloads/geofabrik/bayern-thueringen.osm.bz2'
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
        resultList=self.getEdgeEntryForWayId(25491267)
        for edge in resultList:
            (edgeId, startRef, endRef, length, wayId, source, target, cost, reverseCost)=edge
            print(edge)
            
        resultList=self.getEdgeEntryForWayId(25491266)
        for edge in resultList:
            (edgeId, startRef, endRef, length, wayId, source, target, cost, reverseCost)=edge
            print(edge)

        resultList=self.getEdgeEntryForWayId(23685496)
        for edge in resultList:
            (edgeId, startRef, endRef, length, wayId, source, target, cost, reverseCost)=edge
            print(edge)
            
        
#        self.cursorGlobal.execute('SELECT refId, tags, type, AsText(geom) FROM refTable WHERE refId==892024881')
#        allentries=self.cursorGlobal.fetchall()
#        for x in allentries:
#            print(self.refFromDB(x))

    def printCrossingsForWayId(self, wayId):
        self.cursorGlobal.execute('SELECT * from crossingTable WHERE wayId=%d'%(wayId))
        allentries=self.cursorGlobal.fetchall()
        for x in allentries:
            print(self.crossingFromDB(x))

    def recreateCrossings(self):
        self.clearCrosssingsTable()
        
        print("recreate crossings")
        self.createCrossingEntries()
        print("end recreate crossings")
                                
    def recreateEdges(self):
        self.clearEdgeTable()
        print("recreate edges")
        self.createEdgeTableEntries()
        print("end recreate edges")   
                        
        print("recreate edge nodes")
        self.createEdgeTableNodeEntries()
        print("end recreate edge nodes")
        
        print("remove orphaned edges")
        self.removeOrphanedEdges()
        print("end remove orphaned edges")
        
        print("vacuum edge DB")
        self.vacuumEdgeDB()
        print("end vacuum edge DB")
        
    def testAddress(self):
        start=time.time()
        self.cursorAdress.execute('SELECT * FROM addressTable WHERE country==0 AND city=="Salzburg" AND streetName=="Münchner Bundesstraße"')
        allentries=self.cursorAdress.fetchall()
        for x in allentries:
            print(self.addressFromDB(x))
        print("%f"%(time.time()-start))
            
    def vacuumEdgeDB(self):
        self.cursorEdge.execute('VACUUM')

    def vacuumGlobalDB(self):
        self.cursorGlobal.execute('VACUUM')
                
    def removeOrphanedEdges(self):
        self.cursorEdge.execute('SELECT * FROM edgeTable')
        allentries=self.cursorEdge.fetchall()
        for x in allentries:
            edgeId, startRef, endRef, length, wayId, source, target, cost, reverseCost=self.edgeFromDB(x)
            resultList1=self.getEdgeEntryForSource(target)
            resultList2=self.getEdgeEntryForTarget(source)
            resultList3=self.getEdgeEntryForSource(source)
            resultList4=self.getEdgeEntryForTarget(target)
            if len(resultList1)==0 and len(resultList2)==0 and len(resultList3)==1 and len(resultList4)==1:
                print("remove edge %d %d %d %d"%(edgeId, wayId, startRef, endRef))
                self.cursorEdge.execute('DELETE FROM edgeTable WHERE id=%d'%(edgeId))
                
    def recreateCostsForEdges(self):
        print("recreate costs")
        self.cursorEdge.execute('SELECT * FROM edgeTable')
        allentries=self.cursorEdge.fetchall()
        for x in allentries:
            edgeId, startRef, endRef, length, wayId, source, target, cost, reverseCost=self.edgeFromDB(x)
            wayId, tags, refs, streetTypeId, name, nameRef, oneway, roundabout, maxspeed=self.getWayEntryForId3(wayId)
            if wayId==None:
                continue
            cost, reverseCost=self.getCostsOfWay(wayId, tags, refs, length, 1, streetTypeId, oneway, roundabout, maxspeed)
            self.updateCostsOfEdge(edgeId, cost, reverseCost)

        print("end recreate costs")
              
    def testEdgeTableGeom(self):
        self.cursorEdge.execute('SELECT AsText(geom) FROM edgeTable')
        allentries=self.cursorEdge.fetchall()
        for x in allentries:
            print(x)
                            
    def getNodesInBboxWithGeom(self, lat, lon, margin):
        latRangeMax=lat+margin
        lonRangeMax=lon+margin*1.4
        latRangeMin=lat-margin
        lonRangeMin=lon-margin*1.4       

        self.cursorGlobal.execute('SELECT refId, tags, type, AsText(geom) FROM refTable WHERE ROWID IN (SELECT rowid FROM idx_refTable_geom WHERE rowid MATCH RTreeWithin(%f, %f, %f, %f))'%(lonRangeMin, latRangeMin, lonRangeMax, latRangeMax))
        allentries=self.cursorGlobal.fetchall()
        resultList=list()
        for x in allentries:
            resultList.append(self.refFromDB(x))
        
    def getEdgesInBboxWithGeom(self, lat, lon, margin, bbox=None):
        if bbox==None: 
            latRangeMax=lat+margin
            lonRangeMax=lon+margin*1.4
            latRangeMin=lat-margin
            lonRangeMin=lon-margin*1.4       
            
            self.currentSearchBBox=[lonRangeMin, latRangeMin, lonRangeMax, latRangeMax]
        else:
            latRangeMax=bbox[3]+margin
            lonRangeMax=bbox[2]+margin
            latRangeMin=bbox[1]-margin
            lonRangeMin=bbox[0]-margin  

#            self.currentSearchBBox=[lonRangeMin, latRangeMin, lonRangeMax, latRangeMax]
            
        self.cursorEdge.execute('SELECT id, startRef, endRef, length, wayId, source, target, cost, reverseCost, streetInfo, AsText(geom) FROM edgeTable WHERE ROWID IN (SELECT rowid FROM idx_edgeTable_geom WHERE rowid MATCH RTreeIntersects(%f, %f, %f, %f))'%(lonRangeMin, latRangeMin, lonRangeMax, latRangeMax))
        allentries=self.cursorEdge.fetchall()
        resultList=list()
        for x in allentries:
            resultList.append(self.edgeFromDBWithCoords(x))
            
        return resultList

    def getWaysInBboxWithGeom(self, lat, lon, margin, bbox, streetTypeList):
        latRangeMax=bbox[3]+margin
        lonRangeMax=bbox[2]+margin
        latRangeMin=bbox[1]-margin
        lonRangeMin=bbox[0]-margin  
        
        # streetTypeList [] means all
        if streetTypeList==None or len(streetTypeList)==0:    
            self.cursorGlobal.execute('SELECT wayId, tags, refs, streetInfo, name, ref, maxspeed, poiList, AsText(geom) FROM wayTable WHERE ROWID IN (SELECT rowid FROM idx_wayTable_geom WHERE rowid MATCH RTreeIntersects(%f, %f, %f, %f))'%(lonRangeMin, latRangeMin, lonRangeMax, latRangeMax))
        else:
            filterString='('
            for streetType in streetTypeList:
                filterString=filterString+str(streetType)+','
            filterString=filterString[:-1]
            filterString=filterString+')'
            
            self.cursorGlobal.execute('SELECT wayId, tags, refs, streetInfo, name, ref, maxspeed, poiList, AsText(geom) FROM wayTable WHERE streetTypeId IN %s AND ROWID IN (SELECT rowid FROM idx_wayTable_geom WHERE rowid MATCH RTreeIntersects(%f, %f, %f, %f))'%(filterString, lonRangeMin, latRangeMin, lonRangeMax, latRangeMax))
            
        allentries=self.cursorGlobal.fetchall()
        resultList=list()
        for x in allentries:
            resultList.append(self.wayFromDBWithCoords(x))
            
        return resultList
            
    def getCoordsOfEdge(self, edgeId):
        (edgeId, _, _, _, _, _, _, _, _, _, coords)=self.getEdgeEntryForEdgeIdWithCoords(edgeId)                    
        return coords

    def getCoordsOfTrackItem(self, trackItem):
        coords=list()
        for trackItemRef in trackItem["refs"]:
            coords.append(trackItemRef["coords"])  
        return coords
    
    def isActiveTurnRestriction(self, fromEdgeId, toEdgeId, crossingRef):
        restrictionList=self.getRestrictionEntryForTargetEdge(toEdgeId)
        if len(restrictionList)!=0:
            # TODO: only if the restriction is valid for ref
            restrictedEdge=False
            for restriction in restrictionList:
                _, _, viaPath, _=restriction
                # TODO: viaPath can be more the one way if supported
                # TODO: better use the viaNode if available - add to DB
                if int(viaPath) == fromEdgeId:
                    restrictedEdge=True
                    break
                
            return restrictedEdge
        
        return False

    def getHeadingOnEdgeId(self, edgeId, ref):
        edgeId, _, endRef, _, _, _, _, _, _, _, _, coords=self.getEdgeEntryForEdgeIdWithCoords(edgeId)
        if ref==endRef:
            coords.reverse()
        heading=self.getHeadingForPoints(coords)
        return heading
            
    def getHeadingForPoints(self, coords):
        lat1, lon1=coords[0]
        for lat2, lon2 in coords[1:]:
            # use refs with distance more the 20m to calculate heading
            # if available else use the last one
            if self.osmutils.distance(lat1, lon1, lat2, lon2)>HEADING_CALC_LENGTH:
                break

        heading=self.osmutils.headingDegrees(lat1, lon1, lat2, lon2)
        return heading    

    def getDistanceFromPointToRef(self, lat, lon, ref):
        storedRefId, lat1, lon1, storedTags, storedNodeTypeList=self.getRefEntryForId(ref)
        if storedRefId==None:
            return None
        
        return self.osmutils.distance(lat, lon, lat1, lon1)

    def getNearerRefToPoint(self, lat, lon, ref1, ref2):
        distanceRef1=self.getDistanceFromPointToRef(lat, lon, ref1)
        distanceRef2=self.getDistanceFromPointToRef(lat, lon, ref2)
                
        if distanceRef1 < distanceRef2:
            return ref1
        return ref2    
    
    def getEdgesOfTunnel(self, edgeId, ref):
        tunnelEdgeList=list()
        data=dict()
        data["edge"]=edgeId
        data["startRef"]=ref
        data["heading"]=self.getHeadingOnEdgeId(edgeId, ref)
        tunnelEdgeList.append(data)
        
        _, startRef, endRef, _, _, _, _, _, _=self.getEdgeEntryForEdgeId(edgeId)
        if ref==startRef:
            nextEndRef=endRef
        else:
            nextEndRef=startRef
            
        self.followEdge(edgeId, nextEndRef, tunnelEdgeList, self.followEdgeCheck, data)

        return tunnelEdgeList

    def followEdgeCheck(self, wayId, ref):
        tags=self.getTagsForWayEntry(wayId)
        if not "tunnel" in tags:
            return False
        return True
    
    def followEdge(self, edgeId, ref, edgeList, followEdgeCheck, lastData):
        resultList=self.getEdgeEntryForStartPoint(ref, None)
        
        for edge in resultList:    
            edgeId, startRef, endRef, _, wayId, _, _, _, _=edge
            if ref==startRef:
                nextEndRef=endRef
            else:
                nextEndRef=startRef

            if followEdgeCheck(wayId, nextEndRef)==False:
                lastData["endRef"]=ref
                return
            
            data=dict()
            data["edge"]=edgeId
            data["startRef"]=ref
            data["heading"]=self.getHeadingOnEdgeId(edgeId, ref)

            edgeList.append(data)

            self.followEdge(edgeId, nextEndRef, edgeList, followEdgeCheck, data)

    def mergeEqualWayEntries(self, wayId):        
        self.cursorGlobal.execute('SELECT wayId, tags, refs, streetInfo, name, ref, maxspeed, poiList, AsText(geom) FROM wayTable WHERE wayId=%d'%(wayId))

        allWays=self.cursorGlobal.fetchall()
        way=allWays[0]
        wayId, tags, refs, streetInfo, name, nameRef, maxspeed, poiList, coords=self.wayFromDBWithCoords(way)
        if name!=None:
            streetTypeId, oneway, roundabout=self.decodeStreetInfo(streetInfo)
            
            allRefs=list()
            allRefs.append((wayId, refs, oneway, roundabout))
            resultList=self.getWayEntryForStreetName(name)
            for otherWay in resultList:
                otherWayId, otherTags, otherRefs, otherStreetInfo, _, otherNameRef, otherMaxspeed, otherPoiList, otherCoords=otherWay
                if otherWayId==wayId:
                    continue
            
                if streetInfo!=otherStreetInfo:
                    continue
                
                if maxspeed!=otherMaxspeed:
                    continue
                
                if nameRef!=otherNameRef:
                    continue
                
                if len(tags)!=len(otherTags):
                    continue
                
                if tags!=otherTags:
                    continue
                
                streetTypeId, oneway, roundabout=self.decodeStreetInfo(otherStreetInfo)
                allRefs.append((otherWayId, otherRefs, oneway, roundabout))
            
            refRings=self.mergeWayRefs(allRefs)
            return refRings
        
        return None
                
def main(argv):    
    p = OSMParserData()
    
    p.initDB()
    
    p.openAllDB()
#    p.cursorEdge.execute("SELECT * FROM sqlite_master WHERE type='table'")
#    allentries=p.cursorEdge.fetchall()
#    for x in allentries:
#        print(x)


#    p.cursorEdge.execute('PRAGMA table_info(cache_edgeTable_Geometry)')
#    p.cursorEdge.execute('SELECT DiscardGeometryColumn("edgeTable", "geom")')
#    p.cursorEdge.execute("SELECT RecoverGeometryColumn('edgeTable', 'geom', 4326, 'LINESTRING', 2)")
#    p.cursorEdge.execute('SELECT CreateSpatialIndex("edgeTable", "geom")')
#
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
#    p.testAddress()
#    p.testRoutes()
#    p.testWayTable()
#    p.recreateCostsForEdges()
#    p.removeOrphanedEdges()
#    p.createGeomDataForEdgeTable()

#    p.parseAreaRelations()
#    p.vacuumEdgeDB()
#    p.vacuumGlobalDB()

    p.mergeEqualWayEntries()
    
    p.closeAllDB()


if __name__ == "__main__":
    main(sys.argv)  
    

