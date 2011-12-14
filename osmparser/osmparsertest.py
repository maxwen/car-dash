'''
Created on Dec 13, 2011

@author: maxl
'''
from osmparser.parser.simple import OSMParser

# simple class that handles the parsed OSM data.

class ParserTestBase(object):
    osm_filename = None
    ways_filter = None
    nodes_filter = None
    relations_filter = None
    street_by_name=None
    def __init__(self):
        self.nodes = dict()
        self.coords = dict()
        self.ways = dict()
        self.relations = dict()
        self.street_by_name=dict()
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
#                print(way)
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
               
    def printWayCoords(self, name):
        if name in self.street_by_name:
            ways=self.street_by_name[name] 

            way=self.findStartWay(ways)
                
            while way!=None:
                refStart=way[2][0]
                refEnd=way[2][-1]
                way=self.findWayWithStartRef(ways, refEnd)
                if way!=None:
                    print("%f %f"%(self.coords[refStart][1], self.coords[refStart][0]))
                else:
                    print("%f %f"%(self.coords[refEnd][1], self.coords[refEnd][0]))
                    
                
    def findWayWithStartRef(self, ways, startRef):
        for way in ways:
            if way[2][0]==startRef:
                return way
        return None
    
    def findWayWithEndRef(self, ways, endRef):
        for way in ways:
            if way[2][-1]==endRef:
                return way
        return None
    
    def findStartWay(self, ways):
        for way in ways:
            startRef=way[2][0]
            if self.findWayWithEndRef(ways, startRef)==None:
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
                
t=ParserTestBase()

p = OSMParser(4, nodes_callback=t.parse_nodes, 
              ways_callback=t.parse_ways, 
              relations_callback=t.parse_relations,
              coords_callback=t.parse_coords)
p.parse('/home/maxl/Downloads/salzburg-streets.osm.bz2')
#p.parse('salzburg-streets.osm')
#p.parse('test1.osm')

#print(t.coords)
#print(t.nodes)
#print(t.ways)
#print(t.relations)

#t.printWayCoords("teststrasse")
#print("")
#t.printRelationCoords("teststrasse")

t.printWayCoords("Münchner Bundesstraße")
#print("")
#t.printRelationCoords("Münchner Straße")
# done
