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
from osmparser.dijkstrawrapper import DijkstraWrapper
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
        wayId, usedRefId, usedPos=osmParserData.getWayIdForPos(self.lat, self.lon)
        if wayId==None:
            print("resolveFromPos not found for %f %f"%(self.lat, self.lon))

        resultList=osmParserData.getEdgeEntryForWayId(wayId)
        
        self.lat=usedPos[0]
        self.lon=usedPos[1]
            
        targetFound=False
        for result in resultList:
            if targetFound:
                break
            
            (edgeId, startRef, endRef, length, oneway, wayId, source1, target1, refList, maxspeed)=result

            for edgeRef in refList:
                if edgeRef==usedRefId:
                    (self.lat, self.lon)=osmParserData.getCoordsWithRef(edgeRef)
                    self.edgeId=edgeId
                    self.target=target1
                    self.source=source1
                    self.usedRefId=edgeRef
                    self.wayId=wayId
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
    def __init__(self, file):
        self.nodes = dict()
        self.coords = dict()
        self.relations = dict()
        self.track=list()
        self.trackWayList=list()
        self.streetNameIndex=dict()
        self.streetIndex=dict()
        self.file=file
        self.wayRefIndex=dict()
        self.wayToStreetIndex=dict()
        self.connection=None
        self.cursor=None
        self.edgeId=0
        self.actLevel=0
        self.wantLevel=0
        self.trackItemList=list()
        self.doneEdges=list()
        self.edgeList=list()
        self.crossingId=0
        self.nodeId=1
        self.dWrapper=None
        self.osmutils=OSMUtils()
        self.initBoarders()
        self.initOSMDataInfo()
        
    def createTables(self):
        self.createRefTable()
        self.createWayTable()
        self.createStreetTable()
        self.createCrossingsTable()
        self.createEdgeTable()

    def openDB(self):
        self.connection=sqlite3.connect(self.getDBFile())
        self.cursor=self.connection.cursor()   

    def createRefTable(self):
        self.cursor.execute('CREATE TABLE refTable (refId INTEGER PRIMARY KEY, lat REAL, lon REAL, ways BLOB)')
    
    def createWayTable(self):
        self.cursor.execute('CREATE TABLE wayTable (wayId INTEGER PRIMARY KEY, tags BLOB, refs BLOB, refsDistance BLOB)')

    def createStreetTable(self):
        self.cursor.execute('CREATE TABLE streetTable (street TEXT PRIMARY KEY, wayIdList BLOB)')
    
    def createCrossingsTable(self):
        self.cursor.execute('CREATE TABLE crossingTable (id INTEGER PRIMARY KEY, wayId INTEGER, refId INTEGER, nextWayIdList BLOB)')

    def createEdgeTable(self):
        self.cursor.execute('CREATE TABLE edgeTable (id INTEGER PRIMARY KEY, startRef INTEGER, endRef INTEGER, length INTEGER, oneway BOOL, wayID INTEGER, source INTEGER, target INTEGER, refList BLOB, maxspeed INTEGER)')
 
    def addToRefTable(self, refid, lat, lon, wayIdList):
        self.cursor.execute('INSERT INTO refTable VALUES( ?, ?, ?, ?)', (refid, lat, lon, pickle.dumps(wayIdList)))

    def addToWayTable(self, wayid, tags, refs, distances):
        self.cursor.execute('INSERT INTO wayTable VALUES( ?, ?, ?, ?)', (wayid, pickle.dumps(tags), pickle.dumps(refs), pickle.dumps(distances)))

    def addToStreetTable(self, streetInfo, wayidList):
        (name, ref)=streetInfo
        streetInfoString=name+"_"+ref
        self.cursor.execute('INSERT INTO streetTable VALUES( ?, ?)', (streetInfoString, pickle.dumps(wayidList)))

    def addToCrossingsTable(self, wayid, refId, nextWaysList):
        self.cursor.execute('INSERT INTO crossingTable VALUES( ?, ?, ?, ?)', (self.crossingId, wayid, refId, pickle.dumps(nextWaysList)))
        self.crossingId=self.crossingId+1

    def addToEdgeTable(self, startRef, endRef, length, oneway, wayId, refList, maxspeed):
        self.cursor.execute('INSERT INTO edgeTable VALUES( ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (self.edgeId, startRef, endRef, length, oneway, wayId, 0, 0, pickle.dumps(refList), maxspeed))
        self.edgeId=self.edgeId+1
    
    def updateSourceOfEdge(self, edgeId, sourceId):
        existingEdgeId, startRef, endRef, length, oneway, wayId, source, target, refList, maxspeed=self.getEdgeEntryForEdgeId(edgeId)
        if existingEdgeId==None:
            print("no edge with id %d"%(edgeId))
            return
        self.cursor.execute('REPLACE INTO edgeTable VALUES( ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (edgeId, startRef, endRef, length, oneway, wayId, sourceId, target, pickle.dumps(refList), maxspeed))

    def updateTargetOfEdge(self, edgeId, targetId):
        existingEdgeId, startRef, endRef, length, oneway, wayId, source, target, refList, maxspeed=self.getEdgeEntryForEdgeId(edgeId)
        if existingEdgeId==None:
            print("no edge with id %d"%(edgeId))
            return
        self.cursor.execute('REPLACE INTO edgeTable VALUES( ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (edgeId, startRef, endRef, length, oneway, wayId, source, targetId, pickle.dumps(refList), maxspeed))     
      
    def getEdgeEntryForSource(self, sourceId):
        self.cursor.execute('SELECT * FROM edgeTable where source=="%s"'%(str(sourceId)))
        resultList=list()
        allentries=self.cursor.fetchall()
        for result in allentries:
            edge=self.edgeFromDB(result)
            resultList.append(edge)
        return resultList      
    
    def getEdgeEntryForTarget(self, targetId):
        self.cursor.execute('SELECT * FROM edgeTable where target=="%s"'%(str(targetId)))
        resultList=list()
        allentries=self.cursor.fetchall()
        for result in allentries:
            edge=self.edgeFromDB(result)
            resultList.append(edge)
        return resultList      
    
    def getEdgeEntryForSourceAndTarget(self, sourceId, targetId):
        self.cursor.execute('SELECT * FROM edgeTable where source=="%s" AND target=="%s"'%(str(sourceId), str(targetId)))
        resultList=list()
        allentries=self.cursor.fetchall()
        for result in allentries:
            edge=self.edgeFromDB(result)
            resultList.append(edge)
        return resultList   
    
    def getEdgeEntryForEdgeId(self, edgeId):
        self.cursor.execute('SELECT * FROM edgeTable where id=="%s"'%(str(edgeId)))
        allentries=self.cursor.fetchall()
        if len(allentries)==1:
            edge=self.edgeFromDB(allentries[0])
            return edge
        print("no edge with %d"%(edgeId))
        return (None, None, None, None, None, None, None, None, None, None)
        
    def getEdgeEntryForStartPoint(self, startRef, edgeId):
        self.cursor.execute('SELECT * FROM edgeTable where startRef="%s" AND id!="%s"'%(str(startRef), str(edgeId)))
        resultList=list()
        allentries=self.cursor.fetchall()
        for result in allentries:
            edge=self.edgeFromDB(result)
            resultList.append(edge)
        return resultList
 
    def getEdgeEntryForEndPoint(self, endRef, edgeId):
        self.cursor.execute('SELECT * FROM edgeTable where endRef=="%s" AND id!="%s"'%(str(endRef), str(edgeId)))
        resultList=list()
        allentries=self.cursor.fetchall()
        for result in allentries:
            edge=self.edgeFromDB(result)
            resultList.append(edge)
        return resultList
    
    def getEdgeEntryForWayId(self, wayId):
        self.cursor.execute('SELECT * FROM edgeTable where wayId=="%s"'%(str(wayId)))
        resultList=list()
        allentries=self.cursor.fetchall()
        for result in allentries:
            edge=self.edgeFromDB(result)
            resultList.append(edge)
        return resultList
    
    def getRefEntryForId(self, refId):
        self.cursor.execute('SELECT * FROM refTable where refId==%s'%(str(refId)))
        allentries=self.cursor.fetchall()
        if len(allentries)==1:
            return self.refFromDB(allentries[0])
        
        return (None, None, None, None)

    def getWayEntryForId(self, wayId):
        self.cursor.execute('SELECT * FROM wayTable where wayId==%s'%(str(wayId)))
        allentries=self.cursor.fetchall()
        if len(allentries)==1:
            return self.wayFromDB(allentries[0])
        
        return (None, None, None, None)
    
    def getStreetEntryForName(self, streetInfo):
        (name, ref)=streetInfo
        streetInfoString=name+"_"+ref
        self.cursor.execute('SELECT * FROM streetTable where street=="%s"'%(str(streetInfoString)))
        allentries=self.cursor.fetchall()
        if len(allentries)==1:
            return self.streetFromDB(allentries[0])
        
        return (None, None, None)
    
    def getCrossingEntryFor(self, wayid):
        self.cursor.execute('SELECT * FROM crossingTable where wayId=="%s"'%(str(wayid)))
        
        resultList=list()
        allentries=self.cursor.fetchall()
        for result in allentries:
            crossing=self.crossingFromDB(result)
            resultList.append(crossing)
            
        return resultList
    
    def getCrossingEntryForRefId(self, wayid, refId):
        self.cursor.execute('SELECT * FROM crossingTable where wayId=="%s" AND refId=="%s"'%(str(wayid), str(refId)))
        
        resultList=list()
        allentries=self.cursor.fetchall()
        for result in allentries:
            crossing=self.crossingFromDB(result)
            resultList.append(crossing)
            
        return resultList
    
    def testRefTable(self):
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
        nodes=self.getNearNodes(actlat, actlon)
#        print(nodes)
        minDistance=1000
        minWayId=0
        usedRefId=0
        if len(nodes)==0:
            return None, None, (None, None)
        
        for (refId, lat, lon, wayIdList) in nodes:  
            (revLat, revLon)=self.getCoordsWithRef(refId)
 
            for wayId in wayIdList:
                # find matching way by creating interpolation points betwwen refs
                (wayId, tags, refs, distances)=self.getWayEntryForId(wayId)
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
        return minWayId, usedRefId, (usedLat, usedLon) 
        
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
            
    def getNearNodes(self, lat, lon):
        latRangeMax=lat+0.003
        lonRangeMax=lon+0.003
        latRangeMin=lat-0.003
        lonRangeMin=lon-0.003
        
        nodes=list()
        self.cursor.execute('SELECT * FROM refTable where lat>%s AND lat<%s AND lon>%s AND lon<%s'%(latRangeMin, latRangeMax, lonRangeMin, lonRangeMax))
        allentries=self.cursor.fetchall()
        for x in allentries:
            refId, lat1, lon1, wayIdList=self.refFromDB(x)
            distance=self.osmutils.distance(lat, lon, lat1, lon1)
            if distance>1000:
                continue
            nodes.append((refId, lat1, lon1, wayIdList))

        return nodes
    
    def testWayTable(self):
        self.cursor.execute('SELECT * FROM wayTable')
        allentries=self.cursor.fetchall()
        for x in allentries:
            wayId, tags, refs, distances=self.wayFromDB(x)
            print( "way: " + str(wayId) + "  tags: " + str(tags) + "  refs: " + str(refs) + " distances: "+str(distances))

    def testStreetTable(self):
        self.cursor.execute('SELECT * FROM streetTable')
        allentries=self.cursor.fetchall()
        for x in allentries:
            name, ref, wayIdList=self.streetFromDB(x)
            print( "name: " + name + " ref:"+ref+ " wayIdList: " + str(wayIdList))

    def testCrossingTable(self):
        self.cursor.execute('SELECT * FROM crossingTable')
        allentries=self.cursor.fetchall()
        for x in allentries:
            id, wayid, refId, wayIdList=self.crossingFromDB(x)
            print( "id: "+ str(id) + " wayid: " + str(wayid) +  " refId: "+ str(refId) + " wayIdList: " + str(wayIdList))
        
    def testEdgeTable(self):
        self.cursor.execute('SELECT * FROM edgeTable')
        allentries=self.cursor.fetchall()
        for x in allentries:
            edgeId, startRef, endRef, length, oneway, wayId, source, target, refList, maxspeed=self.edgeFromDB(x)
            print( "edgeId: "+str(edgeId) +" startRef: " + str(startRef)+" endRef:"+str(endRef)+ " length:"+str(length)+ " oneway: "+str(oneway)+ " wayId:"+str(wayId) +" source:"+str(source)+" target:"+str(target) +" refList:"+str(refList) + " maxspeed: "+str(maxspeed))

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
        return (edgeId, startRef, endRef, length, oneway, wayId, source, target, refList, maxspeed)
                
    def commitDB(self):
        self.connection.commit()
        
    def closeDB(self):
        self.commitDB()
        self.cursor.close()
        
    def addAllRefsToDB(self):
        for ref, wayIdList in self.wayRefIndex.items():
            try:
                lat=self.coords[ref][1]
                lon=self.coords[ref][0]
            except KeyError:
                continue
            self.addToRefTable(ref, lat, lon, wayIdList)
            

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

    def collectWaysByName(self):
        street_by_name=dict()
        self.cursor.execute('SELECT * FROM wayTable')
        allWays=self.cursor.fetchall()
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
            self.addToStreetTable((name, ref), wayIdList)
        
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

#        else:
#            print(str(tags))

        return (name, ref)
    
    def getWaysWithRef(self, ref):
#        if ref in self.wayRefIndex:
#            return self.wayRefIndex[ref]
        (refId, lat, lon, wayIdList)=self.getRefEntryForId(ref)
        if refId!=None:
            return wayIdList
        
        return None

    def getStreetInfoWithWayId(self, wayId):
        (id, tags, refs, distances)=self.getWayEntryForId(wayId)
        if id!=None:
            (name, ref)=self.getStreetNameInfo(tags)
            return (name, ref)
        return (None, None)
        
    def getCoordsWithRef(self, ref):
        (refId, lat, lon, wayIdList)=self.getRefEntryForId(ref)
        if refId!=None:
            return (lat, lon)
        
        return (None, None)
    
    def findWayWithRefInAllWays(self, ref, fromWayId):
        possibleWays=list()
        wayIdList=self.getWaysWithRef(ref)
        if wayIdList==None:
            return possibleWays
        
        for wayid in wayIdList:
            if wayid==fromWayId:
                continue
            
            (id, tags, refs, distances)=self.getWayEntryForId(wayid)
            if id==None:
                print("no entry in way DB for "+str(wayid))
                continue
            
            for wayRef in refs:
                if wayRef==ref:
                    possibleWays.append((wayid, tags, refs))
 
        return possibleWays
    
    def findWayWithEndRef(self, ways, endRef):
        possibleWays=list()
        for wayId  in ways:
            (actWayId, tags, refs, distances)=self.getWayEntryForId(wayId)
            if refs[-1]==endRef:
                possibleWays.append(actWayId)
        return possibleWays
    
    def findStartWay(self, ways):
        for wayId  in ways:
            (actWayId, tags, refs, distances)=self.getWayEntryForId(wayId)
            startRef=refs[0]
            possibleWays=self.findWayWithEndRef(ways, startRef)
            if len(possibleWays)==0:
                return actWayId
        return ways[0]
                 
    def getStreetList(self):
        self.cursor.execute('SELECT * FROM streetTable')
        allentries=self.cursor.fetchall()
        streetList=dict()
        for x in allentries:
            name, ref, wayIdList=self.streetFromDB(x)
            streetList[(name, ref)]=wayIdList

        return streetList
    
    def getTrackListByName(self, name, ref):
        if not (name, ref) in self.streetNameIndex.keys():
            self.postprocessWay(name, ref)
        
        trackList=list()
        if (name, ref) in self.streetNameIndex.keys():
            tracks=self.streetNameIndex[(name, ref)]
            for track in tracks:
                trackList.append(self.streetIndex[track])
            
        return trackList
                
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
            for point in routingPointList[:-1]:
            # find out if last edge goes through the end point
            # if yes we need to shorten it
            # if no we need to add the last points
            # same is true for the actual starting point

                if point.getSource()==0:
                    point.resolveFromPos(self)
                source=point.getSource()
                
                targetPoint=routingPointList[i+1]
                if targetPoint.getSource()==0:
                    targetPoint.resolveFromPos(self)
                        
                target=targetPoint.getTarget()
                
                print(point.getWayId())
                print(point.getRefId())

                print(targetPoint.getWayId())
                print(targetPoint.getRefId())
                
                print(source)
                print(target) 
                
                if source==0 and target==0:
                    print("source and target==0!")
                    break

                if targetPoint.getSource()==point.getSource() and targetPoint.getTarget()==point.getTarget() and targetPoint.getWayId()==point.getWayId():
                    print("source and target equal!")
                    allEdgeList.append(point.getEdgeId())
#                    allPathCost=allPathCost+pathCost            
                else:                  
                    if self.dWrapper!=None:
                        edgeList, pathCost=self.dWrapper.computeShortestPath(source, target)
                        allEdgeList.extend(edgeList)
                        allPathCost=allPathCost+pathCost            
                
                i=i+1
                
            return allEdgeList, allPathCost

        return None, None

    def createTrackForEdgeList(self, edgeList, routingPointList):
        if edgeList!=None:
            return self.printEdgeList(edgeList, routingPointList)
        
    def showWay(self, wayId, usedRefId, level):
        self.edgeList=list()
        self.getEdgeListForWayLevels(wayId, usedRefId, level)
        return self.printEdgeList(self.edgeList)
    
    def showWayWithName(self, name, ref):
        name, ref, wayIdList=self.getStreetEntryForName((name, ref))
        if name==None:
            print("street with name %s and ref %snot found"%(name, ref))
            return
                
        self.edgeList=list()
        self.possibleWays=wayIdList
        while len(self.possibleWays)!=0:
            wayId=self.findStartWay(self.possibleWays)
            (actWayId, tags, refs, distances)=self.getWayEntryForId(wayId)
            startRef=refs[0]
            
            resultList=self.getEdgeEntryForStartPoint(startRef, wayId)
            if len(resultList)==0:
                print("no start edge found for way %d"%(wayId))
                continue
    
            self.getEdgeListForWayName(resultList[0], (name, ref))
        return self.printEdgeList(self.edgeList)
    
    def printEdge(self, edgeId, trackWayList):
        result=self.getEdgeEntryForEdgeId(edgeId)
        print(result)
        (edgeId, _, _, length, oneway, wayId, _, _, refList, maxspeed)=result
        (wayId, tags, _, _)=self.getWayEntryForId(wayId)

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
            resultList=self.getCrossingEntryForRefId(wayId, ref)
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
        (edgeId, _, _, length, oneway, wayId, _, _, _, maxspeed)=result
        (wayId, tags, _, _)=self.getWayEntryForId(wayId)

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
            resultList=self.getCrossingEntryForRefId(wayId, ref)
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
           
#        trackWayList.append(self.createEndTrackItem())
    
#    def printEdgeToRoutingPoint(self, routingPoint, wayId, trackWayList):
#        (wayId, tags, _, _)=self.getWayEntryForId(wayId)
#
#        if "highway" in tags:
#            streetType=tags["highway"]
#            
#        (name, ref)=self.getStreetNameInfo(tags)
#
#        print("added line to routing end point from %d"%(routingPoint.getRefId()))
#        trackItem=dict()
#        trackItem["wayId"]=wayId
#        trackItem["ref"]=routingPoint.getRefId()
#        trackItem["lat"]=routingPoint.getLat()
#        trackItem["lon"]=routingPoint.getLon()        
#        trackItem["oneway"]=False
#        trackItem["type"]=streetType
#        trackItem["info"]=(name, ref)
#        trackItem["maxspeed"]=30
##        trackItem["length"]=length
#
#        trackWayList.append(trackItem)
           
    def printEdgeList(self, edgeList, routingPointList):
        trackWayList=list()
        track=dict()
        track["name"]=""
               
        endPoint=routingPointList[-1]
        routeEndRefId=endPoint.getRefId()
        endEdgeId=endPoint.getEdgeId()

        startPoint=routingPointList[0]
        routeStartRefId=startPoint.getRefId()
        startEdgeId=startPoint.getEdgeId()
     
        currentRefList=None

        if len(edgeList)==1:
            (startEdgeId, _, _, _, _, _, _, _, startRefList, _)=self.getEdgeEntryForEdgeId(startEdgeId)                       
            indexStart=startRefList.index(routeStartRefId)
            indexEnd=startRefList.index(routeEndRefId)
            if indexEnd < indexStart:
                startRefList.reverse()
            self.printEdgeForRefList(startRefList, startEdgeId, trackWayList, routeEndRefId, routeStartRefId)  
        else:
            firstEdgeId=edgeList[0]
            (firstEdgeId, firstStartRef, firstEndRef, _, _, _, _, _, refList, _)=self.getEdgeEntryForEdgeId(firstEdgeId)                       

#            (lat, lon)=self.getCoordsWithRef(routeStartRefId)
#            if lat!=startPoint.getLat() and lon!=startPoint.getLon():
#                self.printEdgeToRoutingPoint(startPoint, startPoint.getWayId(), trackWayList)

            if not routeStartRefId in refList:
                (startEdgeId, startStartRef, startEndRef, _, _, _, _, _, startRefList, _)=self.getEdgeEntryForEdgeId(startEdgeId)                       
            
                if firstStartRef==startStartRef or firstEndRef==startStartRef:
                    startRefList.reverse()
                print("add start edge")
                self.printEdgeForRefList(startRefList, startEdgeId, trackWayList, None, routeStartRefId)
                currentRefList=startRefList
                routeStartRefId=None

            for edgeId in edgeList:
                (edgeId, currentStartRef, currentEndRef, _, _, _, _, _, refList, _)=self.getEdgeEntryForEdgeId(edgeId)                       
    
                if currentRefList!=None:
                    if currentRefList[-1]!=refList[0]:
                        refList.reverse()
                else:
                    nextEdgeId=edgeList[1]
                    (nextEdgeId, nextStartRef, nextEndRef, _, _, _, _, _, _, _)=self.getEdgeEntryForEdgeId(nextEdgeId)                       
    
                    if nextStartRef==currentStartRef or nextEndRef==currentStartRef:
                        refList.reverse()
    
                self.printEdgeForRefList(refList, edgeId, trackWayList, routeEndRefId, routeStartRefId)
                
                currentRefList=refList
                routeStartRefId=None
                                         
            if not routeEndRefId in currentRefList:      
                (endEdgeId, _, _, _, _, _, _, _, endRefList, _)=self.getEdgeEntryForEdgeId(endEdgeId)
                if currentRefList[-1]!=endRefList[0]:
                    endRefList.reverse()
                print("add end edge")
                self.printEdgeForRefList(endRefList, endEdgeId, trackWayList, routeEndRefId, None)

#            (lat, lon)=self.getCoordsWithRef(routeEndRefId)
#            if lat!=endPoint.getLat() and lon!=endPoint.getLon():
#                self.printEdgeToRoutingPoint(endPoint, endPoint.getWayId(), trackWayList)
            
        track["track"]=trackWayList
        trackList=list()
        trackList.append(track)
        return trackList    

    def getEdgeListForWayLevels(self, wayId, usedRefId, level):
        self.wantLevel=level
        self.level=0
        print(wayId)
        print(usedRefId)
                
        startRefFound=False

        resultList=self.getEdgeEntryForWayId(wayId)
        for result in resultList:
            if startRefFound:
                break
            
            (edgeId, startRef, endRef, length, oneway, wayId, source, target, refList, maxspeed)=result

            for edgeRef in refList:
                if edgeRef==usedRefId:
                    startEdge=edgeId
                    startRefFound=True
                    break
                
        print(startEdge)
        self.doneEdges=list()
        result=self.getEdgeEntryForEdgeId(startEdge)

        self.getEdgePartLevels(result)
        print(self.edgeList)

    def getEdgePartLevels(self, edge):
        (edgeId, startRef, endRef, length, oneway, wayId, source, target, refList, maxspeed)=edge

        self.doneEdges.append(edgeId)
        self.edgeList.append(edgeId)

        if self.level==self.wantLevel:
            return
        
        print(edge)
        
        if target!=0:
            resultList=self.getEdgeEntryForSource(target)  
            for result in resultList:
                edgeId, startRef, endRef, length, oneway1, wayId, source1, target1, refList, maxspeed=result
                if edgeId in self.doneEdges:
                    continue
                
                self.level=self.level+1
                self.getEdgePartLevels(result)
                self.level=self.level-1
        
        if target!=0:
            resultList=self.getEdgeEntryForTarget(target)  
            for result in resultList:
                edgeId, startRef, endRef, length, oneway1, wayId, source1, target1, refList, maxspeed=result
                if edgeId in self.doneEdges:
                    continue
                if oneway1==1:
                    continue
                
                self.level=self.level+1
                self.getEdgePartLevels(result)
                self.level=self.level-1      
      
        if source!=0:
            resultList=self.getEdgeEntryForTarget(source)
            for result in resultList:
                edgeId, startRef, endRef, length, oneway1, wayId, source1, target1, refList, maxspeed=result
                if edgeId in self.doneEdges:
                    continue
                if oneway1==1:
                    continue

                self.level=self.level+1
                self.getEdgePartLevels(result)
                self.level=self.level-1
            
        if source!=0:
            resultList=self.getEdgeEntryForSource(source)
            for result in resultList:
                edgeId, startRef, endRef, length, oneway1, wayId, source1, target1, refList, maxspeed=result
                if edgeId in self.doneEdges:
                    continue
                if oneway==1 and oneway1==1:
                    continue

                self.level=self.level+1
                self.getEdgePartLevels(result)
                self.level=self.level-1
                
    def getEdgeListForWayName(self, edge, streetInfo):        
        self.doneEdges=list()
                
        self.getEdgePartName(edge, streetInfo)
        
    def getEdgePartName(self, edge, streetInfo):
        (edgeId, startRef, endRef, length, oneway, wayId, source, target, refList, maxspeed)=edge

        self.doneEdges.append(edgeId)
        if wayId in self.possibleWays:
            self.possibleWays.remove(wayId)
        self.edgeList.append(edgeId)
                
        print(edge)
        
        resultList=self.getEdgeEntryForSource(target)  
        for result in resultList:
            edgeId, startRef, endRef, length, oneway1, wayId1, source1, target1, refList, maxspeed=result
            if edgeId in self.doneEdges:
                continue
            
            newStreetInfo=self.getStreetInfoWithWayId(wayId1)
            if newStreetInfo==streetInfo:
                self.getEdgePartName(result, streetInfo)
       
        resultList=self.getEdgeEntryForTarget(target)  
        for result in resultList:
            edgeId, startRef, endRef, length, oneway1, wayId1, source1, target1, refList, maxspeed=result
            if edgeId in self.doneEdges:
                continue
            if oneway1==1:
                continue
            
            newStreetInfo=self.getStreetInfoWithWayId(wayId1)
            if newStreetInfo==streetInfo:
                self.getEdgePartName(result, streetInfo)
      
        resultList=self.getEdgeEntryForTarget(source)
        for result in resultList:
            edgeId, startRef, endRef, length, oneway1, wayId1, source1, target1, refList, maxspeed=result
            if edgeId in self.doneEdges:
                continue
            if oneway1==1:
                continue

            newStreetInfo=self.getStreetInfoWithWayId(wayId1)
            if newStreetInfo==streetInfo:
                self.getEdgePartName(result, streetInfo)
            
        resultList=self.getEdgeEntryForSource(source)
        for result in resultList:
            edgeId, startRef, endRef, length, oneway1, wayId1, source1, target1, refList, maxspeed=result
            if edgeId in self.doneEdges:
                continue
            if oneway==1 and oneway1==1:
                continue

            newStreetInfo=self.getStreetInfoWithWayId(wayId1)
            if newStreetInfo==streetInfo:
                self.getEdgePartName(result, streetInfo)

    def createEdgeTableEntries(self):
        self.cursor.execute('SELECT * FROM wayTable')
        allWays=self.cursor.fetchall()
        for way in allWays:
            wayId, tags, refs, distances=self.wayFromDB(way)
            self.createEdgeTableEntriesForWay(wayId)

    def createEdgeTableNodeEntries(self):
        self.cursor.execute('SELECT id FROM edgeTable')
        allEdges=self.cursor.fetchall()
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

        self.cursor.execute('SELECT id FROM edgeTable WHERE source==0 OR target==0')
        allEdges=self.cursor.fetchall()

        # TODO this includes edges with refs maybe outside of
        # the actual country
        currentCountry=self.osmDataList[0]["polyCountry"]
        for id in allEdges:
            edgeId=id[0]
            edge=self.getEdgeEntryForEdgeId(edgeId)
            edgeId, startRef, endRef, length, oneway, wayId, source, target, refList, maxspeed=edge
            
            (lat, lon)=self.getCoordsWithRef(endRef)
            if lat!=None and lon!=None:
                pointCountry=self.countryNameOfPoint(lat, lon)
                if currentCountry!=pointCountry:
                    print("ref %d is in country %s"%(endRef, pointCountry))
            (lat, lon)=self.getCoordsWithRef(startRef)
            if lat!=None and lon!=None:
                pointCountry=self.countryNameOfPoint(lat, lon)
                if currentCountry!=pointCountry:
                    print("ref %d is in country %s"%(startRef, pointCountry))
            
            if source==0:
                sourceId=self.nodeId
                self.nodeId=self.nodeId+1
                self.updateSourceOfEdge(edgeId, sourceId)
            if target==0:
                targetId=self.nodeId
                self.nodeId=self.nodeId+1
                self.updateTargetOfEdge(edgeId, targetId)

        self.cursor.execute("CREATE INDEX source_idx ON edgeTable (source)")
        self.cursor.execute("CREATE INDEX target_idx ON edgeTable (target)")
   
    def createEdgeTableNodeSameStartEnriesFor(self, edge):
        edgeId, startRef, endRef, length, oneway, wayId, sourceId, targetId, refList, maxspeed =edge
                           
        resultList=self.getEdgeEntryForStartPoint(startRef, edgeId)
        if len(resultList)!=0:
            if sourceId==0:
                sourceId=self.nodeId
                self.nodeId=self.nodeId+1
    
        for result in resultList:
            edgeId1, l1, l2, l3, oneway1, wayId1, source1, target1, l6, maxspeed=result
            if source1!=0:
                continue
            
#            if oneway==1 and oneway1==1:
#                continue

            self.updateSourceOfEdge(edgeId, sourceId)
            self.updateSourceOfEdge(edgeId1, sourceId)

    def createEdgeTableNodeSameEndEnriesFor(self, edge):
        edgeId, startRef, endRef, length, oneway, wayId, sourceId, targetId, refList, maxspeed=edge
                           
        resultList=self.getEdgeEntryForEndPoint(endRef, edgeId)
        if len(resultList)!=0:
            if targetId==0:
                targetId=self.nodeId
                self.nodeId=self.nodeId+1
            
        for result in resultList:
            edgeId1, l1, l2, l3, oneway1, wayId1, source1, target1, l6, maxspeed=result
            if target1!=0:
                continue
            
#            if oneway1==1:
#                continue
            
            self.updateTargetOfEdge(edgeId, targetId)
            self.updateTargetOfEdge(edgeId1, targetId)
            
    def createEdgeTableNodeSourceEnriesFor(self, edge):
        edgeId, startRef, endRef, length, oneway, wayId, sourceId, targetId, refList, maxspeed=edge
        
        resultList=self.getEdgeEntryForStartPoint(endRef, edgeId)        
        if len(resultList)!=0:
            if targetId==0:
                targetId=self.nodeId
                self.nodeId=self.nodeId+1

        for result in resultList:
            edgeId1, l1, l2, l3, oneway1, wayId1, source1, target1, l6, maxspeed=result
            
            if source1==0:
                self.updateSourceOfEdge(edgeId1, targetId)
                self.updateTargetOfEdge(edgeId, targetId)
            else:
                self.updateTargetOfEdge(edgeId, source1)
                
            
#    def createEdgeTableNodeTargetEnriesFor(self, edge):
#        edgeId, startRef, endRef, length, oneway, wayId, sourceId, targetId, refList=edge
#                           
#        resultList=self.getEdgeEntryForEndPoint(startRef, edgeId)
#        if len(resultList)!=0:
#            if sourceId==0:
#                sourceId=self.nodeId
#                self.nodeId=self.nodeId+1
#        
#        for result in resultList:
#            edgeId1, l1, l2, l3, oneway1, wayId1, source1, target1, l6=result
#
##            if oneway1==1:
##                continue
#
#            if target1==0:
#                self.updateSourceOfEdge(edgeId1, sourceId)
#                self.updateTargetOfEdge(edgeId, sourceId)
#            else:
#                self.updateTargetOfEdge(edgeId, target1)
            
    def createEdgeTableEntriesForWay(self, wayId):
        (id, tags, refs, distances)=self.getWayEntryForId(wayId)
        if id!=None:
            resultList=self.getCrossingEntryFor(wayId)
            
            nextWayDict=dict()
            for result in resultList:
                id, wayId, refId, nextWayIdList=result
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
                print("street with same start and end and not roundabout %d %s"%(wayId, str(tags)))
                
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
                    maxspeed=80
                
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

                        self.addToEdgeTable(startRef, endRef, distance, oneway, wayId, refNodeList, maxspeed)
                            
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

                    self.addToEdgeTable(startRef, endRef, distance, oneway, wayId, refNodeList, maxspeed)

    def getStreetTrackList(self, wayid):
        if wayid in self.streetIndex:
            return self.streetIndex[wayid]["track"]
        return None

    def createCrossingEntries(self):
        self.cursor.execute('SELECT * FROM wayTable')
        allWays=self.cursor.fetchall()
        for way in allWays:
            wayid, tags, refs, distances=self.wayFromDB(way)          
                
#            oneway=False
#            if "oneway" in tags:
#                if tags["oneway"]=="yes":
#                    oneway=True
#            if "junction" in tags:
#                if tags["junction"]=="roundabout":
#                    oneway=True
#            elif refs[0]==refs[-1]:
##                print("found way with same start and end and not roundabout %d %s"%(wayid, str(tags)))
#                oneway=True

            
            crossingType=1
            for ref in refs:  
                nextWays=self.findWayWithRefInAllWays(ref, wayid)  
                if len(nextWays)!=0:
                    wayList=list()
                    for (wayid2, tags2, refs2) in nextWays:
                        wayList.append((wayid2, crossingType))
                    
                    if len(wayList)!=0:
                        self.addToCrossingsTable(wayid, ref, wayList)

#                        newOneway=False
#                        newRoundabout=False
#                        if "oneway" in tags2:
#                            if tags2["oneway"]=="yes":
#                                newOneway=True
#                        if "junction" in tags2:
#                            if tags2["junction"]=="roundabout":
#                                newRoundabout=True
#                        # TODO hack
#                        elif refs2[0]==refs2[-1]:
#                            newRoundabout=True
#                                                        
#                        if not oneway: 
#                            if newOneway:
#                                if not refs2[0]==ref:
#                                    # crossing only if new oneway starts here
#                                    crossingType=0
#                        if newOneway:
#                            if refs2[-1]==ref:
#                                # no crossing with end of a oneway
#                                crossingType=0
##                        if not oneway and not newOneway:
##                            if not newRoundabout:
##                                if ref!=refs2[0] and ref!=refs2[-1]:
##                                    # crossing in middle of way
##                                    crossingType=1
#                            
#                        if not wayid2 in wayList:
#                            wayList.append((wayid2, crossingType))
                    

    def parse(self):
        p = OSMParser(1, nodes_callback=self.parse_nodes, 
                  ways_callback=self.parse_ways, 
                  relations_callback=None,
                  coords_callback=self.parse_coords)
        p.parse(self.file)


    def getDataDir(self):
        return os.path.join(os.environ['HOME'], "workspaces", "pydev", "car-dash", "data")
    
    def getDBFile(self):
        file=os.path.basename(self.file)+".db"
        return os.path.join(self.getDataDir(), file)
    
    def dbExists(self):
        return os.path.exists(self.getDBFile())
        
    def initGraph(self):
        if self.dWrapper==None:
            self.dWrapper=DijkstraWrapper(self.cursor)

        if not self.dWrapper.isGraphLoaded():
            print("init graph")
            self.dWrapper.initGraph()
            print("init graph done")

    def initDB(self):
        createDB=not self.dbExists()
        
        if createDB:
            self.openDB()
            self.createTables()
            print("start parsing")
            self.parse()
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
            
            self.closeDB()
            print("commited DB")
            
#        print("postprocess streets")
#        self.postprocessWays()
#        print("end postprocess streets")
            
    def initBoarders(self):
        self.bu=OSMBoarderUtils()
        self.bu.initData()
        
    def countryNameOfPoint(self, lat, lon):
        return self.bu.countryNameOfPoint(lat, lon)
    
    def initOSMDataInfo(self):
        self.osmDataList=list()
        osmData=dict()
        osmData["country"]="austria"
        osmData["osmFile"]='/home/maxl/Downloads/austria.osm.bz2'
        osmData["poly"]="austria.poly"
        osmData["polyCountry"]="Europe / Western Europe / Austria"
        self.osmDataList.append(osmData)
        
        osmData=dict()
        osmData["country"]="switzerland"
        osmData["osmFile"]='/home/maxl/Downloads/switzerland.osm.bz2'
        osmData["poly"]="switzerland.poly"
        osmData["polyCountry"]="Europe / Western Europe / Switzerland"
        self.osmDataList.append(osmData)
    
        osmData=dict()
        osmData["country"]="germany"
        osmData["osmFile"]='/home/maxl/Downloads/germany.osm.bz2'
        osmData["poly"]="germany.poly"
        osmData["polyCountry"]="Europe / Western Europe / Germany"
        self.osmDataList.append(osmData)
    
def main(argv):    
    try:
        osmFile=argv[1]
    except IndexError:
#        osmFile='/home/maxl/Downloads/austria.osm.bz2'
#        osmFile='/home/maxl/Downloads/salzburg-streets.osm.bz2'
        osmFile='/home/maxl/Downloads/salzburg-city-streets.osm'
#        osmFile='test1.osm'
    
    p = OSMParserData(osmFile)
    
    p.initDB()
    
    p.openDB()
#    p.initGraph()
    
#    p.testRefTable()
#    p.testWayTable()
#    p.testStreetTable()
#    p.testCrossingTable()
#    p.testEdgeTable()
        
#    l=p.getEdgeEntryForWayId(30525406)
#    for edge in l:
#        print(edge)
#
#    l=p.getEdgeEntryForWayId(30510253)
#    for edge in l:
#        print(edge)
#        
#    l=p.getEdgeEntryForWayId(82173348)
#    for edge in l:
#        print(edge)
        
#    print(p.getEdgeEntryForSourceAndTarget(3773, 1703))
#    print(p.getEdgeEntryForSourceAndTarget(1703, 3773))
#    print(p.getEdgeEntryForSourceAndTarget(3024, 821))
#    print(p.getEdgeEntryForSourceAndTarget(877, 887))
    
    # home to work
#    start=time.time()
#    print(p.dWrapper.computeShortestPath(1507, 7229))
#    stop=time.time()
#    dur=int(stop-start)
#    print(str(dur)+"s")
    
#    config=Config("routingTest.cfg")
#    section="routing"
#    if not config.hasSection(section):
#        config.addSection(section)
#
#    point1=OSMRoutingPoint("start", 0, 10.0, 20.0)
#    point2=OSMRoutingPoint("end", 1, 20.0, 30.0)
#    point3=OSMRoutingPoint("way", 2, 30.0, 40.0)
#
#    print(point1)    
#    print(point2)    
#    print(point3)    
#
#    point1.saveToConfig(config, section, "start")
#    point2.saveToConfig(config, section, "end")
#    point3.saveToConfig(config, section, "way")
#    
#    config.writeConfig()
#    
#    config.readConfig()
#    for name, value in config.items(section):
#        if name=="start":
#            point11=OSMRoutingPoint()
#            point11.readFromConfig(value)
#        if name=="end":
#            point22=OSMRoutingPoint()
#            point22.readFromConfig(value)
#        if name=="way":
#            point33=OSMRoutingPoint()
#            point33.readFromConfig(value)
#
#    print(point11)    
#    print(point22)    
#    print(point33)    


    l=p.getEdgeEntryForWayId(69489908)
    for edge in l:
        print(edge)
#    l=p.getEdgeEntryForWayId(36268167)
#    for edge in l:
#        print(edge)
#
#    l=p.getEdgeEntryForWayId(12138807)
#    for edge in l:
#        print(edge)        
#        82173657
#        10711379
#        4064363
#        4064350
#    l=p.getEdgeEntryForWayId(62074609)
#    for edge in l:
#        print(edge)

#    print(p.getWayEntryForId(62074609))
#    print(p.getEdgeEntryForWayId(62074609))
#    print(p.getWayEntryForId(82173348))
#    print(p.getEdgeEntryForWayId(82173348))

    
    
#    p.printWay(3, 99)
#    streetList=p.getStreetList()
#    lat1=47.8
#    lon1=13.0
##    print(p.getNearNodes(lat, lon))
#    lat2=47.8
#    lon2=13.1
#    
#    osmutils=OSMUtils()
#    print(osmutils.headingDegrees(lat1, lon1, lat2, lon2))
#    distance=int(osmutils.distance(lat, lon, lat1, lon1))
#    frac=10
#    print(distance)
#    newLat=lat1
#    newLon=lon1
#    if distance>frac:
#        doneDistance=0
#        while doneDistance<distance:
#            newLat, newLon=osmutils.linepart(lat, lon, lat1, lon1, doneDistance/distance)
#            print("%f-%f"%(newLat, newLon))
#            doneDistance=doneDistance+frac
    
#    for name, ref in streetList.keys():
#        waylist=p.getTrackListByName(name, ref)
##        p.postprocessWay(name, ref)
##        print(p.streetNameIndex[(name, ref)])
#        for wayid in waylist:
#            print(p.getStreetTrackList(wayid))
##            print(p.streetIndex[way])
        
#    p.closeDB()


if __name__ == "__main__":
    main(sys.argv)  
    

