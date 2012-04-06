'''
Created on Mar 31, 2012

@author: maxl
'''

import env
import os
from PyQt4.QtCore import Qt
from PyQt4.QtGui import QPixmap, QColor, QPen, QBrush
from osmparser.osmparserdata import Constants

class OSMStyle():
    def __init__(self):
        self.styleDict=dict()
        self.colorDict=dict()
        self.pixmapDict=dict()
        self.penDict=dict()
        self.brushDict=dict()
        
        self.errorImage=QPixmap(os.path.join(env.getImageRoot(), "error.png"))
        self.errorColor=QColor(255, 0, 0, 254)
        
        self.pixmapDict["gpsPointImage"]=QPixmap(os.path.join(env.getImageRoot(), "gps-move-1.png"))
        self.pixmapDict["gpsPointImageStop"]=QPixmap(os.path.join(env.getImageRoot(), "gps-stop-big.png"))
        self.pixmapDict["startPointImage"]=QPixmap(os.path.join(env.getImageRoot(), "source.png"))
        self.pixmapDict["endPointImage"]=QPixmap(os.path.join(env.getImageRoot(), "target.png"))
        self.pixmapDict["wayPointImage"]=QPixmap(os.path.join(env.getImageRoot(), "waypoint.png"))        
        self.pixmapDict["turnRightImage"]=QPixmap(os.path.join(env.getImageRoot(), "directions/right.png"))
        self.pixmapDict["turnLeftImage"]=QPixmap(os.path.join(env.getImageRoot(), "directions/left.png"))
        self.pixmapDict["turnRighHardImage"]=QPixmap(os.path.join(env.getImageRoot(), "directions/sharply_right.png"))
        self.pixmapDict["turnLeftHardImage"]=QPixmap(os.path.join(env.getImageRoot(), "directions/sharply_left.png"))
        self.pixmapDict["turnRightEasyImage"]=QPixmap(os.path.join(env.getImageRoot(), "directions/slightly_right.png"))
        self.pixmapDict["turnLeftEasyImage"]=QPixmap(os.path.join(env.getImageRoot(), "directions/slightly_left.png"))
        self.pixmapDict["straightImage"]=QPixmap(os.path.join(env.getImageRoot(), "directions/forward.png"))
        self.pixmapDict["uturnImage"]=QPixmap(os.path.join(env.getImageRoot(), "u-turn.png"))
        self.pixmapDict["roundaboutImage"]=QPixmap(os.path.join(env.getImageRoot(), "directions/roundabout.png"))
        self.pixmapDict["roundabout1Image"]=QPixmap(os.path.join(env.getImageRoot(), "directions/roundabout_exit1.png"))
        self.pixmapDict["roundabout2Image"]=QPixmap(os.path.join(env.getImageRoot(), "directions/roundabout_exit2.png"))
        self.pixmapDict["roundabout3Image"]=QPixmap(os.path.join(env.getImageRoot(), "directions/roundabout_exit3.png"))
        self.pixmapDict["roundabout4Image"]=QPixmap(os.path.join(env.getImageRoot(), "directions/roundabout_exit4.png"))
        self.pixmapDict["speedCameraImage"]=QPixmap(os.path.join(env.getImageRoot(), "trafficcamera.png"))
        self.pixmapDict["tunnelPixmap"]=QPixmap(os.path.join(env.getImageRoot(), "tunnel.png"))
        self.pixmapDict["poiPixmap"]=QPixmap(os.path.join(env.getImageRoot(), "flag.png"))
        self.pixmapDict["gasStationPixmap"]=QPixmap(os.path.join(env.getImageRoot(), "fillingstation.png"))
        self.pixmapDict["barrierPixmap"]=QPixmap(os.path.join(env.getImageRoot(), "barrier.png"))
        self.pixmapDict["parkingPixmap"]=QPixmap(os.path.join(env.getImageRoot(), "parking.png"))
        self.pixmapDict["startPixmap"]=QPixmap(os.path.join(env.getImageRoot(), "start.png"))
        self.pixmapDict["finishPixmap"]=QPixmap(os.path.join(env.getImageRoot(), "finish.png"))
        self.pixmapDict["flagPixmap"]=QPixmap(os.path.join(env.getImageRoot(), "flag.png"))
        self.pixmapDict["downloadPixmap"]=QPixmap(os.path.join(env.getImageRoot(), "download.png"))
        self.pixmapDict["followGPSPixmap"]=QPixmap(os.path.join(env.getImageRoot(), "gps.png"))
        self.pixmapDict["favoritesPixmap"]=QPixmap(os.path.join(env.getImageRoot(), "favorites.png"))
        self.pixmapDict["addressesPixmap"]=QPixmap(os.path.join(env.getImageRoot(), "addresses.png"))
        self.pixmapDict["routePixmap"]=QPixmap(os.path.join(env.getImageRoot(), "route.png"))
        self.pixmapDict["centerGPSPixmap"]=QPixmap(os.path.join(env.getImageRoot(), "map-gps.png"))
        self.pixmapDict["settingsPixmap"]=QPixmap(os.path.join(env.getImageRoot(), "settings.png"))
        self.pixmapDict["gpsDataPixmap"]=QPixmap(os.path.join(env.getImageRoot(), "gps.png"))
        self.pixmapDict["mapPointPixmap"]=QPixmap(os.path.join(env.getImageRoot(), "mappoint.png"))
        self.pixmapDict["placeTagPixmap"]=QPixmap(os.path.join(env.getImageRoot(), "placeTagEmpty.png"))
        
        self.colorDict["backgroundColor"]=QColor(120, 120, 120, 200)
        self.colorDict["mapBackgroundColor"]=QColor(255, 255, 255, 254)
        self.colorDict["wayCasingColor"]=QColor(20, 20, 20, 200)
        self.colorDict["accessWaysColor"]=QColor(255, 0, 0, 100)
        self.colorDict["onewayWaysColor"]=QColor(0, 0, 255, 100)
        self.colorDict["livingStreeColor"]=QColor(0, 255, 0, 100)
        self.colorDict["waterColor"]=QColor(0xb5, 0xd0, 0xd0, 254)
        self.colorDict["adminAreaColor"]=QColor(0, 0, 0, 254)
        self.colorDict["warningBackgroundColor"]=QColor(255, 0, 0, 200)
        self.colorDict["naturalColor"]=QColor(0x8d, 0xc5, 0x6c, 254)
        self.colorDict["buildingColor"]=QColor(100, 100, 100, 254)
        self.colorDict["highwayAreaColor"]=QColor(255, 255, 255, 254)
        self.colorDict["railwayAreaColor"]=QColor(150, 150, 150, 254)
        self.colorDict["railwayColor"]=QColor(10, 10, 10, 254)
        self.colorDict["landuseColor"]=QColor(150, 150, 150, 254)
        self.colorDict["placeTagColor"]=QColor(0x38, 0x75, 0xd7, 200)
        
        self.initStreetColors()
        self.initBrush()
        self.initPens()
        
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
        pen.setColor(Qt.white)
        self.penDict["textPen"]=pen

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
        pen.setColor(self.getStyleColor("railwayColor"))
        pen.setStyle(Qt.SolidLine)
        pen.setCapStyle(Qt.RoundCap)
        self.penDict["railwayBridge"]=pen
        
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
        elif crossingType==Constants.CROSSING_TYPE_FORBIDDEN:
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
            return 1.2
        if zoom==17:
            return 0.8
        if zoom==16:
            return 0.6
        if zoom==15:
            return 0.4
        if zoom==14:
            return 0.2
        return 0.1
    
    def getStreetWidth(self, streetTypeId, zoom):
        width=14
        if streetTypeId==Constants.STREET_TYPE_MOTORWAY:
            width=width*2
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
        else:
            width=width*1.0
            
        return self.getRelativePenWidthForZoom(zoom)*width
    
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
        
        return 0

    def getRailwayPenWidthForZoom(self, zoom, tags):
        if zoom==18:
            return 5
        if zoom==17:
            return 4
        if zoom==16:
            return 3
        if zoom==15:
            return 2
        if zoom==14:
            return 1
        
        return 1

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
        
        return 0
    
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
                    brush=QBrush(color, Qt.Dense2Pattern)
                elif bridge==True:
                    brush=QBrush(Qt.black, Qt.SolidPattern)
                else:
                    brush=QBrush(color, Qt.SolidPattern)
                    pen.setWidth(width-2)
        
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
        
    def getPixmapForNodeType(self, nodeType):
        if nodeType==Constants.POI_TYPE_ENFORCEMENT:
            return self.getStylePixmap("speedCameraImage")
        if nodeType==Constants.POI_TYPE_GAS_STATION:
            return self.getStylePixmap("gasStationPixmap")
        if nodeType==Constants.POI_TYPE_BARRIER:
            return self.getStylePixmap("barrierPixmap")
        if nodeType==Constants.POI_TYPE_PARKING:
            return self.getStylePixmap("parkingPixmap")
        if nodeType==Constants.POI_TYPE_PLACE:
            return self.getStylePixmap("placeTagPixmap")
            
        return self.getStylePixmap("poiPixmap")
        