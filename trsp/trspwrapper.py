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
    
    def getQueryBBox(self, bbox):
        ymin=bbox[1]-0.1
        xmin=bbox[0]-0.1
        ymax=bbox[3]+0.1
        xmax=bbox[2]+0.1
        return [xmin, ymin, xmax, ymax]
    
    def getSQLQueryEdge(self):
        xmin, ymin, xmax, ymax=self.lastBBox
        
        return 'SELECT id, source, target, cost, reverseCost FROM edgeTable WHERE MbrWithin("geom", BuildMbr(%f, %f, %f, %f, 4326))==1'%(xmin, ymin, xmax, ymax)

#        return "SELECT id, source, target, cost, reverseCost FROM edgeTable ORDER BY id"

    def getSQLQueryRestriction(self):
        return "SELECT target, toCost, viaPath FROM restrictionTable"
    
    def isBBoxInsideLastBBox(self, bbox):
        if self.lastBBox[0]<=bbox[0] and self.lastBBox[1]<=bbox[1] and self.lastBBox[2]>=bbox[2] and self.lastBBox[3]>=bbox[3]:
            return True
        return False
    
    def computeShortestPath(self, startNode, endNode, bbox):
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
            print("this is a new bbox")
#            print(self.lastBBox)
#            print(bbox)
            
        
#        print(self.getSQLQueryEdge())
        startNodeC=c_int(startNode)
        endNodeC=c_int(endNode)
        path_count=c_int(0)
        file=c_char_p(self.getDB().encode(encoding='utf_8', errors='strict'))
        sqlEdge=c_char_p(self.getSQLQueryEdge().encode(encoding='utf_8', errors='strict'))
        sqlRestriction=c_char_p(self.getSQLQueryRestriction().encode(encoding='utf_8', errors='strict'))
        
        
        class path_element_t(Structure):
            _fields_ = [("vertex_id", c_int),
                     ("edge_id", c_int),
                     ("cost", c_float)]
         
        path=path_element_t()
        pathPointer=pointer(path)
        
        ret=lib_routing.compute_shortest_path(file, sqlEdge, startNodeC, endNodeC, sqlRestriction, byref(pathPointer), byref(path_count))
        lib_routing.clean_edge_table()
        
        if ret>=0:
            num=path_count.value
            if pathPointer[num-1].edge_id==-1:
                num=num-1
            
            for i in range(num):
                edgeList.append(pathPointer[i].edge_id)
                cost=cost+pathPointer[i].cost
            return edgeList, cost
        else:
            print("error during routing")
            return None, None
