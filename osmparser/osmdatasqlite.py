'''
Created on Apr 30, 2012

@author: maxl
'''

import sqlite3
import pickle
import os
from utils.env import getDataRoot
from utils.gisutils import GISUtils

class OSMDataSQLite():
    def __init__(self):
        self.connectionEdge=None
        self.cursorEdge=None
        self.connectionArea=None
        self.cursorArea=None
        self.connectionAdress=None
        self.cursorAdress=None
        self.cursorWay=None
        self.connectionWay=None
        self.cursorNode=None
        self.connectionNode=None
        self.gisUtils=GISUtils()

    def getGISUtils(self):
        return self.gisUtils
    
    def setPragmaForDB(self, cursor):
#        cursor.execute('PRAGMA journal_mode=OFF')
#        cursor.execute('PRAGMA synchronous=OFF')
        cursor.execute('PRAGMA cache_size=40000')
        cursor.execute('PRAGMA page_size=4096')
#        cursor.execute('PRAGMA ignore_check_constraint=ON')
        
    def openEdgeDB(self):
        self.connectionEdge=sqlite3.connect(self.getEdgeDBFile())
        self.cursorEdge=self.connectionEdge.cursor()
        self.connectionEdge.enable_load_extension(True)
        self.cursorEdge.execute("SELECT load_extension('libspatialite.so')")
        self.setPragmaForDB(self.cursorEdge)

    def openAreaDB(self):
        self.connectionArea=sqlite3.connect(self.getAreaDBFile())
        self.cursorArea=self.connectionArea.cursor()
        self.connectionArea.enable_load_extension(True)
        self.cursorArea.execute("SELECT load_extension('libspatialite.so')")
        self.setPragmaForDB(self.cursorArea)

    def openWayDB(self):
        self.connectionWay=sqlite3.connect(self.getWayDBFile())
        self.cursorWay=self.connectionWay.cursor()
        self.connectionWay.enable_load_extension(True)
        self.cursorWay.execute("SELECT load_extension('libspatialite.so')")
        self.setPragmaForDB(self.cursorWay)

    def openNodeDB(self):
        self.connectionNode=sqlite3.connect(self.getNodeDBFile())
        self.cursorNode=self.connectionNode.cursor()
        self.connectionNode.enable_load_extension(True)
        self.cursorNode.execute("SELECT load_extension('libspatialite.so')")
        self.setPragmaForDB(self.cursorNode)
        
    def openAdressDB(self):
        self.connectionAdress=sqlite3.connect(self.getAdressDBFile())
        self.cursorAdress=self.connectionAdress.cursor()
        self.setPragmaForDB(self.cursorAdress)
    
    def closeEdgeDB(self):
        if self.connectionEdge!=None:
            self.connectionEdge.commit()        
            self.cursorEdge.close()
            self.connectionEdge=None     
            self.cursorEdge=None

    def closeAreaDB(self):
        if self.connectionArea!=None:
            self.connectionArea.commit()        
            self.cursorArea.close()
            self.connectionArea=None     
            self.cursorArea=None
           
    def closeWayDB(self):
        if self.connectionWay!=None:
            self.connectionWay.commit()        
            self.cursorWay.close()
            self.connectionWay=None     
            self.cursorWay=None

    def closeNodeDB(self):
        if self.connectionNode!=None:
            self.connectionNode.commit()        
            self.cursorNode.close()
            self.connectionNode=None     
            self.cursorNode=None

    def closeAdressDB(self):
        if self.connectionAdress!=None:
            self.connectionAdress.commit()
            self.cursorAdress.close()
            self.connectionAdress=None
            self.cursorAdress=None
                 
    def openAllDB(self):
        self.openWayDB()
        self.openNodeDB()
        self.openEdgeDB()
        self.openAreaDB()
        self.openAdressDB()
        
    def closeAllDB(self):
        self.closeWayDB()
        self.closeNodeDB()
        self.closeEdgeDB()
        self.closeAreaDB()
        self.closeAdressDB()
        
    def wayFromDB(self, x):
        wayId=x[0]
        refs=pickle.loads(x[2])
        tags=self.decodeWayTags(x[1])
        streetInfo=x[3]
        name=x[4]
        nameRef=x[5]
        maxspeed=x[6]
        poiList=None
        if x[7]!=None:
            poiList=pickle.loads(x[7])

        return (wayId, tags, refs, streetInfo, name, nameRef, maxspeed, poiList)
 
    def wayFromDBWithCoordsString(self, x):
        wayId=x[0]
        refs=pickle.loads(x[2])
        tags=self.decodeWayTags(x[1])
        streetInfo=x[3]
        name=x[4]
        nameRef=x[5]
        maxspeed=x[6]
        poiList=None
        if x[7]!=None:
            poiList=pickle.loads(x[7])    
        layer=int(x[8])
        coordsStr=x[9]            
        return (wayId, tags, refs, streetInfo, name, nameRef, maxspeed, poiList, layer, coordsStr)   
    
    def poiRefFromDB(self, x):
        refId=int(x[0])
            
        tags=None
        if x[1]!=None:
            tags=pickle.loads(x[1])
        
        nodeType=int(x[2])            
        layer=int(x[3])

        pointStr=x[4]
        lat, lon=self.getGISUtils().createPointFromPointString(pointStr)

        return (refId, lat, lon, tags, nodeType, layer)
    
    def crossingFromDB(self, x):
        crossingEntryId=x[0]
        wayid=x[1]
        refId=x[2]            
        nextWayIdList=pickle.loads(x[3])
        return (crossingEntryId, wayid, refId, nextWayIdList)
    
    def edgeFromDB(self, x):
        edgeId=x[0]
        startRef=x[1]
        endRef=x[2]
        length=x[3]
        wayId=x[4]     
        source=x[5]
        target=x[6]
        cost=x[7]
        reverseCost=x[8]
        return (edgeId, startRef, endRef, length, wayId, source, target, cost, reverseCost)
 
    def edgeFromDBWithCoords(self, x):
        edgeId=x[0]
        startRef=x[1]
        endRef=x[2]
        length=x[3]
        wayId=x[4]     
        source=x[5]
        target=x[6]
        cost=x[7]
        reverseCost=x[8]
        streetInfo=x[9]
        coordsStr=x[10]
        coords=self.getGISUtils().createCoordsFromLineString(coordsStr)
        return (edgeId, startRef, endRef, length, wayId, source, target, cost, reverseCost, streetInfo, coords)

    def areaFromDBWithCoordsString(self, x):
        osmId=x[0]
        areaType=x[1]
        tags=pickle.loads(x[2])  
        layer=int(x[3])
        polyStr=x[4]
        return (osmId, areaType, tags, layer, polyStr)

    def adminAreaFromDBWithCoordsString(self, x):
        osmId=x[0]
        tags=pickle.loads(x[1])
        adminLevel=int(x[2])  
        polyStr=x[3]
        return (osmId, tags, adminLevel, polyStr)
    
    def adminAreaFromDBWithParent(self, x):
        osmId=x[0]
        tags=pickle.loads(x[1])
        if x[2]!=None:
            adminLevel=int(x[2])  
        else:
            adminLevel=None
        if x[3]!=None:
            parent=int(x[3])
        else:
            parent=None
        return (osmId, tags, adminLevel, parent)
     
    def areaFromDB(self, x):
        osmId=x[0]
        areaType=x[1]
        tags=pickle.loads(x[2])  
        return (osmId, areaType, tags)
    
    def decodeStreetInfo(self, streetInfo):
        oneway=(streetInfo&63)>>4
        roundabout=(streetInfo&127)>>6
        streetTypeId=(streetInfo&15)
        return streetTypeId, oneway, roundabout
    
    def decodeStreetInfo2(self, streetInfo):
        oneway=(streetInfo&63)>>4
        roundabout=(streetInfo&127)>>6
        tunnel=(streetInfo&255)>>7
        bridge=(streetInfo&511)>>8
        streetTypeId=(streetInfo&15)
        return streetTypeId, oneway, roundabout, tunnel, bridge

    def addressFromDB(self, x):
        addressId=x[0]
        refId=x[1]
        country=x[2]
        if x[3]!=None:
            city=int(x[3])
        else:
            city=None
        postCode=x[4]
        streetName=x[5]
        houseNumber=x[6]
        lat=x[7]
        lon=x[8]
        return (addressId, refId, country, city, postCode, streetName, houseNumber, lat, lon)

    def restrictionFromDB(self, x):
        restrictionId=x[0]
        target=x[1]
        viaPath=x[2]
        toCost=x[3]
        return (restrictionId, target, viaPath, toCost)
    
    # TODO: should be relativ to this dir by default
    def getDataDir(self):
        return os.path.join(getDataRoot(), "data1")

    def getEdgeDBFile(self):
        file="edge.db"
        return os.path.join(self.getDataDir(), file)

    def getAreaDBFile(self):
        file="area.db"
        return os.path.join(self.getDataDir(), file)
    
    def getAdressDBFile(self):
        file="adress.db"
        return os.path.join(self.getDataDir(), file)
    
    def getWayDBFile(self):
        file="ways.db"
        return os.path.join(self.getDataDir(), file)

    def getNodeDBFile(self):
        file="nodes.db"
        return os.path.join(self.getDataDir(), file)
                        
    def edgeDBExists(self):
        return os.path.exists(self.getEdgeDBFile())

    def areaDBExists(self):
        return os.path.exists(self.getAreaDBFile())

    def wayDBExists(self):
        return os.path.exists(self.getWayDBFile())

    def nodeDBExists(self):
        return os.path.exists(self.getNodeDBFile())
                
    def adressDBExists(self):
        return os.path.exists(self.getAdressDBFile())
    
    def getOSMDataInfo(self):
        osmDataList=dict()
        osmData=dict()
