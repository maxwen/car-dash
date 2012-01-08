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
from osmparser.dijkstrapygraph import DijkstraWrapperPygraph
from osmparser.dijkstraigraph import DijkstraWrapperIgraph

from config import Config
from osmparser.osmboarderutils import OSMBoarderUtils
from shootingstar.shootingstarwrapper import ShootingStarWrapper

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
            
            (edgeId, _, _, _, _, wayId, source1, target1, refList, _, country)=result

            for edgeRef in refList:
                if edgeRef==usedRefId:
                    (self.lat, self.lon)=osmParserData.getCoordsWithRef(edgeRef)
                    self.edgeId=edgeId
                    self.target=target1
                    self.source=source1
                    self.usedRefId=edgeRef
                    self.wayId=wayId
                    self.country=country
                    targetFound=True
                    break
    
    def __repr__(self):
        return "%s %d %f %f"%(self.name, self.type, self.lat, self.lon)
    
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
        config.set(section, name, "%s:%d:%f:%f"%(self.name,self.type, self.lat,self.lon))
        
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
        self.edgeId=1
        self.edgeIdShootingStar=1
        self.trackItemList=list()
#        self.doneEdges=list()
#        self.edgeList=list()
        self.nodeId=1
        self.nodeIdShootingStar=1

        self.addressId=0
        self.dWrapper=None
        self.dWrapperShootingStar=None
        self.osmutils=OSMUtils()
        self.initBoarders()
        self.osmList=self.getOSMDataInfo()
        self.debugCountry=0
        self.wayCount=0
        
    def initCountryData(self):
        self.crossingId=0
        self.nodes = dict()
        self.coords = dict()
        self.relations = dict()
        self.streetNameIndex=dict()
        self.streetIndex=dict()
        self.wayRefIndex=dict()
#        self.wayToStreetIndex=dict()
        self.wayRestricitionListFrom=dict()
#        self.wayRestriction=dict()

    def createCountryTables(self):
        self.createRefTable()
        self.createWayTable()
#        self.createStreetTable()
        self.createCrossingsTable()

    def createEdgeTables(self):
        self.createEdgeTable()
        self.createEdgeTableShootingStar()
    
    def createGlobalCountryTables(self):
        self.createRefCountryTable()
        self.createNodeWayCountryTable()

    def createAdressTable(self):
#        self.createStreetTable()
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

    def closeCountryDB(self, country):
        cursor=self.osmList[country]["cursor"]
        connection=self.osmList[country]["connection"]
        connection.commit()
        cursor.close()
        self.osmList[country]["cursor"]=None
        self.osmList[country]["connection"]=None

    def closeEdgeDB(self):
        self.connectionEdge.commit()        
        self.cursorEdge.close()
        self.connectionEdge=None     
        self.cursorEdge=None
       
    def closeAdressDB(self):
        self.connectionAdress.commit()
        self.cursorAdress.close()
        self.connectionAdress=None
        self.cursorAdress=None
    
    def closeGlobalCountryDB(self):
        self.connectionCountry.commit()
        self.cursorCountry.close()
        self.connectionCountry=None
        self.cursorCountry=None
                
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
        if country!=self.debugCountry:
            print("switching cursor from %d to %d"%(self.debugCountry, country))
            
        self.connection=self.osmList[country]["connection"]
        self.cursor=self.osmList[country]["cursor"]
        self.debugCountry=country
      
    def getCountryForPolyCountry(self, polyCountry):
        for country, osmData in self.osmList.items():
            if osmData["polyCountry"]==polyCountry:
                return country
        return None
    
    def getCountryNameForIdCountry(self, country):
        return self.osmList[country]["country"]
    
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

    def createRefTable(self):
        self.cursor.execute('CREATE TABLE refTable (refId INTEGER PRIMARY KEY, lat REAL, lon REAL, ways BLOB)')
    
    def createWayTable(self):
        self.cursor.execute('CREATE TABLE wayTable (wayId INTEGER PRIMARY KEY, tags BLOB, refs BLOB, refsDistance BLOB)')

#    def createStreetTable(self):
#        self.cursorAdress.execute('CREATE TABLE streetTable (id INTEGER PRIMARY KEY, country INTEGER, name TEXT, ref TEXT, wayIdList BLOB)')
#    
    def createAddressTable(self):
        self.cursorAdress.execute('CREATE TABLE addressTable (id INTEGER PRIMARY KEY, refId INTEGER, country INTEGER, city TEXT, postCode INTEGER, streetName TEXT, houseNumber TEXT, lat REAL, lon REAL)')
        
    def addToAddressTable(self, refId, country, city, postCode, streetName, houseNumber, lat, lon):
        self.cursorAdress.execute('INSERT INTO addressTable VALUES( ?, ?, ?, ?, ?, ?, ?, ?, ?)', (self.addressId, refId, country, city, postCode, streetName, houseNumber, lat, lon))
        self.addressId=self.addressId+1

    def getAddressTableEntryWithRefId(self, refId):
        self.cursorAdress.execute('SELECT * FROM addressTable where refId=="%s"'%(refId))
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
        self.cursorAdress.execute('SELECT * FROM addressTable')
        allentries=self.cursorAdress.fetchall()
        return len(allentries)
    
    def createCrossingsTable(self):
        self.cursor.execute('CREATE TABLE crossingTable (id INTEGER PRIMARY KEY, wayId INTEGER, refId INTEGER, nextWayIdList BLOB)')
        self.cursor.execute("CREATE INDEX wayId_idx ON crossingTable (wayId)")
        self.cursor.execute("CREATE INDEX refId_idx ON crossingTable (refId)")

    def createEdgeTable(self):
        self.cursorEdge.execute('CREATE TABLE edgeTable (id INTEGER PRIMARY KEY, startRef INTEGER, endRef INTEGER, length INTEGER, oneway BOOL, wayId INTEGER, source INTEGER, target INTEGER, refList BLOB, maxspeed INTEGER, country INTEGER)')
        self.cursorEdge.execute("CREATE INDEX startRef_idx ON edgeTable (startRef)")
        self.cursorEdge.execute("CREATE INDEX endRef_idx ON edgeTable (endRef)")
        self.cursorEdge.execute("CREATE INDEX source_idx ON edgeTable (source)")
        self.cursorEdge.execute("CREATE INDEX target_idx ON edgeTable (target)")
        self.cursorEdge.execute("CREATE INDEX wayId_idx ON edgeTable (wayId)")

    def createEdgeTableShootingStar(self):
        self.cursorEdge.execute('CREATE TABLE edgeTableShootingStar (id INTEGER PRIMARY KEY, startRef INTEGER, endRef INTEGER, source INTEGER, target INTEGER, cost REAL, reverseCost REAL, x1 REAL, y1 REAL, x2 REAL, y2 REAL, toCost REAL, rule TEXT, wayId INTEGER)')
        self.cursorEdge.execute("CREATE INDEX startRefShootingStar_idx ON edgeTableShootingStar (startRef)")
        self.cursorEdge.execute("CREATE INDEX endRefShootingStar_idx ON edgeTableShootingStar (endRef)")
        self.cursorEdge.execute("CREATE INDEX sourceShootingStar_idx ON edgeTableShootingStar (source)")
        self.cursorEdge.execute("CREATE INDEX targetShootingStar_idx ON edgeTableShootingStar (target)")
        self.cursorEdge.execute("CREATE INDEX wayIdShootingStar_idx ON edgeTableShootingStar (wayId)")

    def createRefCountryTable(self):
        self.cursorCountry.execute('CREATE TABLE refCountryTable (id INTEGER PRIMARY KEY, country INTEGER)')
    
    def addToCountryRefTable(self, refId, country, lat, lon):
        storedRefId, storedCountry=self.getCountryOfRef(refId)
        if storedRefId!=None:
            None
#            polyCountry=self.countryNameOfPoint(lat, lon)
#            refCountry=self.getCountryForPolyCountry(polyCountry)
#            if refCountry!=storedCountry:
#                print("refid %d stored with country %d but belongs to country %d"%(storedRefId, storedCountry, refCountry))
        else:
            polyCountry=self.countryNameOfPoint(lat, lon)
            refCountry=self.getCountryForPolyCountry(polyCountry)
            if refCountry!=None:
                self.cursorCountry.execute('INSERT INTO refCountryTable VALUES( ?, ?)', (refId, refCountry))
#            else:
#                print("cannot resolve country for ref %d"%(refId))
                
#        storedRefId, storedCountry=self.getCountryOfRef(refId)
#        if storedRefId==None:
#            self.cursorEdge.execute('INSERT INTO refCountryTable VALUES( ?, ?)', (refId, country))
#        else:
#            polyCountry=self.countryNameOfPoint(lat, lon)
#            refCountry=self.getCountryForPolyCountry(polyCountry)
#            if refCountry!=None:
#                if refCountry!=storedCountry:
##                    print("refid %d stored with country %d"%(storedRefId, storedCountry))
##                    print("but belongs to country %d"%(refCountry))
#                    self.cursorEdge.execute('REPLACE INTO refCountryTable VALUES( ?, ?)', (refId, country))
                    
    def getCountryOfRef(self, refId):
        self.cursorCountry.execute('SELECT id, country FROM refCountryTable where id=="%s"'%(str(refId)))
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

    def addToCountryWayTable(self, wayId, country, refs):
        resultList=self.getCountrysOfWay(wayId)
        if len(resultList)!=0:
            None
