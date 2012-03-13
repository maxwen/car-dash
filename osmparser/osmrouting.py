'''
Created on Feb 22, 2012

@author: maxl
'''

from osmparser.osmutils import OSMUtils
import time

WITH_CROSSING_DEBUG=True

MAXIMUM_DECISION_LENGTH=1000.0
NORMAL_EDGE_RANGE=30.0
CLOSE_EDGE_RANGE=20.0
DECISION_EDGE_RANGE=10.0
CLOSE_HEADING_RANGE=45
NORMAL_HEADING_RANGE=60
NO_CROSSING_SPEED=60
NEAR_CROSSING_LENGTH_MIN=NORMAL_EDGE_RANGE
PAST_CROSSING_LENGTH_MIN=15.0
CROSSING_CALC_LENGTH_MIN=NORMAL_EDGE_RANGE*2

class OSMRouting():
    def __init__(self, osmParserData):
        self.osmParserData=osmParserData
        self.osmutils=OSMUtils()
        self.currentPossibleEdgeList=list()
        self.expectedNextEdgeId=None
        self.expectedNextEdge=None
        self.expectedHeading=None
        self.crosingWithoutExpected=False
        self.checkExpectedEdge=False
        self.approachingRef=None
        self.currentEdge=None, None
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
        self.currentEdgeCheckTrigger=0
        self.longestPossibleEdge=None
        
    def getCurrentSearchEdgeList(self):
        return self.currentPossibleEdgeList
    
    def getExpectedNextEdge(self):
        return self.expectedNextEdgeId
    
    def calcApproachingRef(self, lat, lon, startRef, endRef, coords, track, useLastValue):
        # find the ref we are aproaching based on track
        # since we ony check when coming to a crossing 
        # but not on leaving
        ref=None
        if useLastValue==False or self.lastApproachingRef==None:
            # f no previous value is available use close range
            onEdge=self.checkEdgeDataForPosWithCoords(lat, lon, coords, DECISION_EDGE_RANGE)
            if onEdge==False:
                self.debugPrint(lat, lon, "calcApproachingRef: not on edge")
                return ref
            
            lat1, lon1=coords[0]
            heading1=self.osmutils.headingDegrees(lat, lon, lat1, lon1)
    
            lat2, lon2=coords[-1]
            heading2=self.osmutils.headingDegrees(lat, lon, lat2, lon2)
            
            headingDiff1=self.osmutils.headingDiffAbsolute(track, heading1)
            headingDiff2=self.osmutils.headingDiffAbsolute(track, heading2)
            
            if headingDiff1<CLOSE_HEADING_RANGE or headingDiff2<CLOSE_HEADING_RANGE:
                if headingDiff1<headingDiff2:
                    ref=startRef
                else:
                    ref=endRef
            else:
                self.debugPrint(lat, lon, "calcApproachingRef: headingDiff=%d %d"%(headingDiff1, headingDiff2))
        else:
            if self.lastApproachingRef==startRef:
                ref=endRef
            elif self.lastApproachingRef==endRef:
                ref=startRef
                            
        return ref
    
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
        resultList=self.osmParserData.getDifferentEdgeEntryForStartOrEndPointWithCoords(crossingRef, self.currentEdge[0])
        if len(resultList)!=0: 
            for edge in resultList:
                nextEdgeId, startRef, endRef, length, _, _, _, _, _, streetInfo, coords=edge
                streetTypeId, oneway, roundabout=self.osmParserData.decodeStreetInfo(streetInfo)
       
                # ignore certain types for crossing expectations
                #if streetTypeId==0 or streetTypeId==1 or streetTypeId==13 or streetTypeId==14:
                if streetTypeId==13:
                    # street type service
                    continue
            
                # filter out onways with wrong start
                if oneway!=0:
                    if not self.osmParserData.isValidOnewayEnter(oneway, crossingRef, startRef, endRef):
                        continue

                # left turns in roundabouts
                if roundabout!=0:
                    if not crossingRef==startRef:
                        continue
                    
                # TODO: check turn restrictions but that takes time
                if self.osmParserData.isActiveTurnRestriction(self.currentEdge[0], nextEdgeId, self.approachingRef):
                    continue
                        
                # filter out access limited streets
