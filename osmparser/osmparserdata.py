'''
Created on Dec 13, 2011

@author: maxl
'''
from osmparser.parser.simple import OSMParser
import sys
import os
import sqlite3
import bz2

# simple class that handles the parsed OSM data.

class OSMParserData(object):
    def __init__(self, file):
        self.nodes = dict()
        self.coords = dict()
        self.ways = dict()
        self.relations = dict()
        self.street_by_name=dict()
        self.track=list()
        self.trackWayList=list()
        self.streetNameIndex=dict()
        self.streetIndex=dict()
        self.file=file
        self.doneWays=list()
        self.wayRefIndex=dict()
        self.wayToStreetIndex=dict()
        self.gpsGrid=[]
#        for i in range(10000):
#            self.gpsGrid.append([])
#            for j in range(10000):
#                self.gpsGrid[i].append(None)
                
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
                if streetType=="services" or streetType=="bridleway" or streetType=="path" or streetType=="track" or streetType=="footway" or streetType=="pedestrian" or streetType=="cycleway" or streetType=="service" or streetType=="living_street" or streetType=="steps":
                    continue
                
                if "service" in tags:
                    continue
                
                if "parking" in tags:
                    continue
                
                if "amenity" in tags:
                    continue
                
                self.ways[osmid]=(tags, refs)
                for ref in refs:
                    wayRefList=list()
                    if ref in self.wayRefIndex:
                        wayRefList=self.wayRefIndex[ref]
                
                    wayRefList.append(osmid)
                    self.wayRefIndex[ref]=wayRefList
                
                if streetType=="motorway_link" or streetType=="primary_link" or streetType=="secondary_link":
                    continue
                
                if "name" in tags or "ref" in tags:
                    (name, ref)=self.getStreetNameInfo(tags)
                    if name=="" and ref=="":
                        print("cannot create indexname for "+str(tags))
                        continue


#                    if ref!="A1" and name!="Münchner Bundesstraße":
#                        continue
                    
                    if not (name, ref) in self.street_by_name.keys():
                        streetWayList=list()
                        streetWayList.append((osmid, tags, refs))
                        self.street_by_name[(name, ref)]=streetWayList
                    else:
                        streetWayList=self.street_by_name[(name, ref)]
                        streetWayList.append((osmid, tags, refs))
                
#                    if ref!="" and name!=ref:
#                        tags["name"]=ref
#                        if not (ref, ref) in self.street_by_name.keys():
#                            streetWayList=list()
#                            streetWayList.append((osmid, tags, refs))
#                            self.street_by_name[(ref, ref)]=streetWayList
#                        else:
#                            streetWayList=self.street_by_name[(ref, ref)]
#                            streetWayList.append((osmid, tags, refs))

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
                if name=="":
                    name=ref    
        elif streetType=="secondary" or streetType=="secondary_link":
            if ref!="":
                ref=ref.replace(' ', '')
                if name=="":
                    name=ref  
        elif streetType=="tertiary" or streetType=="tertiary_link":
            if ref!="":
                ref=ref.replace(' ', '')
                if name=="":
                    name=ref  
        elif streetType=="residential":
            None

        elif streetType=="unclassified":
            None

#        else:
#            print(str(tags))

        return (name, ref)
    
    def getWaysWithRef(self, ref):
        if ref in self.wayRefIndex:
            return self.wayRefIndex[ref]
        return None

    def findWayWithRefInAllWays(self, ref, fromWayId, streetInfo):
        possibleWays=list()
        wayIdList=self.getWaysWithRef(ref)
        if wayIdList==None:
            return possibleWays
        
        for wayid in wayIdList:
            tags=self.ways[wayid][0]
            refs=self.ways[wayid][1]
            
            if wayid==fromWayId:
                continue
#            if wayid in self.doneWays:
#                continue
            
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
        return possibleWays
    
    def findLinkWaysWithRefInAllWays(self, ref, fromWayId, streetInfo, streetType):
        possibleWays=list()
        wayIdList=self.getWaysWithRef(ref)
        if wayIdList==None:
            return possibleWays
        
        for wayid in wayIdList:
            tags=self.ways[wayid][0]
            refs=self.ways[wayid][1]
            
            if wayid==fromWayId:
                continue
            if wayid in self.doneWays:
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
        return possibleWays
    
    def findLinkEndWaysWithRefInAllWays(self, ref, fromWayId, streetInfo, streetType):
        wayIdList=self.getWaysWithRef(ref)
        if wayIdList==None:
            return (None, None, None)
        
        for wayid in wayIdList:
            tags=self.ways[wayid][0]
            refs=self.ways[wayid][1]
            
            if wayid==fromWayId:
                continue
