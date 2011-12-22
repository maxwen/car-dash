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
        self.gpsGrid=[]
        self.connection=None
        self.cursor=None

#        for i in range(10000):
#            self.gpsGrid.append([])
#            for j in range(10000):
#                self.gpsGrid[i].append(None)
                
    def createTables(self):
        if self.cursor!=None:
            self.createRefTable()
            self.createWayTable()
            self.createStreetTable()

    def openDB(self):
        self.connection=sqlite3.connect(self.getDBFile())
        self.cursor=self.connection.cursor()   

    def createRefTable(self):
        self.cursor.execute('CREATE TABLE refTable (refId INTEGER PRIMARY KEY, lat REAL, lon REAL, ways TEXT)')
    
    def createWayTable(self):
        self.cursor.execute('CREATE TABLE wayTable (wayId INTEGER PRIMARY KEY, tags TEXT, refs TEXT)')

    def createStreetTable(self):
        self.cursor.execute('CREATE TABLE streetTable (street TEXT, wayIdList TEXT)')

    def addToRefTable(self, ref, lat, lon, wayIdList):
        wayIdListString=""
        for wayId in wayIdList:
            wayIdListString=wayIdListString+str(wayId)+"|"
        wayIdListString=wayIdListString[:-1]
        self.cursor.execute('INSERT INTO refTable VALUES( ?, ?, ?, ?)', (ref, lat, lon, wayIdListString))

    def addToWayTable(self, way, tags, refs):
        refsString=""
        for ref in refs:
            refsString=refsString+str(ref)+"|"
        refsString=refsString[:-1]
        tagsString=""
        for key, value in tags.items():
            tagsString=tagsString+key+"|"+value+"||"
        tagsString=tagsString[:-2]
        self.cursor.execute('INSERT INTO wayTable VALUES( ?, ?, ?)', (way, tagsString, refsString))

    def addToStreetTable(self, streetInfo, wayidList):
        (name, ref)=streetInfo
        streetInfoString=name+"_"+ref
        wayIdListString=""
        for wayId in wayidList:
            wayIdListString=wayIdListString+str(wayId)+"|"
        wayIdListString=wayIdListString[:-1]
        self.cursor.execute('INSERT INTO streetTable VALUES( ?, ?)', (streetInfoString, wayIdListString))

    def getRefEntryForId(self, refId):
        self.cursor.execute('SELECT * FROM refTable where refId==%s'%(str(refId)))
        allentries=self.cursor.fetchall()
        if len(allentries)==1:
            refId, lat, lon, wayIdList=self.refFromDB(allentries[0])
            return (refId, lat, lon, wayIdList)
        
        return (None, None, None, None)

    def getWayEntryForId(self, wayId):
        self.cursor.execute('SELECT * FROM wayTable where wayId==%s'%(str(wayId)))
        allentries=self.cursor.fetchall()
        if len(allentries)==1:
            wayId, tags, refs=self.wayFromDB(allentries[0])
            return (wayId, tags, refs)
        
        return (None, None, None)
    
    def getStreetEntryForName(self, streetInfo):
        (name, ref)=streetInfo
        streetInfoString=name+"_"+ref
        self.cursor.execute('SELECT * FROM streetTable where street=="%s"'%(str(streetInfoString)))
        allentries=self.cursor.fetchall()
        if len(allentries)==1:
            name, ref, wayIdList=self.streetFromDB(allentries[0])
            return (name, ref, wayIdList)
        
        return (None, None, None)
    def testRefTable(self):
        self.cursor.execute('SELECT * FROM refTable')
        allentries=self.cursor.fetchall()
        for x in allentries:
            refId, lat, lon, wayIdList=self.refFromDB(x)
            print( "ref: " + str(refId) + "  lat: " + str(lat) + "  lon: " + str(lon) + " ways:"+str(wayIdList))
             
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
            wayId, tags, refs=self.wayFromDB(x)
            print( "way: " + str(wayId) + "  tags: " + str(tags) + "  refs: " + str(refs))

    def testStreetTable(self):
        self.cursor.execute('SELECT * FROM streetTable')
        allentries=self.cursor.fetchall()
        for x in allentries:
            name, ref, wayIdList=self.streetFromDB(x)
            print( "name: " + name + " ref:"+ref+ " wayIdList: " + str(wayIdList))

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
        return (wayId, tags, refs)
    
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
        for osmid, tags, coords in node:
            self.nodes[osmid]=(tags, coords)
                    
    def printGPSGrid(self):
        for i in range(10000):
            for j in range(10000):
                if self.gpsGrid[i][j]!=None:
                    reflist=self.gpsGrid[i][j]
                    print("%d %d %d"%(i,j,len(reflist)))
                
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
        for osmid, tags, refs in way:
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
                
                self.addToWayTable(osmid, tags, refs)
                for ref in refs:
                    wayRefList=list()
                    if ref in self.wayRefIndex:
                        wayRefList=self.wayRefIndex[ref]
                
                    wayRefList.append(osmid)
                    self.wayRefIndex[ref]=wayRefList                   

    def collectWaysByName(self):
        street_by_name=dict()
        self.cursor.execute('SELECT * FROM wayTable')
        allWays=self.cursor.fetchall()
        for way in allWays:
            wayId, tags, refs=self.wayFromDB(way)
                
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
        (id, tags, refs)=self.getWayEntryForId(wayId)
        (name, ref)=self.getStreetNameInfo(tags)
        return (name, ref)
            
    def getCoordsWithRef(self, ref):
        (refId, lat, lon, wayIdList)=self.getRefEntryForId(ref)
        if refId!=None:
            return (lat, lon)
        
        return (None, None)
    
    def findWayWithRefInAllWays(self, ref, fromWayId, streetInfo):
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
            
            (id, tags, refs)=self.getWayEntryForId(wayid)
            if id==None:
                print("no entry in way DB for "+str(wayid))
                continue
            
            if "highway" in tags:
#                streetType=tags["highway"]
                oneway=False
                if "oneway" in tags:
                    if tags["oneway"]=="yes":
                        oneway=True
                if "name" in tags or "ref" in tags:
                    newStreetInfo=self.getStreetNameInfo(tags)
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
            
            (id, tags, refs)=self.getWayEntryForId(wayid)
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
            
            (id, tags, refs)=self.getWayEntryForId(wayid)
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
    
    def findWayWithRefAndCoords(self, ways, fromWayId, ref):
        possibleWays=list()
        for (wayid, tags, refs) in ways:
            if wayid==fromWayId:
                continue
            if wayid in self.doneWays:
                continue
            for wayRef in refs:
                if wayRef==ref:
                    possibleWays.append((wayid, tags, refs))
#                else:
#                    coords1=self.getCoordsWithRef(ref)
#                    coords2=self.getCoordsWithRef(wayRef)
#                    if coords1==coords2:
#                        possibleWays.append((wayid, tags, refs))
                        
        return possibleWays
    
    def findWayWithStartRef(self, ways, startRef):
        possibleWays=list()
        for (wayid, tags, refs) in ways:
            if refs[0]==startRef:
                possibleWays.append((wayid, tags, refs))
        return possibleWays
    
    def findWayWithEndRef(self, ways, endRef):
        possibleWays=list()
        for (wayid, tags, refs) in ways:
            if refs[-1]==endRef:
                possibleWays.append((wayid, tags, refs))
        return possibleWays
    
    def findStartWay(self, ways):
        for (wayid, tags, refs) in ways:
            startRef=refs[0]
            possibleWays=self.findWayWithEndRef(ways, startRef)
            if len(possibleWays)==0:
                return (wayid, tags, refs)
        return ways[0]
    
    def findEndWay(self, ways):
        for (wayid, tags, refs) in ways:
            endRef=refs[-1]
            possibleWays=self.findWayWithStartRef(ways, endRef)
            if len(possibleWays)==0:
                return (wayid, tags, refs)        
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
    
    def postprocessWayForWayId(self, wayIdList):
        allWayList=list()
        for wayId in wayIdList:
            (id, tags, refs)=self.getWayEntryForId(wayId)
            (name, ref)=self.getStreetNameInfo(tags)
            if name=="" and ref=="":
                continue
            self.postprocessWay(name, ref)
            waylist=self.streetNameIndex[(name, ref)]
            allWayList.extend(waylist)
        return allWayList

    def postprocessWay(self, name, ref):
        name, ref, wayIdList=self.getStreetEntryForName((name, ref))
        
        ways=list()

        for wayId in wayIdList:
            (id, tags, refs)=self.getWayEntryForId(wayId)
            ways.append((id, tags, refs))
            

        self.waysCopy=ways

        self.doneWays=list()
        
        while len(self.waysCopy)!=0:
            way=self.findStartWay(self.waysCopy)
            
            if way!=None:   
                self.track=dict()
                self.trackWayList=list()
                self.track["name"]=(name, ref)
                self.track["track"]=list()                         
                
                (startWayid, tags, refs)=way
                              
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
        
        (wayid, tags, refs)=way
        
        if not wayid in self.doneWays:
            self.doneWays.append(wayid)
        
        for ref in refs:
            try:                
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
                
                way_crossings=self.findWayWithRefInAllWays(ref, wayid, streetInfo)
                if len(way_crossings)!=0:
                    for (wayid1, tags1, refs1) in way_crossings:
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

            except KeyError:
                print("resolveWay no node with %d"%(ref))

            possibleWays=self.findWayWithRefAndCoords(self.waysCopy, wayid, ref)  
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
            try:                
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

            except KeyError:
                print("resolveWay no node with %d"%(ref))

    def parse(self):
        p = OSMParser(1, nodes_callback=None, 
                  ways_callback=self.parse_ways, 
                  relations_callback=None,
                  coords_callback=self.parse_coords)
        p.parse(self.file)

