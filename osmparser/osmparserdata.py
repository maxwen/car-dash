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
import re
from misc.progress import ProgressBar
import cProfile

#from pygraph-routing.dijkstrapygraph import DijkstraWrapperPygraph
#from igraph.dijkstraigraph import DijkstraWrapperIgraph

from config import Config
from osmparser.osmboarderutils import OSMBoarderUtils
from trsp.trspwrapper import TrspWrapper
from osmparser.osmpoly import OSMPoly

HEADING_CALC_LENGTH=20.0

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
    
    POI_TYPE_ENFORCEMENT=1
    POI_TYPE_MOTORWAY_JUNCTION=2
    POI_TYPE_BARRIER=3
    POI_TYPE_ENFORCEMENT_WAYREF=4
    POI_TYPE_GAS_STATION=5
    POI_TYPE_ADDRESS=6
    POI_TYPE_PARKING=7
    POI_TYPE_PLACE=8
    POI_TYPE_HOSPITAL=9
    POI_TYPE_POLICE=10
    POI_TYPE_SUPERMARKET=11
    
    AREA_TYPE_ADMIN=0
    AREA_TYPE_NATURAL=1
    AREA_TYPE_LANDUSE=2
    AREA_TYPE_BUILDING=3
    AREA_TYPE_HIGHWAY_AREA=4
    AREA_TYPE_RAILWAY=5
    AREA_TYPE_AEROWAY=6
    
    LANDUSE_TYPE_SET=set(["forest", "grass", "grassland", "field", "farm", "farmland", "farmyard", "meadow", "residential", "greenfield", "brownfield", "commercial", "industrial", "railway", "water", "reservoir", "basin", "cemetery", "military", "recreation_ground", "village_green", "allotments", "orchard"])
    LANDUSE_NATURAL_TYPE_SET=set(["forest", "grass", "grassland", "field", "farm", "farmland", "meadow", "greenfield", "brownfield", "farmyard", "recreation_ground", "village_green", "allotments", "orchard"])
    LANDUSE_WATER_TYPE_SET=set(["reservoir", "basin", "water"])
    
    NATURAL_TYPE_SET=set(["water", "wood", "tree", "forest", "park", "riverbank"])
    WATERWAY_TYPE_SET=set(["riverbank", "river", "stream", "drain"])
    RAILWAY_TYPE_SET=set(["rail"])
    AEROWAY_TYPE_SET=set(["runway", "taxiway", "apron", "aerodrome"])
    HIGHWAY_NODES_TYPE_SET=set(["motorway_junction", "speed_camera"])
    AMENITY_NODES_TYPE_SET=set(["fuel", "parking", "hospital", "police"])
    SHOP_NODES_TYPE_SET=set(["supermarket"])
    BARIER_NODES_TYPE_SET=set(["bollard"])
    BOUNDARY_TYPE_SET=set(["administrative"])
    PLACE_NODES_TYPE_SET=set(["city", "village", "town", "suburb"])
    REQUIRED_HIGHWAY_TAGS_SET=set(["motorcar", "motor_vehicle", "access", "vehicle", "service", "layer", "lanes"])
    
    AMENITY_TYPE_DICT={"fuel": POI_TYPE_GAS_STATION, 
                       "parking": POI_TYPE_PARKING,
                       "hospital": POI_TYPE_HOSPITAL, 
                       "police": POI_TYPE_POLICE}
    
    SHOP_TYPE_DICT={"supermarket": POI_TYPE_SUPERMARKET}
    
    HIGHWAY_TYPE_DICT={"motorway_junction": POI_TYPE_MOTORWAY_JUNCTION, 
                       "speed_camera": POI_TYPE_ENFORCEMENT}
    
    STREET_TYPE_DICT={"road": STREET_TYPE_ROAD,
        "unclassified": STREET_TYPE_UNCLASSIFIED,
        "motorway": STREET_TYPE_MOTORWAY,
        "motorway_link": STREET_TYPE_MOTORWAY_LINK,
        "trunk":STREET_TYPE_TRUNK,
        "trunk_link":STREET_TYPE_TRUNK_LINK,
        "primary":STREET_TYPE_PRIMARY,
        "primary_link":STREET_TYPE_PRIMARY_LINK,
        "secondary":STREET_TYPE_SECONDARY,
        "secondary_link":STREET_TYPE_SECONDARY_LINK,
        "tertiary":STREET_TYPE_TERTIARY,
        "tertiary_link":STREET_TYPE_TERTIARY_LINK,
        "residential":STREET_TYPE_RESIDENTIAL,
        "service":STREET_TYPE_SERVICE,
        "living_street":STREET_TYPE_LIVING_STREET}
    
    ONEWAY_OVERLAY_STREET_SET=set([STREET_TYPE_SERVICE,
                STREET_TYPE_UNCLASSIFIED,
                STREET_TYPE_ROAD,
                STREET_TYPE_PRIMARY,
                STREET_TYPE_SECONDARY,
                STREET_TYPE_TERTIARY,
                STREET_TYPE_RESIDENTIAL])
    
    ADDRESS_STREET_SET=set([STREET_TYPE_SERVICE,
                STREET_TYPE_UNCLASSIFIED,
                STREET_TYPE_ROAD,
                STREET_TYPE_PRIMARY,
                STREET_TYPE_SECONDARY,
                STREET_TYPE_TERTIARY,
                STREET_TYPE_RESIDENTIAL])
    
    ADMIN_LEVEL_SET=[2, 4, 6, 8]
            
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
        self.cursorTmp=None
        self.connectionTmp=None
        self.edgeId=1
        self.restrictionId=0
        self.trackItemList=list()
        self.nodeId=1
        self.addressId=0
        self.areaId=0
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
        self.skipNodes=False
        self.skipWays=False
        self.skipCoords=False
        self.skipRelations=False
        self.skipHighways=False
        self.skipAddress=False
        self.skipAreas=False
        self.skipPOINodes=False
        self.nodeList=dict()

    def createEdgeTables(self):
        self.createEdgeTable()
        self.createRestrictionTable()

    def createAdressTable(self):
        self.createAddressTable()
        
    def setPragmaForDB(self, cursor):
        cursor.execute('PRAGMA journal_mode=OFF')
        cursor.execute('PRAGMA synchronous=OFF')
        
    def openEdgeDB(self):
        self.connectionEdge=sqlite3.connect(self.getEdgeDBFile())
        self.cursorEdge=self.connectionEdge.cursor()
        self.connectionEdge.enable_load_extension(True)
        self.cursorEdge.execute("SELECT load_extension('libspatialite.so')")
        self.setPragmaForDB(self.cursorEdge)

    def openAreaDB(self):
        self.connectionArea=sqlite3.connect(self.getAreaDBFile())
        self.cursorArea=self.connectionArea.cursor()
        self.connectionArea.enable_load_extension(True)
        self.cursorArea.execute("SELECT load_extension('libspatialite.so')")
        self.setPragmaForDB(self.cursorArea)

    def openGlobalDB(self):
        self.connectionGlobal=sqlite3.connect(self.getGlobalDBFile())
        self.cursorGlobal=self.connectionGlobal.cursor()
        self.connectionGlobal.enable_load_extension(True)
        self.cursorGlobal.execute("SELECT load_extension('libspatialite.so')")
        self.setPragmaForDB(self.cursorGlobal)
        
    def openAdressDB(self):
        self.connectionAdress=sqlite3.connect(self.getAdressDBFile())
        self.cursorAdress=self.connectionAdress.cursor()
        self.setPragmaForDB(self.cursorAdress)

    def openCoordsDB(self):
        self.connectionCoords=sqlite3.connect(self.getCoordsDBFile())
#        self.connectionCoords=sqlite3.connect(":memory:")
        self.cursorCoords=self.connectionCoords.cursor()
        self.setPragmaForDB(self.cursorCoords)

    def openTmpDB(self):
#        self.connectionTmp=sqlite3.connect(self.getTmpDBFile())
        self.connectionTmp=sqlite3.connect(":memory:")
        self.cursorTmp=self.connectionTmp.cursor()
        self.setPragmaForDB(self.cursorTmp)
        
    def createCoordsDBTables(self):
        self.createCoordsTable()
        self.createWayRefTable()

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

    def closeTmpDB(self, delete):
        if self.connectionTmp!=None:
            self.connectionTmp.commit()
            self.cursorTmp.close()
            self.connectionTmp=None
            self.cursorTmp=None   
            if delete==True: 
                self.deleteTmpDBFile() 
                 
    def openAllDB(self):
        self.openGlobalDB()
        self.openEdgeDB()
        self.openAreaDB()
        self.openAdressDB()
#        self.openTmpDB()
        self.openCoordsDB()
        
    def closeAllDB(self):
        self.closeGlobalDB()
        self.closeEdgeDB()
        self.closeAreaDB()
        self.closeAdressDB()
#        self.closeTmpDB(False)
        self.closeCoordsDB(False)
      
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

    def addToCoordsTable(self, ref, lat, lon):
        self.cursorCoords.execute('INSERT OR IGNORE INTO coordsTable VALUES( ?, ?, ?)', (ref, lat, lon))
    
    def addToWayRefTable(self, wayId, refs):
        self.cursorCoords.execute('INSERT OR IGNORE INTO wayRefTable VALUES( ?, ?)', (wayId, pickle.dumps(refs)))
        
    def addToTmpRefWayTable(self, refid, wayId):
        storedRef, wayIdList=self.getTmpRefWayEntryForId(refid)
        if storedRef!=None:                            
            if wayIdList==None:
                wayIdList=list()
            if not wayId in wayIdList:
                wayIdList.append(wayId)
            self.cursorTmp.execute('REPLACE INTO refWayTable VALUES( ?, ?)', (refid, pickle.dumps(wayIdList)))
            return
            
        wayIdList=list()
        wayIdList.append(wayId)
        self.cursorTmp.execute('INSERT INTO refWayTable VALUES( ?, ?)', (refid, pickle.dumps(wayIdList)))

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
    
    def getTmpRefWayEntryForId(self, ref):
        self.cursorTmp.execute('SELECT * FROM refWayTable WHERE refId=%d'%(ref))
        allentries=self.cursorTmp.fetchall()
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

    def createTmpTable(self):
