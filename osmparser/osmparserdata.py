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
            
            (edgeId, startRef, endRef, length, oneway, wayId, source1, target1, refList, maxspeed, country)=result

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
        self.connectionGlobal=None
        self.cursorGlobal=None
        self.connectionAdress=None
        self.cursorAdress=None
        self.edgeId=0
        self.trackItemList=list()
#        self.doneEdges=list()
#        self.edgeList=list()
        self.nodeId=1
        self.streetId=0
        self.dWrapper=None
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
        self.wayToStreetIndex=dict()

    def createCountryTables(self):
        self.createRefTable()
        self.createWayTable()
#        self.createStreetTable()
        self.createCrossingsTable()

    def createGlobalTables(self):
        self.createEdgeTable()
        self.createRefCountryTable()
        self.createNodeWayCountryTable()
        
    def createAdressTable(self):
        self.createStreetTable2()
        
    def openGlobalDB(self):
        self.connectionGlobal=sqlite3.connect(self.getGlobalDBFile())
        self.cursorGlobal=self.connectionGlobal.cursor()

    def openAdressDB(self):
        self.connectionAdress=sqlite3.connect(self.getAdressDBFile())
        self.cursorAdress=self.connectionAdress.cursor()

    def closeCountryDB(self, country):
        cursor=self.osmList[country]["cursor"]
        connection=self.osmList[country]["connection"]
        connection.commit()
        cursor.close()
        self.osmList[country]["cursor"]=None
        self.osmList[country]["connection"]=None

    def closeGlobalDB(self):
        self.connectionGlobal.commit()        
        self.cursorGlobal.close()
        self.connectionGlobal=None     
        self.cursorGlobal=None
       
    def closeAdressDB(self):
        self.connectionAdress.commit()
        self.cursorAdress.close()
        self.connectionAdress=None
        self.cursorAdress=None
                
    def openAllDB(self):
        self.openGlobalDB()
        self.openAdressDB()
        for country in self.osmList.keys():
            self.openCountryDB(country)
        
    def closeAllDB(self):
        self.closeGlobalDB()
        self.closeAdressDB()
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
#        self.cursor.execute('CREATE TABLE streetTable (street TEXT PRIMARY KEY, wayIdList BLOB)')

    def createStreetTable2(self):
        self.cursorAdress.execute('CREATE TABLE streetTable (id INTEGER PRIMARY KEY, country INTEGER, street TEXT, wayIdList BLOB)')
    
    def createCrossingsTable(self):
        self.cursor.execute('CREATE TABLE crossingTable (id INTEGER PRIMARY KEY, wayId INTEGER, refId INTEGER, nextWayIdList BLOB)')
        self.cursor.execute("CREATE INDEX wayId_idx ON crossingTable (wayId)")
        self.cursor.execute("CREATE INDEX refId_idx ON crossingTable (refId)")

    def createEdgeTable(self):
        self.cursorGlobal.execute('CREATE TABLE edgeTable (id INTEGER PRIMARY KEY, startRef INTEGER, endRef INTEGER, length INTEGER, oneway BOOL, wayID INTEGER, source INTEGER, target INTEGER, refList BLOB, maxspeed INTEGER, country INTEGER)')
        self.cursorGlobal.execute("CREATE INDEX startRef_idx ON edgeTable (startRef)")
        self.cursorGlobal.execute("CREATE INDEX endRef_idx ON edgeTable (endRef)")
        self.cursorGlobal.execute("CREATE INDEX source_idx ON edgeTable (source)")
        self.cursorGlobal.execute("CREATE INDEX target_idx ON edgeTable (target)")

    def createRefCountryTable(self):
        self.cursorGlobal.execute('CREATE TABLE refCountryTable (id INTEGER PRIMARY KEY, country INTEGER)')
    
    def addToCountryRefTable(self, refId, country, lat, lon):
        storedRefId, storedCountry=self.getCountryOfRef(refId)
        if storedRefId==None:
            self.cursorGlobal.execute('INSERT INTO refCountryTable VALUES( ?, ?)', (refId, country))
        else:
#            print("refid %d stored with country %d"%(storedRefId, storedCountry))
            polyCountry=self.countryNameOfPoint(lat, lon)
            refCountry=self.getCountryForPolyCountry(polyCountry)
            if refCountry!=None:
                if refCountry!=storedCountry:
