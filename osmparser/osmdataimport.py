'''
Created on Dec 13, 2011

@author: maxl
'''
import sys
import os
import sqlite3
import pickle
import re
import cProfile

from utils.progress import ProgressBar
from utils.env import getDataRoot, getPolyDataRoot
from utils.osmutils import OSMUtils
from imposm.parser.xml.parser import XMLParser
from imposm.parser import OSMParser

from osmparser.osmboarderutils import OSMBoarderUtils
from osmparser.osmdataaccess import Constants
from osmparser.osmdatasqlite import OSMDataSQLite

from Polygon import Polygon
from osmparser.importlog import ImportLog
 
importLog=ImportLog(True)

class OSMDataImport(OSMDataSQLite):
    def __init__(self):
        super(OSMDataImport, self).__init__()
        self.cursorTmp=None
        self.connectionTmp=None
        self.connectionCoords=None
        self.cursorCoords=None
        self.edgeId=1
        self.restrictionId=0
        self.nodeId=1
        self.addressId=0
        self.osmutils=OSMUtils()
        self.initBoarders()
        self.osmList=self.getOSMDataInfo()
        self.wayCount=0
        self.wayRestricitionList=list()
        self.barrierRestrictionList=list()
        self.usedBarrierList=list()
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
        self.disableMemoryDB=True
        self.addressCache=set()
        self.highestAdminRelationNumber=0

    def openAllDB(self):
        super(OSMDataImport, self).openAllDB()
        self.openTmpDB()
        self.openCoordsDB()
        
    def closeAllDB(self):
        super(OSMDataImport, self).closeAllDB()
        self.closeTmpDB()
        self.closeCoordsDB()  
        
    def createEdgeTables(self):
        self.createEdgeTable()
        self.createRestrictionTable()

    def createAdressTable(self):
        self.createAddressTable()

    def openTmpDB(self):
        if self.disableMemoryDB==True:
            self.connectionTmp=sqlite3.connect(self.getTmpDBFile())
        else:
            self.connectionTmp=sqlite3.connect(":memory:")
        self.cursorTmp=self.connectionTmp.cursor()
#        self.setPragmaForDB(self.cursorTmp)

    def getTmpDBFile(self):
        file="tmp.db"
        return os.path.join(self.getDataDir(), file)

    def tmpDBExists(self):
        return os.path.exists(self.getTmpDBFile())
    
    def openCoordsDB(self):
        if self.disableMemoryDB==True:
            self.connectionCoords=sqlite3.connect(self.getCoordsDBFile())
        else:
            self.connectionCoords=sqlite3.connect(":memory:")
        self.cursorCoords=self.connectionCoords.cursor()