#                if "access" in tags:
#                    continue
                
                self.currentPossibleEdgeList.append(nextEdgeId)
                # TODO heading is calculated only from crossinfRef
                # but e.g. in a curve the heading can change depending
                # on the position
                if crossingRef==endRef:
                    coords.reverse()
                heading=self.osmParserData.getHeadingForPoints(coords)

                edgeHeadings.append(heading)
                possibleEdges.append(edge)
                if length>self.longestPossibleEdge:
                    self.longestPossibleEdge=length

        self.debugPrint(lat, lon, possibleEdges)
        return possibleEdges, edgeHeadings
    
    def getBestMatchingNextEdgeForHeading(self, track, possibleEdges, edgeHeadings, lat, lon):
        otherNearHeading=False
        nearPossibleEdges=list()
        if len(possibleEdges)==0:
            return None, None, otherNearHeading, nearPossibleEdges

        if len(possibleEdges)==1:
            expectedNextEdge=possibleEdges[0]
            nextEdgeLength=expectedNextEdge[3]
            return expectedNextEdge, nextEdgeLength, otherNearHeading, nearPossibleEdges
            
        minHeadingDiff=360
        minHeadingEntry=None
        i=0
        for heading in edgeHeadings:
            if heading!=None:
                # use best matching heading
                headingDiff=self.osmutils.headingDiffAbsolute(track, heading)
                if headingDiff < minHeadingDiff:
                    minHeadingDiff=headingDiff
                    minHeadingEntry=i
                
            i=i+1
        self.debugPrint(lat, lon, "minHeadingDiff=%f"%minHeadingDiff)
        if minHeadingEntry!=None:
            i=0
            for heading in edgeHeadings:
                if heading!=None and heading!=edgeHeadings[minHeadingEntry]:
                    headingDiff=self.osmutils.headingDiffAbsolute(edgeHeadings[minHeadingEntry], heading)
#                    print(headingDiff)
                    if headingDiff<CLOSE_HEADING_RANGE:
                        # next best heading is near to best matching
                        self.debugPrint(lat, lon, "heading diff < %d %f"%(CLOSE_HEADING_RANGE, headingDiff))
                        nearPossibleEdges.append(possibleEdges[i])
                        otherNearHeading=True
                i=i+1
            expectedNextEdge=possibleEdges[minHeadingEntry]
            nextEdgeLength=expectedNextEdge[3]
            return expectedNextEdge, nextEdgeLength, otherNearHeading, nearPossibleEdges

        return None, None, None, None
    
    # in routing mode we always set the nextEdgeIdOnRoute as the expected
    def setNextEdgeOnRouteAsExpected(self, track, possibleEdges, edgeHeadings, lat, lon, nextEdgeIdOnRoute):
        otherNearHeading=False
        nearPossibleEdges=list()
        if len(possibleEdges)==0:
            return None, None, otherNearHeading, nearPossibleEdges

        if len(possibleEdges)==1:
            expectedNextEdge=possibleEdges[0]
            nextEdgeLength=expectedNextEdge[3]
            return expectedNextEdge, nextEdgeLength, otherNearHeading, nearPossibleEdges
            
        nextEdgeHeadingEntry=None
        i=0
        for possibleEdge in possibleEdges:
            if possibleEdge[0]==nextEdgeIdOnRoute:
                nextEdgeHeadingEntry=i
                break
            i=i+1
            
        if nextEdgeHeadingEntry!=None:
            i=0
            for heading in edgeHeadings:
                if heading!=None and heading!=edgeHeadings[nextEdgeHeadingEntry]:
                    headingDiff=self.osmutils.headingDiffAbsolute(edgeHeadings[nextEdgeHeadingEntry], heading)
