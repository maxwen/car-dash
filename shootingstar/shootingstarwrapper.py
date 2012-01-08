'''
Created on Dec 28, 2011

@author: maxl
'''

import os
from ctypes import *
        
class ShootingStarWrapper():
    def __init__(self, dataDir):
        self.dataDir=dataDir
        
    def isGraphLoaded(self):
        return True
    
    def getDB(self):
        return os.path.join(self.dataDir, "edge.db")
    
    def getSQLQuery(self):
        return "SELECT id, source, target, cost, reverseCost, x1, y1, x2, y2, toCost, rule FROM edgeTableShootingStar"
    
    def computeShortestPath(self, startEdge, endEdge):
        lib_routing = cdll.LoadLibrary("_compute_path.so")

        startEdgeC=c_int(startEdge)
        endEdgeC=c_int(endEdge)
        path_count=c_int(0)
        file=c_char_p(self.getDB().encode(encoding='utf_8', errors='strict'))
        sql=c_char_p(self.getSQLQuery().encode(encoding='utf_8', errors='strict'))
        
        class path_element_t(Structure):
            _fields_ = [("vertex_id", c_int),
                     ("edge_id", c_int),
                     ("cost", c_float)]
         
        path=path_element_t()
        pathPointer=pointer(path)
        
        ret=lib_routing.compute_shortest_path(file, sql, startEdgeC, endEdgeC, byref(pathPointer), byref(path_count))
        if ret >=0:
            num=path_count.value
            edgeList=list()
            for i in range(num):
                edgeList.append(pathPointer[i].edge_id)
            return edgeList
        else:
            print("error during routing")
            return None
