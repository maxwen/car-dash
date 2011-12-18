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
        self.doneWays=list()
        self.wayRefIndex=dict()
        
    def parse_nodes(self, node):
        for osmid, tags, coords in node:
            self.nodes[osmid]=(tags, coords)
                    
    def parse_coords(self, coord):
        for osmid, lat, lon in coord:
            self.coords[osmid]=(lat, lon)
            
    def parse_ways(self, way):
        for osmid, tags, refs in way:
#            self.ways[osmid]=(tags, refs)
            if "highway" in tags:
                streetType=tags["highway"]
                if streetType=="path" or streetType=="track" or streetType=="footway" or streetType=="pedestrian" or streetType=="cycleway" or streetType=="service":
                    continue
                
                self.ways[osmid]=(tags, refs)
                for ref in refs:
                    wayRefList=list()
                    if ref in self.wayRefIndex:
                        wayRefList=self.wayRefIndex[ref]
                        if type(wayRefList)==type(0):
                            None
                
                    wayRefList.append(osmid)
                    self.wayRefIndex[ref]=wayRefList
                
                if "name" in tags or "ref" in tags:
                    indexName=self.getIndexNameOfStreet(tags)
                        
                    tags["index"]=indexName
                    if indexName!="A1" and indexName!="B150" and indexName!="B156" and indexName!="Europastraße" and indexName!="Europastraße" and indexName!="Münchner Bundesstraße":
                        continue
                        
                    if not indexName in self.street_by_name.keys():
                        streetWayList=list()
                        streetWayList.append((osmid, tags, refs))
                        self.street_by_name[indexName]=streetWayList
                    else:
                        streetWayList=self.street_by_name[indexName]
                        streetWayList.append((osmid, tags, refs))
                
    def parse_relations(self, relation):
        for osmid, tags, ways in relation:
            self.relations[osmid]=(tags, ways)
            
    def getIndexNameOfStreet(self, tags):
        streetType=tags["highway"]

        if "name" in tags:
            name=tags["name"]
            
            if streetType=="motorway":
                if "ref" in tags:
                    ref=tags["ref"]
                    name=ref.replace(' ', '')
        elif "ref" in tags:
            name=tags["ref"]
            
        indexName=name
#        if "postal_code" in tags:
#            indexName=indexName+"("+tags["postal_code"]+")"
#        if "is_in" in tags:
#            indexName=indexName+"("+tags["is_in"]+")"
        return indexName
    
    def getWaysWithRef(self, ref):
        if ref in self.wayRefIndex:
            return self.wayRefIndex[ref]
        return None

    def findWayWithRefAndCoordsInAllWays(self, ref, streetName):
        possibleWays=list()
        wayIdList=self.getWaysWithRef(ref)
        if wayIdList==None:
            return possibleWays
        
        for wayid in wayIdList:
            tags=self.ways[wayid][0]
            refs=self.ways[wayid][1]
            if wayid in self.doneWays:
                continue
            
            if "highway" in tags:
                if "name" in tags or "ref" in tags:
                    if streetName==None:
                        return possibleWays
                    
                    indexName=self.getIndexNameOfStreet(tags)
        
                    if indexName==streetName:
                        continue

                for wayRef in refs:
                    if wayRef==ref:
                        possibleWays.append((wayid, tags, refs))
                    else:
                        try:
                            coords1=self.coords[wayRef]
                            coords2=self.coords[ref]
                            if coords1==coords2:
                                possibleWays.append((wayid, tags, refs))
                        except KeyError as msg:
                            #print("findWayWithRefAndCoordsInAllWays no node with "+str(wayRef)+ ", "+str(ref))
                            None
        return possibleWays
    
    def findWayWithRefAndCoords(self, ways, ref):
        possibleWays=list()
        for way in ways:
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
            if way[2][0]==startRef:
                possibleWays.append(way)
        return possibleWays
    
    def findWayWithEndRef(self, ways, endRef):
        possibleWays=list()
        for way in ways:
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
           
    def findMotorwayLinks(self, ref):
        wayIdList=self.getWaysWithRef(ref)
        if wayIdList==None:
            return (None, None, None)
        
        for wayid in wayIdList:
            if wayid in self.doneWays:
                continue
            tags=self.ways[wayid][0]
            refs=self.ways[wayid][1]
            if "highway" in tags:
                streetType=tags["highway"]
                if streetType=="motorway_link":
                    if refs[0]==ref:
                        return (wayid, tags, refs)
                    if refs[-1]==ref:
                        return (wayid, tags, refs)
        return (None, None, None)
    
    def findMotorwayEndLinks(self, ref):
        possibleWays=list()
        wayIdList=self.getWaysWithRef(ref)
        if wayIdList==None:
            return possibleWays
        
        for wayid in wayIdList:
            tags=self.ways[wayid][0]
            refs=self.ways[wayid][1]
            if wayid in self.doneWays:
                continue
            
            if "highway" in tags:
                streetType=tags["highway"]
                if streetType!="motorway_link" and streetType!="motorway":
                    for wayRef in refs:
                        if wayRef==ref:
                            possibleWays.append((wayid, tags, refs))
                        else:
                            try:
                                coords1=self.coords[wayRef]
                                coords2=self.coords[ref]
                                if coords1==coords2:
                                    possibleWays.append((wayid, tags, refs))
                            except KeyError as msg:
                                None
        return possibleWays

    
