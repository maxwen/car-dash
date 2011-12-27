'''
Created on Dec 13, 2011

@author: maxl
'''
from osmparser.parser.simple import OSMParser
import sys
import os
import sqlite3
import bz2
import time
import array
from osmparser.osmutils import OSMUtils
import pickle

# simple class that handles the parsed OSM data.

class OSMParserData(object):
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
                
    def createTables(self):
        if self.cursor!=None:
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
        self.cursor.execute('CREATE TABLE edgeTable (id INTEGER PRIMARY KEY, startRefId INTEGER, endRefId INTEGER, wayID INTEGER, edge BLOB)')
 
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

    def addToEdgeTable(self, startRefId, endRefId, wayId, refIdList):
#        if wayId==62074609:
#            print("%d %d %d %d %s"%(self.edgeId, startRefId, endRefId, wayId, str(refIdList)))
            
#        edgeId, existingRefId, existingWayId, idList=self.getEdgeEntryForId(refId, wayId)
#        if existingWayId!=None:
#            print("refId wayId already in table %d %d"%(refId, wayId))
#            return
#            if not refIdList in idList:
#                idList.extend(refIdList)
#                self.cursor.execute('REPLACE INTO edgeTable VALUES( ?, ?, ?, ?)', (edgeId, refId, wayId, pickle.dumps(idList)))
#        else:
        self.cursor.execute('INSERT INTO edgeTable VALUES( ?, ?, ?, ?, ?)', (self.edgeId, startRefId, endRefId, wayId, pickle.dumps(refIdList)))
        self.edgeId=self.edgeId+1
    
    def getEdgeEntryForWayAndStartRefId(self, startRefId, wayId):
        self.cursor.execute('SELECT * FROM edgeTable where startRefId=="%s" AND wayId=="%s"'%(str(startRefId), str(wayId)))
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
        return (None, None, None, None, None)
        
    def getEdgeEntryForStartRefId(self, startRefId):
        self.cursor.execute('SELECT * FROM edgeTable where startRefId=="%s"'%(str(startRefId)))
        resultList=list()
        allentries=self.cursor.fetchall()
        for result in allentries:
            edge=self.edgeFromDB(result)
            resultList.append(edge)
        return resultList
 
    def getEdgeEntryForEndRefId(self, endRefId):
        self.cursor.execute('SELECT * FROM edgeTable where endRefId=="%s"'%(str(endRefId)))
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
#                (crossingIdString, crossingList, wayIdList)=self.getCrossingEntryFor(wayId, refId)
#                if crossingIdString!=None:
#                    if index==len(refs)-1:
#                        prevRefId=refs[index-1]
#                        (id, tags, refs)=self.getWayEntryForId(wayIdList[0])
#                        if id!=None:
#                            nextRevId=refs[0]
#                            return (prevRefId, nextRevId)
            else:
                prevRefId=refs[index-1]
                nextRevId=refs[index+1]
                return (prevRefId, nextRevId)
            
        return (None, None)
    
    def getWayIdForPos(self, actlat, actlon):
        if self.cursor!=None:
            osmutils=OSMUtils()

            nodes=self.getNearNodes(actlat, actlon)
#            minDistance=1000
#            index=0
#            i=0
            minDistance=1000
            minWayId=0
            usedRefId=0
#            minWayList=list()
            for (refId, lat, lon, wayIdList) in nodes:   
                for wayId in wayIdList:
                    # TODO find matching way by creating interpolation points betwwen refs
                    
#                    print("trying %s-%s"%(name, ref))
                    (id, tags, refs, distances)=self.getWayEntryForId(wayId)
                    if id==None:
                        continue
                    
#                    (name, ref)=self.getStreetNameInfo(tags)
                    (prevRefId, nextRefId)=self.getPrevAndNextRefForWay(refId, id, tags, refs)
                    if prevRefId!=None and nextRefId!=None:
                        (prevLat, prevLon)=self.getCoordsWithRef(prevRefId)
                        (nextLat, nextLon)=self.getCoordsWithRef(nextRefId)
                        
                        tempPoints=self.createTemporaryPoint(lat, lon, prevLat, prevLon)
                        tempPoints.extend(self.createTemporaryPoint(lat, lon, nextLat, nextLon))
                        
                        for (tmpLat, tmpLon) in tempPoints:
                            distance=int(osmutils.distance(actlat, actlon, tmpLat, tmpLon))