#        self.cursorTmp.execute('CREATE TABLE wayTable (wayId INTEGER PRIMARY KEY, tags BLOB, refs BLOB, streetInfo INTEGER, name TEXT, ref TEXT, maxspeed INTEGER)')
#        self.cursorTmp.execute("CREATE INDEX name_idx ON wayTable (name)")
        self.cursorTmp.execute('CREATE TABLE refWayTable (refId INTEGER PRIMARY KEY, wayIdList BLOB)')

#    def dropTmpWayTable(self):
#        self.cursorTmp.execute('DROP TABLE wayTable')
#        self.cursorTmp.execute('DROP INDEX name_idx')

    def dropTmpTable(self):
        self.cursorTmp.execute('DROP TABLE refWayTable')
        
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
    
    def createEdgeTable(self):
        self.cursorEdge.execute("SELECT InitSpatialMetaData()")
        self.cursorEdge.execute('CREATE TABLE edgeTable (id INTEGER PRIMARY KEY, startRef INTEGER, endRef INTEGER, length INTEGER, wayId INTEGER, source INTEGER, target INTEGER, cost REAL, reverseCost REAL, streetInfo INTEGER)')
        self.cursorEdge.execute("CREATE INDEX startRef_idx ON edgeTable (startRef)")
        self.cursorEdge.execute("CREATE INDEX endRef_idx ON edgeTable (endRef)")
        self.cursorEdge.execute("CREATE INDEX wayId_idx ON edgeTable (wayId)")
        self.cursorEdge.execute("CREATE INDEX source_idx ON edgeTable (source)")
        self.cursorEdge.execute("CREATE INDEX target_idx ON edgeTable (target)")        
        self.cursorEdge.execute("SELECT AddGeometryColumn('edgeTable', 'geom', 4326, 'LINESTRING', 2)")

    def createAreaTable(self):
        self.cursorArea.execute("SELECT InitSpatialMetaData()")
        self.cursorArea.execute('CREATE TABLE areaTable (osmId INTEGER PRIMARY KEY, type INTEGER, tags BLOB, adminLevel INTEGER)')
        self.cursorArea.execute("SELECT AddGeometryColumn('areaTable', 'geom', 4326, 'MULTIPOLYGON', 2)")
        self.cursorArea.execute('CREATE TABLE areaLineTable (osmId INTEGER PRIMARY KEY, type INTEGER, tags BLOB, adminLevel INTEGER)')
        self.cursorArea.execute("SELECT AddGeometryColumn('areaLineTable', 'geom', 4326, 'LINESTRING', 2)")

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

        storedRefId, lat, lon, storedTags, storedNodeTypeList=self.getRefEntryForId(refid)
            
        if storedRefId!=None:    
            if tags!=None:
                if storedTags!=None:
                    # merge tags
                    for key, value in tags.items():
                        storedTags[key]=value
                else:
                    storedTags=tags
        
            tagsString=None
            if storedTags!=None:
                tagsString=pickle.dumps(storedTags)

            # add to list if !=0
            if nodeType!=None and nodeType!=0:
                if storedNodeTypeList!=None:
                    if not nodeType in storedNodeTypeList:
                        storedNodeTypeList.append(nodeType)
                else:                        
                    storedNodeTypeList=list()
                    storedNodeTypeList.append(nodeType)
            
            nodeTypeListStr=None
            if storedNodeTypeList!=None:
                nodeTypeListStr=pickle.dumps(storedNodeTypeList)
                
            self.cursorGlobal.execute('REPLACE INTO refTable VALUES( ?, ?, ?, PointFromText(%s, 4326))'%(pointString), (refid, tagsString, nodeTypeListStr))
        
        else:
            tagsString=None
            if tags!=None:
                tagsString=pickle.dumps(tags)
    
            storedNodeTypeList=None
            if nodeType!=None and nodeType!=0:
                storedNodeTypeList=list()
                storedNodeTypeList.append(nodeType)
            
            nodeTypeListStr=None
            if storedNodeTypeList!=None:
                nodeTypeListStr=pickle.dumps(storedNodeTypeList)
    
            self.cursorGlobal.execute('INSERT INTO refTable VALUES( ?, ?, ?, PointFromText(%s, 4326))'%(pointString), (refid, tagsString, nodeTypeListStr))
        
    def updateWayTableEntryPOIList(self, wayId, poiList):
        wayId, tags, refs, streetInfo, name, nameRef, maxspeed, _, coords=self.getWayEntryForIdWithCoords(wayId)
        if wayId!=None:
            streetTypeId, _, _=self.decodeStreetInfo(streetInfo)
            lineString=self.createLineStringFromCoords(coords)
            self.cursorGlobal.execute('REPLACE INTO wayTable VALUES( ?, ?, ?, ?, ?, ?, ?, ?, ?, LineFromText(%s, 4326))'%(lineString), (wayId, self.encodeWayTags(tags), pickle.dumps(refs), streetInfo, name, nameRef, maxspeed, pickle.dumps(poiList), streetTypeId))
        
    def updateRefTableEntry(self, refId, tags, nodeType):
        storedRefId, lat, lon, storedTags, storedNodeTypeList=self.getRefEntryForId(refId)
        if storedRefId!=None:
            tagsChanged=False
            if tags!=None:
                if storedTags!=None:
                    tagsChanged=True
                    # merge tags
                    for key, value in tags.items():
                        storedTags[key]=value
                else:
                    storedTags=tags
                    tagsChanged=True
                
            nodeTypeListChanged=False
            if nodeType!=None and nodeType!=0:
                # add to list if !=0
                if storedNodeTypeList!=None:
                    if not nodeType in storedNodeTypeList:
                        nodeTypeListChanged=True
                        storedNodeTypeList.append(nodeType)
                else:
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
        name=self.encodeStreetName(name)
        streetInfo=self.encodeStreetInfo2(streetTypeId, oneway, roundabout, tunnel, bridge)
        lineString=self.createLineStringFromCoords(coords)
        self.cursorGlobal.execute('INSERT OR IGNORE INTO wayTable VALUES( ?, ?, ?, ?, ?, ?, ?, ?, ?, LineFromText(%s, 4326))'%(lineString), (wayid, self.encodeWayTags(tags), pickle.dumps(refs), streetInfo, name, nameRef, maxspeed, None, streetTypeId))

#    def addToTmpWayTable(self, wayid, tags, refs, streetTypeId, name, nameRef, oneway, roundabout, maxspeed, tunnel, bridge):
#        name=self.encodeStreetName(name)
#        streetInfo=self.encodeStreetInfo2(streetTypeId, oneway, roundabout, tunnel, bridge)
#        self.cursorTmp.execute('INSERT OR IGNORE INTO wayTable VALUES( ?, ?, ?, ?, ?, ?, ?)', (wayid, self.encodeWayTags(tags), pickle.dumps(refs), streetInfo, name, nameRef, maxspeed))
    
    def encodeStreetName(self, name):
        if name!=None:
            return name.replace('"', '').replace('\'', '')
        return name
        
    def addToCrossingsTable(self, wayid, refId, nextWaysList):
        self.cursorGlobal.execute('INSERT INTO crossingTable VALUES( ?, ?, ?, ?)', (self.crossingId, wayid, refId, pickle.dumps(nextWaysList)))
        self.crossingId=self.crossingId+1

    def addToEdgeTable(self, startRef, endRef, length, wayId, cost, reverseCost, streetInfo, coords):
        resultList=self.getEdgeEntryForStartAndEndPointAndWayId(startRef, endRef, wayId)
        if len(resultList)==0:
            lineString=self.createLineStringFromCoords(coords)
            
            self.cursorEdge.execute('INSERT INTO edgeTable VALUES( ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, LineFromText(%s, 4326))'%(lineString), (self.edgeId, startRef, endRef, length, wayId, 0, 0, cost, reverseCost, streetInfo))
            self.edgeId=self.edgeId+1
        
    def addPolygonToAreaTable(self, areaType, osmId, tags, adminLevel, polyString):
        self.cursorArea.execute('INSERT OR IGNORE INTO areaTable VALUES( ?, ?, ?, ?, MultiPolygonFromText(%s, 4326))'%(polyString), (osmId, areaType, pickle.dumps(tags), adminLevel))

    def addLineToAreaTable(self, areaType, osmId, tags, adminLevel, lineString):
        self.cursorArea.execute('INSERT OR IGNORE INTO areaLineTable VALUES( ?, ?, ?, ?, LineFromText(%s, 4326))'%(lineString), (osmId, areaType, pickle.dumps(tags), adminLevel))
        
#    def isAreaEntryInDB(self, osmId, areaType):
#        self.cursorArea.execute('SELECT id FROM areaTable WHERE osmId=%d AND type=%d'%(osmId, areaType))
#        allentries=self.cursorArea.fetchall()
#        return len(allentries)!=0
    
    def createSpatialIndexForEdgeTable(self):
        self.cursorEdge.execute('SELECT CreateSpatialIndex("edgeTable", "geom")')

    def createSpatialIndexForAreaTable(self):
        self.cursorArea.execute('SELECT CreateSpatialIndex("areaTable", "geom")')
        self.cursorArea.execute('SELECT CreateSpatialIndex("areaLineTable", "geom")')

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

#    def clearSourceAndTargetOfEdges(self):
#        self.cursorEdge.execute('SELECT id FROM edgeTable')
#        allentries=self.cursorEdge.fetchall()
#        for x in allentries:
#            edgeId=x[0]
#            self.updateSourceOfEdge(edgeId, 0)
#            self.updateTargetOfEdge(edgeId, 0)

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

#    def getTmpWayEntryForId(self, wayId):
#        self.cursorTmp.execute('SELECT * FROM wayTable where wayId=%d'%(wayId))
#        allentries=self.cursorTmp.fetchall()
#        if len(allentries)==1:
#            return self.wayFromTmpDB(allentries[0])
#        
#        return (None, None, None, None, None, None, None)

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
    