#                    print(headingDiff)
                    if headingDiff<CLOSE_HEADING_RANGE:
                        # next best heading is near to best matching
                        self.debugPrint(lat, lon, "heading diff < %d %f"%(CLOSE_HEADING_RANGE, headingDiff))
                        nearPossibleEdges.append(possibleEdges[i])
                        otherNearHeading=True
                i=i+1
            expectedNextEdge=possibleEdges[nextEdgeHeadingEntry]
            nextEdgeLength=expectedNextEdge[3]
            return expectedNextEdge, nextEdgeLength, otherNearHeading, nearPossibleEdges

        return None, None, None, None
    
    def checkEdgeDataForPos(self, lat, lon, edge, maxDistance):
        coords=edge[10]
        return self.checkForPosOnEdgeId(lat, lon, coords, maxDistance)

    def checkEdgeDataForPosWithCoords(self, lat, lon, coords, maxDistance):
        return self.checkForPosOnEdgeId(lat, lon, coords, maxDistance)
    
    # still use track info if available to select a "good" edge
    def getEdgeIdOnPosForRoutingFallback(self, lat, lon, fromMouse, margin, track, speed):        
        # TODO: should be and fromMouse==False
        if track!=None:  
            # use close range if no current edge is available
            edge=self.getEdgeIdOnPosWithTrack(lat, lon, track, margin, DECISION_EDGE_RANGE)
            if edge!=None:
                if self.currentEdgeData==None:
                    self.useEdge(lat, lon, track, speed, edge, True)
                elif self.currentEdgeData!=edge:
                    self.useEdge(lat, lon, track, speed, edge, True)
            else:
                self.currentEdge=None, None
                self.currentEdgeData=None
            
            return self.currentEdge
            
        self.cleanEdgeCalculations(True)
        self.currentEdge=None, None
        self.currentEdgeData=None
        
        edge=self.osmParserData.getEdgeOnPos(lat, lon, margin, DECISION_EDGE_RANGE)
        if edge!=None:
            return edge[0], edge[4]

        return None, None
    
    def cleanCurrentEdge(self):
        self.currentEdge=None, None
        self.currentEdgeData=None
        
    def cleanEdgeCalculations(self, cleanLastApproachingRef):
        if cleanLastApproachingRef==False:
            self.lastApproachingRef=self.approachingRef
        else:
            self.lastApproachingRef=None
            
        self.approachingRef=None
        self.currentPossibleEdgeList.clear()
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
        self.currentEdgeCheckTrigger=0
        self.longestPossibleEdge=None

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
        
        # past crossing
        crossingRange=self.getFromCrossingCheckDistance(speed)
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
            self.currentPossibleEdgeList.clear()
            self.possibleEdges, self.edgeHeadings=self.calcNextPossibleEdgesOnCrossing(self.approachingRef, lat, lon)
        
    def calcNextEdgeValues(self, lat, lon, track, speed):
        edgeId, startRef, endRef, _, wayId, _, _, _, _, _, coords=self.currentEdgeData
        
        # can be None if is not clear
        self.approachingRef=self.calcApproachingRef(lat, lon, startRef, endRef, coords, track, True)
        
        # check if approaching ref is valid
        if self.approachingRef!=None:
            self.debugPrint(lat, lon, "approachingRef %d"%self.approachingRef)
            
            distance=self.osmParserData.getDistanceFromPointToRef(lat, lon, self.approachingRef)
            self.distanceToCrossing=distance
            self.crossingPassed=False
            self.nearCrossing=False
            self.crossingReached=False
        
    def useEdge(self, lat, lon, track, speed, edge, cleanLastApproachingRef):
        self.cleanEdgeCalculations(cleanLastApproachingRef)
            
        self.currentEdge=edge[0], edge[4]
        self.currentEdgeData=edge
        
        # immediately calc next crossing to be available on the next call
        # else in case of a short edge we might miss the next crossing
        self.calcNextEdgeValues(lat, lon, track, speed)
        
        if self.approachingRef!=None:
            self.calcNextCrossingEdges(lat, lon)
            distance=self.osmParserData.getDistanceFromPointToRef(lat, lon, self.approachingRef)
            self.updateCrossingDistances(lat, lon, distance, speed)
            self.calcCurrentBestMatchingEdge(lat, lon, track, speed, distance, None)

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
        approachingRef=self.calcApproachingRef(lat, lon, startRef, endRef, coords, track, False)
        if approachingRef!=self.approachingRef:
            return True, approachingRef
            
        return False, approachingRef
    
    def calcCurrentBestMatchingEdge(self, lat, lon, track, speed, distance, nextEdgeOnRoute):
        if self.expectedNextEdgeId!=None or self.nearCrossing==True: 
            self.debugPrint(lat, lon, "check possible edges - distance %d"%(distance))   
            if nextEdgeOnRoute!=None:
                expectedNextEdge, nextEdgeLength, otherNearHeading, nearPossibleEdges=self.setNextEdgeOnRouteAsExpected(track, self.possibleEdges, self.edgeHeadings, lat, lon, nextEdgeOnRoute)
            else:    
                expectedNextEdge, nextEdgeLength, otherNearHeading, nearPossibleEdges=self.getBestMatchingNextEdgeForHeading(track, self.possibleEdges, self.edgeHeadings, lat, lon)
            if expectedNextEdge!=None:
                self.debugPrint(lat, lon, "expected next edge %d %d"%(expectedNextEdge[0], nextEdgeLength))   
                self.expectedNextEdgeId=expectedNextEdge[0]
                self.expectedNextEdge=expectedNextEdge
                self.nextEdgeLength=nextEdgeLength
                self.otherNearHeading=otherNearHeading
                self.nearPossibleEdges=nearPossibleEdges
       
    def checkEdge(self, lat, lon, track, speed, edge, fromMouse, margin):
        # use a large maxDistance to make sure we match the
        # epected edge in most cases
        maxDistance=NORMAL_EDGE_RANGE
        if self.otherNearHeading==True:
            # except other near edges
            maxDistance=DECISION_EDGE_RANGE
            
        # check the current expected
        if not self.checkEdgeDataForPos(lat, lon, edge, maxDistance):
            if self.distanceFromCrossing>self.nextEdgeLength:
                self.debugPrint(lat, lon, "distance from crossing longer then edge length  fallback")
                return self.getEdgeIdOnPosForRoutingFallback(lat, lon, fromMouse, margin, track, speed)
            
        else:
            self.debugPrint(lat, lon, "pos on edge confirmed")
            self.useEdge(lat, lon, track, speed, edge, False)
            return self.currentEdge

        # no decision possible
        return None, None

    def getEdgeIdOnPosForRouting(self, lat, lon, track, nextEdgeOnRoute, margin, fromMouse, speed):        
        if track==None:
            return self.getEdgeIdOnPosForRoutingFallback(lat, lon, fromMouse, margin, track, speed)

        if self.currentEdgeData!=None:
            self.debugPrint(lat, lon, "current edge=%d"%self.currentEdgeData[0])
        if nextEdgeOnRoute!=None:
            self.debugPrint(lat, lon, "next edge=%d"%nextEdgeOnRoute)
            
        if self.currentEdgeData!=None:
            if self.approachingRef!=None:
                distance=self.osmParserData.getDistanceFromPointToRef(lat, lon, self.approachingRef)
                self.updateCrossingDistances(lat, lon, distance, speed)
            
            # check if we turned on the edge
            if (self.nearCrossing==False or self.approachingRef==None) and speed<30:
                changed, newApproachingRef=self.isChangedApproachingRef(lat, lon, track)
                if changed==True:
                    # can still be None
                    self.debugPrint(lat, lon, "approaching ref changed")
                    self.useEdge(lat, lon, track, speed, self.currentEdgeData, True)
                    return self.currentEdge
                
            # check if we are still on the expected edge
            # only used between crossingPassed and nearCrossing            
            if self.nearCrossing==False:
                self.getEdgeIdOnPosForRoutingFallback(lat, lon, fromMouse, margin, track, speed)                
                return self.currentEdge 

            if self.expectedNextEdgeId!=None:                
                if self.crossingPassed==True or self.crossingReached==True:                    
                    if self.crossingReached==True:
                        if self.isQuickNextEdgeChoices(lat, lon, track, speed, self.expectedNextEdgeId):
                            self.useEdge(lat, lon, track, speed, self.expectedNextEdge, False)
                            return self.currentEdge
                                        
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
                                    
                                if self.distanceFromCrossing>self.nextEdgeLength:
                                    self.debugPrint(lat, lon, "distance from crossing longer then edge length  fallback")
                                    return self.getEdgeIdOnPosForRoutingFallback(lat, lon, fromMouse, margin, track, speed)
                            
                            elif onlyOneMatchingEdge==True:
                                if self.currentEdgeCheckTrigger==1:
                                    edge=self.checkEdge(lat, lon, track, speed, self.expectedNextEdge, fromMouse, margin)
                                    if edge[0]!=None:
                                        return self.currentEdge
                                else:
                                    # TODO: delay for one more gps signal
                                    # test if this has unwanted side effects
                                    self.debugPrint(lat, lon, "wait for on more gps data until decision")
                                    self.currentEdgeCheckTrigger=self.currentEdgeCheckTrigger+1
                                
                        else:
                            edge=self.checkEdge(lat, lon, track, speed, self.expectedNextEdge, fromMouse, margin)
                            if edge[0]!=None:
                                return self.currentEdge
                            
            if self.approachingRef==None:
                self.calcNextEdgeValues(lat, lon, track, speed)

            if self.possibleEdges==None:
                self.calcNextCrossingEdges(lat, lon)

            if self.possibleEdges==None or len(self.possibleEdges)==0:
#                self.debugPrint(lat, lon, "no next crossing possible")
                return self.currentEdge
                        
            self.calcCurrentBestMatchingEdge(lat, lon, track, speed, distance, nextEdgeOnRoute)

            # immediately check for any quick decisions on the next edge
            # else we have to wait till the next call
            if self.expectedNextEdgeId!=None: 
                if self.crossingReached==True:
                    if self.isQuickNextEdgeChoices(lat, lon, track, speed, self.expectedNextEdgeId):
                        self.useEdge(lat, lon, track, speed, self.expectedNextEdge, False)

            return self.currentEdge
                
        return self.getEdgeIdOnPosForRoutingFallback(lat, lon, fromMouse, margin, track, speed)

    def getApproachingRef(self):
        return self.approachingRef
    
    def debugPrint(self, lat, lon, text):
        if WITH_CROSSING_DEBUG==True:
            print("%f %f %s"%(lat, lon, text))
    
    def getEdgeIdOnPosWithTrack(self, lat, lon, track, margin, maxDistance):
        resultList=self.osmParserData.getEdgesInBboxWithGeom(lat, lon, margin)  
        closestEdge=None
        minDistance=maxDistance
        minHeadingDiff=CLOSE_HEADING_RANGE
        
        currentEdgeData=None
        if self.currentEdgeData!=None:
            currentEdgeData=self.currentEdgeData
            
        for edge in resultList:
            _, _, _, _, _, _, _, _, _, streetInfo, coords=edge
            # if current still matches use it as default
            if currentEdgeData!=None and edge==currentEdgeData:
                return currentEdgeData
            
            streetTypeId, oneway, roundabout=self.osmParserData.decodeStreetInfo(streetInfo)
                                                
            lat1, lon1=coords[0]
            for lat2, lon2 in coords[1:]:
                onLine, distance, point=self.osmParserData.isMinimalDistanceOnLineBetweenPoints(lat, lon, lat1, lon1, lat2, lon2, maxDistance)
                if onLine==True:
                    if oneway==0 or oneway==2:
                        heading=self.osmutils.headingDegrees(lat2, lon2, lat1, lon1)
                        headingDiff=self.osmutils.headingDiffAbsolute(track, heading)
                        if headingDiff<CLOSE_HEADING_RANGE and headingDiff < minHeadingDiff:
                            if distance<minDistance:
                                minHeadingDiff=headingDiff
                                minDistance=distance
                                closestEdge=edge
                        
                    if oneway==0 or oneway==1 or roundabout==1:
                        heading=self.osmutils.headingDegrees(lat1, lon1, lat2, lon2)
                        headingDiff=self.osmutils.headingDiffAbsolute(track, heading)
                        if headingDiff<CLOSE_HEADING_RANGE and headingDiff < minHeadingDiff:
                            if distance<minDistance:
                                minHeadingDiff=headingDiff
                                minDistance=distance
                                closestEdge=edge

                lat1=lat2
                lon1=lon2
                    
        return closestEdge