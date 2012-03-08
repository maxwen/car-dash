'''
Created on Feb 22, 2012

@author: maxl
'''

from osmparser.osmutils import OSMUtils
import time

WITH_CROSSING_DEBUG=False

MAXIMUM_DECISION_LENGTH=1000.0
NORMAL_EDGE_RANGE=30.0
CLOSE_EDGE_RANGE=10.0
DECISION_EDGE_RANGE=5.0
CLOSE_HEADING_RANGE=45
NORMAL_HEADING_RANGE=60
NO_CROSSING_SPEED=60
NEAR_CROSSING_LENGHT_MIN=NORMAL_EDGE_RANGE
PAST_CROSSING_LENGTH_MIN=15.0
CROSSING_CALC_LENHGT_MIN=NORMAL_EDGE_RANGE*4

class OSMRouting():
    def __init__(self, osmParserData):
        self.osmParserData=osmParserData
        self.osmutils=OSMUtils()
        self.currentPossibleEdgeList=list()
        self.expectedNextEdgeId=None
        self.expectedHeading=None
        self.crosingWithoutExpected=False
        self.checkExpectedEdge=False
        self.approachingRef=None
#        self.getPosTrigger=0
        self.currentEdge=None, None, None, None, None
        self.possibleEdges=None
        self.nearPossibleEdges=None
        self.edgeHeadings=None
        self.distanceToCrossing=None
        self.crossingPassed=False
        self.nearCrossing=False
        self.crossingReached=False
#        self.shortEdge=False
        self.nextEdgeLength=None
        self.otherNearHeading=False
        self.lastApproachingRef=None
        self.checkCurrentEdge=True
        self.distanceFromCrossing=None
#        self.stoppedOnEdge=False
#        self.currentEdgeCheckTrigger=0
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
            # TODO: we should only do this if lat, lon are between startRef
            # end endRef but then we need to check all refs
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
                print("calcApproachingRef: headingDiff=%d %d"%(headingDiff1, headingDiff2))
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

    def getNearNodes(self, lat, lon, country, maxDistance, margin, nodeType=None):  
        latRangeMax=lat+margin
        lonRangeMax=lon+margin*1.4
        latRangeMin=lat-margin
        lonRangeMin=lon-margin*1.4
        
        self.currentSearchBBox=[lonRangeMin, latRangeMin, lonRangeMax, latRangeMax]
        nodes=list()
#        print("%f %f"%(self.osmutils.distance(latRangeMin, lonRangeMin, latRangeMax, lonRangeMin),
#                       self.osmutils.distance(latRangeMin, lonRangeMin, latRangeMin, lonRangeMax)))
        
        allentries=self.osmParserData.getNodesInBBox(self.currentSearchBBox, country, nodeType)
        for x in allentries:
            refId, lat1, lon1, wayIdList, _=x
            if wayIdList==None:
                # node ref not way ref
                continue

            distance=self.osmutils.distance(lat, lon, lat1, lon1)
            if distance>maxDistance:
                continue
            nodes.append((refId, lat1, lon1, wayIdList))
