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
        self.streetIndex=dict()
        self.wayIndex=dict()
        self.file=file
        self.doneRefs=list()
        self.doneWays=list()
        self.startCount=0
        self.endCount=0
        
    def parse_nodes(self, node):
        for osmid, tags, coords in node:
            self.nodes[osmid]=(tags, coords)
                    
    def parse_coords(self, coord):
        for osmid, lat, lon in coord:
            self.coords[osmid]=(lat, lon)
            
    def parse_ways(self, way):
        for osmid, tags, refs in way:
#            self.ways[osmid]=(tags, refs)
            try:
                if "highway" in tags and "name" in tags:
                    streetType=tags["highway"]
                    if streetType=="path" or streetType=="track" or streetType=="footway" or streetType=="pedestrian" or streetType=="cycleway":
                        continue
                    
                    self.ways[osmid]=(tags, refs)

                    indexName=self.getIndexNameOfStreet(tags)
                        
                    tags["index"]=indexName
                    if indexName!="Alpenstraße":
                        continue
                        
                    if not indexName in self.street_by_name.keys():
                        streetWayList=list()
                        streetWayList.append((osmid, tags, refs))
                        self.street_by_name[indexName]=streetWayList
                    else:
                        streetWayList=self.street_by_name[indexName]
                        streetWayList.append((osmid, tags, refs))
            except KeyError as msg:
                print(msg)
    def parse_relations(self, relation):
        for osmid, tags, ways in relation:
            self.relations[osmid]=(tags, ways)
            
    def getIndexNameOfStreet(self, tags):
        name=tags["name"]
        indexName=name
        streetType=tags["highway"]
        if "ref" in tags:
            ref=tags["ref"]
            if streetType=="motorway":
                indexName=ref.replace(' ', '')
            else:
                if "postal_code" in tags:
                    indexName=indexName+"("+tags["postal_code"]+")"
                if "is_in" in tags:
                    indexName=indexName+"("+tags["is_in"]+")"
        return indexName
    
    def findWayWithRefAndCoordsInAllWays(self, ref, streetName):
        possibleWays=list()
        for wayid in self.ways.keys():
            tags=self.ways[wayid][0]
            refs=self.ways[wayid][1]
            
            indexName=self.getIndexNameOfStreet(tags)

            if indexName==streetName:
                continue

#            if refs[0]==ref:
#                possibleWays.append((wayid, tags, refs))
            for wayRef in refs:
                if wayRef==ref:
                    possibleWays.append((wayid, tags, refs))
                else:
                    try:
                        coords1=self.coords[wayRef]
                        coords2=self.coords[ref]
                        if coords1==coords2:
                            possibleWays.append((wayid, tags, refs))
                    except KeyError:
                        None
        return possibleWays
    
    def findWayWithRefAndCoords(self, ways, ref):
        possibleWays=list()
        for way in ways:
            if way[0] in self.doneWays:
                continue

            for wayRef in way[2]:
                if wayRef==ref:
                    possibleWays.append(way)
                else:
                    try:
                        coords1=self.coords[wayRef]
                        coords2=self.coords[ref]
                        if coords1==coords2:
                            possibleWays.append(way)
                    except KeyError:
                        None

        return possibleWays
    
    def findWayWithStartRef(self, ways, startRef):
        possibleWays=list()
        for way in ways:
            if way[0] in self.doneWays:
                continue
            if way[2][0]==startRef:
                possibleWays.append(way)
        return possibleWays
    
    def findWayWithEndRef(self, ways, endRef):
        possibleWays=list()
        for way in ways:
            if way[0] in self.doneWays:
                continue
            if way[2][-1]==endRef:
                possibleWays.append(way)
        return possibleWays
    
    def findStartWay(self, ways):
        for way in ways:
            startRef=way[2][0]
            possibleWays=self.findWayWithEndRef(ways, startRef)
            if len(possibleWays)==0:
                return way
        return ways[0]
    
    def findEndWay(self, ways):
        for way in ways:
            endRef=way[2][-1]
            possibleWays=self.findWayWithStartRef(ways, endRef)
            if len(possibleWays)==0:
                return way        
        return ways[0]
            
    def findMotorwayJunctions(self, ref):
        if ref in self.nodes:
            tags, coords=self.nodes[ref]
            if "highway" in tags:
                nodeType=tags["highway"]
                if nodeType=="motorway_junction":
                    return ref
        return None

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
        i=0
        for name,ways in self.street_by_name.items():
            self.waysCopy=ways
            print("process %d of %d"%(i, len(self.street_by_name)))

            self.doneWays=list()
            self.doneRefs=list()
            
            while len(self.waysCopy)!=0:
                way=self.findStartWay(self.waysCopy)

                self.track=dict()
                self.track["name"]=name
                self.track["track"]=list()
                
