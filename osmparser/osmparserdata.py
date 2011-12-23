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

# simple class that handles the parsed OSM data.

class OSMParserData(object):
    def __init__(self, file):
        self.nodes = dict()
        self.coords = dict()
#        self.ways = dict()
        self.relations = dict()
        self.track=list()
        self.trackWayList=list()
        self.streetNameIndex=dict()
        self.streetIndex=dict()
        self.file=file
        self.doneWays=list()
        self.wayRefIndex=dict()
        self.wayToStreetIndex=dict()
#        self.gpsGrid=[]
        self.connection=None
        self.cursor=None
        self.crossingTest=list()

#        for i in range(10000):
#            self.gpsGrid.append([])
#            for j in range(10000):
#                self.gpsGrid[i].append(None)
                
    def createTables(self):
        if self.cursor!=None:
            self.createRefTable()
            self.createWayTable()
            self.createStreetTable()
            self.createCrossingsTable()

    def openDB(self):
        self.connection=sqlite3.connect(self.getDBFile())
        self.cursor=self.connection.cursor()   

    def createRefTable(self):
        self.cursor.execute('CREATE TABLE refTable (refId INTEGER PRIMARY KEY, lat REAL, lon REAL, ways TEXT)')
    
    def createWayTable(self):
        self.cursor.execute('CREATE TABLE wayTable (wayId INTEGER PRIMARY KEY, tags TEXT, refs TEXT, refsDistance TEXT)')

    def createStreetTable(self):
        self.cursor.execute('CREATE TABLE streetTable (street TEXT PRIMARY KEY, wayIdList TEXT)')
    
    def createCrossingsTable(self):
        self.cursor.execute('CREATE TABLE crossingTable (crossingId TEXT PRIMARY KEY, crossingWayIdList TEXT, nextWayIdList TEXT)')

    def addToRefTable(self, refid, lat, lon, wayIdList):
        wayIdListString=""
        for wayId in wayIdList:
            wayIdListString=wayIdListString+str(wayId)+"|"
        wayIdListString=wayIdListString[:-1]
        self.cursor.execute('INSERT INTO refTable VALUES( ?, ?, ?, ?)', (refid, lat, lon, wayIdListString))

    def addToWayTable(self, wayid, tags, refs, distances):
        refsString=""
        for ref in refs:
            refsString=refsString+str(ref)+"|"
        refsString=refsString[:-1]
        
        tagsString=""
        for key, value in tags.items():
            tagsString=tagsString+key+"|"+value+"||"
        tagsString=tagsString[:-2]
        
        distanceString=""
        for distance in distances:
            distanceString=distanceString+str(distance)+"|"
        distanceString=distanceString[:-1]
        self.cursor.execute('INSERT INTO wayTable VALUES( ?, ?, ?, ?)', (wayid, tagsString, refsString, distanceString))

    def addToStreetTable(self, streetInfo, wayidList):
        (name, ref)=streetInfo
        streetInfoString=name+"_"+ref
        wayIdListString=""
        for wayId in wayidList:
            wayIdListString=wayIdListString+str(wayId)+"|"
        wayIdListString=wayIdListString[:-1]
        self.cursor.execute('INSERT INTO streetTable VALUES( ?, ?)', (streetInfoString, wayIdListString))

    def addToCrossingsTable(self, refid, wayid, crossingList, nextWaysList):
        existingEntryId, existingCrossingList, existingNextWayIdList=self.getCrossingEntryFor(refid, wayid)
        
        if existingEntryId!=None:
            # e.g. roundabouts have the same ref twice
            return

        crossingIdString="%d|%d"%(refid, wayid)
       
        nextWaysListString=""   
        for wayId in nextWaysList:
            nextWaysListString=nextWaysListString+str(wayId)+"|"
        nextWaysListString=nextWaysListString[:-1]

        nextCrossingListString=""
        for wayId in crossingList:
            nextCrossingListString=nextCrossingListString+str(wayId)+"|"
        nextCrossingListString=nextCrossingListString[:-1]
  
        self.crossingTest.append(crossingIdString)
