'''
Created on Mar 31, 2012

@author: maxl
'''

import os
import math

from PyQt4.QtCore import Qt
from PyQt4.QtGui import QFont, QPixmap, QColor, QPen, QBrush
from osmparser.osmdataaccess import Constants
from utils.env import getImageRoot

class OSMStyle():
    POI_INFO_DICT={Constants.POI_TYPE_BARRIER:{"pixmap":"barrierPixmap", "desc":"Barrier", "zoom":15},
                   Constants.POI_TYPE_ENFORCEMENT:{"pixmap":"speedCameraImage", "desc":"Speed Camera", "zoom":15},
                   Constants.POI_TYPE_GAS_STATION:{"pixmap":"gasStationPixmap", "desc":"Gas Station", "zoom":15},
                   Constants.POI_TYPE_PARKING:{"pixmap":"parkingPixmap", "desc":"Parking", "zoom":15},
                   Constants.POI_TYPE_HOSPITAL:{"pixmap":"hospitalPixmap", "desc":"Hospital", "zoom":15},
                   Constants.POI_TYPE_PLACE:{"pixmap":None, "desc":"Place", "zoom":10},
                   Constants.POI_TYPE_MOTORWAY_JUNCTION:{"pixmap":None, "desc":"Highway Exit", "zoom":15},
                   Constants.POI_TYPE_POLICE:{"pixmap":"policePixmap", "desc":"Police", "zoom":15},
                   Constants.POI_TYPE_SUPERMARKET:{"pixmap":"supermarketPixmap", "desc":"Supermarket", "zoom":15},
                   Constants.POI_TYPE_AIRPORT:{"pixmap":"airportPixmap", "desc":"Airport", "zoom":15},
                   Constants.POI_TYPE_RAILWAYSTATION:{"pixmap":"railwaystationtPixmap", "desc":"Railway Station", "zoom":15},
                   Constants.POI_TYPE_VETERIANERY:{"pixmap":"veterinaryPixmap", "desc":"Veterinary", "zoom":15},
                   Constants.POI_TYPE_CAMPING:{"pixmap":"campingPixmap", "desc":"Camping", "zoom":15}}
    
    AREA_INFO_DICT={Constants.AREA_TYPE_AEROWAY:{"desc":"Aeroways", "zoom":None},
                    Constants.AREA_TYPE_BUILDING:{"desc":"Buildings", "zoom":18},
                    Constants.AREA_TYPE_HIGHWAY_AREA:{"desc":"Highway Areas", "zoom":None},
                    Constants.AREA_TYPE_LANDUSE:{"desc":"Landuse", "zoom":None},
                    Constants.AREA_TYPE_NATURAL:{"desc":"Natural", "zoom":None},
                    Constants.AREA_TYPE_RAILWAY:{"desc":"Railways", "zoom":None},
                    Constants.AREA_TYPE_AMENITY:{"desc":"Amenity", "zoom":None}, 
                    Constants.AREA_TYPE_TOURISM:{"desc":"Tourism", "zoom":None}}
    
    def __init__(self):
        selfDict=dict()
        self.colorDict=dict()
        self.pixmapDict=dict()
        self.penDict=dict()
        self.brushDict=dict()
        self.fontDict=dict()
        
        self.errorImage=QPixmap(os.path.join(getImageRoot(), "error.png"))
        self.errorColor=QColor(255, 0, 0)
        
        self.pixmapDict["gpsPointImage"]=QPixmap(os.path.join(getImageRoot(), "gps-move.png"))
        self.pixmapDict["gpsPointImageStop"]=QPixmap(os.path.join(getImageRoot(), "gps-stop.png"))
        self.pixmapDict["minusPixmap"]=QPixmap(os.path.join(getImageRoot(), "minus.png"))
        self.pixmapDict["plusPixmap"]=QPixmap(os.path.join(getImageRoot(), "plus.png"))
        self.pixmapDict["showSidebarPixmap"]=QPixmap(os.path.join(getImageRoot(), "showSidebar.png"))
        self.pixmapDict["hideSidebarPixmap"]=QPixmap(os.path.join(getImageRoot(), "hideSidebar.png"))
      
        self.pixmapDict["turnRightImage"]=QPixmap(os.path.join(getImageRoot(), "directions/right.png"))
        self.pixmapDict["turnLeftImage"]=QPixmap(os.path.join(getImageRoot(), "directions/left.png"))
        self.pixmapDict["turnRighHardImage"]=QPixmap(os.path.join(getImageRoot(), "directions/sharply_right.png"))
        self.pixmapDict["turnLeftHardImage"]=QPixmap(os.path.join(getImageRoot(), "directions/sharply_left.png"))
        self.pixmapDict["turnRightEasyImage"]=QPixmap(os.path.join(getImageRoot(), "directions/slightly_right.png"))
        self.pixmapDict["turnLeftEasyImage"]=QPixmap(os.path.join(getImageRoot(), "directions/slightly_left.png"))
        self.pixmapDict["straightImage"]=QPixmap(os.path.join(getImageRoot(), "directions/forward.png"))
        self.pixmapDict["uturnImage"]=QPixmap(os.path.join(getImageRoot(), "directions/u-turn.png"))
        self.pixmapDict["roundaboutImage"]=QPixmap(os.path.join(getImageRoot(), "directions/roundabout.png"))
        self.pixmapDict["roundabout1Image"]=QPixmap(os.path.join(getImageRoot(), "directions/roundabout_exit1.png"))
        self.pixmapDict["roundabout2Image"]=QPixmap(os.path.join(getImageRoot(), "directions/roundabout_exit2.png"))
        self.pixmapDict["roundabout3Image"]=QPixmap(os.path.join(getImageRoot(), "directions/roundabout_exit3.png"))
        self.pixmapDict["roundabout4Image"]=QPixmap(os.path.join(getImageRoot(), "directions/roundabout_exit4.png"))
        
        self.pixmapDict["tunnelPixmap"]=QPixmap(os.path.join(getImageRoot(), "tunnel.png"))
        self.pixmapDict["downloadPixmap"]=QPixmap(os.path.join(getImageRoot(), "download.png"))
        self.pixmapDict["followGPSPixmap"]=QPixmap(os.path.join(getImageRoot(), "gps.png"))
        self.pixmapDict["favoritesPixmap"]=QPixmap(os.path.join(getImageRoot(), "favorites.png"))
        self.pixmapDict["addressesPixmap"]=QPixmap(os.path.join(getImageRoot(), "addresses.png"))
        self.pixmapDict["routePixmap"]=QPixmap(os.path.join(getImageRoot(), "route.png"))
        self.pixmapDict["centerGPSPixmap"]=QPixmap(os.path.join(getImageRoot(), "center-gps.png"))
        self.pixmapDict["settingsPixmap"]=QPixmap(os.path.join(getImageRoot(), "settings.png"))
        self.pixmapDict["gpsDataPixmap"]=QPixmap(os.path.join(getImageRoot(), "gps.png"))
        self.pixmapDict["mapPointPixmap"]=QPixmap(os.path.join(getImageRoot(), "flagMap.png"))
        
        self.pixmapDict["startPixmap"]=QPixmap(os.path.join(getImageRoot(), "routing/start.png"))
        self.pixmapDict["finishPixmap"]=QPixmap(os.path.join(getImageRoot(), "routing/finish.png"))
        self.pixmapDict["wayPixmap"]=QPixmap(os.path.join(getImageRoot(), "routing/way.png"))
        self.pixmapDict["crossingPixmap"]=QPixmap(os.path.join(getImageRoot(), "crossing.png"))
        
        self.pixmapDict["hospitalPixmap"]=QPixmap(os.path.join(getImageRoot(), "poi/hospital.png"))
        self.pixmapDict["policePixmap"]=QPixmap(os.path.join(getImageRoot(), "poi/police.png"))
        self.pixmapDict["supermarketPixmap"]=QPixmap(os.path.join(getImageRoot(), "poi/supermarket.png"))
        self.pixmapDict["gasStationPixmap"]=QPixmap(os.path.join(getImageRoot(), "poi/fillingstation.png"))
        self.pixmapDict["barrierPixmap"]=QPixmap(os.path.join(getImageRoot(), "poi/barrier.png"))
        self.pixmapDict["parkingPixmap"]=QPixmap(os.path.join(getImageRoot(), "poi/parking.png"))
        self.pixmapDict["speedCameraImage"]=QPixmap(os.path.join(getImageRoot(), "poi/trafficcamera.png"))
        self.pixmapDict["highwayExitImage"]=QPixmap(os.path.join(getImageRoot(), "poi/flag.png"))
        self.pixmapDict["poiPixmap"]=QPixmap(os.path.join(getImageRoot(), "poi/flag.png"))
        self.pixmapDict["airportPixmap"]=QPixmap(os.path.join(getImageRoot(), "poi/airport.png"))
        self.pixmapDict["railwaystationtPixmap"]=QPixmap(os.path.join(getImageRoot(), "poi/train.png"))
        self.pixmapDict["veterinaryPixmap"]=QPixmap(os.path.join(getImageRoot(), "poi/veterinary.png"))
        self.pixmapDict["campingPixmap"]=QPixmap(os.path.join(getImageRoot(), "poi/camping.png"))
        
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
        self.colorDict["woodAreaColor"]=QColor(0xae, 0xd1, 0xa0)
        self.colorDict["scrubAreaColor"]=QColor(0xb5, 0xe3, 0xb5)
        self.colorDict["tourismAreaColor"]=Qt.red
        self.colorDict["tourismCampingAreaColor"]=QColor(0xcc, 0xff, 0x99)
        self.colorDict["amenityParkingAreaColor"]=QColor(0xf7, 0xef, 0xb7)
        self.colorDict["amenityAreaColor"]=Qt.red
        self.colorDict["buildingColor"]=QColor(0xbc, 0xa9, 0xa9, 200)
        self.colorDict["highwayAreaColor"]=QColor(255, 255, 255)
        self.colorDict["railwayAreaColor"]=QColor(0xdf, 0xd1, 0xd6)
        self.colorDict["railwayColor"]=QColor(0x90, 0x90, 0x90)
        self.colorDict["landuseColor"]=QColor(150, 150, 150)
        self.colorDict["placeTagColor"]=QColor(78, 167, 255, 150)
        self.colorDict["residentialColor"]=QColor(0xdd, 0xdd, 0xdd)
        self.colorDict["commercialColor"]=QColor(0xef, 0xc8, 0xc8)
        self.colorDict["farmColor"]=QColor(0xea, 0xd8, 0xbd)
        self.colorDict["grassColor"]=QColor(0xcf, 0xec, 0xa8)
        self.colorDict["greenfieldColor"]=QColor(0x9d, 0x9d, 0x6c)
        self.colorDict["industrialColor"]=QColor(0xdf, 0xd1, 0xd6)
        self.colorDict["aerowayColor"]=QColor(0xbb, 0xbb, 0xcc)
        self.colorDict["aerowayAreaColor"]=QColor(0xdf, 0xd1, 0xd6)
        self.colorDict["nightModeColor"]=QColor(120, 120, 120, 70)
        self.colorDict["villageGreenAreaColor"]=QColor(0xcf, 0xec, 0xa8)
        self.colorDict["cliffColor"]=QColor(Qt.darkGray)
        self.colorDict["militaryColor"]=QColor(0xff, 0x55, 0x55)
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
        
        pen=QPen()
        pen.setColor(self.getStyleColor("cliffColor"))
        pen.setStyle(Qt.DashLine)
        pen.setWidth(2.0)
        self.penDict["cliffPen"]=pen
        
        pen=QPen()
        pen.setColor(self.getStyleColor("militaryColor"))
        pen.setWidth(3.0)
        self.penDict["militaryPen"]=pen
                              
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
    
    def getStreetWidth(self, streetTypeId, zoom, tags):
