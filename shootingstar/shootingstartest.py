'''
Created on Dec 13, 2011

@author: maxl
'''
import sys
import sqlite3
from ctypes import *

class ShootingStarTest():
    def __init__(self):
        self.connection=None
        self.cursor=None
        self.gid=1

    def createTable(self):
        self.cursor.execute('CREATE TABLE edgeTable (id INTEGER PRIMARY KEY, source INTEGER, target INTEGER, cost REAL, reverseCost REAL, x1 REAL, y1 REAL, x2 REAL, y2 REAL, toCost REAL, rule TEXT)')

    def openDB(self, file):
        self.connection=sqlite3.connect(file)
        self.cursor=self.connection.cursor()
    
    def closeDB(self):
        self.connection.commit()
        self.cursor.close()
        
    def addToTable(self, source, target, cost, reverseCost, x1, y1, x2, y2, toCost, rule):
        self.cursor.execute('INSERT INTO edgeTable VALUES( ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (self.gid, source, target, cost, reverseCost, x1, y1, x2, y2, toCost, rule))
        self.gid=self.gid+1
    
    def testTable(self):
        self.cursor.execute('SELECT * FROM edgeTable')
        allentries=self.cursor.fetchall()
        for x in allentries:
            print(x)
    
    def calcRoute(self, startEdge, endEdge):
        lib_routing = cdll.LoadLibrary("_compute_path.so")

        startEdgeC=c_int(startEdge)
        endEdgeC=c_int(endEdge)
        path_count=c_int(0)
        file=c_char_p("/tmp/edge.db".encode(encoding='utf_8', errors='strict'))
        sql=c_char_p("SELECT * FROM edgeTable".encode(encoding='utf_8', errors='strict'))
        
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
            
def main(argv):    
    p = ShootingStarTest()
    
#    p.openDB("/tmp/edge.db")
#    p.createTable()
#    
##    for x in range(10):
##        p.addToTable(x, x+1, 0.0 ,1.1 ,2.2 ,3.3 ,4.4 ,5.5, 6.6, "1,2")
#
#    p.addToTable(1 ,      2 , 14.2572101668807 ,             1000 , 76.7176891326003 ,   33.775246780918 , 87.3962905382969 ,  43.2217018705726 , 0     ,None)
#    p.addToTable(2 ,      3 , 11.0893168443772 ,             1000 , 87.3962905382969 ,  43.2217018705726 , 87.3962905382969 ,  54.3110187149498 ,0      ,None)        
#    p.addToTable(3 ,      4 , 13.9884637834871 ,             1000 , 87.3962905382969 ,  54.3110187149498 , 76.7176891326003 ,  63.3467583659239 ,0      ,None)        
#    p.addToTable(4 ,      5 , 14.2572101668807 ,             1000 , 76.7176891326003 ,  63.3467583659239 , 67.2712340429456 ,  52.6681569602273 ,0      ,None)        
#    p.addToTable(5 ,      6 , 10.6864968606796 ,             1000 , 67.2712340429456 ,  52.6681569602273 ,  66.860518604265 ,  41.9895555545307 ,0      ,None)        
#    p.addToTable(6 ,      1 , 12.8311604873812 ,             1000 ,  66.860518604265 ,  41.9895555545307 , 76.7176891326003 ,   33.775246780918 ,0      ,None)        
#    p.addToTable(7 ,      1 , 53.8753258085636 , 53.8753258085636 ,               80 ,               -20 , 76.7176891326003 ,   33.775246780918 ,0      ,None)        
#    p.addToTable(8 ,      4 , 62.5380849791951 , 62.5380849791951 , 73.0212501844746 ,  125.775505045381 , 76.7176891326003 ,  63.3467583659239 ,0      ,None)        
#    p.addToTable(7 ,      9 ,               40 ,               40 ,               80 ,               -20 ,              120 ,               -20 ,0      ,None)        
#    p.addToTable(9 ,     10 , 33.4201752293529 , 33.4201752293529 ,              120 ,               -20 , 141.610728444141 , -45.4928328844451 ,100      ,16)        
#    p.addToTable(9 ,     11 ,               60 ,               60 ,              120 ,               -20 ,              180 ,               -20 ,0      ,None)        
#    p.addToTable(11 ,     12 , 25.9044654619518 , 25.9044654619518 ,              180 ,               -20 , 180.217979680121 , -45.9035483231257 ,0      ,None)        
#    p.addToTable(12 ,     10 , 38.6094358307609 , 38.6094358307609 , 180.217979680121 , -45.9035483231257 , 141.610728444141 , -45.4928328844451 ,0      ,None)        
#    p.addToTable(13 ,     12 , 29.5829181472758 , 29.5829181472758 , 181.039410557482 , -75.4750599081316 , 180.217979680121 , -45.9035483231257 ,100      ,17)        
#    p.addToTable(13 ,     14 , 39.4286821133412 , 39.4286821133412 , 181.039410557482 , -75.4750599081316 , 141.610728444141 , -75.4750599081316 ,0      ,None)        
#    p.addToTable(14 ,     10 , 29.9822270236865 , 29.9822270236865 , 141.610728444141 , -75.4750599081316 , 141.610728444141 , -45.4928328844451 ,0      ,None)        
#    p.addToTable(15 ,     13 , 39.2224758594282 , 39.2224758594282 ,              220 ,               -80 , 181.039410557482 , -75.4750599081316 ,0      ,None)        
#    p.addToTable(15 ,     16 , 38.0005743220152 ,             1000 ,              220 ,               -80 , 251.682466010552 , -79.1714988562574 ,0      ,None)        
#    p.addToTable(16 ,     15 , 38.0539027874633 ,             1000 , 251.682466010552 , -79.1714988562574 ,              220 ,               -80 ,0      ,None)        
#    p.addToTable(17 ,     16 , 48.3246366252935 , 48.3246366252935 ,              300 ,               -80 , 251.682466010552 , -79.1714988562574 ,0      ,None)        
#    p.addToTable(11 ,     18 ,  115.27849852631 ,  115.27849852631 ,              180 ,               -20 , 295.218302510699 , -23.7249146343713 ,0      ,None)        
#    p.addToTable(18 ,     17 , 56.4778705670458 , 56.4778705670458 , 295.218302510699 , -23.7249146343713 ,              300 ,               -80 ,0      ,None)
#        
#    p.testTable()
#    p.closeDB()
    
    print(p.calcRoute(20,8))
    print(p.calcRoute(8,20))

if __name__ == "__main__":
    main(sys.argv)  
    