#        self.setPragmaForDB(self.cursorCoords)

    def getCoordsDBFile(self):
        file="coords.db"
        return os.path.join(self.getDataDir(), file)

    def coordsDBExists(self):
        return os.path.exists(self.getCoordsDBFile())

    def createCoordsDBTables(self):
        self.createCoordsTable()

    def commitAdressDB(self):
        self.connectionAdress.commit()
        
    def commitEdgeDB(self):
        self.connectionEdge.commit()

    def commitCoordsDB(self):
        self.connectionCoords.commit()

    def commitWayDB(self):
        self.connectionWay.commit()

    def commitNodeDB(self):
        self.connectionNode.commit()
        
    def commitAreaDB(self):
        self.connectionArea.commit()
        
    def closeTmpDB(self):
        if self.connectionTmp!=None:
            self.connectionTmp.commit()
            self.cursorTmp.close()
            self.connectionTmp=None
            self.cursorTmp=None   

    def closeCoordsDB(self):
        if self.connectionCoords!=None:
            self.connectionCoords.commit()
            self.cursorCoords.close()
            self.connectionCoords=None
            self.cursorCoords=None   
            
    def createCoordsTable(self):
        self.cursorCoords.execute('CREATE TABLE coordsTable (refId INTEGER PRIMARY KEY, lat REAL, lon REAL)')
        
    def addToCoordsTable(self, ref, lat, lon):
        self.cursorCoords.execute('INSERT OR IGNORE INTO coordsTable VALUES( ?, ?, ?)', (ref, lat, lon))

    def getCoordsEntry(self, ref):
        self.cursorCoords.execute('SELECT * FROM coordsTable WHERE refId=%d'%(ref))
        allentries=self.cursorCoords.fetchall()
        if len(allentries)==1:
            return(allentries[0][0], allentries[0][1], allentries[0][2])
        return None, None, None
    
    def addToTmpWayRefTable(self, wayId, refs):
        self.cursorTmp.execute('INSERT OR IGNORE INTO wayRefTable VALUES( ?, ?)', (wayId, pickle.dumps(refs)))
        
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

    def getTmpWayRefEntry(self, wayId):
        self.cursorTmp.execute('SELECT * FROM wayRefTable WHERE wayId=%d'%(wayId))
        allentries=self.cursorTmp.fetchall()
        if len(allentries)==1:
            return(allentries[0][0], pickle.loads(allentries[0][1]))
        return None, None    
    
    def getTmpRefWayEntryForId(self, ref):
        self.cursorTmp.execute('SELECT * FROM refWayTable WHERE refId=%d'%(ref))
        allentries=self.cursorTmp.fetchall()
        if len(allentries)==1:
            return(allentries[0][0], pickle.loads(allentries[0][1]))
        return None, None    
        
    def createNodeDBTables(self):
        self.cursorNode.execute("SELECT InitSpatialMetaData()")

        self.cursorNode.execute('CREATE TABLE poiRefTable (refId INTEGER, refType INTEGER, tags BLOB, type INTEGER, layer INTEGER, country INTEGER, city INTEGER, UNIQUE (refId, refType, type) ON CONFLICT IGNORE)')
        self.cursorNode.execute("CREATE INDEX poiRefId_idx ON poiRefTable (refId)")
        self.cursorNode.execute("CREATE INDEX type_idx ON poiRefTable (type)")
        self.cursorNode.execute("CREATE INDEX country_idx ON poiRefTable (country)")
        self.cursorNode.execute("CREATE INDEX city_idx ON poiRefTable (city)")
        self.cursorNode.execute("SELECT AddGeometryColumn('poiRefTable', 'geom', 4326, 'POINT', 2)")
        
    def createWayDBTables(self):
        self.cursorWay.execute("SELECT InitSpatialMetaData()")
        self.cursorWay.execute('CREATE TABLE wayTable (wayId INTEGER PRIMARY KEY, tags BLOB, refs BLOB, streetInfo INTEGER, name TEXT, ref TEXT, maxspeed INTEGER, poiList BLOB, streetTypeId INTEGER, layer INTEGER)')
        self.cursorWay.execute("CREATE INDEX streetTypeId_idx ON wayTable (streetTypeId)")
        self.cursorWay.execute("SELECT AddGeometryColumn('wayTable', 'geom', 4326, 'LINESTRING', 2)")

        self.cursorWay.execute('CREATE TABLE crossingTable (id INTEGER PRIMARY KEY, wayId INTEGER, refId INTEGER, nextWayIdList BLOB)')
        self.cursorWay.execute("CREATE INDEX wayId_idx ON crossingTable (wayId)")
        self.cursorWay.execute("CREATE INDEX refId_idx ON crossingTable (refId)")

    def createTmpTable(self):
        self.cursorTmp.execute('CREATE TABLE refWayTable (refId INTEGER PRIMARY KEY, wayIdList BLOB)')
        self.cursorTmp.execute('CREATE TABLE wayRefTable (wayId INTEGER PRIMARY KEY, refList BLOB)')
        
    def createAddressTable(self):
        self.cursorAdress.execute('CREATE TABLE addressTable (id INTEGER PRIMARY KEY, refId INTEGER, country INTEGER, city INTEGER, postCode INTEGER, streetName TEXT, houseNumber TEXT, lat REAL, lon REAL)')
        self.cursorAdress.execute("CREATE INDEX streetName_idx ON addressTable (streetName)")
        self.cursorAdress.execute("CREATE INDEX country_idx ON addressTable (country)")
        self.cursorAdress.execute("CREATE INDEX houseNumber_idx ON addressTable (houseNumber)")
        self.cursorAdress.execute("CREATE INDEX city_idx ON addressTable (city)")
        
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
    
    def addToAddressTable(self, refId, country, city, streetName, houseNumber, lat, lon):
        cacheKey="%s:%s"%(streetName, houseNumber)
        if not cacheKey in self.addressCache: 
            self.cursorAdress.execute('INSERT INTO addressTable VALUES( ?, ?, ?, ?, ?, ?, ?, ?, ?)', (self.addressId, refId, country, city, None, streetName, houseNumber, lat, lon))
            self.addressId=self.addressId+1
            self.addressCache.add(cacheKey)
        else:
            resultList=self.getAdressListForStreetAndNumber(streetName, houseNumber)
            for address in resultList:
                _, _, _, _, _, _, _, storedLat, storedLon=address
                bbox=self.createBBoxAroundPoint(storedLat, storedLon, 0.0005)      
                if self.pointInsideBBox(bbox, lat, lon):
                    return
                
            self.cursorAdress.execute('INSERT INTO addressTable VALUES( ?, ?, ?, ?, ?, ?, ?, ?, ?)', (self.addressId, refId, country, city, None, streetName, houseNumber, lat, lon))
            self.addressId=self.addressId+1

    def addToAddressTable2(self, refId, country, city, streetName, houseNumber, lat, lon):
        self.cursorAdress.execute('INSERT INTO addressTable VALUES( ?, ?, ?, ?, ?, ?, ?, ?, ?)', (self.addressId, refId, country, city, None, streetName, houseNumber, lat, lon))
        self.addressId=self.addressId+1
                
    def updateAddressEntry(self, addressId, country, city):
        self.cursorAdress.execute('UPDATE OR IGNORE addressTable SET country=%d,city=%d WHERE id=%d'%(country, city, addressId))

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
        self.cursorArea.execute('CREATE TABLE areaTable (osmId INTEGER, areaId INTEGER, type INTEGER, tags BLOB, layer INTEGER, UNIQUE (osmId, areaId) ON CONFLICT IGNORE)')
        self.cursorArea.execute("CREATE INDEX osmId_idx ON areaTable (osmId)")
        self.cursorArea.execute("CREATE INDEX areaType_idx ON areaTable (type)")
        self.cursorArea.execute("SELECT AddGeometryColumn('areaTable', 'geom', 4326, 'MULTIPOLYGON', 2)")
        
        self.cursorArea.execute('CREATE TABLE areaLineTable (osmId INTEGER PRIMARY KEY, type INTEGER, tags BLOB, layer INTEGER)')
        self.cursorArea.execute("CREATE INDEX areaLineType_idx ON areaLineTable (type)")
        self.cursorArea.execute("SELECT AddGeometryColumn('areaLineTable', 'geom', 4326, 'LINESTRING', 2)")

        self.cursorArea.execute('CREATE TABLE adminAreaTable (osmId INTEGER PRIMARY KEY, tags BLOB, adminLevel INTEGER, parent INTEGER)')
        self.cursorArea.execute("CREATE INDEX adminLevel_idx ON adminAreaTable (adminLevel)")
        self.cursorArea.execute("CREATE INDEX parent_idx ON adminAreaTable (parent)")
        self.cursorArea.execute("SELECT AddGeometryColumn('adminAreaTable', 'geom', 4326, 'MULTIPOLYGON', 2)")

    def createRestrictionTable(self):
        self.cursorEdge.execute('CREATE TABLE restrictionTable (id INTEGER PRIMARY KEY, target INTEGER, viaPath TEXT, toCost REAL)')
        self.cursorEdge.execute("CREATE INDEX restrictionTarget_idx ON restrictionTable (target)")
        
    def addToRestrictionTable(self, target, viaPath, toCost):
        self.cursorEdge.execute('INSERT INTO restrictionTable VALUES( ?, ?, ?, ?)', (self.restrictionId, target, viaPath, toCost))
        self.restrictionId=self.restrictionId+1
                
    def addToPOIRefTable(self, refid, refType, lat, lon, tags, nodeType, layer):           
        pointString=self.getGISUtils().createPointStringFromCoords(lat, lon)
        tags=self.stripUnneededNodeTags(tags)
        tagsString=self.encodeTags(tags)
        self.cursorNode.execute('INSERT INTO poiRefTable VALUES( ?, ?, ?, ?, ?, ?, ?, PointFromText(%s, 4326))'%(pointString), (refid, refType, tagsString, nodeType, layer, None, None))
        
    def updateWayTableEntryPOIList(self, wayId, poiList):
        wayId, tags, refs, streetInfo, name, nameRef, maxspeed, _, layer, coordsStr=self.getWayEntryForIdWithCoords(wayId)
        if wayId!=None:
            streetTypeId, _, _=self.decodeStreetInfo(streetInfo)
            self.cursorWay.execute('REPLACE INTO wayTable VALUES( ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, LineFromText("%s", 4326))'%(coordsStr), (wayId, self.encodeTags(tags), pickle.dumps(refs), streetInfo, name, nameRef, maxspeed, pickle.dumps(poiList), streetTypeId, layer))
        
    def addToWayTable(self, wayid, tags, refs, streetTypeId, name, nameRef, oneway, roundabout, maxspeed, tunnel, bridge, coords, layer):
        name=self.encodeStreetName(name)
        streetInfo=self.encodeStreetInfo2(streetTypeId, oneway, roundabout, tunnel, bridge)
        lineString=self.getGISUtils().createLineStringFromCoords(coords)
        self.cursorWay.execute('INSERT OR IGNORE INTO wayTable VALUES( ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, LineFromText(%s, 4326))'%(lineString), (wayid, self.encodeTags(tags), pickle.dumps(refs), streetInfo, name, nameRef, maxspeed, None, streetTypeId, layer))
    
    def encodeStreetName(self, name):
        if name!=None:
            return name.replace('"', '').replace('\'', '')
        return name
        
    def addToCrossingsTable(self, wayid, refId, nextWaysList):
        self.cursorWay.execute('INSERT INTO crossingTable VALUES( ?, ?, ?, ?)', (self.crossingId, wayid, refId, pickle.dumps(nextWaysList)))
        self.crossingId=self.crossingId+1

    def addToEdgeTable(self, startRef, endRef, length, wayId, cost, reverseCost, streetInfo, coords):
        resultList=self.getEdgeEntryForStartAndEndPointAndWayId(startRef, endRef, wayId)
        if len(resultList)==0:
            lineString=self.getGISUtils().createLineStringFromCoords(coords)
            
            self.cursorEdge.execute('INSERT INTO edgeTable VALUES( ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, LineFromText(%s, 4326))'%(lineString), (self.edgeId, startRef, endRef, length, wayId, 0, 0, cost, reverseCost, streetInfo))
            self.edgeId=self.edgeId+1
        
    def addPolygonToAreaTable(self, osmId, areaId, areaType, tags, polyString, layer):
        tags=self.stripUnneededAreaTags(tags)
        self.cursorArea.execute('INSERT OR IGNORE INTO areaTable VALUES( ?, ?, ?, ?, ?, MultiPolygonFromText(%s, 4326))'%(polyString), (osmId, areaId, areaType, self.encodeTags(tags), layer))

    def addLineToAreaTable(self, osmId, areaType, tags, lineString, layer):
        tags=self.stripUnneededAreaTags(tags)
        self.cursorArea.execute('INSERT OR IGNORE INTO areaLineTable VALUES( ?, ?, ?, ?, LineFromText(%s, 4326))'%(lineString), (osmId, areaType, self.encodeTags(tags), layer))

    def addPolygonToAdminAreaTable(self, osmId, tags, adminLevel, polyString):
        self.cursorArea.execute('INSERT OR IGNORE INTO adminAreaTable VALUES( ?, ?, ?, ?, MultiPolygonFromText(%s, 4326))'%(polyString), (osmId, self.encodeTags(tags), adminLevel, None))
        
    def updateAdminAreaParent(self, osmId, parent):
        self.cursorArea.execute('UPDATE adminAreaTable SET parent=%d WHERE osmId=%d'%(parent, osmId))
    
    def createSpatialIndexForEdgeTable(self):
        self.cursorEdge.execute('SELECT CreateSpatialIndex("edgeTable", "geom")')

    def createSpatialIndexForAreaTable(self):
        self.cursorArea.execute('SELECT CreateSpatialIndex("areaTable", "geom")')
        self.cursorArea.execute('SELECT CreateSpatialIndex("areaLineTable", "geom")')
        self.cursorArea.execute('SELECT CreateSpatialIndex("adminAreaTable", "geom")')

    def createSpatialIndexForWayTables(self):
        self.cursorWay.execute('SELECT CreateSpatialIndex("wayTable", "geom")')

    def createSpatialIndexForNodeTables(self):
        self.cursorNode.execute('SELECT CreateSpatialIndex("poiRefTable", "geom")')
                            
    def updateSourceOfEdge(self, edgeId, sourceId):
        self.cursorEdge.execute('UPDATE OR IGNORE edgeTable SET source=%d WHERE id=%d'%(sourceId, edgeId))

    def updateTargetOfEdge(self, edgeId, targetId):
        self.cursorEdge.execute('UPDATE OR IGNORE edgeTable SET target=%d WHERE id=%d'%(targetId, edgeId))
        
    def updateCostsOfEdge(self, edgeId, cost, reverseCost):
        self.cursorEdge.execute('UPDATE OR IGNORE edgeTable SET cost=%d, reverseCost=%d WHERE id=%d'%(cost, reverseCost, edgeId))

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

    # in theory could be more then one if there 
    # is a wayId same to a node refId
    # so use it only with wayrefs
    def getPOIRefEntryForId(self, refId, refType, nodeType):
        self.cursorNode.execute('SELECT refId, tags, type, layer, AsText(geom) FROM poiRefTable WHERE refId=%d AND type=%d AND refType=%d'%(refId, nodeType, refType))
        allentries=self.cursorNode.fetchall()
        if len(allentries)==1:
            return self.poiRefFromDB(allentries[0])

        return None, None, None, None, None, None
    
    def getAllPOIRefEntrysDict(self, nodeTypeList):
        filterString=self.createSQLFilterStringForIN(nodeTypeList)

        self.cursorNode.execute('SELECT refId, tags, type FROM poiRefTable WHERE type IN %s'%(filterString))
        allentries=self.cursorNode.fetchall()
        resultDict=dict()
        for x in allentries:
            refId=int(x[0])
            tags=self.decodeTags(x[1])
            nodeType=int(x[2])
            resultDict["%d:%d"%(refId, nodeType)]=tags

        return resultDict
    
    def updatePOIRefEntry(self, refId, refType, poiType, country, city):
        self.cursorNode.execute('UPDATE OR IGNORE poiRefTable SET country=%d,city=%d WHERE refId=%d AND refType=%d AND type=%d'%(country, city, refId, refType, poiType))
    
    def getWayEntryForIdWithCoords(self, wayId):
        self.cursorWay.execute('SELECT wayId, tags, refs, streetInfo, name, ref, maxspeed, poiList, layer, AsText(geom) FROM wayTable where wayId=%d'%(wayId))
        allentries=self.cursorWay.fetchall()
        if len(allentries)==1:
            return self.wayFromDBWithCoordsString(allentries[0])
        
        return (None, None, None, None, None, None, None, None, None, None)
        
    def getCrossingEntryFor(self, wayid):
        self.cursorWay.execute('SELECT * FROM crossingTable where wayId=%d'%(wayid))      
        resultList=list()
        allentries=self.cursorWay.fetchall()
        for result in allentries:
            crossing=self.crossingFromDB(result)
            resultList.append(crossing)
            
        return resultList
        
    def isUsableBarierType(self):
        return Constants.BARIER_NODES_TYPE_SET

    def isUsablePlaceNodeType(self):
        return Constants.PLACE_NODES_TYPE_SET
        
    def getHighwayNodeTypeId(self, nodeTag):
        if nodeTag in Constants.HIGHWAY_POI_TYPE_DICT.keys():
            return Constants.HIGHWAY_POI_TYPE_DICT[nodeTag]

        return -1
    
    def getAmenityNodeTypeId(self, nodeTag, tags):
        if nodeTag in Constants.AMENITY_POI_TYPE_DICT.keys():
            entry=Constants.AMENITY_POI_TYPE_DICT[nodeTag]
            nodeType=entry[0]
            limitationDict=entry[1]
            if limitationDict!=None:
                for key, value in limitationDict.items():
                    if key in tags.keys():
                        if value!=tags[key]:
                            return -1
            return nodeType
        
        return -1

    def getShopNodeTypeId(self, nodeTag):
        if nodeTag in Constants.SHOP_POI_TYPE_DICT.keys():
            return Constants.SHOP_POI_TYPE_DICT[nodeTag]
        
        return -1

    def getAerowayNodeTypeId(self, nodeTag):
        if nodeTag in Constants.AEROWAY_POI_TYPE_DICT.keys():
            return Constants.AEROWAY_POI_TYPE_DICT[nodeTag]
        
        return -1

    def getRailwayNodeTypeId(self, nodeTag):
        if nodeTag in Constants.RAILWAY_POI_TYPE_DICT.keys():
            return Constants.RAILWAY_POI_TYPE_DICT[nodeTag]
        
        return -1
    
    def getTourismNodeTypeId(self, nodeTag):
        if nodeTag in Constants.TOURISM_POI_TYPE_DICT.keys():
            return Constants.TOURISM_POI_TYPE_DICT[nodeTag]
        
        return -1

    def parse_nodes(self, node):
        if self.skipNodes==True:
            return
        
        if self.firstNode==False:
            self.firstNode=True
            self.log("Parsing nodes...")

        for ref, tags, coords in node:
            # <tag k="highway" v="motorway_junction"/>
            lat=float(coords[1])
            lon=float(coords[0])
            
            layer=self.getLayerValue(tags)
                
            if self.skipPOINodes==False:
                if "highway" in tags:
                    nodeType=self.getHighwayNodeTypeId(tags["highway"])
                    if nodeType!=-1:
                        self.addToPOIRefTable(ref, 0, lat, lon, tags, nodeType, layer)
                            
                if "barrier" in tags:
                    if tags["barrier"] in self.isUsableBarierType():
                        self.addToPOIRefTable(ref, 0, lat, lon, tags, Constants.POI_TYPE_BARRIER, layer)
                      
                if "amenity" in tags:
                    nodeType=self.getAmenityNodeTypeId(tags["amenity"], tags)
                    if nodeType!=-1:
                        self.addToPOIRefTable(ref, 0, lat, lon, tags, nodeType, layer)
                
                if "place" in tags:
                    if tags["place"] in self.isUsablePlaceNodeType():
                        self.addToPOIRefTable(ref, 0, lat, lon, tags, Constants.POI_TYPE_PLACE, layer)
 
                if "shop" in tags:
                    nodeType=self.getShopNodeTypeId(tags["shop"])
                    if nodeType!=-1:
                        self.addToPOIRefTable(ref, 0, lat, lon, tags, nodeType, layer)

                if "aeroway" in tags:
                    nodeType=self.getAerowayNodeTypeId(tags["aeroway"])
                    if nodeType!=-1:
                        self.addToPOIRefTable(ref, 0, lat, lon, tags, nodeType, layer)

                if "railway" in tags:
                    nodeType=self.getRailwayNodeTypeId(tags["railway"])
                    if nodeType!=-1:
                        self.addToPOIRefTable(ref, 0, lat, lon, tags, nodeType, layer)
                
                if "tourism" in tags:
                    nodeType=self.getTourismNodeTypeId(tags["tourism"])
                    if nodeType!=-1:
                        self.addToPOIRefTable(ref, 0, lat, lon, tags, nodeType, layer)
                    
            if self.skipAddress==False:
                if "addr:street" in tags:
#                    self.addToRefTable(ref, lat, lon, layer)
                    self.parseFullAddress(tags, ref, lat, lon)

    def parse_coords(self, coord):
        if self.skipCoords==True:
            return
        
        for osmid, lon, lat in coord:
            self.addToCoordsTable(osmid, float(lat), float(lon))
           
    def parseFullAddress(self, tags, refId, lat, lon):  
        #   <node id="652701965" version="2" timestamp="2011-10-03T18:04:48Z" uid="47756" user="tunnelbauer" changeset="9462694" lat="47.8182158" lon="13.0495882">
#    <tag k="addr:city" v="Salzburg"/>
#    <tag k="addr:country" v="AT"/>
#    <tag k="addr:housenumber" v="9"/>
#    <tag k="addr:postcode" v="5020"/>
#    <tag k="addr:street" v="Magazinstraße"/>
#  </node>

#        city=None
#        postCode=None
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

        if streetName==None or houseNumber==None:
            return False
        
        # rest of info is filled later on from admin boundaries
        self.addToAddressTable(refId, None, None, streetName, houseNumber, lat, lon)
        return True
    
    def encodeStreetInfo2(self, streetTypeId, oneway, roundabout, tunnel, bridge):
        streetInfo=streetTypeId+(oneway<<4)+(roundabout<<6)+(tunnel<<7)+(bridge<<8)
        return streetInfo
    
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

    def stripUnneededWayTags(self, tags):
        newTags=dict()
        tagList=self.getRequiredWayTags()
        for key, value in tags.items():
            if key in tagList:
                newTags[key]=value
        return newTags

    def getRequiredAreaTags(self):
        return Constants.REQUIRED_AREA_TAGS_SET

    def stripUnneededAreaTags(self, tags):
        newTags=dict()
        tagList=self.getRequiredAreaTags()
        for key, value in tags.items():
            if key in tagList:
                newTags[key]=value
        return newTags    

    def getRequiredNodeTags(self):
        return Constants.REQUIRED_NODE_TAGS_SET

    def stripUnneededNodeTags(self, tags):
        newTags=dict()
        tagList=self.getRequiredNodeTags()
        for key, value in tags.items():
            if key in tagList:
                newTags[key]=value
        return newTags       
    
    def encodeTags(self, tags):
        if len(tags.keys())==0:
            return None
        pickeledTags=pickle.dumps(tags)
        return pickeledTags
        
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
    
    def getTourismTypes(self):
        return Constants.TOURISM_TYPE_SET
    
    def getAmenityTypes(self):
        return Constants.AMENITY_AREA_TYPE_SET
    
    def getLayerValue(self, tags):
        layer=0
        if "layer" in tags:
            try:
                layer=int(tags["layer"])
            except ValueError:
                layer=0
                
        return layer
    
    def getCenterOfPolygon(self, refs):
        coords, _=self.createRefsCoords(refs)
        if len(coords)>2:
            cPolygon=Polygon(coords)
            try:
                lat, lon=cPolygon.center()
                return lat, lon
            except:
                print(refs)
                return coords[0]
    
        # lat = Sum(lat_1..lat_n)/n , lon=Sum(lon_1, lon_n)/n 
        n=len(coords)
        sumLat=0
        sumLon=0
        for lat, lon in coords:
            sumLat=sumLat+lat
            sumLon=sumLon+lon
            
        return sumLat/n, sumLon/n
    
    def parseBooleanTag(self, tags, key):
        if key in tags:
            if tags[key]=="1" or tags[key]=="true" or tags[key]=="yes":
                return True
            
        return False
    
    def parse_ways(self, way):
        if self.skipWays==True:
            return 
        
        if self.firstWay==False:
            self.firstWay=True
            self.log("Parsing ways...")
            
        for wayid, tags, refs in way:
            if len(refs)<2:
                self.log("way with len(ref)<2 %d"%(wayid))
                continue
                            
            isBuilding=False
            isLanduse=False
            isNatural=False
            isRailway=False
            isAeroway=False
            isTourism=False
            isAmenity=False
                       
            layer=self.getLayerValue(tags)
                
            if "building" in tags:
                if self.skipAddress==False:
                    if "addr:street" in tags:
                        lat, lon=self.getCenterOfPolygon(refs)
                        self.parseFullAddress(tags, None, lat, lon)
                        
            if "amenity" in tags:
                if self.skipPOINodes==False:
                    nodeType=self.getAmenityNodeTypeId(tags["amenity"], tags)
                    if nodeType!=-1:
                        lat, lon=self.getCenterOfPolygon(refs)
                        self.addToPOIRefTable(wayid, 1, lat, lon, tags, nodeType, layer)

            if "shop" in tags:
                if self.skipPOINodes==False:
                    nodeType=self.getShopNodeTypeId(tags["shop"])
                    if nodeType!=-1:
                        lat, lon=self.getCenterOfPolygon(refs)
                        self.addToPOIRefTable(wayid, 1, lat, lon, tags, nodeType, layer)

            if "aeroway" in tags and "name" in tags:
                if self.skipPOINodes==False:
                    nodeType=self.getAerowayNodeTypeId(tags["aeroway"])
                    if nodeType!=-1:
                        lat, lon=self.getCenterOfPolygon(refs)
                        self.addToPOIRefTable(wayid, 1, lat, lon, tags, nodeType, layer)

            if "tourism" in tags:
                if self.skipPOINodes==False:
                    nodeType=self.getTourismNodeTypeId(tags["tourism"])
                    if nodeType!=-1:
                        lat, lon=self.getCenterOfPolygon(refs)
                        self.addToPOIRefTable(wayid, 1, lat, lon, tags, nodeType, layer)

            if "place" in tags:
                if tags["place"] in self.isUsablePlaceNodeType():
                    lat, lon=self.getCenterOfPolygon(refs)
                    self.addToPOIRefTable(wayid, 1, lat, lon, tags, Constants.POI_TYPE_PLACE, layer)

            if not "highway" in tags:   
                # could be part of a relation                    
                self.addToTmpWayRefTable(wayid, refs)
                 
                if self.skipAreas==False:         
                    if "waterway" in tags:
                        if tags["waterway"] in self.getWaterwayTypes():
                            isNatural=True
                                                
                    if "natural" in tags:
                        if tags["natural"] in self.getNaturalTypes():
                            isNatural=True
                        
                    if "landuse" in tags:
                        if tags["landuse"] in self.getLanduseTypes():
                            isLanduse=True
                            # landuse overrides natural
                            isNatural=False
                                                   
                    if "railway" in tags:
                        if tags["railway"] in self.getRailwayTypes():
                            isRailway=True
                              
                    if "aeroway" in tags:
                        if tags["aeroway"] in self.getAerowayTypes():
                            isAeroway=True
                    
                    if "tourism" in tags:
                        if tags["tourism"] in self.getTourismTypes():
                            isTourism=True

                    if "amenity" in tags:
                        if tags["amenity"] in self.getAmenityTypes():
                            isAmenity=True
                            
                    if "building" in tags:
                        isBuilding=True
                        isLanduse=False
                        isNatural=False
                        isRailway=False
                        isAeroway=False
                        isTourism=False
                        isAmenity=False
               
                    if isAmenity==False and isTourism==False and isAeroway==False and isBuilding==False and isLanduse==False and isNatural==False and isRailway==False:
                        continue
                    
                    isPolygon=False
                    if refs[0]==refs[-1]:
                        isPolygon=True
                        
                    coords, newRefList=self.createRefsCoords(refs)
                    if isPolygon==True:
                        if len(coords)<3:
                            self.log("parse_ways: skipping polygon area %d %s len(coords)<3"%(wayid, refs))
                            continue
                    else:
                        if len(coords)<2:
                            self.log("parse_ways: skipping line area %d %s len(coords)<2"%(wayid, refs))
                            continue
                    
                    # TODO: skip complete area if coords are missing?
                    # e.g. waterway=riverbank ist missing then for Salzach
                    if isPolygon==True:
                        if newRefList[0]==newRefList[-1]:
                            geomString=self.getGISUtils().createMultiPolygonFromCoords(coords)
                        else:
                            self.log("parse_ways: skipping polygon area %d %s newRefList[0]!=newRefList[-1]"%(wayid, newRefList))
                            continue
                    else:
                        geomString=self.getGISUtils().createLineStringFromCoords(coords)
                        
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
                    elif isTourism==True:
                        areaType=Constants.AREA_TYPE_TOURISM
                    elif isAmenity==True:
                        areaType=Constants.AREA_TYPE_AMENITY
                        
                    if areaType!=None:
                        if isPolygon==True:
                            self.addPolygonToAreaTable(wayid, 0, areaType, tags, geomString, layer)
                        else:
                            self.addLineToAreaTable(wayid, areaType, tags, geomString, layer)
                        
            # highway
            else:             
                streetType=tags["highway"]
                                                                 
                streetTypeId=self.getStreetTypeId(streetType)
                if streetTypeId==-1:
                    # but could be part of a relation                    
                    self.addToTmpWayRefTable(wayid, refs)
                    continue
                
                if "area" in tags:
                    if self.skipAreas==False:         
                        if tags["area"]=="yes":
                            if refs[0]==refs[-1]:                                
                                coords, newRefList=self.createRefsCoords(refs)
                                if len(coords)<2:
                                    self.log("parse_ways: skipping area %d %s len(coords)<2"%(wayid, refs))
                                    continue
                    
                                geomString=self.getGISUtils().createMultiPolygonFromCoords(coords)
                                self.addPolygonToAreaTable(wayid, 0, Constants.AREA_TYPE_HIGHWAY_AREA, tags, geomString, layer)
                            
                            continue
                
                if self.skipHighways==False:
                    (name, nameRef)=self.getStreetNameInfo(tags, streetTypeId)
                    
                    oneway=0
                    roundabout=0
                    if "oneway" in tags:
                        if tags["oneway"]=="yes" or tags["oneway"]=="true" or tags["oneway"]=="1":
                            oneway=1
                        elif tags["oneway"]=="-1":
                            oneway=2
                    if "junction" in tags:
                        if tags["junction"]=="roundabout":
                            roundabout=1
                            if "oneway" in tags:
                                print("roundabout with oneway %d"%(wayid))
                                if tags["oneway"]=="-1":
                                    print("roundabout with oneway=-1 %d"%(wayid))
                                                        

                    tunnel=0
                    if "tunnel" in tags:
                        tunnel=1
                    
                    bridge=0
                    if "bridge" in tags:
                        bridge=1
                            
                    maxspeed=self.getMaxspeed(tags, streetTypeId)
                        
                    for ref in refs:  
                        storedRef, lat, lon=self.getCoordsEntry(ref)
                        if storedRef==None:
                            continue
    