#        laneWidth=self.meterToPixel(5, zoom)
#        width=laneWidth*2
#        
#        if "lanes" in tags:
#            try:
#                numberLanes=int(tags["lanes"])
#                print(numberLanes)
#                if numberLanes>2:
#                    width=laneWidth*numberLanes
#                
#            except TypeError:
#                None
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
        if "width" in tags:
            try:
                value=int(tags["width"])
                return self.meterToPixel(value, zoom)
            except ValueError:
                None
                
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
#        if "width" in tags:
#            try:
#                value=int(tags["width"])
#                return self.meterToPixel(value, zoom)
#            except ValueError:
#                None
        
        if waterwayType=="river":
            if zoom==18:
                return 12
            if zoom==17:
                return 10
            if zoom==16:
                return 8
            if zoom==15:
                return 4
            
        elif waterwayType=="ditch":
            if zoom==18:
                return 2
                    
        else:
            if zoom==18:
                return 8
            if zoom==17:
                return 6
            if zoom==16:
                return 4
            if zoom==15:
                return 2
        
        return 1
    
    def getPenWithForPoints(self, zoom):
        return self.getStreetPenWidthForZoom(zoom)+4
   
    def getRoadPenKey(self, streetTypeId, zoom, casing, oneway, tunnel, bridge, access, livingStreet):
        return "%s-%s-%s-%s-%s-%s-%s-%s"%(str(streetTypeId), str(zoom), str(casing), str(oneway), str(tunnel), str(bridge), str(access), str(livingStreet))
    
    def getRoadPen(self, streetTypeId, zoom, casing, oneway, tunnel, bridge, access, livingStreet, tags):
        key=self.getRoadPenKey(streetTypeId, zoom, casing, oneway, tunnel, bridge, access, livingStreet)
        
        if key in self.penDict:
            return self.penDict[key]
                
        color=self.getStyleColor(streetTypeId)
        width=self.getStreetWidth(streetTypeId, zoom, tags)
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
        self.brushDict["highwayArea"]=QBrush(self.getStyleColor("highwayAreaColor"), Qt.SolidPattern)
        self.brushDict["railwayLanduse"]=QBrush(self.getStyleColor("railwayAreaColor"), Qt.SolidPattern)
        self.brushDict["landuse"]=QBrush(self.getStyleColor("landuseColor"), Qt.SolidPattern)
        self.brushDict["residential"]=QBrush(self.getStyleColor("residentialColor"), Qt.SolidPattern)
        self.brushDict["commercial"]=QBrush(self.getStyleColor("commercialColor"), Qt.SolidPattern)
        self.brushDict["farm"]=QBrush(self.getStyleColor("farmColor"), Qt.SolidPattern)
        self.brushDict["grass"]=QBrush(self.getStyleColor("grassColor"), Qt.SolidPattern)
        self.brushDict["greenfield"]=QBrush(self.getStyleColor("greenfieldColor"), Qt.SolidPattern)
        self.brushDict["industrial"]=QBrush(self.getStyleColor("industrialColor"), Qt.SolidPattern)
        self.brushDict["aerowayArea"]=QBrush(self.getStyleColor("aerowayAreaColor"), Qt.SolidPattern)
        self.brushDict["placeTag"]=QBrush(self.getStyleColor("placeTagColor"), Qt.SolidPattern)
        self.brushDict["tourismArea"]=QBrush(self.getStyleColor("tourismAreaColor"), Qt.SolidPattern)
        self.brushDict["tourismCampingArea"]=QBrush(self.getStyleColor("tourismCampingAreaColor"), Qt.SolidPattern)
        self.brushDict["amenityArea"]=QBrush(self.getStyleColor("amenityAreaColor"), Qt.SolidPattern)
        self.brushDict["amenityParkingArea"]=QBrush(self.getStyleColor("amenityParkingAreaColor"), Qt.SolidPattern)
        
        self.brushDict["villageGreenArea"]=QBrush(self.getStyleColor("villageGreenAreaColor"), Qt.SolidPattern)

        brush=QBrush(self.getStyleColor("scrubAreaColor"))
        brush.setTexture(QPixmap(os.path.join(getImageRoot(), "patterns/scrub.png")))
        brush.setStyle(Qt.TexturePattern)
        self.brushDict["scrubPatternArea"]=brush
        
        brush=QBrush(self.getStyleColor("naturalColor"))
        brush.setTexture(QPixmap(os.path.join(getImageRoot(), "patterns/forest.png")))
        brush.setStyle(Qt.TexturePattern)        
        self.brushDict["forestPatternArea"]=brush
        
        self.brushDict["scrubArea"]=QBrush(self.getStyleColor("scrubAreaColor"), Qt.SolidPattern)
        self.brushDict["forestArea"]=QBrush(self.getStyleColor("naturalColor"), Qt.SolidPattern)
        self.brushDict["woodArea"]=QBrush(self.getStyleColor("woodAreaColor"), Qt.SolidPattern)
        
        brush=QBrush(self.getStyleColor("waterColor"))
        brush.setTexture(QPixmap(os.path.join(getImageRoot(), "patterns/marsh.png")))
        brush.setStyle(Qt.TexturePattern)
        self.brushDict["marshPatternArea"]=brush

        brush=QBrush()
        brush.setTexture(QPixmap(os.path.join(getImageRoot(), "patterns/glacier2.png")))
        brush.setStyle(Qt.TexturePattern)
        self.brushDict["glacierPatternArea"]=brush

        brush=QBrush()
        brush.setTexture(QPixmap(os.path.join(getImageRoot(), "patterns/cliff2.png")))
        brush.setStyle(Qt.TexturePattern)
        self.brushDict["cliffPatternArea"]=brush

        brush=QBrush()
        brush.setTexture(QPixmap(os.path.join(getImageRoot(), "patterns/grave_yard_generic.png")))
        brush.setStyle(Qt.TexturePattern)
        self.brushDict["cemeteryPatternArea"]=brush

        brush=QBrush()
        brush.setTexture(QPixmap(os.path.join(getImageRoot(), "patterns/military.png")))
        brush.setStyle(Qt.TexturePattern)
        self.brushDict["militaryPatternArea"]=brush

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

    def getFontForTextDisplay(self, zoom, virtualZoom):        
        if virtualZoom==True:
            minFont=14
        else:    
            if zoom==18:
                minFont=12
            elif zoom==17:
                minFont=10
            else:
                minFont=8
                
        font=self.fontDict["normalFont"]
        font.setPointSize(minFont)
        return font
    
    def getFontForPlaceTagDisplay(self, tags, zoom, virtualZoom):
        placeType=tags["place"]
        
        if virtualZoom==True:
            minFont=18
        else:    
            if zoom==18:
                minFont=16
            elif zoom==17:
                minFont=14
            elif zoom==16:
                minFont=12
            elif zoom==15:
                minFont=10
            elif zoom==14:
                minFont=10
            else:
                minFont=8
            
        font=None
        if placeType=="city":
            font=self.fontDict["cityFont"]
            font.setPointSize(minFont+6)
        elif placeType=="town":
            font=self.fontDict["cityFont"]
            font.setPointSize(minFont+4)
        else:
            font=self.fontDict["normalFont"]
            if placeType=="village":
                font.setPointSize(minFont+2)                    
            elif placeType=="suburb" or placeType=="hamlet":
                font.setPointSize(minFont)
            
        return font
    
    def displayPlaceTypeForZoom(self, placeType, zoom):
        if zoom>=14:
            return True
        elif zoom>=13:
            if placeType!="hamlet":
                return True
        elif zoom>=12:
            if placeType!="hamlet" and placeType!="suburb":
                return True
        else:
            if placeType=="city" or placeType=="town":
                return True
            
        return False
    
    def getStyleFont(self, key):
        if key in self.fontDict.keys():
            return self.fontDict[key]
        
        return self.fontDict["defaultFont"]
    
    def initFonts(self):
        font = QFont("Sans")
        font.setBold(True)
        font.setUnderline(True)
        self.fontDict["cityFont"]=font
        
        font = QFont("Sans")
        font.setBold(True)
        self.fontDict["boldFont"]=font
        
        font = QFont("Sans")
        self.fontDict["normalFont"]=font

        font = QFont("Sans")
        font.setPointSize(18)
        self.fontDict["wayInfoFont"]=font
        
        font = QFont("Sans")
        font.setPointSize(16)
        self.fontDict["defaultFont"]=font

        font = QFont("Sans")
        font.setPointSize(16)
        self.fontDict["routeDistanceFont"]=font     
        
        font = QFont("Mono")
        font.setPointSize(16)
        font.setStyleHint(QFont.TypeWriter)
        self.fontDict["monoFontTopbar"]=font     

        font = QFont("Mono")
        font.setPointSize(14)
        font.setStyleHint(QFont.TypeWriter)
        self.fontDict["monoFont"]=font     
           
    SHOW_CASING_START_ZOOM=14
    SHOW_BRIDGES_START_ZOOM=16
    SHOW_STREET_OVERLAY_START_ZOOM=17
    USE_ANTIALIASING_START_ZOOM=17
    SHOW_BUILDING_START_ZOOM=17
    SHOW_REF_LABEL_WAYS_START_ZOOM=15
    SHOW_NAME_LABEL_WAYS_START_ZOOM=17
        
    # TODO: values for lat 45 dec north
    # http://wiki.openstreetmap.org/wiki/FAQ#What_is_the_map_scale_for_a_particular_zoom_level_of_the_map.3F
    # * cos(lat)
    def meterToPixel(self, value, zoom):
        mpp=None
        if zoom==18: 
            mpp=0.844525     
        elif zoom==17:
            mpp=1.689051
        elif zoom==16:
            mpp=3.378103
        elif zoom==15:
            mpp=6.756207
        elif zoom==14:
            mpp=13.512415   
        elif zoom==13:
            mpp=27.024829    
        
        pixel=1
        if mpp!=None:
            pixel=value/mpp
            if pixel < 1:
                pixel=1
            
        return int(pixel)
    
