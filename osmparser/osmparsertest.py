'''
Created on Dec 13, 2011

@author: maxl
'''
from osmparser.parser.simple import OSMParser
import sys

# simple class that handles the parsed OSM data.

class ParserTestBase(object):
    def __init__(self):
        self.nodes = dict()
        self.coords = dict()
        self.ways = dict()
        self.relations = dict()
        self.street_by_name=dict()
        self.track=list()
        self.doneWays=list()
    def parse_nodes(self, node):
#        print(node)
        for osmid, tags, coords in node:
            self.nodes[osmid]=(tags, coords)
    def parse_coords(self, coord):
#        print(coord)
        for osmid, lat, lon in coord:
            self.coords[osmid]=(lat, lon)
    def parse_ways(self, way):
        for osmid, tags, refs in way:
            self.ways[osmid]=(tags, refs)
            try:
                if "highway" in tags and "name" in tags:
                    name=tags["name"]
    #                print(name)
                    if not name in self.street_by_name.keys():
                        streetWayList=list()
                        streetWayList.append((osmid, tags, refs))
                        self.street_by_name[name]=streetWayList
                    else:
                        streetWayList=self.street_by_name[name]
                        streetWayList.append((osmid, tags, refs))
            except KeyError:
                None
    def parse_relations(self, relation):
#        print(relation)
        for osmid, tags, ways in relation:
            self.relations[osmid]=(tags, ways)
             
    def handleWay(self, ways, way, doneWays):
        if way==None:
            return
        
        for ref in way[2][0:-1]:
            self.track.append((self.coords[ref][1], self.coords[ref][0]))

        refEnd=way[2][-1]
        doneWays.append(way[0])

        possibleWays=self.findWayWithStartRef(ways, refEnd, doneWays)  
        if len(possibleWays)==0:
            try:
                self.track.append((self.coords[refEnd][1], self.coords[refEnd][0]))
                self.track.append(("end", "end"))
            except KeyError:
                print("no node with id=%d"%(refEnd))
        else:
            if len(possibleWays)!=1:
                self.track.append(("start", "start"))
#                print(way)
#                print(refEnd)
#                print(possibleWays)
            for possibleWay in possibleWays:  
                self.handleWay(ways, possibleWay, doneWays)
            
    def printWayCoords(self, name):
        self.track=list()
        doneWays=list()
        
        if name in self.street_by_name:
            ways=self.street_by_name[name] 

            way=self.findStartWay(ways)
            if way!=None:
                self.track.append(("start", "start"))
                self.handleWay(ways, way, doneWays)
                
                   
    def handleWayReverse(self, ways, way, doneWays):
        if way==None:
            return
        
        for ref in way[2][-1:0:-1]:
            self.track.append((self.coords[ref][1], self.coords[ref][0]))

        refStart=way[2][0]
        doneWays.append(way[0])

        possibleWays=self.findWayWithEndRef(ways, refStart, doneWays)  
        if len(possibleWays)==0:
            try:
                self.track.append((self.coords[refStart][1], self.coords[refStart][0]))
                self.track.append(("end", "end"))
            except KeyError:
                print("no node with id=%d"%(refStart))
        else:
            if len(possibleWays)!=1:
                self.track.append(("start", "start"))
#                print(way)
#                print(refEnd)
#                print(possibleWays)
            for possibleWay in possibleWays: 
                self.handleWayReverse(ways, possibleWay, doneWays)  
                           
    def printWayCoordsReverse(self, name):
        self.track=list()
        doneWays=list()
        
        if name in self.street_by_name:
            ways=self.street_by_name[name] 

            way=self.findEndWay(ways)
            if way!=None:
                self.track.append(("start", "start"))
                self.handleWayReverse(ways, way, doneWays)

    def findWayWithStartRef(self, ways, startRef, doneWays):
        possibleWays=list()
        for way in ways:
            if way[0] in doneWays:
                continue
            if way[2][0]==startRef:
                possibleWays.append(way)
        return possibleWays
    
    def findWayWithEndRef(self, ways, endRef, doneWays):
        possibleWays=list()
        for way in ways:
            if way[0] in doneWays:
                continue
            if way[2][-1]==endRef:
                possibleWays.append(way)
        return possibleWays
    
    def findStartWay(self, ways):
        for way in ways:
            startRef=way[2][0]
            possibleWays=self.findWayWithEndRef(ways, startRef, list())
            if len(possibleWays)==0:
                return way
        return None
    
    def findEndWay(self, ways):
        for way in ways:
            endRef=way[2][-1]
            possibleWays=self.findWayWithStartRef(ways, endRef, list())
            if len(possibleWays)==0:
                return way        
        return None
            
            
    
    def printRelationCoords(self, name):
        for osmid, relation in self.relations.items():
            try:
                if relation[0]["name"]==name:
#                    print(osmid)
                    for way in relation[1]:
                        if way[1]=="way":
#                            print(way)
                            wayRef=self.ways[way[0]]
                            for ref in wayRef[1]:   
#                                print(ref)                         
                                print("%f %f"%(self.coords[ref][1], self.coords[ref][0]))
            except KeyError:
                None
              
              
def main(argv): 
    t=ParserTestBase()
    
    p = OSMParser(8, nodes_callback=t.parse_nodes, 
                  ways_callback=t.parse_ways, 
                  relations_callback=t.parse_relations,
                  coords_callback=t.parse_coords)
#    p.parse('/home/maxl/Downloads/salzburg-streets.osm')
    #p.parse('salzburg-streets.osm')
    p.parse('test1.osm')
    
    #print(t.coords)
    #print(t.nodes)
    #print(t.ways)
    #print(t.relations)
    
    
    t.printWayCoords("teststrasse")
    track=t.track
    print(track)
    t.printWayCoordsReverse("teststrasse")
    track=t.track
    print(track)
        
    #print("")
#    t.printRelationCoords("teststrasse")
    
    #t.printWayCoords("Münchner Bundesstraße")
    #track=t.track
    #print(track[0])
    #print(track[-1])
    #print(t.printWayCoordsReverse("Münchner Bundesstraße"))
    
    #print("xxx")
    #t.printWayCoords("Münchner Straße")
    
    #print("")
    #t.printRelationCoords("Münchner Straße")
    # done

if __name__ == "__main__":
    main(sys.argv)  
    