#                    print("but belongs to country %d"%(refCountry))
                    self.cursorGlobal.execute('REPLACE INTO refCountryTable VALUES( ?, ?)', (refId, country))
                    
    def getCountryOfRef(self, refId):
        self.cursorGlobal.execute('SELECT id, country FROM refCountryTable where id=="%s"'%(str(refId)))
        allentries=self.cursorGlobal.fetchall()
        if len(allentries)==1:
            return (allentries[0][0], allentries[0][1])
        return (None, None)

    def testCountryRefTable(self):
        self.cursorGlobal.execute('SELECT * FROM refCountryTable')
        allentries=self.cursorGlobal.fetchall()
        for x in allentries:
            print( "refId: "+str(x[0]) +" country: " + x[1])

    def createNodeWayCountryTable(self):
        self.cursorGlobal.execute('CREATE TABLE wayCountryTable (id INTEGER PRIMARY KEY, wayId INTEGER, country INTEGER)')

    def addToCountryWayTable(self, wayId, country):
        self.cursorGlobal.execute('INSERT INTO wayCountryTable VALUES( ?, ?, ?)', (self.wayCount, wayId, country))
        self.wayCount=self.wayCount+1
        
    def getCountrysOfWay(self, wayId):
        self.cursorGlobal.execute('SELECT id, wayId, country FROM wayCountryTable where wayId=="%s"'%(str(wayId)))
        allentries=self.cursorGlobal.fetchall()
        resultList=list()
        for x in allentries:
            resultList.append((x[0], x[1], x[2]))
        return resultList
    
    def testCountryWayTable(self):
        self.cursorGlobal.execute('SELECT * FROM wayCountryTable')
        allentries=self.cursorGlobal.fetchall()
        for x in allentries:
            print( "id: "+x[0]+ "wayId: "+str(x[1]) +" country: " + x[2])

    def addToRefTable(self, refid, lat, lon, wayIdList):
        self.setDBCursorForCountry(self.country)
        self.cursor.execute('INSERT INTO refTable VALUES( ?, ?, ?, ?)', (refid, lat, lon, pickle.dumps(wayIdList)))

    def addToWayTable(self, wayid, tags, refs, distances):
        self.setDBCursorForCountry(self.country)
        self.cursor.execute('INSERT INTO wayTable VALUES( ?, ?, ?, ?)', (wayid, pickle.dumps(tags), pickle.dumps(refs), pickle.dumps(distances)))