#                        self.addToRefTable(ref, lat, lon, layer)
                        self.addToTmpRefWayTable(ref, wayid)
                    
                    coords, newRefList=self.createRefsCoords(refs)
                    if len(coords)>=2:
                        requiredTags=self.stripUnneededWayTags(tags)
                        self.addToWayTable(wayid, requiredTags, newRefList, streetTypeId, name, nameRef, oneway, roundabout, maxspeed, tunnel, bridge, coords, layer)   
                    else:
                        self.log("parse_ways: skipping way %d %s len(coords)<2"%(wayid, refs))

    def parse_relations(self, relation):
        if self.skipRelations==True:
            return
        
        if self.firstRelation==False:
            self.firstRelation=True
            self.log("Parsing relations...")

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
                elif tags["type"]=="multipolygon" or tags["type"]=="boundary":
                    isBuilding=False
                    isLanduse=False
                    isNatural=False
                    isAdminBoundary=False
                    isAeroway=False
                    isTourism=False
                    isAmenity=False
                    adminLevel=None
                    layer=self.getLayerValue(tags)

                    if "boundary" in tags:
                        if tags["boundary"] in self.getBoundaryTypes():
                            if not "name" in tags:
                                self.log("skip admin multipolygon: %d no name in tags"%(osmid))
                                continue
                            
                            if not "admin_level" in tags:
                                self.log("skip admin multipolygon: %d no admin_level in tags"%(osmid))
                                continue
                            
                            try:
                                adminLevel=int(tags["admin_level"])
                                if adminLevel!=2 and adminLevel!=4 and adminLevel!=6 and adminLevel!=8:
                                    self.log("skip admin multipolygon: %d %s level=%d"%(osmid, tags["name"], adminLevel))
                                    continue                                    
                            except ValueError:
                                self.log("skip admin multipolygon: %d %s parse error adminLevel %s "%(osmid, tags["name"], tags["admin_level"]))
                                continue
 
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
                            # landuse overrides natural
                            isNatural=False
                    
                    if "aeroway" in tags:
                        if tags["aeroway"] in self.getAerowayTypes():
                            isAeroway=True
                    
                    if "tourism" in tags:
                        if tags["tourism"] in self.getTourismTypes():
                            isTourism=True
                    
                    if "amenity" in tags:
                        if tags["amenity"] in self.getAmenityTypes():
                            isAmenity=True

                    if "building" in tags:
                        isBuilding=True
                        isLanduse=False
                        isNatural=False
                        isAdminBoundary=False
                        isAeroway=False
                        isTourism=False
                        isAmenity=False
                        
                    if isAmenity==False and isTourism==False and isAeroway==False and isAdminBoundary==False and isBuilding==False and isLanduse==False and isNatural==False:
                        if len(tags)!=1:
                            self.log("skip multipolygon: %d %s unknwon type"%(osmid, tags))
                        continue
                                            
                    # (59178604, 'way', 'outer')
                    allOuterRefs=list()
                    allInnerRefs=list()
                    skipArea=False
                        
                    for way in ways:
                        memberType=way[1]
                        relationWayId=int(way[0])
                        role=way[2]
                        
                        if memberType=="relation":
                            self.log("super relation %d %s"%(osmid, tags))
                            skipArea=True
                            break

                        if memberType=="way":
                            if role=="inner":
                                wayId, refs=self.getTmpWayRefEntry(relationWayId)
                                if wayId!=None:
                                    allInnerRefs.append((wayId, refs, 0, 0))
                                else:
                                    wayId, _, refs, _, _, _, _, _=self.getWayEntryForId(relationWayId)
                                    if wayId!=None:
                                        allInnerRefs.append((wayId, refs, 0, 0))
                                    else:
                                        self.log("failed to resolve way %d from inner relation %d"%(relationWayId, osmid))    
                                        continue
                            else:
                                wayId, refs=self.getTmpWayRefEntry(relationWayId)
                                if wayId!=None:
                                    allOuterRefs.append((wayId, refs, 0, 0))
                                else:
                                    wayId, _, refs, _, _, _, _, _=self.getWayEntryForId(relationWayId)
                                    if wayId!=None:
                                        allOuterRefs.append((wayId, refs, 0, 0))
                                    else:
                                        self.log("failed to resolve way %d from outer relation %d"%(relationWayId, osmid))    
                                        skipArea=True
                                        break
                    
                    if skipArea==True:
                        continue
                    
                    if len(allOuterRefs)==0:
                        self.log("skip multipolygon: %d len(allOuterRefs)==0"%(osmid))
                        continue
                    
                    outerRefRings=self.getGISUtils().mergeRelationRefs(allOuterRefs, self)
                    innerRefRings=self.getGISUtils().mergeRelationRefs(allInnerRefs, self)

                    # convert to multipolygon
                    polyString="'MULTIPOLYGON("
                    for refRingEntry in outerRefRings:                                
                        refs=refRingEntry["refs"]
                        if refs[0]!=refs[-1]:
                            self.log("skip outer multipolygon: %d refs[0]!=refs[-1]"%(osmid))
                            skipArea=True
                            break
                        
                        cPolygonOuter=refRingEntry["polygon"]
                        if cPolygonOuter==None:
                            self.log("skip outer multipolygon: %d invalid Polygon"%(osmid))
                            skipArea=True
                            break
                        
                        newRefList=refRingEntry["newRefs"]
                        outerCoords=refRingEntry["coords"]
                        if len(refs)!=len(newRefList):
                            self.log("skip outer multipolygon: %d coords missing"%(osmid))
                            skipArea=True
                            break
                        
                        innerCoords=list()
                        if len(innerRefRings)!=0:
                            for innerRefRingEntry in innerRefRings:
                                innerRefs=innerRefRingEntry["refs"]
                                if innerRefs[0]!=innerRefs[-1]:
                                    self.log("skip inner multipolygon: %d refs[0]!=refs[-1]"%(osmid))
                                    continue

                                innerNewRefs=innerRefRingEntry["newRefs"]
                                if len(innerRefs)!=len(innerNewRefs):
                                    self.log("skip inner multipolygon: %d coords missing"%(osmid))
                                    continue
                                
                                cPolygonInner=innerRefRingEntry["polygon"]
                                if cPolygonInner==None:
                                    self.log("skip inner multipolygon: %d invalid Polygon"%(osmid))
                                    continue
                                
                                if not cPolygonOuter.covers(cPolygonInner):
                                    continue
                                
                                innerCoords.append(innerRefRingEntry["coords"])
                                
                        polyStringPart=self.getGISUtils().createMultiPolygonPartFromCoordsWithInner(outerCoords, innerCoords)

                        polyString=polyString+polyStringPart
                                                        
                    polyString=polyString[:-1]
                    polyString=polyString+")'"

                    if skipArea==True:
                        continue
                    
                    if isAdminBoundary==True:
                        if adminLevel!=None:
                            # to add our own admin infor later without clashing
                            if osmid>self.highestAdminRelationNumber:
                                self.highestAdminRelationNumber=osmid
                            self.addPolygonToAdminAreaTable(osmid, tags, adminLevel, polyString)
                        else:
                            self.log("skip admin multipolygon: %d %s adminLevel=None"%(osmid, tags["name"]))
                            continue
                    else:    
                        areaType=None
                        if isNatural==True:
                            areaType=Constants.AREA_TYPE_NATURAL
                        elif isLanduse==True:
                            areaType=Constants.AREA_TYPE_LANDUSE
                        elif isBuilding==True:
                            areaType=Constants.AREA_TYPE_BUILDING
                        elif isAeroway==True:
                            areaType=Constants.AREA_TYPE_AEROWAY
                        elif isTourism==True:
                            areaType=Constants.AREA_TYPE_TOURISM
                        elif isAmenity==True:
                            areaType=Constants.AREA_TYPE_AMENITY
                            
                        if areaType!=None:
                            # make sure th osmid does not clash with a way area
                            # polygon added before
                            self.addPolygonToAreaTable(osmid, 1, areaType, tags, polyString, layer)
                   
                elif tags["type"]=="enforcement":
                    if "enforcement" in tags:
                        if tags["enforcement"]=="maxspeed":
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
                                storedRefId, lat, lon=self.getCoordsEntry(fromRefId)
                                if storedRefId!=None:
                                    tags["deviceRef"]=deviceRef
                                    self.addToPOIRefTable(fromRefId, 0, lat, lon, tags, Constants.POI_TYPE_ENFORCEMENT_WAYREF, 0)
                   
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
    
    def findWayWithRefInAllWays(self, refId, fromWayId):
        possibleWays=list()
        
        wayIdList=self.getWaysForRef(refId)
        if wayIdList==None or len(wayIdList)<=1:
            # no crossings at ref if not more then on different wayIds
            return possibleWays
        
        for wayid in wayIdList: 
            wayEntryId, tags, refs, streetInfo, name, nameRef, _, _=self.getWayEntryForId(wayid)   
            if wayEntryId==None:
                self.log("create crossings: skip crossing for wayId %s at refId %d to wayId %d"%(fromWayId, refId, wayid))
                continue
            
            streetTypeId, oneway, roundabout=self.decodeStreetInfo(streetInfo)
            
            for wayRef in refs:
                if wayRef==refId:
                    # dont add same wayid if at beginning or end
                    if fromWayId==wayid:
                        if refId==refs[0] or refId==refs[-1]:
                            continue
                    possibleWays.append((wayid, tags, refs, streetTypeId, name, nameRef, oneway, roundabout))
        
        return possibleWays      
    
    def getAdressListForStreetAndNumber(self, streetName, houseNumber):
        streetList=list()
        
        self.cursorAdress.execute('SELECT * FROM addressTable WHERE streetName="%s" AND houseNumber="%s"'%(streetName, houseNumber))
        allentries=self.cursorAdress.fetchall()
        for x in allentries:
            streetList.append(self.addressFromDB(x))
            
        return streetList
 
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

    def createEdgeTableEntries(self):
        self.cursorWay.execute('SELECT * FROM wayTable')
        allWays=self.cursorWay.fetchall()
        
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
             
            edgeId=int(edgeEntryId[0])
            edge=self.getEdgeEntryForEdgeId(edgeId)
            self.createEdgeTableNodeSameStartEnriesFor(edge)
            
            edge=self.getEdgeEntryForEdgeId(edgeId)
            self.createEdgeTableNodeSameEndEnriesFor(edge)

            edge=self.getEdgeEntryForEdgeId(edgeId)
            self.createEdgeTableNodeSourceEnriesFor(edge)

        print("")
        
        self.cursorEdge.execute('SELECT id FROM edgeTable WHERE source=0 OR target=0')
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
    
    def createBarrierRestrictions(self):
        allRestricitionLength=len(self.barrierRestrictionList)
        allRestrictionCount=0

        prog = ProgressBar(0, allRestricitionLength, 77)

        for barrierRestrictionEntry in self.barrierRestrictionList:
            prog.updateAmount(allRestrictionCount)
            print(prog, end="\r")
            allRestrictionCount=allRestrictionCount+1
            
            wayId=barrierRestrictionEntry["wayId"]
            ref=barrierRestrictionEntry["ref"]
            
            _, _, refs, _, _, _, _, _=self.getWayEntryForId(wayId)

            if not ref in refs:
                continue
            
            fromEdge=None
            toEdge=None
            
            if ref==refs[0] or ref==refs[-1]:
                # barrier at start or end of way
                resultList=self.getEdgeEntryForStartOrEndPoint(ref)
                
                # find first edge with the barrier
                for edge in resultList:
                    _, startRef, endRef, _, edgeWayId, _, _, _, _=edge
                    if edgeWayId==wayId:
                        fromEdge=edge
                        break
                
                if fromEdge!=None:
                    # add restriction from and to all others
                    for edge in resultList:
                        _, startRef, endRef, _, edgeWayId, _, _, _, _=edge
                        if edge==fromEdge:
                            continue
                        
                        toEdge=edge
                        
                        self.usedBarrierList.append(ref)
    
                        self.addToRestrictionTable(toEdge[0], str(fromEdge[0]), 10000)
                        self.addToRestrictionTable(fromEdge[0], str(toEdge[0]), 10000)
                else:
                    self.log("createBarrierRestrictions: failed to resolve fromEdge for %s"%(barrierRestrictionEntry))
            else:
                # barrier in the middle of the way
                resultList=self.getEdgeEntryForWayId(wayId)
                for edge in resultList:
                    _, startRef, endRef, _, _, _, _, _, _=edge
                    if startRef==ref or endRef==ref:
                        if fromEdge==None:
                            fromEdge=edge
                        else:
                            toEdge=edge
                            break
                        
                if fromEdge!=None and toEdge!=None:
                    self.usedBarrierList.append(ref)
                    
                    self.addToRestrictionTable(toEdge[0], str(fromEdge[0]), 10000)
                    self.addToRestrictionTable(fromEdge[0], str(toEdge[0]), 10000)
                else:
                    self.log("createBarrierRestrictions: failed to resolve %s"%(barrierRestrictionEntry))
   
        self.barrierRestrictionList=None
        print("")
        
    def createWayRestrictionsDB(self):
        allRestricitionLength=len(self.wayRestricitionList)
        allRestrictionCount=0

        prog = ProgressBar(0, allRestricitionLength, 77)

        toAddRules=list()
        for wayRestrictionEntry in self.wayRestricitionList:
            prog.updateAmount(allRestrictionCount)
            print(prog, end="\r")
            allRestrictionCount=allRestrictionCount+1

            fromWayId=int(wayRestrictionEntry["from"])
            toWayId=int(wayRestrictionEntry["to"])
            restrictionType=wayRestrictionEntry["type"]

            if "viaWay" in wayRestrictionEntry:
#                self.log("relation with via type way %s"%(wayRestrictionEntry))
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
        
        self.wayRestricitionList=None
        print("")
            
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
    
    def getAccessFactor(self, tags, streetTypeId):
        value=None
        if "vehicle" in tags:
            value=tags["vehicle"]

        if "motorcar" in tags:
            value=tags["motorcar"]
                
        if "motor_vehicle" in tags:
            value=tags["motor_vehicle"]
            
        if "access" in tags:
            value=tags["access"]
            
        if value!=None:
            if value=="destination":
                return 1000
            if value=="permissive":
                return 1000
            if value=="private":
                return 10000
            if value=="no":
                return 10000
            
            # TODO: everything else
            return 10000

        # avoid living streets
        if streetTypeId==Constants.STREET_TYPE_LIVING_STREET:
            # living_street
            return 1000
        
        # never route over parking_aisle
        if "service" in tags:
            if tags["service"]=="parking_aisle":
                return 10000
            
        return 1
    
    def getCostsOfWay(self, wayId, tags, distance, crossingFactor, streetInfo, maxspeed):
            
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
            self.log(tags)
        except TypeError:
            cost=distance
            self.log(tags)
            
        if oneway==1:
            reverseCost=100000
        elif oneway==2:
            reverseCost=cost
            cost=100000
        else:
            reverseCost=cost
        
        return cost, reverseCost

    def createEdgeTableEntriesForWay(self, way):        
        wayId, tags, refs, streetInfo, _, _, maxspeed, _=self.wayFromDB(way)
        resultList=self.getCrossingEntryFor(wayId)
                
        nextWayDict=dict()
        for result in resultList:
            _, wayId, refId, nextWayIdList=result                    
            nextWayDict[refId]=nextWayIdList
        
        crossingFactor=1
        
        crossingRefs=set()
        for ref in refs:                  
            if ref in nextWayDict:                                                                        
                crossingRefs.add(ref)
        
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

            if ref in crossingRefs:
                if len(refNodeList)!=0:
                        
                    refNodeList.append(ref)
                    startRef=refNodeList[0]
                    endRef=refNodeList[-1]                 

                    refList=self.getRefListSubset(refs, startRef, endRef)
                    coords, _=self.createRefsCoords(refList)
                    if len(coords)>=2:
                        cost, reverseCost=self.getCostsOfWay(wayId, tags, distance, crossingFactor, streetInfo, maxspeed)                                         
                        self.addToEdgeTable(startRef, endRef, distance, wayId, cost, reverseCost, streetInfo, coords)
#                    else:
#                        self.log("createEdgeTableEntriesForWay: skipping wayId %d from %d to %d len(coords)<2"%(wayId, startRef, endRef))

                    refNodeList=list()
                    distance=0
           
            refNodeList.append(ref)
        
        # handle last portion
        if not ref in crossingRefs:
            if len(refNodeList)!=0:
                startRef=refNodeList[0]
                endRef=refNodeList[-1]
                
                refList=self.getRefListSubset(refs, startRef, endRef)
                coords, _=self.createRefsCoords(refList)                
                if len(coords)>=2:
                    cost, reverseCost=self.getCostsOfWay(wayId, tags, distance, crossingFactor, streetInfo, maxspeed)                    
                    self.addToEdgeTable(startRef, endRef, distance, wayId, cost, reverseCost, streetInfo, coords)