#    def getWayEntryForId3(self, wayId):
#        self.cursorGlobal.execute('SELECT * FROM wayTable where wayId=%d'%(wayId))
#        allentries=self.cursorGlobal.fetchall()
#        if len(allentries)==1:
#            return self.wayFromDB3(allentries[0])
#        
#        return (None, None, None, None, None, None, None, None, None)

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
            return self.wayFromDBWithCoordsList(allentries[0])
        
        return (None, None, None, None, None, None, None, None, None)
    
    def getWayEntryForStreetName(self, streetName):
        self.cursorGlobal.execute('SELECT wayId, tags, refs, streetInfo, name, ref, maxspeed, poiList, AsText(geom) FROM wayTable WHERE name="%s"'%(streetName))
        allentries=self.cursorGlobal.fetchall()
        resultList=list()
        for x in allentries:
            resultList.append(self.wayFromDBWithCoordsList(x))
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
        resultList=self.getEdgesAroundPointWithGeom(lat, lon, margin)  
        usedEdgeId=None
        usedWayId=None
        minDistance=maxDistance
        
        for edge in resultList:
            edgeId, _, _, _, wayId, _, _, _, _, _, coords=edge

            lat1, lon1=coords[0]
            for lat2, lon2 in coords[1:]:
                onLine, distance, _=self.isMinimalDistanceOnLineBetweenPoints(lat, lon, lat1, lon1, lat2, lon2, maxDistance)
                if onLine==True:
                    if distance<minDistance:
                        minDistance=distance
                        usedEdgeId=edgeId
                        usedWayId=wayId
                    
                lat1=lat2
                lon1=lon2
                     
        return usedEdgeId, usedWayId
    
    def getEdgeOnPos(self, lat, lon, margin, maxDistance):  
        resultList=self.getEdgesAroundPointWithGeom(lat, lon, margin)  
        usedEdge=None
        minDistance=maxDistance
        
        for edge in resultList:
            _, _, _, _, _, _, _, _, _, _, coords=edge

            lat1, lon1=coords[0]
            for lat2, lon2 in coords[1:]:
                onLine, distance, _=self.isMinimalDistanceOnLineBetweenPoints(lat, lon, lat1, lon1, lat2, lon2, maxDistance)
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
        self.cursorGlobal.execute('SELECT * FROM wayTable WHERE wayId=147462600')
        allentries=self.cursorGlobal.fetchall()
        for x in allentries:
            wayId, tags, refs, streetTypeId, name, nameRef, oneway, roundabout, maxspeed, poiList=self.wayFromDB4(x)
            print( "way: " + str(wayId) + " streetType:"+str(streetTypeId)+ " name:" +str(name) + " ref:"+str(nameRef)+" tags: " + str(tags) + "  refs: " + str(refs) + " oneway:"+str(oneway)+ " roundabout:"+str(roundabout) + " maxspeed:"+str(maxspeed)+" poilist:"+str(poiList))

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
        self.cursorArea.execute('SELECT osmId, type, tags, adminLevel, AsText(geom) FROM areaTable WHERE type=%d'%(Constants.AREA_TYPE_AEROWAY))
        allentries=self.cursorArea.fetchall()
        for x in allentries:
            osmId, areaType, tags, adminLevel, polyStr=self.areaFromDBWithCoordsString(x)
            print("osmId: "+str(osmId)+ " type: "+str(areaType) +" tags: "+str(tags)+ " adminLevel: "+ str(adminLevel)+" polyStr:"+str(polyStr))

        self.cursorArea.execute('SELECT osmId, type, tags, adminLevel, AsText(geom) FROM areaLineTable WHERE type=%d'%(Constants.AREA_TYPE_AEROWAY))
        allentries=self.cursorArea.fetchall()
        for x in allentries:
            osmId, areaType, tags, adminLevel, polyStr=self.areaFromDBWithCoordsString(x)
            print("osmId: "+str(osmId)+ " type: "+str(areaType) +" tags: "+str(tags)+ " adminLevel: "+ str(adminLevel)+" polyStr:"+str(polyStr))

    def dropAreaTable(self):
        self.cursorArea.execute('DROP TABLE areaTable')

    def testCoordsTable(self):
        self.cursorCoords.execute('SELECT * from coordsTable WHERE refId=98110819')
        allentries=self.cursorCoords.fetchall()  
        print(allentries)

    def wayFromDB(self, x):
        wayId=x[0]
        refs=pickle.loads(x[2])
        tags=self.decodeWayTags(x[1])
        streetInfo=x[3]
        streetTypeId, _, _=self.decodeStreetInfo(streetInfo)
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

#    def wayFromDB3(self, x):
#        wayId=x[0]
#        refs=pickle.loads(x[2])
#        tags=self.decodeWayTags(x[1])
#        streetInfo=x[3]
#        streetTypeId, oneway, roundabout=self.decodeStreetInfo(streetInfo)
#        name=x[4]
#        nameRef=x[5]
#        maxspeed=x[6]
#        return (wayId, tags, refs, streetTypeId, name, nameRef, oneway, roundabout, maxspeed)

#    def wayFromTmpDB(self, x):
#        wayId=x[0]
#        refs=pickle.loads(x[2])
#        tags=self.decodeWayTags(x[1])
#        streetInfo=x[3]
#        name=x[4]
#        nameRef=x[5]
#        maxspeed=x[6]
#        return (wayId, tags, refs, streetInfo, name, nameRef, maxspeed)

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
 
    def wayFromDBWithCoordsList(self, x):
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
        coordsStr=x[8]
        coords=self.createCoordsFromLineString(coordsStr)
        
        return (wayId, tags, refs, streetInfo, name, nameRef, maxspeed, poiList, coords)   

    def wayFromDBWithCoordsString(self, x):
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
        coordsStr=x[8]
        
        return (wayId, tags, refs, streetInfo, name, nameRef, maxspeed, poiList, coordsStr)   
    
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

    def areaFromDBWithCoordsString(self, x):
        osmId=x[0]
        areaType=x[1]
        tags=pickle.loads(x[2])  
        adminLevel=x[3]
        polyStr=x[4]
        return (osmId, areaType, tags, adminLevel, polyStr)
        
    def areaFromDB(self, x):
        osmId=x[0]
        areaType=x[1]
        tags=pickle.loads(x[2])  
        adminLevel=x[3]
        return (osmId, areaType, tags, adminLevel)
    
    def isUsableBarierType(self):
        return Constants.BARIER_NODES_TYPE_SET

    def isUsablePlaceNodeType(self):
        return Constants.PLACE_NODES_TYPE_SET
        
    def getHighwayNodeTypeId(self, nodeTag):
        if nodeTag in Constants.HIGHWAY_TYPE_DICT.keys():
            return Constants.HIGHWAY_TYPE_DICT[nodeTag]

        return -1
    
    def getAmenityNodeTypeId(self, nodeTag):
        if nodeTag in Constants.AMENITY_TYPE_DICT.keys():
            return Constants.AMENITY_TYPE_DICT[nodeTag]
        
        return -1

    def getShopNodeTypeId(self, nodeTag):
        if nodeTag in Constants.SHOP_TYPE_DICT.keys():
            return Constants.SHOP_TYPE_DICT[nodeTag]
        
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
            
            if self.skipPOINodes==False:
                if "highway" in tags:
                    nodeType=self.getHighwayNodeTypeId(tags["highway"])
                    if nodeType!=-1:
                        self.addToRefTable(ref, lat, lon, tags, nodeType)
                            
                if "barrier" in tags:
                    if tags["barrier"] in self.isUsableBarierType():
                        self.addToRefTable(ref, lat, lon, tags, Constants.POI_TYPE_BARRIER)
                      
                if "amenity" in tags:
                    nodeType=self.getAmenityNodeTypeId(tags["amenity"])
                    if nodeType!=-1:
                        self.addToRefTable(ref, lat, lon, tags, nodeType)
                        self.nodeList[ref]=nodeType
                
                if "place" in tags:
                    if tags["place"] in self.isUsablePlaceNodeType():
                        self.addToRefTable(ref, lat, lon, tags, Constants.POI_TYPE_PLACE)
 
                if "shop" in tags:
                    nodeType=self.getShopNodeTypeId(tags["shop"])
                    if nodeType!=-1:
                        self.addToRefTable(ref, lat, lon, tags, nodeType)
                        self.nodeList[ref]=nodeType
                
            if self.skipAddress==False:
                if "addr:street" in tags:
                    self.addToRefTable(ref, lat, lon, tags, Constants.POI_TYPE_ADDRESS)
                    refCountry=self.getCountryOfPos(lat, lon)
                    if refCountry!=None:
                        if self.parseFullAddress(tags, ref, lat, lon, refCountry):
                            self.nodeList[ref]=Constants.POI_TYPE_ADDRESS
                        

    def parse_coords(self, coord):
        if self.skipCoords==True:
            return
        
        for osmid, lon, lat in coord:
            self.addToCoordsTable(osmid, float(lat), float(lon))
           
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
#        if "addr:city" in tags:
#            city=tags["addr:city"]
        if "addr:housenumber" in tags:
            houseNumber=tags["addr:housenumber"]