#                            print("way %d %s-%s has distance of %d"%(wayId, name, ref, distance))

                            if distance < minDistance:
                                minDistance=distance
                                minWayId=wayId
                                usedRefId=refId

            return minWayId, usedRefId    
        
    def createTemporaryPoint(self, lat, lon, lat1, lon1):
        osmutils=OSMUtils()
        distance=int(osmutils.distance(lat, lon, lat1, lon1))
        frac=10
        points=list()
        if distance>frac:
            doneDistance=0
            while doneDistance<distance:
                newLat, newLon=osmutils.linepart(lat, lon, lat1, lon1, doneDistance/distance)
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
            refId, lat, lon, wayIdList=self.refFromDB(x)
            nodes.append((refId, lat, lon, wayIdList))

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
            edgeId, startRefId, endRefId, wayId, refIdList=self.edgeFromDB(x)
            print( "edgeId: "+str(edgeId) +" startRefId: " + str(startRefId)+" endRefId:"+str(endRefId)+ " wayId:"+str(wayId)+ " refIdList: " + str(refIdList))

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
        startRefId=x[1]
        endRefId=x[2]
        wayId=x[3]     
        refIdList=pickle.loads(x[4])
        return (edgeId, startRefId, endRefId, wayId, refIdList)
                
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
            self.coords[osmid]=(lat, lon)
                
    def parse_ways(self, way):
        osmutils=OSMUtils()

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
                            distance=int(osmutils.distance(lat, lon, lat1, lon1))
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
    
    def findWayWithStartRef(self, ways, startRef):
        possibleWays=list()
        for (wayid, tags, refs, distances) in ways:
            if refs[0]==startRef:
                possibleWays.append((wayid, tags, refs, distances))
        return possibleWays
    
    def findWayWithEndRef(self, ways, endRef):
        possibleWays=list()
        for (wayid, tags, refs, distances) in ways:
            if refs[-1]==endRef:
                possibleWays.append((wayid, tags, refs, distances))
        return possibleWays
    
    def findStartWay(self, ways):
        for (wayid, tags, refs, distances) in ways:
            startRef=refs[0]
            possibleWays=self.findWayWithEndRef(ways, startRef)
            if len(possibleWays)==0:
                return (wayid, tags, refs, distances)
        return ways[0]
    
    def findEndWay(self, ways):
        for (wayid, tags, refs, distances) in ways:
            endRef=refs[-1]
            possibleWays=self.findWayWithStartRef(ways, endRef)
            if len(possibleWays)==0:
                return (wayid, tags, refs, distances)        
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

    def showWay(self, wayId, usedRefId, level):
        self.edgeList=list()
        self.getEdgeListForWayLevels(wayId, usedRefId, level)
        return self.printEdgeList(self.edgeList)
    
    def showWayWithName(self, name, ref):
        name, ref, wayIdList=self.getStreetEntryForName((name, ref))
        if name==None:
            print("street with name %s and ref %snot found"%(name, ref))
            return
        
        ways=list()
        for id in wayIdList:
            ways.append(self.getWayEntryForId(id))            
        
        (wayId, tags, refs, distances)=self.findStartWay(ways)
        startRef=refs[0]
        resultList=self.getEdgeEntryForWayAndStartRefId(startRef, wayId)
        if len(resultList)!=1:
            print("more then one start edge")
            return
        
#        startEdge, startRefId, endRefId, wayId, edgeInfo=resultList[0]
#        print(startEdge)

        self.edgeList=list()
        self.getEdgeListForWayName(resultList[0], (name, ref))
        return self.printEdgeList(self.edgeList)
    
    def printEdgeList(self, edgeList):
        trackWayList=list()
        track=dict()
        track["name"]=""

        for edgeId in edgeList:
            result=self.getEdgeEntryForEdgeId(edgeId)
            edgeId, startRefId, endRefId, wayId, edgeInfo=result
            (id, tags, refs, distances)=self.getWayEntryForId(wayId)

            if "highway" in tags:
                streetType=tags["highway"]
                
            (name, ref)=self.getStreetNameInfo(tags)
                
            trackWayList.append(self.createStartTrackItem())

            for ref in edgeInfo["r"]:
#                print("%d %d %d %d"%(edgeId, refId, wayId, ref))
                trackItem=dict()
                trackItem["wayId"]=wayId
                trackItem["ref"]=ref
                (lat, lon)=self.getCoordsWithRef(ref)
                if lat==None:
                    print("resolveWay no node in DB with %d"%(ref))
                    continue
                trackItem["lat"]=lat
                trackItem["lon"]=lon        
                trackItem["oneway"]=edgeInfo["o"]
                trackItem["type"]=streetType
                trackItem["info"]=(name, ref)
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
            
            trackWayList.append(self.createEndTrackItem())
        
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
            edgeId, startRefId, endRefId, wayId, edgeInfo=result

            for edgeRef in edgeInfo["r"]:
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
        edgeId, startRefId, endRefId, wayId, edgeInfo=edge
        oneway=edgeInfo["o"]
        
        self.doneEdges.append(edgeId)
        self.edgeList.append(edgeId)

        if self.level==self.wantLevel:
            return
        
        resultList=self.getEdgeEntryForStartRefId(startRefId)
        for result in resultList:
            edgeId1, startRefId1, endRefId1, wayId1, edgeInfo1=result
            if edgeId1 in self.doneEdges:
                continue
            oneway1=edgeInfo1["o"]
            if oneway==1 and oneway1==1:
                continue
            
            self.level=self.level+1
            self.getEdgePartLevels(result)
            self.level=self.level-1
            
        resultList=self.getEdgeEntryForEndRefId(startRefId)
        for result in resultList:
            edgeId1, startRefId1, endRefId1, wayId1, edgeInfo1=result
            if edgeId1 in self.doneEdges:
                continue
            oneway1=edgeInfo1["o"]
            if oneway1==1:
                continue
            self.level=self.level+1
            self.getEdgePartLevels(result)
            self.level=self.level-1
            
        resultList=self.getEdgeEntryForStartRefId(endRefId)
        for result in resultList:
            edgeId1, startRefId1, endRefId1, wayId1, edgeInfo1=result
            if edgeId1 in self.doneEdges:
                continue           

            self.level=self.level+1
            self.getEdgePartLevels(result)
            self.level=self.level-1
            
        resultList=self.getEdgeEntryForEndRefId(endRefId)
        for result in resultList:
            edgeId1, startRefId1, endRefId1, wayId1, edgeInfo1=result
            if edgeId1 in self.doneEdges:
                continue
            oneway1=edgeInfo1["o"]
            if oneway1==1:
                continue
            self.level=self.level+1
            self.getEdgePartLevels(result)
            self.level=self.level-1
                
    def getEdgeListForWayName(self, edge, streetInfo):        
        self.doneEdges=list()
                
        self.getEdgePartName(edge, streetInfo)
        
    def getEdgePartName(self, edge, streetInfo):
        edgeId, startRefId, endRefId, wayId, edgeInfo=edge
        oneway=edgeInfo["o"]

        self.doneEdges.append(edgeId)
        self.edgeList.append(edgeId)
                
        resultList=self.getEdgeEntryForStartRefId(startRefId)
        for result in resultList:
            edgeId1, startRefId1, endRefId1, wayId1, edgeInfo1=result
            if edgeId1 in self.doneEdges:
                continue
            oneway1=edgeInfo1["o"]
            if oneway==1 and oneway1==1:
                continue

            newStreetInfo=self.getStreetInfoWithWayId(wayId1)
            if newStreetInfo==streetInfo:
                self.getEdgePartName(result, streetInfo)
            
        resultList=self.getEdgeEntryForEndRefId(startRefId)
        for result in resultList:
            edgeId1, startRefId1, endRefId1, wayId1, edgeInfo1=result
            if edgeId1 in self.doneEdges:
                continue
            oneway1=edgeInfo1["o"]
            if oneway1==1:
                continue
            newStreetInfo=self.getStreetInfoWithWayId(wayId1)
            if newStreetInfo==streetInfo:
                self.getEdgePartName(result, streetInfo)
                            
        resultList=self.getEdgeEntryForStartRefId(endRefId)
        for result in resultList:
            edgeId1, startRefId1, endRefId1, wayId1, edgeInfo1=result
            if edgeId1 in self.doneEdges:
                continue           
            newStreetInfo=self.getStreetInfoWithWayId(wayId1)
            if newStreetInfo==streetInfo:
                self.getEdgePartName(result, streetInfo)
                            
        resultList=self.getEdgeEntryForEndRefId(endRefId)
        for result in resultList:
            edgeId1, startRefId1, endRefId1, wayId1, edgeInfo1=result
            if edgeId1 in self.doneEdges:
                continue
            oneway1=edgeInfo1["o"]
            if oneway1==1:
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
                        if i+1<len(distances):
                            distance=distance+distances[i+1]
                            
                        edgeInfo=dict()
                        edgeInfo["r"]=refNodeList
                        edgeInfo["d"]=distance
                        edgeInfo["o"]=oneway
                        self.addToEdgeTable(refNodeList[0], refNodeList[-1], wayId, edgeInfo)
                            
                        refNodeList=list()
                        distance=0
               
                refNodeList.append(ref)
                i=i+1
                if i<len(distances):
                    distance=distance+distances[i]
            
            # handle last portion
            if not ref in doneRefs:
                if len(refNodeList)!=0:
                    edgeInfo=dict()
                    edgeInfo["r"]=refNodeList
                    edgeInfo["d"]=distance
                    edgeInfo["o"]=oneway

                    self.addToEdgeTable(refNodeList[0], refNodeList[-1], wayId, edgeInfo)

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


    def getDBFile(self):
        return self.file+".db"
    
    def dbExists(self):
        return os.path.exists(self.getDBFile())
        
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
            
            self.closeDB()
            print("commited DB")
            
#        print("postprocess streets")
#        self.postprocessWays()
#        print("end postprocess streets")
            
def main(argv):    
    try:
        osmFile=argv[1]
    except IndexError:
#        osmFile='/home/maxl/Downloads/austria.osm.bz2'
        osmFile='/home/maxl/Downloads/salzburg-streets.osm.bz2'
#        osmFile='/home/maxl/Downloads/salzburg-city-streets.osm'
#        osmFile='test1.osm'

    p = OSMParserData(osmFile)
    
    p.initDB()
    
    p.openDB()
    p.testRefTable()
    p.testWayTable()
    p.testStreetTable()
    p.testCrossingTable()
    p.testEdgeTable()
    
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
        
    p.closeDB()


if __name__ == "__main__":
    main(sys.argv)  
    