#        self.cursor.execute('REPLACE INTO crossingTable VALUES( ?, ?, ?)', (crossingIdString, nextCrossingListString, nextWaysListString))
        try:
            self.cursor.execute('INSERT INTO crossingTable VALUES( ?, ?, ?)', (crossingIdString, nextCrossingListString, nextWaysListString))
        except sqlite3.IntegrityError as msg:
            print("sqlite3 error %s"%(msg))

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
    
    def getCrossingEntryFor(self, refid, wayid):
        crossingIdString="%d|%d"%(refid, wayid)
#        print(crossingIdString)
        self.cursor.execute('SELECT * FROM crossingTable where crossingId=="%s"'%(crossingIdString))
        allentries=self.cursor.fetchall()
        if len(allentries)==1:
            return self.crossingFromDB(allentries[0])
        else:
            None
        return (None, None, None)  
    
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
            
#            minWayList=list()
            for (refId, lat, lon, wayIdList) in nodes:   
#                distance=osmutils.distance(actlat, actlon, lat, lon)   
#                if distance < minDistance:
#                    minDistance=distance
#                    index=i
#                i=i+1
#            
#            if minDistance>100:
#                return
#            
#            refId=nodes[index][0]
#            wayIdList=nodes[index][3]
#            lat=nodes[index][1]
#            lon=nodes[index][2]
            
                for wayId in wayIdList:
                    # TODO find matching way by creating interpolation points betwwen refs
                    
#                    print("trying %s-%s"%(name, ref))
                    (id, tags, refs, distances)=self.getWayEntryForId(wayId)
                    if id==None:
                        continue
                    
                    (name, ref)=self.getStreetNameInfo(tags)
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
#                        (name, ref)=self.getStreetNameInfo(tags)
#                    else:
#                        print("next and ref not found on same way %d"%(wayId))
                        
#            (id, tags, refs)=self.getWayEntryForId(minWayId)
#            if id!=None:
#                (name, ref)=self.getStreetNameInfo(tags)
#                print("way %d %s-%s %s has min distance of %d"%(minWayId, name, ref, tags["highway"], minDistance))
#                minWayList.append(minWayId)
                
#            waylist=self.postprocessWayForWayId(minWayList)
            return minWayId    
        
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
#        self.cursor.execute('SELECT * FROM refTable where refId==1')
#        allentries=self.cursor.fetchall()
#        for x in allentries:
#            wayIdListString=x[3]
#            wayIdList=list()
#            for wayId in wayIdListString.split("|"):
#                wayIdList.append(int(wayId))
#            lat=float(x[1])
#            lon=float(x[2])
#            refId=int(x[0])
#            print( "ref: " + str(refId) + "  lat: " + str(lat) + "  lon: " + str(lon) + " ways:"+str(wayIdList))

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
            crossingIdString, crossingList, wayIdList=self.crossingFromDB(x)
            print( "id: " + crossingIdString + " crossingList:"+str(crossingList)+ " wayIdList: " + str(wayIdList))
        
    def wayFromDB(self, x):
        wayId=int(x[0])
        refListString=x[2]
        refs=list()
        for ref in refListString.split("|"):
            refs.append(int(ref))
            
        tagsString=x[1]
        tags=dict()
        for dictEntry in tagsString.split("||"):
            try:
                (key, value)=dictEntry.split("|")
                tags[key]=value
            except ValueError:
                print("%s %s %s"%(wayId, tagsString, refListString))
        
        distanceString=x[3]
        distances=list()
        for distance in distanceString.split("|"):
            distances.append(int(distance))
        return (wayId, tags, refs, distances)
    
    def refFromDB(self, x):
        wayIdListString=x[3]
        wayIdList=list()
        for wayId in wayIdListString.split("|"):
            wayIdList.append(int(wayId))
        lat=float(x[1])
        lon=float(x[2])
        refId=int(x[0])
        return (refId, lat, lon, wayIdList)

    def streetFromDB(self, x):
        streetInfoString=x[0]
        (name, ref)=streetInfoString.split("_")
        wayIdListString=x[1]
        wayIdList=list()
        for wayId in wayIdListString.split("|"):
            wayIdList.append(int(wayId))
        return (name, ref, wayIdList)
        
    def crossingFromDB(self, x):
        crossingIdString=x[0]
        crossingListString=x[1]
        crossingList=list()
        
        if len(crossingListString)!=0:
            for wayId in crossingListString.split("|"):
                crossingList.append(int(wayId))
            
        nextWaysListString=x[2]
        nextWayIdList=list()
        if len(nextWaysListString)!=0:
            for wayId in nextWaysListString.split("|"):
                nextWayIdList.append(int(wayId))
                
        return (crossingIdString, crossingList, nextWayIdList)
    
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
                self.addToRefTable(ref, lat, lon, wayIdList)
            except KeyError:
                None

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

                    
#    def printGPSGrid(self):
#        for i in range(10000):
#            for j in range(10000):
#                if self.gpsGrid[i][j]!=None:
#                    reflist=self.gpsGrid[i][j]
#                    print("%d %d %d"%(i,j,len(reflist)))
                
    def parse_coords(self, coord):
        for osmid, lat, lon in coord:
            self.coords[osmid]=(lat, lon)
                   
