'''
Created on Feb 22, 2012

@author: maxl
'''

from utils.osmutils import OSMUtils
from osmparser.osmdataaccess import Constants
import time

WITH_CROSSING_DEBUG=False

MAXIMUM_DECISION_LENGTH=100.0
MAXIMUM_DECISION_LENGTH_SHORT=50.0
NORMAL_EDGE_RANGE=30.0
CLOSE_EDGE_RANGE=20.0
DECISION_EDGE_RANGE=10.0
CLOSE_HEADING_RANGE=45
DECISION_HEADING_RANGE=20
NORMAL_HEADING_RANGE=60
NO_CROSSING_SPEED=60
NEAR_CROSSING_LENGTH_MIN=NORMAL_EDGE_RANGE
PAST_CROSSING_LENGTH_MIN=15.0
PAST_CROSSING_LENGTH_MIN_SHORT=10.0
CROSSING_CALC_LENGTH_MIN=NORMAL_EDGE_RANGE*2
HEADING_CALC_LENGTH=20.0
CHECK_TURN_SPEED=5

class OSMRoute():
    def __init__(self, name="", routingPointList=None):
        self.name=name
        self.routingPointList=routingPointList
        self.routeInfo=None
        self.routeFinished=False
        
    def isRouteFinished(self):
        return self.routeFinished
    
    def getName(self):
        return self.name
    
    def getRoutingPointList(self):
        return self.routingPointList
    
    def calcRoute(self, osmParserData):
        if self.routeInfo==None:
#            print(self.routingPointList)
            self.routeInfo=osmParserData.calcRoute(self)
            self.routeFinished=False
            
    def changeRouteFromPoint(self, currentPoint, osmParserData):        
        self.routingPointList[0]=currentPoint
        self.routeInfo=None

    def getRouteInfo(self):
        return self.routeInfo

    def getRouteInfoLength(self):
        return len(self.routeInfo)
    
    def getStartPoint(self, index):
        if self.routeInfo!=None:
            if len(self.routeInfo)>index:
                return self.routeInfo[index]["startPoint"]
        return None 

    def getTargetPoint(self, index):
        if self.routeInfo!=None:
            if len(self.routeInfo)>index:
                return self.routeInfo[index]["targetPoint"]
        return None 
    
    def getEdgeList(self, index):
        if self.routeInfo!=None:
            if len(self.routeInfo)>index:
                return self.routeInfo[index]["edgeList"]
        return None   
      
    def getLength(self, index):
        if self.routeInfo!=None:
            if len(self.routeInfo)>index:
                return self.routeInfo[index]["length"]
        return 0

    def getTime(self, index):
        if self.routeInfo!=None:
            if len(self.routeInfo)>index:
                return self.routeInfo[index]["time"]
        return 0
        
    def getAllLength(self):
        if self.routeInfo!=None:
            i=0
            length=0
            while i<len(self.routeInfo):
                length=length+self.routeInfo[i]["length"]
                i=i+1
            return length
        return 0
    
    def getAllTime(self):
        if self.routeInfo!=None:
            i=0
            time=0
            while i<len(self.routeInfo):
                time=time+self.routeInfo[i]["time"]
                i=i+1
            return time
        return 0      
      
    def getTrackList(self, index):
        if self.routeInfo!=None:
            if len(self.routeInfo)>index:
                if "trackList" in self.routeInfo[index]:
                    return self.routeInfo[index]["trackList"]
        return None
    
    def complete(self):
        if self.routeInfo==None:
            return False
        
        for entry in self.routeInfo:
            if not "trackList" in entry:
                return False
        
        return True
    
    def printRoute(self, osmParserData):
        if self.routeInfo!=None:
            osmParserData.printRoute(self)
            
    def resolveRoutingPoints(self, osmParserData):
        for point in self.routingPointList:
            if point.getSource()==0:
                point.resolveFromPos(osmParserData)

    def isValid(self):
        for point in self.routingPointList:
            if not point.isValid():
                return False
        return True
    
    def targetPointReached(self, index):
        if self.routeInfo!=None:
            if len(self.routeInfo)>index:
                routeInfoEntry=self.routeInfo[index]
                startPoint=routeInfoEntry["startPoint"]
                self.routingPointList.remove(startPoint)
                if index==len(self.routeInfo)-1:
                    self.routeFinished=True
        
    def saveToConfig(self, config, section, name):    
        routeString="%s:"%(self.name)
        for point in self.routingPointList:
            routeString=routeString+point.toString()+":"
        
        routeString=routeString[:-1]
        config.set(section, name, "%s"%(routeString))

    def readFromConfig(self, value):
        self.routingPointList=list()
        parts=value.split(":")
        self.name=parts[0]
        for i in range(1, len(parts)-1, 4):
            name=parts[i]
            pointType=parts[i+1]
            lat=parts[i+2]
            lon=parts[i+3]
            point=OSMRoutingPoint()
            point.readFromConfig("%s:%s:%s:%s"%(name, pointType, lat, lon))
            self.routingPointList.append(point)
    
    def __repr__(self):
        routeString="%s:"%(self.name)
        for point in self.routingPointList:
            routeString=routeString+point.toString()+":"
        
        routeString=routeString[:-1]
        return routeString

        return "%s:%d:%f:%f"%(self.name, self.type, self.lat, self.lon)

        
