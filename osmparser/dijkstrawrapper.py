'''
Created on Dec 28, 2011

@author: maxl
'''

import math
from pygraph.classes.digraph import digraph
from pygraph.algorithms.minmax import shortest_path, shortest_path_bellman_ford
from pygraph.algorithms.generators import generate
from pygraph.mixins import labeling
import time

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
        self.graphLoaded=False

    def isGraphLoaded(self):
        return self.graphLoaded
    
    def edgeFromDB(self, x):
        edgeId=x[0]
        length=x[1]
        oneway=x[2]
        source=x[3]
        target=x[4]
        maxspeed=x[5]
        return (edgeId, length, oneway, source, target, maxspeed)

    def fillEdges(self):
        edgeList=list()
        self.cursor.execute("SELECT id, length, oneway, source, target, maxspeed from edgeTable")
        allentries=self.cursor.fetchall()
        for x in allentries:
            edgeId, length, oneway, source, target, maxspeed=self.edgeFromDB(x)
                  
            # TODO length calculation
            edge=Edge()
#            cost=length
            cost=(length / (maxspeed/3.6))*100
            
            if oneway:
                reverseCost=cost*100000
            else:
                reverseCost=cost
                
            edge.fillEdge(edgeId, source, target, cost, reverseCost)
            edgeList.append(edge)
        self.graphLoaded=True
        return edgeList    

    def route(self, gr, st, startNode, targetNode):
        lastnode = targetNode
        path = []
        while lastnode != startNode:
            nextnode = st[lastnode]
            assert nextnode in gr.neighbors(lastnode)
            path.append((lastnode, st[lastnode]))
            lastnode = nextnode
#        path.append((startNode, st[startNode]))
        path.reverse()
        print(path)
        return path
    
    def dijkstra(self, startNode, targetNode):       
        start=time.time()
        if not self.gr.has_node(startNode):
            print("start node not found %d"%(startNode))
            return None, None
        
        if not self.gr.has_node(targetNode):
            print("target node not found %d"%(targetNode))
            return None, None
        curr=time.time()
        dur=int(curr-start)
        print(str(dur)+"s")

        pathEdgeList=list()
        pathCost=0.0
        start=time.time()
        st, dist = shortest_path(self.gr, startNode)     
        curr=time.time()
        dur=int(curr-start)
        print(str(dur)+"s")
               
        start=time.time()
        path=self.route(self.gr, st, startNode, targetNode)        
        curr=time.time()
        dur=int(curr-start)
        print(str(dur)+"s")
      
        start=time.time()
        for source, target in path:
            pathEdgeList.append(int(self.gr.edge_label((source, target))))

        curr=time.time()
        dur=int(curr-start)
        print(str(dur)+"s")
                
        if targetNode in dist:
            pathCost=float(dist[targetNode])
            
        return pathEdgeList, pathCost
        
    def initGraph(self):
        self.allEdgesList=self.fillEdges()
        
        self.gr=digraph()
        for edge in self.allEdgesList:
            edgeId=edge.id
            source=edge.source
            target=edge.target
            cost=edge.cost
            reverseCost=edge.reverseCost
            
#            if source==626 and target==2862:
#                None
#            
#            if source==2862 and target==626:
#                None
                
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
        pathEdgeList, pathCost=self.dijkstra(startNode, targetNode)
#        if pathCost!=None and pathEdgeList!=None:
#            print("%s %d"%(str(pathEdgeList), pathCost))
            
        return pathEdgeList, pathCost
