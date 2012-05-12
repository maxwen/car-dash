'''
Created on Dec 28, 2011

@author: maxl
'''

import os
from ctypes import *
from Polygon import Polygon

class TrspWrapper():
    def __init__(self, dataDir):
        self.dataDir=dataDir
        self.lastBBoxCPolygon=None
        self.lastBBox=None
        
    def isGraphLoaded(self):
        return True
    
    def getDB(self):
        return os.path.join(self.dataDir, "edge.db")
    
    def getRoutingBBoxMargin(self):
        return 0.5
    
    def calcQueryBBox(self, bbox):
        ymin=bbox[1]-self.getRoutingBBoxMargin()
        xmin=bbox[0]-self.getRoutingBBoxMargin()
        ymax=bbox[3]+self.getRoutingBBoxMargin()
        xmax=bbox[2]+self.getRoutingBBoxMargin()
        bboxNew=[xmin, ymin, xmax, ymax]
        self.lastBBoxCPolygon=Polygon([(bboxNew[0], bboxNew[3]), (bboxNew[2], bboxNew[3]), (bboxNew[2], bboxNew[1]), (bboxNew[0], bboxNew[1])])    
        self.lastBBox=bboxNew
    
    def getCurrentRoutingBBox(self):
        return self.lastBBox
        
    def getSQLQueryEdgeShortest(self):
        if self.lastBBox!=None:
            xmin, ymin, xmax, ymax=self.lastBBox        
            return 'SELECT id, source, target, length AS cost, CASE WHEN reverseCost IS cost THEN length ELSE reverseCost END FROM edgeTable WHERE MbrWithin("geom", BuildMbr(%f, %f, %f, %f, 4326))==1'%(xmin, ymin, xmax, ymax)
        else:
            return 'SELECT id, source, target, length AS cost, CASE WHEN reverseCost IS cost THEN length ELSE reverseCost END FROM edgeTable'
            
    def getSQLQueryEdge(self):
        if self.lastBBox!=None:
            xmin, ymin, xmax, ymax=self.lastBBox
            return 'SELECT id, source, target, cost, reverseCost FROM edgeTable WHERE ROWID IN (SELECT rowid FROM idx_edgeTable_geom WHERE rowid MATCH RTreeWithin(%f, %f, %f, %f))'%(xmin, ymin, xmax, ymax)
        else:
            return 'SELECT id, source, target, cost, reverseCost FROM edgeTable'
            
    def getSQLQueryRestriction(self):
        return "SELECT target, toCost, viaPath FROM restrictionTable"
    
    def isBBoxInsideLastBBox(self, bbox):
        bboxCPolyon=Polygon([(bbox[0], bbox[3]), (bbox[2], bbox[3]), (bbox[2], bbox[1]), (bbox[0], bbox[1])])    
        return self.lastBBoxCPolygon.covers(bboxCPolyon)
        
    def computeShortestPath(self, startEdge, endEdge, startPos, endPos, bbox, shortest):
        lib_routing = cdll.LoadLibrary("librouting_trsp.so")
                
        edgeList=list()
        cost=0
        
#        print(startEdge)
#        print(endEdge)
#        print(startPos)
#        print(endPos)
        
#        newBBox=True
#        if bbox!=None:
#            if self.lastBBoxCPolygon!=None:
#                if self.isBBoxInsideLastBBox(bbox):
#                    newBBox=False
#            
#            if self.lastBBoxCPolygon==None or newBBox==True:
#                self.calcQueryBBox(bbox)
#                lib_routing.clean_edges()
#        else:
#            self.lastBBoxCPolygon=None
#            lib_routing.clean_edges()
#            
#        lib_routing.clean_edges()
#        self.calcQueryBBox(bbox)
#        print(self.lastBBox)
        self.lastBBox=None

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
        
        ret=lib_routing.compute_trsp(file, sqlEdge, sqlRestriction, doVertexC, startEdgeC, startPosC, endEdgeC, endPosC, byref(pathPointer), byref(path_count))
        
        if ret==0:
            num=path_count.value
            if pathPointer[num-1].edge_id==-1:
                num=num-1
            
            for i in range(num):
                edgeList.append(pathPointer[i].edge_id)
                cost=cost+pathPointer[i].cost
                
#            print(edgeList)
#            print(len(edgeList))
#            print(cost)
            return edgeList, cost
        else:
            print("error during routing")
            return None, None