#        osmData["osmFile"]='/home/maxl/Downloads/geofabrik/austria.osm.bz2'
        osmData["osmFile"]='/home/maxl/Downloads/cloudmade/salzburg-2.osm.bz2'
        osmData["poly"]="austria.poly"
        osmData["polyCountry"]="Europe / Western Europe / Austria"
        osmDataList[0]=osmData
        
#        osmData=dict()
#        osmData["osmFile"]='/home/maxl/Downloads/geofabrik/switzerland.osm.bz2'
##        osmData["osmFile"]=None
#        osmData["poly"]="switzerland.poly"
#        osmData["polyCountry"]="Europe / Western Europe / Switzerland"
#        osmDataList[1]=osmData
    
        osmData=dict()
#        osmData["osmFile"]='/home/maxl/Downloads/geofabrik/bayern.osm.bz2'
#        osmData["osmFile"]='/home/maxl/Downloads/geofabrik/germany-1.osm.bz2'
        osmData["osmFile"]='/home/maxl/Downloads/cloudmade/bayern-2.osm.bz2'
#        osmData["osmFile"]=None
        osmData["poly"]="germany.poly"
        osmData["polyCountry"]="Europe / Western Europe / Germany"
        osmDataList[2]=osmData
        
#        osmData=dict()
#        osmData["osmFile"]='/home/maxl/Downloads/geofabrik/liechtenstein.osm.bz2'
##        osmData["osmFile"]=None
#        osmData["poly"]="liechtenstein.poly"
#        osmData["polyCountry"]="Europe / Western Europe / Liechtenstein"
#        osmDataList[3]=osmData

        return osmDataList
    
    def getWayEntryForId(self, wayId):
        self.cursorWay.execute('SELECT * FROM wayTable where wayId=%d'%(wayId))
        allentries=self.cursorWay.fetchall()
        if len(allentries)==1:
            return self.wayFromDB(allentries[0])
        
        return (None, None, None, None, None, None, None, None)

    def getLenOfEdgeTable(self):
        self.cursorEdge.execute('SELECT COUNT(id) FROM edgeTable')
        allentries=self.cursorEdge.fetchall()
        return allentries[0][0]
    
    def getEdgeEntryForEdgeId(self, edgeId):
        self.cursorEdge.execute('SELECT * FROM edgeTable where id=%d'%(edgeId))
        allentries=self.cursorEdge.fetchall()
        if len(allentries)==1:
            edge=self.edgeFromDB(allentries[0])
            return edge
        self.log("no edge with %d"%(edgeId))
        return (None, None, None, None, None, None, None, None, None)
    
    def isValidOnewayEnter(self, oneway, ref, startRef, endRef):
        # in the middle of a oneway
        if ref!=startRef and ref!=endRef:
            return True
        
        if oneway==1:
            if ref==startRef:
                return True
        elif oneway==2:
            if ref==endRef:
                return True
        return False

    def decodeWayTags(self, plainTags):
        if plainTags==None:
            return dict()
#        plainTags=zlib.decompress(compressedTags)
        tags=pickle.loads(plainTags)
        return tags

    def getAllAdminAreas(self, adminLevelList, sortByAdminLevel):
        filterString=self.createSQLFilterStringForIN(adminLevelList)

        if sortByAdminLevel==True:
            sql='SELECT osmId, tags, adminLevel, AsText(geom) FROM adminAreaTable WHERE adminLevel IN %s ORDER BY adminLevel'%(filterString)
        else:
            sql='SELECT osmId, tags, adminLevel, AsText(geom) FROM adminAreaTable WHERE adminLevel IN %s'%(filterString)

        self.cursorArea.execute(sql)
             
        allentries=self.cursorArea.fetchall()
        resultList=list()
        for x in allentries:
            resultList.append(self.adminAreaFromDBWithCoordsString(x))
            
        return resultList     
    
    def createSQLFilterStringForIN(self, typeIdList):
        filterString='('
        for typeId in typeIdList:
            filterString=filterString+str(typeId)+','
            
        filterString=filterString[:-1]
        filterString=filterString+')'
        return filterString