#            refId, startRefCountry=self.getCountryOfRef(refs[0])
#            refId, endRefCountry=self.getCountryOfRef(refs[-1])
#
#            for result in resultList:
#                storedWayCountId, storedWayId, storedCountry=result
#                if storedCountry!=startRefCountry and startRefCountry!=endRefCountry:
#                    print("way %d was stored with country %d but start and end are in %d"%(wayId, storedCountry, startRefCountry))
        else:
            refId, startRefCountry=self.getCountryOfRef(refs[0])
            refId, endRefCountry=self.getCountryOfRef(refs[-1])
            if startRefCountry==endRefCountry:
                self.cursorCountry.execute('INSERT INTO wayCountryTable VALUES( ?, ?, ?)', (self.wayCount, wayId, startRefCountry))
                self.wayCount=self.wayCount+1
            else:
                self.cursorCountry.execute('INSERT INTO wayCountryTable VALUES( ?, ?, ?)', (self.wayCount, wayId, startRefCountry))
                self.wayCount=self.wayCount+1
                self.cursorCountry.execute('INSERT INTO wayCountryTable VALUES( ?, ?, ?)', (self.wayCount, wayId, endRefCountry))
                self.wayCount=self.wayCount+1

#        resultList=self.getCountrysOfWay(wayId)
#        if len(resultList)==0:
#            self.cursorEdge.execute('INSERT INTO wayCountryTable VALUES( ?, ?, ?)', (self.wayCount, wayId, country))
#            self.wayCount=self.wayCount+1
#        else:
#            for result in resultList:
#                storedWayCountId, storedWayId, storedCountry=result
#                refId, startRefCountry=self.getCountryOfRef(refs[0])
#                refId, endRefCountry=self.getCountryOfRef(refs[-1])
#                if startRefCountry==endRefCountry:
#                    if startRefCountry!=None and storedCountry!=startRefCountry:
#                        print("way %d was stored with country %d but start and end are in %d"%(wayId, storedCountry, startRefCountry))
#                        self.cursorEdge.execute('REPLACE INTO wayCountryTable VALUES( ?, ?, ?)', (storedWayCountId, wayId, startRefCountry))
#                else:
#                    self.cursorEdge.execute('INSERT INTO wayCountryTable VALUES( ?, ?, ?)', (self.wayCount, wayId, country))
#                    self.wayCount=self.wayCount+1
        
    def getCountrysOfWay(self, wayId):
        self.cursorCountry.execute('SELECT id, wayId, country FROM wayCountryTable where wayId=="%s"'%(str(wayId)))
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
            storedWayCountId, storedWayId, storedCountry=result
            if storedCountry==country:
                return True

        return False
    
    def testCountryWayTable(self):
        self.cursorCountry.execute('SELECT * FROM wayCountryTable')
        allentries=self.cursorCountry.fetchall()
        for x in allentries:
            print( "id: "+x[0]+ "wayId: "+str(x[1]) +" country: " + x[2])

    def getLenOfCountryWayTable(self):
        self.cursorCountry.execute('SELECT * FROM wayCountryTable')
        allentries=self.cursorCountry.fetchall()
        return len(allentries)

    def addToRefTable(self, refid, lat, lon, wayIdList):
        self.setDBCursorForCountry(self.country)
        self.cursor.execute('INSERT INTO refTable VALUES( ?, ?, ?, ?)', (refid, lat, lon, pickle.dumps(wayIdList)))

    def addToWayTable(self, wayid, tags, refs, distances):
        self.setDBCursorForCountry(self.country)
        self.cursor.execute('INSERT INTO wayTable VALUES( ?, ?, ?, ?)', (wayid, pickle.dumps(tags), pickle.dumps(refs), pickle.dumps(distances)))

    def getStreetEntryForNameAndCountry(self, streetInfo, country):
        (name, ref)=streetInfo
        self.cursorAdress.execute('SELECT * FROM addressTable where streetName=="%s" and country=="%s"'%(str(name), str(country)))
        allentries=self.cursorAdress.fetchall()
        resultList=list()
        for x in allentries:
            resultList.append(self.addressFromDB(x))
        
        return resultList
    
#    def addToStreetTable(self, country, streetInfo, wayidList):
#        (name, ref)=streetInfo
#        resultList=self.getStreetEntryForNameAndCountry(streetInfo, country)
#        if len(resultList)==0:
#            self.cursorAdress.execute('INSERT INTO streetTable VALUES( ?, ?, ?, ?, ?)', (self.streetId, country, name, ref, pickle.dumps(wayidList)))
#            self.streetId=self.streetId+1
        