#        if "addr:postcode" in tags:
#            postCode=tags["addr:postcode"]
        if "addr:street" in tags:
            streetName=tags["addr:street"]

        if streetName==None:
            return False
        if houseNumber==None:
            return False
        
        # rest of info is filled later on from admin boundaries
        self.addToAddressTable(refId, country, city, postCode, streetName, houseNumber, lat, lon)
        return True
    
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
        if streetType in Constants.STREET_TYPE_DICT.keys():
            return Constants.STREET_TYPE_DICT[streetType]

        return -1

    def getRequiredWayTags(self):
        return Constants.REQUIRED_HIGHWAY_TAGS_SET

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
        
    def getWaterwayTypes(self):
        return Constants.WATERWAY_TYPE_SET

    def getNaturalTypes(self):
        return Constants.NATURAL_TYPE_SET

    def getLanduseTypes(self):
        return Constants.LANDUSE_TYPE_SET
            
    def getBoundaryTypes(self):
        return Constants.BOUNDARY_TYPE_SET
    
    def getRailwayTypes(self):
        return Constants.RAILWAY_TYPE_SET

    def getAerowayTypes(self):
        return Constants.AEROWAY_TYPE_SET
    
    def isNodeDefined(self, refs, nodeType):
        for ref in refs:
            if ref in self.nodeList.keys():
                if self.nodeList[ref]==nodeType:
                    return True
        return False
    
    def parse_ways(self, way):
        if self.skipWays==True:
            return 
        
        if self.firstWay==False:
            self.firstWay=True
            print("Parsing ways...")
            
        for wayid, tags, refs in way:
            if len(refs)<2:
                print("way with len(ref)<2 %d"%(wayid))
                continue
            
            isBuilding=False
            isLanduse=False
            isNatural=False
            isRailway=False
            isAeroway=False
                       
            if "building" in tags:
                if self.skipAddress==False:
                    if "addr:street" in tags:
                        if not self.isNodeDefined(refs, Constants.POI_TYPE_ADDRESS):
                            # TODO: use first ref as location for addr?
                            # may use entrance node
                            storedRef, lat, lon=self.getCoordsEntry(refs[0])
                            if storedRef!=None:
                                if lat!=None and lon!=None:
                                    self.addToRefTable(refs[0], lat, lon, tags, Constants.POI_TYPE_ADDRESS)
                                    refCountry=self.getCountryOfPos(lat, lon)
                                    if refCountry!=None:
                                        self.parseFullAddress(tags, refs[0], lat, lon, refCountry)
                        
            if "amenity" in tags:
                if self.skipPOINodes==False:
                    nodeType=self.getAmenityNodeTypeId(tags["amenity"])
                    if nodeType!=-1:
                        if not self.isNodeDefined(refs, nodeType):
                            # TODO: use first ref as location for amenity?
                            # may use entrance node
                            storedRef, lat, lon=self.getCoordsEntry(refs[0])
                            if storedRef!=None:
                                self.addToRefTable(storedRef, lat, lon, tags, nodeType)

            if "shop" in tags:
                if self.skipPOINodes==False:
                    nodeType=self.getShopNodeTypeId(tags["shop"])
                    if nodeType!=-1:
                        if not self.isNodeDefined(refs, nodeType):
                            # TODO: use first ref as location for amenity?
                            # may use entrance node
                            storedRef, lat, lon=self.getCoordsEntry(refs[0])
                            if storedRef!=None:
                                self.addToRefTable(storedRef, lat, lon, tags, nodeType)

            if not "highway" in tags:    
                if self.skipAreas==False:         
                    # TODO: do we miss any waterways then?
                    if "boundary" in tags:
                        if tags["boundary"] in self.getBoundaryTypes():
                            self.addToWayRefTable(wayid, refs)
                            continue
    
                    if "waterway" in tags:
                        if tags["waterway"] in self.getWaterwayTypes():
                            isNatural=True
                                                
                    if "natural" in tags:
                        if tags["natural"] in self.getNaturalTypes():
                            isNatural=True
                        
                    if "landuse" in tags:
                        if tags["landuse"] in self.getLanduseTypes():
                            isLanduse=True
                                                   
                    if "railway" in tags:
                        if tags["railway"] in self.getRailwayTypes():
                            isRailway=True
                              
                    if "aeroway" in tags:
                        if tags["aeroway"] in self.getAerowayTypes():
                            isAeroway=True
                        
                    if "building" in tags:
                        isBuilding=True
                        isLanduse=False
                        isNatural=False
                        isRailway=False
                        isAeroway=False
               
                    if isAeroway==False and isBuilding==False and isLanduse==False and isNatural==False and isRailway==False:
                        continue
                    
                    isPolygon=False
                    if refs[0]==refs[-1]:
                        isPolygon=True
                        
                    coords, newRefList=self.createRefsCoords(refs)
                    if isPolygon==True:
                        if len(coords)<3:
                            print("parse_ways: skipping polygon area %d %s len(coords)<3"%(wayid, refs))
                            continue
                    else:
                        if len(coords)<2:
                            print("parse_ways: skipping line area %d %s len(coords)<2"%(wayid, refs))
                            continue
                    
                    # TODO: skip complete area if coords are missing?
                    # e.g. waterway=riverbank ist missing then for Salzach
    #                if len(refs)==len(newRefList):
                    if isPolygon==True:
                        geomString=self.createMultiPolygonFromCoords(coords)
                    else:
                        geomString=self.createLineStringFromCoords(coords)
                        
                    areaType=None
                    if isNatural==True:
                        areaType=Constants.AREA_TYPE_NATURAL
                    elif isLanduse==True:
                        areaType=Constants.AREA_TYPE_LANDUSE
                    elif isBuilding==True:
                        areaType=Constants.AREA_TYPE_BUILDING
                    elif isRailway==True:
                        areaType=Constants.AREA_TYPE_RAILWAY
                    elif isAeroway==True:
                        areaType=Constants.AREA_TYPE_AEROWAY
                        
                    if areaType!=None:
                        if isPolygon==True:
                            self.addPolygonToAreaTable(areaType, wayid, tags, None, geomString)
                        else:
                            self.addLineToAreaTable(areaType, wayid, tags, None, geomString)
                        
            # highway
            else:             
                streetType=tags["highway"]
                                                                 
                streetTypeId=self.getStreetTypeId(streetType)
                if streetTypeId==-1:
                    continue
                
                if "area" in tags:
                    if self.skipAreas==False:         
                        if tags["area"]=="yes":
                            if refs[0]==refs[-1]:                                
                                coords, newRefList=self.createRefsCoords(refs)
                                if len(coords)<2:
                                    print("parse_ways: skipping area %d %s len(coords)<2"%(wayid, refs))
                                    continue
                    
                                geomString=self.createMultiPolygonFromCoords(coords)
                                self.addPolygonToAreaTable(Constants.AREA_TYPE_HIGHWAY_AREA, wayid, tags, None, geomString)
                            
                            continue
                
                if self.skipHighways==False:
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
                            oneway=2
                    if "junction" in tags:
                        if tags["junction"]=="roundabout":
                            roundabout=1
                    
#                    if roundabout==0:
#                        if refs[0]==refs[-1]:
#                            print("highway + closed: %d %s"%(wayid, tags))
                    

                    tunnel=0
                    if "tunnel" in tags:
                        if tags["tunnel"]=="yes":
                            tunnel=1
                    
                    bridge=0
                    if "bridge" in tags:
                        if tags["bridge"]=="yes":
                            bridge=1
                            
                    maxspeed=self.getMaxspeed(tags, streetTypeId)
                        
                    for ref in refs:  
                        storedRef, lat, lon=self.getCoordsEntry(ref)
                        if storedRef==None:
                            continue
    
                        self.addToRefTable(ref, lat, lon, None, 0)
                        self.addToTmpRefWayTable(ref, wayid)
                    
                    coords, newRefList=self.createRefsCoords(refs)
                    if len(coords)>=2:
                        requiredTags=self.stripUnneededTags(tags)
                        self.addToWayTable(wayid, requiredTags, newRefList, streetTypeId, name, nameRef, oneway, roundabout, maxspeed, tunnel, bridge, coords)   
                    else:
                        print("parse_ways: skipping way %d %s len(coords)<2"%(wayid, refs))

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
                    isBuilding=False
                    isLanduse=False
                    isNatural=False
                    isAdminBoundary=False
                    isAeroway=False
                    
                    if "boundary" in tags:
                        if tags["boundary"] in self.getBoundaryTypes():
                            isAdminBoundary=True
                        
                    if "waterway" in tags:
                        if tags["waterway"] in self.getWaterwayTypes():
                            isNatural=True
                            
                    if "natural" in tags:
                        if tags["natural"] in self.getNaturalTypes():
                            isNatural=True
                            
                    if "landuse" in tags:
                        if tags["landuse"] in self.getLanduseTypes():
                            isLanduse=True
                    
                    if "aeroway" in tags:
                        if tags["aeroway"] in self.getAerowayTypes():
                            isAeroway=True
                              
                    if "building" in tags:
                        isBuilding=True
                        isLanduse=False
                        isNatural=False
                        isAdminBoundary=False
                        isAeroway=False
                        
                    if isAeroway==False and isAdminBoundary==False and isBuilding==False and isLanduse==False and isNatural==False:
                        continue
                    
#                    print("multipolygon: %s"%(tags))
                    
                    # (59178604, 'way', 'outer')
                    allRefs=list()

                    for way in ways:
                        memberType=way[1]
                        relationWayId=int(way[0])
                        role=way[2]
                        
                        if role=="outer" and memberType=="way":
                            # from boundary way table
                            wayId, refs=self.getWayRefEntry(relationWayId)
                            if wayId!=None:
                                allRefs.append((wayId, refs, 0, 0))
                            else:
                                # from "real" way table
                                wayId, _, refs, _, _, _, oneway, roundabout=self.getWayEntryForId2(relationWayId)
                                if wayId!=None:
                                    allRefs.append((wayId, refs, oneway, roundabout))
                                            
                    if len(allRefs)!=0:
                        refRings=self.mergeWayRefs(allRefs)
                        if len(refRings)!=0:
                            skipArea=False
                            # convert to multipolygon
                            polyString="'MULTIPOLYGON("
                            for refRingEntry in refRings:                                
                                refs=refRingEntry["refs"]
                                if refs[0]!=refs[-1]:
                                    skipArea=True
                                    break

                                coords, newRefList=self.createRefsCoords(refs)
                                # TODO: skip complete area if coords are missing?
                                if len(refs)==len(newRefList):
                                    polyStringPart=self.createMultiPolygonPartFromCoords(coords)
                                else:
                                    skipArea=True
                                    break
                                
                                polyString=polyString+polyStringPart
                                                                
                            polyString=polyString[:-1]
                            polyString=polyString+")'"

                            # TODO: skip complete relation if coords are missing?
                            if skipArea==False:
                                if isAdminBoundary==True:
                                    adminLevel=None
                                    if "admin_level" in tags:
                                        adminLevel=tags["admin_level"]
                                    self.addPolygonToAreaTable(Constants.AREA_TYPE_ADMIN, osmid, tags, adminLevel, polyString)
                                elif isNatural==True:
                                    self.addPolygonToAreaTable(Constants.AREA_TYPE_NATURAL, osmid, tags, None, polyString)
                                elif isLanduse==True:
                                    self.addPolygonToAreaTable(Constants.AREA_TYPE_LANDUSE, osmid, tags, None, polyString)
                                elif isBuilding==True:  
                                    self.addPolygonToAreaTable(Constants.AREA_TYPE_BUILDING, osmid, tags, None, polyString)
                                elif isAeroway==True:
                                    self.addPolygonToAreaTable(Constants.AREA_TYPE_AEROWAY, osmid, tags, None, polyString)

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
                                    storedRefId, _, _, _, _=self.getRefEntryForId(fromRefId)
                                    if storedRefId!=None:
                                        tags["deviceRef"]=deviceRef
                                        self.updateRefTableEntry(storedRefId, tags, Constants.POI_TYPE_ENFORCEMENT_WAYREF)
           
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
            
        return refRings
    
    def getStreetNameInfo(self, tags, streetTypeId):

        name=None
        ref=None
