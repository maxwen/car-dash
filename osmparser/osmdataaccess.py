'''
Created on Dec 13, 2011

@author: maxl
'''
import sys
import os
import sqlite3
from osmparser.osmutils import OSMUtils
import pickle
import env
import re
import cProfile

#from pygraph-routing.dijkstrapygraph import DijkstraWrapperPygraph
#from igraph.dijkstraigraph import DijkstraWrapperIgraph

from osmparser.osmboarderutils import OSMBoarderUtils
from trsp.trspwrapper import TrspWrapper

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
    CROSSING_TYPE_BARRIER=10
    
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
    POI_TYPE_AIRPORT=12
    POI_TYPE_RAILWAYSTATION=13
    POI_TYPE_VETERIANERY=15
    POI_TYPE_CAMPING=16
    
    AREA_TYPE_NATURAL=1
    AREA_TYPE_LANDUSE=2
    AREA_TYPE_BUILDING=3
    AREA_TYPE_HIGHWAY_AREA=4
    AREA_TYPE_RAILWAY=5
    AREA_TYPE_AEROWAY=6
    AREA_TYPE_TOURISM=7
    AREA_TYPE_AMENITY=8
    
    LANDUSE_TYPE_SET=set(["forest", "grass", "field", "farm", "farmland", "farmyard", "meadow", "residential", "greenfield", "brownfield", "commercial", "industrial", "railway", "water", "reservoir", "basin", "cemetery", "military", "recreation_ground", "village_green", "allotments", "orchard", "retail", "construction"])
    LANDUSE_NATURAL_TYPE_SET=set(["forest", "grass", "field", "farm", "farmland", "meadow", "greenfield", "brownfield", "farmyard", "recreation_ground", "village_green", "allotments", "orchard"])
    LANDUSE_WATER_TYPE_SET=set(["reservoir", "basin", "water"])
    
    NATURAL_TYPE_SET=set(["water", "wood", "tree", "forest", "park", "riverbank", "fell", "scrub", "heath", "grassland", "wetland", "scree"])
    NATURAL_WATER_TYPE_SET=set(["water", "riverbank", "wetland"])
    
    WATERWAY_TYPE_SET=set(["riverbank", "river", "stream", "drain", "ditch"])
    RAILWAY_TYPE_SET=set(["rail"])
    AEROWAY_TYPE_SET=set(["runway", "taxiway", "apron", "aerodrome"])
    TOURISM_TYPE_SET=set(["camp_site", "caravan_site"])
    
    BARIER_NODES_TYPE_SET=set(["bollard", "block", "chain", "fence"])
    BOUNDARY_TYPE_SET=set(["administrative"])
    PLACE_NODES_TYPE_SET=set(["city", "village", "town", "suburb"])
    REQUIRED_HIGHWAY_TAGS_SET=set(["motorcar", "motor_vehicle", "access", "vehicle", "service", "lanes"])
    
    PARKING_LIMITATIONS_DICT={"access":"yes",
                              "fee":"no"}
    
    AMENITY_POI_TYPE_DICT={"fuel": (POI_TYPE_GAS_STATION, None),
                       "parking": (POI_TYPE_PARKING, PARKING_LIMITATIONS_DICT),
                       "hospital": (POI_TYPE_HOSPITAL, None),
                       "police": (POI_TYPE_POLICE, None),
                       "veterinary":(POI_TYPE_VETERIANERY, None)}
    
    AMENITY_AREA_TYPE_SET=set(["parking"])
    
    TOURISM_POI_TYPE_DICT={"camp_site": POI_TYPE_CAMPING,
                       "caravan_site": POI_TYPE_CAMPING}
    
    SHOP_POI_TYPE_DICT={"supermarket": POI_TYPE_SUPERMARKET}
    
    HIGHWAY_POI_TYPE_DICT={"motorway_junction": POI_TYPE_MOTORWAY_JUNCTION, 
                       "speed_camera": POI_TYPE_ENFORCEMENT}
    
    AEROWAY_POI_TYPE_DICT={"aerodrome": POI_TYPE_AIRPORT}
    
    RAILWAY_POI_TYPE_DICT={"station": POI_TYPE_RAILWAYSTATION}
    
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
                STREET_TYPE_PRIMARY_LINK,
                STREET_TYPE_SECONDARY,
                STREET_TYPE_SECONDARY_LINK,
                STREET_TYPE_TERTIARY,
                STREET_TYPE_TERTIARY_LINK,
                STREET_TYPE_RESIDENTIAL])
    
    ADDRESS_STREET_SET=set([STREET_TYPE_SERVICE,
                STREET_TYPE_UNCLASSIFIED,
                STREET_TYPE_ROAD,
                STREET_TYPE_PRIMARY,
                STREET_TYPE_SECONDARY,
                STREET_TYPE_TERTIARY,
                STREET_TYPE_RESIDENTIAL])
    
    ADMIN_LEVEL_SET=[2, 4, 6, 8]
    
    REF_LABEL_WAY_SET=set([STREET_TYPE_PRIMARY, 
                           STREET_TYPE_TRUNK, 
                           STREET_TYPE_MOTORWAY, 
                           STREET_TYPE_SECONDARY,
                           STREET_TYPE_TERTIARY])

    NAME_LABEL_WAY_SET=set([STREET_TYPE_PRIMARY, 
                           STREET_TYPE_TRUNK, 
                           STREET_TYPE_MOTORWAY, 
                           STREET_TYPE_SECONDARY,
                           STREET_TYPE_TERTIARY,
                           STREET_TYPE_RESIDENTIAL])

            
