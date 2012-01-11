'''
Created on Dec 28, 2011

@author: maxl
'''

from igraph import *
import time
import os

#class Edge():
#    def __init__(self):
#        self.source=0
#        self.target=0
#        self.id=0
#        self.cost=0
#        self.reverseCost=0
#        
#    def __repr__(self):
#        return "%d %d %d %d %d"%(self.id, self.source, self.target, self.cost, self.reverseCost)
#    
#    def fillEdge(self, id, source, target, cost, reverseCost):
#        self.source=source
#        self.target=target
#        self.id=id
#        self.cost=cost
#        self.reverseCost=reverseCost
        
class DijkstraWrapperIgraph():
    def __init__(self, cursor, dataDir):
        self.cursor=cursor
        self.graph=None
        self.directed=True
        self.hasReverseCost=True
        self.graphLoaded=False
        self.dataDir=dataDir
        
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
#        edgeList=list()
        nodeList=set()
        weightList=list()
        idList=list()
        edgeListForIgraph=list()
        
        self.cursor.execute("SELECT id, length, oneway, source, target, maxspeed, cost, reverseCost from edgeTable")
        allentries=self.cursor.fetchall()
        for x in allentries:
            edgeId, length, oneway, source, target, maxspeed, cost, reverseCost=self.edgeFromDB(x)
            
            # TODO length calculation
#            edge=Edge()
#            cost=length            
#            edge.fillEdge(edgeId, source, target, cost, reverseCost)
#            edgeList.append(edge)
            
            nodeList.add(str(source))
            nodeList.add(str(target))

            edgeListForIgraph.append((str(source), str(target)))
            edgeListForIgraph.append((str(target), str(source)))
            
            weightList.append(cost)
            weightList.append(reverseCost)

            idList.append(edgeId)
            idList.append(edgeId)

        return nodeList, weightList, idList, edgeListForIgraph   

    def dijkstra(self, startNode, targetNode):   
        print("dijkstra:igraph from %d to %d"%(startNode, targetNode))    
        pathEdgeList=list()
        start=time.time()
        result=self.graph.get_shortest_paths(str(startNode), to=str(targetNode), weights="weight", output="epath")  
        if len(result)==0:
            print("no path found")
            return None, None
        
        cost=0
        for edgeId in result[0]:
            edge=self.graph.es[edgeId]
            pathEdgeList.append(int(edge["id"]))
            cost=cost+int(edge["weight"])
        curr=time.time()
        dur=int(curr-start)
        print("dijkstra:igraph: "+str(dur)+"s")
                                            
        return pathEdgeList, cost
        
    def initGraph(self):
        start=time.time()

        if os.path.exists(self.getGraphFile()):
            self.graph=Graph.Read_Picklez(self.getGraphFile())
            
        else:
            nodeSet, weightList, idList, edgeListForIgraph=self.fillEdges()
            
            self.graph = Graph(directed=self.directed)
            
            nodeList=list()
            nodeList.extend(nodeSet)
            self.graph.add_vertices(nodeList)
            self.graph.add_edges(edgeListForIgraph)
            self.graph.es["weight"] = weightList
            self.graph.es["id"]=idList
            
#            for edge in edgeList:
#                edgeId=edge.id
#                source=str(edge.source)
#                target=str(edge.target)
#                cost=edge.cost
#                reverseCost=edge.reverseCost            
#                
##                self.graph.add_vertex(str(source))
##                self.graph.add_vertex(str(target))
#                
#                attr=dict()
#                attr["id"]=edgeId
#                attr["weight"]=cost
##                eid = self.graph.ecount()   
#                self.graph.add_edge(source, target, **attr)  
##                print(self.graph.es[eid]["weight"])
#                
#                attr=dict()
#                attr["id"]=edgeId
#                attr["weight"]=reverseCost
#                self.graph.add_edge(target, source, **attr)            
    
#            self.graph.es["weight"] = weightList
#            self.graph.es["id"]=idList
            self.graph.write_picklez(self.getGraphFile())
            
        self.graphLoaded=True
        
        curr=time.time()
        dur=int(curr-start)
        print("initGraph:igraph: "+str(dur)+"s")

    def getGraphFile(self):
        return os.path.join(self.getDataDir(), "igraph.file")
    
    def getDataDir(self):
        return self.dataDir
        
    def computeShortestPath(self, startNode, targetNode):                       
        pathEdgeList, pathCost=self.dijkstra(startNode, targetNode)
#        if pathCost!=None and pathEdgeList!=None:
#            print("%s %d"%(str(pathEdgeList), pathCost))
        return pathEdgeList, pathCost