#    def getLenOfStreetTable(self):
#        self.cursorAdress.execute('SELECT * FROM streetTable')
#        allentries=self.cursorAdress.fetchall()
#        return len(allentries)
 
    def addToCrossingsTable(self, wayid, refId, nextWaysList):
        self.setDBCursorForCountry(self.country)
        self.cursor.execute('INSERT INTO crossingTable VALUES( ?, ?, ?, ?)', (self.crossingId, wayid, refId, pickle.dumps(nextWaysList)))
        self.crossingId=self.crossingId+1

    def addToEdgeTable(self, startRef, endRef, length, oneway, wayId, refList, maxspeed, country):
        resultList=self.getEdgeEntryForStartAndEndPoint(startRef, endRef)
        if len(resultList)==0:
            self.cursorEdge.execute('INSERT INTO edgeTable VALUES( ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (self.edgeId, startRef, endRef, length, oneway, wayId, 0, 0, pickle.dumps(refList), maxspeed, country))
            self.edgeId=self.edgeId+1
    
    def addToEdgeTableShootingStar(self, startRef, endRef, source, target, cost, reverseCost, x1, y1, x2, y2, toCost, rule, wayId):
        resultList=self.getEdgeEntryForStartAndEndPointShootingStar(startRef, endRef)
        if len(resultList)==0:
            self.cursorEdge.execute('INSERT INTO edgeTableShootingStar VALUES( ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (self.edgeIdShootingStar, startRef, endRef, source, target, cost, reverseCost, x1, y1, x2, y2, toCost, rule, wayId))
            self.edgeIdShootingStar=self.edgeIdShootingStar+1

    def getLenOfEdgeTable(self):
        self.cursorEdge.execute('SELECT * FROM edgeTable')
        allentries=self.cursorEdge.fetchall()
        return len(allentries)
    
    def getLenOfEdgeTableShootingStar(self):
        self.cursorEdge.execute('SELECT * FROM edgeTableShootingStar')
        allentries=self.cursorEdge.fetchall()
        return len(allentries)
    
    def updateSourceOfEdge(self, edgeId, sourceId):
        existingEdgeId, startRef, endRef, length, oneway, wayId, _, target, refList, maxspeed, country=self.getEdgeEntryForEdgeId(edgeId)
        if existingEdgeId==None:
            print("no edge with id %d"%(edgeId))
            return
        self.cursorEdge.execute('REPLACE INTO edgeTable VALUES( ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (edgeId, startRef, endRef, length, oneway, wayId, sourceId, target, pickle.dumps(refList), maxspeed, country))

    def updateTargetOfEdge(self, edgeId, targetId):
        existingEdgeId, startRef, endRef, length, oneway, wayId, source, _, refList, maxspeed, country=self.getEdgeEntryForEdgeId(edgeId)
        if existingEdgeId==None:
            print("no edge with id %d"%(edgeId))
            return
        self.cursorEdge.execute('REPLACE INTO edgeTable VALUES( ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (edgeId, startRef, endRef, length, oneway, wayId, source, targetId, pickle.dumps(refList), maxspeed, country))     
    
    def updateRuleOfEdgeShootingStar(self, edgeId, rule):
        existingEdgeId, startRef, endRef, source, target, cost, reverseCost, x1, y1, x2, y2, toCost, existingRule, wayId=self.getEdgeEntryForEdgeIdShootingStar(edgeId)
        if existingEdgeId==None:
            print("no edge with id %d"%(edgeId))
            return
        self.cursorEdge.execute('REPLACE INTO edgeTableShootingStar VALUES( ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (edgeId, startRef, endRef, source, target, cost, reverseCost, x1, y1, x2, y2, 10000, rule, wayId))

    def updateSourceOfEdgeShootingStar(self, edgeId, sourceId):
        existingEdgeId, startRef, endRef, source, target, cost, reverseCost, x1, y1, x2, y2, toCost, rule, wayId=self.getEdgeEntryForEdgeIdShootingStar(edgeId)
        if existingEdgeId==None:
            print("no edge with id %d"%(edgeId))
            return
        self.cursorEdge.execute('REPLACE INTO edgeTableShootingStar VALUES( ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (edgeId, startRef, endRef, sourceId, target, cost, reverseCost, x1, y1, x2, y2, toCost, rule, wayId))

    def updateTargetOfEdgeShootingStar(self, edgeId, targetId):
        existingEdgeId, startRef, endRef, source, target, cost, reverseCost, x1, y1, x2, y2, toCost, rule, wayId=self.getEdgeEntryForEdgeIdShootingStar(edgeId)
        if existingEdgeId==None:
            print("no edge with id %d"%(edgeId))
            return
        self.cursorEdge.execute('REPLACE INTO edgeTableShootingStar VALUES( ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (edgeId, startRef, endRef, source, targetId, cost, reverseCost, x1, y1, x2, y2, toCost, rule, wayId))
  
    def clearSourceAndTargetOfEdges(self):
        self.cursorEdge.execute('SELECT * FROM edgeTable')
        allentries=self.cursorEdge.fetchall()
        for x in allentries:
            edgeId, startRef, endRef, length, oneway, wayId, source, target, refList, maxspeed, country=self.edgeFromDB(x)
            self.updateSourceOfEdge(edgeId, 0)
            self.updateTargetOfEdge(edgeId, 0)

    def clearSourceAndTargetOfEdgesShootingStar(self):
        self.cursorEdge.execute('SELECT * FROM edgeTableShootingStar')
        allentries=self.cursorEdge.fetchall()
        for x in allentries:
            edgeId, startRef, endRef, source, target, cost, reverseCost, x1, y1, x2, y2, toCost, rule, wayId=self.edgeFromDBShootingStar(x)
            self.updateSourceOfEdgeShootingStar(edgeId, 0)
            self.updateTargetOfEdgeShootingStar(edgeId, 0)

    def getEdgeEntryForSource(self, sourceId):
        self.cursorEdge.execute('SELECT * FROM edgeTable where source=="%s"'%(str(sourceId)))
        resultList=list()
        allentries=self.cursorEdge.fetchall()
        for result in allentries:
            edge=self.edgeFromDB(result)
            resultList.append(edge)
        return resultList      
    
    def getEdgeEntryForTarget(self, targetId):
        self.cursorEdge.execute('SELECT * FROM edgeTable where target=="%s"'%(str(targetId)))
        resultList=list()
        allentries=self.cursorEdge.fetchall()
        for result in allentries:
            edge=self.edgeFromDB(result)
            resultList.append(edge)
        return resultList      
    
    def getEdgeEntryForSourceAndTarget(self, sourceId, targetId):
        self.cursorEdge.execute('SELECT * FROM edgeTable where source=="%s" AND target=="%s"'%(str(sourceId), str(targetId)))
        resultList=list()
        allentries=self.cursorEdge.fetchall()
        for result in allentries:
            edge=self.edgeFromDB(result)
            resultList.append(edge)
        return resultList   

    def getEdgeEntryForSourceShootingStar(self, sourceId):
        self.cursorEdge.execute('SELECT * FROM edgeTableShootingStar where source=="%s"'%(str(sourceId)))
        resultList=list()
        allentries=self.cursorEdge.fetchall()
        for result in allentries:
            edge=self.edgeFromDBShootingStar(result)
            resultList.append(edge)
        return resultList      
    
    def getEdgeEntryForTargetShootingStar(self, targetId):
        self.cursorEdge.execute('SELECT * FROM edgeTableShootingStar where target=="%s"'%(str(targetId)))
        resultList=list()
        allentries=self.cursorEdge.fetchall()
        for result in allentries:
            edge=self.edgeFromDBShootingStar(result)
            resultList.append(edge)
        return resultList      
    
    def getEdgeEntryForSourceAndTargetShootingStar(self, sourceId, targetId):
        self.cursorEdge.execute('SELECT * FROM edgeTableShootingStar where source=="%s" AND target=="%s"'%(str(sourceId), str(targetId)))
        resultList=list()
        allentries=self.cursorEdge.fetchall()
        for result in allentries:
            edge=self.edgeFromDBShootingStar(result)
            resultList.append(edge)
        return resultList   
    
    def getEdgeEntryForEdgeId(self, edgeId):
        self.cursorEdge.execute('SELECT * FROM edgeTable where id=="%s"'%(str(edgeId)))
        allentries=self.cursorEdge.fetchall()
        if len(allentries)==1:
            edge=self.edgeFromDB(allentries[0])
            return edge
        print("no edge with %d"%(edgeId))
        return (None, None, None, None, None, None, None, None, None, None, None)

    def getEdgeEntryForEdgeIdShootingStar(self, edgeId):
        self.cursorEdge.execute('SELECT * FROM edgeTableShootingStar where id=="%s"'%(str(edgeId)))
        allentries=self.cursorEdge.fetchall()
        if len(allentries)==1:
            edge=self.edgeFromDBShootingStar(allentries[0])
            return edge
        print("no edge with %d"%(edgeId))
        return (None, None, None, None, None, None, None, None, None, None, None, None, None)
        
    def getEdgeEntryForStartPoint(self, startRef, edgeId):
        self.cursorEdge.execute('SELECT * FROM edgeTable where startRef="%s" AND id!="%s"'%(str(startRef), str(edgeId)))
        resultList=list()
        allentries=self.cursorEdge.fetchall()
        for result in allentries:
            edge=self.edgeFromDB(result)
            resultList.append(edge)
        return resultList
 
    def getEdgeEntryForEndPoint(self, endRef, edgeId):
        self.cursorEdge.execute('SELECT * FROM edgeTable where endRef=="%s" AND id!="%s"'%(str(endRef), str(edgeId)))
        resultList=list()
        allentries=self.cursorEdge.fetchall()
        for result in allentries:
            edge=self.edgeFromDB(result)
            resultList.append(edge)
        return resultList
    
    def getEdgeEntryForStartAndEndPoint(self, startRef, endRef):
        self.cursorEdge.execute('SELECT * FROM edgeTable where startRef=="%s" AND endRef=="%s"'%(str(startRef), str(endRef)))
        resultList=list()
        allentries=self.cursorEdge.fetchall()
        for result in allentries:
            edge=self.edgeFromDB(result)
            resultList.append(edge)
        return resultList

    def getEdgeEntryForStartPointShootingStar(self, startRef, edgeId):
        self.cursorEdge.execute('SELECT * FROM edgeTableShootingStar where startRef="%s" AND id!="%s"'%(str(startRef), str(edgeId)))
        resultList=list()
        allentries=self.cursorEdge.fetchall()
        for result in allentries:
            edge=self.edgeFromDBShootingStar(result)
            resultList.append(edge)
        return resultList
 
    def getEdgeEntryForEndPointShootingStar(self, endRef, edgeId):
        self.cursorEdge.execute('SELECT * FROM edgeTableShootingStar where endRef=="%s" AND id!="%s"'%(str(endRef), str(edgeId)))
        resultList=list()
        allentries=self.cursorEdge.fetchall()
        for result in allentries:
            edge=self.edgeFromDBShootingStar(result)
            resultList.append(edge)
        return resultList    
    
    def getEdgeEntryForStartAndEndPointShootingStar(self, startRef, endRef):
        self.cursorEdge.execute('SELECT * FROM edgeTableShootingStar where startRef=="%s" AND endRef=="%s"'%(str(startRef), str(endRef)))
        resultList=list()
        allentries=self.cursorEdge.fetchall()
        for result in allentries:
            edge=self.edgeFromDBShootingStar(result)
            resultList.append(edge)
        return resultList

    def getEdgeEntryForWayId(self, wayId):
        self.cursorEdge.execute('SELECT * FROM edgeTable where wayId=="%s"'%(str(wayId)))
        resultList=list()
        allentries=self.cursorEdge.fetchall()
        for result in allentries:
            edge=self.edgeFromDB(result)
            resultList.append(edge)
        return resultList

    def getEdgeEntryForWayIdShootingStar(self, wayId):
        self.cursorEdge.execute('SELECT * FROM edgeTableShootingStar where wayId=="%s"'%(str(wayId)))
        resultList=list()
        allentries=self.cursorEdge.fetchall()
        for result in allentries:
            edge=self.edgeFromDBShootingStar(result)
            resultList.append(edge)
        return resultList    
    
    def getRefEntryForId(self, refId):
        refId, country=self.getCountryOfRef(refId)
        if refId==None:
            return (None, None, None, None)
        self.setDBCursorForCountry(country)
        self.cursor.execute('SELECT * FROM refTable where refId==%s'%(str(refId)))
        allentries=self.cursor.fetchall()
        if len(allentries)==1:
            return self.refFromDB(allentries[0])
        
        return (None, None, None, None)

    def getWayEntryForId(self, wayId):
        resultList=self.getCountrysOfWay(wayId)
        if len(resultList)==0:
            return (None, None, None, None)
        
        country=resultList[0][2]
        return self.getWayEntryForIdAndCountry(wayId, country)
    
    def getWayEntryForIdAndCountry(self, wayId, country):
        self.setDBCursorForCountry(country)
        self.cursor.execute('SELECT * FROM wayTable where wayId==%s'%(str(wayId)))
        allentries=self.cursor.fetchall()
        if len(allentries)==1:
            return self.wayFromDB(allentries[0])
        
        return (None, None, None, None)
    
    def getCrossingEntryFor(self, wayid, country):
        self.setDBCursorForCountry(country)
        self.cursor.execute('SELECT * FROM crossingTable where wayId=="%s"'%(str(wayid)))      
        resultList=list()
        allentries=self.cursor.fetchall()
        for result in allentries:
            crossing=self.crossingFromDB(result)
            resultList.append(crossing)
            
        return resultList
    
    def getCrossingEntryForRefId(self, wayid, refId, country):
        self.setDBCursorForCountry(country)
        self.cursor.execute('SELECT * FROM crossingTable where wayId=="%s" AND refId=="%s"'%(str(wayid), str(refId)))  
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
            refId, lat, lon, wayIdList=self.refFromDB(x)
            print( "ref: " + str(refId) + "  lat: " + str(lat) + "  lon: " + str(lon) + " ways:"+str(wayIdList))
         

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

        nodes=self.getNearNodes(actlat, actlon, country)
        minDistance=1000
        minWayId=0
        usedRefId=0
        if len(nodes)==0:
            return None, None, (None, None), None
        
        for (refId, lat, lon, wayIdList) in nodes:  
            (revLat, revLon)=self.getCoordsWithRef(refId)
 
            for wayId in wayIdList:
                # find matching way by creating interpolation points betwwen refs
                (wayId, tags, refs, _)=self.getWayEntryForIdAndCountry(wayId, country)
                if wayId==None:
                    continue
                
                (prevRefId, nextRefId)=self.getPrevAndNextRefForWay(refId, wayId, tags, refs)
                if prevRefId!=None and nextRefId!=None:
                    (prevLat, prevLon)=self.getCoordsWithRef(prevRefId)
                    (nextLat, nextLon)=self.getCoordsWithRef(nextRefId)
                    
                    if prevRefId==None or prevLon==None or nextLon==None or nextLat==None:
                        continue
                    
                    tempPoints=self.createTemporaryPoint(lat, lon, prevLat, prevLon)                    
                    for (tmpLat, tmpLon) in tempPoints:
                        distance=int(self.osmutils.distance(actlat, actlon, tmpLat, tmpLon))

                        if distance < minDistance:
                            minDistance=distance
                            minWayId=wayId
                            distanceRef=int(self.osmutils.distance(actlat, actlon, revLat, revLon))
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
                            distanceRef=int(self.osmutils.distance(actlat, actlon, revLat, revLon))
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
        latRangeMax=lat+0.003
        lonRangeMax=lon+0.003
        latRangeMin=lat-0.003
        lonRangeMin=lon-0.003
        
        nodes=list()
        self.setDBCursorForCountry(country)
        self.cursor.execute('SELECT * FROM refTable where lat>%s AND lat<%s AND lon>%s AND lon<%s'%(latRangeMin, latRangeMax, lonRangeMin, lonRangeMax))
        allentries=self.cursor.fetchall()
        for x in allentries:
            refId, lat1, lon1, wayIdList=self.refFromDB(x)
            distance=self.osmutils.distance(lat, lon, lat1, lon1)
            if distance>1000:
                continue
            nodes.append((refId, lat1, lon1, wayIdList))

        return nodes
    
    def testWayTable(self, country):
        self.setDBCursorForCountry(country)

        self.cursor.execute('SELECT * FROM wayTable')
        allentries=self.cursor.fetchall()
        for x in allentries:
            wayId, tags, refs, distances=self.wayFromDB(x)
            print( "way: " + str(wayId) + "  tags: " + str(tags) + "  refs: " + str(refs) + " distances: "+str(distances))

#    def testStreetTable(self):
#        self.cursorAdress.execute('SELECT * FROM streetTable')
#        allentries=self.cursorAdress.fetchall()
#        for x in allentries:
#            streetId, country, streetInfo, wayIdList=self.streetFromDB(x)
#            print( "id:"+str(streetId) +" country: "+str(country)+" streetInfo: " + str(streetInfo) + " wayIdList: " + str(wayIdList))

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
            edgeId, startRef, endRef, length, oneway, wayId, source, target, refList, maxspeed, country=self.edgeFromDB(x)
            print( "edgeId: "+str(edgeId) +" startRef: " + str(startRef)+" endRef:"+str(endRef)+ " length:"+str(length)+ " oneway: "+str(oneway)+ " wayId:"+str(wayId) +" source:"+str(source)+" target:"+str(target) +" refList:"+str(refList) + " maxspeed:"+str(maxspeed) + " country:"+str(country))

    def testEdgeTableShootingStar(self):
        self.cursorEdge.execute('SELECT * FROM edgeTableShootingStar')
        allentries=self.cursorEdge.fetchall()
        for x in allentries:
            edgeId, startRef, endRef, source, target, cost, reverseCost, x1, y1, x2, y2, toCost, rule, wayId=self.edgeFromDBShootingStar(x)
            print( "edgeId: "+str(edgeId) +" startRef: " + str(startRef)+" endRef:"+str(endRef)+ " source:"+str(source)+ " target: "+str(target)+ " cost:"+str(cost) +" reverseCost:"+str(reverseCost)+" x1:"+str(x1) +" y1:"+str(y1) + " x2:"+str(x2) + " y2:"+str(y2) + " toCost:"+str(toCost)+ " rule:"+str(rule) + " wayId:"+str(wayId))

    def testEdgeTableShootingStar2(self):
        self.cursorEdge.execute("SELECT id, source, target, cost, reverseCost, x1, y1, x2, y2, toCost, rule FROM edgeTableShootingStar")
        allentries=self.cursorEdge.fetchall()
        for x in allentries:
            print(x)
            
    def wayFromDB(self, x):
        wayId=x[0]
        refs=pickle.loads(x[2])
        tags=pickle.loads(x[1])
        distances=pickle.loads(x[3])
        return (wayId, tags, refs, distances)
    
    def refFromDB(self, x):
        wayIdList=pickle.loads(x[3])
        lat=x[1]
        lon=x[2]
        refId=x[0]
        return (refId, lat, lon, wayIdList)

#    def streetFromDB(self, x):
#        streetId=x[0]
#        country=x[1]
#        name=x[2]
#        ref=x[3]
#        wayIdList=pickle.loads(x[4])
#        return (streetId, country, (name, ref), wayIdList)
        
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
        oneway=x[4]
        wayId=x[5]     
        source=x[6]
        target=x[7]
        refList=pickle.loads(x[8])
        maxspeed=x[9]
        country=x[10]
        return (edgeId, startRef, endRef, length, oneway, wayId, source, target, refList, maxspeed, country)

    def edgeFromDBShootingStar(self, x):
        edgeId=x[0]
        startRef=x[1]
        endRef=x[2]
        source=x[3]
        target=x[4]
        cost=x[5]     
        reverseCost=x[6]
        x1=x[7]
        y1=x[8]
        x2=x[9]
        y2=x[10]
        toCost=x[11]
        rule=x[12]
        wayId=x[13]
        return (edgeId, startRef, endRef, source, target, cost, reverseCost, x1, y1, x2, y2, toCost, rule, wayId)
        
    def addAllRefsToDB(self):
        for ref, wayIdList in self.wayRefIndex.items():
            try:
                lat=self.coords[ref][0]
                lon=self.coords[ref][1]
            except KeyError:
                continue
            self.addToRefTable(ref, lat, lon, wayIdList)
            self.addToCountryRefTable(ref, self.country, lat, lon)

    def addWayRefsToDB(self):
        self.setDBCursorForCountry(self.country)
        self.cursor.execute('SELECT * FROM wayTable')
        allWays=self.cursor.fetchall()
        
        for way in allWays:
            wayId, _, refs, _=self.wayFromDB(way)
            self.addToCountryWayTable(wayId, self.country, refs)

    def locationToGridIndex(self, lat, lon):
        normLat=lat+180.0
        normLon=lon+180.0
        
        xIndex=int((normLat*1000)/36)
        yIndex=int((normLon*1000)/36)
        
        return (xIndex, yIndex)
    
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
            self.coords[int(osmid)]=(float(lat), float(lon))
              
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
            if "building" in tags:
                if refs[0] in self.coords:
                    (lat, lon)=self.coords[refs[0]]
                    if lat!=None and lon!=None:
                        self.parseAddress(tags, refs[0], lat, lon)

            if "highway" in tags:
                streetType=tags["highway"]
                if streetType=="services" or streetType=="bridleway" or streetType=="path" or streetType=="track" or streetType=="footway" or streetType=="pedestrian" or streetType=="cycleway" or streetType=="service" or streetType=="living_street" or streetType=="steps" or streetType=="platform" or streetType=="crossing" or streetType=="raceway":
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
                
                if "acccess" in tags:
                    if tags["access"]=="private":
                        continue
                    if tags["access"]=="destination":
                        continue

                
                if "area" in tags:
                    if tags["area"]=="yes":
                        continue
                if "building" in tags:
                    if tags["building"]=="yes":
                        continue
                distances=list()
    
                if len(refs)==1:
                    print("way with len(ref)==1 %d"%(wayid))
                    
                startRef=refs[0]
                if startRef in self.coords:
                    (lat, lon)=self.coords[startRef]
                else:
                    lat=0.0
                    lon=0.0
                           
                for ref in refs:  
                    if ref!=startRef:
                        if ref in self.coords:
                            (lat1, lon1)=self.coords[ref]
                            if lat==0.0 and lon==0.0:
                                lat=lat1
                                lon=lon1
                            distance=int(self.osmutils.distance(lat, lon, lat1, lon1))
                            distances.append(distance)
                            lat=lat1
                            lon=lon1
                        else:
                            distances.append(0)
                    else:
                        distances.append(0)
                        
                    wayRefList=list()
                    if ref in self.wayRefIndex:
                        wayRefList=self.wayRefIndex[ref]
            
                    if not wayid in wayRefList:
                        wayRefList.append(wayid)
                    self.wayRefIndex[ref]=wayRefList     
                        
                self.addToWayTable(wayid, tags, refs, distances)

#    def collectWaysByName(self):
#        self.setDBCursorForCountry(self.country)
#        self.cursor.execute('SELECT * FROM wayTable')
#        allWays=self.cursor.fetchall()
#        
#        street_by_name=dict()
#
#        for way in allWays:
#            wayId, tags, _, _=self.wayFromDB(way)
#            if not self.isWayInCountry(wayId, self.country):
#                continue
#                
#            if "highway" in tags:
#                streetType=tags["highway"]
#                if streetType[-5:]=="_link":
#                    continue
#                
#            if "name" in tags or "ref" in tags:
#                (name, ref)=self.getStreetNameInfo(tags)
#                if name=="" and ref=="":
#                    print("cannot create indexname for "+str(tags))
#                    continue
#
#
##                    if ref!="A1" and name!="Münchner Bundesstraße":
##                        continue
#                
#                if not (name, ref) in street_by_name.keys():
#                    wayIdList=list()
#                    wayIdList.append(wayId)
#                    street_by_name[(name, ref)]=wayIdList
#                else:
#                    wayIdList=street_by_name[(name, ref)]
#                    wayIdList.append(wayId)
#
#        for name, ref in street_by_name.keys():
#            wayIdList=street_by_name[(name, ref)]
#            self.addToStreetTable(self.country, (name, ref), wayIdList)
        
    def parse_relations(self, relation):
        for osmid, tags, ways in relation:
            if "type" in tags:     
                if tags["type"]=="restriction":
                    if "restriction" in tags:
#                        print(tags)
#                        print(ways)
                        
#                        self.relations[osmid]=(tags, ways)
                        restrictionType=tags["restriction"]
                        
                        isWay=False
                        fromWayId=None
                        toWayId=None
                        viaNode=None
    
                        for part in ways:
                            wayId=part[0]
                            type=part[1]
                            role=part[2]
    
                            if type=="way":
                                isWay=True
                            elif type=="node":
                                isNode=True
                            if role=="from":
                                fromWayId=wayId
                            elif role=="to":
                                toWayId=wayId
                            elif role=="via":
                                viaNode=wayId
                        if isWay:
                            restrictionEntry=dict()
                            restrictionEntry["type"]=restrictionType
                            restrictionEntry["to"]=toWayId
                            restrictionEntry["from"]=fromWayId
                            if viaNode!=None:
                                restrictionEntry["via"]=viaNode
                            
                            restrictionList=list()
                            if fromWayId in self.wayRestricitionListFrom:
                                restrictionList=self.wayRestricitionListFrom[fromWayId]
                            restrictionList.append(restrictionEntry)
                            self.wayRestricitionListFrom[fromWayId]=restrictionList
                        
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
        elif streetType=="trunk":
            if ref!="":
                ref=ref.replace(' ', '')
                if name=="":
                    name=ref  
        elif streetType=="unclassified":
            None

        return (name, ref)
    
    def getWaysWithRef(self, ref):
        (refId, _, _, wayIdList)=self.getRefEntryForId(ref)
        if refId!=None:
            return wayIdList
        
        return None

    def getStreetInfoWithWayId(self, wayId, country):
        (streetEntryId, tags, _, _)=self.getWayEntryForIdAndCountry(wayId, country)
        if streetEntryId!=None:
            (name, ref)=self.getStreetNameInfo(tags)
            return (name, ref)
        return (None, None)
        
    def getCoordsWithRef(self, ref):
        (refId, lat, lon, _)=self.getRefEntryForId(ref)
        if refId!=None:
            return (lat, lon)
        
        return (None, None)
    
    def findWayWithRefInAllWays(self, refId, fromWayId):
        possibleWays=list()
        wayIdList=self.getWaysWithRef(refId)
        if wayIdList==None:
            return possibleWays
        
        refId, country=self.getCountryOfRef(refId)
        for wayid in wayIdList:
            if wayid==fromWayId:
                continue
            
            (wayEntryId, tags, refs, _)=self.getWayEntryForIdAndCountry(wayid, country)
            if wayEntryId==None:
                print("no entry in way DB for "+str(wayid))
                continue
            
            for wayRef in refs:
                if wayRef==refId:
                    possibleWays.append((wayid, tags, refs))
 
        return possibleWays
    
    def findWayWithEndRef(self, ways, endRef, country):
        possibleWays=list()
        for wayId  in ways:
            (actWayId, tags, refs, distances)=self.getWayEntryForIdAndCountry(wayId, country)
            if refs[-1]==endRef:
                possibleWays.append(actWayId)
        return possibleWays
    
    def findStartWay(self, ways, country):
        for wayId  in ways:
            (actWayId, tags, refs, distances)=self.getWayEntryForIdAndCountry(wayId, country)
            startRef=refs[0]
            possibleWays=self.findWayWithEndRef(ways, startRef, country)
            if len(possibleWays)==0:
                return actWayId
        return ways[0]
                 
    def getStreetList(self):
        self.cursorAdress.execute('SELECT * FROM streetTable')
        allentries=self.cursorAdress.fetchall()
        streetList=list()
        for x in allentries:
            streetList.append(self.streetFromDB(x))

        return streetList
    
    def getAddressList(self):
        self.cursorAdress.execute('SELECT * FROM addressTable')
        allentries=self.cursorAdress.fetchall()
        streetList=list()
        for x in allentries:
            streetList.append(self.addressFromDB(x))
        return streetList
    
    def getAddressListForCountry(self, country):
        self.cursorAdress.execute('SELECT * FROM addressTable WHERE country=="%s"'%str(country))
        allentries=self.cursorAdress.fetchall()
        streetList=list()
        for x in allentries:
            streetList.append(self.addressFromDB(x))
        return streetList
    
    def getAddressListForCity(self, city):
        self.cursorAdress.execute('SELECT * FROM addressTable WHERE city=="%s"'%str(city))
        allentries=self.cursorAdress.fetchall()
        streetList=list()
        for x in allentries:
            streetList.append(self.addressFromDB(x))
        return streetList
    
    def getAddressListForPostCode(self, postCode):
        self.cursorAdress.execute('SELECT * FROM addressTable WHERE postCode=="%s"'%str(postCode))
        allentries=self.cursorAdress.fetchall()
        streetList=list()
        for x in allentries:
            streetList.append(self.addressFromDB(x))
        return streetList
    
#    def getTrackListByName(self, name, ref):
#        if not (name, ref) in self.streetNameIndex.keys():
#            self.postprocessWay(name, ref)
#        
#        trackList=list()
#        if (name, ref) in self.streetNameIndex.keys():
#            tracks=self.streetNameIndex[(name, ref)]
#            for track in tracks:
#                trackList.append(self.streetIndex[track])
#            
#        return trackList
                
    def createStartTrackItem(self):
        streetTrackItem=dict()
        streetTrackItem["start"]="start"
        return streetTrackItem
    
    def createEndTrackItem(self):
        streetTrackItem=dict()
        streetTrackItem["end"]="end"
        return streetTrackItem

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
                            
                print("%d %d %d"%(source, startPoint.getWayId(), startPoint.getRefId()))
                print("%d %d %d"%(target, targetPoint.getWayId(), targetPoint.getRefId()))
                
                if source==0 and target==0:
                    print("source and target==0!")
                    break

                if targetPoint.getSource()==startPoint.getSource() and targetPoint.getTarget()==startPoint.getTarget() and targetPoint.getWayId()==startPoint.getWayId():
                    print("source and target equal!")
                    allEdgeList.append(startPoint.getEdgeId())
#                    allPathCost=allPathCost+pathCost            
                else:                  
#                    if self.dWrapper!=None:
#                        edgeList, pathCost=self.dWrapper.computeShortestPath(source, target)
#                        allEdgeList.extend(edgeList)
#                        allPathCost=allPathCost+pathCost            
                
                    if self.dWrapperShootingStar!=None:
                        edgeList=self.dWrapperShootingStar.computeShortestPath(sourceEdge, targetEdge)
                        allEdgeList.extend(edgeList)
                        
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
            return edgeList
                                
        return None

    def calcRouteForEdgesShootingStar(self, sourceEdge, targetEdge):        
        if sourceEdge==0 and targetEdge==0:
            print("source and target==0!")
            return None
            
        if self.dWrapperShootingStar!=None:
            edgeList=self.dWrapperShootingStar.computeShortestPath(sourceEdge, targetEdge)
            return edgeList
                        
        return None

    def createTrackForEdgeList(self, edgeList, routingPointList):
        if edgeList!=None:
            return self.printEdgeList(edgeList, routingPointList)
        
#    def showWay(self, wayId, usedRefId, level):
#        self.edgeList=list()
#        self.getEdgeListForWayLevels(wayId, usedRefId, level)
#        return self.printEdgeList(self.edgeList)
    
    def showWayWithName(self, streetInfo):
        (streetId, country, name, ref, wayIdList)=streetInfo       

        self.edgeList=list()
        self.possibleWays=wayIdList
        while len(self.possibleWays)!=0:
            wayId=self.findStartWay(self.possibleWays, country)
            (actWayId, tags, refs, distances)=self.getWayEntryForIdAndCountry(wayId, country)
            startRef=refs[0]
            
            resultList=self.getEdgeEntryForStartPoint(startRef, wayId)
            if len(resultList)==0:
                print("no start edge found for way %d"%(wayId))
                continue
    
            self.getEdgeListForWayName(resultList[0], (name, ref))
            
        return self.printEdgeList2(self.edgeList)
    
#    def printEdge(self, edgeId, trackWayList):
#        result=self.getEdgeEntryForEdgeId(edgeId)
#        print(result)
#        (edgeId, _, _, length, oneway, wayId, _, _, refList, maxspeed, country)=result
#        (wayId, tags, _, _)=self.getWayEntryForIdAndCountry(wayId, country)
#
#        if "highway" in tags:
#            streetType=tags["highway"]
#            
#        (name, ref)=self.getStreetNameInfo(tags)
#            
##        trackWayList.append(self.createStartTrackItem())
#
#        for ref in refList:       
#            trackItem=dict()
#            trackItem["wayId"]=wayId
#            trackItem["ref"]=ref
#            (lat, lon)=self.getCoordsWithRef(ref)
#            if lat==None:
#                print("resolveWay no node in DB with %d"%(ref))
#                continue
#            trackItem["lat"]=lat
#            trackItem["lon"]=lon        
#            trackItem["oneway"]=bool(oneway)
#            trackItem["type"]=streetType
#            trackItem["info"]=(name, ref)
#            trackItem["maxspeed"]=maxspeed
#            trackItem["length"]=length
#            resultList=self.getCrossingEntryForRefId(wayId, ref, country)
#            if len(resultList)!=0:
#                crossingType=0
#                for result in resultList:
#                    if crossingType!=0:
#                        break
#                    (crossingEntryId, wayId, refId, nextWayIdList)=result
#                    for nextWayId, crossingType in nextWayIdList:
#                        if crossingType==1:
#                            print("crossing with traffic lights")
#                            break
#                trackItem["crossing"]=crossingType
#
#            trackWayList.append(trackItem)
#           
##        trackWayList.append(self.createEndTrackItem())

    def printEdgeForRefList(self, refListPart, edgeId, trackWayList, routeEndRefId, routeStartRefId):
        result=self.getEdgeEntryForEdgeId(edgeId)
        print(result)
#        print(refListPart)
        (edgeId, _, _, length, oneway, wayId, _, _, _, maxspeed, country)=result
        (wayId, tags, _, _)=self.getWayEntryForIdAndCountry(wayId, country)

        if "highway" in tags:
            streetType=tags["highway"]
            
        (name, refName)=self.getStreetNameInfo(tags)
            
#        trackWayList.append(self.createStartTrackItem())
        latTo=None
        lonTo=None
        latFrom=None
        lonFrom=None
        for ref in refListPart:  
            if routeStartRefId!=None:
                if ref!=routeStartRefId:
#                    print("skip before start ref %d"%(ref))
                    continue
                else:
                    routeStartRefId=None

            trackItem=dict()
            trackItem["wayId"]=wayId
            trackItem["ref"]=ref
            (lat, lon)=self.getCoordsWithRef(ref)
            if lat==None:
                print("resolveWay no node in DB with %d"%(ref))
                continue
            
            if ref!=refListPart[-1]:
                latFrom=lat
                lonFrom=lon
                      
            if ref!=refListPart[0]:
                latTo=lat
                lonTo=lon
                
            if self.lastTrackItem!=None and latTo!=None and lonTo!=None and self.latCross!=None and self.lonCross!=None:
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
            trackItem["oneway"]=bool(oneway)
            trackItem["type"]=streetType
            trackItem["info"]=(name, ref)
            trackItem["maxspeed"]=maxspeed
            trackItem["length"]=length
            resultList=self.getCrossingEntryForRefId(wayId, ref, country)
            if len(resultList)!=0:
                crossingType=-1
                crossingInfo=None
                for result in resultList:
                    if crossingType!=-1:
                        break
                    (_, wayId, _, nextWayIdList)=result
                    for nextWayId, crossingType, crossingInfo in nextWayIdList:
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

           
    def printEdgeList(self, edgeList, routingPointList):
        trackWayList=list()
        track=dict()
        track["name"]=""
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
            (startEdgeId, _, _, _, _, _, _, _, startRefList, _, _)=self.getEdgeEntryForEdgeId(startEdgeId)                       
            indexStart=startRefList.index(routeStartRefId)
            indexEnd=startRefList.index(routeEndRefId)
            if indexEnd < indexStart:
                startRefList.reverse()
            self.printEdgeForRefList(startRefList, startEdgeId, trackWayList, routeEndRefId, routeStartRefId)  
        else:
            firstEdgeId=edgeList[0]
            (firstEdgeId, firstStartRef, firstEndRef, _, _, _, _, _, refList, _, _)=self.getEdgeEntryForEdgeId(firstEdgeId)                       
        
            if not routeStartRefId in refList:
                (startEdgeId, startStartRef, _, length, _, _, _, _, startRefList, _, _)=self.getEdgeEntryForEdgeId(startEdgeId)                       
            
                if firstStartRef==startStartRef or firstEndRef==startStartRef:
                    startRefList.reverse()
                print("add start edge")
                self.printEdgeForRefList(startRefList, startEdgeId, trackWayList, None, routeStartRefId)
                currentRefList=startRefList
                routeStartRefId=None
                # TODO maybe not the complete length
                allLength=allLength+length
    
            for edgeId in edgeList:
                (edgeId, currentStartRef, _, length, _, _, _, _, refList, _, _)=self.getEdgeEntryForEdgeId(edgeId)                       
    
                if currentRefList!=None:
                    if currentRefList[-1]!=refList[0]:
                        refList.reverse()
                else:
                    if len(edgeList)>1:
                        nextEdgeId=edgeList[1]
                        (nextEdgeId, nextStartRef, nextEndRef, _, _, _, _, _, _, _, _)=self.getEdgeEntryForEdgeId(nextEdgeId)                       
        
                        if nextStartRef==currentStartRef or nextEndRef==currentStartRef:
                            refList.reverse()
    
                self.printEdgeForRefList(refList, edgeId, trackWayList, routeEndRefId, routeStartRefId)
                
                currentRefList=refList
                routeStartRefId=None
                # TODO maybe not the complete length
                allLength=allLength+length
                                         
            if not routeEndRefId in currentRefList:      
                (endEdgeId, _, _, length, _, _, _, _, endRefList, _, _)=self.getEdgeEntryForEdgeId(endEdgeId)
                if currentRefList[-1]!=endRefList[0]:
                    endRefList.reverse()
                print("add end edge")
                self.printEdgeForRefList(endRefList, endEdgeId, trackWayList, routeEndRefId, None)
                # TODO maybe not the complete length
                allLength=allLength+length
                            
        track["track"]=trackWayList
        trackList=list()
        trackList.append(track)
        return trackList, allLength   
                
    def printEdgeList2(self, edgeList):
        trackWayList=list()
        track=dict()
        track["name"]=""
        allLength=0
             
        for edgeId in edgeList:
            self.createStartTrackItem()
            (edgeId, currentStartRef, _, length, _, _, _, _, refList, _, _)=self.getEdgeEntryForEdgeId(edgeId)                       
            self.printEdgeForRefList(refList, edgeId, trackWayList, None, None)
            self.createEndTrackItem()
            
        track["track"]=trackWayList
        trackList=list()
        trackList.append(track)
        return trackList, allLength   

    def getEdgeListForWayName(self, edge, streetInfo):        
        self.doneEdges=list()
                
        self.getEdgePartName(edge, streetInfo)
        
    def getEdgePartName(self, edge, streetInfo):
        (edgeId, startRef, endRef, length, oneway, wayId, source, target, refList, maxspeed, country)=edge

        self.doneEdges.append(edgeId)
        if wayId in self.possibleWays:
            self.possibleWays.remove(wayId)
        self.edgeList.append(edgeId)
                
        print(edge)
        
        resultList=self.getEdgeEntryForSource(target)  
        for result in resultList:
            edgeId, startRef, endRef, length, oneway1, wayId1, source1, target1, refList, maxspeed, country=result
            if edgeId in self.doneEdges:
                continue
            
            newStreetInfo=self.getStreetInfoWithWayId(wayId1, country)
            if newStreetInfo==streetInfo:
                self.getEdgePartName(result, streetInfo)
       
        resultList=self.getEdgeEntryForTarget(target)  
        for result in resultList:
            edgeId, startRef, endRef, length, oneway1, wayId1, source1, target1, refList, maxspeed, country=result
            if edgeId in self.doneEdges:
                continue
            if oneway1==1:
                continue
            
            newStreetInfo=self.getStreetInfoWithWayId(wayId1, country)
            if newStreetInfo==streetInfo:
                self.getEdgePartName(result, streetInfo)
      
        resultList=self.getEdgeEntryForTarget(source)
        for result in resultList:
            edgeId, startRef, endRef, length, oneway1, wayId1, source1, target1, refList, maxspeed, country=result
            if edgeId in self.doneEdges:
                continue
            if oneway1==1:
                continue

            newStreetInfo=self.getStreetInfoWithWayId(wayId1, country)
            if newStreetInfo==streetInfo:
                self.getEdgePartName(result, streetInfo)
            
        resultList=self.getEdgeEntryForSource(source)
        for result in resultList:
            edgeId, startRef, endRef, length, oneway1, wayId1, source1, target1, refList, maxspeed, country=result
            if edgeId in self.doneEdges:
                continue
            if oneway==1 and oneway1==1:
                continue

            newStreetInfo=self.getStreetInfoWithWayId(wayId1, country)
            if newStreetInfo==streetInfo:
                self.getEdgePartName(result, streetInfo)

    def createEdgeTableEntries(self):
        self.setDBCursorForCountry(self.country)
        self.cursor.execute('SELECT * FROM wayTable')
        allWays=self.cursor.fetchall()
        for way in allWays:
            wayId, _, _, _=self.wayFromDB(way)
            self.createEdgeTableEntriesForWay(wayId)

    def createEdgeTableNodeEntries(self):
        self.cursorEdge.execute('SELECT id FROM edgeTable')
        allEdges=self.cursorEdge.fetchall()
        for edgeEntryId in allEdges:
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
            edgeId, _, _, _, _, _, source, target, _, _, _=edge
            
#            (lat, lon)=self.getCoordsWithRef(endRef)
#            if lat!=None and lon!=None:
#                pointCountry=self.countryNameOfPoint(lat, lon)
#                if currentCountry!=pointCountry:
#                    print("ref %d is in country %s"%(endRef, pointCountry))
#            (lat, lon)=self.getCoordsWithRef(startRef)
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
        edgeId, startRef, _, _, _, _, sourceId, _, _, _, _ =edge
                           
        resultList=self.getEdgeEntryForStartPoint(startRef, edgeId)
        if len(resultList)!=0:
            if sourceId==0:
                sourceId=self.nodeId
                self.nodeId=self.nodeId+1
    
        for result in resultList:
            edgeId1, _, _, _, _, _, source1, _, _, _, _=result
            if source1!=0:
                continue

            self.updateSourceOfEdge(edgeId, sourceId)
            self.updateSourceOfEdge(edgeId1, sourceId)

    def createEdgeTableNodeSameEndEnriesFor(self, edge):
        edgeId, _, endRef, _, _, _, _, targetId, _, _, _=edge
                           
        resultList=self.getEdgeEntryForEndPoint(endRef, edgeId)
        if len(resultList)!=0:
            if targetId==0:
                targetId=self.nodeId
                self.nodeId=self.nodeId+1
            
        for result in resultList:
            edgeId1, _, _, _, _, _, _, target1, _, _, _=result
            if target1!=0:
                continue
            
            self.updateTargetOfEdge(edgeId, targetId)
            self.updateTargetOfEdge(edgeId1, targetId)
            
    def createEdgeTableNodeSourceEnriesFor(self, edge):
        edgeId, _, endRef, _, _, _, _, targetId, _, _, _=edge
        
        resultList=self.getEdgeEntryForStartPoint(endRef, edgeId)        
        if len(resultList)!=0:
            if targetId==0:
                targetId=self.nodeId
                self.nodeId=self.nodeId+1

        for result in resultList:
            edgeId1, _, _, _, _, _, source1, _, _, _, _=result
            
            if source1==0:
                self.updateSourceOfEdge(edgeId1, targetId)
                self.updateTargetOfEdge(edgeId, targetId)
            else:
                self.updateTargetOfEdge(edgeId, source1)
    
    def createEdgeTableNodeEntriesShootingStar(self):
        self.cursorEdge.execute('SELECT id FROM edgeTableShootingStar')
        allEdges=self.cursorEdge.fetchall()
        for edgeEntryId in allEdges:
            edgeId=edgeEntryId[0]
            edge=self.getEdgeEntryForEdgeIdShootingStar(edgeId)
            self.createEdgeTableNodeSameStartEnriesForShootingStar(edge)
            
#        for id in allEdges:
#            edgeId=id[0]
            edge=self.getEdgeEntryForEdgeIdShootingStar(edgeId)
            self.createEdgeTableNodeSameEndEnriesForShootingStar(edge)

#        for id in allEdges:
#            edgeId=id[0]
            edge=self.getEdgeEntryForEdgeIdShootingStar(edgeId)
            self.createEdgeTableNodeSourceEnriesForShootingStar(edge)

        self.cursorEdge.execute('SELECT id FROM edgeTableShootingStar WHERE source==0 OR target==0')
        allEdges=self.cursorEdge.fetchall()

        for edgeEntryId in allEdges:
            edgeId=edgeEntryId[0]
            edge=self.getEdgeEntryForEdgeIdShootingStar(edgeId)
            edgeId, _, _, source, target, _, _, _, _, _, _, _, _, _=edge
            
#            (lat, lon)=self.getCoordsWithRef(endRef)
#            if lat!=None and lon!=None:
#                pointCountry=self.countryNameOfPoint(lat, lon)
#                if currentCountry!=pointCountry:
#                    print("ref %d is in country %s"%(endRef, pointCountry))
#            (lat, lon)=self.getCoordsWithRef(startRef)
#            if lat!=None and lon!=None:
#                pointCountry=self.countryNameOfPoint(lat, lon)
#                if currentCountry!=pointCountry:
#                    print("ref %d is in country %s"%(startRef, pointCountry))
            
            if source==0:
                sourceId=self.nodeIdShootingStar
                self.nodeIdShootingStar=self.nodeIdShootingStar+1
                self.updateSourceOfEdgeShootingStar(edgeId, sourceId)
            if target==0:
                targetId=self.nodeIdShootingStar
                self.nodeIdShootingStar=self.nodeIdShootingStar+1
                self.updateTargetOfEdgeShootingStar(edgeId, targetId)
        
        self.createWayRestrictions()

    def createWayRestrictions(self):
        for fromWayId, wayRestrictionList in self.wayRestricitionListFrom.items():
            for wayRestrictionItem in wayRestrictionList:
                toWayId=wayRestrictionItem["to"]
                restrictionType=wayRestrictionItem["type"]

                resultList=self.getEdgeEntryForWayIdShootingStar(fromWayId)
                for fromWayIdResult in resultList:
                    (fromEdgeId, startRefFrom, endRefFrom, _, _, _, _, x1From, y1From, x2From, y2From, _, _, fromWayId)=fromWayIdResult
        
                    resultList=self.getEdgeEntryForWayIdShootingStar(toWayId)
                    if len(resultList)!=0:
                        for toWayIdResult in resultList:
                            (toEdgeId, startRefTo, endRefTo, _, _, _, _, x1To, y1To, x2To, y2To, _, _, toWayId)=toWayIdResult
                                
                            latCross=None
                            lonCross=None
                            latFrom=None
                            lonFrom=None
                            latTo=None
                            lonTo=None
                            
                            if startRefTo==startRefFrom:
                                latCross=x1From
                                lonCross=y1From
                                latFrom=x2From
                                lonFrom=y2From
                                latTo=x2To
                                lonTo=y2To
                            elif endRefTo==endRefFrom:
                                latCross=x2From
                                lonCross=y2From
                                latFrom=x1From
                                lonFrom=y1From
                                latTo=x1To
                                lonTo=y1To
                            elif startRefTo==endRefFrom:
                                latCross=x2From
                                lonCross=y2From
                                latFrom=x1From
                                lonFrom=y1From
                                latTo=x1To
                                lonTo=y1To
                            elif endRefTo==startRefFrom:
                                latCross=x2From
                                lonCross=y2From
                                latFrom=x1From
                                lonFrom=y1From
                                latTo=x1To
                                lonTo=y1To  
                                
                            if latCross==None:
                                print("calc direction not possible")
                                print("way restriction from %d"%(fromWayId))
                                print("way restriction to %d"%(toWayId))
                                print("way restriction type %s"%(restrictionType))
                                continue
                            
                            print("way restriction from %d"%(fromWayId))
                            print("way restriction to %d"%(toWayId))
                            print("way restriction type %s"%(restrictionType))

                            azimuth=self.osmutils.azimuth((latCross, lonCross), (latFrom, lonFrom), (latTo, lonTo))   
                            direction=self.osmutils.direction(azimuth)
                            
                            print(direction)
                            addRestriction=False
                            # no_left_turn 
                            # no_right_turn, 
                            # only_right_turn 
                            # only_left_turn 
                            # only_straight_on 
                            # no_straight_on
                            if direction==1:
                                # right
                                if restrictionType=="no_right_turn":
                                    addRestriction=True
                                if restrictionType=="only_left_turn":
                                    addRestriction=True
                                if restrictionType=="only_straight_on":
                                    addRestriction=True
                            elif direction==-1:
                                # left
                                if restrictionType=="no_left_turn":
                                    addRestriction=True
                                if restrictionType=="only_right_turn":
                                    addRestriction=True
                                if restrictionType=="only_straight_on":
                                    addRestriction=True
                            elif direction==0:
                                if restrictionType=="no_straight_on":
                                    addRestriction=True
                                    
                            if addRestriction:
                                print("need rule %d to edge %d"%(fromEdgeId, toEdgeId))
        #                        self.updateRuleOfEdgeShootingStar(toEdgeId, fromEdgeId)
                    
    def createEdgeTableNodeSameStartEnriesForShootingStar(self, edge):
        edgeId, startRef, _, sourceId, _, _, _, _, _, _, _, _, _, _=edge

        resultList=self.getEdgeEntryForStartPointShootingStar(startRef, edgeId)
        if len(resultList)!=0:
            if sourceId==0:
                sourceId=self.nodeIdShootingStar
                self.nodeIdShootingStar=self.nodeIdShootingStar+1
    
        for result in resultList:
            edgeId1, _, _, source1, _, _, _, _, _, _, _, _, _, _=result
            if source1!=0:
                continue

            self.updateSourceOfEdgeShootingStar(edgeId, sourceId)
            self.updateSourceOfEdgeShootingStar(edgeId1, sourceId)

    def createEdgeTableNodeSameEndEnriesForShootingStar(self, edge):
        edgeId, _, endRef, _, targetId, _, _, _, _, _, _, _, _, _=edge
                           
        resultList=self.getEdgeEntryForEndPointShootingStar(endRef, edgeId)
        if len(resultList)!=0:
            if targetId==0:
                targetId=self.nodeIdShootingStar
                self.nodeIdShootingStar=self.nodeIdShootingStar+1
            
        for result in resultList:
            edgeId1, _, _, _, target1, _, _, _, _, _, _, _, _, _=result
            if target1!=0:
                continue
            
            self.updateTargetOfEdgeShootingStar(edgeId, targetId)
            self.updateTargetOfEdgeShootingStar(edgeId1, targetId)
            
    def createEdgeTableNodeSourceEnriesForShootingStar(self, edge):
        edgeId, _, endRef, _, targetId, _, _, _, _, _, _, _, _, _=edge
        
        resultList=self.getEdgeEntryForStartPointShootingStar(endRef, edgeId)        
        if len(resultList)!=0:
            if targetId==0:
                targetId=self.nodeIdShootingStar
                self.nodeIdShootingStar=self.nodeIdShootingStar+1

        for result in resultList:
            edgeId1, _, _, source1, _, _, _, _, _, _, _, _, _, _=result
            
            if source1==0:
                self.updateSourceOfEdgeShootingStar(edgeId1, targetId)
                self.updateTargetOfEdgeShootingStar(edgeId, targetId)
            else:
                self.updateTargetOfEdgeShootingStar(edgeId, source1)
            
    def createEdgeTableEntriesForWay(self, wayId):
#        if not self.isWayInCountry(wayId, self.country):
#            return
        
        (wayId, tags, refs, distances)=self.getWayEntryForIdAndCountry(wayId, self.country)
        if wayId!=None:
            resultList=self.getCrossingEntryFor(wayId, self.country)
            
            nextWayDict=dict()
            for result in resultList:
                crossingEntryId, wayId, refId, nextWayIdList=result
                nextWayDict[refId]=nextWayIdList
            
#            wayRestrictionList=None
#            if wayId in self.wayRestricitionListFrom:
#                wayRestrictionList=self.wayRestricitionListFrom[wayId]                

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
                roundabout=1
#                print("street with same start and end and not roundabout %d %s"%(wayId, str(tags)))
                
#            if "access" in tags:
#                if tags["access"]=="destination":
#                    oneway=1

            # TODO iplicit
            #     <tag k="source:maxspeed" v="AT:urban"/>
            if "maxspeed" in tags:
                maxspeed=tags["maxspeed"]
                if ";" in maxspeed:
#                    print(maxspeed)
#                    print(maxspeed.split(";")[0])
                    try:
                        maxspeed=int(maxspeed.split(";")[0])
                    except ValueError:
                        maxspeed=int(maxspeed.split(";")[1])
                else:
                    try:
                        maxspeed=int(maxspeed)
                    except ValueError:
                        maxspeed=50
            else:
                if streetType=="residential":
                    maxspeed=50
                elif streetType=="motorway":
                    maxspeed=100
                else:
                    maxspeed=50
                
            doneRefs=list()
            for ref in refs:                  
                if ref in nextWayDict:
#                    if wayRestrictionList!=None:
#                        nextWayIdList=nextWayDict[ref]
#                        for nextWayId, crossingType, crossingInfo in nextWayIdList: 
#                            for wayRestricionEntry in wayRestrictionList:                      
#                                if wayRestricionEntry["to"]==nextWayId:
#                                    restricitionType=wayRestricionEntry["type"]
#                                    wayRestrictionItem=dict()
#                                                                        
#                                    wayRestrictionItem["to"]=nextWayId
#                                    wayRestrictionItem["from"]=wayId
#                                    wayRestrictionItem["type"]=restricitionType
#                                    self.wayRestriction[nextWayId]=wayRestrictionItem
#                                    print("added restriction %d %s"%(nextWayId, str(wayRestrictionItem)))
                                                                        
                    # TODO crossings with traffic lights should increase cost for this edge
#                    nextWayIdList=nextWayDict[ref]
#                    for nextWayId, crossingType in nextWayIdList:
#                        if crossingType==1:
#                            # with traffic lights
#                            None
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

                        cost=distance
                        if oneway:
                            reverseCost=10000
                        else:
                            reverseCost=cost
                            
                        if startRef in self.coords and endRef in self.coords:
                            x1, y1=self.coords[startRef]
                            x2, y2=self.coords[endRef]                        
                        
                            self.addToEdgeTableShootingStar(startRef, endRef, 0, 0, cost, reverseCost, x1, y1, x2, y2, 0, None, wayId)
                            self.addToEdgeTable(startRef, endRef, distance, oneway, wayId, refNodeList, maxspeed, self.country)
                        else:
                            print("skipping way %d because start %d and end %d are not in coords - country %d"%(wayId, startRef, endRef, self.country))
                        
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
                    
                    cost=distance
                    if oneway:
                        reverseCost=10000
                    else:
                        reverseCost=cost

                    if startRef in self.coords and endRef in self.coords:
                        x1, y1=self.coords[startRef]
                        x2, y2=self.coords[endRef]
                    
                        self.addToEdgeTableShootingStar(startRef, endRef, 0, 0, cost, reverseCost, x1, y1, x2, y2, 0, None, wayId)
                        self.addToEdgeTable(startRef, endRef, distance, oneway, wayId, refNodeList, maxspeed, self.country)
                    else:
                        print("skipping way %d because start %d and end %d are not in coords - country %d"%(wayId, startRef, endRef, self.country))

    def getStreetTrackList(self, wayid):
        if wayid in self.streetIndex:
            return self.streetIndex[wayid]["track"]
        return None

    def createCrossingEntries(self):
        self.setDBCursorForCountry(self.country)
        self.cursor.execute('SELECT * FROM wayTable')
        allWays=self.cursor.fetchall()
        for way in allWays:
            wayid, tags, refs, _=self.wayFromDB(way)    
             
#            if not self.isWayInCountry(wayid, self.country):
#                continue
            
            streetInfo=None
            if "name" in tags or "ref" in tags:
                streetInfo=self.getStreetNameInfo(tags) 
            
#            wayRestrictionList=None
#            if wayid in self.wayRestricitionListFrom:
#                wayRestrictionList=self.wayRestricitionListFrom[wayid]
                
            crossingType=0
            crossingInfo=None
            for ref in refs:  
                nextWays=self.findWayWithRefInAllWays(ref, wayid)  
                if len(nextWays)!=0:
                    if ref in self.nodes:
                        nodeTags, coords=self.nodes[ref]
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
#                        if wayRestrictionList!=None:
#                            for wayRestricionEntry in wayRestrictionList:
#                                if wayRestricionEntry["to"]==wayid2:
#                                    restricitionType=wayRestricionEntry["type"]
#                                    print("restriction from %d to %d %s"%(wayid, wayid2, restricitionType))
                       
                                
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

    def dbExists(self, country):
        return os.path.exists(self.getDBFile(country))

    def edgeDBExists(self):
        return os.path.exists(self.getEdgeDBFile())
        
    def globalCountryDBExists(self):
        return os.path.exists(self.getGlobalCountryDBFile())

    def adressDBExists(self):
        return os.path.exists(self.getAdressDBFile())

    def initGraph(self):
        
        if self.dWrapperShootingStar==None:
            self.dWrapperShootingStar=ShootingStarWrapper(self.getDataDir())
            
        if self.dWrapper==None:
            self.dWrapper=DijkstraWrapperPygraph(self.cursorEdge)
            self.dWrapper=DijkstraWrapperIgraph(self.cursorEdge, self.getDataDir())

        if not self.dWrapper.isGraphLoaded():
            print("init graph")
            self.dWrapper.initGraph()
            print("init graph done")

    def initDB(self):
        
        createEdgeDB=not self.edgeDBExists()
        if createEdgeDB:
            self.openEdgeDB()
            self.createEdgeTables()
        else:
            self.openEdgeDB()
            self.edgeId=self.getLenOfEdgeTable()+1
            self.edgeIdShootingStar=self.getLenOfEdgeTableShootingStar()+1
        
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

        updateEdgeDB=False
        for country in countryList:
            updateEdgeDB=True
            self.country=country
            self.debugCountry=country
            self.setDBCursorForCountry(country)
            
            print(self.osmList[country])
            self.initCountryData()
            print("start parsing")
            self.parse(country)
            print("end parsing")
            
            print("add refs")
            self.addAllRefsToDB()
            print("end add refs")

            print("add way refs")
            self.addWayRefsToDB()
            print("end add way refs")

#            print("collect streets")
#            self.collectWaysByName()
#            print("end collect streets")
            
            print("create crossings")
            self.createCrossingEntries()
            print("end create crossings")
            
            print("create edges")
            self.createEdgeTableEntries()
            print("end create edges")                    
                        
        if updateEdgeDB:
            self.clearSourceAndTargetOfEdges()
            self.clearSourceAndTargetOfEdgesShootingStar()
            print("create edge nodes")
            self.createEdgeTableNodeEntries()
            self.createEdgeTableNodeEntriesShootingStar()
            print("end create edge nodes")

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
        osmData["osmFile"]='/home/maxl/Downloads/salzburg.osm.bz2'
        osmData["poly"]="austria.poly"
        osmData["polyCountry"]="Europe / Western Europe / Austria"
        osmData["countryCode"]="AT"
        osmDataList[0]=osmData
        
#        osmData=dict()
#        osmData["country"]="switzerland"
#        osmData["osmFile"]='/home/maxl/Downloads/switzerland.osm.bz2'
#        osmData["poly"]="switzerland.poly"
#        osmData["polyCountry"]="Europe / Western Europe / Switzerland"
#        osmDataList[1]=osmData
    
        osmData=dict()
        osmData["country"]="germany"
        osmData["osmFile"]='/home/maxl/Downloads/bayern-south.osm'
        osmData["poly"]="germany.poly"
        osmData["polyCountry"]="Europe / Western Europe / Germany"
        osmData["countryCode"]="DE"
        osmDataList[2]=osmData
        return osmDataList
    
def main(argv):    
    p = OSMParserData()
    
    p.initDB()
    
    p.openAllDB()
    p.initGraph()
#    p.testCountryRefTable()
#    p.testCountryWayTable()
#    p.testStreetTable2()
#    p.testEdgeTable()
#    p.testEdgeTableShootingStar2()
        
#    print(p.calcRouteForNodes(158, 3048))
#    print(p.getLenOfEdgeTable())
#    print(p.getEdgeEntryForEdgeId(6719))
#    print(p.getEdgeEntryForEdgeId(2024))

#    print(p.calcRouteForEdgesShootingStar(6719, 6433))  
#    print(p.getLenOfEdgeTableShootingStar())
#    print(p.getEdgeEntryForEdgeIdShootingStar(6719))
#    print(p.getEdgeEntryForEdgeIdShootingStar(2024))


    p.closeAllDB()


if __name__ == "__main__":
    main(sys.argv)  
    