class OSMRoutingPoint():
    TYPE_START=0
    TYPE_END=1
    TYPE_WAY=2
    TYPE_GPS=3
    TYPE_FAVORITE=4
    TYPE_TMP=5
    TYPE_MAP=6

    DEFAULT_RESOLVE_POINT_MARGIN=0.0005
    # maximal distance we try to resolve the pos
    DEFAULT_RESOLVE_MAX_DISTANCE=30.0
    
    def __init__(self, name="", pointType=0, pos=(0.0, 0.0)):
        self.lat=pos[0]
        self.lon=pos[1]
        self.target=0
        self.source=0
        # 0 start
        # 1 end
        # 2 way
        # 3 gps
        # 4 favorite
        # 5 temporary
        # 6 map point
        self.type=pointType
        self.wayId=None
        self.edgeId=None
        self.name=name
        self.usedRefId=0
        self.posOnEdge=0.0
        self.refPos=None
        self.closestRefPos=None
    
    def resolveFromPos(self, osmParserData):
        edgeId, _=osmParserData.getEdgeIdOnPos(self.lat, self.lon, self.DEFAULT_RESOLVE_POINT_MARGIN, self.DEFAULT_RESOLVE_MAX_DISTANCE)
        if edgeId==None:
            return

        (edgeId, startRef, endRef, length, wayId, source, target, _, _, _, coords)=osmParserData.getEdgeEntryForEdgeIdWithCoords(edgeId)
        wayId, _, refs, _, _, _, _, _=osmParserData.getWayEntryForId(wayId)
        if wayId==None:
            return
        
        refList=osmParserData.getRefListSubset(refs, startRef, endRef)
        ref, refPos, closestRefPos=osmParserData.getClosestRefOnEdge(self.lat, self.lon, refList, coords, 30.0)

        if ref==None:
            print("resolveFromPos not found for %f %f"%(self.lat, self.lon))
            return 
        
        self.closestRefPos=closestRefPos
        self.edgeId=edgeId
        self.target=target
        self.source=source
        self.usedRefId=ref
        self.wayId=wayId
        self.refPos=refPos
        
        self.posOnEdge=osmParserData.getPosOnOnEdge(self.closestRefPos[0], self.closestRefPos[1], coords, length)
#        print(self.posOnEdge)

    def isValid(self):
        return self.closestRefPos!=None and self.source!=0
    
    def getPosOnEdge(self):
        return self.posOnEdge
    
    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.lat==other.lat and self.lon==other.lon and self.type==other.type

    def __repr__(self):
        return "%s:%d:%f:%f"%(self.name, self.type, self.lat, self.lon)
    
    def toString(self):
        return self.__repr__()
    
    def __lt__(self, other):
        return self.name < other.name
    
    def getName(self):
        return self.name
    
    def getType(self):
        return self.type
    
    # real pos - can be anywhere
    def getPos(self):
        return (self.lat, self.lon)
    
    # nearest pos that lies on the edge
    # maybe a temporary created point between "real" refs
    def getClosestRefPos(self):
        return self.closestRefPos
    
    # nearest "real" way ref pos
    def getRefPos(self):
        return self.refPos
    
    def getEdgeId(self):
        return self.edgeId
    
    def getWayId(self):
        return self.wayId
    
    def getRefId(self):
        return self.usedRefId
    
    def getSource(self):
        return self.source
        
    def getTarget(self):
        return self.target
    
    def changeType(self, newType):
        self.type=newType
        
    def saveToConfig(self, config, section, name):        
        config.set(section, name, "%s"%(self.toString()))
        
    def readFromConfig(self, value):
        name, pointType, lat, lon=value.split(":")
        self.type=int(pointType)
        self.name=name
        self.lat=float(lat)
        self.lon=float(lon)

class OSMRouting():
    def __init__(self, osmParserData):
        self.osmParserData=osmParserData
        self.osmutils=OSMUtils()
        self.expectedNextEdgeId=None
        self.expectedNextEdge=None
        self.expectedHeading=None
        self.crosingWithoutExpected=False
        self.checkExpectedEdge=False
        self.approachingRef=None
        self.approachingRefPos=None
        self.currentEdgeData=None
        self.possibleEdges=None
        self.nearPossibleEdges=None
        self.edgeHeadings=None
        self.distanceToCrossing=None
        self.crossingPassed=False
        self.nearCrossing=False
        self.crossingReached=False
        self.nextEdgeLength=None
        self.otherNearHeading=False
        self.lastApproachingRef=None
        self.distanceFromCrossing=None
#        self.currentEdgeCheckTrigger=0
        self.longestPossibleEdge=None
        self.distanceToNextCrossing=None

    def cleanAll(self):
        self.cleanCurrentEdge()
        self.cleanEdgeCalculations(True)
        
    def cleanCurrentEdge(self):
        self.debugPrint(0.0, 0.0, "cleanCurrentEdge")
        self.currentEdgeData=None
        
    def cleanEdgeCalculations(self, cleanLastApproachingRef):
        if cleanLastApproachingRef==False:
            self.lastApproachingRef=self.approachingRef
        else:
            self.lastApproachingRef=None
            
        self.approachingRef=None
        self.approachingRefPos=None
        self.expectedNextEdgeId=None
        self.expectedNextEdge=None
        self.possibleEdges=None
        self.distanceToCrossing=None
        self.crossingPassed=False
        self.crossingReached=False
        self.nextEdgeLength=None
        self.otherNearHeading=False
        self.distanceFromCrossing=None
        self.nearCrossing=False
        self.nearPossibleEdges=None