#        print(len(nodes))

        return nodes
    
    def calcNextPossibleEdgesOnCrossing(self, crossingRef, currentEdgeOnRoute, lat, lon):
        possibleEdges=list()
        edgeHeadings=list()
        
        self.longestPossibleEdge=0
        # does not include currentEdgeOnRoute
        resultList=self.osmParserData.getDifferentEdgeEntryForStartOrEndPointWithCoords(crossingRef, currentEdgeOnRoute)
        if len(resultList)!=0: 
            _, country=self.osmParserData.getCountryOfRef(crossingRef) 
            for result in resultList:
                nextEdgeId, startRef, endRef, length, wayId, _, _, _, _, coords=result
                (wayId, _, _, streetTypeId, _, _, oneway, roundabout)=self.osmParserData.getWayEntryForIdAndCountry2(wayId, country)
       
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
                if self.osmParserData.isActiveTurnRestriction(currentEdgeOnRoute, nextEdgeId, self.approachingRef):
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
                possibleEdges.append((nextEdgeId, length))
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
            expectedNextEdgeId=possibleEdges[0][0]
            nextEdgeLength=possibleEdges[0][1]
            return expectedNextEdgeId, nextEdgeLength, otherNearHeading, nearPossibleEdges
            
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
                        nearPossibleEdges.append(possibleEdges[i][0])
                        otherNearHeading=True
                i=i+1
            expectedNextEdgeId=possibleEdges[minHeadingEntry][0]
            nextEdgeLength=possibleEdges[minHeadingEntry][1]
            return expectedNextEdgeId, nextEdgeLength, otherNearHeading, nearPossibleEdges

        return None, None, None, None
    
    # in routing mode we always set the nextEdgeIdOnRoute as the expected
    def setNextEdgeOnRouteAsExpected(self, track, possibleEdges, edgeHeadings, lat, lon, nextEdgeIdOnRoute):
        otherNearHeading=False
        nearPossibleEdges=list()
        if len(possibleEdges)==0:
            return None, None, otherNearHeading, nearPossibleEdges

        if len(possibleEdges)==1:
            expectedNextEdgeId=possibleEdges[0][0]
            nextEdgeLength=possibleEdges[0][1]
            return expectedNextEdgeId, nextEdgeLength, otherNearHeading, nearPossibleEdges
            
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
                        nearPossibleEdges.append(possibleEdges[i][0])
                        otherNearHeading=True
                i=i+1
            expectedNextEdgeId=possibleEdges[nextEdgeHeadingEntry][0]
            nextEdgeLength=possibleEdges[nextEdgeHeadingEntry][1]
            return expectedNextEdgeId, nextEdgeLength, otherNearHeading, nearPossibleEdges

        return None, None, None, None
    
    def checkEdgeDataForPos(self, lat, lon, edgeId, speed, maxDistance):
        edgeId, _, _, _, _, _, _, _, _, coords=self.osmParserData.getEdgeEntryForEdgeIdWithCoords(edgeId)
#        if length<self.getToCrossingCheckDistance(speed):
#            return True
                    
        return self.checkForPosOnEdgeId(lat, lon, coords, maxDistance)
    
    # still use track info if available to select a "good" edge
    def getEdgeIdOnPosForRoutingFallback(self, lat, lon, fromMouse, margin, track, speed, nextEdgeOnRoute):        
        self.cleanEdgeCalculations(True)

        # TODO: should be and fromMouse==False
        if track!=None:  
            start=time.time()  
            edgeId, ref, point=self.getEdgeIdOnPosWithTrack(lat, lon, track, margin, NORMAL_EDGE_RANGE)
            print("getEdgeIdOnPosWithTrack: %f"%(time.time()-start))
            if edgeId!=None:
                self.currentEdge=self.useNextEdge(lat, lon, track, speed, edgeId, True)
            else:
                self.currentEdge=None, None, None, None
            
            return self.currentEdge
            
        start=time.time()
        self.currentEdge=self.osmParserData.getEdgeIdOnPos(lat, lon, margin, NORMAL_EDGE_RANGE)
        print("getEdgeIdOnPos: %f"%(time.time()-start))
        return self.currentEdge
    
    def cleanEdgeCalculations(self, cleanLastApproachingRef):
        if cleanLastApproachingRef==False:
            self.lastApproachingRef=self.approachingRef
        else:
            self.lastApproachingRef=None
            
        self.approachingRef=None
        self.currentPossibleEdgeList.clear()
        self.expectedNextEdgeId=None
        self.possibleEdges=None
        self.distanceToCrossing=None
        self.crossingPassed=False
        self.crossingReached=False
#        self.shortEdge=False
        self.nextEdgeLength=None
        self.otherNearHeading=False
        self.checkCurrentEdge=True
        self.distanceFromCrossing=None
        self.nearCrossing=False
        self.nearPossibleEdges=None