#            (x, y)=self.locationToGridIndex(lat, lon)
#            if self.gpsGrid[x][y]!=None:
#                reflist=self.gpsGrid[x][y]
#                reflist.append((osmid, lat, lon))
#            else:
#                reflist=list()
#                reflist.append((osmid, lat, lon))
#                self.gpsGrid[x][y]=reflist
                
    def parse_ways(self, way):
        osmutils=OSMUtils()

        for wayid, tags, refs in way:
            if "highway" in tags:
                streetType=tags["highway"]
                if streetType=="services" or streetType=="bridleway" or streetType=="path" or streetType=="track" or streetType=="footway" or streetType=="pedestrian" or streetType=="cycleway" or streetType=="service" or streetType=="living_street" or streetType=="steps" or streetType=="platform":
                    continue
                
                if "service" in tags:
                    continue
                
                if "parking" in tags:
                    continue
                
                if "amenity" in tags:
                    continue
                
                distances=list()
    
                startRef=refs[0]
                if startRef in self.coords:
                    (lat, lon)=self.coords[startRef]
                else:
                    lat=0.0
                    lon=0.0
                distances.append(0)
                           
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
                        
                    wayRefList=list()
                    if ref in self.wayRefIndex:
                        wayRefList=self.wayRefIndex[ref]
            
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
    
    def findWayWithRefInAllWays(self, ref, fromWayId, streetInfo, sameway):
        possibleWays=list()
        wayIdList=self.getWaysWithRef(ref)
        if wayIdList==None:
            return possibleWays
        
        for wayid in wayIdList:
#            tags=self.ways[wayid][0]
#            refs=self.ways[wayid][1]
            
            if wayid==fromWayId:
                continue
#            if wayid in self.doneWays:
#                continue
            
            (id, tags, refs, distances)=self.getWayEntryForId(wayid)
            if id==None:
                print("no entry in way DB for "+str(wayid))
                continue
            
            if "highway" in tags:
#                streetType=tags["highway"]
                oneway=False
                if "oneway" in tags:
                    if tags["oneway"]=="yes":
                        oneway=True
                if streetInfo!=None:
                    if "name" in tags or "ref" in tags:
                        newStreetInfo=self.getStreetNameInfo(tags)
                        if sameway:
                            if streetInfo!=newStreetInfo:
                                continue
                        else:
                            if streetInfo==newStreetInfo:
                                continue

                if oneway:
                    if refs[0]==ref:
                        possibleWays.append((wayid, tags, refs))
                else:
                    for wayRef in refs:
                        if wayRef==ref:
                            possibleWays.append((wayid, tags, refs))
#                        else:
#                            coords1=self.getCoordsWithRef(ref)
#                            coords2=self.getCoordsWithRef(wayRef)
#                            if coords1==coords2:
#                                possibleWays.append((wayid, tags, refs))
 
        return possibleWays
    
    def findLinkWaysWithRefInAllWays(self, ref, fromWayId, streetInfo, streetType):
        possibleWays=list()
        wayIdList=self.getWaysWithRef(ref)
        if wayIdList==None:
            return possibleWays
        
        for wayid in wayIdList:
#            tags=self.ways[wayid][0]
#            refs=self.ways[wayid][1]
            
            if wayid==fromWayId:
                continue
            if wayid in self.doneWays:
                continue
            
            (id, tags, refs, distances)=self.getWayEntryForId(wayid)
            if id==None:
                print("no entry in way DB for "+str(wayid))
                continue

            if "highway" in tags:
                newStreetType=tags["highway"]
                if newStreetType!=streetType+"_link":
                    continue
                
                oneway=False
                if "oneway" in tags:
                    if tags["oneway"]=="yes":
                        oneway=True

#                if oneway:
#                    if refs[0]==ref:
#                        possibleWays.append((wayid, tags, refs))
#                else:
                for wayRef in refs:
                    if wayRef==ref:
                        possibleWays.append((wayid, tags, refs))
#                    else:
#                        coords1=self.getCoordsWithRef(ref)
#                        coords2=self.getCoordsWithRef(wayRef)
#                        if coords1==coords2:
#                            possibleWays.append((wayid, tags, refs))
        return possibleWays
    
    def findLinkEndWaysWithRefInAllWays(self, ref, fromWayId, streetInfo, streetType):
        wayIdList=self.getWaysWithRef(ref)
        if wayIdList==None:
            return (None, None, None)
        
        for wayid in wayIdList:
#            tags=self.ways[wayid][0]
#            refs=self.ways[wayid][1]
            
            if wayid==fromWayId:
                continue
#            if wayid in self.doneWays:
#                continue
            
            (id, tags, refs, distances)=self.getWayEntryForId(wayid)
            if id==None:
                print("no entry in way DB for "+str(wayid))
                continue

            if "highway" in tags:
                newStreetType=tags["highway"]
                if newStreetType!=streetType+"_link":
                    for wayRef in refs:
                        if wayRef==ref:
                            return (wayid, tags, refs)
#                        else:
#                            coords1=self.getCoordsWithRef(ref)
#                            coords2=self.getCoordsWithRef(wayRef)
#                            if coords1==coords2:
#                                return ((wayid, tags, refs))
        return (None, None, None)
    
#    def findWayWithRefAndCoords(self, ways, fromWayId, ref):
#        possibleWays=list()
#        for (wayid, tags, refs) in ways:
#            if wayid==fromWayId:
#                continue
#            if wayid in self.doneWays:
#                continue
#            for wayRef in refs:
#                if wayRef==ref:
#                    possibleWays.append((wayid, tags, refs))
##                else:
##                    coords1=self.getCoordsWithRef(ref)
##                    coords2=self.getCoordsWithRef(wayRef)
##                    if coords1==coords2:
##                        possibleWays.append((wayid, tags, refs))
#                        
#        return possibleWays
    
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

#    def printRelationCoords(self, name):
#        for osmid, relation in self.relations.items():
#            try:
#                if relation[0]["name"]==name:
#                    for way in relation[1]:
#                        if way[1]=="way":
#                            wayRef=self.ways[way[0]]
#                            for ref in wayRef[1]:   
#                                print("%f %f"%(self.coords[ref][1], self.coords[ref][0]))
#            except KeyError:
#                None
        