#    def getLaneWith(self, zoom):
#        print(zoom)
#        S=6371000*math.cos(0)/math.pow(2, zoom+8)
#        return S

    def getBrushForLanduseArea(self, tags, zoom):
        brush=Qt.NoBrush
        pen=Qt.NoPen
        
        landuse=tags["landuse"]
        if landuse=="railway":
            brush=self.getStyleBrush("railwayLanduse")
        elif landuse=="residential":
            brush=self.getStyleBrush("residential")
        elif landuse=="commercial" or landuse=="retail":
            brush=self.getStyleBrush("commercial")
        elif landuse=="field" or landuse=="farmland" or landuse=="farm" or landuse=="farmyard":
            brush=self.getStyleBrush("farm")
        elif landuse=="grass" or landuse=="meadow" or landuse=="grassland":
            brush=self.getStyleBrush("grass")
        elif landuse=="greenfield" or landuse=="brownfield":
            brush=self.getStyleBrush("greenfield")
        elif landuse=="industrial":
            brush=self.getStyleBrush("industrial")
        elif landuse=="forest":
            if zoom>=14:
                brush=self.getStyleBrush("forestPatternArea")
            else:
                brush=self.getStyleBrush("forestArea")
        elif landuse=="cemetery" or landuse=="grave_yard":
            brush=self.getStyleBrush("cemeteryPatternArea")
        elif landuse=="village_green":
            brush=self.getStyleBrush("villageGreenArea")
        elif landuse in Constants.LANDUSE_NATURAL_TYPE_SET:
            brush=self.getStyleBrush("natural")
        elif landuse in Constants.LANDUSE_WATER_TYPE_SET:
            brush=self.getStyleBrush("water") 
        elif landuse=="military":
            brush=self.getStyleBrush("militaryPatternArea")
            pen=self.getStylePen("militaryPen")                   
        else:
            brush=self.getStyleBrush("landuse")
        
        return brush, pen
        
    def getBrushForNaturalArea(self, tags, zoom):
        brush=Qt.NoBrush
        pen=Qt.NoPen
        if "waterway" in tags:         
            brush=self.getStyleBrush("water")
 
            if tags["waterway"]!="riverbank":
                pen=self.getStylePen("waterwayPen")
                pen.setWidth(self.getWaterwayPenWidthForZoom(zoom, tags))                      
            
        elif "natural" in tags:
            natural=tags["natural"]
            if natural=="scrub":
                if zoom>=14:
                    brush=self.getStyleBrush("scrubPatternArea")
                else:
                    brush=self.getStyleBrush("scrubArea")
                    
            elif natural=="marsh" or natural=="wetland" or natural=="mud":
                if zoom>=13:
                    brush=self.getStyleBrush("marshPatternArea")
                else:
                    brush=self.getStyleBrush("water")
                    
            elif natural=="wood":
                brush=self.getStyleBrush("woodArea")
            
            elif natural=="glacier":
                brush=self.getStyleBrush("glacierPatternArea")
            
            elif natural=="cliff":
                pen=self.getStylePen("cliffPen")
                
            else:
                if natural in Constants.NATURAL_WATER_TYPE_SET:
                    brush=self.getStyleBrush("water")
                else:
                    brush=self.getStyleBrush("natural")
        
        return brush, pen

    def getBrushForAmenityArea(self, tags, zoom):
        brush=Qt.NoBrush
        pen=Qt.NoPen
        
        amenity=tags["amenity"]
        if amenity=="parking":    
            brush=self.getStyleBrush("amenityParkingArea")
        else:
            brush=self.getStyleBrush("amenityArea")

        return brush, pen
    
    def getBrushForTourismArea(self, tags, zoom):
        brush=Qt.NoBrush
        pen=Qt.NoPen
        
        tourism=tags["tourism"]
        if tourism=="camping" or tourism=="camp_site":    
            brush=self.getStyleBrush("tourismCampingArea")
        else:
            brush=self.getStyleBrush("tourismArea")

        return brush, pen    
    