#        intref=None
        
        if "name" in tags:
            name=tags["name"]
        
        if "ref" in tags:
            ref=tags["ref"]
            
#        if "int_ref" in tags:
#            intref=tags["int_ref"]
            
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
        storedRef, wayIdList=self.getTmpRefWayEntryForId(ref)
        if storedRef!=None:
            return wayIdList
        
        return None
        
    def getCoordsWithRef(self, refId):
        storedRefId, lat, lon, _, _=self.getRefEntryForId(refId)
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
        storedRefId, lat1, lon1, _, _=self.getRefEntryForId(ref1)
        if storedRefId==None:
            return False
        storedRefId, lat2, lon2, _, _=self.getRefEntryForId(ref2)
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
    
    def getPOIListOnWay(self, wayId):  
        poiList=list()      
        wayId, _, _, _, _, _, _, _, _, storedPoiList=self.getWayEntryForId4(wayId)
        if wayId!=None:
            if storedPoiList!=None:
                for _, deviceRef, nodeType in storedPoiList:
                    # enforcement
                    if nodeType==Constants.POI_TYPE_ENFORCEMENT_WAYREF:
                        deviceRef, lat, lon, storedTags, _=self.getRefEntryForId(deviceRef)
                        if deviceRef!=None:
                            enforcement=dict()
                            enforcement["type"]="enforcement"
                            enforcement["coords"]=(lat, lon)
                            if storedTags!=None and "maxspeed" in storedTags:
                                enforcement["info"]="maxspeed:%s"%(storedTags["maxspeed"])
                            poiList.append(enforcement)
                    
                    if nodeType==Constants.POI_TYPE_BARRIER:
                        barrier=dict()
                        barrier["type"]="barrier"
                        barrier["coords"]=(lat, lon)
                        poiList.append(barrier)

        if len(poiList)!=0:
            return poiList
        
        return None
    
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
                (lastName, _)=lastTrackItem["info"]
            
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
        
        allWaysLength=len(allWays)
        allWaysCount=0

        prog = ProgressBar(0, allWaysLength, 77)
        
        for way in allWays:
            prog.updateAmount(allWaysCount)
            print(prog, end="\r")
            allWaysCount=allWaysCount+1

            self.createEdgeTableEntriesForWay(way)

        print("")
        
    def createEdgeTableNodeEntries(self):
        self.cursorEdge.execute('SELECT id FROM edgeTable')
        allEdges=self.cursorEdge.fetchall()
        
        allEdgesLength=len(allEdges)
        allEdgesCount=0

        prog = ProgressBar(0, allEdgesLength, 77)
                
        for edgeEntryId in allEdges:   
            prog.updateAmount(allEdgesCount)
            print(prog, end="\r")
            allEdgesCount=allEdgesCount+1
             
            edgeId=edgeEntryId[0]
            edge=self.getEdgeEntryForEdgeId(edgeId)
            self.createEdgeTableNodeSameStartEnriesFor(edge)
            
            edge=self.getEdgeEntryForEdgeId(edgeId)
            self.createEdgeTableNodeSameEndEnriesFor(edge)

            edge=self.getEdgeEntryForEdgeId(edgeId)
            self.createEdgeTableNodeSourceEnriesFor(edge)

        self.cursorEdge.execute('SELECT id FROM edgeTable WHERE source==0 OR target==0')
        allEdges=self.cursorEdge.fetchall()
        
        allEdgesLength=len(allEdges)
        allEdgesCount=0

        prog = ProgressBar(0, allEdgesLength, 77)
        
        for edgeEntryId in allEdges:
            prog.updateAmount(allEdgesCount)
            print(prog, end="\r")
            allEdgesCount=allEdgesCount+1

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
                
        print("")
        
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
    
    def isAccessRestricted(self, tags):
        if "vehicle" in tags:
            if tags["vehicle"]=="private":
                return True
            if tags["vehicle"]=="no":
                return True

        if "motorcar" in tags:
            if tags["motorcar"]=="private":
                return True
            if tags["motorcar"]=="no":
                return True
                
        if "motor_vehicle" in tags:
            if tags["motor_vehicle"]=="private":
                return True
            if tags["motor_vehicle"]=="no":
                return True
            
        if "access" in tags:
            if tags["access"]=="private":
                return True
            if tags["access"]=="no":
                return True

        return False
    
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
        wayId, tags, refs, streetInfo, _, _, maxspeed, _=self.wayFromDB5(way)
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
                    coords, _=self.createRefsCoords(refList)
                    if len(coords)>=2:
                        cost, reverseCost=self.getCostsOfWay(wayId, tags, refs, distance, crossingFactor, streetInfo, maxspeed)                                         
                        self.addToEdgeTable(startRef, endRef, distance, wayId, cost, reverseCost, streetInfo, coords)
#                    else:
#                        print("createEdgeTableEntriesForWay: skipping wayId %d from %d to %d len(coords)<2"%(wayId, startRef, endRef))

                    refNodeList=list()
                    distance=0
           
            refNodeList.append(ref)
        
        # handle last portion
        if not ref in doneRefs:
            if len(refNodeList)!=0:
                startRef=refNodeList[0]
                endRef=refNodeList[-1]
                
                refList=self.getRefListSubset(refs, startRef, endRef)
                coords, _=self.createRefsCoords(refList)                
                if len(coords)>=2:
                    cost, reverseCost=self.getCostsOfWay(wayId, tags, refs, distance, crossingFactor, streetInfo, maxspeed)                    
                    self.addToEdgeTable(startRef, endRef, distance, wayId, cost, reverseCost, streetInfo, coords)
#                else:
#                    print("createEdgeTableEntriesForWay: skipping wayId %d from %d to %d len(coords)<2"%(wayId, startRef, endRef))

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
                # TODO: skip complete way if coords are missing?
                continue
            
        return coords, newRefList
    
    def createLineStringFromCoords(self, coords):
        lineString="'LINESTRING("
        coordString=''.join(["%f %f"%(lon, lat)+"," for lat, lon in coords])    
        coordString=coordString[:-1]
        lineString=lineString+coordString+")'"
        return lineString
    
    def createCoordsFromLineString(self, lineString):
        coords=list()
        coordsStr=lineString[11:-1]
        x=re.findall(r'[0-9\.]+|[^0-9\.]+', coordsStr)
        i=0
        while i<len(x)-2:
            coords.append((float(x[i+2]), float(x[i])))
            i=i+4
            
#        coordsPairs=coordsStr.split(",")
#        for coordPair in coordsPairs:
#            coordPair=coordPair.lstrip().rstrip()
#            lon, lat=coordPair.split(" ")
#            coords.append((float(lat), float(lon)))
            
        return coords

    def createCoordsFromMultiPolygon(self, coordsStr):
        allCoordsList=list()
        coordsStr=coordsStr[15:-3]
        polyParts=coordsStr.split(")), ((")
        if len(polyParts)==1:
            poly=coordsStr
            coords=list()
            x=re.findall(r'[0-9\.]+|[^0-9\.]+', poly)
            i=0
            while i<len(x)-2:
                coords.append((float(x[i+2]), float(x[i])))
                i=i+4

#            coordsList=poly.split(',')
#            for coordPair in coordsList:
#                coordPair=coordPair.lstrip().rstrip()
#                lon, lat=coordPair.split(" ")
#                coords.append((float(lat), float(lon)))
            allCoordsList.append(coords)
        else:
            for poly in polyParts:
                coords=list()
                x=re.findall(r'[0-9\.]+|[^0-9\.]+', poly)
                i=0
                while i<len(x)-2:
                    coords.append((float(x[i+2]), float(x[i])))
                    i=i+4
                    