#    def postprocessWays(self):
#        i=1
#        for (name, ref),ways in self.street_by_name.items():
##            print((name, ref))
#            self.waysCopy=ways
#            print("process %d of %d"%(i, len(self.street_by_name)))
#
#            self.doneWays=list()
#            
#            while len(self.waysCopy)!=0:
#                way=self.findStartWay(self.waysCopy)
#                
#                if way!=None:   
#                    self.track=dict()
#                    self.trackWayList=list()
#                    self.track["name"]=(name, ref)
#                    self.track["track"]=list()                         
#                    
#                    (startWayid, tags, refs)=way
#                                  
#                    self.resolveWay(way, (name, ref))
#
#                    wayList=list()
#                    if (name, ref) in self.streetNameIndex:
#                        wayList=self.streetNameIndex[(name, ref)]
#                    
#                    wayList.append(startWayid)
#                            
#                    self.streetNameIndex[(name, ref)]=wayList
#                    self.streetIndex[startWayid]=self.track
#                    
#                    for wayid in self.trackWayList:
#                        self.wayToStreetIndex[wayid]=startWayid
#                else:
#                    print("no start way found "+str(ways))
#                    break
##                if len(self.waysCopy)!=0:
##                    print("self.waysCopy!=0 "+str(self.waysCopy))
#                
#            i=i+1
                 
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
    
    def getTrackListByWay(self, wayId):
        (id, tags, refs, distances)=self.getWayEntryForId(wayId)
        if id!=None:
            track=dict()
            track["name"]=""
            trackItemList=list()
            distance=0
            i=0
            for ref in refs:
                refDistance=distances[i]
                distance=distance+refDistance
                trackItem=dict()
                trackItem["wayId"]=wayId
                trackItem["ref"]=ref
                (lat, lon)=self.getCoordsWithRef(ref)
                if lat==None:
                    print("resolveWay no node in DB with %d"%(ref))
                    continue
                trackItem["lat"]=lat
                trackItem["lon"]=lon
                trackItemList.append(trackItem)
                
                streetInfo=None 
                if "name" in tags or "ref" in tags:
                    streetInfo=self.getStreetNameInfo(tags)
                
                streetType=""
                if "highway" in tags:
                    streetType=tags["highway"]
                oneway=False
                if "oneway" in tags:
                    if tags["oneway"]=="yes":
                        oneway=True
                if "junction" in tags:
                    if tags["junction"]=="roundabout":
                        oneway=True
                        
                trackItem["oneway"]=oneway
                trackItem["type"]=streetType

                croosingList=list()
                crossingId, crossingIdList, nextWayIdList=self.getCrossingEntryFor(ref, wayId)
                if crossingId!=None:
                    way_crossings=list()
                    for crossingId in crossingIdList:
                        (crossingWayid, crossingTags, crossingRefs, crossingDistances)=self.getWayEntryForId(crossingId)
                        if crossingWayid!=None:
                            newStreetInfo=self.getStreetNameInfo(crossingTags)
                            if streetInfo==newStreetInfo:
                                continue
    
                            way_crossings.append((crossingWayid, crossingTags, crossingRefs, crossingDistances))
                        
                    if len(way_crossings)!=0:
                        for (wayid1, tags1, refs1, distances1) in way_crossings:
                            if "highway" in tags1:
                                if not wayid1 in croosingList:
                                    croosingList.append(wayid1)
                        if len(croosingList)!=0:  
                            trackItem["crossing"]=croosingList

                i=i+1
            track["track"]=trackItemList
            wayIdList=list()
            wayIdList.append(track)
            print(distance)
            return wayIdList

    def getStreetTrackList(self, wayid):
        if wayid in self.streetIndex:
            return self.streetIndex[wayid]["track"]
        return None

#    def postprocessWayForWayId(self, wayIdList):
#        allWayList=list()
#        for wayId in wayIdList:
#            (id, tags, refs, distances)=self.getWayEntryForId(wayId)
#            (name, ref)=self.getStreetNameInfo(tags)
#            if name=="" and ref=="":
#                continue
#            if not (name, ref) in self.streetNameIndex.keys():
#                self.postprocessWay(name, ref)
#            waylist=self.streetNameIndex[(name, ref)]
#            allWayList.extend(waylist)
#        return allWayList

    def postprocessWay(self, name, ref):
        print("postprocess %s-%s"%(name, ref))
        name, ref, wayIdList=self.getStreetEntryForName((name, ref))
        
        ways=list()

        for wayId in wayIdList:
            ways.append(self.getWayEntryForId(wayId))            

        self.waysCopy=ways

        self.doneWays=list()
        
        while len(self.waysCopy)!=0:
            way=self.findStartWay(self.waysCopy)
            
            if way!=None:   
                self.track=dict()
                self.trackWayList=list()
                self.track["name"]=(name, ref)
                self.track["track"]=list()                         
                
                (startWayid, tags, refs, distances)=way
                              
                self.resolveWay(way, (name, ref))

                wayList=list()
                if (name, ref) in self.streetNameIndex:
                    wayList=self.streetNameIndex[(name, ref)]
                
                wayList.append(startWayid)
                        
                self.streetNameIndex[(name, ref)]=wayList
                self.streetIndex[startWayid]=self.track
                
                for wayid in self.trackWayList:
                    self.wayToStreetIndex[wayid]=startWayid
            else:
                print("no start way found "+str(ways))
                break