#    def addToStreetTable(self, streetInfo, wayidList):
#        (name, ref)=streetInfo
#        streetInfoString=name+"_"+ref
#        self.cursor.execute('INSERT INTO streetTable VALUES( ?, ?)', (streetInfoString, pickle.dumps(wayidList)))

    def addToStreetTable2(self, country, streetInfo, wayidList):
        (name, ref)=streetInfo
        streetInfoString=name+"_"+ref
        self.cursorAdress.execute('INSERT INTO streetTable VALUES( ?, ?, ?, ?)', (self.streetId, country, streetInfoString, pickle.dumps(wayidList)))
        self.streetId=self.streetId+1
        
    def addToCrossingsTable(self, wayid, refId, nextWaysList):
        self.setDBCursorForCountry(self.country)
        self.cursor.execute('INSERT INTO crossingTable VALUES( ?, ?, ?, ?)', (self.crossingId, wayid, refId, pickle.dumps(nextWaysList)))
        self.crossingId=self.crossingId+1

    def addToEdgeTable(self, startRef, endRef, length, oneway, wayId, refList, maxspeed, country):
        self.cursorGlobal.execute('INSERT INTO edgeTable VALUES( ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (self.edgeId, startRef, endRef, length, oneway, wayId, 0, 0, pickle.dumps(refList), maxspeed, country))
        self.edgeId=self.edgeId+1
    
    def updateSourceOfEdge(self, edgeId, sourceId):
        existingEdgeId, startRef, endRef, length, oneway, wayId, source, target, refList, maxspeed, country=self.getEdgeEntryForEdgeId(edgeId)
        if existingEdgeId==None:
            print("no edge with id %d"%(edgeId))
            return
        self.cursorGlobal.execute('REPLACE INTO edgeTable VALUES( ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (edgeId, startRef, endRef, length, oneway, wayId, sourceId, target, pickle.dumps(refList), maxspeed, country))

    def updateTargetOfEdge(self, edgeId, targetId):
        existingEdgeId, startRef, endRef, length, oneway, wayId, source, target, refList, maxspeed, country=self.getEdgeEntryForEdgeId(edgeId)
        if existingEdgeId==None:
            print("no edge with id %d"%(edgeId))
            return
        self.cursorGlobal.execute('REPLACE INTO edgeTable VALUES( ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (edgeId, startRef, endRef, length, oneway, wayId, source, targetId, pickle.dumps(refList), maxspeed, country))     
      
    def getEdgeEntryForSource(self, sourceId):
        self.cursorGlobal.execute('SELECT * FROM edgeTable where source=="%s"'%(str(sourceId)))
        resultList=list()
        allentries=self.cursorGlobal.fetchall()
        for result in allentries:
            edge=self.edgeFromDB(result)
            resultList.append(edge)
        return resultList      
    
    def getEdgeEntryForTarget(self, targetId):
        self.cursorGlobal.execute('SELECT * FROM edgeTable where target=="%s"'%(str(targetId)))
        resultList=list()
        allentries=self.cursorGlobal.fetchall()
        for result in allentries:
            edge=self.edgeFromDB(result)
            resultList.append(edge)
        return resultList      
    
    def getEdgeEntryForSourceAndTarget(self, sourceId, targetId):
        self.cursorGlobal.execute('SELECT * FROM edgeTable where source=="%s" AND target=="%s"'%(str(sourceId), str(targetId)))
        resultList=list()
        allentries=self.cursorGlobal.fetchall()
        for result in allentries:
            edge=self.edgeFromDB(result)
            resultList.append(edge)
        return resultList   
    
    def getEdgeEntryForEdgeId(self, edgeId):
        self.cursorGlobal.execute('SELECT * FROM edgeTable where id=="%s"'%(str(edgeId)))
        allentries=self.cursorGlobal.fetchall()
        if len(allentries)==1:
            edge=self.edgeFromDB(allentries[0])
            return edge
        print("no edge with %d"%(edgeId))
        return (None, None, None, None, None, None, None, None, None, None, None)
        
    def getEdgeEntryForStartPoint(self, startRef, edgeId):
        self.cursorGlobal.execute('SELECT * FROM edgeTable where startRef="%s" AND id!="%s"'%(str(startRef), str(edgeId)))
        resultList=list()
        allentries=self.cursorGlobal.fetchall()
        for result in allentries:
            edge=self.edgeFromDB(result)
            resultList.append(edge)
        return resultList
 
    def getEdgeEntryForEndPoint(self, endRef, edgeId):
        self.cursorGlobal.execute('SELECT * FROM edgeTable where endRef=="%s" AND id!="%s"'%(str(endRef), str(edgeId)))
        resultList=list()
        allentries=self.cursorGlobal.fetchall()
        for result in allentries:
            edge=self.edgeFromDB(result)
            resultList.append(edge)
        return resultList
    
    def getEdgeEntryForWayId(self, wayId):
        self.cursorGlobal.execute('SELECT * FROM edgeTable where wayId=="%s"'%(str(wayId)))
        resultList=list()
        allentries=self.cursorGlobal.fetchall()
        for result in allentries:
            edge=self.edgeFromDB(result)
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

#    def getWayEntryForId(self, wayId, country):
#        resultList=self.getCountrysOfWay(wayId)
#        if wayId==None:
#            return (None, None, None, None)
#        self.setDBCursorForCountry(country)
#        self.cursor.execute('SELECT * FROM wayTable where wayId==%s'%(str(wayId)))
#        allentries=self.cursor.fetchall()
#        if len(allentries)==1:
#            return self.wayFromDB(allentries[0])
#        
#        return (None, None, None, None)
    
    def getWayEntryForIdAndCountry(self, wayId, country):
        self.setDBCursorForCountry(country)
        self.cursor.execute('SELECT * FROM wayTable where wayId==%s'%(str(wayId)))
        allentries=self.cursor.fetchall()
        if len(allentries)==1:
            return self.wayFromDB(allentries[0])
        
        return (None, None, None, None)
    
#    def getStreetEntryForName(self, streetInfo):
#        (name, ref)=streetInfo
#        streetInfoString=name+"_"+ref
#        self.cursor.execute('SELECT * FROM streetTable where street=="%s"'%(str(streetInfoString)))
#        allentries=self.cursor.fetchall()
#        if len(allentries)==1:
#            return self.streetFromDB(allentries[0])
#        
#        return (None, None, None)

    def getStreetEntryForName2(self, streetInfo):
        (name, ref)=streetInfo
        streetInfoString=name+"_"+ref
        self.cursorAdress.execute('SELECT * FROM streetTable where street=="%s"'%(str(streetInfoString)))
        allentries=self.cursor.fetchall()
        if len(allentries)==1:
            return self.streetFromDB2(allentries[0])
        
        return (None, None, None, None, None)
    
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
                (wayId, tags, refs, distances)=self.getWayEntryForIdAndCountry(wayId, country)
                if wayId==None:
                    continue
                
                (prevRefId, nextRefId)=self.getPrevAndNextRefForWay(refId, wayId, tags, refs)
                if prevRefId!=None and nextRefId!=None:
                    (prevLat, prevLon)=self.getCoordsWithRef(prevRefId)
                    (nextLat, nextLon)=self.getCoordsWithRef(nextRefId)
                    
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
#        self.cursor.execute('SELECT * FROM streetTable')
#        allentries=self.cursor.fetchall()
#        for x in allentries:
#            name, ref, wayIdList=self.streetFromDB(x)
#            print( "name: " + name + " ref:"+ref+ " wayIdList: " + str(wayIdList))

    def testStreetTable2(self):
        self.cursorAdress.execute('SELECT * FROM streetTable')
        allentries=self.cursorAdress.fetchall()
        for x in allentries:
            streetId, country, name, ref, wayIdList=self.streetFromDB2(x)
            print( "id:"+str(streetId) +" country: "+str(country)+" name: " + name + " ref:"+ref+ " wayIdList: " + str(wayIdList))

    def testCrossingTable(self, country):
        self.setDBCursorForCountry(country)

        self.cursor.execute('SELECT * FROM crossingTable')
        allentries=self.cursor.fetchall()
        for x in allentries:
            id, wayid, refId, wayIdList=self.crossingFromDB(x)
            print( "id: "+ str(id) + " wayid: " + str(wayid) +  " refId: "+ str(refId) + " wayIdList: " + str(wayIdList))
        
    def testEdgeTable(self):
        self.cursorGlobal.execute('SELECT * FROM edgeTable')
        allentries=self.cursorGlobal.fetchall()
        for x in allentries:
            edgeId, startRef, endRef, length, oneway, wayId, source, target, refList, maxspeed, country=self.edgeFromDB(x)
            print( "edgeId: "+str(edgeId) +" startRef: " + str(startRef)+" endRef:"+str(endRef)+ " length:"+str(length)+ " oneway: "+str(oneway)+ " wayId:"+str(wayId) +" source:"+str(source)+" target:"+str(target) +" refList:"+str(refList) + " maxspeed:"+str(maxspeed) + " country:"+str(country))

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

    def streetFromDB(self, x):
        streetInfoString=x[0]
        (name, ref)=streetInfoString.split("_")
        wayIdList=pickle.loads(x[1])
        return (name, ref, wayIdList)

    def streetFromDB2(self, x):
        streetId=x[0]
        country=x[1]
        streetInfoString=x[2]
        (name, ref)=streetInfoString.split("_")
        wayIdList=pickle.loads(x[3])
        return (streetId, country, name, ref, wayIdList)
        
    def crossingFromDB(self, x):
        id=x[0]
        wayid=x[1]
        refId=x[2]            
        nextWayIdList=pickle.loads(x[3])
        return (id, wayid, refId, nextWayIdList)
    
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
        
    def addAllRefsToDB(self):
        for ref, wayIdList in self.wayRefIndex.items():
            try:
                lat=self.coords[ref][1]
                lon=self.coords[ref][0]
            except KeyError:
                continue
            self.addToRefTable(ref, lat, lon, wayIdList)
            self.addToCountryRefTable(ref, self.country, lat, lon)

    def locationToGridIndex(self, lat, lon):
        normLat=lat+180.0
        normLon=lon+180.0
        
        xIndex=int((normLat*1000)/36)
        yIndex=int((normLon*1000)/36)
        
        return (xIndex, yIndex)
    
    def parse_nodes(self, node):
        None
#        for osmid, tags, coords in node:
##            self.nodes[osmid]=(tags, coords)
#            self.coords[osmid]=(coords[1], coords[0])

                
    def parse_coords(self, coord):
        for osmid, lat, lon in coord:
            self.coords[int(osmid)]=(float(lat), float(lon))
                
    def parse_ways(self, way):
        for wayid, tags, refs in way:
            if wayid==33094518:
                print("parse_ways %d %d"%(wayid, self.country))
            if "highway" in tags:
                streetType=tags["highway"]
                if streetType=="services" or streetType=="bridleway" or streetType=="path" or streetType=="track" or streetType=="footway" or streetType=="pedestrian" or streetType=="cycleway" or streetType=="service" or streetType=="living_street" or streetType=="steps" or streetType=="platform" or streetType=="crossing" or streetType=="raceway":
                    continue
                
                if "service" in tags:
                    continue
                
                if "parking" in tags:
                    continue
                
                if "amenity" in tags:
                    continue
                
                if "area" in tags:
                    if tags["area"]=="yes":
                        continue
                if "building" in tags:
                    if tags["building"]=="yes":
                        continue
                distances=list()
    
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
                self.addToCountryWayTable(wayid, self.country)

    def collectWaysByName(self):
        self.setDBCursorForCountry(self.country)
        self.cursor.execute('SELECT * FROM wayTable')
        allWays=self.cursor.fetchall()
        
        street_by_name=dict()

        for way in allWays:
            wayId, tags, refs, distances=self.wayFromDB(way)
                
            if "highway" in tags:
                streetType=tags["highway"]
                if streetType[-5:]=="_link":
                    continue
                
            if "name" in tags or "ref" in tags:
                (name, ref)=self.getStreetNameInfo(tags)
                if name=="" and ref=="":
                    print("cannot create indexname for "+str(tags))
                    continue


#                    if ref!="A1" and name!="Münchner Bundesstraße":
#                        continue
                
                if not (name, ref) in street_by_name.keys():
                    wayIdList=list()
                    wayIdList.append(wayId)
                    street_by_name[(name, ref)]=wayIdList
                else:
                    wayIdList=street_by_name[(name, ref)]
                    wayIdList.append(wayId)

        for name, ref in street_by_name.keys():
            wayIdList=street_by_name[(name, ref)]
#            self.addToStreetTable((name, ref), wayIdList)
            self.addToStreetTable2(self.country, (name, ref), wayIdList)
        
    def parse_relations(self, relation):
        for osmid, tags, ways in relation:
            self.relations[osmid]=(tags, ways)
            
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
        (refId, lat, lon, wayIdList)=self.getRefEntryForId(ref)
        if refId!=None:
            return wayIdList
        
        return None

    def getStreetInfoWithWayId(self, wayId, country):
        (id, tags, refs, distances)=self.getWayEntryForIdAndCountry(wayId, country)
        if id!=None:
            (name, ref)=self.getStreetNameInfo(tags)
            return (name, ref)
        return (None, None)
        
    def getCoordsWithRef(self, ref):
        (refId, lat, lon, wayIdList)=self.getRefEntryForId(ref)
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
            
            (id, tags, refs, distances)=self.getWayEntryForIdAndCountry(wayid, country)
            if id==None:
                print("no entry in way DB for "+str(wayid))
                continue
            
            for wayRef in refs:
                if wayRef==refId:
                    possibleWays.append((wayid, tags, refs))
 
        return possibleWays
    
#    def findWayWithEndRef(self, ways, endRef, country):
#        possibleWays=list()
#        for wayId  in ways:
#            (actWayId, tags, refs, distances)=self.getWayEntryForIdAndCountry(wayId, country)
#            if refs[-1]==endRef:
#                possibleWays.append(actWayId)
#        return possibleWays
#    
#    def findStartWay(self, ways, country):
#        for wayId  in ways:
#            (actWayId, tags, refs, distances)=self.getWayEntryForIdAndCountry(wayId, country)
#            startRef=refs[0]
#            possibleWays=self.findWayWithEndRef(ways, startRef, country)
#            if len(possibleWays)==0:
#                return actWayId
#        return ways[0]
                 
    def getStreetList(self):
        self.cursorAddress.execute('SELECT * FROM streetTable')
        allentries=self.cursorAddress.fetchall()
        streetList=dict()
        for x in allentries:
            name, ref, wayIdList=self.streetFromDB(x)
            streetList[(name, ref)]=wayIdList

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
                
#    def createStartTrackItem(self):
#        streetTrackItem=dict()
#        streetTrackItem["start"]="start"
#        return streetTrackItem
#    
#    def createEndTrackItem(self):
#        streetTrackItem=dict()
#        streetTrackItem["end"]="end"
#        return streetTrackItem

    def calcRouteForPoints(self, routingPointList):        
        allPathCost=0.0
        allEdgeList=list()
        
        if len(routingPointList)!=0:  
            i=0   
            startPoint=routingPointList[0]
            if startPoint.getSource()==0:
                # should not happen
                print("startPoint NOT resolved in calc route")
                startPoint.resolveFromPos(self)
            source=startPoint.getSource()

            for targetPoint in routingPointList[1:]:
            # find out if last edge goes through the end point
            # if yes we need to shorten it
            # if no we need to add the last points
            # same is true for the actual starting point

                if targetPoint.getTarget()==0:
                    # should not happen
                    print("targetPoint NOT resolved in calc route")
                    targetPoint.resolveFromPos(self)
                target=targetPoint.getTarget()
                            
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
                    if self.dWrapper!=None:
                        edgeList, pathCost=self.dWrapper.computeShortestPath(source, target)
                        allEdgeList.extend(edgeList)
                        allPathCost=allPathCost+pathCost            
                
                startPoint=targetPoint
                source=startPoint.getTarget()
                i=i+1
                
            return allEdgeList, allPathCost

        return None, None

    def createTrackForEdgeList(self, edgeList, routingPointList):
        if edgeList!=None:
            return self.printEdgeList(edgeList, routingPointList)
        
#    def showWay(self, wayId, usedRefId, level):
#        self.edgeList=list()
#        self.getEdgeListForWayLevels(wayId, usedRefId, level)
#        return self.printEdgeList(self.edgeList)
    
#    def showWayWithName(self, name, ref):
#        streetId, country, name, ref, wayIdList=self.getStreetEntryForName2((name, ref))
#        if name==None:
#            print("street with name %s and ref %snot found"%(name, ref))
#            return
#                
#        self.edgeList=list()
#        self.possibleWays=wayIdList
#        while len(self.possibleWays)!=0:
#            wayId=self.findStartWay(self.possibleWays, country)
#            (actWayId, tags, refs, distances)=self.getWayEntryForIdAndCountry(wayId, country)
#            startRef=refs[0]
#            
#            resultList=self.getEdgeEntryForStartPoint(startRef, wayId)
#            if len(resultList)==0:
#                print("no start edge found for way %d"%(wayId))
#                continue
#    
#            self.getEdgeListForWayName(resultList[0], (name, ref))
#        return self.printEdgeList(self.edgeList)
    
    def printEdge(self, edgeId, trackWayList):
        result=self.getEdgeEntryForEdgeId(edgeId)
        print(result)
        (edgeId, _, _, length, oneway, wayId, _, _, refList, maxspeed, country)=result
        (wayId, tags, _, _)=self.getWayEntryForIdAndCountry(wayId, country)

        if "highway" in tags:
            streetType=tags["highway"]
            
        (name, ref)=self.getStreetNameInfo(tags)
            
#        trackWayList.append(self.createStartTrackItem())

        for ref in refList:       
            trackItem=dict()
            trackItem["wayId"]=wayId
            trackItem["ref"]=ref
            (lat, lon)=self.getCoordsWithRef(ref)
            if lat==None:
                print("resolveWay no node in DB with %d"%(ref))
                continue
            trackItem["lat"]=lat
            trackItem["lon"]=lon        
            trackItem["oneway"]=bool(oneway)
            trackItem["type"]=streetType
            trackItem["info"]=(name, ref)
            trackItem["maxspeed"]=maxspeed
            trackItem["length"]=length
            resultList=self.getCrossingEntryForRefId(wayId, ref, country)
            if len(resultList)!=0:
                crossingType=1
                for result in resultList:
                    if crossingType==0:
                        break
                    (id, wayId, refId, nextWayIdList)=result
                    for nextWayId, crossingType in nextWayIdList:
                        if crossingType==0:
                            break
                trackItem["crossing"]=crossingType

            trackWayList.append(trackItem)
           
#        trackWayList.append(self.createEndTrackItem())

    def printEdgeForRefList(self, refListPart, edgeId, trackWayList, routeEndRefId, routeStartRefId):
        result=self.getEdgeEntryForEdgeId(edgeId)
        print(result)
#        print(refListPart)
        (edgeId, _, _, length, oneway, wayId, _, _, _, maxspeed, country)=result
        (wayId, tags, _, _)=self.getWayEntryForIdAndCountry(wayId, country)

        if "highway" in tags:
            streetType=tags["highway"]
            
        (name, ref)=self.getStreetNameInfo(tags)
            
#        trackWayList.append(self.createStartTrackItem())

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
            trackItem["lat"]=lat
            trackItem["lon"]=lon        
            trackItem["oneway"]=bool(oneway)
            trackItem["type"]=streetType
            trackItem["info"]=(name, ref)
            trackItem["maxspeed"]=maxspeed
            trackItem["length"]=length
            resultList=self.getCrossingEntryForRefId(wayId, ref, country)
            if len(resultList)!=0:
                crossingType=1
                for result in resultList:
                    if crossingType==0:
                        break
                    (id, wayId, refId, nextWayIdList)=result
                    for nextWayId, crossingType in nextWayIdList:
                        if crossingType==0:
                            break
                trackItem["crossing"]=crossingType

            trackWayList.append(trackItem)
                   
            if routeEndRefId!=None and ref==routeEndRefId:
#                print("skip end after stop ref %d"%(ref))
                break
           
    def printEdgeList(self, edgeList, routingPointList):
        trackWayList=list()
        track=dict()
        track["name"]=""
        allLength=0
        
        endPoint=routingPointList[-1]
        routeEndRefId=endPoint.getRefId()
        endEdgeId=endPoint.getEdgeId()

        startPoint=routingPointList[0]
        routeStartRefId=startPoint.getRefId()
        startEdgeId=startPoint.getEdgeId()
     
        currentRefList=None

        if len(edgeList)==1:
            (startEdgeId, _, _, _, _, _, _, _, startRefList, _, _)=self.getEdgeEntryForEdgeId(startEdgeId)                       
            indexStart=startRefList.index(routeStartRefId)
            indexEnd=startRefList.index(routeEndRefId)
            if indexEnd < indexStart:
                startRefList.reverse()
            self.printEdgeForRefList(startRefList, startEdgeId, trackWayList, routeEndRefId, routeStartRefId)  
        else:
            firstEdgeId=edgeList[0]
            (firstEdgeId, firstStartRef, firstEndRef, _, _, _, _, _, refList, _, _)=self.getEdgeEntryForEdgeId(firstEdgeId)                       

#            (lat, lon)=self.getCoordsWithRef(routeStartRefId)
#            if lat!=startPoint.getLat() and lon!=startPoint.getLon():
#                self.printEdgeToRoutingPoint(startPoint, startPoint.getWayId(), trackWayList)

            if not routeStartRefId in refList:
                (startEdgeId, startStartRef, startEndRef, length, _, _, _, _, startRefList, _, _)=self.getEdgeEntryForEdgeId(startEdgeId)                       
            
                if firstStartRef==startStartRef or firstEndRef==startStartRef:
                    startRefList.reverse()
                print("add start edge")
                self.printEdgeForRefList(startRefList, startEdgeId, trackWayList, None, routeStartRefId)
                currentRefList=startRefList
                routeStartRefId=None
                # TODO maybe not the complete length
                allLength=allLength+length

            for edgeId in edgeList:
                (edgeId, currentStartRef, currentEndRef, length, _, _, _, _, refList, _, _)=self.getEdgeEntryForEdgeId(edgeId)                       
    
                if currentRefList!=None:
                    if currentRefList[-1]!=refList[0]:
                        refList.reverse()
                else:
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
                
#            (lat, lon)=self.getCoordsWithRef(routeEndRefId)
#            if lat!=endPoint.getLat() and lon!=endPoint.getLon():
#                self.printEdgeToRoutingPoint(endPoint, endPoint.getWayId(), trackWayList)
            
        track["track"]=trackWayList
        trackList=list()
        trackList.append(track)
        return trackList, allLength   
                
#    def getEdgeListForWayName(self, edge, streetInfo):        
#        self.doneEdges=list()
#                
#        self.getEdgePartName(edge, streetInfo)
        
#    def getEdgePartName(self, edge, streetInfo):
#        (edgeId, startRef, endRef, length, oneway, wayId, source, target, refList, maxspeed, country)=edge
#
#        self.doneEdges.append(edgeId)
#        if wayId in self.possibleWays:
#            self.possibleWays.remove(wayId)
#        self.edgeList.append(edgeId)
#                
#        print(edge)
#        
#        resultList=self.getEdgeEntryForSource(target)  
#        for result in resultList:
#            edgeId, startRef, endRef, length, oneway1, wayId1, source1, target1, refList, maxspeed, country=result
#            if edgeId in self.doneEdges:
#                continue
#            
#            newStreetInfo=self.getStreetInfoWithWayId(wayId1, country)
#            if newStreetInfo==streetInfo:
#                self.getEdgePartName(result, streetInfo)
#       
#        resultList=self.getEdgeEntryForTarget(target)  
#        for result in resultList:
#            edgeId, startRef, endRef, length, oneway1, wayId1, source1, target1, refList, maxspeed, country=result
#            if edgeId in self.doneEdges:
#                continue
#            if oneway1==1:
#                continue
#            
#            newStreetInfo=self.getStreetInfoWithWayId(wayId1, country)
#            if newStreetInfo==streetInfo:
#                self.getEdgePartName(result, streetInfo)
#      
#        resultList=self.getEdgeEntryForTarget(source)
#        for result in resultList:
#            edgeId, startRef, endRef, length, oneway1, wayId1, source1, target1, refList, maxspeed, country=result
#            if edgeId in self.doneEdges:
#                continue
#            if oneway1==1:
#                continue
#
#            newStreetInfo=self.getStreetInfoWithWayId(wayId1, country)
#            if newStreetInfo==streetInfo:
#                self.getEdgePartName(result, streetInfo)
#            
#        resultList=self.getEdgeEntryForSource(source)
#        for result in resultList:
#            edgeId, startRef, endRef, length, oneway1, wayId1, source1, target1, refList, maxspeed, country=result
#            if edgeId in self.doneEdges:
#                continue
#            if oneway==1 and oneway1==1:
#                continue
#
#            newStreetInfo=self.getStreetInfoWithWayId(wayId1, country)
#            if newStreetInfo==streetInfo:
#                self.getEdgePartName(result, streetInfo)

    def createEdgeTableEntries(self):
        self.setDBCursorForCountry(self.country)
        self.cursor.execute('SELECT * FROM wayTable')
        allWays=self.cursor.fetchall()
        for way in allWays:
            wayId, tags, refs, distances=self.wayFromDB(way)
            self.createEdgeTableEntriesForWay(wayId)

    def createEdgeTableNodeEntries(self):
        self.cursorGlobal.execute('SELECT id FROM edgeTable')
        allEdges=self.cursorGlobal.fetchall()
        for id in allEdges:
            edgeId=id[0]
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

        self.cursorGlobal.execute('SELECT id FROM edgeTable WHERE source==0 OR target==0')
        allEdges=self.cursorGlobal.fetchall()

        # TODO this includes edges with refs maybe outside of
        # the actual country
#        currentCountry=self.osmDataList[0]["polyCountry"]
        for id in allEdges:
            edgeId=id[0]
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
            
#            if oneway==1 and oneway1==1:
#                continue

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
            
#            if oneway1==1:
#                continue
            
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
            
    def createEdgeTableEntriesForWay(self, wayId):
        (wayId, tags, refs, distances)=self.getWayEntryForIdAndCountry(wayId, self.country)
        if wayId!=None:
            resultList=self.getCrossingEntryFor(wayId, self.country)
            
            nextWayDict=dict()
            for result in resultList:
                crossingId, wayId, refId, nextWayIdList=result
                nextWayDict[refId]=nextWayIdList
            
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
                
            if "access" in tags:
                if tags["access"]=="destination":
                    oneway=1

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
                    doneRefs.append(ref)
            
            refNodeList=list()
            distance=0
            i=0
            for ref in refs:
                if ref in doneRefs:
                    if len(refNodeList)!=0:
                        refNodeList.append(ref)
#                        if i+1<len(distances):
#                            distance=distance+distances[i+1]
                            
                        startRef=refNodeList[0]
                        endRef=refNodeList[-1]

                        self.addToEdgeTable(startRef, endRef, distance, oneway, wayId, refNodeList, maxspeed, self.country)
                            
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

                    self.addToEdgeTable(startRef, endRef, distance, oneway, wayId, refNodeList, maxspeed, self.country)

    def getStreetTrackList(self, wayid):
        if wayid in self.streetIndex:
            return self.streetIndex[wayid]["track"]
        return None

    def createCrossingEntries(self):
        self.setDBCursorForCountry(self.country)
        self.cursor.execute('SELECT * FROM wayTable')
        allWays=self.cursor.fetchall()
        for way in allWays:
            wayid, tags, refs, distances=self.wayFromDB(way)     
            
#            streetInfo=None
#            if "name" in tags or "ref" in tags:
#                streetInfo=self.getStreetNameInfo(tags) 
                
            crossingType=1
            for ref in refs:  
                nextWays=self.findWayWithRefInAllWays(ref, wayid)  
                if len(nextWays)!=0:
                    wayList=list()
                    for (wayid2, tags2, refs2) in nextWays:
#                        if streetInfo!=None:
#                            if "name" in tags or "ref" in tags2:
#                                newStreetInfo=self.getStreetNameInfo(tags2) 
#                                if streetInfo==newStreetInfo:
#                                    continue

                        wayList.append((wayid2, crossingType))
                    
                    if len(wayList)!=0:
                        self.addToCrossingsTable(wayid, ref, wayList)
                        
    def parse(self, country):
        p = OSMParser(2, nodes_callback=self.parse_nodes, 
                  ways_callback=self.parse_ways, 
                  relations_callback=None,
                  coords_callback=self.parse_coords)
        p.parse(self.getOSMFile(country))

    def getOSMFile(self, country):
        return self.osmList[country]["osmFile"]
    
    def getDataDir(self):
        return os.path.join(os.environ['HOME'], "workspaces", "pydev", "car-dash", "data")
    
    def getDBFile(self, country):
        file=os.path.basename(self.getOSMFile(country))+".db"
        return os.path.join(self.getDataDir(), file)

    def getGlobalDBFile(self):
        file="global.db"
        return os.path.join(self.getDataDir(), file)
    
    def getAdressDBFile(self):
        file="adress.db"
        return os.path.join(self.getDataDir(), file)
    
    def dbExists(self, country):
        return os.path.exists(self.getDBFile(country))

    def globalDBExists(self):
        return os.path.exists(self.getGlobalDBFile())
        
    def initGraph(self):
        if self.dWrapper==None:
#            self.dWrapper=DijkstraWrapperPygraph(self.cursorGlobal)
            self.dWrapper=DijkstraWrapperIgraph(self.cursorGlobal)

        if not self.dWrapper.isGraphLoaded():
            print("init graph")
            self.dWrapper.initGraph()
            print("init graph done")

    def initDB(self):
        createAllDB=not self.globalDBExists()
        if createAllDB:
            self.openGlobalDB()
            self.createGlobalTables()
            
            self.openAdressDB()
            self.createAdressTable()
            
            for country in self.osmList.keys():
                self.country=country
                self.debugCountry=country
                
                createDB=not self.dbExists(country)
        
                if createDB:
                    print(self.osmList[country])
                    self.initCountryData()
                    self.openCountryDB(country)
                    self.createCountryTables()
                    print("start parsing")
                    self.parse(country)
                    print("end parsing")
                    
                    print("add refs")
                    self.addAllRefsToDB()
                    print("end add refs")
        
                    print("collect streets")
                    self.collectWaysByName()
                    print("end collect streets")
                    
                    print("create crossings")
                    self.createCrossingEntries()
                    print("end create crossings")
                    
                    print("create edges")
                    self.createEdgeTableEntries()
                    print("end create edges")                    
                                
            print("create edge nodes")
            self.createEdgeTableNodeEntries()
            print("end create edge nodes")

            self.initGraph()

            self.closeAllDB()
           
                        
    def initBoarders(self):
        self.bu=OSMBoarderUtils()
        self.bu.initData()
        
    def countryNameOfPoint(self, lat, lon):
        return self.bu.countryNameOfPoint(lat, lon)
    
    def getOSMDataInfo(self):
        osmDataList=dict()
        osmData=dict()
        osmData["country"]="austria"
        osmData["osmFile"]='/home/maxl/Downloads/salzburg.osm'
        osmData["poly"]="austria.poly"
        osmData["polyCountry"]="Europe / Western Europe / Austria"
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
        
#    p.initGraph()
    p.closeAllDB()


if __name__ == "__main__":
    main(sys.argv)  
    