#                trackItem=dict()
#                trackItem["start"]="start"
#                self.startCount=self.startCount+1
#                self.track["track"].append(trackItem)
                
                if way!=None:
                    self.resolveWay(way, name, False)
                    
#                    trackItem=dict()
#                    trackItem["end"]="end"
#                    self.endCount=self.endCount+1
#                    self.track["track"].append(trackItem)
                    
                    dictName=name
                    if dictName in self.streetIndex:
                        dictName=name+"_"+str(way[0])
                    self.streetIndex[dictName]=way[0]
                    self.wayIndex[way[0]]=self.track
#                    print(self.wayIndex[way[0]])
#                    print(self.streetIndex[name])

                    print(self.startCount)
                    print(self.endCount)
                if len(self.waysCopy)!=0:
                    None
                
            i=i+1
                                              
    def resolveWay(self, way, streetName, reverse):
        if way==None:
            return
        

        streetType=""
#        i=0

#        print(way[2])
        if reverse:
            refList=way[2][::-1]
#            print("reverse "+str(refList))
        else:
            refList=way[2]
#            print("normal "+str(refList))
#        for ref in way[2][0:-1]:
        for ref in refList:
            try:
#                if i>0:
#                    if ref in self.doneRefs:
#                        print(ref)
#                        break
#                i=i+1
                trackItem=dict()
                trackItem["wayId"]=way[0]
                trackItem["ref"]=ref
                trackItem["lat"]=self.coords[ref][1]
                trackItem["lon"]=self.coords[ref][0]
                
                wayTags=way[1]
                if "highway" in wayTags:
                    streetType=wayTags["highway"]
                
                way_crossings=self.findWayWithRefAndCoordsInAllWays(ref, streetName)
                if len(way_crossings)!=0:
                    for way_crossing in way_crossings:
                        wayid, tags, refs=way_crossing

#                        if "name" in tags:
#                            name=tags["name"]
#                        else:
#                            name="unknown"
                        trackItem["crossing"]=wayid
#                        print(name + " crossing mit "+str(wayid))
                
                if streetType=="motorway":
                    nodeid=self.findMotorwayJunctions(ref)
                    if nodeid!=None:
                        trackItem["crossing"]=nodeid

                self.track["track"].append(trackItem)

            except KeyError:
                print("no node with id=%d"%(ref))

            self.doneRefs.append(ref)

            possibleWays=self.findWayWithRefAndCoords(self.waysCopy, ref)  
            if len(possibleWays)!=0:
                addStart=True