#                if len(self.waysCopy)!=0:
#                    print("self.waysCopy!=0 "+str(self.waysCopy))
                
    def resolveWay(self, way, streetInfo):
        if way==None:
            return
        
        (wayid, tags, refs, distances)=way
        
        if not wayid in self.doneWays:
            self.doneWays.append(wayid)
        
        for ref in refs:
            trackItem=dict()
            trackItem["wayId"]=wayid
            trackItem["ref"]=ref
            (lat, lon)=self.getCoordsWithRef(ref)
            if lat==None:
                print("resolveWay no node in DB with %d"%(ref))
                continue
            trackItem["lat"]=lat
            trackItem["lon"]=lon
            
            if not wayid in self.trackWayList:
                self.trackWayList.append(wayid)
                
            streetType=""
            if "highway" in tags:
                streetType=tags["highway"]
            oneway=False
            if "oneway" in tags:
                if tags["oneway"]=="yes":
                    oneway=True
            if "junction" in tags:
                if tags["junction"]=="roundabout":
                    oneway=True
                    
            trackItem["oneway"]=oneway
            trackItem["type"]=streetType

            croosingList=list()
            
            crossingId, crossingIdList, nextWayIdList=self.getCrossingEntryFor(ref, wayid)
            if crossingId!=None:
                way_crossings=list()
                for wayId in crossingIdList:
                    if not wayId in self.doneWays:
                        (crossingWayid, crossingTags, crossingRefs, crossingDistances)=self.getWayEntryForId(wayId)
                        if crossingWayid!=None:
                            newStreetInfo=self.getStreetNameInfo(crossingTags)
                            if streetInfo==newStreetInfo:
                                continue

                            way_crossings.append((crossingWayid, crossingTags, crossingRefs, crossingDistances))
                    
#                way_crossings=self.findWayWithRefInAllWays(ref, wayid, streetInfo, False)
                if len(way_crossings)!=0:
                    for (wayid1, tags1, refs1, distances1) in way_crossings:
                        if "highway" in tags1:
                            if not wayid1 in croosingList:
                                croosingList.append(wayid1)
                    if len(croosingList)!=0:  
                        trackItem["crossing"]=croosingList
           
            link_crossings=self.findLinkWaysWithRefInAllWays(ref, wayid, streetInfo, streetType)
            if len(link_crossings)!=0:
                for link_crossing in link_crossings:
                    linkTrackItem=dict()
                    linkTrackItem["start"]="start"
                    self.track["track"].append(linkTrackItem)
                    
                    self.resolveLink(link_crossing, streetInfo, streetType)
                
                    linkTrackItem=dict()
                    linkTrackItem["end"]="end"
                    self.track["track"].append(linkTrackItem)
                    
            self.track["track"].append(trackItem)

            crossingId, crossingIdList, nextWayIdList=self.getCrossingEntryFor(ref, wayid)
            if crossingId!=None:
                possibleWays=list()
                for wayId in nextWayIdList:
                    if not wayId in self.doneWays:
                        (crossingWayid, crossingTags, crossingRefs, crossingDistancees)=self.getWayEntryForId(wayId)
                        if crossingWayid!=None:
                            newStreetInfo=self.getStreetNameInfo(crossingTags)
                            if streetInfo!=newStreetInfo:
                                continue
                            possibleWays.append((crossingWayid, crossingTags, crossingRefs, crossingDistancees))