class OSMDataAccess():
    def __init__(self):
        self.connectionEdge=None
        self.cursorEdge=None
        self.connectionArea=None
        self.cursorArea=None
        self.connectionAdress=None
        self.cursorAdress=None
        self.connectionCoords=None
        self.cursorCoords=None
        self.cursorWay=None
        self.connectionWay=None
        self.cursorNode=None
        self.connectionNode=None
        self.cursorTmp=None
        self.connectionTmp=None
        self.trackItemList=list()
        self.dWrapperTrsp=TrspWrapper(self.getDataDir())
        self.osmutils=OSMUtils()
#        self.initBoarders()
        self.roundaboutExitNumber=None
        self.roundaboutEnterItem=None
        self.currentSearchBBox=None
        
    def setPragmaForDB(self, cursor):
#        cursor.execute('PRAGMA journal_mode=OFF')
#        cursor.execute('PRAGMA synchronous=OFF')
        cursor.execute('PRAGMA cache_size=40000')
        cursor.execute('PRAGMA page_size=4096')
#        cursor.execute('PRAGMA ignore_check_constraint=ON')
        
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

    def openWayDB(self):
        self.connectionWay=sqlite3.connect(self.getWayDBFile())
        self.cursorWay=self.connectionWay.cursor()
        self.connectionWay.enable_load_extension(True)
        self.cursorWay.execute("SELECT load_extension('libspatialite.so')")
        self.setPragmaForDB(self.cursorWay)

    def openNodeDB(self):
        self.connectionNode=sqlite3.connect(self.getNodeDBFile())
        self.cursorNode=self.connectionNode.cursor()
        self.connectionNode.enable_load_extension(True)
        self.cursorNode.execute("SELECT load_extension('libspatialite.so')")
        self.setPragmaForDB(self.cursorNode)
        
    def openAdressDB(self):
        self.connectionAdress=sqlite3.connect(self.getAdressDBFile())
        self.cursorAdress=self.connectionAdress.cursor()
        self.setPragmaForDB(self.cursorAdress)

    def openCoordsDB(self):
        self.connectionCoords=sqlite3.connect(self.getCoordsDBFile())
        self.cursorCoords=self.connectionCoords.cursor()
        self.setPragmaForDB(self.cursorCoords)
        
    def closeEdgeDB(self):
        if self.connectionEdge!=None:
            self.cursorEdge.close()
            self.connectionEdge=None     
            self.cursorEdge=None

    def closeAreaDB(self):
        if self.connectionArea!=None:
            self.cursorArea.close()
            self.connectionArea=None     
            self.cursorArea=None
           
    def closeWayDB(self):
        if self.connectionWay!=None:
            self.cursorWay.close()
            self.connectionWay=None     
            self.cursorWay=None

    def closeNodeDB(self):
        if self.connectionNode!=None:
            self.cursorNode.close()
            self.connectionNode=None     
            self.cursorNode=None

    def closeAdressDB(self):
        if self.connectionAdress!=None:
            self.cursorAdress.close()
            self.connectionAdress=None
            self.cursorAdress=None
                
    def closeCoordsDB(self):
        if self.connectionCoords!=None:
            self.cursorCoords.close()
            self.connectionCoords=None
            self.cursorCoords=None       
                 
    def openAllDB(self):
        self.openWayDB()
        self.openNodeDB()
        self.openEdgeDB()
        self.openAreaDB()
        self.openAdressDB()
        self.openCoordsDB()
        
    def closeAllDB(self):
        self.closeWayDB()
        self.closeNodeDB()
        self.closeEdgeDB()
        self.closeAreaDB()
        self.closeAdressDB()
        self.closeCoordsDB()
    
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
        
    def testAddressTable(self):
        self.cursorAdress.execute('SELECT * FROM addressTable')
        allentries=self.cursorAdress.fetchall()
        for x in allentries:
            addressId, refId, country, cityId, postCode, streetName, houseNumber, lat, lon=self.addressFromDB(x)
            print( "id: "+str(addressId) + " refId:"+str(refId) +" country: "+str(country)+" cityId: " + str(cityId) + " postCode: " + str(postCode) + " streetName: "+str(streetName) + " houseNumber:"+ str(houseNumber) + " lat:"+str(lat) + " lon:"+str(lon))

    def addressFromDB(self, x):
        addressId=x[0]
        refId=x[1]
        country=x[2]
        if x[3]!=None:
            city=int(x[3])
        else:
            city=None
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

    def getPOIRefEntryForId(self, refId, nodeType):
        self.cursorNode.execute('SELECT refId, tags, type, layer, AsText(geom) FROM poiRefTable where refId=%d AND type=%d'%(refId, nodeType))
        allentries=self.cursorNode.fetchall()
        if len(allentries)==1:
            return self.poiRefFromDB(allentries[0])

        return None, None, None, None, None, None
    
    def getAllPOIRefEntrysDict(self, nodeTypeList):
        filterString='('
        for nodeType in nodeTypeList:
            filterString=filterString+str(nodeType)+','
        filterString=filterString[:-1]
        filterString=filterString+')'

        self.cursorNode.execute('SELECT refId, tags, type FROM poiRefTable WHERE type IN %s'%(filterString))
        allentries=self.cursorNode.fetchall()
        resultDict=dict()
        for x in allentries:
            refId=int(x[0])
            if x[1]!=None:
                tags=pickle.loads(x[1])
            nodeType=int(x[2])
            resultDict["%d:%d"%(refId, nodeType)]=tags

        return resultDict
    
    def getTagsForWayEntry(self, wayId):
        self.cursorWay.execute('SELECT tags FROM wayTable where wayId=%d'%(wayId))
        allentries=self.cursorWay.fetchall()
        if len(allentries)==1:
            return self.decodeWayTags(allentries[0][0])
        
        return None

    def getWayEntryForId(self, wayId):
        self.cursorWay.execute('SELECT * FROM wayTable where wayId=%d'%(wayId))
        allentries=self.cursorWay.fetchall()
        if len(allentries)==1:
            return self.wayFromDB(allentries[0])
        
        return (None, None, None, None, None, None, None, None)

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
    
    def getCrossingEntryForRefId(self, wayid, refId):
        self.cursorWay.execute('SELECT * FROM crossingTable where wayId=%d AND refId=%d'%(wayid, refId))  
        resultList=list()
        allentries=self.cursorWay.fetchall()
        for result in allentries:
            crossing=self.crossingFromDB(result)
            resultList.append(crossing)
            
        return resultList
    