#            if wayid in self.doneWays:
#                continue
            
            if "highway" in tags:
                newStreetType=tags["highway"]
                if newStreetType!=streetType+"_link":
                    for wayRef in refs:
                        if wayRef==ref:
                            return (wayid, tags, refs)
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

    def printRelationCoords(self, name):
        for osmid, relation in self.relations.items():
            try:
                if relation[0]["name"]==name:
                    for way in relation[1]:
                        if way[1]=="way":
                            wayRef=self.ways[way[0]]
                            for ref in wayRef[1]:   
                                print("%f %f"%(self.coords[ref][1], self.coords[ref][0]))
            except KeyError:
                None
        
    def postprocessWays(self):
        i=1
        for (name, ref),ways in self.street_by_name.items():
#            print((name, ref))
            self.waysCopy=ways
            print("process %d of %d"%(i, len(self.street_by_name)))

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
                
            i=i+1
                                     
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
                trackItem["lat"]=self.coords[ref][1]
                trackItem["lon"]=self.coords[ref][0]
                
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
                trackItem["lat"]=self.coords[ref][1]
                trackItem["lon"]=self.coords[ref][0]
                
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
        p = OSMParser(1, nodes_callback=self.parse_nodes, 
                  ways_callback=self.parse_ways, 
                  relations_callback=None,
                  coords_callback=self.parse_coords)
        p.parse(self.file)

    def dump(self):
        dump=bz2.BZ2File(self.getDumpFile(), "w")
        dump.write("streetNameIndex\n".encode())

        for (ref, name), waylist in self.streetNameIndex.items():
            dump.write(ref.encode()+"|".encode()+name.encode()+"::".encode())
            for wayid in waylist:
                dump.write(str(wayid).encode()+"|".encode())
            dump.write("\n".encode())
                
        dump.write("streetIndex\n".encode())

        for wayId in self.streetIndex.keys():
            dump.write(str(wayId).encode()+"::".encode())
            track=self.streetIndex[wayId]
            (ref, name)=track["name"]
            dump.write(ref.encode()+"|".encode()+name.encode())
            
            trackList=track["track"]
            dump.write("::".encode())

            for trackItem in trackList:
                dump.write("|".encode())
                
                if "lat" in trackItem.keys():
                    dump.write(str(trackItem["lat"]).encode()+":".encode())
                if "lon" in trackItem.keys():
                    dump.write(str(trackItem["lon"]).encode()+":".encode())
                if "wayId" in trackItem.keys():
                    dump.write(str(trackItem["wayId"]).encode()+":".encode())
                if "ref" in trackItem.keys():
                    dump.write(str(trackItem["ref"]).encode()+":".encode())
                if "oneway" in trackItem.keys():
                    dump.write(str(trackItem["oneway"]).encode()+":".encode())
                if "type" in trackItem.keys():
                    dump.write(str(trackItem["type"]).encode())
                if "crossing" in trackItem.keys():
                    crossingList=trackItem["crossing"]
                    dump.write(":".encode())
                    for crossing in crossingList:
                        dump.write(str(crossing).encode()+"-".encode())
                if "start" in trackItem.keys():
                    dump.write(str(trackItem["start"]).encode())
                if "end" in trackItem.keys():
                    dump.write(str(trackItem["end"]).encode())
            dump.write("|".encode())
            dump.write("\n".encode())


        dump.write("wayRefIndex\n".encode())
        for ref, waylist  in self.wayRefIndex.items():
            dump.write(str(ref).encode()+"::".encode())
            for wayid in waylist:
                dump.write(str(wayid).encode()+"|".encode())
            dump.write("\n".encode())

        dump.write("wayToStreetIndex\n".encode())
        for wayid, streetWayId  in self.wayToStreetIndex.items():
            dump.write(str(wayid).encode()+"|".encode()+str(streetWayId).encode()+"::".encode())
        dump.write("\n".encode())
            
        dump.close()
        
    def loadDump(self):
        if os.path.exists(self.getDumpFile()):
            dump=bz2.BZ2File(self.getDumpFile(), "r")
            streetIndex=False
            streetNameIndex=False
            wayRefIndex=False
            wayToStreetIndex=False
            for line in dump:
                line=line.decode()
                if line=="streetNameIndex\n":
                    streetNameIndex=True
                    streetIndex=False
                    wayRefIndex=False
                    wayToStreetIndex=False
                    continue
                if line=="streetIndex\n":
                    streetIndex=True
                    streetNameIndex=False
                    wayRefIndex=False
                    wayToStreetIndex=False
                    continue
                if line=="wayRefIndex\n":
                    streetIndex=False
                    streetNameIndex=False
                    wayRefIndex=True
                    wayToStreetIndex=False
                    continue
                if line=="wayToStreetIndex\n":
                    streetIndex=False
                    streetNameIndex=False
                    wayRefIndex=False
                    wayToStreetIndex=True
                    continue
                if wayRefIndex:
                    (ref, waylist)=line.split("::")
                    ways=list()
                    for wayid in waylist.split("|"):
                        if len(wayid)!=0 and wayid!="\n":
                            ways.append(int(wayid))
                    self.wayRefIndex[ref]=ways
                if wayToStreetIndex:
                    for item in line.split("::"):
                        if len(item)!=0 and item!="\n":
                            wayid, streetWayId=item.split("|")     
                            self.wayToStreetIndex [int(wayid)]=int(streetWayId)         
                if streetNameIndex:
                    (streetInfo,waylist)=line.split("::")
                    (name, ref)=streetInfo.split("|")
                    ways=list()
                    for wayid in waylist.split("|"):
                        if len(wayid)!=0 and wayid!="\n":
                            ways.append(int(wayid))
                    self.streetNameIndex[(name, ref)]=ways
                if streetIndex:
                    (wayId, name, restLine)=line.split("::")
                    trackInfo=dict()
                    trackInfo["name"]=name
                    trackList=list()
                    for trackItemData in restLine.split("|"):
                        if len(trackItemData)==0 or trackItemData=="\n":
                            continue
                        
                        trackItem=dict()
                        if trackItemData=="start":
                            trackItem["start"]="start"
                        elif trackItemData=="end":
                            trackItem["end"]="end"
                        else:
                            trackData=trackItemData.split(":")
                            
                            if len(trackData)>=6:
                                trackItem["lat"]=float(trackData[0])
                                trackItem["lon"]=float(trackData[1])
                                trackItem["wayId"]=int(trackData[2])
                                trackItem["ref"]=int(trackData[3])
                                trackItem["oneway"]=bool(trackData[4])
                                trackItem["type"]=trackData[5]

                            if len(trackData)==7:

                                crossingList=list()
                                crossingListData=trackData[6].split("-")
                                for crossing in crossingListData:
                                    if len(crossing)!=0 and crossing!="\n":
                                        crossingList.append(int(crossing))
                                trackItem["crossing"]=crossingList
                        trackList.append(trackItem)
                    trackInfo["track"]=trackList
                    self.streetIndex[int(wayId)]=trackInfo
            dump.close()
    def getDumpFile(self):
        return self.file+".dump.bz2"
    
    def dumpExists(self):
        return os.path.exists(self.getDumpFile())
        