#    def dump(self):
#        dump=bz2.BZ2File(self.getDumpFile(), "w")
#        dump.write("streetNameIndex\n".encode())
#
#        for (ref, name), waylist in self.streetNameIndex.items():
#            dump.write(ref.encode()+"|".encode()+name.encode()+"::".encode())
#            for wayid in waylist:
#                dump.write(str(wayid).encode()+"|".encode())
#            dump.write("\n".encode())
#                
#        dump.write("streetIndex\n".encode())
#
#        for wayId in self.streetIndex.keys():
#            dump.write(str(wayId).encode()+"::".encode())
#            track=self.streetIndex[wayId]
#            (ref, name)=track["name"]
#            dump.write(ref.encode()+"|".encode()+name.encode())
#            
#            trackList=track["track"]
#            dump.write("::".encode())
#
#            for trackItem in trackList:
#                dump.write("|".encode())
#                
#                if "lat" in trackItem.keys():
#                    dump.write(str(trackItem["lat"]).encode()+":".encode())
#                if "lon" in trackItem.keys():
#                    dump.write(str(trackItem["lon"]).encode()+":".encode())
#                if "wayId" in trackItem.keys():
#                    dump.write(str(trackItem["wayId"]).encode()+":".encode())
#                if "ref" in trackItem.keys():
#                    dump.write(str(trackItem["ref"]).encode()+":".encode())
#                if "oneway" in trackItem.keys():
#                    dump.write(str(trackItem["oneway"]).encode()+":".encode())
#                if "type" in trackItem.keys():
#                    dump.write(str(trackItem["type"]).encode())
#                if "crossing" in trackItem.keys():
#                    crossingList=trackItem["crossing"]
#                    dump.write(":".encode())
#                    for crossing in crossingList:
#                        dump.write(str(crossing).encode()+"-".encode())
#                if "start" in trackItem.keys():
#                    dump.write(str(trackItem["start"]).encode())
#                if "end" in trackItem.keys():
#                    dump.write(str(trackItem["end"]).encode())
#            dump.write("|".encode())
#            dump.write("\n".encode())
#
#
##        dump.write("wayRefIndex\n".encode())
##        for ref, waylist  in self.wayRefIndex.items():
##            dump.write(str(ref).encode()+"::".encode())
##            for wayid in waylist:
##                dump.write(str(wayid).encode()+"|".encode())
##            dump.write("\n".encode())
#
#        dump.write("wayToStreetIndex\n".encode())
#        for wayid, streetWayId  in self.wayToStreetIndex.items():
#            dump.write(str(wayid).encode()+"|".encode()+str(streetWayId).encode()+"::".encode())
#        dump.write("\n".encode())
#            
#        dump.close()
        