#    def findMotorwayJunctions(self, ref):
#        if ref in self.nodes:
#            tags, coords=self.nodes[ref]
#            if "highway" in tags:
#                nodeType=tags["highway"]
#                if nodeType=="motorway_junction":
#                    return ref
#        return None

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
        for name,ways in self.street_by_name.items():
            self.waysCopy=ways
            print("process %d of %d"%(i, len(self.street_by_name)))

            self.doneWays=list()
            
            while len(self.waysCopy)!=0:
                way=self.findStartWay(self.waysCopy)
                
                if way!=None:   
                    self.track=dict()
                    self.track["name"]=name
                    self.track["track"]=list()                         
                    
                    (wayid, tags, refs)=way
                    
#                    oneway=False
#                    if "oneway" in tags:
#                        if tags["oneway"]=="yes":
#                            oneway=True
                            
                    self.resolveWay(way, name, False)
                    dictName=name
                    
#                    if oneway:
#                        dictName=name
#                    else:
#                        dictName=name

                    wayList=list()
                    if dictName in self.streetIndex:
                        wayList=self.streetIndex[dictName]
                    
                    wayList.append(wayid)
#                        if oneway:
#                            dictName=name+" (2)"
#                        else:
#                            dictName=name+" (wayid="+str(wayid)+")"
                            
                    self.streetIndex[dictName]=wayList
                    self.wayIndex[wayid]=self.track
                else:
                    print("no start way found "+str(ways))
                    break
                if len(self.waysCopy)!=0:
                    None
                
            i=i+1
                                              
    def resolveWay(self, way, streetName, reverse):
        if way==None:
            return
        
#        print(way[2])
        if reverse:
            refList=way[2][::-1]
#            print("reverse "+str(refList))
        else:
            refList=way[2]