#        self.currentEdgeCheckTrigger=0
        self.longestPossibleEdge=None
        self.distanceToNextCrossing=None
                
    def getCurrentSearchEdgeList(self):
        return self.possibleEdges
    
    def getExpectedNextEdge(self):
        return self.expectedNextEdge

    def getCurrentEdge(self):
        return self.currentEdgeData
        
    def calcApproachingRef(self, lat, lon, startRef, endRef, coords, track, useLastValue):
        # find the ref we are aproaching based on track
        # since we ony check when coming to a crossing 
        # but not on leaving
        ref=None
        refPos=None
        if useLastValue==False or self.lastApproachingRef==None:
            # if no previous value is available use close range
            onEdge=self.checkEdgeDataForPosWithCoords(lat, lon, coords, DECISION_EDGE_RANGE)
            if onEdge==False:
                self.debugPrint(lat, lon, "calcApproachingRef: not on edge")
                return ref, refPos
            
            lat1, lon1=coords[0]
            heading1=self.osmutils.headingDegrees(lat, lon, lat1, lon1)
    
            lat2, lon2=coords[-1]
            heading2=self.osmutils.headingDegrees(lat, lon, lat2, lon2)
            
            headingDiff1=self.osmutils.headingDiffAbsolute(track, heading1)
            headingDiff2=self.osmutils.headingDiffAbsolute(track, heading2)
            
            if headingDiff1<CLOSE_HEADING_RANGE or headingDiff2<CLOSE_HEADING_RANGE:
                if headingDiff1<headingDiff2:
                    ref=startRef
                    refPos=coords[0]
                else:
                    ref=endRef
                    refPos=coords[-1]
            else:
                self.debugPrint(lat, lon, "calcApproachingRef: headingDiff=%d %d"%(headingDiff1, headingDiff2))
        else:
            if self.lastApproachingRef==startRef:
                ref=endRef
                refPos=coords[-1]
            elif self.lastApproachingRef==endRef:
                ref=startRef
                refPos=coords[0]
                  
        return ref, refPos
    
    def checkForPosOnEdgeId(self, lat, lon, coords, maxDistance):
        if len(coords)!=0:
            lat1, lon1=coords[0]
            for lat2, lon2 in coords[1:]:
                onTrack=self.osmParserData.isOnLineBetweenPoints(lat, lon, lat1, lon1, lat2, lon2, maxDistance)
                if onTrack==True:
                    return True
                lat1=lat2
                lon1=lon2
                
        return False
    
    # check for any pos in on the first two track positions (first edge)
    def checkForPosOnTracklist(self, lat, lon, trackList, maxDistance=NORMAL_EDGE_RANGE):
        endTrack=2
        if len(trackList)==1:
            endTrack=1
        for trackItem in trackList[:endTrack]:
#            self.debugPrint(lat, lon, trackItem)
            coords=self.osmParserData.getCoordsOfTrackItem(trackItem)
            lat1, lon1=coords[0]
            for lat2, lon2 in coords[1:]:
                onTrack=self.osmParserData.isOnLineBetweenPoints(lat, lon, lat1, lon1, lat2, lon2, maxDistance)
                if onTrack==True:
                    return True
                lat1=lat2
                lon1=lon2
        
        return False
    
    def calcNextPossibleEdgesOnCrossing(self, crossingRef, lat, lon):
        possibleEdges=list()
        edgeHeadings=list()
        
        self.longestPossibleEdge=0
        # does not include currentEdgeOnRoute
        resultList=self.osmParserData.getDifferentEdgeEntryForStartOrEndPointWithCoords(crossingRef, self.currentEdgeData[0])
        if len(resultList)!=0: 
            for edge in resultList:
                edgeId, startRef, endRef, length, _, _, _, _, _, streetInfo, coords=edge
                streetTypeId, oneway, roundabout=self.osmParserData.decodeStreetInfo(streetInfo)
       
                # ignore certain types for crossing expectations
#                if streetTypeId==Constants.STREET_TYPE_SERVICE:
#                    # street type service
#                    continue
            
                # filter out onways with wrong start
                if oneway!=0:
                    if not self.osmParserData.isValidOnewayEnter(oneway, crossingRef, startRef, endRef):
                        continue

                # left turns in roundabouts
                if roundabout!=0:
                    if not crossingRef==startRef:
                        continue
                    
                # check turn restrictions but that takes time
                if self.osmParserData.isActiveTurnRestriction(self.currentEdgeData[0], edgeId, self.approachingRef):
                    continue
                        
                # filter out access limited streets
