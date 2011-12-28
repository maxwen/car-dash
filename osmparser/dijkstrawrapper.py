'''
Created on Dec 28, 2011

@author: maxl
'''

import math
from pygraph.classes.digraph import digraph
from pygraph.algorithms.minmax import shortest_path, shortest_path_bellman_ford
from pygraph.algorithms.generators import generate
from pygraph.mixins import labeling

class Edge():
    def __init__(self):
        self.source=0
        self.target=0
        self.id=0
        self.cost=0
        self.reverseCost=0
        
    def __repr__(self):
        return "%d %d %d %d %d"%(self.id, self.source, self.target, self.cost, self.reverseCost)
    
    def fillEdge(self, id, source, target, cost, reverseCost):
        self.source=source
        self.target=target
        self.id=id
        self.cost=cost
        self.reverseCost=reverseCost
        
class DijkstraWrapper():
    def __init__(self, cursor):
        self.cursor=cursor
        self.gr=None
        self.directed=True
        self.hasReverseCost=True

        
    def edgeFromDB(self, x):
        edgeId=x[0]
        length=x[1]
        oneway=x[2]
        source=x[3]
        target=x[4]
        return (edgeId, length, oneway, source, target)

    def fillEdges(self):
        edgeList=list()
        self.cursor.execute("SELECT id, length, oneway, source, target from edgeTable")
        allentries=self.cursor.fetchall()
        for x in allentries:
            edgeId, length, oneway, source, target=self.edgeFromDB(x)
                  
            edge=Edge()
            if oneway:
                reverseCost=length*100000
            else:
                reverseCost=length
            edge.fillEdge(edgeId, source, target, length, reverseCost)
            edgeList.append(edge)
        return edgeList    

    def route(self, gr, st, startNode, targetNode):
        lastnode = targetNode
        path = []
        while lastnode != startNode:
            nextnode = st[lastnode]
            assert nextnode in gr.neighbors(lastnode)
            path.append((lastnode, st[lastnode]))
            lastnode = nextnode
        path.reverse()
        print(path)
        return path
    
    def dijkstra(self, startNode, targetNode):       
        if not self.gr.has_node(startNode):
            print("start node not found %d"%(startNode))
            return None, None
        
        if not self.gr.has_node(targetNode):
            print("target node not found %d"%(targetNode))
            return None, None

        pathEdgeList=list()
        pathLen=0
        
        st, dist = shortest_path(self.gr, startNode)                    
        path=self.route(self.gr, st, startNode, targetNode)        
                
        for source, target in path:
            pathEdgeList.append(int(self.gr.edge_label((source, target))))
                
        if targetNode in dist:
            pathLen=dist[targetNode]
            
        return pathEdgeList, pathLen
        
    def initGraph(self):
        self.allEdgesList=self.fillEdges()
        
        self.gr=digraph()
        for edge in self.allEdgesList:
            edgeId=edge.id
            source=edge.source
            target=edge.target
            cost=edge.cost
            reverseCost=edge.reverseCost
            
            if source==626 and target==2862:
                None
            
            if source==2862 and target==626:
                None
                
            if not self.gr.has_node(source):
                self.gr.add_node(source, ["source", source])
            
            if not self.gr.has_node(target):
                self.gr.add_node(target, ["target", target])
            
            if not self.gr.has_edge((source, target)):
                self.gr.add_edge((source, target), cost, str(edgeId))            
            else:
                cost1=self.gr.edge_weight((source, target))
                if cost<cost1:
                    self.gr.del_edge((source, target))
                    self.gr.add_edge((source, target), cost, str(edgeId))            
                else:
                    print("edge source=%d target=%d already added but with larger cost"%(source, target))
                
            if not self.directed or (self.directed and self.hasReverseCost):
                if self.hasReverseCost:
                    if not self.gr.has_edge((target, source)):
                        self.gr.add_edge((target, source), reverseCost, str(edgeId))
                    else:
                        reverseCost1=self.gr.edge_weight((target, source))
                        if reverseCost<reverseCost1:
                            self.gr.del_edge((target, source))
                            self.gr.add_edge((target, source), reverseCost, str(edgeId))
                        else:
                            print("edge target=%d source=%d already added but with larget reverseCost"%(target, source))
                else:
                    if not self.gr.has_edge((target, source)):
                        self.gr.add_edge((target, source), cost, str(edgeId))
                    else:
                        cost1=self.gr.edge_weight((target, source))
                        if cost<cost1:
                            self.gr.del_edge((target, source))
                            self.gr.add_edge((target, source), cost, str(edgeId))            
                        else:
                            print("edge target=%d source=%d already added but with larger cost"%(target, source))

                        print("edge target=%d source=%d already added"%(target, source))
        
        
    def computeShortestPath(self, startNode, targetNode):                       
        pathEdgeList, pathLen=self.dijkstra(startNode, targetNode)
        if pathLen!=None and pathEdgeList!=None:
            print("%s %d"%(str(pathEdgeList), pathLen))
            
        return pathEdgeList, pathLen
