'''
Created on Mar 31, 2012

@author: maxl
'''

import env
import os
import math

from PyQt4.QtCore import Qt
from PyQt4.QtGui import QFont, QPixmap, QColor, QPen, QBrush
from osmparser.osmparserdata import Constants

class OSMStyle():
    POI_INFO_DICT={Constants.POI_TYPE_BARRIER:{"pixmap":"barrierPixmap", "desc":"Barrier", "zoom":15},
                   Constants.POI_TYPE_ENFORCEMENT:{"pixmap":"speedCameraImage", "desc":"Speed Camera", "zoom":15},
                   Constants.POI_TYPE_GAS_STATION:{"pixmap":"gasStationPixmap", "desc":"Gas Station", "zoom":15},
                   Constants.POI_TYPE_PARKING:{"pixmap":"parkingPixmap", "desc":"Parking", "zoom":15},
                   Constants.POI_TYPE_HOSPITAL:{"pixmap":"hospitalPixmap", "desc":"Hospital", "zoom":15},
                   Constants.POI_TYPE_PLACE:{"pixmap":None, "desc":"Place", "zoom":13},
                   Constants.POI_TYPE_MOTORWAY_JUNCTION:{"pixmap":"highwayExitImage", "desc":"Highway Exit", "zoom":15},
                   Constants.POI_TYPE_POLICE:{"pixmap":"policePixmap", "desc":"Police", "zoom":15},
                   Constants.POI_TYPE_SUPERMARKET:{"pixmap":"supermarketPixmap", "desc":"Supermarket", "zoom":15},
                   Constants.POI_TYPE_AIRPORT:{"pixmap":"airportPixmap", "desc":"Airport", "zoom":15},
                   Constants.POI_TYPE_RAILWAYSTATION:{"pixmap":"railwaystationtPixmap", "desc":"Railway Station", "zoom":15}}
    
    AREA_INFO_DICT={Constants.AREA_TYPE_AEROWAY:{"desc":"Aeroways", "zoom":None},
                    Constants.AREA_TYPE_BUILDING:{"desc":"Buildings", "zoom":16},
                    Constants.AREA_TYPE_HIGHWAY_AREA:{"desc":"Highway Areas", "zoom":None},
                    Constants.AREA_TYPE_LANDUSE:{"desc":"Landuse", "zoom":None},
                    Constants.AREA_TYPE_NATURAL:{"desc":"Natural", "zoom":None},
                    Constants.AREA_TYPE_RAILWAY:{"desc":"Railways", "zoom":None}}  
          
    def __init__(self):
        self.styleDict=dict()
        self.colorDict=dict()
        self.pixmapDict=dict()
        self.penDict=dict()
        self.brushDict=dict()
        self.fontDict=dict()
        
        self.errorImage=QPixmap(os.path.join(env.getImageRoot(), "error.png"))
        self.errorColor=QColor(255, 0, 0)
        
        self.pixmapDict["gpsPointImage"]=QPixmap(os.path.join(env.getImageRoot(), "gps-move.png"))
        self.pixmapDict["gpsPointImageStop"]=QPixmap(os.path.join(env.getImageRoot(), "gps-stop.png"))
      
        self.pixmapDict["turnRightImage"]=QPixmap(os.path.join(env.getImageRoot(), "directions/right.png"))
        self.pixmapDict["turnLeftImage"]=QPixmap(os.path.join(env.getImageRoot(), "directions/left.png"))
        self.pixmapDict["turnRighHardImage"]=QPixmap(os.path.join(env.getImageRoot(), "directions/sharply_right.png"))
        self.pixmapDict["turnLeftHardImage"]=QPixmap(os.path.join(env.getImageRoot(), "directions/sharply_left.png"))
        self.pixmapDict["turnRightEasyImage"]=QPixmap(os.path.join(env.getImageRoot(), "directions/slightly_right.png"))
        self.pixmapDict["turnLeftEasyImage"]=QPixmap(os.path.join(env.getImageRoot(), "directions/slightly_left.png"))
        self.pixmapDict["straightImage"]=QPixmap(os.path.join(env.getImageRoot(), "directions/forward.png"))
        self.pixmapDict["uturnImage"]=QPixmap(os.path.join(env.getImageRoot(), "directions/u-turn.png"))
        self.pixmapDict["roundaboutImage"]=QPixmap(os.path.join(env.getImageRoot(), "directions/roundabout.png"))
        self.pixmapDict["roundabout1Image"]=QPixmap(os.path.join(env.getImageRoot(), "directions/roundabout_exit1.png"))
        self.pixmapDict["roundabout2Image"]=QPixmap(os.path.join(env.getImageRoot(), "directions/roundabout_exit2.png"))
        self.pixmapDict["roundabout3Image"]=QPixmap(os.path.join(env.getImageRoot(), "directions/roundabout_exit3.png"))
        self.pixmapDict["roundabout4Image"]=QPixmap(os.path.join(env.getImageRoot(), "directions/roundabout_exit4.png"))
        
        self.pixmapDict["tunnelPixmap"]=QPixmap(os.path.join(env.getImageRoot(), "tunnel.png"))
        self.pixmapDict["downloadPixmap"]=QPixmap(os.path.join(env.getImageRoot(), "download.png"))
        self.pixmapDict["followGPSPixmap"]=QPixmap(os.path.join(env.getImageRoot(), "gps.png"))
        self.pixmapDict["favoritesPixmap"]=QPixmap(os.path.join(env.getImageRoot(), "favorites.png"))
        self.pixmapDict["addressesPixmap"]=QPixmap(os.path.join(env.getImageRoot(), "addresses.png"))
        self.pixmapDict["routePixmap"]=QPixmap(os.path.join(env.getImageRoot(), "route.png"))
        self.pixmapDict["centerGPSPixmap"]=QPixmap(os.path.join(env.getImageRoot(), "map-gps.png"))
        self.pixmapDict["settingsPixmap"]=QPixmap(os.path.join(env.getImageRoot(), "settings.png"))
        self.pixmapDict["gpsDataPixmap"]=QPixmap(os.path.join(env.getImageRoot(), "gps.png"))
        self.pixmapDict["mapPointPixmap"]=QPixmap(os.path.join(env.getImageRoot(), "flagMap.png"))
        
        self.pixmapDict["startPixmap"]=QPixmap(os.path.join(env.getImageRoot(), "routing/start.png"))
        self.pixmapDict["finishPixmap"]=QPixmap(os.path.join(env.getImageRoot(), "routing/finish.png"))
        self.pixmapDict["wayPixmap"]=QPixmap(os.path.join(env.getImageRoot(), "routing/way.png"))
        
        self.pixmapDict["hospitalPixmap"]=QPixmap(os.path.join(env.getImageRoot(), "poi/hospital.png"))
        self.pixmapDict["policePixmap"]=QPixmap(os.path.join(env.getImageRoot(), "poi/police.png"))
        self.pixmapDict["supermarketPixmap"]=QPixmap(os.path.join(env.getImageRoot(), "poi/supermarket.png"))
        self.pixmapDict["gasStationPixmap"]=QPixmap(os.path.join(env.getImageRoot(), "poi/fillingstation.png"))
        self.pixmapDict["barrierPixmap"]=QPixmap(os.path.join(env.getImageRoot(), "poi/barrier.png"))
        self.pixmapDict["parkingPixmap"]=QPixmap(os.path.join(env.getImageRoot(), "poi/parking.png"))
        self.pixmapDict["speedCameraImage"]=QPixmap(os.path.join(env.getImageRoot(), "poi/trafficcamera.png"))
        self.pixmapDict["highwayExitImage"]=QPixmap(os.path.join(env.getImageRoot(), "poi/flag.png"))
        self.pixmapDict["poiPixmap"]=QPixmap(os.path.join(env.getImageRoot(), "poi/flag.png"))
        self.pixmapDict["airportPixmap"]=QPixmap(os.path.join(env.getImageRoot(), "poi/airport.png"))
        self.pixmapDict["railwaystationtPixmap"]=QPixmap(os.path.join(env.getImageRoot(), "poi/train.png"))
        
        self.colorDict["backgroundColor"]=QColor(120, 120, 120, 200)
        self.colorDict["mapBackgroundColor"]=QColor(255, 255, 255)
        self.colorDict["wayCasingColor"]=QColor(0x99, 0x99, 0x99)
        self.colorDict["tunnelColor"]=Qt.white
        self.colorDict["bridgeCasingColor"]=QColor(0x50, 0x50, 0x50)
        self.colorDict["accessWaysColor"]=QColor(255, 0, 0, 100)
        self.colorDict["onewayWaysColor"]=QColor(0, 0, 255, 100)
        self.colorDict["livingStreeColor"]=QColor(0, 255, 0, 100)
        self.colorDict["waterColor"]=QColor(0xb5, 0xd0, 0xd0)
        self.colorDict["adminAreaColor"]=QColor(0, 0, 0)
        self.colorDict["warningBackgroundColor"]=QColor(255, 0, 0, 200)
        self.colorDict["naturalColor"]=QColor(0x8d, 0xc5, 0x6c)
        self.colorDict["buildingColor"]=QColor(0xbc, 0xa9, 0xa9, 200)
        self.colorDict["highwayAreaColor"]=QColor(255, 255, 255)
        self.colorDict["railwayAreaColor"]=QColor(0xdf, 0xd1, 0xd6)
        self.colorDict["railwayColor"]=QColor(0x90, 0x90, 0x90)
        self.colorDict["landuseColor"]=QColor(150, 150, 150)
        self.colorDict["placeTagColor"]=QColor(0xff, 0xff, 0xff, 150)
        self.colorDict["residentialColor"]=QColor(0xdd, 0xdd, 0xdd)
        self.colorDict["commercialColor"]=QColor(0xef, 0xc8, 0xc8)
        self.colorDict["farmColor"]=QColor(0xea, 0xd8, 0xbd)
        self.colorDict["grassColor"]=QColor(0xcf, 0xec, 0xa8)
        self.colorDict["greenfieldColor"]=QColor(0x9d, 0x9d, 0x6c)
        self.colorDict["industrialColor"]=QColor(0xdf, 0xd1, 0xd6)
        self.colorDict["aerowayColor"]=QColor(0x50, 0x50, 0x50)
        self.colorDict["aerowayAreaColor"]=QColor(0xdf, 0xd1, 0xd6)
        
        self.initStreetColors()
        self.initBrush()
        self.initPens()
        self.initFonts()
        
        self.displayPOITypeList=list(self.POI_INFO_DICT.keys())
        self.displayAreaTypeList=list(self.AREA_INFO_DICT.keys())

    def getDisplayPOITypeList(self):
        return self.displayPOITypeList
        
    def setDisplayPOITypeList(self, displayPOITypeList):
        self.displayPOITypeList=displayPOITypeList
        
    def getDisplayAreaTypeList(self):
        return self.displayAreaTypeList
    
    def setDisplayAreaTypeList(self, displayAreaTypeList):
        self.displayAreaTypeList=displayAreaTypeList
        
    def getStyleColor(self, key):
        if key in self.colorDict:
            return self.colorDict[key]
        
        return self.errorColor
    
    def getStylePixmap(self, key):
        if key in self.pixmapDict:
            return self.pixmapDict[key]
        
        return self.errorImage
    
    def createStreetPen(self, color):
        pen=QPen()
        pen.setColor(color)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        return pen

    def initPens(self):
        self.penDict["edgePen"]=self.createStreetPen(QColor(255, 255, 0, 200))
        self.penDict["routePen"]=self.createStreetPen(QColor(255, 0, 0, 200))
        self.penDict["trackPen"]=self.createStreetPen(QColor(0, 255, 0, 200))
        self.penDict["routeOverlayPen"]=self.createStreetPen(QColor(0, 255, 0, 200))
        self.penDict["blueCrossingPen"]=self.createStreetPen(QColor(0, 0, 255, 200))
        self.penDict["redCrossingPen"]=self.createStreetPen(QColor(255, 0, 0, 200))
        self.penDict["greenCrossingPen"]=self.createStreetPen(QColor(0, 255, 0, 200))
        self.penDict["cyanCrossingPen"]=self.createStreetPen(QColor(0, 255, 255, 200))
        self.penDict["grayCrossingPen"]=self.createStreetPen(QColor(120, 120, 120, 200))
        self.penDict["blackCrossingPen"]=self.createStreetPen(QColor(0, 0, 0, 200))
        self.penDict["yellowCrossingPen"]=self.createStreetPen(QColor(255, 255, 0, 200))
        self.penDict["whiteCrossingPen"]=self.createStreetPen(QColor(255, 255, 255, 200))
        
        pen=QPen()
        pen.setColor(self.getStyleColor("waterColor"))
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        pen.setStyle(Qt.SolidLine)
        self.penDict["waterwayPen"]=pen

        pen=QPen()
        pen.setColor(self.getStyleColor("waterColor"))
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        pen.setStyle(Qt.DotLine)
        self.penDict["waterwayTunnelPen"]=pen
        
        pen=QPen()
        pen.setColor(Qt.white)
        self.penDict["textPen"]=pen

        pen=QPen()
        pen.setColor(Qt.black)
        self.penDict["placePen"]=pen
        
        pen=QPen()
        pen.setColor(self.getStyleColor("adminAreaColor"))
        pen.setStyle(Qt.DotLine)
        pen.setWidth(2.0)
        self.penDict["adminArea"]=pen

        pen=QPen()
        pen.setColor(self.getStyleColor("railwayColor"))
        pen.setStyle(Qt.DashLine)
        self.penDict["railway"]=pen        

        pen=QPen()
        pen.setColor(self.getStyleColor("bridgeCasingColor"))
        pen.setStyle(Qt.SolidLine)
        pen.setCapStyle(Qt.FlatCap)
        self.penDict["railwayBridge"]=pen

        pen=QPen()
        pen.setColor(self.getStyleColor("railwayColor"))
        pen.setStyle(Qt.DashLine)
        self.penDict["railwayTunnel"]=pen

        pen=QPen()
        pen.setColor(self.getStyleColor("aerowayColor"))
        pen.setStyle(Qt.SolidLine)
        self.penDict["aeroway"]=pen
                      
    def getStylePen(self, key):
        if key in self.penDict:
            return self.penDict[key]
        return self.Qt.NoPen
    
    def getPenForCrossingType(self, crossingType):
        if crossingType==Constants.CROSSING_TYPE_NORMAL:
            return self.getStylePen("greenCrossingPen")
        elif crossingType==Constants.CROSSING_TYPE_LINK_LINK:
            return self.getStylePen("cyanCrossingPen")
        elif crossingType==Constants.CROSSING_TYPE_MOTORWAY_EXIT or crossingType==Constants.CROSSING_TYPE_LINK_START or crossingType==Constants.CROSSING_TYPE_LINK_END:
            # motorway junction or _link
            return self.getStylePen("blueCrossingPen")
        elif crossingType==Constants.CROSSING_TYPE_ROUNDABOUT_ENTER:
            # roundabout enter
            return self.getStylePen("yellowCrossingPen")
        elif crossingType==Constants.CROSSING_TYPE_ROUNDABOUT_EXIT:
            # roundabout exit
            return self.getStylePen("yellowCrossingPen")
        elif crossingType==Constants.CROSSING_TYPE_FORBIDDEN or crossingType==Constants.CROSSING_TYPE_BARRIER:
            # no enter oneway
            return self.getStylePen("blackCrossingPen")
           
        return self.getStylePen("whiteCrossingPen")
    
    def initStreetColors(self):
        self.colorDict[Constants.STREET_TYPE_MOTORWAY]=QColor(0x80, 0x9b, 0xc0)
        self.colorDict[Constants.STREET_TYPE_MOTORWAY_LINK]=QColor(0x80, 0x9b, 0xc0)
        self.colorDict[Constants.STREET_TYPE_TRUNK]=QColor(0xa9, 0xdb, 0xa9)
        self.colorDict[Constants.STREET_TYPE_TRUNK_LINK]=QColor(0xa9, 0xdb, 0xa9)
        self.colorDict[Constants.STREET_TYPE_PRIMARY]=QColor(0xec, 0x98, 0x9a)
        self.colorDict[Constants.STREET_TYPE_PRIMARY_LINK]=QColor(0xec, 0x98, 0x9a)
        self.colorDict[Constants.STREET_TYPE_SECONDARY]=QColor(0xfe, 0xd7, 0xa5)
        self.colorDict[Constants.STREET_TYPE_SECONDARY_LINK]=QColor(0xfe, 0xd7, 0xa5)
        self.colorDict[Constants.STREET_TYPE_TERTIARY]=QColor(0xff, 0xff, 0xb3)
        self.colorDict[Constants.STREET_TYPE_TERTIARY_LINK]=QColor(0xff, 0xff, 0xb3)
        self.colorDict[Constants.STREET_TYPE_RESIDENTIAL]=QColor(0xff, 0xff, 0xff)
        self.colorDict[Constants.STREET_TYPE_UNCLASSIFIED]=QColor(0xff, 0xff, 0xff)
        self.colorDict[Constants.STREET_TYPE_ROAD]=QColor(0xff, 0xff, 0xff)
        self.colorDict[Constants.STREET_TYPE_SERVICE]=QColor(0xff, 0xff, 0xff)
        self.colorDict[Constants.STREET_TYPE_LIVING_STREET]=QColor(0xff, 0xff, 0xff)

    def getRelativePenWidthForZoom(self, zoom):
        if zoom==18:
            return 1.0
        if zoom==17:
            return 0.8
        if zoom==16:
            return 0.7
        if zoom==15:
            return 0.6
        if zoom==14:
            return 0.5

        return 0.4
    
    def getStreetWidth(self, streetTypeId, zoom):
        width=14
        if streetTypeId==Constants.STREET_TYPE_MOTORWAY:
            width=width*1.6
        # motorway link
        elif streetTypeId==Constants.STREET_TYPE_MOTORWAY_LINK:
            width=width*1.2
        # trunk
        elif streetTypeId==Constants.STREET_TYPE_TRUNK:
            width=width*1.6
        # trunk link
        elif streetTypeId==Constants.STREET_TYPE_TRUNK_LINK:
            width=width*1.2
        # primary
        elif streetTypeId==Constants.STREET_TYPE_PRIMARY or streetTypeId==Constants.STREET_TYPE_PRIMARY_LINK:
            width=width*1.4
        # secondary
        elif streetTypeId==Constants.STREET_TYPE_SECONDARY or streetTypeId==Constants.STREET_TYPE_SECONDARY_LINK:
            width=width*1.2
        # tertiary
        elif streetTypeId==Constants.STREET_TYPE_TERTIARY or streetTypeId==Constants.STREET_TYPE_TERTIARY_LINK:
            width=width*1.0
        # 
        elif streetTypeId==Constants.STREET_TYPE_LIVING_STREET or streetTypeId==Constants.STREET_TYPE_RESIDENTIAL or streetTypeId==Constants.STREET_TYPE_ROAD or streetTypeId==Constants.STREET_TYPE_UNCLASSIFIED:
            width=width*0.8
        # service
        else:
            width=width*0.6
            
        return int(self.getRelativePenWidthForZoom(zoom)*width)
    
    def getStreetPenWidthForZoom(self, zoom):
        if zoom==18:
            return 16
        if zoom==17:
            return 14
        if zoom==16:
            return 10
        if zoom==15:
            return 8
        if zoom==14:
            return 4
        
        return 2

    def getRailwayPenWidthForZoom(self, zoom, tags):
        if zoom==18:
            return 4
        if zoom==17:
            return 3
        if zoom==16:
            return 2
        if zoom==15:
            return 1
        
        return 1

    def getAerowayPenWidthForZoom(self, zoom, tags):
        aerowayType=tags["aeroway"]
        if aerowayType=="runway":
            if zoom==18:
                return 25
            if zoom==17:
                return 18
            if zoom==16:
                return 15
            if zoom==15:
                return 10
            if zoom==14:
                return 8
        elif aerowayType=="taxiway":
            if zoom==18:
                return 10
            if zoom==17:
                return 8
            if zoom==16:
                return 5
            if zoom==15:
                return 3
            if zoom==14:
                return 2

        return 2
    
    def getWaterwayPenWidthForZoom(self, zoom, tags):
        waterwayType=tags["waterway"]
        if waterwayType=="river":
            if zoom==18:
                return 12
            if zoom==17:
                return 10
            if zoom==16:
                return 8
            if zoom==15:
                return 4
            if zoom==14:
                return 1
            
        else:
            if zoom==18:
                return 8
            if zoom==17:
                return 6
            if zoom==16:
                return 4
            if zoom==15:
                return 2
            if zoom==14:
                return 1
        
        return 1
    
    def getPenWithForPoints(self, zoom):
        return self.getStreetPenWidthForZoom(zoom)+4
   
    def getRoadPenKey(self, streetTypeId, zoom, casing, oneway, tunnel, bridge, access, livingStreet):
        return "%s-%s-%s-%s-%s-%s-%s-%s"%(str(streetTypeId), str(zoom), str(casing), str(oneway), str(tunnel), str(bridge), str(access), str(livingStreet))
    
    def getRoadPen(self, streetTypeId, zoom, casing, oneway, tunnel, bridge, access, livingStreet):
        key=self.getRoadPenKey(streetTypeId, zoom, casing, oneway, tunnel, bridge, access, livingStreet)
        
        if key in self.penDict:
            return self.penDict[key]
                
        color=self.getStyleColor(streetTypeId)
        width=self.getStreetWidth(streetTypeId, zoom)
        brush=Qt.NoBrush
        pen=QPen()
        pen.setStyle(Qt.SolidLine)
        pen.setWidth(width)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)

        if casing==True:
            brush=QBrush(self.getStyleColor("wayCasingColor"), Qt.SolidPattern)
            pen.setWidth(width)

        else:
            if access==True:
                brush=QBrush(self.getStyleColor("accessWaysColor"), Qt.SolidPattern)
                pen.setWidth(width/2)
                pen.setStyle(Qt.DotLine)

            elif oneway==True:
                brush=QBrush(self.getStyleColor("onewayWaysColor"), Qt.SolidPattern)
                pen.setWidth(width/2)
                pen.setStyle(Qt.DotLine)
            
            elif livingStreet==True:
                brush=QBrush(self.getStyleColor("livingStreeColor"), Qt.SolidPattern)
                pen.setWidth(width/2)
                pen.setStyle(Qt.DotLine)

            else:
                if tunnel==True:
                    brush=QBrush(self.getStyleColor("tunnelColor"), Qt.Dense2Pattern)
                    pen.setWidth(width-2)
                elif bridge==True:
                    brush=QBrush(self.getStyleColor("bridgeCasingColor"), Qt.SolidPattern)
                    pen.setCapStyle(Qt.FlatCap)
                    pen.setWidth(width+2)
                else:
                    brush=QBrush(color, Qt.SolidPattern)
                    if width>2:
                        pen.setWidth(width-2)
                    else:
                        pen.setWidth(width)
                        
        pen.setBrush(brush)
        self.penDict[key]=pen
        return pen
    
    def getStyleBrush(self, key):
        if key in self.brushDict:
            return self.brushDict[key]
        return Qt.NoBrush
     
    def initBrush(self):
        self.brushDict["water"]=QBrush(self.getStyleColor("waterColor"), Qt.SolidPattern)
        self.brushDict["natural"]=QBrush(self.getStyleColor("naturalColor"), Qt.SolidPattern)
        self.brushDict["adminArea"]=QBrush(self.getStyleColor("adminAreaColor"), Qt.SolidPattern)
        self.brushDict["building"]=QBrush(self.getStyleColor("buildingColor"), Qt.SolidPattern)
        self.brushDict["highway"]=QBrush(self.getStyleColor("highwayAreaColor"), Qt.SolidPattern)
        self.brushDict["railwayLanduse"]=QBrush(self.getStyleColor("railwayAreaColor"), Qt.SolidPattern)
        self.brushDict["landuse"]=QBrush(self.getStyleColor("landuseColor"), Qt.SolidPattern)
        self.brushDict["residential"]=QBrush(self.getStyleColor("residentialColor"), Qt.SolidPattern)
        self.brushDict["commercial"]=QBrush(self.getStyleColor("commercialColor"), Qt.SolidPattern)
        self.brushDict["farm"]=QBrush(self.getStyleColor("farmColor"), Qt.SolidPattern)
        self.brushDict["grass"]=QBrush(self.getStyleColor("grassColor"), Qt.SolidPattern)
        self.brushDict["greenfield"]=QBrush(self.getStyleColor("greenfieldColor"), Qt.SolidPattern)
        self.brushDict["industrial"]=QBrush(self.getStyleColor("industrialColor"), Qt.SolidPattern)
        self.brushDict["aerowayArea"]=QBrush(self.getStyleColor("aerowayAreaColor"), Qt.SolidPattern)
        
    def getPixmapForNodeType(self, nodeType):
        if nodeType in self.POI_INFO_DICT.keys():
            pixmapName=self.POI_INFO_DICT[nodeType]["pixmap"]
            if pixmapName!=None:
                return self.getStylePixmap(pixmapName)
            return None
            
        return self.getStylePixmap("poiPixmap")
        
    def getPOIDictAsList(self):
        poiTypeList=list()
        i=0
        for key, value in self.POI_INFO_DICT.items():
            poiTypeList.append((i, key, value["pixmap"], value["desc"], value["zoom"]))
            i=i+1
        return poiTypeList

    def getDisplayPOIListForZoom(self, zoom):
        poiTypeList=list()
        for poiType in self.displayPOITypeList:
            tags=self.POI_INFO_DICT[poiType]
            zoomValue=tags["zoom"]
            if zoomValue!=None:
                if zoomValue<=zoom:
                    poiTypeList.append(poiType)
            else:
                poiTypeList.append(poiType)
        return poiTypeList
                                 
    def getAreaDictAsList(self):
        areaTypeList=list()
        i=0
        for key, value in self.AREA_INFO_DICT.items():
            areaTypeList.append((i, key, value["desc"], value["zoom"]))
            i=i+1
        return areaTypeList
    
    def getDisplayAreaListForZoom(self, zoom):
        areaTypeList=list()
        for areaType in self.displayAreaTypeList:
            tags=self.AREA_INFO_DICT[areaType]
            zoomValue=tags["zoom"]
            if zoomValue!=None:
                if zoomValue<=zoom:
                    areaTypeList.append(areaType)
            else:
                areaTypeList.append(areaType)
        return areaTypeList

    def getFontForTextDisplay(self, tags, zoom, virtualZoom):
        placeType=tags["place"]
        
        if zoom==18:
            minFont=16
        elif zoom==17:
            minFont=14
        else:
            minFont=12
        
        if virtualZoom==True:
            minFont=minFont*2
                
        font=None
        if placeType=="city":
            font=self.fontDict["boldFont"]
            font.setPointSize(minFont+6)
        else:
            if zoom <15:
                return None
            
            font=self.fontDict["normalFont"]
            if placeType=="town":
                font.setPointSize(minFont+4)
            elif placeType=="village":
                font.setPointSize(minFont+2)                    
            elif placeType=="suburb":
                font.setPointSize(minFont)
            
        return font
    
    def getStyleFont(self, key):
        if key in self.fontDict.keys():
            return self.fontDict[key]
        
        return self.fontDict["defaultFont"]
    
    def initFonts(self):
        font = QFont("Helvetica")
        font.setBold(True)
        self.fontDict["boldFont"]=font
        
        font = QFont("Helvetica")
        self.fontDict["normalFont"]=font

        font = QFont("Helvetica")
        font.setPointSize(20)
        self.fontDict["wayInfoFont"]=font
        
        font = QFont("Helvetica")
        font.setPointSize(16)
        self.fontDict["defaultFont"]=font
        
    SHOW_CASING_START_ZOOM=14
    SHOW_BRIDGES_START_ZOOM=16
    SHOW_STREET_OVERLAY_START_ZOOM=17
    USE_ANTIALIASING_START_ZOOM=17
    SHOW_BUILDING_START_ZOOM=17
    
#    def getLaneWith(self, zoom):
#        print(zoom)
#        S=6371000*math.cos(0)/math.pow(2, zoom+8)
#        return S
        