#                if self.osmParserData.isAccessRestricted(tags):
#                if "access" in tags:
#                    continue
                
                headingCoords=coords
                if crossingRef==endRef:
                    headingCoords=list()
                    headingCoords.extend(coords)
                    headingCoords.reverse()
                    
                heading=self.getCrossingHeadingForPoints(headingCoords)

                edgeHeadings.append(heading)
                possibleEdges.append(edge)
                if length>self.longestPossibleEdge:
                    self.longestPossibleEdge=length

        self.debugPrint(lat, lon, possibleEdges)
        return possibleEdges, edgeHeadings

    def getCrossingHeadingForPoints(self, coords):
        lat1, lon1=coords[0]
        for lat2, lon2 in coords[1:]:
            # use refs with distance more the 20m to calculate heading
            # if available else use the last one
            if self.osmutils.distance(lat1, lon1, lat2, lon2)>HEADING_CALC_LENGTH:
                break

        heading=self.osmutils.headingDegrees(lat1, lon1, lat2, lon2)
        return heading  
        
    def getBestMatchingNextEdgeForHeading(self, track, possibleEdges, edgeHeadings, lat, lon):
        if len(possibleEdges)==0:
            self.otherNearHeading=False
            self.nearPossibleEdges=list()
            return None, None

        if len(possibleEdges)==1:
            self.otherNearHeading=False
            self.nearPossibleEdges=list()
            expectedNextEdge=possibleEdges[0]
            nextEdgeLength=expectedNextEdge[3]
            return expectedNextEdge, nextEdgeLength
            
        closestEdge=self.getCurrentBestMatchingEdge(lat, lon, track, possibleEdges, NORMAL_EDGE_RANGE)
        if closestEdge==None:
            return None, None
        
        minHeadingEntry=possibleEdges.index(closestEdge)
        if minHeadingEntry!=None:
            expectedNextEdge=possibleEdges[minHeadingEntry]
            nextEdgeLength=expectedNextEdge[3]

            # no change - no need to calc rest
            if expectedNextEdge==self.expectedNextEdge:
                return expectedNextEdge, nextEdgeLength

            self.nearPossibleEdges=list()
            self.otherNearHeading=False
            i=0
            for heading in edgeHeadings:
                if heading!=None and heading!=edgeHeadings[minHeadingEntry]:
                    headingDiff=self.osmutils.headingDiffAbsolute(edgeHeadings[minHeadingEntry], heading)
                    if headingDiff<CLOSE_HEADING_RANGE:
                        # next best heading is near to best matching
                        self.debugPrint(lat, lon, "heading diff < %d %f"%(CLOSE_HEADING_RANGE, headingDiff))
                        self.nearPossibleEdges.append(possibleEdges[i])
                        self.otherNearHeading=True
                i=i+1
            return expectedNextEdge, nextEdgeLength

        return None, None
    
    # in routing mode we always set the nextEdgeIdOnRoute as the expected
    def setNextEdgeOnRouteAsExpected(self, track, possibleEdges, edgeHeadings, lat, lon, nextEdgeIdOnRoute):
        if len(possibleEdges)==0:
            self.otherNearHeading=False
            self.nearPossibleEdges=list()
            return None, None

        if len(possibleEdges)==1:
            self.otherNearHeading=False
            self.nearPossibleEdges=list()
            expectedNextEdge=possibleEdges[0]
            nextEdgeLength=expectedNextEdge[3]
            return expectedNextEdge, nextEdgeLength
            
        nextEdgeHeadingEntry=None
        i=0
        for possibleEdge in possibleEdges:
            if possibleEdge[0]==nextEdgeIdOnRoute:
                nextEdgeHeadingEntry=i
                break
            i=i+1
            
        if nextEdgeHeadingEntry!=None:
            expectedNextEdge=possibleEdges[nextEdgeHeadingEntry]
            nextEdgeLength=expectedNextEdge[3]
            # no change - no need to calc rest
            if expectedNextEdge==self.expectedNextEdge:
                return expectedNextEdge, nextEdgeLength

            self.nearPossibleEdges=list()
            self.otherNearHeading=False
            i=0
            for heading in edgeHeadings:
                if heading!=None and heading!=edgeHeadings[nextEdgeHeadingEntry]:
                    headingDiff=self.osmutils.headingDiffAbsolute(edgeHeadings[nextEdgeHeadingEntry], heading)
                    if headingDiff<CLOSE_HEADING_RANGE:
                        # next best heading is near to best matching
                        self.debugPrint(lat, lon, "heading diff < %d %f"%(CLOSE_HEADING_RANGE, headingDiff))
                        self.nearPossibleEdges.append(possibleEdges[i])
                        self.otherNearHeading=True
                i=i+1
            return expectedNextEdge, nextEdgeLength

        return None, None
    
    def checkEdgeDataForPos(self, lat, lon, edge, maxDistance):
        coords=edge[10]
        return self.checkForPosOnEdgeId(lat, lon, coords, maxDistance)

    def checkEdgeDataForPosWithCoords(self, lat, lon, coords, maxDistance):
        return self.checkForPosOnEdgeId(lat, lon, coords, maxDistance)
    
    # still use track info if available to select a "good" edge
    def getEdgeIdOnPosForRoutingFallback(self, lat, lon, fromMouse, margin, track, speed):        
        if track!=None and fromMouse==False:  
            # use close range if no current edge is available
            # it is also called for checking if still on current edge
            maxDistance=NORMAL_EDGE_RANGE
            if self.currentEdgeData==None:
                maxDistance=DECISION_EDGE_RANGE
                
            edge=self.getEdgeIdOnPosWithTrack(lat, lon, track, margin, maxDistance)
            if edge!=None:
                if self.currentEdgeData==None:
                    self.useEdge(lat, lon, track, speed, edge, True)
                elif self.currentEdgeData!=edge:
                    self.useEdge(lat, lon, track, speed, edge, True)
            else:
                self.cleanAll()
            
            return self.currentEdgeData
            
        self.cleanAll()
        
        edge=self.osmParserData.getEdgeOnPos(lat, lon, margin, DECISION_EDGE_RANGE)
        if edge!=None:
            return edge

        return None

    # distance to crossing that we assume is near crossing
    # here we start calculating the expected edge
    # and check for quick next edge
    def getToCrossingCheckDistance(self, speed):
        # must not be to long else we may switch to a "quick"
        # next edge before the next pos check is correct 
        # on that edge
        if speed==0:
            return NEAR_CROSSING_LENGTH_MIN
        value=int(speed/3.6)
        if value < NEAR_CROSSING_LENGTH_MIN:
            return NEAR_CROSSING_LENGTH_MIN
        return value
     
    # distance after crossing that we assume we
    # have passed the crossing
    # here we start checking the best matching edge
    # based on heading and pos and other near edges
    # must be higher then the minimal distance between
    # to gps signals
    def getFromCrossingCheckDistance(self, speed):
        if speed==0:
            return PAST_CROSSING_LENGTH_MIN
        value=int(speed/3.6)
        if value < PAST_CROSSING_LENGTH_MIN:
            return PAST_CROSSING_LENGTH_MIN
        return value
    
    # is the edge is shorter then the distance between to
    # gps signals we assume that we pass it