#        self.stoppedOnEdge=False
#        self.currentEdgeCheckTrigger=0
        self.longestPossibleEdge=None

    # distance to crossing that we assume is near crossing
    # here we start calculating the expected edge
    # and check for quick next edge
    def getToCrossingCheckDistance(self, speed):
        # must not be to long else we may switch to a "quick"
        # next edge before the next pos check is correct 
        # on that edge
        if speed==0:
            return NEAR_CROSSING_LENGHT_MIN
        value=int(speed/3.6)
        if value < NEAR_CROSSING_LENGHT_MIN:
            return NEAR_CROSSING_LENGHT_MIN
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
    
    # assume that we get 1 gps signal per second
    # what is the maximal distance in m depending on speed
    # that we pass between the last and the next signal
#    def getPosDistanceForSpeed(self, speed):
#        if speed==0:
#            return NORMAL_EDGE_RANGE
#        value=int(speed/3.6)
#        if value < NORMAL_EDGE_RANGE:
#            return NORMAL_EDGE_RANGE
#        return value
    
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
            if distance > CROSSING_CALC_LENHGT_MIN:
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
    
    # TODO: maybe dont check every time
    def checkPosOnCurrentEdge(self, lat, lon, coords, maxDistance):
        return self.checkForPosOnEdgeId(lat, lon, coords, maxDistance)
        
    def calcNextCrossingEdges(self, edgeId, lat, lon):
        # check if approaching ref is valid
        if self.approachingRef!=None:
            self.debugPrint(lat, lon, "calc next crossing edges at %d"%self.approachingRef)
            self.currentPossibleEdgeList.clear()
            self.possibleEdges, self.edgeHeadings=self.calcNextPossibleEdgesOnCrossing(self.approachingRef, edgeId, lat, lon)
        
    def calcNextEdgeValues(self, lat, lon, edgeId, track, speed):
        edgeId, startRef, endRef, _, wayId, _, _, _, _, coords=self.osmParserData.getEdgeEntryForEdgeIdWithCoords(edgeId)

        # can be None if is not clear
        self.approachingRef=self.calcApproachingRef(lat, lon, startRef, endRef, coords, track, True)
        
        # check if approaching ref is valid
        # else current edge stays the same
        if self.approachingRef!=None:
            self.debugPrint(lat, lon, "approachingRef %d"%self.approachingRef)
            
            # TODO: shoud NO be self.approachingRef but nearest ref
            # usedLat and usedLon should be a temporary point on this edge
            _, country=self.osmParserData.getCountryOfRef(self.approachingRef)
            usedLat, usedLon=self.osmParserData.getCoordsWithRefAndCountry(self.approachingRef, country)
            self.currentEdge=edgeId, wayId, self.approachingRef, (usedLat, usedLon)
            
            distance=self.osmParserData.getDistanceFromPointToRef(lat, lon, self.approachingRef)
            self.distanceToCrossing=distance
            self.crossingPassed=False
            self.nearCrossing=False
            self.crossingReached=False
            
#            if length<self.getToCrossingCheckDistance(speed):
#                self.shortEdge=True
#            else:
#                self.shortEdge=False
        
    def useNextEdge(self, lat, lon, track, speed, nextEdgeId, cleanLastApproachingRef):
        self.cleanEdgeCalculations(cleanLastApproachingRef)
            
        # immediately calc next crossing to be available on the next call
        # else in case of a short edge we might miss the next crossing
        self.calcNextEdgeValues(lat, lon, nextEdgeId, track, speed)
        self.calcNextCrossingEdges(nextEdgeId, lat, lon)
        
        if self.approachingRef!=None:
            distance=self.osmParserData.getDistanceFromPointToRef(lat, lon, self.approachingRef)
            self.updateCrossingDistances(lat, lon, distance, speed)
            self.calcCurrentBestMatchingEdge(lat, lon, track, speed, distance, None)

        return self.currentEdge

    def isOnlyMatchingOnEdgeForDistance(self, lat, lon, speed, maxDistance):
        matchExpected=self.checkEdgeDataForPos(lat, lon, self.expectedNextEdgeId, speed, maxDistance)
        
        matchingCount=0
        for otherPossible in self.nearPossibleEdges:
            matchOther=self.checkEdgeDataForPos(lat, lon, otherPossible, speed, maxDistance)
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
    
    def isChangedApproachRef(self, lat, lon, startRef, endRef, track):
        if self.approachingRef!=None:
            approachingRef=self.calcApproachingRef(lat, lon, startRef, endRef, track, False)
            if approachingRef!=None and approachingRef!=self.approachingRef:
                return True
        
        return False
    
    def calcCurrentBestMatchingEdge(self, lat, lon, track, speed, distance, nextEdgeOnRoute):