#    def testRefTable(self):
#        self.cursorNode.execute('SELECT refId, layer, AsText(geom) FROM refTable')
#        allentries=self.cursorNode.fetchall()
#        for x in allentries:
#            refId, lat, lon, layer=self.refFromDB(x)
#            print("ref: " + str(refId) + "  lat: " + str(lat) + "  lon: " + str(lon) + " layer:"+str(layer))

    def testPOIRefTable(self):
        self.cursorNode.execute('SELECT id, refId, tags, type, layer, country, city, AsText(geom) FROM poiRefTable')
        allentries=self.cursorNode.fetchall()
        for x in allentries:
            poiId, refId, lat, lon, tags, nodeType, layer, country, city=self.poiRefFromDB2(x)
            print("ref: " + str(refId) + "  lat: " + str(lat) + "  lon: " + str(lon) + " tags:"+str(tags) + " nodeType:"+str(nodeType) + " layer:"+str(layer) + " country:"+str(country)+" city:"+str(city))

    def getPOIEntriesWithAddress(self):
        resultList=list()
        self.cursorNode.execute('SELECT id, refId, tags, type, layer, country, city, AsText(geom) FROM poiRefTable')
        allentries=self.cursorNode.fetchall()
        for x in allentries:
            poiId, refId, lat, lon, tags, nodeType, layer, country, city=self.poiRefFromDB2(x)
            streetName, houseNumber=self.getAddressForRefId(refId)
            if streetName!=None:
                resultList.append((poiId, refId, lat, lon, tags, nodeType, layer, country, city, streetName, houseNumber))

        return resultList
    
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
    
    def testWayTable(self):
        self.cursorWay.execute('SELECT * FROM wayTable WHERE wayId=147462600')
        allentries=self.cursorWay.fetchall()
        for x in allentries:
            wayId, tags, refs, streetTypeId, name, nameRef, oneway, roundabout, maxspeed, poiList=self.wayFromDB(x)
            print( "way: " + str(wayId) + " streetType:"+str(streetTypeId)+ " name:" +str(name) + " ref:"+str(nameRef)+" tags: " + str(tags) + "  refs: " + str(refs) + " oneway:"+str(oneway)+ " roundabout:"+str(roundabout) + " maxspeed:"+str(maxspeed)+" poilist:"+str(poiList))

    def testCrossingTable(self):
        self.cursorWay.execute('SELECT * FROM crossingTable')
        allentries=self.cursorWay.fetchall()
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
        self.cursorArea.execute('SELECT osmId, type, tags, layer, AsText(geom) FROM areaTable')
        allentries=self.cursorArea.fetchall()
        for x in allentries:
            osmId, areaType, tags, layer, polyStr=self.areaFromDBWithCoordsString(x)
            print("osmId: "+str(osmId)+ " type: "+str(areaType) +" tags: "+str(tags)+ " layer: "+ str(layer)+" polyStr:"+str(polyStr))

        self.cursorArea.execute('SELECT osmId, type, tags, layer, AsText(geom) FROM areaLineTable')
        allentries=self.cursorArea.fetchall()
        for x in allentries:
            osmId, areaType, tags, layer, polyStr=self.areaFromDBWithCoordsString(x)
            print("osmId: "+str(osmId)+ " type: "+str(areaType) +" tags: "+str(tags)+ " layer: "+ str(layer)+" polyStr:"+str(polyStr))

    def testAdminAreaTable(self):
        self.cursorArea.execute('SELECT osmId, tags, adminLevel, parent, AsText(geom) FROM adminAreaTable WHERE adminLevel=4')
        allentries=self.cursorArea.fetchall()
        for x in allentries:
            osmId, tags, adminLevel, parent=self.adminAreaFromDBWithParent(x)
            print("%d %s"%(osmId, tags["name"]))
#            print("osmId: "+str(osmId)+ " tags: "+str(tags)+ " adminLevel: "+ str(adminLevel) + " parent:"+str(parent))

    def testCoordsTable(self):
