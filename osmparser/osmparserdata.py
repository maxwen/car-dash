'''
Created on Dec 13, 2011

@author: maxl
'''
from osmparser.parser.simple import OSMParser
import sys
import os
import sqlite3
from osmparser.osmutils import OSMUtils
import pickle
import time
#from osmparser.dijkstrapygraph import DijkstraWrapperPygraph
from osmparser.dijkstraigraph import DijkstraWrapperIgraph

#from config import Config
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
            self.edgeList, self.pathCost=osmParserData.calcRouteForPoints(self.routingPointList)
    
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
    def __init__(self, name="", pointType=0, lat=0.0, lon=0.0):
        self.lat=lat
        self.lon=lon
        self.target=0
        self.source=0
        # 0 start
        # 1 end
        # 2 way
        # 3 gps
        # 4 favorite
        self.type=pointType
        self.wayId=None
        self.edgeId=None
        self.name=name
        self.usedRefId=0
    
    def resolveFromPos(self, osmParserData):
        wayId, usedRefId, usedPos, country=osmParserData.getWayIdForPos(self.lat, self.lon)
        if wayId==None:
            print("resolveFromPos not found for %f %f"%(self.lat, self.lon))

        resultList=osmParserData.getEdgeEntryForWayId(wayId)
        
        self.lat=usedPos[0]
        self.lon=usedPos[1]
            
        targetFound=False
        for result in resultList:
            if targetFound:
                break
            
            (edgeId, _, _, _, wayId, source1, target1, refList, cost, reverseCost)=result

            for edgeRef in refList:
                if edgeRef==usedRefId:
                    _, country=osmParserData.getCountryOfRef(edgeRef)
                    if country==None:
                        continue
                    (lat, lon)=osmParserData.getCoordsWithRefAndCountry(edgeRef, country)
                    if lat==None:
                        continue
                    self.lat=lat
                    self.lon=lon
                    self.edgeId=edgeId
                    self.target=target1
                    self.source=source1
                    self.usedRefId=edgeRef
                    self.wayId=wayId
                    targetFound=True
                    break
    
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
    
    def getLat(self):
        return self.lat
    
    def getLon(self):
        return self.lon
    
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
        self.refIdDB=0
        self.nodes = dict()
        self.relations = dict()
        
    def initCountryData(self):
        self.crossingId=0
        self.nodes = dict()
#        self.coords = dict()
        self.relations = dict()
#        self.streetNameIndex=dict()
#        self.streetIndex=dict()
#        self.wayRefIndex=dict()
#        self.ways=dict()

    def createCountryTables(self):
        self.createRefTable()
        self.createWayTable()
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
        self.cursor=self.connection.cursor()
        self.osmList[country]["cursor"]=self.cursor
        self.osmList[country]["connection"]=self.connection

    def createCoordsTable(self):
        self.cursorCoords.execute('CREATE TABLE coordsTable (refId INTEGER PRIMARY KEY, lat REAL, lon REAL)')

    def addToCoordsTable(self, ref, lat, lon):
        self.cursorCoords.execute('INSERT INTO coordsTable VALUES( ?, ?, ?)', (ref, lat, lon))
    
    def getCoordsEntry(self, ref):
        self.cursorCoords.execute('SELECT * FROM coordsTable WHERE refId==%d'%(ref))
        allentries=self.cursorCoords.fetchall()
        if len(allentries)==1:
            return(allentries[0][0], allentries[0][1], allentries[0][2])
#        print("no coords entry for %d"%(ref))
        return None, None, None
    
    def createRefTable(self):
        self.cursor.execute('CREATE TABLE refTable (refGid INTEGER PRIMARY KEY, refId INTEGER, lat REAL, lon REAL, wayId INTEGER)')
        self.cursor.execute("CREATE INDEX refTableRefId_idx ON refTable (refId)")
        self.cursor.execute("CREATE INDEX refTableLat_idx ON refTable (lat)")
        self.cursor.execute("CREATE INDEX refTableLon_idx ON refTable (lon)")
        
    def createWayTable(self):
        self.cursor.execute('CREATE TABLE wayTable (wayId INTEGER PRIMARY KEY, tags BLOB, refs BLOB, refsDistance BLOB)')

    def createAddressTable(self):
        self.cursorAdress.execute('CREATE TABLE addressTable (id INTEGER PRIMARY KEY, refId INTEGER, country INTEGER, city TEXT, postCode INTEGER, streetName TEXT, houseNumber TEXT, lat REAL, lon REAL)')
        
    def addToAddressTable(self, refId, country, city, postCode, streetName, houseNumber, lat, lon):
        self.cursorAdress.execute('INSERT INTO addressTable VALUES( ?, ?, ?, ?, ?, ?, ?, ?, ?)', (self.addressId, refId, country, city, postCode, streetName, houseNumber, lat, lon))
        self.addressId=self.addressId+1

    def getAddressTableEntryWithRefId(self, refId):
        self.cursorAdress.execute('SELECT * FROM addressTable where refId==%d'%(refId))
        allentries=self.cursorAdress.fetchall()
        if len(allentries)==1:
            return self.addressFromDB(allentries[0])
        return None, None, None, None, None, None, None, None, None
    
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
    
    # TODO create index after inserting
    def createCrossingsTable(self):
        self.cursor.execute('CREATE TABLE crossingTable (id INTEGER PRIMARY KEY, wayId INTEGER, refId INTEGER, nextWayIdList BLOB)')
        self.cursor.execute("CREATE INDEX wayId_idx ON crossingTable (wayId)")
        self.cursor.execute("CREATE INDEX refId_idx ON crossingTable (refId)")

    # TODO create index after inserting
    def createEdgeTable(self):
        self.cursorEdge.execute('CREATE TABLE edgeTable (id INTEGER PRIMARY KEY, startRef INTEGER, endRef INTEGER, length INTEGER, wayId INTEGER, source INTEGER, target INTEGER, refList BLOB, cost REAL, reverseCost REAL)')
        self.createEdgeTableIndexes()
        
    def createEdgeTableIndexes(self):
        self.cursorEdge.execute("CREATE INDEX startRef_idx ON edgeTable (startRef)")
        self.cursorEdge.execute("CREATE INDEX endRef_idx ON edgeTable (endRef)")
        self.cursorEdge.execute("CREATE INDEX source_idx ON edgeTable (source)")
        self.cursorEdge.execute("CREATE INDEX target_idx ON edgeTable (target)")
        self.cursorEdge.execute("CREATE INDEX wayId_idx ON edgeTable (wayId)")

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
    
    def addToCountryRefTable(self, refId, lat, lon):
        storedRefId, _=self.getCountryOfRef(refId)
        if storedRefId!=None:
            return
        polyCountry=self.countryNameOfPoint(lat, lon)
        refCountry=self.getCountryForPolyCountry(polyCountry)
            
        if refCountry!=None:
            self.cursorCountry.execute('INSERT INTO refCountryTable VALUES( ?, ?)', (refId, refCountry))