#                coordsList=poly.split(',')
#                for coordPair in coordsList:
#                    coordPair=coordPair.lstrip().rstrip()
#                    lon, lat=coordPair.split(" ")
#                    coords.append((float(lat), float(lon)))
                
                allCoordsList.append(coords)
        
        return allCoordsList
    
    def createMultiPolygonFromCoords(self, coords):
        polyString="'MULTIPOLYGON((("
        coordString=''.join(["%f %f"%(lon, lat)+"," for lat, lon in coords])    
        coordString=coordString[:-1]
        polyString=polyString+coordString+")))'"        
        return polyString

    def createMultiPolygonPartFromCoords(self, coords):
        polyString="(("
        coordString=''.join(["%f %f"%(lon, lat)+"," for lat, lon in coords])    
        coordString=coordString[:-1]
        polyString=polyString+coordString+")),"                
        return polyString
        
    def isLinkToLink(self, streetTypeId, streetTypeId2):
        return (streetTypeId==Constants.STREET_TYPE_MOTORWAY_LINK and streetTypeId2==Constants.STREET_TYPE_MOTORWAY_LINK) or (streetTypeId==Constants.STREET_TYPE_TRUNK_LINK and streetTypeId2==Constants.STREET_TYPE_TRUNK_LINK) or (streetTypeId==Constants.STREET_TYPE_PRIMARY_LINK and streetTypeId2==Constants.STREET_TYPE_PRIMARY_LINK) or (streetTypeId==Constants.STREET_TYPE_SECONDARY_LINK and streetTypeId2==Constants.STREET_TYPE_SECONDARY_LINK) or (streetTypeId==Constants.STREET_TYPE_TERTIARY_LINK and streetTypeId2==Constants.STREET_TYPE_TERTIARY_LINK)

    def isLinkEnter(self, streetTypeId, streetTypeId2):
        return (streetTypeId!=Constants.STREET_TYPE_MOTORWAY_LINK and streetTypeId2==Constants.STREET_TYPE_MOTORWAY_LINK) or (streetTypeId!=Constants.STREET_TYPE_TRUNK_LINK and streetTypeId2==Constants.STREET_TYPE_TRUNK_LINK) or (streetTypeId!=Constants.STREET_TYPE_PRIMARY_LINK and streetTypeId2==Constants.STREET_TYPE_PRIMARY_LINK) or (streetTypeId!=Constants.STREET_TYPE_SECONDARY_LINK and streetTypeId2==Constants.STREET_TYPE_SECONDARY_LINK) or (streetTypeId!=Constants.STREET_TYPE_TERTIARY_LINK and streetTypeId2==Constants.STREET_TYPE_TERTIARY_LINK)

    def isLinkExit(self, streetTypeId, streetTypeId2):
        return (streetTypeId==Constants.STREET_TYPE_MOTORWAY_LINK and streetTypeId2!=Constants.STREET_TYPE_MOTORWAY_LINK) or (streetTypeId==Constants.STREET_TYPE_TRUNK_LINK and streetTypeId2!=Constants.STREET_TYPE_TRUNK_LINK) or (streetTypeId==Constants.STREET_TYPE_PRIMARY_LINK and streetTypeId2!=Constants.STREET_TYPE_PRIMARY_LINK) or (streetTypeId==Constants.STREET_TYPE_SECONDARY_LINK and streetTypeId2!=Constants.STREET_TYPE_SECONDARY_LINK) or (streetTypeId==Constants.STREET_TYPE_TERTIARY_LINK and streetTypeId2!=Constants.STREET_TYPE_TERTIARY_LINK)

    def createCrossingEntries(self):
        self.cursorGlobal.execute('SELECT * FROM wayTable')
        allWays=self.cursorGlobal.fetchall()
        
        allWaysLength=len(allWays)
        allWaysCount=0

        prog = ProgressBar(0, allWaysLength, 77)
        for way in allWays:
            wayid, tags, refs, streetTypeId, name, nameRef, oneway, roundabout=self.wayFromDB2(way)    
  
            prog.updateAmount(allWaysCount)
            print(prog, end="\r")
            allWaysCount=allWaysCount+1

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
        
        print("")
        self.dropTmpTable()
        
    def createPOIEntriesForWays(self):
        self.cursorGlobal.execute('SELECT * FROM wayTable')
        allWays=self.cursorGlobal.fetchall()
        
        allWaysLength=len(allWays)
        allWaysCount=0

        prog = ProgressBar(0, allWaysLength, 77)
        
        for way in allWays:
            wayId, _, refs, _, _, _, _, _, _, poiList=self.wayFromDB4(way)    
            
            prog.updateAmount(allWaysCount)
            print(prog, end="\r")
            allWaysCount=allWaysCount+1

            if poiList==None:
                poiList=list()
            
            for ref in refs:
                storedRefId, _, _, tags, nodeTypeList=self.getRefEntryForId(ref)
                if storedRefId!=None:
                    if nodeTypeList!=None:
                        if Constants.POI_TYPE_ENFORCEMENT_WAYREF in nodeTypeList:
                            # enforcement
                            if tags!=None and "deviceRef" in tags:
                                deviceRef=tags["deviceRef"]
                                if not (ref, deviceRef, Constants.POI_TYPE_ENFORCEMENT_WAYREF) in poiList:
                                    poiList.append((ref, deviceRef, Constants.POI_TYPE_ENFORCEMENT_WAYREF))
                            else:
                                deviceRef=ref
                                if not (ref, deviceRef, Constants.POI_TYPE_ENFORCEMENT_WAYREF) in poiList:
                                    poiList.append((ref, deviceRef, Constants.POI_TYPE_ENFORCEMENT_WAYREF))
                        
                        if Constants.POI_TYPE_BARRIER in nodeTypeList:
                            # barrier
                            poiList.append((ref, ref, Constants.POI_TYPE_BARRIER))
                            
            if len(poiList)!=0:
                self.updateWayTableEntryPOIList(wayId, poiList)
            
        print("")
            
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
        return os.path.join(env.getDataRoot(), "data2")

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
    
    def getTmpDBFile(self):
        file="tmp.db"
        return os.path.join(self.getDataDir(), file)
        
    def deleteCoordsDBFile(self):
        if os.path.exists(self.getCoordsDBFile()):
            os.remove(self.getCoordsDBFile())

    def deleteTmpDBFile(self):
        if os.path.exists(self.getTmpDBFile()):
            os.remove(self.getTmpDBFile())
            
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

    def tmpDBExists(self):
        return os.path.exists(self.getTmpDBFile())
    
    def initGraph(self):                     
        if self.dWrapperTrsp==None:
            self.dWrapperTrsp=TrspWrapper(self.getDataDir())

    def initDB(self):
        print(self.getDataDir())
        
#        self.openCoordsDB()
#        self.createCoordsDBTables()
        
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

        self.openTmpDB()
        self.createTmpTable()
        
#        createTmpWayDB=not self.tmpDBExists()
#        if createTmpWayDB:
#            self.openTmpDB()
#            self.createTmpTable()
#        else:
#            self.openTmpDB()

        if createGlobalDB==True:
            self.skipNodes=False
            self.skipWays=False
            self.skipCoords=False
            self.skipRelations=False
            self.skipAddress=False
            self.skipHighways=False
            self.skipAreas=False
            self.skipPOINodes=False
            
            countryList=self.osmList.keys()
            for country in countryList:       
                self.firstWay=False
                self.firstRelation=False
                self.firstNode=False   
  
                print(self.osmList[country])
                print("start parsing")
                self.parse(country)
                print("end parsing")
                self.commitGlobalDB()
                self.commitAdressDB()
            
            self.commitCoordsDB()
                            
#            print("merge ways")
#            self.mergeWayEntries()
#            print("end merge ways")
                                                     
#            print("create POI entries")
#            self.createPOIEntriesForWays()
         
            print("create crossings")
            self.createCrossingEntries()
            
            self.commitGlobalDB()
            
        if createEdgeDB:            
            print("create edges")
            self.createEdgeTableEntries()

            print("create edge nodes")
            self.createEdgeTableNodeEntries()
                        
            print("create way restrictions")
            self.createWayRestrictionsDB()              
            print("end create way restrictions")

            print("remove orphaned edges")
            self.removeOrphanedEdges()
            self.commitEdgeDB()

            print("remove orphaned ways")
            self.removeOrphanedWays()
            self.commitGlobalDB()
            
            print("vacuum global DB")
            self.vacuumGlobalDB()
            print("end vacuum global DB")

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

        if createAdressDB==True:
            self.resolveAddresses()
            self.commitAdressDB()
            self.vacuumAddressDB()
            
        self.initGraph() 
        self.closeCoordsDB(False)
        self.closeTmpDB(False)
        self.closeAllDB()

    def parseAreas(self):
        self.skipWays=False
        self.skipNodes=True
        self.skipRelations=False
        self.skipAddress=True
        self.skipHighways=True
        self.skipCoords=True
        self.skipAreas=False
        self.skipPOINodes=True
        
        countryList=self.osmList.keys()
        for country in countryList:       
            self.firstRelation=False
            self.firstWay=False
            self.firstNode=False   
            
            print(self.osmList[country])
            print("start parsing")
            self.parse(country)
            print("end parsing")
                
        self.commitAreaDB()

    def parseNodes(self):
        self.skipWays=True
        self.skipNodes=False
        self.skipRelations=True
        self.skipAddress=True
        self.skipHighways=True
        self.skipCoords=True
        self.skipAreas=True
        self.skipPOINodes=False
        
        countryList=self.osmList.keys()
        for country in countryList:       
            self.firstRelation=False
            self.firstWay=False
            self.firstNode=False   
            
            print(self.osmList[country])
            print("start parsing")
            self.parse(country)
            print("end parsing")
                
        self.commitGlobalDB()
    
    def parseAddresses(self):
        self.skipWays=False
        self.skipNodes=False
        self.skipRelations=True
        self.skipAddress=False
        self.skipHighways=True
        self.skipCoords=True
        self.skipAreas=True
        self.skipPOINodes=True
        
        countryList=self.osmList.keys()
        for country in countryList:       
            self.firstRelation=False
            self.firstWay=False
            self.firstNode=False   
            
            print(self.osmList[country])
            print("start parsing")
            self.parse(country)
            print("end parsing")
                
        self.commitAdressDB()
        
    def initBoarders(self):
        self.bu=OSMBoarderUtils(self.getDataDir())
        self.bu.initData()
        
    def countryNameOfPoint(self, lat, lon):
        country=self.bu.countryNameOfPoint(lat, lon)
        return country
    
    def countryNameOfPointDeep(self, lat, lon):
        country=self.bu.countryNameOfPoint(lat, lon)
        if country==None:
            # HACK if the point is exactly on the border:(
            country=self.bu.countryNameOfPoint(lat+0.0001, lon+0.0001)
        return country
    
    def getOSMDataInfo(self):
        osmDataList=dict()
        osmData=dict()
        osmData["country"]="Austria"
        osmData["osmFile"]='/home/maxl/Downloads/geofabrik/austria.osm.bz2'