#            possibleWays=self.findWayWithRefAndCoords(self.waysCopy, wayid, ref)  
                if len(possibleWays)!=0:
                    for possibleWay in possibleWays:  
                        streetTrackItem=dict()
                        streetTrackItem["start"]="start"
                        self.track["track"].append(streetTrackItem)
    
                        self.resolveWay(possibleWay, streetInfo)
    
                        streetTrackItem=dict()
                        streetTrackItem["end"]="end"
                        self.track["track"].append(streetTrackItem)
        
        if not way in self.waysCopy:
            None
        else:
            self.waysCopy.remove(way)

    def resolveLink(self, way, streetInfo, streetType):
        if way==None:
            return
        
        (wayid, tags, refs)=way
        
        if not wayid in self.doneWays:
            self.doneWays.append(wayid)
        
        for ref in refs:
            trackItem=dict()
            trackItem["wayId"]=wayid
            trackItem["ref"]=ref
            (lat, lon)=self.getCoordsWithRef(ref)
            if lat==None:
                print("resolveLink no node in DB with %d"%(ref))
                continue
            trackItem["lat"]=lat
            trackItem["lon"]=lon
            
            if not wayid in self.trackWayList:
                self.trackWayList.append(wayid)
                
            newStreetType=""
            if "highway" in tags:
                newStreetType=tags["highway"]
            oneway=False
            if "oneway" in tags:
                if tags["oneway"]=="yes":
                    oneway=True
            if "junction" in tags:
                if tags["junction"]=="roundabout":
                    oneway=True
                    
            trackItem["oneway"]=oneway
            trackItem["type"]=newStreetType
            
            croosingList=list()

            (wayid1, tags1, refs1)=self.findLinkEndWaysWithRefInAllWays(ref, wayid, streetInfo, streetType)
            if wayid1!=None:
                if "highway" in tags1:
                    endLinkStreetType=tags1["highway"]
                    # no crossings on motorway entries
                    if endLinkStreetType!="motorway":
                        if not wayid1 in croosingList:
                            croosingList.append(wayid1)
                    if len(croosingList)!=0:  
                        trackItem["crossing"]=croosingList
            else:
                link_crossings=self.findLinkWaysWithRefInAllWays(ref, wayid, streetInfo, streetType)
                if len(link_crossings)!=0:
                    for link_crossing in link_crossings:
                        linkTrackItem=dict()
                        linkTrackItem["start"]="start"
                        self.track["track"].append(linkTrackItem)
                        
                        self.resolveLink(link_crossing, streetInfo, streetType)
                    
                        linkTrackItem=dict()
                        linkTrackItem["end"]="end"
                        self.track["track"].append(linkTrackItem)
#                    else:
#                        if ref==refs[-1]:
#                            print("end of links without crossing reached "+str(ref))
            self.track["track"].append(trackItem)

    def createCrossingEntries(self):
        self.cursor.execute('SELECT * FROM wayTable')
        allWays=self.cursor.fetchall()
        for way in allWays:
            wayid, tags, refs, distances=self.wayFromDB(way)
            streetType=""
            if "highway" in tags:
                streetType=tags["highway"]
            oneway=False
            if "oneway" in tags:
                if tags["oneway"]=="yes":
                    oneway=True
            if "junction" in tags:
                if tags["junction"]=="roundabout":
                    oneway=True
            
            streetInfo=None 
            if "name" in tags or "ref" in tags:
                streetInfo=self.getStreetNameInfo(tags)
                
            for ref in refs:  
                crossingWayIdList=list()
                nextWaysIdList=list()

                crossingWays=self.findWayWithRefInAllWays(ref, wayid, streetInfo, False)
                if len(crossingWays)!=0:
                    for (wayid1, tags1, refs1) in crossingWays:
                        if not wayid1 in crossingWayIdList:
                            crossingWayIdList.append(wayid1)

                nextWays=self.findWayWithRefInAllWays(ref, wayid, streetInfo, True)  
                if len(nextWays)!=0:
                    for (wayid2, tags2, refs2) in nextWays:
                        if not wayid2 in nextWaysIdList:
                            nextWaysIdList.append(wayid2)

                self.addToCrossingsTable(ref, wayid, crossingWayIdList, nextWaysIdList)

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
        osmFile='/home/maxl/Downloads/salzburg-city-streets.osm'
#        osmFile='test1.osm'

    p = OSMParserData(osmFile)
    
    p.initDB()
    
    p.openDB()
#    p.testRefTable()
    p.testWayTable()
#    p.testStreetTable()
#    p.testCrossingTable()
    
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
    