#    def isShortEdgeForSpeed(self, length, speed):
#        # if the length of the edge is shorter
#        # then the shortest possible - dont use as quick decision
#        # e.g. node 802094940
#        if length < NORMAL_EDGE_RANGE:
#            return False
#        value=self.getPosDistanceForSpeed(speed)
#        if length < value:
#            return True
#        return False
    
    # if the speed is high we assume that that we will
    # not take any crossing at all
    # will not be used if there are near edges
    def isSpeedHighEnoughForNoCrossing(self, speed):
        if speed > NO_CROSSING_SPEED:
            return True
        return False
    
    def updateCrossingDistances(self, lat, lon, distance, speed):
        if self.distanceToCrossing==None:
            return
        
        if self.nearCrossing==False and self.crossingPassed==False:
            # start counting if we are comming near to the crossing
            if distance > CROSSING_CALC_LENGTH_MIN:
                self.distanceToCrossing=distance
                return
            
        if distance <= self.distanceToCrossing:
            self.distanceToCrossing=distance
            crossingRange=self.getToCrossingCheckDistance(speed)
            # near crossing
            if self.distanceToCrossing < crossingRange:
                self.nearCrossing=True
                self.debugPrint(lat, lon, "near crossing %d"%self.distanceToCrossing)
            
            return

        self.distanceFromCrossing=distance
        self.crossingReached=True     
        self.debugPrint(lat, lon, "crossing reached %d"%self.distanceFromCrossing)
        
        # past crossing
        crossingRange=self.getFromCrossingCheckDistance(speed)
        if self.distanceFromCrossing >= PAST_CROSSING_LENGTH_MIN_SHORT:
            # if the edge is shorter then the minimal mast crossing range
            # decide earlier - which is maybe wrong
            if self.nextEdgeLength!=None and self.nextEdgeLength<crossingRange:
                self.crossingPassed=True
                self.debugPrint(lat, lon, "past crossing for short edge %d"%self.distanceFromCrossing)
                return
        
        if self.distanceFromCrossing > crossingRange:
            self.crossingPassed=True
            self.debugPrint(lat, lon, "past crossing %d"%self.distanceFromCrossing)

     
    def isQuickNextEdgeChoices(self, lat, lon, track, speed, edgeId):
        if len(self.possibleEdges)==1:
            # only one possible edge
            self.debugPrint(lat, lon, "next edge only one possible")
            return True
        
        # some assumptions if there are no near other edges
        if self.otherNearHeading==False:
            if self.isSpeedHighEnoughForNoCrossing(speed):
                self.debugPrint(lat, lon, "speed large - assume pass through")
                return True
            