#    def loadDump(self):
#        if os.path.exists(self.getDumpFile()):
#            dump=bz2.BZ2File(self.getDumpFile(), "r")
#            streetIndex=False
#            streetNameIndex=False
##            wayRefIndex=False
#            wayToStreetIndex=False
#            for line in dump:
#                line=line.decode()
#                if line=="streetNameIndex\n":
#                    streetNameIndex=True
#                    streetIndex=False
##                    wayRefIndex=False
#                    wayToStreetIndex=False
#                    continue
#                if line=="streetIndex\n":
#                    streetIndex=True
#                    streetNameIndex=False
##                    wayRefIndex=False
#                    wayToStreetIndex=False
#                    continue
##                if line=="wayRefIndex\n":
##                    streetIndex=False
##                    streetNameIndex=False
###                    wayRefIndex=True
##                    wayToStreetIndex=False
##                    continue
#                if line=="wayToStreetIndex\n":
#                    streetIndex=False
#                    streetNameIndex=False
##                    wayRefIndex=False
#                    wayToStreetIndex=True
#                    continue
##                if wayRefIndex:
##                    (ref, waylist)=line.split("::")
##                    ways=list()
##                    for wayid in waylist.split("|"):
##                        if len(wayid)!=0 and wayid!="\n":
##                            ways.append(int(wayid))
##                    self.wayRefIndex[ref]=ways
#                if wayToStreetIndex:
#                    for item in line.split("::"):
#                        if len(item)!=0 and item!="\n":
#                            wayid, streetWayId=item.split("|")     
#                            self.wayToStreetIndex [int(wayid)]=int(streetWayId)         
#                if streetNameIndex:
#                    (streetInfo,waylist)=line.split("::")
#                    (name, ref)=streetInfo.split("|")
#                    ways=list()
#                    for wayid in waylist.split("|"):
#                        if len(wayid)!=0 and wayid!="\n":
#                            ways.append(int(wayid))
#                    self.streetNameIndex[(name, ref)]=ways
#                if streetIndex:
#                    (wayId, name, restLine)=line.split("::")
#                    trackInfo=dict()
#                    trackInfo["name"]=name
#                    trackList=list()
#                    for trackItemData in restLine.split("|"):
#                        if len(trackItemData)==0 or trackItemData=="\n":
#                            continue
#                        
#                        trackItem=dict()
#                        if trackItemData=="start":
#                            trackItem["start"]="start"
#                        elif trackItemData=="end":
#                            trackItem["end"]="end"
#                        else:
#                            trackData=trackItemData.split(":")
#                            
#                            if len(trackData)>=6:
#                                trackItem["lat"]=float(trackData[0])
#                                trackItem["lon"]=float(trackData[1])
#                                trackItem["wayId"]=int(trackData[2])
#                                trackItem["ref"]=int(trackData[3])
#                                trackItem["oneway"]=bool(trackData[4])
#                                trackItem["type"]=trackData[5]
#
#                            if len(trackData)==7:
#
#                                crossingList=list()
#                                crossingListData=trackData[6].split("-")
#                                for crossing in crossingListData:
#                                    if len(crossing)!=0 and crossing!="\n":
#                                        crossingList.append(int(crossing))
#                                trackItem["crossing"]=crossingList
#                        trackList.append(trackItem)
#                    trackInfo["track"]=trackList
#                    self.streetIndex[int(wayId)]=trackInfo
#            dump.close()
#    def getDumpFile(self):
#        return self.file+".dump.bz2"
    
    def getDBFile(self):
        return self.file+".db"
    
#    def dumpExists(self):
#        return os.path.exists(self.getDumpFile())
    
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
            print("add to DB")
            self.addAllRefsToDB()
            self.collectWaysByName()
            print("end collect streets")
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
        osmFile='/home/maxl/Downloads/salzburg-city-streets.osm.bz2'
#        osmFile='test1.osm'

    p = OSMParserData(osmFile)
    
    p.initDB()
    
    p.openDB()
#    p.testRefTable()
#    p.testWayTable()
#    p.testStreetTable()
    
    streetList=p.getStreetList()
    lat=47.8
    lon=13.0
    print(p.getNearNodes(lat, lon))
#    for name, ref in streetList.keys():
#        p.postprocessWay(name, ref)
#        print(p.streetNameIndex[(name, ref)])
#        for way in p.streetNameIndex[(name, ref)]:
#            print(p.streetIndex[way])
        
    p.closeDB()


if __name__ == "__main__":
    main(sys.argv)  
    