#        self.cursorCoords.execute('SELECT * from coordsTable WHERE refId=98110819')
#        allentries=self.cursorCoords.fetchall()  

        self.cursorCoords.execute('SELECT * from wayRefTable WHERE wayId=31664992')
        allentries=self.cursorCoords.fetchall()  
        
        print(allentries)

    def wayFromDB(self, x):
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
        layer=int(x[8])
        coordsStr=x[9]            
        return (wayId, tags, refs, streetInfo, name, nameRef, maxspeed, poiList, layer, coordsStr)   

    def refFromDB(self, x):
        refId=x[0]
        layer=int(x[1])
        pointStr=x[2]

        pointStr=pointStr[6:-1]
        coordsPairs=pointStr.split(" ")
        lon=float(coordsPairs[0].lstrip().rstrip())
        lat=float(coordsPairs[1].lstrip().rstrip())

        return (refId, lat, lon, layer)
    
    def poiRefFromDB(self, x):
        refId=int(x[0])
        
        tags=None
        if x[1]!=None:
            tags=pickle.loads(x[1])
        
        nodeType=int(x[2])            
        layer=int(x[3])
        pointStr=x[4]

        pointStr=pointStr[6:-1]
        coordsPairs=pointStr.split(" ")
        lon=float(coordsPairs[0].lstrip().rstrip())
        lat=float(coordsPairs[1].lstrip().rstrip())

        return (refId, lat, lon, tags, nodeType, layer)

    def poiRefFromDB2(self, x):
        poiId=int(x[0])
        refId=int(x[1])
        
        tags=None
        if x[2]!=None:
            tags=pickle.loads(x[2])
        
        nodeType=int(x[3])            
        layer=int(x[4])
        if x[5]!=None:
            country=int(x[5])
        else:
            country=None
        
        if x[6]!=None:
            city=int(x[6])
        else:
            city=None
            
        pointStr=x[7]

        pointStr=pointStr[6:-1]
        coordsPairs=pointStr.split(" ")
        lon=float(coordsPairs[0].lstrip().rstrip())
        lat=float(coordsPairs[1].lstrip().rstrip())

        return (poiId, refId, lat, lon, tags, nodeType, layer, country, city)    
    
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
        layer=int(x[3])
        polyStr=x[4]
        return (osmId, areaType, tags, layer, polyStr)

    def adminAreaFromDBWithCoordsString(self, x):
        osmId=x[0]
        tags=pickle.loads(x[1])
        adminLevel=int(x[2])  
        polyStr=x[3]
        return (osmId, tags, adminLevel, polyStr)
    
    def adminAreaFromDBWithParent(self, x):
        osmId=x[0]
        tags=pickle.loads(x[1])
        if x[2]!=None:
            adminLevel=int(x[2])  
        else:
            adminLevel=None
        if x[3]!=None:
            parent=int(x[3])
        else:
            parent=None
        return (osmId, tags, adminLevel, parent)
     
    def areaFromDB(self, x):
        osmId=x[0]
        areaType=x[1]
        tags=pickle.loads(x[2])  
        return (osmId, areaType, tags)
    
    def decodeStreetInfo(self, streetInfo):
        oneway=(streetInfo&63)>>4
        roundabout=(streetInfo&127)>>6
        streetTypeId=(streetInfo&15)
        return streetTypeId, oneway, roundabout
    
    def decodeStreetInfo2(self, streetInfo):
        oneway=(streetInfo&63)>>4
        roundabout=(streetInfo&127)>>6
        tunnel=(streetInfo&255)>>7
        bridge=(streetInfo&511)>>8
        streetTypeId=(streetInfo&15)
        return streetTypeId, oneway, roundabout, tunnel, bridge
    
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
        
    def decodeWayTags(self, plainTags):
        if plainTags==None:
            return dict()