#        if self.shortEdge==True or distance < self.getToCrossingCheckDistance(speed) or self.expectedNextEdgeId!=None or self.nearCrossing==True: 
        if self.expectedNextEdgeId!=None or self.nearCrossing==True: 
            self.debugPrint(lat, lon, "check possible edges - distance %d"%(distance))   
            if nextEdgeOnRoute!=None:
                expectedNextEdgeId, nextEdgeLength, otherNearHeading, nearPossibleEdges=self.setNextEdgeOnRouteAsExpected(track, self.possibleEdges, self.edgeHeadings, lat, lon, nextEdgeOnRoute)
            else:    
                expectedNextEdgeId, nextEdgeLength, otherNearHeading, nearPossibleEdges=self.getBestMatchingNextEdgeForHeading(track, self.possibleEdges, self.edgeHeadings, lat, lon)
            if expectedNextEdgeId!=None:
                self.debugPrint(lat, lon, "expected next edge %d"%(expectedNextEdgeId))   
                self.expectedNextEdgeId=expectedNextEdgeId
                self.nextEdgeLength=nextEdgeLength
                self.otherNearHeading=otherNearHeading
                self.nearPossibleEdges=nearPossibleEdges
       
    def checkEdge(self, lat, lon, track, speed, edgeId):
        # use a large maxDistance to make sure we match the
        # epected edge in most cases
        maxDistance=NORMAL_EDGE_RANGE
        if self.otherNearHeading==True:
            # except other near edges
            maxDistance=DECISION_EDGE_RANGE
            
        # check the current expected
        if not self.checkEdgeDataForPos(lat, lon, edgeId, speed, maxDistance):
            # we havnt confirmed the edge in the time - just use it
            # a wrong edge decision would be recognized by the next "lost edge" check
            if self.distanceFromCrossing>self.longestPossibleEdge:
                self.debugPrint(lat, lon, "distance from crossing longer then edge length  - use expected")
                return self.useNextEdge(lat, lon, track, speed, edgeId, False)
            
            # dont try other - hope that the self.expectedNextEdgeId has been set
            # correctly and stick to it
#            # try if a other possible edge matches better then the expected
#            otherEdgeId=self.getBestMatchingOtherEdgeForHeading(lat, lon, self.possibleEdges, self.edgeHeadings, self.expectedNextEdgeId, speed, track)
#            if otherEdgeId!=self.expectedNextEdgeId:
#                self.debugPrint(lat, lon, "next edge not confirmed - fallback to other possible")
#            else:
#                self.debugPrint(lat, lon, "next edge not confirmed - no better fallback found still use expected")
#                
#            return self.useNextEdge(lat, lon, track, speed, otherEdgeId, False)

        else:
            self.debugPrint(lat, lon, "pos on edge confirmed")
            return self.useNextEdge(lat, lon, track, speed, edgeId, False)

        # no decision possible
        return None, None, None, None, None
    
#    def updateCurrentEdgeForPos(self, lat, lon, coords):
#        maxDistance=NORMAL_EDGE_RANGE
#        lat1, lon1=coords[0]
#        for lat2, lon2 in coords[1:]:
#            onLine, distance, point=self.isMinimalDistanceOnLineBetweenPoints(lat, lon, lat1, lon1, lat2, lon2, maxDistance)
#            if onLine==True:
#                if distance<maxDistance:
#                    maxDistance=distance
#                    usedRefId=ref
#                    usedPoint=point
#                
#            lat1=lat2
#            lon1=lon2

    def getEdgeIdOnPosForRouting2(self, lat, lon, track, currentEdgeOnRoute, nextEdgeOnRoute, margin, fromMouse, speed):        
        if track==None:
            return self.getEdgeIdOnPosForRoutingFallback(lat, lon, fromMouse, margin, track, speed, nextEdgeOnRoute)

        if currentEdgeOnRoute!=None:
            self.debugPrint(lat, lon, "current edge=%d"%currentEdgeOnRoute)
        if nextEdgeOnRoute!=None:
            self.debugPrint(lat, lon, "next edge=%d"%nextEdgeOnRoute)
                