#        osmData["osmFile"]='/home/maxl/Downloads/cloudmade/salzburg-2.osm'
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
        self.createEdgeTable()
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

    def getStreetTypeIdForAddesses(self):
        return Constants.ADDRESS_STREET_SET
    
    def resolveAddresses(self):
        print("resolve addresses from admin boundaries")
        self.addressId=self.getLenOfAddressTable()
        adminLevelList=[4, 6, 8]
        self.cursorAdress.execute('SELECT * FROM addressTable')
        allentries=self.cursorAdress.fetchall()
        
        allAddressLength=len(allentries)
        allAddressCount=0

        prog = ProgressBar(0, allAddressLength, 77)
        
        for x in allentries:
            addressId, refId, country, _, postCode, streetName, houseNumber, lat, lon=self.addressFromDB(x)
            
            prog.updateAmount(allAddressCount)
            print(prog, end="\r")
            allAddressCount=allAddressCount+1
            
            resultList=self.getAdminAreasOnPointWithGeom(lat, lon, 0.0, adminLevelList, True)
            resultList.reverse()
            for area in resultList:
                tags=area[2]
                adminCity=tags["name"]
                self.replaceInAddressTable(addressId, refId, country, adminCity, postCode, streetName, houseNumber, lat, lon)
                break
            
        print("")
        
        print("add all ways to address DB")
        self.cursorGlobal.execute('SELECT * FROM wayTable')
        allWays=self.cursorGlobal.fetchall()
        
        allWaysLength=len(allWays)
        allWaysCount=0

        prog = ProgressBar(0, allWaysLength, 77)
        
        addressSet=set()
        for way in allWays:
            _, _, refs, streetTypeId, name, _, _, _, _, _=self.wayFromDB4(way)    
            
            prog.updateAmount(allWaysCount)
            print(prog, end="\r")
            allWaysCount=allWaysCount+1
            
            if name==None:
                continue
            
            if not streetTypeId in self.getStreetTypeIdForAddesses():
                continue
            
            # TODO: which ref to use for way address
            # could be somewhere in the middle 
            refId, lat, lon=self.getCoordsEntry(refs[0])

            if refId!=None:
                refCountry=self.getCountryOfPos(lat, lon)
                resultList=self.getAdminAreasOnPointWithGeom(lat, lon, 0.0, adminLevelList, False)
                resultList.reverse()
                for area in resultList:
                    tags=area[2]
                    adminCity=tags["name"]
                    if not "%s-%s"%(name, adminCity) in addressSet:
                        self.addToAddressTable(refId, refCountry, adminCity, None, name, None, lat, lon)
                        addressSet.add("%s-%s"%(name, adminCity))
                    break
                    
        print("")
        
    def vacuumEdgeDB(self):
        self.cursorEdge.execute('VACUUM')

    def vacuumGlobalDB(self):
        self.cursorGlobal.execute('VACUUM')

    def vacuumAddressDB(self):
        self.cursorAdress.execute('VACUUM')
                        
    def removeOrphanedEdges(self):
        self.cursorEdge.execute('SELECT * FROM edgeTable')
        allEdges=self.cursorEdge.fetchall()
        
        allEdgesLength=len(allEdges)
        allEdgesCount=0

        prog = ProgressBar(0, allEdgesLength, 77)
        
        for edge in allEdges:
            prog.updateAmount(allEdgesCount)
            print(prog, end="\r")
            allEdgesCount=allEdgesCount+1

            edgeId, startRef, endRef, length, wayId, source, target, cost, reverseCost=self.edgeFromDB(edge)
            resultList1=self.getEdgeEntryForSource(target)
            resultList2=self.getEdgeEntryForTarget(source)
            resultList3=self.getEdgeEntryForSource(source)
            resultList4=self.getEdgeEntryForTarget(target)
            if len(resultList1)==0 and len(resultList2)==0 and len(resultList3)==1 and len(resultList4)==1:
#                print("remove edge %d %d %d %d"%(edgeId, wayId, startRef, endRef))
                self.cursorEdge.execute('DELETE FROM edgeTable WHERE id=%d'%(edgeId))
        
        print("")
        
    def removeOrphanedWays(self):
        self.cursorGlobal.execute('SELECT * FROM wayTable')
        allWays=self.cursorGlobal.fetchall()
        
        allWaysLength=len(allWays)
        allWaysCount=0

        prog = ProgressBar(0, allWaysLength, 77)
        for way in allWays:
            wayid, tags, refs, streetTypeId, name, nameRef, oneway, roundabout=self.wayFromDB2(way)    

            prog.updateAmount(allWaysCount)
            print(prog, end="\r")
            allWaysCount=allWaysCount+1

            resultList=self.getEdgeEntryForWayId(wayid)
            if len(resultList)==0:
                for ref in refs:
                    self.cursorGlobal.execute('DELETE FROM refTable WHERE refId=%d'%(ref))
                    
                self.cursorGlobal.execute('DELETE FROM wayTable WHERE wayId=%d'%(wayid))
                
        print("")

        
    def recreateCostsForEdges(self):
        print("recreate costs")
        self.cursorEdge.execute('SELECT * FROM edgeTable')
        allEdges=self.cursorEdge.fetchall()
        
        allEdgesLength=len(allEdges)
        allEdgesCount=0

        prog = ProgressBar(0, allEdgesLength, 77)
        
        for edge in allEdges:
            prog.updateAmount(allEdgesCount)
            print(prog, end="\r")
            allEdgesCount=allEdgesCount+1
            
            edgeId, startRef, endRef, length, wayId, source, target, cost, reverseCost=self.edgeFromDB(edge)
            wayId, tags, refs, streetTypeId, name, nameRef, oneway, roundabout, maxspeed, poiList=self.getWayEntryForId4(wayId)
            if wayId==None:
                continue
            cost, reverseCost=self.getCostsOfWay(wayId, tags, refs, length, 1, streetTypeId, oneway, roundabout, maxspeed)
            self.updateCostsOfEdge(edgeId, cost, reverseCost)

        print("")
                      
    def testEdgeTableGeom(self):
        self.cursorEdge.execute('SELECT AsText(geom) FROM edgeTable')
        allentries=self.cursorEdge.fetchall()
        for x in allentries:
            print(x)
                   
    def createBBoxAroundPoint(self, lat, lon, margin):
        latRangeMax=lat+margin
        lonRangeMax=lon+margin*1.4
        latRangeMin=lat-margin
        lonRangeMin=lon-margin*1.4          
        
        return lonRangeMin, latRangeMin, lonRangeMax, latRangeMax
    
    def createBBoxWithMargin(self, bbox, margin):
        latRangeMax=bbox[3]+margin
        lonRangeMax=bbox[2]+margin
        latRangeMin=bbox[1]-margin
        lonRangeMin=bbox[0]-margin  

        return lonRangeMin, latRangeMin, lonRangeMax, latRangeMax
        
    def getNodesInBBoxWithGeom(self, bbox, margin, nodeTypeList):
        lonRangeMin, latRangeMin, lonRangeMax, latRangeMax=self.createBBoxWithMargin(bbox, margin)      

        self.cursorGlobal.execute('SELECT refId, tags, type, AsText(geom) FROM refTable WHERE type IS NOT NULL AND ROWID IN (SELECT rowid FROM idx_refTable_geom WHERE rowid MATCH RTreeIntersects(%f, %f, %f, %f))'%(lonRangeMin, latRangeMin, lonRangeMax, latRangeMax))
            
        allentries=self.cursorGlobal.fetchall()
        resultList=list()
        nodeTypeSet=set(nodeTypeList)
        for x in allentries:
            refId, lat, lon, tags, storedNodeList=self.refFromDB(x)
            for nodeType in storedNodeList:
                if nodeType in nodeTypeSet:
                    resultList.append((refId, lat, lon, tags, storedNodeList))
            
        return resultList
        
    def getNearestNodeOfType(self, lat, lon, distance, nodeType):
#        lonRangeMin, latRangeMin, lonRangeMax, latRangeMax=self.createBBoxAroundPoint(lat, lon, margin)      
        self.cursorGlobal.execute('SELECT refId, tags, type, AsText(geom), GeodesicLength(MakeLine(geom, MakePoint(%f, %f, 4236))) FROM refTable WHERE type IS NOT NULL AND ROWID IN (SELECT rowid FROM idx_refTable_geom WHERE rowid MATCH RTreeDistWithin(%f, %f, %f))'%(lon, lat, lon, lat, distance))
            
        allentries=self.cursorGlobal.fetchall()
        resultList=list()

        for x in allentries:
            distance=int(x[4])
            refId, nodeLat, nodeLon, tags, storedNodeList=self.refFromDB(x) 
            if nodeType in storedNodeList:
                print(tags)
                print(distance)
                
#            resultList.append((refId, lat, lon, tags, storedNodeList))
            
        return resultList
        
    def getEdgesInBboxWithGeom(self, bbox, margin):
        lonRangeMin, latRangeMin, lonRangeMax, latRangeMax=self.createBBoxWithMargin(bbox, margin)      
   
        self.cursorEdge.execute('SELECT id, startRef, endRef, length, wayId, source, target, cost, reverseCost, streetInfo, AsText(geom) FROM edgeTable WHERE ROWID IN (SELECT rowid FROM idx_edgeTable_geom WHERE rowid MATCH RTreeIntersects(%f, %f, %f, %f))'%(lonRangeMin, latRangeMin, lonRangeMax, latRangeMax))
        allentries=self.cursorEdge.fetchall()
        resultList=list()
        for x in allentries:
            resultList.append(self.edgeFromDBWithCoords(x))
            
        return resultList

    def getEdgesAroundPointWithGeom(self, lat, lon, margin):
        lonRangeMin, latRangeMin, lonRangeMax, latRangeMax=self.createBBoxAroundPoint(lat, lon, margin)      
        self.currentSearchBBox=[lonRangeMin, latRangeMin, lonRangeMax, latRangeMax]

        self.cursorEdge.execute('SELECT id, startRef, endRef, length, wayId, source, target, cost, reverseCost, streetInfo, AsText(geom) FROM edgeTable WHERE ROWID IN (SELECT rowid FROM idx_edgeTable_geom WHERE rowid MATCH RTreeIntersects(%f, %f, %f, %f))'%(lonRangeMin, latRangeMin, lonRangeMax, latRangeMax))
        allentries=self.cursorEdge.fetchall()
        resultList=list()
        for x in allentries:
            resultList.append(self.edgeFromDBWithCoords(x))
            
        return resultList
    
    def getWaysInBboxWithGeom(self, bbox, margin, streetTypeList):
        lonRangeMin, latRangeMin, lonRangeMax, latRangeMax=self.createBBoxWithMargin(bbox, margin)      
        
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
            
        wayIdSet=set()
        allentries=self.cursorGlobal.fetchall()
        resultList=list()
        for x in allentries:
            way=self.wayFromDBWithCoordsString(x)
            resultList.append(way)
            wayIdSet.add(way[0])
            
        return resultList, wayIdSet

    def getAreasInBboxWithGeom(self, areaTypeList, bbox, margin):
        lonRangeMin, latRangeMin, lonRangeMax, latRangeMax=self.createBBoxWithMargin(bbox, margin)      
        
        filterString='('
        for areaType in areaTypeList:
            filterString=filterString+str(areaType)+','
        filterString=filterString[:-1]
        filterString=filterString+')'