#                else:
#                    self.log("createEdgeTableEntriesForWay: skipping wayId %d from %d to %d len(coords)<2"%(wayId, startRef, endRef))

    # lat, lon
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
            
    def isLinkToLink(self, streetTypeId, streetTypeId2):
        return (streetTypeId==Constants.STREET_TYPE_MOTORWAY_LINK and streetTypeId2==Constants.STREET_TYPE_MOTORWAY_LINK) or (streetTypeId==Constants.STREET_TYPE_TRUNK_LINK and streetTypeId2==Constants.STREET_TYPE_TRUNK_LINK) or (streetTypeId==Constants.STREET_TYPE_PRIMARY_LINK and streetTypeId2==Constants.STREET_TYPE_PRIMARY_LINK) or (streetTypeId==Constants.STREET_TYPE_SECONDARY_LINK and streetTypeId2==Constants.STREET_TYPE_SECONDARY_LINK) or (streetTypeId==Constants.STREET_TYPE_TERTIARY_LINK and streetTypeId2==Constants.STREET_TYPE_TERTIARY_LINK)

    def isLinkEnter(self, streetTypeId, streetTypeId2):
        return (streetTypeId!=Constants.STREET_TYPE_MOTORWAY_LINK and streetTypeId2==Constants.STREET_TYPE_MOTORWAY_LINK) or (streetTypeId!=Constants.STREET_TYPE_TRUNK_LINK and streetTypeId2==Constants.STREET_TYPE_TRUNK_LINK) or (streetTypeId!=Constants.STREET_TYPE_PRIMARY_LINK and streetTypeId2==Constants.STREET_TYPE_PRIMARY_LINK) or (streetTypeId!=Constants.STREET_TYPE_SECONDARY_LINK and streetTypeId2==Constants.STREET_TYPE_SECONDARY_LINK) or (streetTypeId!=Constants.STREET_TYPE_TERTIARY_LINK and streetTypeId2==Constants.STREET_TYPE_TERTIARY_LINK)

    def isLinkExit(self, streetTypeId, streetTypeId2):
        return (streetTypeId==Constants.STREET_TYPE_MOTORWAY_LINK and streetTypeId2!=Constants.STREET_TYPE_MOTORWAY_LINK) or (streetTypeId==Constants.STREET_TYPE_TRUNK_LINK and streetTypeId2!=Constants.STREET_TYPE_TRUNK_LINK) or (streetTypeId==Constants.STREET_TYPE_PRIMARY_LINK and streetTypeId2!=Constants.STREET_TYPE_PRIMARY_LINK) or (streetTypeId==Constants.STREET_TYPE_SECONDARY_LINK and streetTypeId2!=Constants.STREET_TYPE_SECONDARY_LINK) or (streetTypeId==Constants.STREET_TYPE_TERTIARY_LINK and streetTypeId2!=Constants.STREET_TYPE_TERTIARY_LINK)

    def createCrossingEntries(self):
        self.cursorWay.execute('SELECT * FROM wayTable')
        allWays=self.cursorWay.fetchall()
        
        allWaysLength=len(allWays)
        allWaysCount=0

        prog = ProgressBar(0, allWaysLength, 77)
        nodeTypeList=list()
        nodeTypeList.append(Constants.POI_TYPE_BARRIER)
        nodeTypeList.append(Constants.POI_TYPE_MOTORWAY_JUNCTION)
        
        poiDict=self.getAllPOIRefEntrysDict(nodeTypeList)
        
        for way in allWays:
            wayid, _, refs, streetInfo, name, _, _, _=self.wayFromDB(way)
            streetTypeId, oneway, roundabout=self.decodeStreetInfo(streetInfo)
  
            prog.updateAmount(allWaysCount)
            print(prog, end="\r")
            allWaysCount=allWaysCount+1
                        
            for ref in refs:  
                majorCrossingType=Constants.CROSSING_TYPE_NORMAL
                majorCrossingInfo=None  
                
                nextWays=self.findWayWithRefInAllWays(ref, wayid)  
                if len(nextWays)==0:
                    if ref!=refs[0] and ref!=refs[-1]:
                        poiKey="%d:%d"%(ref,Constants.POI_TYPE_BARRIER)                    
                        if poiKey in poiDict.keys():
                            # barrier on a way - need to split 
                            # create a crossing with the same ways                           
                            barrierRestrictionEntry=dict()
                            barrierRestrictionEntry["wayId"]=wayid
                            barrierRestrictionEntry["ref"]=ref
                            self.barrierRestrictionList.append(barrierRestrictionEntry)
                            
                            wayList=list()
                            wayList.append((wayid, Constants.CROSSING_TYPE_BARRIER, ref))

                            self.addToCrossingsTable(wayid, ref, wayList)
                            continue

                if len(nextWays)!=0:  
                    poiKey="%d:%d"%(ref,Constants.CROSSING_TYPE_MOTORWAY_EXIT)
                    if poiKey in poiDict.keys():                 
                        nodeTags=poiDict[poiKey]
                        majorCrossingType=Constants.CROSSING_TYPE_MOTORWAY_EXIT
                        highwayExitRef=None
                        highwayExitName=None
                        if "ref" in nodeTags:
                            highwayExitRef=nodeTags["ref"]
                        if "name" in nodeTags:
                            highwayExitName=nodeTags["name"]
                        majorCrossingInfo="%s:%s"%(highwayExitName, highwayExitRef)                             
                                
                    # Constants.POI_TYPE_BARRIER
                    poiKey="%d:%d"%(ref,Constants.POI_TYPE_BARRIER)
                    if poiKey in poiDict.keys():
                        majorCrossingType=Constants.CROSSING_TYPE_BARRIER
                        
                        barrierRestrictionEntry=dict()
                        barrierRestrictionEntry["wayId"]=wayid
                        barrierRestrictionEntry["ref"]=ref
                        self.barrierRestrictionList.append(barrierRestrictionEntry)
                        crossingInfo=ref
                        
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
          
    def createPOIEntriesForWays(self):
        self.log("create POI way entries")
        self.cursorNode.execute('SELECT refId, tags, type, layer, AsText(geom) FROM poiRefTable WHERE (type=%d OR type=%d) AND refType=0'%(Constants.POI_TYPE_ENFORCEMENT_WAYREF, Constants.POI_TYPE_BARRIER))
        allRefs=self.cursorNode.fetchall()
        
        allRefsLength=len(allRefs)
        allRefsCount=0

        prog = ProgressBar(0, allRefsLength, 77)

        for x in allRefs:
            prog.updateAmount(allRefsLength)
            print(prog, end="\r")
            allRefsCount=allRefsCount+1
            
            refId, lat, lon, tags, nodeType, _=self.poiRefFromDB(x)
                    
            poiList=list()
            poiList.append((refId, nodeType))
            
            self.cursorWay.execute('SELECT wayId, refs, poiList FROM wayTable WHERE ROWID IN (SELECT rowid FROM idx_wayTable_geom WHERE rowid MATCH RTreeIntersects(%f, %f, %f, %f))'%(lon, lat, lon, lat))
            allWays=self.cursorWay.fetchall()
            if len(allWays)==0:
                self.log("could not resolve way for POI refId %d"%(refId))
                continue
            
            wayResoled=False
            for x in allWays:
                wayId=int(x[0])
                refs=pickle.loads(x[1])
                if x[2]!=None:
                    storedPOIList=pickle.loads(x[2])
                    poiList.extend(storedPOIList)
                
                if refId in refs:          
                    self.updateWayTableEntryPOIList(wayId, poiList)
                    wayResoled=True
            
            if wayResoled==False:
                self.log("could not resolve way for POI refId %d"%(refId))
                    
            
        print("")  
        
    def parse(self, country):
        osmFile=self.getOSMFile(country)
        if osmFile!=None:
            self.log(self.osmList[country])
            self.log("start parsing")
            p = XMLParser(nodes_callback=self.parse_nodes, 
                      ways_callback=self.parse_ways, 
                      relations_callback=self.parse_relations,
                      coords_callback=self.parse_coords)
            
#            p = OSMParser(4, nodes_callback=self.parse_nodes, 
#                      ways_callback=self.parse_ways, 
#                      relations_callback=self.parse_relations,
#                      coords_callback=self.parse_coords)
            
            p.parse(osmFile)

    def getOSMFile(self, country):
        return self.osmList[country]["osmFile"]
    
    def initDB(self):
        self.log(self.getDataDir())
                    
        self.openCoordsDB()
        self.createCoordsDBTables()

        self.openTmpDB()
        self.createTmpTable()

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

        createWayDB=not self.wayDBExists()
        if createWayDB:
            self.openWayDB()
            self.createWayDBTables()
        else:
            self.openWayDB()

        createNodeDB=not self.nodeDBExists()
        if createNodeDB:
            self.openNodeDB()
            self.createNodeDBTables()
        else:
            self.openNodeDB()

        if createWayDB==True:
            self.skipNodes=False
            self.skipWays=False
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
  
                self.parse(country)
                self.commitWayDB()
                self.commitNodeDB()
                self.commitAdressDB()
            
            self.commitCoordsDB()
            
            # not needed anymore
            self.addressCache=None
                       
#            self.log("merge ways")
#            self.mergeWayEntries()
#            self.log("end merge ways")
                        
            self.log("create crossings")
            self.createCrossingEntries()
            
            self.commitWayDB()
            self.commitNodeDB()
            
        # not needed anymore
        self.closeTmpDB()

        if createEdgeDB:            
            self.log("create edges")
            self.createEdgeTableEntries()

            self.log("create edge nodes")
            self.createEdgeTableNodeEntries()
                        
            self.log("create barrier restriction entries")
            self.createBarrierRestrictions()
            
            self.log('remove orphaned barriers')
            self.removeOrphanedBarriers()

            self.log("create way restrictions")
            self.createWayRestrictionsDB()              

            self.log("remove orphaned edges")
            self.removeOrphanedEdges()
            self.commitEdgeDB()

            self.log("remove orphaned ways")
            self.removeOrphanedWays()
            self.commitWayDB()
                        
            self.log("vacuum way DB")
            self.vacuumWayDB()
            
            self.log("vacuum edge DB")
            self.vacuumEdgeDB()
            
            self.log("vacuum area DB")
            self.vacuumAreaDB()
            
        if createWayDB==True:
            self.log("create spatial index for way table")
            self.createSpatialIndexForWayTables()

        if createNodeDB==True:
            self.log("create spatial index for node table")
            self.createSpatialIndexForNodeTables()
            
        if createAreaDB==True:
            self.log("create spatial index for area table")
            self.createSpatialIndexForAreaTable()

        if createEdgeDB==True:
            self.log("create spatial index for edge table")
            self.createSpatialIndexForEdgeTable()

        if createAreaDB==True:
            self.resolveAdminAreas()
            
        if createAdressDB==True:
            self.resolveAddresses(True)
            self.commitAdressDB()
            self.vacuumAddressDB()

        self.removeUnnededPOIs()        
        self.createPOIEntriesForWays()
        self.resolvePOIRefs()
        
        self.log("vaccum node DB")
        self.vacuumNodeDB()

        self.closeCoordsDB()
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
            
            self.parse(country)
                
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
            
            self.parse(country)
                
        self.commitNodeDB()
    
    def parseRelations(self):
        self.skipWays=True
        self.skipNodes=True
        self.skipRelations=False
        self.skipAddress=True
        self.skipHighways=True
        self.skipCoords=True
        self.skipAreas=True
        self.skipPOINodes=True
        
        countryList=self.osmList.keys()
        for country in countryList:       
            self.firstRelation=False
            self.firstWay=False
            self.firstNode=False   
            
            self.parse(country)

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
            
            self.log(self.osmList[country])
            self.log("start parsing")
            self.parse(country)
            self.log("end parsing")
                
        self.commitAdressDB()
        
    def initBoarders(self):
        self.bu=OSMBoarderUtils(getPolyDataRoot())
        self.bu.initData()

#        self.buSimple=OSMBoarderUtils(env.getPolyDataRootSimple())
#        self.buSimple.initData()
                        
#    def recreateCrossings(self):
#        self.clearCrosssingsTable()
#        
#        self.log("recreate crossings")
#        self.createCrossingEntries()
#        self.log("end recreate crossings")
                                