def main(argv):    
    try:
        osmFile=argv[1]
    except IndexError:
        osmFile='/home/maxl/Downloads/salzburg-streets.osm.bz2'
    p = OSMParserData(osmFile)
    if not p.dumpExists():
        p.parse()
        p.postprocessWays()
#        print(len(p.coords.keys()))
#        p.printGPSGrid()
        p.dump()
#        print(p.wayRefIndex)
#        print(p.wayToStreetIndex)
    else:
        p.loadDump()
#        print(p.wayRefIndex)
#        print(p.wayToStreetIndex)
    #p.parse('salzburg-streets.osm')
#    p.parse('test1.osm')
    
    #print(t.coords)
    #print(t.nodes)
    #print(t.ways)
    #print(t.relations)
    
    
#    t.printWayCoords("teststrasse")
#    track=t.track
#    print(track)
#    print(p.streetNameIndex)
#    print(p.streetIndex[p.streetNameIndex["teststrasse"]])
#    t.printWayCoordsReverse("teststrasse")
#    track=t.track
#    print(track)
        
    #print("")
#    t.printRelationCoords("teststrasse")
    
#    t.printWayCoords("Münchner Bundesstraße")

#    print(str(p.streetNameIndex))
#    print(str(p.streetIndex.keys()))
#    waylist=p.streetNameIndex[("Münchner Bundesstraße", "B155")]
#    print(str(waylist))
#    
#        
#    print(p.streetNameIndex[("A1", "A1")])
#    print(p.streetNameIndex[("A10", "A10")])
#
##    print(str(waylist))
#    print(p.streetIndex[p.wayToStreetIndex[p.streetNameIndex[("A1", "A1")][0]]]["name"])
#   
#    print(p.streetIndex[p.wayToStreetIndex[43322691]]["name"])
#    print(p.streetIndex[p.wayToStreetIndex[116169365]]["name"])

#    for wayid in waylist:
#        print(p.streetIndex[wayid])
#    t.printWayCoords("A10")

#    track=t.track
#    print(track)
    #print(track[-1])
    #print(t.printWayCoordsReverse("Münchner Bundesstraße"))
    
    #print("xxx")
    #t.printWayCoords("Münchner Straße")
    
    #print("")
    #t.printRelationCoords("Münchner Straße")
    # done

if __name__ == "__main__":
    main(sys.argv)  
    