#        mbrStr='BuildMBR(%f, %f, %f, %f, 4236)'%(lonRangeMin, latRangeMin, lonRangeMax, latRangeMax)
        resultList=list()
        areaIdSet=set()
        
        self.cursorArea.execute('SELECT osmId, type, tags, adminLevel, AsText(geom) FROM areaTable WHERE ROWID IN (SELECT rowid FROM idx_areaTable_geom WHERE rowid MATCH RTreeIntersects(%f, %f, %f, %f)) AND type IN %s '%(lonRangeMin, latRangeMin, lonRangeMax, latRangeMax, filterString))
        allentries=self.cursorArea.fetchall()
        
        for x in allentries:
            (osmId, areaType, tags, adminLevel, polyStr)=self.areaFromDBWithCoordsString(x)
            resultList.append((osmId, areaType, tags, adminLevel, polyStr, 0))
            areaIdSet.add(x[0])
                
        self.cursorArea.execute('SELECT osmId, type, tags, adminLevel, AsText(geom) FROM areaLineTable WHERE ROWID IN (SELECT rowid FROM idx_areaLineTable_geom WHERE rowid MATCH RTreeIntersects(%f, %f, %f, %f)) AND type IN %s '%(lonRangeMin, latRangeMin, lonRangeMax, latRangeMax, filterString))
        allentries=self.cursorArea.fetchall()

        for x in allentries:
            (osmId, areaType, tags, adminLevel, polyStr)=self.areaFromDBWithCoordsString(x)
            resultList.append((osmId, areaType, tags, adminLevel, polyStr, 1))
            areaIdSet.add(x[0])

        return resultList, areaIdSet    
    
    def getAdminAreasInBboxWithGeom(self, bbox, margin, adminLevelList):
        areaType=Constants.AREA_TYPE_ADMIN
        lonRangeMin, latRangeMin, lonRangeMax, latRangeMax=self.createBBoxWithMargin(bbox, margin)      
        
        filterString='('
        for adminLevel in adminLevelList:
            filterString=filterString+str(adminLevel)+','
        filterString=filterString[:-1]
        filterString=filterString+')'
        
        self.cursorArea.execute('SELECT osmId, type, tags, adminLevel, AsText(geom) FROM areaTable WHERE ROWID IN (SELECT rowid FROM idx_areaTable_geom WHERE rowid MATCH RTreeIntersects(%f, %f, %f, %f)) AND type=%d AND adminLevel IN %s AND Intersects(geom, BuildMBR(%f, %f, %f, %f, 4236)) ORDER BY adminLevel'%(lonRangeMin, latRangeMin, lonRangeMax, latRangeMax, areaType, filterString, lonRangeMin, latRangeMin, lonRangeMax, latRangeMax))
             
        allentries=self.cursorArea.fetchall()
        resultList=list()
        areaIdSet=set()
        for x in allentries:
            resultList.append(self.areaFromDBWithCoordsString(x))
            areaIdSet.add(x[0])
            
        return resultList, areaIdSet                 

    def getAdminAreasOnPointWithGeom(self, lat, lon, margin, adminLevelList, sortByAdminLevel):
        areaType=Constants.AREA_TYPE_ADMIN
        lonRangeMin, latRangeMin, lonRangeMax, latRangeMax=self.createBBoxAroundPoint(lat, lon, margin)      

        filterString='('
        for adminLevel in adminLevelList:
            filterString=filterString+str(adminLevel)+','
        filterString=filterString[:-1]
        filterString=filterString+')'

        if sortByAdminLevel==True:
            sql='SELECT osmId, type, tags, adminLevel FROM areaTable WHERE ROWID IN (SELECT rowid FROM idx_areaTable_geom WHERE rowid MATCH RTreeIntersects(%f, %f, %f, %f)) AND type=%d AND adminLevel IN %s AND Contains(geom, MakePoint(%f, %f, 4236)) ORDER BY adminLevel'%(lonRangeMin, latRangeMin, lonRangeMax, latRangeMax, areaType, filterString, lon, lat)
        else:
            sql='SELECT osmId, type, tags, adminLevel FROM areaTable WHERE ROWID IN (SELECT rowid FROM idx_areaTable_geom WHERE rowid MATCH RTreeIntersects(%f, %f, %f, %f)) AND type=%d AND adminLevel IN %s AND Contains(geom, MakePoint(%f, %f, 4236))'%(lonRangeMin, latRangeMin, lonRangeMax, latRangeMax, areaType, filterString, lon, lat)

        self.cursorArea.execute(sql)
             
        allentries=self.cursorArea.fetchall()
        resultList=list()
        for x in allentries:
            resultList.append(self.areaFromDB(x))
            
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
        wayId, tags, refs, streetInfo, name, nameRef, maxspeed, poiList, coords=self.wayFromDBWithCoordsList(way)
        if name!=None:
            streetTypeId, oneway, roundabout=self.decodeStreetInfo(streetInfo)
            
            if oneway!=0 and roundabout==0:
                return None
            
            allRefs=list()
            allRefs.append((wayId, refs, oneway, roundabout))
            resultList=self.getWayEntryForStreetName(name)
            for otherWay in resultList:
                otherWayId, otherTags, otherRefs, otherStreetInfo, _, otherNameRef, otherMaxspeed, otherPoiList, otherCoords=otherWay
                if otherWayId==wayId:
                    continue

                streetTypeId, oneway, roundabout=self.decodeStreetInfo(otherStreetInfo)
            
                if oneway!=0 and roundabout==0:
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
                
                allRefs.append((otherWayId, otherRefs, oneway, roundabout))
            
            refRings=self.mergeWayRefs(allRefs)
            return refRings
        
        return None
              
#    def mergeWayEntries(self): 
#        doneWays=set()       
#        newWayCount=0
#        self.cursorTmp.execute('SELECT * FROM wayTable')
#        allWays=self.cursorTmp.fetchall()
#        
#        allWaysLength=len(allWays)
#        waysBlockCount=int(allWaysLength/100)
#        allWaysCount=0
#        alLWaysPercentCount=0
#        
#        print("old way length=%d"%(allWaysLength))
#
#        for way in allWays:
#            wayId, tags, refs, streetInfo, name, nameRef, maxspeed=self.wayFromTmpDB(way)
##            print(way)
#
#            if allWaysCount>waysBlockCount:
#                print("done %d"%(alLWaysPercentCount))
#                alLWaysPercentCount=alLWaysPercentCount+1
#                allWaysCount=0
#            else:
#                allWaysCount=allWaysCount+1
#                
#            if wayId in doneWays:
#                continue
#            
#            streetTypeId, oneway, roundabout, tunnel, bridge=self.decodeStreetInfo2(streetInfo)
#            
#            if name!=None and (oneway==0 or roundabout==1):    
#                allRefs=list()
#                allRefs.append((wayId, refs, oneway, roundabout))
#                resultList=self.getTmpWayEntryForStreetName(name)
#                for otherWay in resultList:
#                    otherWayId, otherTags, otherRefs, otherStreetInfo, _, otherNameRef, otherMaxspeed=otherWay
#                    if otherWayId==wayId:
#                        continue
#    
#                    if otherWayId in doneWays:
#                        continue
#                    
#                    streetTypeId, oneway, roundabout=self.decodeStreetInfo(otherStreetInfo)
#                
#                    if oneway!=0 and roundabout==0:
#                        continue
#                    
#                    if streetInfo!=otherStreetInfo:
#                        continue
#                    
#                    if maxspeed!=otherMaxspeed:
#                        continue
#                    
#                    if nameRef!=otherNameRef:
#                        continue
#                    
#                    if len(tags)!=len(otherTags):
#                        continue
#                    
#                    if tags!=otherTags:
#                        continue
#                    
#                    allRefs.append((otherWayId, otherRefs, oneway, roundabout))
#                
#                refRings=self.mergeWayRefs(allRefs)
##                print(refRings)
#                for refRingEntry in refRings:
#                    wayId=refRingEntry["wayId"]
#                    refs=refRingEntry["refs"]
#                    wayIdList=refRingEntry["wayIdList"]
#                    for x in wayIdList:
#                        doneWays.add(x)
#                    
#                    coords, newRefList=self.createRefsCoords(refs)
#                    if len(coords)!=0:
##                        if len(wayIdList)>1:
##                            print("add merged way %d %s"%(wayId, wayIdList))
##                        else:
##                            print("add single way %d"%(wayId))
#                        newWayCount=newWayCount+1
#                        self.addToWayTable(wayId, tags, newRefList, streetTypeId, name, nameRef, oneway, roundabout, maxspeed, tunnel, bridge, coords)   
#                        for ref in refs:  
#                            storedRef, lat, lon=self.getCoordsEntry(ref)
#                            if storedRef==None:
#                                continue
#        
#                            self.addToRefTable(ref, lat, lon, None, 0)
#                            self.addToTmpRefWayTable(ref, wayId)
#                    else:
#                        print("mergeWayEntries: skipping wayId %d because of missing coords"%(wayId))
#    
#            else:
#                doneWays.add(wayId)
#                coords, newRefList=self.createRefsCoords(refs)
#                if len(coords)!=0:
##                    print("add single way %d"%wayId)
#                    newWayCount=newWayCount+1
#                    self.addToWayTable(wayId, tags, newRefList, streetTypeId, name, nameRef, oneway, roundabout, maxspeed, tunnel, bridge, coords)   
#                    for ref in refs:  
#                        storedRef, lat, lon=self.getCoordsEntry(ref)
#                        if storedRef==None:
#                            continue
#    
#                        self.addToRefTable(ref, lat, lon, None, 0)
#                        self.addToTmpRefWayTable(ref, wayId)
#                else:
#                    print("mergeWayEntries: skipping wayId %d because of missing coords"%(wayId))
#
#        if len(doneWays)!=allWaysLength:
#            print("length missmatch")
#        
#        print("new way length=%d"%(newWayCount))
        
def main(argv):    
    p = OSMParserData()
    
    p.initDB()
#    p.openAdressDB()
#    p.createAdressTable()
#    p.closeAdressDB()
    
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
#    p.testAreaTable()
#    p.resolveAddresses()
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
    
#    p.parseAddresses()
#    p.resolveAddresses()
    p.parseAreas()
#    p.parseNodes()
#    p.testAddressTable()
#    p.testCoordsTable()
#    p.vacuumEdgeDB()
#    p.vacuumGlobalDB()

#    p.mergeEqualWayEntries()
    
#    p.mergeWayEntries()

    p.closeAllDB()


if __name__ == "__main__":
#    cProfile.run('main(sys.argv)')
    main(sys.argv)  
    