#        plainTags=zlib.decompress(compressedTags)
        tags=pickle.loads(plainTags)
        return tags
    
    def getAdressCityList(self, countryId):
        self.cursorAdress.execute('SELECT DISTINCT city, postCode FROM addressTable WHERE country=%d'%(countryId))
        allentries=self.cursorAdress.fetchall()
        cityList=list()
        for x in allentries:
            if x[0]!=None:
                cityList.append((int(x[0]), x[1]))
        return cityList

    def getAdressListForCity(self, countryId, cityId):
        streetList=list()
        self.cursorAdress.execute('SELECT * FROM addressTable WHERE country=%d AND city=%d'%(countryId, cityId))
        allentries=self.cursorAdress.fetchall()
        for x in allentries:
            streetList.append(self.addressFromDB(x))

        return streetList

    def getAdressListForCityRecursive(self, countryId, osmId):
        streetList=list()
        cityList=list()
        self.getAdminChildsForIdRecursive(osmId, cityList)
        
        # add self
        cityList.append((osmId, None, None))
        filterString='('
        for cityId, cityName, adminLevel in cityList:
            filterString=filterString+str(cityId)+','
        filterString=filterString[:-1]
        filterString=filterString+')'
        
        self.cursorAdress.execute('SELECT * FROM addressTable WHERE country=%d AND city IN %s'%(countryId, filterString))
        allentries=self.cursorAdress.fetchall()
        for x in allentries:
            streetList.append(self.addressFromDB(x))

        return streetList         
                   
    def getAdressListForCountry(self, countryId):
        self.cursorAdress.execute('SELECT * FROM addressTable WHERE country=%d'%(countryId))
        allentries=self.cursorAdress.fetchall()
        streetList=list()
        for x in allentries:
            streetList.append(self.addressFromDB(x))

        return streetList
    
    def getAdressListForStreetAndNumber(self, streetName, houseNumber):
        streetList=list()
        
        self.cursorAdress.execute('SELECT * FROM addressTable WHERE streetName="%s" AND houseNumber="%s"'%(streetName, houseNumber))
        allentries=self.cursorAdress.fetchall()
        for x in allentries:
            streetList.append(self.addressFromDB(x))
            
        return streetList
        
    def getAddressForRefId(self, refId):
        self.cursorAdress.execute('SELECT streetName, houseNumber FROM addressTable WHERE refId=%d'%(refId))
        allentries=self.cursorAdress.fetchall()
        if len(allentries)==1:
            x=allentries[0]
            return x[0], x[1]
        return None, None
    
    # bbox for spatial DB (left, bottom, right, top)
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
        storedRefId, lat1, lon1=self.getCoordsEntry(ref1)
        if storedRefId==None:
            return False
        storedRefId, lat2, lon2=self.getCoordsEntry(ref2)
        if storedRefId==None:
            return False
        
        return self.isOnLineBetweenPoints(lat, lon, lat1, lon1, lat2, lon2, maxDistance)
    
    def isMinimalDistanceOnLineBetweenPoints(self, lat, lon, lat1, lon1, lat2, lon2, maxDistance, addStart=True, addEnd=True):        
        nodes=self.osmutils.createTemporaryPoints(lat1, lon1, lat2, lon2, addStart=addStart, addEnd=addEnd)
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
        wayId, _, _, _, _, _, _, storedPoiList=self.getWayEntryForId(wayId)
        if wayId!=None:
            if storedPoiList!=None:
                for _, nodeType in storedPoiList:
                    if nodeType==Constants.POI_TYPE_ENFORCEMENT_WAYREF:
                        poiList.append(Constants.POI_TYPE_ENFORCEMENT)
                    if nodeType==Constants.POI_TYPE_BARRIER:
                        poiList.append(nodeType)

        if len(poiList)!=0:
            return poiList
        
        return None
    
    def printEdgeForRefList(self, edge, trackWayList, startPoint, endPoint, currentStartRef):
        (edgeId, startRef, endRef, length, wayId, _, _, _, _, _, coords)=edge        
            
        latTo=None
        lonTo=None
        latFrom=None
        lonFrom=None
        
        wayId, _, refs, streetInfo, name, nameRef, _, _=self.getWayEntryForId(wayId)
        streetTypeId, oneway, roundabout=self.decodeStreetInfo(streetInfo)

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
                                    
                                    _, _, _, streetInfo, _, _, _, _=self.getWayEntryForId(edgeWayId)   
                                    streetTypeId, oneway, roundabout=self.decodeStreetInfo(streetInfo)
    
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
        
        wayId, _, refs, streetInfo, name, nameRef, _, _=self.getWayEntryForId(wayId)
        streetTypeId, _, _=self.decodeStreetInfo(streetInfo)

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
    
    def isAccessRestricted(self, tags):
        if "vehicle" in tags:
            if tags["vehicle"]!="yes":
                return True

        if "motorcar" in tags:
            if tags["motorcar"]!="yes":
                return True
                
        if "motor_vehicle" in tags:
            if tags["motor_vehicle"]!="yes":
                return True
            
        if "access" in tags:
            if tags["access"]!="yes":
                return True

        return False
        
    def createLineStringFromCoords(self, coords):
        lineString="'LINESTRING("
        coordString=''.join(["%f %f"%(lon, lat)+"," for lat, lon in coords])    
        coordString=coordString[:-1]
        lineString=lineString+coordString+")'"
        return lineString
    
    def createCoordsFromLineString(self, lineString):
        coords=list()
        coordsStr=lineString[11:-1] # LINESTRING
        x=re.findall(r'[0-9\.]+|[^0-9\.]+', coordsStr)
        i=0
        while i<len(x)-2:
            coords.append((float(x[i+2]), float(x[i])))
            i=i+4
            
        return coords

    def createCoordsFromPolygon(self, polyString):
        coords=list()
        coordsStr=polyString[9:-2] # POLYGON
        x=re.findall(r'[0-9\.]+|[^0-9\.]+', coordsStr)
        i=0
        while i<len(x)-2:
            coords.append((float(x[i+2]), float(x[i])))
            i=i+4
            
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

            allCoordsList.append(coords)
        else:
            for poly in polyParts:
                coords=list()
                x=re.findall(r'[0-9\.]+|[^0-9\.]+', poly)
                i=0
                while i<len(x)-2:
                    coords.append((float(x[i+2]), float(x[i])))
                    i=i+4
                
                allCoordsList.append(coords)
        
        return allCoordsList

    def createPolygonFromCoords(self, coords):
        polyString="'POLYGON(("
        coordString=''.join(["%f %f"%(lon, lat)+"," for lat, lon in coords])    
        coordString=coordString[:-1]
        polyString=polyString+coordString+"))'"        
        return polyString
            
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
            
    # TODO: should be relativ to this dir by default
    def getDataDir(self):
        return os.path.join(env.getDataRoot(), "data4")

    def getEdgeDBFile(self):
        file="edge.db"
        return os.path.join(self.getDataDir(), file)

    def getAreaDBFile(self):
        file="area.db"
        return os.path.join(self.getDataDir(), file)
    
    def getAdressDBFile(self):
        file="adress.db"
        return os.path.join(self.getDataDir(), file)
    
    def getCoordsDBFile(self):
        file="coords.db"
        return os.path.join(self.getDataDir(), file)

    def getWayDBFile(self):
        file="ways.db"
        return os.path.join(self.getDataDir(), file)

    def getNodeDBFile(self):
        file="nodes.db"
        return os.path.join(self.getDataDir(), file)
                        
    def coordsDBExists(self):
        return os.path.exists(self.getCoordsDBFile())

    def edgeDBExists(self):
        return os.path.exists(self.getEdgeDBFile())

    def areaDBExists(self):
        return os.path.exists(self.getAreaDBFile())

    def wayDBExists(self):
        return os.path.exists(self.getWayDBFile())

    def nodeDBExists(self):
        return os.path.exists(self.getNodeDBFile())
                
    def adressDBExists(self):
        return os.path.exists(self.getAdressDBFile())

    def tmpDBExists(self):
        return os.path.exists(self.getTmpDBFile())