#        else:
#            # HACK!!!
#            polyCountry=self.countryNameOfPoint(lat+0.0001, lon+0.0001)
#            refCountry=self.getCountryForPolyCountry(polyCountry)
#            if refCountry!=None:
#                print("DB INSERT ref %d after changing lat and lon"%(refId))
#                self.cursorCountry.execute('INSERT INTO refCountryTable VALUES( ?, ?)', (refId, refCountry))
                    
    def getCountryOfRef(self, refId):
        self.cursorCountry.execute('SELECT id, country FROM refCountryTable where id==%d'%(refId))
        allentries=self.cursorCountry.fetchall()
        if len(allentries)>1:
            print("more then one match in refCountryTable for refId %d"%(refId))
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
        self.cursorCountry.execute('SELECT id, wayId, country FROM wayCountryTable where wayId==%d'%(wayId))
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

    def addToRefTable(self, refid, lat, lon, wayId, country):
        self.setDBCursorForCountry(country)
        resultList=self.getRefEntryForIdAndCountryAndWayId(refid, country, wayId)
        if len(resultList)!=0:
    #            print("ref %d and way %d already in refTable"%(refid, wayId))
            return
        self.cursor.execute('INSERT INTO refTable VALUES( ?, ?, ?, ?, ?)', (self.refIdDB, refid, lat, lon, wayId))
        self.refIdDB=self.refIdDB+1
        
    def addToWayTable(self, wayid, tags, refs, distances, country):
        self.setDBCursorForCountry(country)
        storedWayId, _, _,_=self.getWayEntryForIdAndCountry(wayid, country)
        if storedWayId!=None:
            return
        self.cursor.execute('INSERT INTO wayTable VALUES( ?, ?, ?, ?)', (wayid, pickle.dumps(tags), pickle.dumps(refs), pickle.dumps(distances)))

    def getStreetEntryForNameAndCountry(self, streetInfo, country):
        (name, ref)=streetInfo
        self.cursorAdress.execute('SELECT * FROM addressTable where streetName=="%s" and country==%d'%(str(name), country))
        allentries=self.cursorAdress.fetchall()
        resultList=list()
        for x in allentries:
            resultList.append(self.addressFromDB(x))
        
        return resultList
     
    def addToCrossingsTable(self, wayid, refId, nextWaysList):
        self.setDBCursorForCountry(self.country)
        self.cursor.execute('INSERT INTO crossingTable VALUES( ?, ?, ?, ?)', (self.crossingId, wayid, refId, pickle.dumps(nextWaysList)))
        self.crossingId=self.crossingId+1

    def addToEdgeTable(self, startRef, endRef, length, wayId, refList, cost, reverseCost):
        resultList=self.getEdgeEntryForStartAndEndPointAndWayId(startRef, endRef, wayId)
        if len(resultList)==0:
            self.cursorEdge.execute('INSERT INTO edgeTable VALUES( ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (self.edgeId, startRef, endRef, length, wayId, 0, 0, pickle.dumps(refList), cost, reverseCost))
            self.edgeId=self.edgeId+1
        else:
            print("addToEdgeTable: edge for wayId %d with startRef %d and endRef %d already exists in DB"%(wayId, startRef, endRef))
            
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
        self.cursorEdge.execute('SELECT COUNT(*) FROM edgeTable')
        allentries=self.cursorEdge.fetchall()
        return allentries[0][0]
    
    def updateSourceOfEdge(self, edgeId, sourceId):
        existingEdgeId, startRef, endRef, length, wayId, _, target, refList, cost, reverseCost=self.getEdgeEntryForEdgeId(edgeId)
        if existingEdgeId==None:
            print("no edge with id %d"%(edgeId))
            return
#        self.cursorEdge.execute('REPLACE INTO edgeTable VALUES( ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (edgeId, startRef, endRef, length, wayId, sourceId, target, pickle.dumps(refList), cost, reverseCost))
        self.cursorEdge.execute('UPDATE edgeTable SET source=%d WHERE id==%d'%(sourceId, edgeId))

    def updateTargetOfEdge(self, edgeId, targetId):
        existingEdgeId, startRef, endRef, length, wayId, source, _, refList, cost, reverseCost=self.getEdgeEntryForEdgeId(edgeId)
        if existingEdgeId==None:
            print("no edge with id %d"%(edgeId))
            return
#        self.cursorEdge.execute('REPLACE INTO edgeTable VALUES( ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (edgeId, startRef, endRef, length, wayId, source, targetId, pickle.dumps(refList), cost, reverseCost))     
        self.cursorEdge.execute('UPDATE edgeTable SET target=%d WHERE id==%d'%(targetId, edgeId))
     
    def clearSourceAndTargetOfEdges(self):
        self.cursorEdge.execute('SELECT * FROM edgeTable')
        allentries=self.cursorEdge.fetchall()
        for x in allentries:
            edgeId, _, _, _, _, _, _, _, _, _=self.edgeFromDB(x)
            self.updateSourceOfEdge(edgeId, 0)
            self.updateTargetOfEdge(edgeId, 0)

    def getEdgeEntryForSource(self, sourceId):
        self.cursorEdge.execute('SELECT * FROM edgeTable where source==%d'%(sourceId))
        resultList=list()
        allentries=self.cursorEdge.fetchall()
        for result in allentries:
            edge=self.edgeFromDB(result)
            resultList.append(edge)
        return resultList      
    
    def getEdgeEntryForTarget(self, targetId):
        self.cursorEdge.execute('SELECT * FROM edgeTable where target==%d'%(targetId))
        resultList=list()
        allentries=self.cursorEdge.fetchall()
        for result in allentries:
            edge=self.edgeFromDB(result)
            resultList.append(edge)
        return resultList      
    
    def getEdgeEntryForSourceAndTarget(self, sourceId, targetId):
        self.cursorEdge.execute('SELECT * FROM edgeTable where source==%d AND target==%d'%(sourceId, targetId))
        resultList=list()
        allentries=self.cursorEdge.fetchall()
        for result in allentries:
            edge=self.edgeFromDB(result)
            resultList.append(edge)
        return resultList   
    
    def getEdgeEntryForEdgeId(self, edgeId):
        self.cursorEdge.execute('SELECT * FROM edgeTable where id==%d'%(edgeId))
        allentries=self.cursorEdge.fetchall()
        if len(allentries)==1:
            edge=self.edgeFromDB(allentries[0])
            return edge
        print("no edge with %d"%(edgeId))
        return (None, None, None, None, None, None, None, None, None, None)
        
    def getEdgeEntryForStartPoint(self, startRef, edgeId):
        self.cursorEdge.execute('SELECT * FROM edgeTable where startRef=%d AND id!=%d'%(startRef, edgeId))
        resultList=list()
        allentries=self.cursorEdge.fetchall()
        for result in allentries:
            edge=self.edgeFromDB(result)
            resultList.append(edge)
        return resultList
 
    def getEdgeEntryForEndPoint(self, endRef, edgeId):
        self.cursorEdge.execute('SELECT * FROM edgeTable where endRef==%d AND id!=%d'%(endRef, edgeId))
        resultList=list()
        allentries=self.cursorEdge.fetchall()
        for result in allentries:
            edge=self.edgeFromDB(result)
            resultList.append(edge)
        return resultList
    
    def getEdgeEntryForStartAndEndPointAndWayId(self, startRef, endRef, wayId):
        self.cursorEdge.execute('SELECT * FROM edgeTable where startRef==%d AND endRef==%d AND wayId==%d'%(startRef, endRef, wayId))
        resultList=list()
        allentries=self.cursorEdge.fetchall()
        for result in allentries:
            edge=self.edgeFromDB(result)
            resultList.append(edge)
        return resultList
    
    def getEdgeEntryForStartOrEndPoint(self, ref):
        self.cursorEdge.execute('SELECT * FROM edgeTable where startRef==%d OR endRef==%d'%(ref, ref))
        resultList=list()
        allentries=self.cursorEdge.fetchall()
        for result in allentries:
            edge=self.edgeFromDB(result)
            resultList.append(edge)
        return resultList
        
    def getEdgeEntryForWayId(self, wayId):
        self.cursorEdge.execute('SELECT * FROM edgeTable where wayId==%d'%(wayId))
        resultList=list()
        allentries=self.cursorEdge.fetchall()
        for result in allentries:
            edge=self.edgeFromDB(result)
            resultList.append(edge)
        return resultList
    
    def getRefEntryForIdAndCountry(self, refId, country):
        self.setDBCursorForCountry(country)
        self.cursor.execute('SELECT * FROM refTable where refId==%d'%(refId))
        resultList=list()
        allentries=self.cursor.fetchall()
        for result in allentries:
            refEntry=self.refFromDB(result)
            resultList.append(refEntry)
        return resultList
    
    def getRefEntryForIdAndCountryAndWayId(self, refId, country, wayId):
        self.setDBCursorForCountry(country)
        self.cursor.execute('SELECT * FROM refTable where refId==%d AND wayId==%d'%(refId, wayId))
        resultList=list()
        allentries=self.cursor.fetchall()
        for result in allentries:
            refEntry=self.refFromDB(result)
            resultList.append(refEntry)
        return resultList

#    def getRefEntryForId(self, refId):
#        refId, country=self.getCountryOfRef(refId)
#        if refId==None:
#            return list()
#        return self.getRefEntryForIdAnCountry(refId, country)

#    def getWayEntryForId(self, wayId):
#        resultList=self.getCountrysOfWay(wayId)
#        if len(resultList)==0:
#            return (None, None, None, None)
#        
#        country=resultList[0][2]
#        return self.getWayEntryForIdAndCountry(wayId, country)
    
    def getWayEntryForIdAndCountry(self, wayId, country):
        self.setDBCursorForCountry(country)
        self.cursor.execute('SELECT * FROM wayTable where wayId==%d'%(wayId))
        allentries=self.cursor.fetchall()
        if len(allentries)==1:
            return self.wayFromDB(allentries[0])
        
        return (None, None, None, None)
    
    def getCrossingEntryFor(self, wayid, country):
        self.setDBCursorForCountry(country)
        self.cursor.execute('SELECT * FROM crossingTable where wayId==%d'%(wayid))      
        resultList=list()
        allentries=self.cursor.fetchall()
        for result in allentries:
            crossing=self.crossingFromDB(result)
            resultList.append(crossing)
            
        return resultList
    
    def getCrossingEntryForRefId(self, wayid, refId, country):
        self.setDBCursorForCountry(country)
        self.cursor.execute('SELECT * FROM crossingTable where wayId==%d AND refId==%d'%(wayid, refId))  
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
            refGid, refId, lat, lon, wayId=self.refFromDB(x)
            print( "gid:"+str(refGid)+ " ref: " + str(refId) + "  lat: " + str(lat) + "  lon: " + str(lon) + " wayId:"+str(wayId))
         

    def getPrevAndNextRefForWay(self, refId, wayId, tags, refs):
        if refId in refs:
            index=refs.index(refId)
            if index==0 or index==len(refs)-1:
                if index==0:
                    prevRefId=refs[0]
                    nextRevId=refs[index+1]
                if index==len(refs)-1:
                    prevRefId=refs[index-1]
                    nextRevId=refs[-1]
                return (prevRefId, nextRevId)
            else:
                prevRefId=refs[index-1]
                nextRevId=refs[index+1]
                return (prevRefId, nextRevId)
            
        return (None, None)
    
    def getWayIdForPos(self, actlat, actlon):
        polyCountry=self.countryNameOfPoint(actlat, actlon)
        country=self.getCountryForPolyCountry(polyCountry)
        if country==None:
            return None, None, (None, None), None

        start=time.time()
        nodes=self.getNearNodes(actlat, actlon, country)
        stop=time.time()
        print(stop-start)
        minDistance=100
        minWayId=0
        usedRefId=0
        usedLat=0.0
        usedLon=0.0
        if len(nodes)==0:
            return None, None, (None, None), None
        
        for (refId, lat, lon, wayId) in nodes:  
 
            # find matching way by creating interpolation points betwwen refs
            (wayId, tags, refs, _)=self.getWayEntryForIdAndCountry(wayId, country)
            if wayId==None:
                continue
            
            (prevRefId, nextRefId)=self.getPrevAndNextRefForWay(refId, wayId, tags, refs)
            if prevRefId!=None and nextRefId!=None:
                (prevLat, prevLon)=self.getCoordsWithRefAndCountry(prevRefId, country)
                (nextLat, nextLon)=self.getCoordsWithRefAndCountry(nextRefId, country)
                
                if prevRefId==None or prevLon==None or nextLon==None or nextLat==None:
                    continue
                
                tempPoints=self.createTemporaryPoint(lat, lon, prevLat, prevLon)                    
                for (tmpLat, tmpLon) in tempPoints:
                    distance=int(self.osmutils.distance(actlat, actlon, tmpLat, tmpLon))

                    if distance < minDistance:
                        minDistance=distance
                        minWayId=wayId
                        distanceRef=int(self.osmutils.distance(actlat, actlon, lat, lon))
                        distancePrev=int(self.osmutils.distance(actlat, actlon, prevLat, prevLon))
                        if distancePrev<distanceRef:
                            usedRefId=prevRefId
                        else:
                            usedRefId=refId
                        usedLat=tmpLat
                        usedLon=tmpLon
                        
                tempPoints=self.createTemporaryPoint(lat, lon, nextLat, nextLon)
                for (tmpLat, tmpLon) in tempPoints:
                    distance=int(self.osmutils.distance(actlat, actlon, tmpLat, tmpLon))
                    if distance < minDistance:
                        minDistance=distance
                        minWayId=wayId
                        distanceRef=int(self.osmutils.distance(actlat, actlon, lat, lon))
                        distanceNext=int(self.osmutils.distance(actlat, actlon, nextLat, nextLat))
                        if distanceNext<distanceRef:
                            usedRefId=nextRefId
                        else:
                            usedRefId=refId
                        usedLat=tmpLat
                        usedLon=tmpLon

#        print(minWayId)
        return minWayId, usedRefId, (usedLat, usedLon), country
        
    def createTemporaryPoint(self, lat, lon, lat1, lon1):
        distance=int(self.osmutils.distance(lat, lon, lat1, lon1))
        frac=10
        points=list()
        if distance>frac:
            doneDistance=0
            while doneDistance<distance:
                newLat, newLon=self.osmutils.linepart(lat, lon, lat1, lon1, doneDistance/distance)
                points.append((newLat, newLon))
                doneDistance=doneDistance+frac
        return points
            
    def getNearNodes(self, lat, lon, country):
        latRangeMax=lat+0.001
        lonRangeMax=lon+0.001
        latRangeMin=lat-0.001
        lonRangeMin=lon-0.001
        
        nodes=list()
        self.setDBCursorForCountry(country)
        
        start=time.time()

        self.cursor.execute('SELECT * FROM refTable where lat>%f AND lat<%f AND lon>%f AND lon<%f'%(latRangeMin, latRangeMax, lonRangeMin, lonRangeMax))
        allentries=self.cursor.fetchall()
        stop=time.time()
        print(stop-start)
        print(len(allentries))
        for x in allentries:
            refGid, refId, lat1, lon1, wayId=self.refFromDB(x)
            distance=self.osmutils.distance(lat, lon, lat1, lon1)
            if distance>100:
                continue
            nodes.append((refId, lat1, lon1, wayId))

        return nodes
    
    def testWayTable(self, country):
        self.setDBCursorForCountry(country)

        self.cursor.execute('SELECT * FROM wayTable')
        allentries=self.cursor.fetchall()
        for x in allentries:
            wayId, tags, refs, distances=self.wayFromDB(x)
            print( "way: " + str(wayId) + "  tags: " + str(tags) + "  refs: " + str(refs) + " distances: "+str(distances))

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
            edgeId, startRef, endRef, length, wayId, source, target, refList, cost, reverseCost=self.edgeFromDB(x)
            print( "edgeId: "+str(edgeId) +" startRef: " + str(startRef)+" endRef:"+str(endRef)+ " length:"+str(length)+ " wayId:"+str(wayId) +" source:"+str(source)+" target:"+str(target) +" refList:"+str(refList) + " cost:"+str(cost)+ " reverseCost:"+str(reverseCost))
            
    def wayFromDB(self, x):
        wayId=x[0]
        refs=pickle.loads(x[2])
        tags=pickle.loads(x[1])
        distances=pickle.loads(x[3])
        return (wayId, tags, refs, distances)
    
    def refFromDB(self, x):
        refGid=x[0]
        refId=x[1]
        lat=x[2]
        lon=x[3]
        wayId=x[4]
        return (refGid, refId, lat, lon, wayId)
        
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
        refList=pickle.loads(x[7])
        cost=x[8]
        reverseCost=x[9]
        return (edgeId, startRef, endRef, length, wayId, source, target, refList, cost, reverseCost)
        
#    def addAllRefsToDB(self):
#        for ref, wayIdList in self.wayRefIndex.items():
#            (storedRef, lat, lon)=self.getCoordsEntry(ref)
#            if storedRef==None:
#                continue
##            try:
##                lat=self.coords[ref][0]
##                lon=self.coords[ref][1]
##            except KeyError:
##                continue
#            self.addToCountryRefTable(ref, self.country, lat, lon)
#            _, country=self.getCountryOfRef(ref)
#            if country!=None:
#                self.addToRefTable(ref, lat, lon, wayIdList, country)
#            else:
#                print("skipping ref %d because country==None"%(ref))
            
    def addWayToDB(self, wayId, tags, refs, distances, wayCountries):

#        storedStartRef, countryStart=self.getCountryOfRef(refs[0])
#        storedEndRef, countryEnd=self.getCountryOfRef(refs[-1])
#        if wayId==39671191:
#            print("%d %d %d %d"%(storedStartRef, storedEndRef, countryStart, countryEnd))
        
        if len(wayCountries)==0:
            print("addWayToDB: skipping way %d because all refs are not in global ref DB"%(wayId))
            return
        
        for country in wayCountries:
            self.addToWayTable(wayId, tags, refs, distances, country)   
            self.addToCountryWayTable(wayId, country)
           
#        if storedStartRef==None and storedEndRef==None:
#            print("addWayToDB: skipping way %d because startRef and endRef not in global ref DB"%(wayId))
#            return
#
#        if countryStart==None and countryEnd==None:
#            print("addWayToDB: skipping way %d because country==None"%(wayId))
#            return
#        
#        if countryStart==None:
#            self.addToWayTable(wayId, tags, refs, distances, countryEnd)   
#            self.addToCountryWayTable(wayId, countryEnd)
#            
#        elif countryEnd==None:
#            self.addToWayTable(wayId, tags, refs, distances, countryStart)   
#            self.addToCountryWayTable(wayId, countryStart)
#            
#        elif countryEnd==countryStart:
#            self.addToWayTable(wayId, tags, refs, distances, countryStart)   
#            self.addToCountryWayTable(wayId, countryStart)
#         
#        else:
#            self.addToWayTable(wayId, tags, refs, distances, countryStart)                
#            self.addToCountryWayTable(wayId, countryStart)
#            self.addToWayTable(wayId, tags, refs, distances, countryEnd)                
#            self.addToCountryWayTable(wayId, countryEnd)
    
#    def addAllWaysToDB(self):
#        for wayId, wayData in self.ways.items():
#            self.addWaysToDB(wayData)
    
    def parse_nodes(self, node):
        for osmid, tags, coords in node:
            # <tag k="highway" v="motorway_junction"/>
            if "highway" in tags:
                if tags["highway"]=="motorway_junction":
                    self.nodes[osmid]=(tags, coords)
                if tags["highway"]=="traffic_signals":
                    self.nodes[osmid]=(tags, coords)
            else:
                self.parseAddress(tags, osmid, coords[1], coords[0])

    def parse_coords(self, coord):
        for osmid, lon, lat in coord:
#            self.coords[int(osmid)]=(float(lat), float(lon))
            self.addToCoordsTable(osmid, float(lat), float(lon))
              
    def parseAddress(self, tags, refId, lat, lon):  
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
        countryCode=None
        if "addr:city" in tags:
            city=tags["addr:city"]
        if "addr:housenumber" in tags:
            houseNumber=tags["addr:housenumber"]
        if "addr:postcode" in tags:
            postCode=tags["addr:postcode"]
        if "addr:street" in tags:
            streetName=tags["addr:street"]
        if "addr:country" in tags:
            countryCode=tags["addr:country"]
        
        if city==None and postCode==None:
            return
        if streetName==None:
            return
        if houseNumber==None:
            return
        country=self.getCountryIdForAddrCountry(countryCode)
        if country==None:
            country=self.country
        
        self.addToAddressTable(refId, country, city, postCode, streetName, houseNumber, lat, lon)

    def parse_ways(self, way):
        for wayid, tags, refs in way:
            if len(refs)==1:
                print("way with len(ref)==1 %d"%(wayid))
                continue
            
            if "building" in tags:
                storedRef, lat, lon=self.getCoordsEntry(refs[0])
                if storedRef!=None:
                    if lat!=None and lon!=None:
                        self.parseAddress(tags, refs[0], lat, lon)

            if "highway" in tags:
                streetType=tags["highway"]
                if streetType=="services" or streetType=="bridleway" or streetType=="path" or streetType=="track" or streetType=="footway" or streetType=="pedestrian" or streetType=="cycleway" or streetType=="service" or streetType=="steps" or streetType=="platform" or streetType=="crossing" or streetType=="raceway" or streetType=="construction" or streetType=="via_ferrata":
                    continue
                
#                if streetType=="unclassified":
#                    continue
                
                if "piste:type" in tags:
                    continue
                    
                if "class:bicycle:roadcycling" in tags:
                    continue
                
                if "service" in tags:
                    continue
                
                if "parking" in tags:
                    continue
                
                if "amenity" in tags:
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
                    
                if "bicycle" in tags:
                    if tags["bicycle"]=="designated":
                        continue
                    
#                if "acccess" in tags:
#                    if tags["access"]=="private":
#                        continue
                
                if "area" in tags:
                    if tags["area"]=="yes":
                        continue
                if "building" in tags:
                    if tags["building"]=="yes":
                        continue
                distances=list()
                    
                lastLat=None
                lastLon=None
                wayCountries=list()
                
                for ref in refs:  
                    storedRef, lat, lon=self.getCoordsEntry(ref)
                    if storedRef==None:
#                        print("wayId %d no coords for ref %d"%(wayid, ref))
                        distances.append(0)
                        continue
                    
                    if lastLat!=None and lastLon!=None:
                        distance=int(self.osmutils.distance(lat, lon, lastLat, lastLon))
                        distances.append(distance)
                        lastLat=lat
                        lastLon=lon
                    else:
                        lastLat=lat
                        lastLon=lon
                        distances.append(0)
                        
                    self.addToCountryRefTable(ref, lat, lon)
                    addedRef, country=self.getCountryOfRef(ref)
                    if country!=None:
                        self.addToRefTable(ref, lat, lon, wayid, country)
                        wayCountries.append(country)

                self.addWayToDB(wayid, tags, refs, distances, wayCountries)
        
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
                        
                if tags["type"]=="multipolygon":
                    if "boundary" in tags:
                        if tags["boundary"]=="administrative":
#                            print(tags)
                            None
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

            
    def getStreetNameInfo(self, tags):
        if not "highway" in tags:
            None
        streetType=tags["highway"]

        name=""
        ref=""
        intref=""
        
        if "name" in tags:
            name=tags["name"]
        
        if "ref" in tags:
            ref=tags["ref"]
            
        if "int_ref" in tags:
            intref=tags["int_ref"]
            
        if streetType=="motorway" or streetType=="motorway_link":
            if ref!="":
                ref=ref.replace(' ', '')
                if name=="":
                    name=ref    
        elif streetType=="primary" or streetType=="primary_link":
            if ref!="":
                ref=ref.replace(' ', '')    
                if not ref[0]=="B":
                    ref="B"+ref
                if name=="":
                    name=ref    
        elif streetType=="secondary" or streetType=="secondary_link":
            if ref!="":
                ref=ref.replace(' ', '')
                if not ref[0]=="L":
                    ref="L"+ref
                if name=="":
                    name=ref  
        elif streetType=="tertiary" or streetType=="tertiary_link":
            if ref!="":
                ref=ref.replace(' ', '')
                if name=="":
                    name=ref  
        elif streetType=="residential":
            if ref!="":
                ref=ref.replace(' ', '')
                if name=="":
                    name=ref  
        elif streetType=="trunk" or streetType=="trunk_link":
            if ref!="":
                ref=ref.replace(' ', '')
                if name=="":
                    name=ref  
        elif streetType=="unclassified":
            None

        return (name, ref)
    
    def getWaysWithRefAndCountry(self, ref, country):
        wayIdList=list()
        resultList=self.getRefEntryForIdAndCountry(ref, country)
        for result in resultList:
            refGid, refId, lat, lon, wayId=result
            wayIdList.append(wayId)
        
        return wayIdList

    def getStreetInfoWithWayId(self, wayId, country):
        (streetEntryId, tags, _, _)=self.getWayEntryForIdAndCountry(wayId, country)
        if streetEntryId!=None:
            (name, ref)=self.getStreetNameInfo(tags)
            return (name, ref)
        return (None, None)
        
    def getCoordsWithRefAndCountry(self, refId, country):
        resultList=self.getRefEntryForIdAndCountry(refId, country)
        if len(resultList)!=0:
            return (resultList[0][2], resultList[0][3])
        
        return (None, None)
    
    def findWayWithRefInAllWays(self, refId, fromWayId):
        possibleWays=list()
        _, country=self.getCountryOfRef(refId)
        if country==None:
#            print("create crossings: skip crossing for wayId %d at refId %d it is in country==None"%(fromWayId, refId))
            return possibleWays
        
        wayIdList=self.getWaysWithRefAndCountry(refId, country)
        if len(wayIdList)==0:
            # no crossings at ref
            return possibleWays
        
        for wayid in wayIdList:
            if wayid==fromWayId:
                continue
            
            resultList=self.getCountrysOfWay(wayid)
            if len(resultList)!=0:
                for result in resultList:
                    _, wayid, storedCountry=result
    
                    (wayEntryId, tags, refs, _)=self.getWayEntryForIdAndCountry(wayid, storedCountry)
                    if wayEntryId==None:
                        print("create crossings: skip crossing for wayId %s at refId %d to wayId %d to country %d"%(fromWayId, refId, wayid, storedCountry))
                        continue
                    
                    for wayRef in refs:
                        if wayRef==refId:
                            possibleWays.append((wayid, tags, refs))
            else:
                print("create crossings: skip crossing for wayId %d at refId %d to wayId %s since it is in an unknown country"%(fromWayId, refId, wayid))
        return possibleWays
    
    def findWayWithEndRef(self, ways, endRef, country):
        possibleWays=list()
        for wayId  in ways:
            (actWayId, _, refs, _)=self.getWayEntryForIdAndCountry(wayId, country)
            if refs[-1]==endRef:
                possibleWays.append(actWayId)
        return possibleWays
    
    def findStartWay(self, ways, country):
        for wayId  in ways:
            (actWayId, _, refs, _)=self.getWayEntryForIdAndCountry(wayId, country)
            startRef=refs[0]
            possibleWays=self.findWayWithEndRef(ways, startRef, country)
            if len(possibleWays)==0:
                return actWayId
        return ways[0]
    
    def getAddressList(self):
        self.cursorAdress.execute('SELECT * FROM addressTable')
        allentries=self.cursorAdress.fetchall()
        streetList=list()
        for x in allentries:
            streetList.append(self.addressFromDB(x))
        return streetList
    
    def getAdressCountryList(self):
        return self.osmList.keys()
    
    def getAdressCityList(self, country):
        self.cursorAdress.execute('SELECT DISTINCT city, postCode FROM addressTable WHERE country==%d ORDER by city'%(country))
        allentries=self.cursorAdress.fetchall()
        cityList=list()
        for x in allentries:
            if x[0]!=None:
                cityList.append((x[0], x[1]))
        return cityList

    def getAdressPostCodeList(self, country):
        self.cursorAdress.execute('SELECT postCode FROM addressTable WHERE country==%d'%(country))
        allentries=self.cursorAdress.fetchall()
        postCodeList=set()
        for x in allentries:
            postCode=x[0]
            postCodeList.append(postCode)
        return postCodeList

    def getAdressListForCity(self, country, city):
        self.cursorAdress.execute('SELECT refId, streetName, houseNumber, lat, lon FROM addressTable WHERE country==%d AND city=="%s"'%(country, str(city)))
        allentries=self.cursorAdress.fetchall()
        streetList=list()
        for x in allentries:
            streetList.append((x[0], x[1], x[2], x[3], x[4]))
        return streetList
                    
    def getAdressListForPostCode(self, country, postCode):
        self.cursorAdress.execute('SELECT refId, streetName, houseNumber, lat, lon FROM addressTable WHERE country==%d AND postCode=="%s"'%(country, str(postCode)))
        allentries=self.cursorAdress.fetchall()
        streetList=list()
        for x in allentries:
            streetList.append((x[0], x[1], x[2], x[3]))
        return streetList
    
    def getAdressListForCountry(self, country):
        self.cursorAdress.execute('SELECT city, postCode, streetName, houseNumber, lat, lon FROM addressTable WHERE country==%d'%(country))
        allentries=self.cursorAdress.fetchall()
        streetList=list()
        for x in allentries:
            streetList.append((x[0], x[1], x[2], x[3], x[4], x[5]))
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
        
    def createBBox(self, lat1, lon1, lat2, lon2):
        bbox=[0.0, 0.0, 0.0, 0.0]
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

    def calcRouteForPoints(self, routingPointList):        
        allPathCost=0.0
        allEdgeList=list()
        
        if len(routingPointList)!=0:  
            i=0   
            startPoint=routingPointList[0]
            if startPoint.getSource()==0:
                # should not happen
                print("startPoint NOT resolved in calc route")
                return None, None
#                startPoint.resolveFromPos(self)
            source=startPoint.getSource()
            sourceEdge=startPoint.getEdgeId()

            for targetPoint in routingPointList[1:]:
            # find out if last edge goes through the end point
            # if yes we need to shorten it
            # if no we need to add the last points
            # same is true for the actual starting point

                if targetPoint.getTarget()==0:
                    # should not happen
                    print("targetPoint NOT resolved in calc route")
                    return None, None
#                    targetPoint.resolveFromPos(self)
                target=targetPoint.getTarget()
                targetEdge=targetPoint.getEdgeId()
                            
                print("%d %d %d %d"%(source, sourceEdge, startPoint.getWayId(), startPoint.getRefId()))
                print("%d %d %d %d"%(target, targetEdge, targetPoint.getWayId(), targetPoint.getRefId()))
                
                if source==0 and target==0:
                    print("source and target==0!")
                    break

                if source==target:
                    print("source and target equal!")
                    allEdgeList.append(startPoint.getEdgeId())
                    allEdgeList.append(targetPoint.getEdgeId())

#                    allPathCost=allPathCost+pathCost       
#                elif targetEdge==sourceEdge:
#                    print("source edge and target edge equal!")
#                    allEdgeList.append(startPoint.getEdgeId())
#                    allEdgeList.append(targetPoint.getEdgeId())
                      
                else:                  
#                    if self.dWrapper!=None:
#                        edgeList, pathCost=self.dWrapper.computeShortestPath(source, target)
#                        allEdgeList.extend(edgeList)
#                        allPathCost=allPathCost+pathCost            
                
                    bbox=self.createBBox(startPoint.getLat(), startPoint.getLon(), targetPoint.getLat(), targetPoint.getLon())
                    if self.dWrapperTrsp!=None:
                        edgeList, pathCost=self.dWrapperTrsp.computeShortestPath(source, target, bbox)
                        allEdgeList.extend(edgeList)
                        allPathCost=allPathCost+pathCost 
                        
                startPoint=targetPoint
                source=startPoint.getTarget()
                sourceEdge=startPoint.getEdgeId()
                i=i+1
                
            return allEdgeList, allPathCost

        return None, None

    def calcRouteForNodes(self, source, target):        
        if source==0 and target==0:
            print("source and target==0!")
            return None
        
        if self.dWrapper!=None:
            edgeList, pathCost=self.dWrapper.computeShortestPath(source, target)
            return edgeList, pathCost
                                
        return None

    def calcRouteForNodesTrsp(self, source, target):        
        if source==0 and target==0:
            print("source and target==0!")
            return None
        
        if self.dWrapperTrsp!=None:
            edgeList, pathCost=self.dWrapperTrsp.computeShortestPath(source, target)
            return edgeList, pathCost
                                
        return None
            
    def printEdgeForRefList(self, refListPart, edgeId, trackWayList, routeEndRefId, routeStartRefId):
        result=self.getEdgeEntryForEdgeId(edgeId)
#        print(result)
#        print(refListPart)
        (edgeId, _, _, length, wayId, _, _, _, _, _)=result
            
#        trackWayList.append(self.createStartTrackItem())
        latTo=None
        lonTo=None
        latFrom=None
        lonFrom=None
        for ref in refListPart:  
            _, country=self.getCountryOfRef(ref)
            if country==None:
                continue
            
            (wayId, tags, _, _)=self.getWayEntryForIdAndCountry(wayId, country)

            if "highway" in tags:
                streetType=tags["highway"]
            
                (name, refName)=self.getStreetNameInfo(tags)

            if routeStartRefId!=None:
                if ref!=routeStartRefId:
#                    print("skip before start ref %d"%(ref))
                    continue
                else:
                    routeStartRefId=None

            trackItem=dict()
            trackItem["edgeId"]=edgeId
            trackItem["wayId"]=wayId
            trackItem["ref"]=ref
            (lat, lon)=self.getCoordsWithRefAndCountry(ref, country)
            if lat==None:
                print("resolveWay no node in DB with %d"%(ref))
                continue
            
            if ref!=refListPart[-1]:
                latFrom=lat
                lonFrom=lon
                      
            if ref!=refListPart[0]:
                latTo=lat
                lonTo=lon
                
            if self.lastTrackItem!=None and latTo!=None and lonTo!=None and self.latCross!=None and self.lonCross!=None and self.latFrom!=None and self.lonFrom!=None:
#                print("%f-%f %f-%f %f-%f"%(self.latCross, self.lonCross, self.latFrom, self.lonFrom, latTo, lonTo))
                azimuth=self.osmutils.azimuth((self.latCross, self.lonCross), (self.latFrom, self.lonFrom), (latTo, lonTo))   
                direction=self.osmutils.direction(azimuth)
#                print(direction)
#                print(azimuth)
                self.lastTrackItem["direction"]=direction
                if "crossing" in self.lastTrackItem:
                    crossingType, crossingInfo=self.lastTrackItem["crossing"]
                    lastName=None
                    if "info" in self.lastTrackItem:
                        (lastName, lastRefName)=self.lastTrackItem["info"]

                    if crossingType==1 or crossingType==0:
                        if lastName!=None:
                            if lastName!=name:
                                self.lastTrackItem["crossingInfo"]="change:%s:%s"%(name, refName)
#                                print("change to %s %s"%(name, refName))
                            else:
                                self.lastTrackItem["crossingInfo"]="stay:%s:%s"%(name, refName)
#                                print("stay on %s %s"%(name, refName))
                    elif crossingType==2:
                        # highway junction
                        motorwayExitName=crossingInfo
                        if lastName!=None:
                            if lastName!=name:
                                self.lastTrackItem["crossingInfo"]="exit:%s"%(motorwayExitName)
#                                print("exit motorway at %s"%(motorwayExitName))
                            else:
                                self.lastTrackItem["crossingInfo"]="stay:%s:%s"%(name, refName)
#                                print("stay on %s %s"%(name, refName))

                self.lastTrackItem=None
                self.latCross=None
                self.lonCross=None

            trackItem["lat"]=lat
            trackItem["lon"]=lon        
#            trackItem["oneway"]=bool(oneway)
            trackItem["type"]=streetType
            trackItem["info"]=(name, ref)
#            trackItem["maxspeed"]=maxspeed
            trackItem["length"]=length
            resultList=self.getCrossingEntryForRefId(wayId, ref, country)
            if len(resultList)!=0:
                crossingType=-1
                crossingInfo=None
                for result in resultList:
                    if crossingType!=-1:
                        break
                    (_, wayId, _, nextWayIdList)=result
                    for _, crossingType, crossingInfo in nextWayIdList:
                        if crossingType!=-1:
                            break
                if crossingType!=-1:
                    trackItem["crossing"]=(crossingType, crossingInfo)
                    self.latCross=lat
                    self.lonCross=lon
               
            trackWayList.append(trackItem)
            
            if routeEndRefId!=None and ref==routeEndRefId:
#                print("skip end after stop ref %d"%(ref))
                break
        self.lastTrackItem=trackItem
        self.latFrom=latFrom
        self.lonFrom=lonFrom

    def printRoute(self, route):
        edgeList=route.getEdgeList()
        routingPointList=route.getRoutingPointList()
        
        trackWayList=list()
        allLength=0
        self.latFrom=None
        self.lonFrom=None
        self.latCross=None
        self.lonCross=None
        self.lastTrackItem=None
        
        endPoint=routingPointList[-1]
        routeEndRefId=endPoint.getRefId()
        endEdgeId=endPoint.getEdgeId()

        startPoint=routingPointList[0]
        routeStartRefId=startPoint.getRefId()
        startEdgeId=startPoint.getEdgeId()
     
        currentRefList=None

        if len(edgeList)==0:
            (startEdgeId, _, _, _, _, _, _, startRefList, _, _)=self.getEdgeEntryForEdgeId(startEdgeId)                       
            indexStart=startRefList.index(routeStartRefId)
            indexEnd=startRefList.index(routeEndRefId)
            if indexEnd < indexStart:
                startRefList.reverse()
            self.printEdgeForRefList(startRefList, startEdgeId, trackWayList, routeEndRefId, routeStartRefId)  
        else:
            firstEdgeId=edgeList[0]
            (firstEdgeId, firstStartRef, firstEndRef, _, _, _, _, refList, _, _)=self.getEdgeEntryForEdgeId(firstEdgeId)                       
        
            if not routeStartRefId in refList:
                (startEdgeId, startStartRef, _, length, _, _, _, startRefList, _, _)=self.getEdgeEntryForEdgeId(startEdgeId)                       
            
                if firstStartRef==startStartRef or firstEndRef==startStartRef:
                    startRefList.reverse()
                print("add start edge")
                self.printEdgeForRefList(startRefList, startEdgeId, trackWayList, None, routeStartRefId)
                currentRefList=startRefList
                routeStartRefId=None
                # TODO maybe not the complete length
                allLength=allLength+length
    
            for edgeId in edgeList:
                (edgeId, currentStartRef, _, length, _, _, _, refList, _, _)=self.getEdgeEntryForEdgeId(edgeId)                       
    
                if currentRefList!=None:
                    if currentRefList[-1]!=refList[0]:
                        refList.reverse()
                else:
                    if len(edgeList)>1:
                        nextEdgeId=edgeList[1]
                        (nextEdgeId, nextStartRef, nextEndRef, _, _, _, _, _, _, _)=self.getEdgeEntryForEdgeId(nextEdgeId)                       
        
                        if nextStartRef==currentStartRef or nextEndRef==currentStartRef:
                            refList.reverse()
    
                self.printEdgeForRefList(refList, edgeId, trackWayList, routeEndRefId, routeStartRefId)
                
                currentRefList=refList
                routeStartRefId=None
                # TODO maybe not the complete length
                allLength=allLength+length
                                         
            if not routeEndRefId in currentRefList:      
                (endEdgeId, _, _, length, _, _, _, endRefList, _, _)=self.getEdgeEntryForEdgeId(endEdgeId)
                if currentRefList[-1]!=endRefList[0]:
                    endRefList.reverse()
                print("add end edge")
                self.printEdgeForRefList(endRefList, endEdgeId, trackWayList, routeEndRefId, None)
                # TODO maybe not the complete length
                allLength=allLength+length
                            
        return trackWayList, allLength   

    def createEdgeTableEntries(self, country):
        self.setDBCursorForCountry(country)
        self.cursor.execute('SELECT * FROM wayTable')
        allWays=self.cursor.fetchall()
#        numWays=len(allWays)
#        print(numWays, end=" ")
#        parts=int(numWays/50)
#        count=0

        for way in allWays:
#            count=count+1
#            if count>parts:
#                print(".", end="")
#                count=0
                
            self.createEdgeTableEntriesForWay(self.wayFromDB(way), country)

    def createEdgeTableNodeEntries(self):
#        self.createEdgeTableIndexes()

        self.cursorEdge.execute('SELECT id FROM edgeTable')
        allEdges=self.cursorEdge.fetchall()
#        numEdges=len(allEdges)
#        print(numEdges, end=" ")
#        parts=int(numEdges/50)
#        count=0
        for edgeEntryId in allEdges:
#            count=count+1
#            if count>parts:
#                print(".", end="")
#                count=0
                
            edgeId=edgeEntryId[0]
            edge=self.getEdgeEntryForEdgeId(edgeId)
            self.createEdgeTableNodeSameStartEnriesFor(edge)
            
#        for id in allEdges:
#            edgeId=id[0]
            edge=self.getEdgeEntryForEdgeId(edgeId)
            self.createEdgeTableNodeSameEndEnriesFor(edge)

#        for id in allEdges:
#            edgeId=id[0]
            edge=self.getEdgeEntryForEdgeId(edgeId)
            self.createEdgeTableNodeSourceEnriesFor(edge)

        self.cursorEdge.execute('SELECT id FROM edgeTable WHERE source==0 OR target==0')
        allEdges=self.cursorEdge.fetchall()

        for edgeEntryId in allEdges:
            edgeId=edgeEntryId[0]
            edge=self.getEdgeEntryForEdgeId(edgeId)
            edgeId, _, _, _, _, source, target, _, _, _=edge
            
#            (lat, lon)=self.getCoordsWithRefAndCountry(endRef)
#            if lat!=None and lon!=None:
#                pointCountry=self.countryNameOfPoint(lat, lon)
#                if currentCountry!=pointCountry:
#                    print("ref %d is in country %s"%(endRef, pointCountry))
#            (lat, lon)=self.getCoordsWithRefAndCountry(startRef)
#            if lat!=None and lon!=None:
#                pointCountry=self.countryNameOfPoint(lat, lon)
#                if currentCountry!=pointCountry:
#                    print("ref %d is in country %s"%(startRef, pointCountry))
            
            if source==0:
                sourceId=self.nodeId
                self.nodeId=self.nodeId+1
                self.updateSourceOfEdge(edgeId, sourceId)
            if target==0:
                targetId=self.nodeId
                self.nodeId=self.nodeId+1
                self.updateTargetOfEdge(edgeId, targetId)
                
   
    def createEdgeTableNodeSameStartEnriesFor(self, edge):
        edgeId, startRef, _, _, _, sourceId, _, _, _, _=edge
                           
        resultList=self.getEdgeEntryForStartPoint(startRef, edgeId)
        if len(resultList)!=0:
            if sourceId==0:
                sourceId=self.nodeId
                self.nodeId=self.nodeId+1
    
        for result in resultList:
            edgeId1, _, _, _, _, source1, _, _, _, _=result
            if source1!=0:
                continue

            self.updateSourceOfEdge(edgeId, sourceId)
            self.updateSourceOfEdge(edgeId1, sourceId)

    def createEdgeTableNodeSameEndEnriesFor(self, edge):
        edgeId, _, endRef, _, _, _, targetId, _, _, _=edge
                           
        resultList=self.getEdgeEntryForEndPoint(endRef, edgeId)
        if len(resultList)!=0:
            if targetId==0:
                targetId=self.nodeId
                self.nodeId=self.nodeId+1
            
        for result in resultList:
            edgeId1, _, _, _, _, _, target1, _, _, _=result
            if target1!=0:
                continue
            
            self.updateTargetOfEdge(edgeId, targetId)
            self.updateTargetOfEdge(edgeId1, targetId)
            
    def createEdgeTableNodeSourceEnriesFor(self, edge):
        edgeId, _, endRef, _, _, _, targetId, _, _, _=edge
        
        resultList=self.getEdgeEntryForStartPoint(endRef, edgeId)        
        if len(resultList)!=0:
            if targetId==0:
                targetId=self.nodeId
                self.nodeId=self.nodeId+1

        for result in resultList:
            edgeId1, _, _, _, _, source1, _, _, _, _=result
            
            if source1==0:
                self.updateSourceOfEdge(edgeId1, targetId)
                self.updateTargetOfEdge(edgeId, targetId)
            else:
                self.updateTargetOfEdge(edgeId, source1)
    
    def createWayRestrictionsDB(self):
        # TODO left turns should increase costs
        toAddRules=list()
        for wayRestrictionEntry in self.wayRestricitionList:
            fromWayId=int(wayRestrictionEntry["from"])
            toWayId=int(wayRestrictionEntry["to"])
            restrictionType=wayRestrictionEntry["type"]

            resultList=self.getEdgeEntryForWayId(fromWayId)
            for fromWayIdResult in resultList:
                (fromEdgeId, startRefFrom, endRefFrom, _, fromWayId, _, _, _, _, _)=fromWayIdResult
    
                resultList1=self.getEdgeEntryForWayId(toWayId)
                if len(resultList1)!=0:
                    for toWayIdResult in resultList1:                        
                        (toEdgeId, startRefTo, endRefTo, _, toWayId, _, _, _, _, _)=toWayIdResult
                                                        
                        crossingRef=None
                        if startRefTo==startRefFrom or endRefTo==startRefFrom:
                            crossingRef=startRefFrom
                        
                        if endRefTo==endRefFrom or startRefTo==endRefFrom:
                            crossingRef=endRefFrom
                                                            
                        if crossingRef==None:
                            continue
                        
#                        self.wayRestricitionList.remove(wayRestrictionEntry)

                        if restrictionType[:3]=="no_":
                            if not (toEdgeId, fromEdgeId) in toAddRules:
                                toAddRules.append((toEdgeId, fromEdgeId))
                            continue
                        
                        if restrictionType[:5]=="only_":
                            resultList2=self.getEdgeEntryForStartOrEndPoint(crossingRef)

                            if len(resultList2)!=0:
                                for edge in resultList2:
                                    (otherEdgeId, _, _, _, otherWayId, _, _, _, _, _)=edge
                                    
                                    if otherWayId==fromWayId or otherWayId==toWayId:
                                        continue
                                    if not (otherEdgeId, fromEdgeId) in toAddRules:
                                        toAddRules.append((otherEdgeId, fromEdgeId))

        for toEdgeId, fromEdgeId in toAddRules:
            self.addToRestrictionTable(toEdgeId, str(fromEdgeId), 10000)
        
#        if len(self.wayRestricitionList)!=0:
#            print("could not resolve this way restricions")
#            print(self.wayRestricitionList)
            
    def getStreetTypeFactor(self, streetType):
        if streetType=="motorway" or streetType=="motorway_link":
            return 1.0
        if streetType=="trunk" or streetType=="trunk_link":
            return 1.1
        if streetType=="primary" or streetType=="tertiary_link":
            return 1.2
        if streetType=="secondary" or streetType=="primary_link":
            return 1.3
        if streetType=="tertiary" or streetType=="tertiary_link":
            return 1.4
        if streetType=="residential":
            return 1.5
        
        return 1.6
        
    def getMaxspeed(self, tags, streetType):
        maxspeedDefault=50
        maxspeed=50
        # TODO iplicit
        #     <tag k="source:maxspeed" v="AT:urban"/>
        if "zone:maxspeed" in tags:
            if "urban" in tags["zone:maxspeed"]:
                maxspeed=50
            elif "rural" in tags["zone:maxspeed"]:
                maxspeed=100
            elif "DE:30" in tags["zone:maxspeed"]:
                maxspeed=30
        elif "zone:traffic" in tags:
            if "urban" in tags["zone:traffic"]:
                maxspeed=50
            elif "rural" in tags["zone:traffic"]:
                maxspeed=100
            elif "DE:30" in tags["zone:traffic"]:
                maxspeed=30
        elif "source:maxspeed" in tags:
            if "urban" in tags["source:maxspeed"]:
                maxspeed=50
            elif "motorway" in tags["source:maxspeed"]:
                maxspeed=130
            elif "rural" in tags["source:maxspeed"]:
                maxspeed=100
        elif "maxspeed" in tags:
            if "urban" in tags["maxspeed"]:
                maxspeed=50
            elif "motorway" in tags["maxspeed"]:
                maxspeed=130
            elif "rural" in tags["maxspeed"]:
                maxspeed=100
            else:
                maxspeed=tags["maxspeed"]
    
                if ";" in maxspeed:
                    try:
                        maxspeed=int(maxspeed.split(";")[0])
                    except ValueError:
                        maxspeed=int(maxspeed.split(";")[1])
                else:
                    if maxspeed=="none":
                        if "motorway" in streetType:
                            maxspeed=130
                        elif "trunk" in streetType:
                            maxspeed=100
                        else:
                            maxspeed=50
                    else:
                        try:
                            maxspeed=int(maxspeed)
                        except ValueError:
                            print(tags)
                            maxspeed=maxspeedDefault
        else:
            if streetType=="residential":
                maxspeed=50
            elif "trunk" in streetType:
                maxspeed=100
            elif "motorway" in streetType:
                maxspeed=130
            else:
                maxspeed=50
        
        try:
            maxspeed=int(maxspeed)
        except ValueError:
            print(tags)
            maxspeed=maxspeedDefault
            
        return maxspeed

    def getAccessFactor(self, tags):
        if "motorcar" in tags:
            if tags["motorcar"]=="destination":
                return 100
                
        if "motor_vehicle" in tags:
            if tags["motor_vehicle"]=="destination":
                return 100
            
        if "acccess" in tags:
            if tags["access"]=="destination":
                return 100
            elif tags["access"]=="permissive":
                return 100
            elif tags["access"]=="private":
                return 10000

        return 1
    
    def getCrossingsFactor(self, crossingType):
        if crossingType==0:
            return 1.1
        if crossingType==1:
            return 1.2
        return 1
    
    def createEdgeTableEntriesForWay(self, way, country):        
        wayId, tags, refs, distances=way
        resultList=self.getCrossingEntryFor(wayId, country)
        
        nextWayDict=dict()
        for result in resultList:
            _, wayId, refId, nextWayIdList=result
            nextWayDict[refId]=nextWayIdList

        # crossings with traffic lights should increase cost for this edge
        # motorway exists also
        
        oneway=0
        roundabout=0
        maxspeed=1
        streetType=""
        if "highway" in tags:
            streetType=tags["highway"]
            
        if "oneway" in tags:
            if tags["oneway"]=="yes":
                oneway=1
        if "junction" in tags:
            if tags["junction"]=="roundabout":
                oneway=1
                roundabout=1
        elif refs[0]==refs[-1]:
            oneway=1
        
        accessFactor=self.getAccessFactor(tags)
                 
        streetTypeFactor=self.getStreetTypeFactor(streetType)
        
        maxspeed=self.getMaxspeed(tags, streetType)
        if maxspeed==0:
            return
        
        crossingFactor=1
        
        doneRefs=list()
        doneRefsCrossingType=dict()
        for ref in refs:                  
            if ref in nextWayDict:                                                                        
                nextWayIdList=nextWayDict[ref]
                for _, crossingType, crossingInfo in nextWayIdList:
                    cf=self.getCrossingsFactor(crossingType)
                    if cf>crossingFactor:
                        crossingFactor=cf
                        
                doneRefs.append(ref)
        
        refNodeList=list()
        distance=0
        i=0
        for ref in refs:
            if ref in doneRefs:
                if len(refNodeList)!=0:
                    refNodeList.append(ref)
                        
                    startRef=refNodeList[0]
                    endRef=refNodeList[-1]

#                    cost=distance
                    
                    
                    try:
                        cost=(distance * streetTypeFactor * accessFactor * crossingFactor) / (maxspeed/3.6)
                    except ZeroDivisionError:
                        # TODO
                        cost=42
                        print(tags)
                    except TypeError:
                        print(tags)
                    # TODO streettype dependend costs
#                        if ref in doneRefsCrossingType:
#                            cost=cost+30
                        
                    if oneway:
                        reverseCost=100000
                    else:
                        reverseCost=cost
                        
                    self.addToEdgeTable(startRef, endRef, distance, wayId, refNodeList, cost, reverseCost)
                        
                    refNodeList=list()
                    distance=0
           
            refNodeList.append(ref)
            if i+1<len(distances):
                distance=distance+distances[i+1]
            i=i+1
        
        # handle last portion
        if not ref in doneRefs:
            if len(refNodeList)!=0:
                startRef=refNodeList[0]
                endRef=refNodeList[-1]
                
#                cost=distance
                # TODO streettype dependend costs
                try:
                    cost=(distance * streetTypeFactor * accessFactor * crossingFactor) / (maxspeed/3.6)
                except ZeroDivisionError:
                    # TODO
                    cost=42
                    print(tags)
                except TypeError:
                    print(tags)
                
#                    if ref in doneRefsCrossingType:
#                        cost=cost+30
                
                if oneway:
                    reverseCost=100000
                else:
                    reverseCost=cost
                    
                self.addToEdgeTable(startRef, endRef, distance, wayId, refNodeList, cost, reverseCost)

    def createCrossingEntries(self, country):
        self.setDBCursorForCountry(country)
        self.cursor.execute('SELECT * FROM wayTable')
        allWays=self.cursor.fetchall()
#        numWays=len(allWays)
#        print(len(allWays), end=' ')
#        parts=int(numWays/50)
#        count=0
        for way in allWays:
#            count=count+1
#            if count>parts:
#                print(".", end="")
#                count=0

            wayid, tags, refs, _=self.wayFromDB(way)    
             
#            if not self.isWayInCountry(wayid, self.country):
#                continue
            
            streetInfo=None
            if "name" in tags or "ref" in tags:
                streetInfo=self.getStreetNameInfo(tags) 
                            
            crossingType=0
            crossingInfo=None
            for ref in refs:  
                nextWays=self.findWayWithRefInAllWays(ref, wayid)  
                if len(nextWays)!=0:
                    if ref in self.nodes:
                        nodeTags, _=self.nodes[ref]
#                        <tag k="highway" v="traffic_signals"/>
                        if "highway" in nodeTags:
                            if nodeTags["highway"]=="traffic_signals":
                                crossingType=1
                            if nodeTags["highway"]=="motorway_junction":
                                crossingType=2
                                if "ref" in nodeTags:
                                    crossingInfo=nodeTags["ref"]
                                
                    wayList=list()
                    for (wayid2, tags2, refs2) in nextWays:                       
                                
                        if streetInfo!=None:
                            if "name" in tags or "ref" in tags2:
                                newStreetInfo=self.getStreetNameInfo(tags2) 
                                if streetInfo==newStreetInfo:
                                    crossingType=-1

                        wayList.append((wayid2, crossingType, crossingInfo))
                    
                    if len(wayList)!=0:
                        self.addToCrossingsTable(wayid, ref, wayList)
                
    def parse(self, country):
        p = OSMParser(1, nodes_callback=self.parse_nodes, 
                  ways_callback=self.parse_ways, 
                  relations_callback=self.parse_relations,
                  coords_callback=self.parse_coords)
        p.parse(self.getOSMFile(country))

    def getOSMFile(self, country):
        return self.osmList[country]["osmFile"]
    
    def getDataDir(self):
        return os.path.join(os.environ['HOME'], "workspaces", "pydev", "car-dash", "data1")
    
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
        createEdgeDB=not self.edgeDBExists()
        if createEdgeDB:
            self.openEdgeDB()
            self.createEdgeTables()
        else:
            self.openEdgeDB()
#            self.edgeId=self.getLenOfEdgeTable()
        
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
                                    
            self.commitAdressDB()
            self.commitCountryDB(country)
            self.commitGlobalCountryDB()
            self.closeCoordsDB()
            
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
            print("create edge nodes")
            self.createEdgeTableNodeEntries()
            print("end create edge nodes")
            
            print("create way restrictions")
            self.createWayRestrictionsDB()              
            print("end create way restrictions")

            self.commitEdgeDB()    
                           
        self.initGraph()   
        self.closeAllDB()

    def initBoarders(self):
        self.bu=OSMBoarderUtils(self.getDataDir())
        self.bu.initData()
        
    def countryNameOfPoint(self, lat, lon):
        return self.bu.countryNameOfPoint(lat, lon)
    
    def getOSMDataInfo(self):
        osmDataList=dict()
        osmData=dict()
        osmData["country"]="austria"
        osmData["osmFile"]='/home/maxl/Downloads/austria.osm'
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
        osmData["country"]="germany"
        osmData["osmFile"]='/home/maxl/Downloads/bayern.osm'
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
    
    def getEdgeIdOnPos(self, lat, lon):        
        wayId, usedRefId, (usedLat, usedLon), country=self.getWayIdForPos(lat, lon)
        if wayId==None:
            return None
        
        resultList=self.getEdgeEntryForWayId(wayId)
        for result in resultList:
            edgeId, startRef, endRef, length, wayId, source, target, refList, cost, reverseCost=result
            if usedRefId in refList:
                return edgeId
        
        return None

    def test(self):
#        self.setDBCursorForCountry(0)
#        print("wayTable 0")
#        self.cursor.execute('SELECT * FROM wayTable where wayId==77458446 OR wayId==33073224')
#        allentries=self.cursor.fetchall()
#        for x in allentries:
#            print(self.wayFromDB(x))
#        
#        print("wayTable 2")
#        self.setDBCursorForCountry(2)
#        self.cursor.execute('SELECT * FROM wayTable where wayId==33073224 OR wayId==77458446')
#        allentries=self.cursor.fetchall()
#        for x in allentries:
#            print(self.wayFromDB(x))
#
#        print("wayCountrytable")
#        self.cursorCountry.execute('SELECT * FROM wayCountryTable where wayId==77458446 OR wayId==33073224')
#        allentries=self.cursorCountry.fetchall()
#        for x in allentries:
#            print(x)
#
#        print("refCountryTable")
#        self.cursorCountry.execute('SELECT * FROM refCountryTable where id==373118950 OR id==911691633  OR id==247649642')
#        allentries=self.cursorCountry.fetchall()
#        for x in allentries:
#            print(x)
#            
#        self.setDBCursorForCountry(0)
#        print("refTable 0")
#        self.cursor.execute('SELECT * FROM refTable where refId==373118950 OR refId==911691633 OR refId==247649642')
#        allentries=self.cursor.fetchall()
#        for x in allentries:
#            print(x)
#        
#        print("refTable 2")
#        self.setDBCursorForCountry(2)
#        self.cursor.execute('SELECT * FROM refTable where refId==373118950 OR refId==911691633 OR refId==247649642')
#        allentries=self.cursor.fetchall()
#        for x in allentries:
#            print(x)
            
        self.setDBCursorForCountry(0)
        print("wayTable 0")
        self.cursor.execute('SELECT * FROM wayTable where wayId==130888187 OR wayId==35062691 OR wayId==22751263 OR wayId==5097993 OR wayId==130888193 OR wayId==130888199')
        allentries=self.cursor.fetchall()
        for x in allentries:
            print(self.wayFromDB(x))
            print(self.getEdgeEntryForWayId(x[0]))

        
        print("wayTable 2")
        self.setDBCursorForCountry(2)
        self.cursor.execute('SELECT * FROM wayTable where wayId==130888187 OR wayId==35062691 OR wayId==22751263 OR wayId==5097993 OR wayId==130888193 OR wayId==130888199')
        allentries=self.cursor.fetchall()
        for x in allentries:
            print(self.wayFromDB(x))
            print(self.getEdgeEntryForWayId(x[0]))

            
#        print("edgeTable")
#        print(self.getEdgeEntryForWayId(77458446))
#        print(self.getEdgeEntryForWayId(33073224))

#        print(self.calcRouteForNodes(51377, 55365))
#        print(self.calcRouteForNodesTrsp(51377, 55365))
        
#        print(self.getEdgeEntryForEdgeId(100254))

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
#                (refGid, refId, lat, lon, wayId)=self.refFromDB(x)
                
        print("test wayTable")
        for country in self.osmList.keys():
            self.country=country
            print(country)
            self.setDBCursorForCountry(country)
            self.cursor.execute('SELECT * FROM wayTable')
            allentries=self.cursor.fetchall()
            for x in allentries:
                wayId, tags, refs, distances=self.wayFromDB(x)
                for ref in refs:
                    storedRef, storedCountry=self.getCountryOfRef(ref)
                    if storedRef==None:
                        print("way %d ref %d not in refCountryTable"%(wayId, ref))
                    elif storedCountry==None:
                        print("way %d ref %d country==None in refCountryTable"%(wayId, ref))
                    else:                              
                        resultList=self.getRefEntryForIdAndCountryAndWayId(ref, storedCountry, wayId)
                        if len(resultList)!=1:
                            print("way %d ref %d not in refTable of country %d"%(wayId, ref, storedCountry))
                            print(resultList)
                                    
                resultList=self.getEdgeEntryForWayId(wayId)
                if len(resultList)==0:
                    print("way %d not in edge DB"%(wayId))
                
                resultList=self.getCountrysOfWay(wayId)
                if len(resultList)==0:
                    print("way %d not in wayCountryTable"%(wayId))
                    
#        print("test edgeTable")
#        self.cursorEdge.execute('SELECT * FROM edgeTable')
#        allentries=self.cursorEdge.fetchall()
#        for x in allentries:
#            edgeId, startRef, endRef, length, wayId, source, target, refList, cost, reverseCost=self.edgeFromDB(x)
#            for ref in refList:
#                storedRef, storedCountry=self.getCountryOfRef(ref)
#                if storedRef==None:
#                    print("edge: way %d ref %d not in refCountryTable"%(wayId, ref))
#                elif storedCountry==None:
#                    print("edge: way %d ref %d in refCountryTable with country==None"%(wayId, ref))
#                else:  
#                    resultList=self.getRefEntryForIdAndCountryAndWayId(ref, storedCountry, wayId)
#                    if len(resultList)!=1:
#                        print("edge: way %d ref %d not in refTable of country %d"%(wayId, ref, storedCountry))
                
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
             
    def testAdress(self):
        self.cursorAdress.execute('SELECT * FROM addressTable WHERE country==0 AND city=="Salzburg" AND streetName=="Münchner Bundesstraße"')
        allentries=self.cursorAdress.fetchall()
        for x in allentries:
            print(self.addressFromDB(x))

    def createRefTableIndexes(self):
        for country in self.osmList.keys():
            self.country=country
            self.debugCountry=country
            print(self.osmList[country])
            self.setDBCursorForCountry(country)
            self.cursor.execute("CREATE INDEX refTableLat_idx ON refTable (lat)")
            self.cursor.execute("CREATE INDEX refTableLon_idx ON refTable (lon)")
            
def main(argv):    
    p = OSMParserData()
    
    p.initDB()
    
    p.openAllDB()
#    p.testCountryRefTable()
#    p.testCountryWayTable()
#    p.testStreetTable2()
#    p.testEdgeTable()
        

#    print(p.getLenOfEdgeTable())
#    print(p.getEdgeEntryForEdgeId(6719))
#    print(p.getEdgeEntryForEdgeId(2024))

#    p.test()
#    p.testDBConistency()
#    p.testRestrictionTable()
    p.recreateEdges()
#    p.recreateEdgeNodes()
#    p.createRefTableIndexes()

#    p.recreateCrossings()
#    p.testAdress()
    p.closeAllDB()


if __name__ == "__main__":
    main(sys.argv)  
    