#            print("normal "+str(refList))
        for ref in refList:
            try:
                trackItem=dict()
                trackItem["wayId"]=way[0]
                trackItem["ref"]=ref
                trackItem["lat"]=self.coords[ref][1]
                trackItem["lon"]=self.coords[ref][0]
                                
                streetType=""
                if "highway" in way[1]:
                    streetType=way[1]["highway"]
                    
                way_crossings=self.findWayWithRefAndCoordsInAllWays(ref, streetName)
                if len(way_crossings)!=0:
                    croosingList=list()
                    for way_crossing in way_crossings:
                        (wayid, tags, refs)=way_crossing
                        if "highway" in tags:
                            if streetType=="motorway_link":
                                newStreetType=tags["highway"]
                                if newStreetType!="motorway_link":
                                    croosingList.append(wayid)
                            else :
                                croosingList.append(wayid)
                    if len(croosingList)!=0:  
                        trackItem["crossing"]=croosingList
                
                if streetType=="motorway_link":
                    way_crossings=self.findMotorwayEndLinks(ref)
                    if len(way_crossings)!=0:
                        croosingList=list()
                        for way_crossing in way_crossings:
                            (wayid, tags, refs)=way_crossing
                            if "highway" in tags:
                                croosingList.append(wayid)
                                  
                        if len(croosingList)!=0:  
                            trackItem["crossing"]=croosingList
                  
                if streetType=="motorway" or streetType=="motorway_link":
                    wayid, tags, refs=self.findMotorwayLinks(ref)
                    if wayid!=None:                    
                            self.doneWays.append(wayid)
                            motorwayLink=(wayid, tags, refs)
        
                            newStreetName=None
    #                        if "name" in tags:
    #                            newStreetName=tags["name"]
                            
                            motorwayLinkTrackItem=dict()
                            motorwayLinkTrackItem["start"]="start"
                            self.track["track"].append(motorwayLinkTrackItem)
                            
                            reverse=False
                            if refs[0]==ref:
                                reverse=False
                            elif refs[-1]==ref:
                                reverse=True
                            self.resolveWay(motorwayLink, newStreetName, reverse)
                                
                            motorwayLinkTrackItem=dict()
                            motorwayLinkTrackItem["end"]="end"
                            self.track["track"].append(motorwayLinkTrackItem)

                self.track["track"].append(trackItem)

            except KeyError:
                print("resolveWay no node with %d"%(ref))

            possibleWays=self.findWayWithRefAndCoords(self.waysCopy, ref)  
            if len(possibleWays)!=0:
    
                for possibleWay in possibleWays:  
                    if possibleWay in self.waysCopy:
                        self.waysCopy.remove(possibleWay)
                    else:
                        continue
                    (wayid, tags, refs)=possibleWay
                    self.doneWays.append(wayid)

#                    if "junction" in tags:
#                        if tags["junction"]=="roundabout":
#                            for ref in refs:
#                                roundaboutTrackitem=dict()
#                                roundaboutTrackitem["wayId"]=wayid
#                                roundaboutTrackitem["ref"]=ref
#                                roundaboutTrackitem["lat"]=self.coords[ref][1]
#                                roundaboutTrackitem["lon"]=self.coords[ref][0]
#                                self.track["track"].append(roundaboutTrackitem)
#                            return
                        
                    streetTrackItem=dict()
                    streetTrackItem["start"]="start"
                    self.track["track"].append(streetTrackItem)

                    reverse=False
                    if possibleWay[2][0]==ref:
                        reverse=False
                    elif possibleWay[2][-1]==ref:
                        reverse=True
                    self.resolveWay(possibleWay, streetName, reverse)

                    streetTrackItem=dict()
                    streetTrackItem["end"]="end"
                    self.track["track"].append(streetTrackItem)
    
    def parse(self):
        p = OSMParser(4, nodes_callback=self.parse_nodes, 
                  ways_callback=self.parse_ways, 
                  relations_callback=None,
                  coords_callback=self.parse_coords)
        p.parse(self.file)

    def dump(self):
        dump=bz2.BZ2File(self.getDumpFile(), "w")
        for name, waylist in self.streetIndex.items():
            dump.write(name.encode()+"::".encode())
            for wayid in waylist:
                dump.write(str(wayid).encode()+"|".encode())
            dump.write("\n".encode())
                
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
                    crossingList=trackItem["crossing"]
                    dump.write(":".encode())
                    for crossing in crossingList:
                        dump.write(str(crossing).encode()+"-".encode())
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
                    (name,waylist)=line.split("::")
                    ways=list()
                    for wayid in waylist.split("|"):
                        if len(wayid)!=0 and wayid!="\n":
                            ways.append(int(wayid))
                    self.streetIndex[name]=ways
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
                                crossingList=list()
                                crossingListData=trackData[4].split("-")
                                for crossing in crossingListData:
                                    if len(crossing)!=0 and crossing!="\n":
                                        print(crossing)
                                        crossingList.append(int(crossing))
                                trackItem["crossing"]=crossingList
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
    waylist=p.streetIndex["Europastraße"]
    for wayid in waylist:
        print(p.wayIndex[wayid])

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
    