#    def recreateEdges(self):
#        self.clearEdgeTable()
#        self.log("recreate edges")
#        self.createEdgeTableEntries()
#        self.log("end recreate edges")   
#                        
#        self.log("recreate edge nodes")
#        self.createEdgeTableNodeEntries()
#        self.log("end recreate edge nodes")
#        
#        self.log("create barrier restriction entries")
#        self.createBarrierRestrictions()
#        
##        self.log("remove orphaned edges")
##        self.removeOrphanedEdges()
##        self.log("end remove orphaned edges")
##        
##        self.log("vacuum edge DB")
##        self.vacuumEdgeDB()
##        self.log("end vacuum edge DB")

    def getStreetTypeIdForAddesses(self):
        return Constants.ADDRESS_STREET_SET

    def resolveAddresses(self, addWays):
        self.log("resolve addresses from admin boundaries")
        adminLevelList=[4, 6, 8]
        self.addressId=self.getLenOfAddressTable()
        
        self.cursorAdress.execute('SELECT * FROM addressTable')
        allentries=self.cursorAdress.fetchall()
        
        allAddressLength=len(allentries)
        allAddressCount=0

        prog = ProgressBar(0, allAddressLength, 77)
                
        adminList=self.getAllAdminAreas(adminLevelList, True)
        adminList.reverse()
        
        polyList=list()
        for area in adminList:
            osmId=area[0]
            tags=area[1]
            polyStr=area[3]
            
            if "name" in tags:
                coordsList=self.getGISUtils().createCoordsFromPolygonString(polyStr)
                for coords, _ in coordsList:
                    cPolygon=Polygon(coords)
                    polyList.append((osmId, cPolygon))
        
        countryCache=dict()
        for x in allentries:
            addressId, _, _, storedCity, _, streetName, _, lat, lon=self.addressFromDB(x)
            
            prog.updateAmount(allAddressCount)
            print(prog, end="\r")
            allAddressCount=allAddressCount+1
            
            if storedCity!=None:
                continue
            
            resolved=False
            for osmId, cPolygon in polyList:
                if cPolygon.isInside(lat, lon): 
                    country=None
                    if not osmId in countryCache.keys():
                        adminDict=dict() 
                        self.getAdminListForId(osmId, adminDict)
                        if 2 in adminDict.keys():
                            country=adminDict[2]
                            countryCache[osmId]=country
                    else:
                        country=countryCache[osmId]
                        
                    if country!=None:
                        self.updateAddressEntry(addressId, country, osmId)
#                    else:
#                        self.log("unknown country for %d"%(osmId))
                    resolved=True
                    break
                    
#            if resolved==False:
#                self.log("failed to resolve %s"%(streetName))
                
        print("")
        
        if addWays==True:
            self.log("add all ways to address DB")
            self.cursorWay.execute('SELECT * FROM wayTable')
            allWays=self.cursorWay.fetchall()
            
            allWaysLength=len(allWays)
            allWaysCount=0
    
            prog = ProgressBar(0, allWaysLength, 77)
            
            addressSet=set()
            for way in allWays:
                _, _, refs, streetInfo, streetName, _, _, _=self.wayFromDB(way)
                streetTypeId, _, _=self.decodeStreetInfo(streetInfo)
                
                prog.updateAmount(allWaysCount)
                print(prog, end="\r")
                allWaysCount=allWaysCount+1
                
                if streetName==None:
                    continue
                
                if not streetTypeId in self.getStreetTypeIdForAddesses():
                    continue
                
                # TODO: which ref to use for way address
                # could be somewhere in the middle 
                refId, lat, lon=self.getCoordsEntry(refs[0])
    
                if refId!=None:
                    resolved=False
                    for osmId, cPolygon in polyList:
                        if cPolygon.isInside(lat, lon):    
                            if not "%s-%d"%(streetName, osmId) in addressSet:
                                country=None
                                if not osmId in countryCache.keys():
                                    adminDict=dict() 
                                    self.getAdminListForId(osmId, adminDict)
                                    if 2 in adminDict.keys():
                                        country=adminDict[2]
                                        countryCache[osmId]=country
                                else:
                                    country=countryCache[osmId]
                                
                                if country!=None:
                                    self.addToAddressTable2(refId, country, osmId, streetName, None, lat, lon)
    #                            else:
    #                                self.log("unknown country for %d"%(osmId))
                                addressSet.add("%s-%s"%(streetName, osmId))
                            
                            resolved=True
                            break
                            
    #                if resolved==False:
    #                    self.log("failed to resolve %s"%(streetName))
                        
            print("")

    def poiRefFromDB2(self, x):
        refId=int(x[0])
        refType=int(x[1])
        poiType=int(x[2])      
        city=x[3]      
        lat, lon=self.getGISUtils().createPointFromPointString(x[4])
        return (refId, refType, poiType, lat, lon, city)    
    
    def resolvePOIRefs(self):
        self.log("resolve POI refs from admin boundaries")
        adminLevelList=[4, 6, 8]
        self.cursorNode.execute('SELECT refId, refType, type, city, AsText(geom) FROM poiRefTable')
        allentries=self.cursorNode.fetchall()
        
        allPOIRefsLength=len(allentries)
        allPOIRefCount=0

        prog = ProgressBar(0, allPOIRefsLength, 77)
                
        adminList=self.getAllAdminAreas(adminLevelList, True)
        adminList.reverse()
        
        polyList=list()
        for area in adminList:
            osmId=area[0]
            tags=area[1]
            polyStr=area[3]
            
            if "name" in tags:
                coordsList=self.getGISUtils().createCoordsFromPolygonString(polyStr)
                for coords, _ in coordsList:
                    cPolygon=Polygon(coords)
                    polyList.append((osmId, cPolygon))
        
        countryCache=dict()
        for x in allentries:
            (refId, refType, poiType, lat, lon, storedCity)=self.poiRefFromDB2(x)
                        
            prog.updateAmount(allPOIRefCount)
            print(prog, end="\r")
            allPOIRefCount=allPOIRefCount+1
            
            if storedCity!=None:
                continue
            
            for osmId, cPolygon in polyList:
                if cPolygon.isInside(lat, lon):  
                    country=None
                    if not osmId in countryCache.keys():
                        adminDict=dict() 
                        self.getAdminListForId(osmId, adminDict)
                        if 2 in adminDict.keys():
                            country=adminDict[2]
                            countryCache[osmId]=country
                    else:
                        country=countryCache[osmId]
                    
                    if country!=None:
                        self.updatePOIRefEntry(refId, refType, poiType, country, osmId)
#                    else:
#                        self.log("unknown country for %d"%(osmId))
  
                    break
                
        print("")        
                
    def resolveAdminAreas(self):
        self.log("resolve admin area relations")

        adminLevelList=[8, 6, 4, 2]
        
        adminList=self.getAllAdminAreas(adminLevelList, True)
        
        osmCountryList=list()
        for area in adminList:
            osmId=area[0]
            tags=area[1]
            adminLevel=area[2]
            if adminLevel==2:
                if "name:de" in tags:
                    osmCountryList.append(tags["name:de"])
                if "int_name" in tags:
                    osmCountryList.append(tags["int_name"])
                elif "name" in tags:
                    osmCountryList.append(tags["name"])
  
        # add missing countries from poly files to support
        # parsing parts of countries
        polyCountryList=self.bu.getPolyCountryList()
        i=0
        for polyCountryName in polyCountryList:
            if not polyCountryName in osmCountryList:
                self.log("add country %s from polylist"%(polyCountryName))
                polyString=self.bu.createMultiPolygonFromPoly(polyCountryName)
                tags=dict()
                tags["int_name"]=polyCountryName
                tags["name:de"]=polyCountryName
                tags["name"]=polyCountryName
                adminLevel=2
                # make sure it does not clash with other admin relations
                self.addPolygonToAdminAreaTable(self.highestAdminRelationNumber+1+i, tags, adminLevel, polyString)
                i=i+1

        adminList=self.getAllAdminAreas(adminLevelList, True)
        polyList={2:[], 4:[], 6:[], 8:[]}
        for area in adminList:
            osmId=area[0]
            tags=area[1]
            adminLevel=area[2]
            polyStr=area[3]
            
            coordsList=self.getGISUtils().createCoordsFromPolygonString(polyStr)
            for coords, _ in coordsList:
                cPolygon=Polygon(coords)
                polyList[adminLevel].append((osmId, cPolygon, tags))

        amount=1
        prog = ProgressBar(0, len(adminLevelList)-1, 77)
        
        for adminLevel in adminLevelList[:-1]:
            currentAdminLevelIndex=adminLevelList.index(adminLevel)
            prog.updateAmount(amount)
            print(prog, end="\r")
            
            for osmId, cPolygon, tags in polyList[adminLevel]:
                resolved=False
                
                i=currentAdminLevelIndex+1
                for adminLevel2 in adminLevelList[i:]:
                    if resolved==True:
                        break
                    for osmId2, cPolygon2, tags2 in polyList[adminLevel2]:
                        if cPolygon2.overlaps(cPolygon):
                            self.updateAdminAreaParent(osmId, osmId2)
                            resolved=True
                            break
                    i=i+1
            amount=amount+1

        print("") 
                
    def getAdminListForId(self, osmId, adminDict):
        self.cursorArea.execute('SELECT osmId, adminLevel, parent FROM adminAreaTable WHERE osmId=%d'%(osmId))
        allentries=self.cursorArea.fetchall()
        if len(allentries)==1:
            x=allentries[0]
            osmId=int(x[0])
            adminLevel=int(x[1])
            parent=x[2]
            if parent==None or parent==0:
                adminDict[adminLevel]=osmId
                return
            else:
                parent=int(parent)
                adminDict[adminLevel]=osmId
                return self.getAdminListForId(parent, adminDict)                    
    
    def vacuumEdgeDB(self):
        self.cursorEdge.execute('VACUUM')

    def vacuumWayDB(self):
        self.cursorWay.execute('VACUUM')

    def vacuumNodeDB(self):
        self.cursorNode.execute('VACUUM')

    def vacuumAddressDB(self):
        self.cursorAdress.execute('VACUUM')

    def vacuumAreaDB(self):
        self.cursorArea.execute('VACUUM')

    def vacuumCoordsDB(self):
        self.cursorCoords.execute('VACUUM')
                                
    def removeOrphanedEdges(self):
        self.cursorEdge.execute('SELECT * FROM edgeTable')
        allEdges=self.cursorEdge.fetchall()
        
        allEdgesLength=len(allEdges)
        allEdgesCount=0

        removeCount=0
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
#                self.log("remove edge %d %d %d %d"%(edgeId, wayId, startRef, endRef))
                self.cursorEdge.execute('DELETE FROM edgeTable WHERE id=%d'%(edgeId))
                removeCount=removeCount+1

        print("")
        self.log("removed %d edges"%(removeCount))
        
    def removeOrphanedWays(self):
        self.cursorWay.execute('SELECT * FROM wayTable')
        allWays=self.cursorWay.fetchall()
        
        allWaysLength=len(allWays)
        allWaysCount=0

        removeCount=0
        prog = ProgressBar(0, allWaysLength, 77)
        for way in allWays:
            wayid, _, _, _, _, _, _, _=self.wayFromDB(way)

            prog.updateAmount(allWaysCount)
            print(prog, end="\r")
            allWaysCount=allWaysCount+1

            resultList=self.getEdgeEntryForWayId(wayid)
            if len(resultList)==0:
#                for ref in refs:
#                    self.cursorNode.execute('DELETE FROM refTable WHERE refId=%d'%(ref))
                    
                self.cursorWay.execute('DELETE FROM wayTable WHERE wayId=%d'%(wayid))
                removeCount=removeCount+1
        
        print("")
        self.log("removed %d ways"%(removeCount))
        
    def removeOrphanedBarriers(self):
        if len(self.usedBarrierList)!=0:
            barrierSet=set(self.usedBarrierList)
            self.cursorNode.execute('SELECT refId FROM poiRefTable WHERE type=%d AND refType=0'%(Constants.POI_TYPE_BARRIER))
            allBarrierRefs=self.cursorNode.fetchall()
            
            allRefLength=len(allBarrierRefs)
            allRefsCount=0
            removeCount=0

            prog = ProgressBar(0, allRefLength, 77)
            
            for x in allBarrierRefs:
                refId=int(x[0])
                prog.updateAmount(allRefsCount)
                print(prog, end="\r")
                allRefsCount=allRefsCount+1
                
                if not refId in barrierSet:
                    self.cursorNode.execute('DELETE FROM poiRefTable WHERE refId NOTNULL AND refId=%d AND type=%d AND refType=0'%(refId, Constants.POI_TYPE_BARRIER))
                    removeCount=removeCount+1
            print("")
            self.log("removed %d nodes"%(removeCount))
            
    def removeBuildings(self):
        self.cursorArea.execute('SELECT osmId, type FROM areaTable WHERE type=%d'%(Constants.AREA_TYPE_BUILDING))
        allBuildings=self.cursorArea.fetchall()
        for area in allBuildings:
            osmId=area[0]
            self.cursorArea.execute('DELETE FROM areaTable WHERE osmId=%d AND type=%d'%(osmId, Constants.AREA_TYPE_BUILDING))

    def recreateCostsForEdges(self):
        self.log("recreate costs")
        self.cursorEdge.execute('SELECT * FROM edgeTable')
        allEdges=self.cursorEdge.fetchall()
        
        allEdgesLength=len(allEdges)
        allEdgesCount=0

        prog = ProgressBar(0, allEdgesLength, 77)
        
        for edge in allEdges:
            prog.updateAmount(allEdgesCount)
            print(prog, end="\r")
            allEdgesCount=allEdgesCount+1
            
            edgeId, _, _, length, wayId, _, _, cost, reverseCost=self.edgeFromDB(edge)
            wayId, tags, refs, streetInfo, _, _, maxspeed, _=self.getWayEntryForId(wayId)
            if wayId==None:
                continue
            
            streetTypeId, oneway, roundabout=self.decodeStreetInfo(streetInfo)
            cost, reverseCost=self.getCostsOfWay(wayId, tags, length, 1, streetTypeId, oneway, roundabout, maxspeed)
            self.updateCostsOfEdge(edgeId, cost, reverseCost)

        print("")
        
    def poiRefFromDB3(self, x):
        refId=int(x[0])
        tags=self.decodeTags(x[1])
        poiType=int(x[2])      
        lat, lon=self.getGISUtils().createPointFromPointString(x[3])
        return (refId, tags, poiType, lat, lon)    
      
    # check all pois of refType=node
    # inside an area with refType=way
    # with the same tags. If yes remove the entry for the way                             
    def removeUnnededPOIs(self):
        self.log("remove unneeded POIs")
        nodeTypeList=self.createSQLFilterStringForIN([Constants.POI_TYPE_PARKING, Constants.POI_TYPE_CAMPING, Constants.POI_TYPE_SUPERMARKET, Constants.POI_TYPE_PLACE])
        self.cursorNode.execute('SELECT refId, tags, type, AsText(geom) FROM poiRefTable WHERE refType=0 AND type in %s'%(nodeTypeList))
        allPOIRefs=self.cursorNode.fetchall()
        
        allRefLength=len(allPOIRefs)
        allRefsCount=0
        removeCount=0

        prog = ProgressBar(0, allRefLength, 77)
        
        for x in allPOIRefs:
            (refId, tags, poiType, lat, lon)=self.poiRefFromDB3(x)
            prog.updateAmount(allRefsCount)
            print(prog, end="\r")
            allRefsCount=allRefsCount+1

            lonRangeMin, latRangeMin, lonRangeMax, latRangeMax=self.createBBoxAroundPoint(lat, lon, 0.0)      
            self.cursorArea.execute('SELECT osmId FROM areaTable WHERE ROWID IN (SELECT rowid FROM idx_areaTable_geom WHERE rowid MATCH RTreeIntersects(%f, %f, %f, %f))'%(lonRangeMin, latRangeMin, lonRangeMax, latRangeMax))

            areaList=self.cursorArea.fetchall()
            for y in areaList:
                # in case of a wayRef polygon this is the wayId
                areaId=int(y[0])   
                # check if there is a poi node with this wayId         
                self.cursorNode.execute('SELECT refId, tags, type, AsText(geom) FROM poiRefTable WHERE refId=%d AND refType=1'%(areaId))
                allPOIWayRefs=self.cursorNode.fetchall()
            
                for z in allPOIWayRefs:
                    (refId1, tags1, poiType1, lat1, lon1)=self.poiRefFromDB3(z)
                    # same poi type
                    if poiType==poiType1:
                        removeRef=None
                        # a node POI "overrules" a way POI 
                        # except it has no tags and the way POI has
#                        print("POI node %d %s is inside of POI area %d %s"%(refId, tags, refId1, tags1))
                        if len(tags1)==0:
                            removeRef=refId1
                        elif len(tags)==0:
                            removeRef=refId
                        else:  
                            if poiType==Constants.POI_TYPE_PLACE:
                                if "name" in tags and "name" in tags1:
                                    if tags["place"]==tags1["place"] and tags["name"]==tags1["name"]:
                                        removeRef=refId1

                            else:
#                                if not "name" in tags and "name" in tags1:
#                                    removeRef=refId
                                    
                                removeRef=refId1
                        
                        if removeRef!=None:
#                            print("remove %d"%(removeRef))
                            self.cursorNode.execute("DELETE FROM poiRefTable WHERE refId=%d"%(removeRef))
                            removeCount=removeCount+1
                            
        print("")   
        self.log("removed %d nodes"%(removeCount))

    def createBBoxAroundPoint(self, lat, lon, margin):
        latRangeMax=lat+margin
        lonRangeMax=lon+margin*1.4
        latRangeMin=lat-margin
        lonRangeMin=lon-margin*1.4          
        
        return lonRangeMin, latRangeMin, lonRangeMax, latRangeMax
      
#    def mergeEqualWayEntries(self, wayId):        
#        self.cursorGlobal.execute('SELECT wayId, tags, refs, streetInfo, name, ref, maxspeed, poiList, AsText(geom) FROM wayTable WHERE wayId=%d'%(wayId))
#
#        allWays=self.cursorGlobal.fetchall()
#        way=allWays[0]
#        wayId, tags, refs, streetInfo, name, nameRef, maxspeed, poiList, coords=self.wayFromDBWithCoordsString(way)
#        if name!=None:
#            streetTypeId, oneway, roundabout=self.decodeStreetInfo(streetInfo)
#            
#            if oneway!=0 and roundabout==0:
#                return None
#            
#            allRefs=list()
#            allRefs.append((wayId, refs, oneway, roundabout))
#            resultList=self.getWayEntryForStreetName(name)
#            for otherWay in resultList:
#                otherWayId, otherTags, otherRefs, otherStreetInfo, _, otherNameRef, otherMaxspeed, otherPoiList, otherCoords=otherWay
#                if otherWayId==wayId:
#                    continue
#
#                streetTypeId, oneway, roundabout=self.decodeStreetInfo(otherStreetInfo)
#            
#                if oneway!=0 and roundabout==0:
#                    continue
#                
#                if streetInfo!=otherStreetInfo:
#                    continue
#                
#                if maxspeed!=otherMaxspeed:
#                    continue
#                
#                if nameRef!=otherNameRef:
#                    continue
#                
#                if len(tags)!=len(otherTags):
#                    continue
#                
#                if tags!=otherTags:
#                    continue
#                
#                allRefs.append((otherWayId, otherRefs, oneway, roundabout))
#            
#            refRings=self.mergeWayRefs(allRefs)
#            return refRings
#        
#        return None
              
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
#        self.log("old way length=%d"%(allWaysLength))
#
#        for way in allWays:
#            wayId, tags, refs, streetInfo, name, nameRef, maxspeed=self.wayFromTmpDB(way)
##            self.log(way)
#
#            if allWaysCount>waysBlockCount:
#                self.log("done %d"%(alLWaysPercentCount))
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
##                self.log(refRings)
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
##                            self.log("add merged way %d %s"%(wayId, wayIdList))
##                        else:
##                            self.log("add single way %d"%(wayId))
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
#                        self.log("mergeWayEntries: skipping wayId %d because of missing coords"%(wayId))
#    
#            else:
#                doneWays.add(wayId)
#                coords, newRefList=self.createRefsCoords(refs)
#                if len(coords)!=0:
##                    self.log("add single way %d"%wayId)
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
#                    self.log("mergeWayEntries: skipping wayId %d because of missing coords"%(wayId))
#
#        if len(doneWays)!=allWaysLength:
#            self.log("length missmatch")
#        
#        self.log("new way length=%d"%(newWayCount))

    def log(self, text):
        importLog.addTrackLogLine(str(text))
        
def main(argv):    
    p = OSMDataImport()
    
    p.initDB()
#    p.openAdressDB()
#    p.createAdressTable()
#    p.closeAdressDB()
    
    p.openAllDB()
#    p.cursorArea.execute("SELECT * FROM sqlite_master WHERE type='table'")
#    allentries=p.cursorArea.fetchall()
#    for x in allentries:
#        self.log(x)


#    p.cursorEdge.execute('PRAGMA table_info(cache_edgeTable_Geometry)')
#    p.cursorEdge.execute('SELECT DiscardGeometryColumn("edgeTable", "geom")')
#    p.cursorEdge.execute("SELECT RecoverGeometryColumn('edgeTable', 'geom', 4326, 'LINESTRING', 2)")
#    p.cursorEdge.execute('SELECT CreateSpatialIndex("edgeTable", "geom")')
#
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
#    p.testAreaTable()
       

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
    
    p.closeAllDB()


if __name__ == "__main__":
#    cProfile.run('main(sys.argv)')
    main(sys.argv)  
    

