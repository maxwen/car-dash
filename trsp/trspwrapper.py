'''
Created on Dec 28, 2011

@author: maxl
'''

import os
from ctypes import *
        
class TrspWrapper():
    def __init__(self, dataDir):
        self.dataDir=dataDir
        
    def isGraphLoaded(self):
        return True
    
    def getDB(self):
        return os.path.join(self.dataDir, "edge.db")
    
    def getSQLQueryEdge(self):
        return "SELECT id, source, target, cost, reverseCost FROM edgeTable ORDER BY id"

    def getSQLQueryRestriction(self):
        return "SELECT target, toCost, viaPath FROM restrictionTable"
    
    def computeShortestPath(self, startNode, endNode):
        lib_routing = cdll.LoadLibrary("_compute_path_trsp.so")

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
        if ret>=0:
            num=path_count.value
            if pathPointer[num-1].edge_id==-1:
                num=num-1
            edgeList=list()
            cost=0
            for i in range(num):
                edgeList.append(pathPointer[i].edge_id)
                cost=cost+pathPointer[i].cost
            return edgeList, cost
        else:
            print("error during routing")
            return None, None