#    def initBoarders(self):
#        self.bu=OSMBoarderUtils(env.getPolyDataRoot())
#        self.bu.initData()
#        self.buSimple=OSMBoarderUtils(env.getPolyDataRootSimple())
#        self.buSimple.initData()
            
#    def countryNameOfPoint(self, lat, lon):
#        country=self.bu.countryNameOfPoint(lat, lon)
#        if country==None:
#            # HACK if the point is exactly on the border:(
#            country=self.bu.countryNameOfPoint(lat+0.0001, lon+0.0001)
#        return country
    
    def getOSMDataInfo(self):
        osmDataList=dict()
        osmData=dict()
#        osmData["osmFile"]='/home/maxl/Downloads/geofabrik/austria.osm.bz2'
        osmData["osmFile"]='/home/maxl/Downloads/cloudmade/salzburg-2.osm.bz2'
        osmData["poly"]="austria.poly"
        osmData["polyCountry"]="Europe / Western Europe / Austria"
        osmDataList[0]=osmData
        
#        osmData=dict()
#        osmData["osmFile"]='/home/maxl/Downloads/geofabrik/switzerland.osm.bz2'
##        osmData["osmFile"]=None
#        osmData["poly"]="switzerland.poly"
#        osmData["polyCountry"]="Europe / Western Europe / Switzerland"
#        osmDataList[1]=osmData
    
        osmData=dict()
#        osmData["osmFile"]='/home/maxl/Downloads/geofabrik/bayern.osm.bz2'
#        osmData["osmFile"]='/home/maxl/Downloads/geofabrik/germany-1.osm.bz2'
        osmData["osmFile"]='/home/maxl/Downloads/cloudmade/bayern-2.osm.bz2'
#        osmData["osmFile"]=None
        osmData["poly"]="germany.poly"
        osmData["polyCountry"]="Europe / Western Europe / Germany"
        osmDataList[2]=osmData
        
