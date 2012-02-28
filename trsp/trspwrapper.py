'''
Created on Dec 28, 2011

@author: maxl
'''

import os
from ctypes import *
        
class TrspWrapper():
    def __init__(self, dataDir):
        self.dataDir=dataDir
        self.lastBBox=None
        
    def isGraphLoaded(self):
        return True
    
    def getDB(self):
        return os.path.join(self.dataDir, "edge.db")
    
    def getQueryBBox(self, bbox, margin=0.1):
        ymin=bbox[1]-margin
        xmin=bbox[0]-margin
        ymax=bbox[3]+margin
        xmax=bbox[2]+margin
        return [xmin, ymin, xmax, ymax]
    
    def getSQLQueryEdgeShortest(self):
        xmin, ymin, xmax, ymax=self.lastBBox        
        return 'SELECT id, source, target, length AS cost, CASE WHEN reverseCost IS cost THEN length ELSE reverseCost END FROM edgeTable WHERE MbrWithin("geom", BuildMbr(%f, %f, %f, %f, 4326))==1'%(xmin, ymin, xmax, ymax)
    
    def getSQLQueryEdge(self):
        xmin, ymin, xmax, ymax=self.lastBBox        
        return 'SELECT id, source, target, cost, reverseCost FROM edgeTable WHERE MbrWithin("geom", BuildMbr(%f, %f, %f, %f, 4326))==1'%(xmin, ymin, xmax, ymax)

    def getSQLQueryRestriction(self):
        return "SELECT target, toCost, viaPath FROM restrictionTable"
    
    def isBBoxInsideLastBBox(self, bbox):
        if self.lastBBox[0]<=bbox[0] and self.lastBBox[1]<=bbox[1] and self.lastBBox[2]>=bbox[2] and self.lastBBox[3]>=bbox[3]:
            return True
        return False
    
    def computeShortestPath(self, startNode, endNode, bbox, shortest):
        lib_routing = cdll.LoadLibrary("_compute_path_trsp.so")
                
        edgeList=list()
        cost=0
        
#        print(self.lastBBox)
#        print(bbox)
        
        newBBox=True
        if self.lastBBox!=None:
            if self.isBBoxInsideLastBBox(bbox):
                newBBox=False
        
        
        if self.lastBBox==None or newBBox==True:
            self.lastBBox=self.getQueryBBox(bbox)
#            print("this is a new bbox")
            lib_routing.clean_edge_table()
#            print(self.lastBBox)
#            print(bbox)
            
        
#        print(self.getSQLQueryEdge())
        doVertexC=c_int(1)
        startNodeC=c_int(startNode)
        startPosC=c_float(0.0)
        endNodeC=c_int(endNode)
        endPosC=c_float(0.0)
        path_count=c_int(0)
        file=c_char_p(self.getDB().encode(encoding='utf_8', errors='strict'))
        if shortest==True:
            sqlEdge=c_char_p(self.getSQLQueryEdgeShortest().encode(encoding='utf_8', errors='strict'))
        else:
            sqlEdge=c_char_p(self.getSQLQueryEdge().encode(encoding='utf_8', errors='strict'))
        sqlRestriction=c_char_p(self.getSQLQueryRestriction().encode(encoding='utf_8', errors='strict'))
        
        
        class path_element_t(Structure):
            _fields_ = [("vertex_id", c_int),
                     ("edge_id", c_int),
                     ("cost", c_float)]
         
        path=path_element_t()
        pathPointer=pointer(path)
        
        ret=lib_routing.compute_shortest_path(file, sqlEdge, sqlRestriction, doVertexC, startNodeC, startPosC, endNodeC, endPosC, byref(pathPointer), byref(path_count))
        
        
        if ret>=0:
            num=path_count.value
            if pathPointer[num-1].edge_id==-1:
                num=num-1
            
            for i in range(num):
                edgeList.append(pathPointer[i].edge_id)
                cost=cost+pathPointer[i].cost
                
            print(edgeList)
            print(cost)
            return edgeList, cost
        else:
            print("error during routing")
            return None, None
        
    def computeShortestPathForEdges(self, startEdge, endEdge, startPos, endPos, bbox, shortest):
        lib_routing = cdll.LoadLibrary("_compute_path_trsp.so")
                
        edgeList=list()
        cost=0
        
#        print(self.lastBBox)
#        print(bbox)
        
        newBBox=True
        if self.lastBBox!=None:
            if self.isBBoxInsideLastBBox(bbox):
                newBBox=False
        
        if self.lastBBox==None or newBBox==True:
            self.lastBBox=self.getQueryBBox(bbox)
#            print("this is a new bbox")
            lib_routing.clean_edge_table()
#            print(self.lastBBox)
#            print(bbox)
            
        
#        print(self.getSQLQueryEdge())
        doVertexC=c_int(0)
        startEdgeC=c_int(startEdge)
        startPosC=c_float(startPos)
        endEdgeC=c_int(endEdge)
        endPosC=c_float(endPos)
        path_count=c_int(0)
        file=c_char_p(self.getDB().encode(encoding='utf_8', errors='strict'))
        if shortest==True:
            sqlEdge=c_char_p(self.getSQLQueryEdgeShortest().encode(encoding='utf_8', errors='strict'))
        else:
            sqlEdge=c_char_p(self.getSQLQueryEdge().encode(encoding='utf_8', errors='strict'))
        sqlRestriction=c_char_p(self.getSQLQueryRestriction().encode(encoding='utf_8', errors='strict'))
        
        
        class path_element_t(Structure):
            _fields_ = [("vertex_id", c_int),
                     ("edge_id", c_int),
                     ("cost", c_float)]
         
        path=path_element_t()
        pathPointer=pointer(path)
        
        ret=lib_routing.compute_shortest_path(file, sqlEdge, sqlRestriction, doVertexC, startEdgeC, startPosC, endEdgeC, endPosC, byref(pathPointer), byref(path_count))
        
        
        if ret>=0:
            num=path_count.value
            if pathPointer[num-1].edge_id==-1:
                num=num-1
            
            for i in range(num):
                edgeList.append(pathPointer[i].edge_id)
                cost=cost+pathPointer[i].cost
                
            print(edgeList)
            print(cost)
            return edgeList, cost
        else:
            print("error during routing")
            return None, None