#        if speed==0:
#            self.stoppedOnEdge=True
#		else:
#			self.stoppedOnEdge=False
            
        # final fallback if anything goes wrong
        if self.distanceFromCrossing!=None and self.distanceFromCrossing>MAXIMUM_DECISION_LENGTH:
            self.debugPrint(lat, lon, "too far from crossing  - fallback")
            return self.getEdgeIdOnPosForRoutingFallback(lat, lon, fromMouse, margin, track, speed, nextEdgeOnRoute)

        if currentEdgeOnRoute!=None:
            # check if we are still on the expected edge
            # only used between crossingPassed and nearCrossing
            # use a relative large macDistance to compensate wrong
            # map data and/or gps failures
            
            # TODO: if a expectedNextEdgeId or checkCurrentEdge is set we will 
            # not leave the edge until the MAXIMUM_DECISION_LENGTH is reached
            if self.expectedNextEdgeId==None and self.checkCurrentEdge==True:
                currentEdgeOnRoute, _, _, _, _, _, _, _, _, coords=self.osmParserData.getEdgeEntryForEdgeIdWithCoords(currentEdgeOnRoute)    
                if not self.checkPosOnCurrentEdge(lat, lon, coords, NORMAL_EDGE_RANGE):
                    self.debugPrint(lat, lon, "lost current edge")
                    return self.getEdgeIdOnPosForRoutingFallback(lat, lon, fromMouse, margin, track, speed, nextEdgeOnRoute)

                # TODO: must update self.currentEdge with actual
                # ref and point to allow distance calculation to work
                
                # TODO: if we stop and change the direction
                # approaching ref should be recalculated
#                if self.stoppedOnEdge==True:
#                    self.stoppedOnEdge=False
#                    if self.isChangedApproachRef(lat, lon, startRef, endRef, track):
#                        self.debugPrint(lat, lon, "approaching ref changed after stop")
#                        return self.useNextEdge(lat, lon, track, speed, currentEdgeOnRoute, True)

            if self.expectedNextEdgeId!=None:
                distance=self.osmParserData.getDistanceFromPointToRef(lat, lon, self.approachingRef)
                self.updateCrossingDistances(lat, lon, distance, speed)
                
                if self.crossingPassed==True or self.nearCrossing==True:
                    self.checkCurrentEdge=False
                    
                    if self.crossingReached==True:
                        if self.isQuickNextEdgeChoices(lat, lon, track, speed, self.expectedNextEdgeId):
                            return self.useNextEdge(lat, lon, track, speed, self.expectedNextEdgeId, False)
                                            
                    if self.crossingPassed==True:
#                        if self.isQuickNextEdgeChoices(lat, lon, track, speed, self.expectedNextEdgeId):
#                            return self.useNextEdge(lat, lon, track, speed, self.expectedNextEdgeId, False)

                        if self.otherNearHeading==True and self.nearPossibleEdges!=None:
                            onlyOneMatchingEdge=self.isOnlyMatchingOnEdge(lat, lon, speed)
                            # can also be None
                            if onlyOneMatchingEdge==False or onlyOneMatchingEdge==None:
                                # delay until we can make sure which edge we are
                                if onlyOneMatchingEdge==False:
                                    self.debugPrint(lat, lon, "current point match more then on possible edge")
                                elif onlyOneMatchingEdge==None:
                                    self.debugPrint(lat, lon, "current point match none of the possible edge")
                                    
                                if self.distanceFromCrossing>self.longestPossibleEdge:
                                    self.debugPrint(lat, lon, "distance from crossing longer then edge length  - use expected")
                                    return self.useNextEdge(lat, lon, track, speed, self.expectedNextEdgeId, False)
                            
                            elif onlyOneMatchingEdge==True:
                                edge=self.checkEdge(lat, lon, track, speed, self.expectedNextEdgeId)
                                if edge[0]!=None:
                                    return self.currentEdge
                                
                        else:
                            edge=self.checkEdge(lat, lon, track, speed, self.expectedNextEdgeId)
                            if edge[0]!=None:
                                return self.currentEdge
                                
            if self.approachingRef==None:
                self.calcNextEdgeValues(lat, lon, currentEdgeOnRoute, track, speed)

            if self.possibleEdges==None:
                self.calcNextCrossingEdges(currentEdgeOnRoute, lat, lon)

            if self.possibleEdges==None or len(self.possibleEdges)==0:
#                self.debugPrint(lat, lon, "no next crossing possible")
                return self.currentEdge
            
            distance=self.osmParserData.getDistanceFromPointToRef(lat, lon, self.approachingRef)
            self.updateCrossingDistances(lat, lon, distance, speed)
            
            self.calcCurrentBestMatchingEdge(lat, lon, track, speed, distance, nextEdgeOnRoute)

            # immediately check for any quick decisions on the next edge
            # else we have to wait till the next call
            if self.expectedNextEdgeId!=None: 
                if self.crossingReached==True:
#                if self.crossingPassed==True or self.nearCrossing==True:
                    if self.isQuickNextEdgeChoices(lat, lon, track, speed, self.expectedNextEdgeId):
                        return self.useNextEdge(lat, lon, track, speed, self.expectedNextEdgeId, False)

            return self.currentEdge
                
        return self.getEdgeIdOnPosForRoutingFallback(lat, lon, fromMouse, margin, track, speed, nextEdgeOnRoute)

    def getApproachingRef(self):
        return self.approachingRef
    
    def debugPrint(self, lat, lon, text):
        if WITH_CROSSING_DEBUG==True:
            print("%f %f %s"%(lat, lon, text))

#    def getEdgeIdOnPosWithTrack(self, lat, lon, track, margin, maxDistance):
#        maxNodeDistance=500.0
# 
#        refCountry=self.osmParserData.getCountryOfPos(lat, lon)
#        if refCountry==None:
#            return None, None, None
#
#        possibleWayList=list()
#        nodes=self.osmParserData.getNearNodes(lat, lon, refCountry, maxNodeDistance, margin)
#        for refId, _, _, wayIdList in nodes:           
#            for wayId in wayIdList:
#                (_, _, refs, _, _, _, oneway, _)=self.osmParserData.getWayEntryForIdAndCountry2(wayId, refCountry)
#                # use the refs before and after to check
#                index=refs.index(refId)
#                refList=list()
#                if index==0:
#                    refList.append(refId)
#                    refList.append(refs[index+1])
#                elif index==len(refs)-1:
#                    refList.append(refs[-1])
#                    refList.append(refId)
#                else:
#                    refList.append(refs[index-1])
#                    refList.append(refId)
#                    refList.append(refs[index+1])
#                                    
#                lastRef=refList[0]
#                for ref in refList[1:]:
#                    onLine=self.osmParserData.isOnLineBetweenRefs(lat, lon, ref, lastRef, maxDistance)
#                    if onLine==True:
#                        if not (wayId, refs, ref, oneway) in possibleWayList:
#                            possibleWayList.append((wayId, refs, ref, oneway))
#                        # one for every way is enough
#                        break
#                    lastRef=ref
#                        
#        closestEdgeId=None
#        closestPoint=None
#        closestRef=None
#        
#        if len(possibleWayList)!=0:
##            print(possibleWayList)
#            minDistance=maxDistance
#            doneEdges=list()
#            for wayId, refs, ref, oneway in possibleWayList:
#                resultList=self.osmParserData.getEdgeEntryForWayIdWithCoords(wayId)
#
#                for edge in resultList:
#                    edgeId, startRef, endRef, _, wayId, _, _, _, _, coords=edge
#                    if edgeId in doneEdges:
#                        continue
#                    doneEdges.append(edgeId)
#                    edgeRefList=self.osmParserData.getRefListSubset(refs, startRef, endRef)
#                                        
#                    if ref in edgeRefList:
#                        lat1, lon1=coords[0]
#                        for lat2, lon2 in coords[1:]:
#                            onLine, distance, point=self.osmParserData.isMinimalDistanceOnLineBetweenPoints(lat, lon, lat1, lon1, lat2, lon2, maxDistance)
#                            if onLine==True:
#                                if oneway==0 or oneway==2:
#                                    heading=self.osmutils.headingDegrees(lat2, lon2, lat1, lon1)
#                                    headingDiff=self.osmutils.headingDiffAbsolute(track, heading)
#                                    if headingDiff<CLOSE_HEADING_RANGE:
#                                        if distance<minDistance:
#                                            minDistance=distance
#                                            closestEdgeId=edgeId
#                                            closestPoint=point
#                                            closestRef=ref
#                                
#                                if oneway==0 or oneway==1:
#                                    heading=self.osmutils.headingDegrees(lat1, lon1, lat2, lon2)
#                                    headingDiff=self.osmutils.headingDiffAbsolute(track, heading)
#                                    if headingDiff<CLOSE_HEADING_RANGE:
#                                        if distance<minDistance:
#                                            minDistance=distance
#                                            closestEdgeId=edgeId
#                                            closestPoint=point
#                                            closestRef=ref
#
#                            lat1=lat2
#                            lon1=lon2
#                        
#        return closestEdgeId, closestRef, closestPoint

    def getEdgeIdOnPosWithTrack(self, lat, lon, track, margin, maxDistance):
        maxNodeDistance=500.0                   
        closestEdgeId=None
        closestPoint=None
        closestRef=None

        refCountry=self.osmParserData.getCountryOfPos(lat, lon)
        if refCountry==None:
            return None, None, None, None, None

        doneWays=list()
        minDistance=maxDistance

        nodes=self.osmParserData.getNearNodes(lat, lon, refCountry, maxNodeDistance, margin)
        for refId, _, _, wayIdList in nodes:           
            for wayId in wayIdList:
                if wayId in doneWays:
                    continue
                doneWays.append(wayId)
                
                doneEdges=list()
                (_, _, refs, _, _, _, oneway, _)=self.osmParserData.getWayEntryForIdAndCountry2(wayId, refCountry)
                resultList=self.osmParserData.getEdgeEntryForWayIdWithCoords(wayId)

                for edge in resultList:
                    edgeId, startRef, endRef, _, _, _, _, _, _, coords=edge
                    if edgeId in doneEdges:
                        continue
                    doneEdges.append(edgeId)
                    edgeRefList=self.osmParserData.getRefListSubset(refs, startRef, endRef)
                                        
                    if refId in edgeRefList:
                        lat1, lon1=coords[0]
                        for lat2, lon2 in coords[1:]:
                            onLine, distance, point=self.osmParserData.isMinimalDistanceOnLineBetweenPoints(lat, lon, lat1, lon1, lat2, lon2, maxDistance)
                            if onLine==True:
                                if oneway==0 or oneway==2:
                                    heading=self.osmutils.headingDegrees(lat2, lon2, lat1, lon1)
                                    headingDiff=self.osmutils.headingDiffAbsolute(track, heading)
                                    if headingDiff<CLOSE_HEADING_RANGE:
                                        if distance<minDistance:
                                            minDistance=distance
                                            closestEdgeId=edgeId
                                            closestPoint=point
                                            closestRef=refId
                                
                                if oneway==0 or oneway==1:
                                    heading=self.osmutils.headingDegrees(lat1, lon1, lat2, lon2)
                                    headingDiff=self.osmutils.headingDiffAbsolute(track, heading)
                                    if headingDiff<CLOSE_HEADING_RANGE:
                                        if distance<minDistance:
                                            minDistance=distance
                                            closestEdgeId=edgeId
                                            closestPoint=point
                                            closestRef=refId

                            lat1=lat2
                            lon1=lon2
                        
        return closestEdgeId, closestRef, closestPoint