#                if len(possibleWays)!=1:
#                    addStart=True
    
                for possibleWay in possibleWays:  
                    if possibleWay in self.waysCopy:
                        self.waysCopy.remove(possibleWay)
                    else:
                        continue
        
                    if addStart:
                        trackItem=dict()
                        trackItem["start"]="start"
                        self.startCount=self.startCount+1
                        self.track["track"].append(trackItem)

                    reverse=False
                    if possibleWay[2][0]==ref:
                        reverse=False
                    elif possibleWay[2][-1]==ref:
                        reverse=True
                    self.resolveWay(possibleWay, streetName, reverse)

                    if addStart:
                        trackItem=dict()
                        trackItem["end"]="end"
                        self.endCount=self.endCount+1
                        self.track["track"].append(trackItem)
    
    def parse(self):
        p = OSMParser(2, nodes_callback=self.parse_nodes, 
                  ways_callback=self.parse_ways, 
                  relations_callback=None,
                  coords_callback=self.parse_coords)
        p.parse(self.file)

    def dump(self):
        dump=bz2.BZ2File(self.getDumpFile(), "w")
        for name, wayId in self.streetIndex.items():
            dump.write(name.encode()+"::".encode()+str(wayId).encode()+"\n".encode())
        dump.write("------\n".encode())

        for wayId in self.wayIndex.keys():
            dump.write(str(wayId).encode()+"::".encode())
            track=self.wayIndex[wayId]
            dump.write(track["name"].encode())
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
                    dump.write(str(trackItem["ref"]).encode())
                if "crossing" in trackItem.keys():
                    dump.write(":".encode()+str(trackItem["crossing"]).encode())
                if "start" in trackItem.keys():
                    dump.write(str(trackItem["start"]).encode())
                if "end" in trackItem.keys():
                    dump.write(str(trackItem["end"]).encode())
                
            dump.write("\n".encode())

        dump.close()
        
    def loadDump(self):
        if os.path.exists(self.getDumpFile()):
            dump=bz2.BZ2File(self.getDumpFile(), "r")
            streetIndex=True
            for line in dump:
                line=line.decode()
                if line=="------\n":
                    streetIndex=False
                    continue
                if streetIndex:
                    (name,wayId)=line.split("::")
                    self.streetIndex[name]=int(wayId)
                else:
                    (wayId, name, restLine)=line.split("::")
                    trackInfo=dict()
                    trackInfo["name"]=name
                    trackList=list()
                    for trackItemData in restLine.split("|"):
                        if len(trackItemData)==0:
                            continue
                        
                        trackItem=dict()
                        if trackItemData=="start":
                            trackItem["start"]="start"
                        elif trackItemData=="end":
                            trackItem["end"]="end"
                        else:
                            trackData=trackItemData.split(":")
                            
                            if len(trackData)==4:
                                trackItem["lat"]=float(trackData[0])
                                trackItem["lon"]=float(trackData[1])
                                trackItem["wayId"]=int(trackData[2])
                                trackItem["ref"]=int(trackData[3])
                            elif len(trackData)==5:
                                trackItem["lat"]=float(trackData[0])
                                trackItem["lon"]=float(trackData[1])
                                trackItem["wayId"]=int(trackData[2])
                                trackItem["ref"]=int(trackData[3])
                                trackItem["crossing"]=int(trackData[4])
                        trackList.append(trackItem)
                    trackInfo["track"]=trackList
                    self.wayIndex[int(wayId)]=trackInfo
            dump.close()
    def getDumpFile(self):
        return self.file+".dump.bz2"
    
    def dumpExists(self):
        return os.path.exists(self.getDumpFile())
        
def main(argv):     
    p = OSMParserData('/home/maxl/Downloads/salzburg-city-streets.osm')
#    p = OSMParserData('test1.osm')
    if not p.dumpExists():
        p.parse()
        p.postprocessWays()
        p.dump()
    else:
        p.loadDump()
    #p.parse('salzburg-streets.osm')
#    p.parse('test1.osm')
    
    #print(t.coords)
    #print(t.nodes)
    #print(t.ways)
    #print(t.relations)
    
    
#    t.printWayCoords("teststrasse")
#    track=t.track
#    print(track)
#    print(p.streetIndex)
#    print(p.wayIndex[p.streetIndex["teststrasse"]])
#    t.printWayCoordsReverse("teststrasse")
#    track=t.track
#    print(track)
        
    #print("")
#    t.printRelationCoords("teststrasse")
    
#    t.printWayCoords("Münchner Bundesstraße")
    print(p.wayIndex[p.streetIndex["Alpenstraße"]])

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
    