#            if self.isShortEdgeForSpeed(self.nextEdgeLength, speed):
#                # short edge passed with speed - just use it
#                self.debugPrint(lat, lon, "next edge is short edge and speed large - assume pass through")
#                return True

        return False
        
    def calcNextCrossingEdges(self, lat, lon):
        # check if approaching ref is valid
        if self.approachingRef!=None:
            self.debugPrint(lat, lon, "calc next crossing edges at %d"%self.approachingRef)
            self.possibleEdges, self.edgeHeadings=self.calcNextPossibleEdgesOnCrossing(self.approachingRef, lat, lon)
        
    def calcNextEdgeValues(self, lat, lon, track, speed):
        edgeId, startRef, endRef, _, wayId, _, _, _, _, _, coords=self.currentEdgeData
        
        # can be None if is not clear
        self.approachingRef, self.approachingRefPos=self.calcApproachingRef(lat, lon, startRef, endRef, coords, track, True)
        
        # check if approaching ref is valid
        if self.approachingRef!=None:
            self.debugPrint(lat, lon, "approachingRef %d"%self.approachingRef)
            
            distance=self.getDistanceToNextCrossing(lat, lon)
            self.distanceToCrossing=distance
            self.crossingPassed=False
            self.nearCrossing=False
            self.crossingReached=False
        
    def useEdge(self, lat, lon, track, speed, edge, cleanLastApproachingRef):
        self.currentEdgeData=edge
            
        self.cleanEdgeCalculations(cleanLastApproachingRef)
                    
        # immediately calc next crossing to be available on the next call
        # else in case of a short edge we might miss the next crossing
        self.calcNextEdgeValues(lat, lon, track, speed)
        
        if self.approachingRef!=None:
            self.calcNextCrossingEdges(lat, lon)
            distance=self.getDistanceToNextCrossing(lat, lon)
            self.updateCrossingDistances(lat, lon, distance, speed)
            self.calcCurrentBestMatchingEdge(lat, lon, track, None)

    def isOnlyMatchingOnEdgeForDistance(self, lat, lon, speed, maxDistance):
        matchExpected=self.checkEdgeDataForPos(lat, lon, self.expectedNextEdge, maxDistance)
        
        matchingCount=0
        for otherPossible in self.nearPossibleEdges:
            matchOther=self.checkEdgeDataForPos(lat, lon, otherPossible, maxDistance)
            if matchOther==True:
                matchingCount=matchingCount+1

        if matchingCount>1:
            # can not be the only matching
            return False
        if matchingCount==1 and matchExpected:
            return False
        
        if matchExpected==False:
            return None
        return matchExpected

    def isOnlyMatchingOnEdge(self, lat, lon, speed):
        # first try with a close range to check as soon as possible
        maxDistance=DECISION_EDGE_RANGE
        onlyOneMatching=self.isOnlyMatchingOnEdgeForDistance(lat, lon, speed, maxDistance)
        if onlyOneMatching==None:
            # try again with a larger distance
            maxDistance=CLOSE_EDGE_RANGE
            onlyOneMatching=self.isOnlyMatchingOnEdgeForDistance(lat, lon, speed, maxDistance)
            if onlyOneMatching!=None:
                if onlyOneMatching==True:
                    self.debugPrint(lat, lon, "isOnlyMatchingEdge for CLOSE_EDGE_RANGE")
        else:
            if onlyOneMatching==True:
                self.debugPrint(lat, lon, "isOnlyMatchingEdge for DECISION_EDGE_RANGE")

        return onlyOneMatching
    
    def isChangedApproachingRef(self, lat, lon, track):
        _, startRef, endRef, _, _, _, _, _, _, _, coords=self.currentEdgeData
        approachingRef, _=self.calcApproachingRef(lat, lon, startRef, endRef, coords, track, False)
        if approachingRef!=self.approachingRef:
            return True, approachingRef
            
        return False, approachingRef
    
    def calcCurrentBestMatchingEdge(self, lat, lon, track, nextEdgeOnRoute):
        if self.expectedNextEdgeId!=None or self.nearCrossing==True: 
            self.debugPrint(lat, lon, "check possible edges")   
            if nextEdgeOnRoute!=None:
                expectedNextEdge, nextEdgeLength=self.setNextEdgeOnRouteAsExpected(track, self.possibleEdges, self.edgeHeadings, lat, lon, nextEdgeOnRoute)
            else:    
                expectedNextEdge, nextEdgeLength=self.getBestMatchingNextEdgeForHeading(track, self.possibleEdges, self.edgeHeadings, lat, lon)
            
            if expectedNextEdge!=None:
                self.debugPrint(lat, lon, "expected next edge %d %d"%(expectedNextEdge[0], nextEdgeLength))   
                self.expectedNextEdgeId=expectedNextEdge[0]
                self.expectedNextEdge=expectedNextEdge
                self.nextEdgeLength=nextEdgeLength
            else:
                # expected edge can become unknown again
                self.debugPrint(lat, lon, "expected next edge unknown")   
                self.expectedNextEdgeId=None
                self.expectedNextEdge=None
                self.nextEdgeLength=None
                   
    def checkEdge(self, lat, lon, track, speed, edge, fromMouse, margin):
        # use a large maxDistance to make sure we match the
        # epected edge in most cases
        # we already know that we have only one matching edge
        # in the case of close edges so no need to use a
        # smaler distance
        maxDistance=NORMAL_EDGE_RANGE
            
        # check the current expected
        if not self.checkEdgeDataForPos(lat, lon, edge, maxDistance):
            if self.distanceFromCrossing>self.longestPossibleEdge:
                self.debugPrint(lat, lon, "distance from crossing longer then edge length  fallback")
                return self.getEdgeIdOnPosForRoutingFallback(lat, lon, fromMouse, margin, track, speed)
            
        else:
            self.debugPrint(lat, lon, "pos on edge confirmed")
            self.useEdge(lat, lon, track, speed, edge, False)
            return self.currentEdgeData

        # no decision possible
        return None
    
    def getDistanceToNextCrossing(self, lat, lon):
        _, startRef, _, length, _, _, _, _, _, _, coords=self.currentEdgeData
        
        crossingRef=self.approachingRef
        trackCoords=coords
        if crossingRef==startRef:
            trackCoords=list()
            trackCoords.extend(coords)
            trackCoords.reverse()

        distance=self.osmParserData.getRemainingDistanceOnEdge(trackCoords, lat, lon, length)
        self.distanceToNextCrossing=distance
        
        if distance==None or distance < 0:
            # crossing passed use simple distance from the crossing
            distance=self.osmutils.distance(lat, lon, self.approachingRefPos[0], self.approachingRefPos[1])
        
        return distance
    
    def checkForEdgesInAvailableEdgeList(self, lat, lon, track, margin):
        edgeList=self.getCurrentEdgesInMargin(lat, lon, track, margin)
        if self.expectedNextEdge!=None:
            # is expected edge still in margin?
            if self.expectedNextEdge in edgeList:
                return True
        elif self.possibleEdges!=None:
            # is at least one possible edge in margin?
            for edge in self.possibleEdges:
                if edge in edgeList:
                    return True
                
        return False
    
    def getEdgeIdOnPosForRouting(self, lat, lon, track, nextEdgeOnRoute, margin, fromMouse, speed):        
        if track==None:
            return self.getEdgeIdOnPosForRoutingFallback(lat, lon, fromMouse, margin, track, speed)

        if self.currentEdgeData!=None:
            self.debugPrint(lat, lon, "current edge=%d"%self.currentEdgeData[0])
        if nextEdgeOnRoute!=None:
            self.debugPrint(lat, lon, "next edge=%d"%nextEdgeOnRoute)
            
        if self.currentEdgeData!=None:
            # final fallback if everything goes wrong
            if self.crossingPassed==True:        
                # check if expected edge is not in margin at all            
                if self.otherNearHeading==True:
                    if self.distanceFromCrossing>MAXIMUM_DECISION_LENGTH:
                        if not self.checkForEdgesInAvailableEdgeList(lat, lon, track, margin):
                            self.debugPrint(lat, lon, "lost expected edge fallback")
                            return self.getEdgeIdOnPosForRoutingFallback(lat, lon, fromMouse, margin, track, speed)

                else:
                    if self.distanceFromCrossing>MAXIMUM_DECISION_LENGTH_SHORT:
                        if not self.checkForEdgesInAvailableEdgeList(lat, lon, track, margin):
                            self.debugPrint(lat, lon, "lost expected edge fallback")
                            return self.getEdgeIdOnPosForRoutingFallback(lat, lon, fromMouse, margin, track, speed)
            
            if self.approachingRef!=None:
                distance=self.getDistanceToNextCrossing(lat, lon)
                self.updateCrossingDistances(lat, lon, distance, speed)
            
            # check if we turned on the edge
            if (self.nearCrossing==False and speed<CHECK_TURN_SPEED) or self.approachingRef==None:
                changed, newApproachingRef=self.isChangedApproachingRef(lat, lon, track)
                if changed==True:
                    # can still be None
                    self.debugPrint(lat, lon, "approaching ref changed")
                    self.useEdge(lat, lon, track, speed, self.currentEdgeData, True)
                    return self.currentEdgeData
                
            # check if we are still on the expected edge
            # only used between crossingPassed and nearCrossing  
            # on a short edge the check will fail since
            # nearCrossing is immediately set to True
            if self.nearCrossing==False:
                return self.getEdgeIdOnPosForRoutingFallback(lat, lon, fromMouse, margin, track, speed)                

            if self.expectedNextEdgeId!=None:                
                if self.crossingPassed==True or self.crossingReached==True:                    
                    if self.crossingReached==True:
                        if self.isQuickNextEdgeChoices(lat, lon, track, speed, self.expectedNextEdgeId):
                            self.useEdge(lat, lon, track, speed, self.expectedNextEdge, False)
                            return self.currentEdgeData
                                        
                    if self.crossingPassed==True:
                        if self.otherNearHeading==True and self.nearPossibleEdges!=None:
                            onlyOneMatchingEdge=self.isOnlyMatchingOnEdge(lat, lon, speed)
                            # can also be None
                            if onlyOneMatchingEdge==False or onlyOneMatchingEdge==None:
                                # delay until we can make sure which edge we are
                                if onlyOneMatchingEdge==False:
                                    self.debugPrint(lat, lon, "current point match more then on possible edge")
                                elif onlyOneMatchingEdge==None:
                                    self.debugPrint(lat, lon, "current point match none of the possible edge")
                                    return self.getEdgeIdOnPosForRoutingFallback(lat, lon, fromMouse, margin, track, speed)
                                    
                                if self.distanceFromCrossing>self.longestPossibleEdge:
                                    self.debugPrint(lat, lon, "distance from crossing longer then edge length  fallback")
                                    return self.getEdgeIdOnPosForRoutingFallback(lat, lon, fromMouse, margin, track, speed)
                            
                            elif onlyOneMatchingEdge==True:
#                                if self.currentEdgeCheckTrigger==1:
                                edge=self.checkEdge(lat, lon, track, speed, self.expectedNextEdge, fromMouse, margin)
                                if edge!=None:
                                    return self.currentEdgeData
#                                else:
#                                    self.debugPrint(lat, lon, "wait for on more gps data until decision")
#                                    self.currentEdgeCheckTrigger=self.currentEdgeCheckTrigger+1
                                
                        else:
                            edge=self.checkEdge(lat, lon, track, speed, self.expectedNextEdge, fromMouse, margin)
                            if edge!=None:
                                return self.currentEdgeData
                            
            if self.approachingRef==None:
                self.calcNextEdgeValues(lat, lon, track, speed)

            if self.possibleEdges==None:
                self.calcNextCrossingEdges(lat, lon)

            if self.approachingRef==None or self.possibleEdges==None or len(self.possibleEdges)==0:
#                self.debugPrint(lat, lon, "no next crossing possible")
                return self.currentEdgeData
                        
            self.calcCurrentBestMatchingEdge(lat, lon, track, nextEdgeOnRoute)

            # immediately check for any quick decisions on the next edge
            # else we have to wait till the next call
#            if self.expectedNextEdgeId!=None: 
#                if self.crossingPassed==True:
#                    if self.isQuickNextEdgeChoices(lat, lon, track, speed, self.expectedNextEdgeId):
#                        self.useEdge(lat, lon, track, speed, self.expectedNextEdge, False)

            return self.currentEdgeData
                
        return self.getEdgeIdOnPosForRoutingFallback(lat, lon, fromMouse, margin, track, speed)

    def getApproachingRef(self):
        return self.approachingRef, self.approachingRefPos
    
    def getDistanceToCrossing(self):
        return self.distanceToNextCrossing
    
    def debugPrint(self, lat, lon, text):
        if WITH_CROSSING_DEBUG==True:
            print("%f %f %s"%(lat, lon, text))
    
    def getEdgeIdOnPosWithTrack(self, lat, lon, track, margin, maxDistance):
        resultList=self.osmParserData.getEdgesAroundPointWithGeom(lat, lon, margin)  
        closestEdge=None
        minDistance=maxDistance
        minHeadingDiff=DECISION_HEADING_RANGE
        # dont match end and start points here to make sure we are ON the edge
        addStart=False
        addEnd=False
        
        currentEdgeData=None
        if self.currentEdgeData!=None:
            currentEdgeData=self.currentEdgeData
        
        for edge in resultList:
            _, _, _, _, _, _, _, _, _, streetInfo, coords=edge
            # if current still matches use it as default
            if currentEdgeData!=None and edge==currentEdgeData:
                return currentEdgeData
            
            streetTypeId, oneway, roundabout, tunnel, bridge=self.osmParserData.decodeStreetInfo2(streetInfo)
                    
            # dont match tunnels in driving mode
            if tunnel==1:
                continue
                                        
            lat1, lon1=coords[0]
            for lat2, lon2 in coords[1:]:
                onLine, distance, point=self.osmParserData.isMinimalDistanceOnLineBetweenPoints(lat, lon, lat1, lon1, lat2, lon2, maxDistance, addStart, addEnd)
                if onLine==True:
                    if oneway==0 or oneway==2:
                        heading=self.osmutils.headingDegrees(lat2, lon2, lat1, lon1)
                        headingDiff=self.osmutils.headingDiffAbsolute(track, heading)
                        if headingDiff<DECISION_HEADING_RANGE and headingDiff < minHeadingDiff:
                            if distance<minDistance:
                                minHeadingDiff=headingDiff
                                minDistance=distance
                                closestEdge=edge
                        
                    if oneway==0 or oneway==1 or roundabout==1:
                        heading=self.osmutils.headingDegrees(lat1, lon1, lat2, lon2)
                        headingDiff=self.osmutils.headingDiffAbsolute(track, heading)
                        if headingDiff<DECISION_HEADING_RANGE and headingDiff < minHeadingDiff:
                            if distance<minDistance:
                                minHeadingDiff=headingDiff
                                minDistance=distance
                                closestEdge=edge

                lat1=lat2
                lon1=lon2
                    
        return closestEdge
    
    # get all edges in the margin
    def getCurrentEdgesInMargin(self, lat, lon, track, margin):
        return self.osmParserData.getEdgesAroundPointWithGeom(lat, lon, margin)  
    
    def getCurrentBestMatchingEdge(self, lat, lon, track, possibleEdges, maxDistance):
        closestEdge=None
        minDistance=maxDistance
        minHeadingDiff=DECISION_HEADING_RANGE
        
        crossingRef=self.approachingRef
        for edge in possibleEdges:
            edgeId, _, endRef, _, _, _, _, _, _, _, coords=edge            
            headingCoords=coords
            if crossingRef==endRef:
                headingCoords=list()
                headingCoords.extend(coords)
                headingCoords.reverse()
            
            checkLength=0 
            lat1, lon1=headingCoords[0]
            for lat2, lon2 in headingCoords[1:]:
                checkLength=checkLength+self.osmutils.distance(lat1, lon1, lat2, lon2)
                    
                onLine, distance, _=self.osmParserData.isMinimalDistanceOnLineBetweenPoints(lat, lon, lat1, lon1, lat2, lon2, maxDistance)
                if onLine==True:
                    heading=self.osmutils.headingDegrees(lat1, lon1, lat2, lon2)
                    headingDiff=self.osmutils.headingDiffAbsolute(track, heading)
#                    print("%d %d"%(edgeId, headingDiff))
                    if headingDiff<DECISION_HEADING_RANGE and headingDiff < minHeadingDiff:
                        if distance<minDistance:
                            minHeadingDiff=headingDiff
                            minDistance=distance
                            closestEdge=edge

#                print(checkLength)
#                print(self.otherNearHeading)
                # dont check further the a specific distance from the crossing
                # if the heading diff are clear
                if self.otherNearHeading==False:
                    if checkLength>HEADING_CALC_LENGTH:
                        break

                lat1=lat2
                lon1=lon2
                    
        return closestEdge