#        osmData=dict()
#        osmData["osmFile"]='/home/maxl/Downloads/geofabrik/liechtenstein.osm.bz2'
##        osmData["osmFile"]=None
#        osmData["poly"]="liechtenstein.poly"
#        osmData["polyCountry"]="Europe / Western Europe / Liechtenstein"
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
            
    def printCrossingsForWayId(self, wayId):
        self.cursorWay.execute('SELECT * from crossingTable WHERE wayId=%d'%(wayId))
        allentries=self.cursorWay.fetchall()
        for x in allentries:
            print(self.crossingFromDB(x))
         
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
 
    def getAdminChildsForId(self, osmId):
        childList=list()
        
        self.cursorArea.execute('SELECT osmId, tags, adminLevel FROM adminAreaTable WHERE parent=%d'%(osmId))
        allentries=self.cursorArea.fetchall()
        for x in allentries:
            childId=int(x[0])
            adminLevel=int(x[2])
            if x[1]!=None:
                tags=pickle.loads(x[1])
                if "name" in tags:
                    childList.append((childId, tags["name"], adminLevel))
                    
        return childList

    def getAdminChildsForIdRecursive(self, osmId, childList):        
        self.cursorArea.execute('SELECT osmId, tags, adminLevel FROM adminAreaTable WHERE parent=%d'%(osmId))
        allentries=self.cursorArea.fetchall()
        for x in allentries:
            childId=int(x[0])
            adminLevel=int(x[2])
            if x[1]!=None:
                tags=pickle.loads(x[1])
                if "name" in tags:
                    childList.append((childId, tags["name"], adminLevel))
                    self.getAdminChildsForIdRecursive(childId, childList)
                    
    
    def getAdminCountryList(self):
        adminLevelList=[2]
        countryDict=dict()
        adminList=self.getAllAdminAreas(adminLevelList, False)
            
        for area in adminList:
            osmId=area[0]
            tags=area[1]
            if "name" in tags:
                countryDict[osmId]=tags["name"]
                
        return countryDict      
                                          
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
        
    def getPOINodesInBBoxWithGeom(self, bbox, margin, nodeTypeList):
        lonRangeMin, latRangeMin, lonRangeMax, latRangeMax=self.createBBoxWithMargin(bbox, margin)      

        if len(nodeTypeList)==0:
            self.cursorNode.execute('SELECT refId, tags, type, layer, AsText(geom) FROM poiRefTable WHERE ROWID IN (SELECT rowid FROM idx_poiRefTable_geom WHERE rowid MATCH RTreeIntersects(%f, %f, %f, %f))'%(lonRangeMin, latRangeMin, lonRangeMax, latRangeMax))
        else:
            filterString='('
            for nodeType in nodeTypeList:
                filterString=filterString+str(nodeType)+','
            filterString=filterString[:-1]
            filterString=filterString+')'
            
            self.cursorNode.execute('SELECT refId, tags, type, layer, AsText(geom) FROM poiRefTable WHERE ROWID IN (SELECT rowid FROM idx_poiRefTable_geom WHERE rowid MATCH RTreeIntersects(%f, %f, %f, %f)) AND type IN %s'%(lonRangeMin, latRangeMin, lonRangeMax, latRangeMax, filterString))
            
        allentries=self.cursorNode.fetchall()
        resultList=list()
        for x in allentries:
            refId, lat, lon, tags, nodeType, _=self.poiRefFromDB(x)
            resultList.append((refId, lat, lon, tags, nodeType))
            
        return resultList
        
    def getPOIsOfNodeTypeInDistance(self, lat, lon, distancekm, nodeType):
        distanceDegree=distancekm/100
        
        self.cursorNode.execute('SELECT refId, tags, type, layer, AsText(geom), GeodesicLength(MakeLine(geom, MakePoint(%f, %f, 4236))) FROM poiRefTable WHERE ROWID IN (SELECT rowid FROM idx_poiRefTable_geom WHERE rowid MATCH RTreeDistWithin(%f, %f, %f)) AND type=%d'%(lon, lat, lon, lat, distanceDegree, nodeType))
            
        allentries=self.cursorNode.fetchall()
        resultList=list()

        for x in allentries:
            distance=int(x[5])
            refId, nodeLat, nodeLon, tags, nodeType, layer=self.poiRefFromDB(x) 
            resultList.append((refId, nodeLat, nodeLon, tags, nodeType, distance))
            
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
        
        # streetTypeId an layer sorting
        if streetTypeList==None or len(streetTypeList)==0:    
            self.cursorWay.execute('SELECT wayId, tags, refs, streetInfo, name, ref, maxspeed, poiList, layer, AsText(geom) FROM wayTable WHERE ROWID IN (SELECT rowid FROM idx_wayTable_geom WHERE rowid MATCH RTreeIntersects(%f, %f, %f, %f)) ORDER BY streetTypeId, layer'%(lonRangeMin, latRangeMin, lonRangeMax, latRangeMax))
        else:
            filterString='('
            for streetType in streetTypeList:
                filterString=filterString+str(streetType)+','
            filterString=filterString[:-1]
            filterString=filterString+')'
            
            self.cursorWay.execute('SELECT wayId, tags, refs, streetInfo, name, ref, maxspeed, poiList, layer, AsText(geom) FROM wayTable WHERE ROWID IN (SELECT rowid FROM idx_wayTable_geom WHERE rowid MATCH RTreeIntersects(%f, %f, %f, %f)) AND streetTypeId IN %s ORDER BY streetTypeId, layer'%(lonRangeMin, latRangeMin, lonRangeMax, latRangeMax, filterString))
            
        wayIdSet=set()
        allentries=self.cursorWay.fetchall()
        resultList=list()
        for x in allentries:
            way=self.wayFromDBWithCoordsString(x)
            resultList.append(way)
            wayIdSet.add(way[0])
            
        return resultList, wayIdSet

    def getAreaTagsWithId(self, osmId):
        self.cursorArea.execute('SELECT tags FROM areaTable WHERE osmId=%d'%(osmId))
        allentries=self.cursorArea.fetchall()
        if len(allentries)==1:
            if allentries[0][0]!=None:
                tags=pickle.loads(allentries[0][0])
                return tags

        self.cursorArea.execute('SELECT tags FROM areaLineTable WHERE osmId=%d'%(osmId))
        allentries=self.cursorArea.fetchall()
        if len(allentries)==1:
            if allentries[0][0]!=None:
                tags=pickle.loads(allentries[0][0])
                return tags
            
        return None
    
    def getAreasInBboxWithGeom(self, areaTypeList, bbox, margin):
        lonRangeMin, latRangeMin, lonRangeMax, latRangeMax=self.createBBoxWithMargin(bbox, margin)      
        
        resultList=list()
        areaIdSet=set()
        filterString=None
        
        if areaTypeList!=None and len(areaTypeList)!=0:
            filterString='('
            for areaType in areaTypeList:
                filterString=filterString+str(areaType)+','
            filterString=filterString[:-1]
            filterString=filterString+')'
            
        # TODO: no layer sorting
        if filterString==None:
            self.cursorArea.execute('SELECT osmId, type, tags, layer, AsText(geom) FROM areaTable WHERE ROWID IN (SELECT rowid FROM idx_areaTable_geom WHERE rowid MATCH RTreeIntersects(%f, %f, %f, %f))'%(lonRangeMin, latRangeMin, lonRangeMax, latRangeMax))
        else:
            self.cursorArea.execute('SELECT osmId, type, tags, layer, AsText(geom) FROM areaTable WHERE ROWID IN (SELECT rowid FROM idx_areaTable_geom WHERE rowid MATCH RTreeIntersects(%f, %f, %f, %f)) AND type IN %s'%(lonRangeMin, latRangeMin, lonRangeMax, latRangeMax, filterString))
        
        allentries=self.cursorArea.fetchall()
        
        for x in allentries:
            (osmId, areaType, tags, layer, polyStr)=self.areaFromDBWithCoordsString(x)
            resultList.append((osmId, areaType, tags, layer, polyStr, 0))
            areaIdSet.add(int(x[0]))
                
        # use layer sorting
        if filterString==None:
            self.cursorArea.execute('SELECT osmId, type, tags, layer, AsText(geom) FROM areaLineTable WHERE ROWID IN (SELECT rowid FROM idx_areaLineTable_geom WHERE rowid MATCH RTreeIntersects(%f, %f, %f, %f)) ORDER BY layer'%(lonRangeMin, latRangeMin, lonRangeMax, latRangeMax))
        else:
            self.cursorArea.execute('SELECT osmId, type, tags, layer, AsText(geom) FROM areaLineTable WHERE ROWID IN (SELECT rowid FROM idx_areaLineTable_geom WHERE rowid MATCH RTreeIntersects(%f, %f, %f, %f)) AND type IN %s ORDER BY layer'%(lonRangeMin, latRangeMin, lonRangeMax, latRangeMax, filterString))
        
        allentries=self.cursorArea.fetchall()

        for x in allentries:
            (osmId, areaType, tags, layer, polyStr)=self.areaFromDBWithCoordsString(x)
            resultList.append((osmId, areaType, tags, layer, polyStr, 1))
            areaIdSet.add(int(x[0]))

        return resultList, areaIdSet    
    
    def getAdminAreasInBboxWithGeom(self, bbox, margin, adminLevelList):
        lonRangeMin, latRangeMin, lonRangeMax, latRangeMax=self.createBBoxWithMargin(bbox, margin)      
        
        filterString='('
        for adminLevel in adminLevelList:
            filterString=filterString+str(adminLevel)+','
        filterString=filterString[:-1]
        filterString=filterString+')'
        
        self.cursorArea.execute('SELECT osmId, tags, adminLevel, AsText(geom) FROM adminAreaTable WHERE ROWID IN (SELECT rowid FROM idx_adminAreaTable_geom WHERE rowid MATCH RTreeIntersects(%f, %f, %f, %f)) AND adminLevel IN %s AND Intersects(geom, BuildMBR(%f, %f, %f, %f, 4236)) ORDER BY adminLevel'%(lonRangeMin, latRangeMin, lonRangeMax, latRangeMax, filterString, lonRangeMin, latRangeMin, lonRangeMax, latRangeMax))
             
        allentries=self.cursorArea.fetchall()
        resultList=list()
        areaIdSet=set()
        for x in allentries:
            resultList.append(self.adminAreaFromDBWithCoordsString(x))
            areaIdSet.add(x[0])
            
        return resultList, areaIdSet                 

    def getAdminAreasOnPointWithGeom(self, lat, lon, margin, adminLevelList, sortByAdminLevel):
        lonRangeMin, latRangeMin, lonRangeMax, latRangeMax=self.createBBoxAroundPoint(lat, lon, margin)      

        filterString='('
        for adminLevel in adminLevelList:
            filterString=filterString+str(adminLevel)+','
        filterString=filterString[:-1]
        filterString=filterString+')'

        if sortByAdminLevel==True:
            sql='SELECT osmId, tags, adminLevel, AsText(geom) FROM adminAreaTable WHERE ROWID IN (SELECT rowid FROM idx_adminAreaTable_geom WHERE rowid MATCH RTreeIntersects(%f, %f, %f, %f)) AND adminLevel IN %s AND Contains(geom, MakePoint(%f, %f, 4236)) ORDER BY adminLevel'%(lonRangeMin, latRangeMin, lonRangeMax, latRangeMax, filterString, lon, lat)
        else:
            sql='SELECT osmId, tags, adminLevel, AsText(geom) FROM adminAreaTable WHERE ROWID IN (SELECT rowid FROM idx_adminAreaTable_geom WHERE rowid MATCH RTreeIntersects(%f, %f, %f, %f)) AND adminLevel IN %s AND Contains(geom, MakePoint(%f, %f, 4236))'%(lonRangeMin, latRangeMin, lonRangeMax, latRangeMax, filterString, lon, lat)

        self.cursorArea.execute(sql)
             
        allentries=self.cursorArea.fetchall()
        resultList=list()
        for x in allentries:
            resultList.append(self.adminAreaFromDBWithCoordsString(x))
            
        return resultList          

    def getAllAdminAreas(self, adminLevelList, sortByAdminLevel):

        filterString='('
        for adminLevel in adminLevelList:
            filterString=filterString+str(adminLevel)+','
        filterString=filterString[:-1]
        filterString=filterString+')'

        if sortByAdminLevel==True:
            sql='SELECT osmId, tags, adminLevel, AsText(geom) FROM adminAreaTable WHERE adminLevel IN %s ORDER BY adminLevel'%(filterString)
        else:
            sql='SELECT osmId, tags, adminLevel, AsText(geom) FROM adminAreaTable WHERE adminLevel IN %s'%(filterString)

        self.cursorArea.execute(sql)
             
        allentries=self.cursorArea.fetchall()
        resultList=list()
        for x in allentries:
            resultList.append(self.adminAreaFromDBWithCoordsString(x))
            
        return resultList          
    
    def getAdminAreaConversion(self):
        areaNameDict=dict()
        reverseAdminAreaDict=dict()
        
        sql='SELECT osmId, tags FROM adminAreaTable'
        self.cursorArea.execute(sql)
             
        allentries=self.cursorArea.fetchall()
        for x in allentries:
            osmId=x[0]
            if x[1]==None:
                continue
            tags=pickle.loads(x[1])
            if "name" in tags:
                adminName=tags["name"]
                areaNameDict[osmId]=adminName
                reverseAdminAreaDict[adminName]=osmId
            
        return areaNameDict,reverseAdminAreaDict
      
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
  
def main(argv):    
    p = OSMDataAccess()
    
    p.openAllDB()
#    p.cursorArea.execute("SELECT * FROM sqlite_master WHERE type='table'")
#    allentries=p.cursorArea.fetchall()
#    for x in allentries:
#        print(x)


#    p.cursorEdge.execute('PRAGMA table_info(cache_edgeTable_Geometry)')
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
    
#    p.testAreaTable()
#    p.testRoutes()
#    p.testWayTable()

#    p.testAddressTable()
#    p.testCoordsTable()
#    p.testPOIRefTable()
    
#    p.testAdminAreaTable()
#    print(p.getAdminAreaConversion())
#    p.getPOIEntriesWithAddress()

#    print(p.bu.getPolyCountryList())
    p.closeAllDB()


if __name__ == "__main__":
#    cProfile.run('main(sys.argv)')
    main(sys.argv)  
    

