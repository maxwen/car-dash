'''
Created on Feb 22, 2012

@author: maxl
'''

from osmparser.osmutils import OSMUtils
import time
from datetime import datetime

WITH_CROSSING_DEBUG=True

MAXIMUM_DECISION_LENGTH=1000.0
NORMAL_EDGE_RANGE=30.0
CLOSE_EDGE_RANGE=10.0
DECISION_EDGE_RANGE=5.0
CLOSE_HEADING_RANGE=45
NORMAL_HEADING_RANGE=60
HEADING_CALC_LENGTH=20.0
NO_CROSSING_SPEED=60
NEAR_CROSSING_LENGHT_MIN=NORMAL_EDGE_RANGE
PAST_CROSSING_LENGTH_MIN=15.0
CROSSING_CALC_LENHGT_MIN=NORMAL_EDGE_RANGE*4

class OSMRouting():
    def __init__(self, osmParserData, trackLog=None):
        self.osmParserData=osmParserData
        self.osmutils=OSMUtils()
        self.trackLog=trackLog
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
        self.shortEdge=False
        self.nextEdgeLength=None
        self.otherNearHeading=False
        self.lastApproachingRef=None
        self.checkCurrentEdge=True
        self.distanceFromCrossing=None
        self.stoppedOnEdge=False
        self.currentEdgeCheckTrigger=0
        self.longestPossibleEdge=None
        
    def getCurrentSearchEdgeList(self):
        return self.currentPossibleEdgeList
    
    def getExpectedNextEdge(self):
        return self.expectedNextEdgeId
    
    def calcApproachingRef(self, lat, lon, startRef, endRef, track, useLastValue):
        # find the ref we are aproaching based on track
        # since we ony check when coming to a crossing 
        # but not on leaving
        ref=None
        if useLastValue==False or self.lastApproachingRef==None:
            _, country=self.osmParserData.getCountryOfRef(startRef)
            resultList=self.osmParserData.getRefEntryForIdAndCountry(startRef, country)
            _, lat1, lon1, _, _=resultList[0]
            heading1=self.osmutils.headingDegrees(lat, lon, lat1, lon1)
    
            _, country=self.osmParserData.getCountryOfRef(endRef)
            resultList=self.osmParserData.getRefEntryForIdAndCountry(endRef, country)
            _, lat1, lon1, _, _=resultList[0]
            heading2=self.osmutils.headingDegrees(lat, lon, lat1, lon1)
            
            headingDiff1=self.osmutils.headingDiffAbsolute(track, heading1)
            headingDiff2=self.osmutils.headingDiffAbsolute(track, heading2)
            
            if headingDiff1<CLOSE_HEADING_RANGE or headingDiff2<CLOSE_HEADING_RANGE:
                if headingDiff1<headingDiff2:
                    ref=startRef
                else:
                    ref=endRef
            else:
                print("calcApproachingRef: headinDiff=%d %d"%(headingDiff1, headingDiff2))
        else:
            if self.lastApproachingRef==startRef:
                ref=endRef
            elif self.lastApproachingRef==endRef:
                ref=startRef
                            
        return ref
    
#    def getEdgeIdOnPosForRoutingWOTrack(self, lat, lon, track, currentEdgeOnRoute, nextEdgeOnRoute, margin, fromMouse):        
#        usedEdgeId=None
#        usedWayId=None
#        usedRefId=None
#        usedLat=None
#        usedLon=None
#        usedCountry=None
#                
#        # in routing mode us the next on the route as expected
#        if nextEdgeOnRoute!=None:
#            nextEdgeOnRoute, startRef, endRef, _, wayId, _, _, _, _=self.osmParserData.getEdgeEntryForEdgeId(nextEdgeOnRoute)
#            usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry=self.checkForPosOnEdgeId(lat, lon, nextEdgeOnRoute, startRef, endRef, wayId, maxDistance=10.0)
#            if usedEdgeId!=None:
#                self.debugPrint(lat, lon, "use nextEdgeId on route")
#                self.currentEdge=usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry
#                self.getPosTrigger=0
#                return self.currentEdge
#
#        # check current edge
#        if currentEdgeOnRoute!=None:
#            currentEdgeOnRoute, startRef, endRef, _, wayId, _, _, _, _=self.osmParserData.getEdgeEntryForEdgeId(currentEdgeOnRoute)
#            nearerRef=self.getNearerRefToPoint(lat, lon, startRef, endRef)
#                
#            # are we on the same edge
#            usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry=self.checkForPosOnEdgeId(lat, lon, currentEdgeOnRoute, startRef, endRef, wayId, maxDistance=10.0)
#            if usedEdgeId!=None:
#                self.currentEdge=usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry
#                self.getPosTrigger=0
#                return self.currentEdge
#                                                 
#            possibleEdges=list()
#            
#            # does not include currentEdgeOnRoute
#            resultList=self.osmParserData.getDifferentEdgeEntryForStartOrEndPoint(nearerRef, currentEdgeOnRoute)
#            if len(resultList)!=0:                    
#                for result in resultList:
#                    nextEdgeId, startRef, endRef, _, wayId, _, _, _, _=result
#                    edgeId, wayId, refId, (lat1, lon1), country=self.checkForPosOnEdgeIdStart(lat, lon, nextEdgeId, startRef, endRef, wayId, nearerRef, maxDistance=10.0)
#                    if edgeId!=None:
#                        possibleEdges.append((edgeId, wayId, refId, (lat1, lon1), country))   
#
#            if len(possibleEdges)!=0:
#                if len(possibleEdges)==1:
#                    self.currentEdge=possibleEdges[0]
#                    self.getPosTrigger=0
#                    return self.currentEdge
#               
#                maxDistance=20.0
#                shortestEntry=None
#                i=0
#                for possibleEdge in possibleEdges:
#                    _, _, _, (lat1, lon1), _=possibleEdge
#                    distance=self.osmutils.distance(lat, lon, lat1, lon1)
#                    if distance<maxDistance:
#                        maxDistance=distance
#                        shortestEntry=i
#                    i=i+1
#                if shortestEntry!=None:
#                    self.currentEdge=possibleEdges[shortestEntry]
#                    self.getPosTrigger=0
#                    return self.currentEdge
#                
#        if fromMouse==True:
#            return self.osmParserData.getEdgeIdOnPos(lat, lon, margin)
#            
#        # wait 4 gps calculations until fallback to global search
#        if self.getPosTrigger==3:
#            self.getPosTrigger=0
#            self.currentEdge=None
#            # use smaller search aerea
#            return self.osmParserData.getEdgeIdOnPos(lat, lon, 0.001)
#        
#        self.getPosTrigger=self.getPosTrigger+1
#        
#        # keep the last known edge until
#        if self.currentEdge!=None:
#            return self.currentEdge
#        
#        return usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry
      
    # check id any refs of the edge is near < maxDistance to pos
    def checkForPosOnEdgeId(self, lat, lon, edgeId, startRef, endRef, wayId, maxDistance=10.0):
        refList=self.osmParserData.getRefListOfEdge(edgeId, wayId, startRef, endRef)
#        print(refList)
        usedEdgeId=None
        usedRefId=None
        usedWayId=None
        usedLat=None
        usedLon=None                            
        usedCountry=None

        if len(refList)!=0:
            i=0
            lastRef=refList[0]
            for ref in refList[1:]:   
                _, refCountry=self.osmParserData.getCountryOfRef(ref)
                onLine, (tmpLat, tmpLon)=self.osmParserData.isOnLineBetweenRefs(lat, lon, ref, lastRef, maxDistance)
                if onLine==True:
                    usedEdgeId=edgeId
                    usedRefId=ref
                    usedWayId=wayId
                    usedLat=tmpLat
                    usedLon=tmpLon                            
                    usedCountry=refCountry
                    return usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry

                lastRef=ref  
                i=i+1
                
        return usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry

    # check first two refs - used on crossings
    # filters out impossible oneways
#    def checkForPosOnEdgeIdStart(self, lat, lon, edgeId, startRef, endRef, wayId, crossingRef, maxDistance=10.0):
##        print(refList)
#        usedEdgeId=None
#        usedRefId=None
#        usedWayId=None
#        usedLat=None
#        usedLon=None                            
#        usedCountry=None
#        
#        _, country=self.osmParserData.getCountryOfRef(crossingRef) 
#        (wayId, _, refs, streetTypeId, _, _, oneway, roundabout)=self.osmParserData.getWayEntryForIdAndCountry2(wayId, country)
#       
#        # ignore certain types for crossing expectations
#        if streetTypeId==0 or streetTypeId==1 or streetTypeId==13 or streetTypeId==14:
#            return usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry
#            
#        # filter out onways with wrong start
#        if oneway!=0:
#            if not self.osmParserData.isValidOnewayEnter(oneway, crossingRef, startRef, endRef):
#                return usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry
#
#        # TODO: filter roundabouts?
##        if roundabout:
##            return usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry
#
#        refList=self.osmParserData.getRefListSubset(refs, startRef, endRef)
#        if len(refList)>1:
#            if crossingRef==endRef:
#                refList.reverse()
#            ref1=refList[0]
#            ref2=refList[1]
#            onLine, (tmpLat, tmpLon)=self.osmParserData.isOnLineBetweenRefs(lat, lon, ref1, ref2, maxDistance)
#            if onLine==True:
#                _, refCountry=self.osmParserData.getCountryOfRef(ref1)
#                usedEdgeId=edgeId
#                usedRefId=ref1
#                usedWayId=wayId
#                usedLat=tmpLat
#                usedLon=tmpLon                            
#                usedCountry=refCountry
#        
#        return usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry

    # check pos in on the first two track positions (first edge)
    def checkForPosOnTracklist(self, lat, lon, trackList, maxDistance=NORMAL_EDGE_RANGE):
        endTrack=2
        if len(trackList)==1:
            endTrack=1
        for trackItem in trackList[:endTrack]:
            self.debugPrint(lat, lon, trackItem)
            coords=self.osmParserData.getCoordsOfTrackItem(trackItem)
            lat1, lon1=coords[0]
            for lat2, lon2 in coords[1:]:
                onTrack=self.isOnLineBetweenPoints(lat, lon, lat1, lon1, lat2, lon2, maxDistance)
                if onTrack==True:
                    return True
                lat1=lat2
                lon1=lon2
        
        return False
    
    def getHeadingOnEdgeId(self, edgeId, ref):
        edgeId, startRef, endRef, _, wayId, _, _, _, _=self.osmParserData.getEdgeEntryForEdgeId(edgeId)
        refList=self.osmParserData.getRefListOfEdge(edgeId, wayId, startRef, endRef)
        if len(refList)>1:
            if ref==endRef:
                refList.reverse()
            heading=self.getHeadingForReflist(refList)
            return heading
        
        return None
    
    def getHeadingForReflist(self, refs):
        _, country=self.osmParserData.getCountryOfRef(refs[0])
        if country==None:
            return None
        resultList=self.osmParserData.getRefEntryForIdAndCountry(refs[0], country)
        if len(resultList)==1:
            _, lat1, lon1, _, _=resultList[0]
        else:
            return None
        
        for ref in refs[1:]:
            _, country=self.osmParserData.getCountryOfRef(ref)
            if country==None:
                return None
            resultList=self.osmParserData.getRefEntryForIdAndCountry(ref, country)
            if len(resultList)==1:
                _, lat2, lon2, _, _=resultList[0]
            else:
                return None
            # use refs with distance more the 15m to calculate heading
            # if available else use the last one
            if self.osmutils.distance(lat1, lon1, lat2, lon2)>HEADING_CALC_LENGTH:
                break

        heading=self.osmutils.headingDegrees(lat1, lon1, lat2, lon2)
        return heading
    
    def getHeadingForPoints(self, ref1, ref2):
        _, country=self.osmParserData.getCountryOfRef(ref1)
        if country==None:
            return None
        resultList=self.osmParserData.getRefEntryForIdAndCountry(ref1, country)
        if len(resultList)==1:
            _, lat1, lon1, _, _=resultList[0]
        else:
            return None
        
        _, country=self.osmParserData.getCountryOfRef(ref2)
        if country==None:
            return None
        resultList=self.osmParserData.getRefEntryForIdAndCountry(ref2, country)
        if len(resultList)==1:
            _, lat2, lon2, _, _=resultList[0]
        else:
            return None
        
        heading=self.osmutils.headingDegrees(lat1, lon1, lat2, lon2)
        return heading
    
    def getNearerRefToPoint(self, lat, lon, ref1, ref2):
        distanceRef1=self.getDistanceFromPointToRef(lat, lon, ref1)
        distanceRef2=self.getDistanceFromPointToRef(lat, lon, ref2)
                
        if distanceRef1 < distanceRef2:
            return ref1
        return ref2

    def getDistanceFromPointToRef(self, lat, lon, ref):
        _, country=self.osmParserData.getCountryOfRef(ref)
        if country==None:
            return None
        resultList=self.osmParserData.getRefEntryForIdAndCountry(ref, country)
        if len(resultList)==1:
            _, lat1, lon1, _, _=resultList[0]
        else:
            return None
        
        return self.osmutils.distance(lat, lon, lat1, lon1)

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
    
    def isOnLineBetweenPoints(self, lat, lon, lat1, lon1, lat2, lon2, maxDistance, offset=0.0):
        nodes=self.osmutils.createTemporaryPoints(lat1, lon1, lat2, lon2, offset)
        minDistance=maxDistance
        for tmpLat, tmpLon in nodes:
            distance=self.osmutils.distance(lat, lon, tmpLat, tmpLon)
            if distance<minDistance:
                return True
        
        return False
    
    def calcNextPossibleEdgesOnCrossing(self, crossingRef, currentEdgeOnRoute, lat, lon):
        possibleEdges=list()
        edgeHeadings=list()
        _, country=self.osmParserData.getCountryOfRef(crossingRef) 
        
        self.longestPossibleEdge=0
        # does not include currentEdgeOnRoute
        resultList=self.osmParserData.getDifferentEdgeEntryForStartOrEndPoint(crossingRef, currentEdgeOnRoute)
        if len(resultList)!=0: 
            for result in resultList:
                nextEdgeId, startRef, endRef, length, wayId, _, _, _, _=result
                (wayId, tags, _, streetTypeId, _, _, oneway, roundabout)=self.osmParserData.getWayEntryForIdAndCountry2(wayId, country)
       
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
                heading=self.getHeadingOnEdgeId(nextEdgeId, crossingRef)
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
    
    # we have not confirmed the expected edge with NORMAL_EDGE_RANGE
    # check if one of the other edges matches better based on pos
    # and track
#    def getBestMatchingOtherEdgeForHeading(self, lat, lon, possibleEdges, edgeHeadings, missedEdgeId, speed, track):            
#        i=0
#        for edgeId, _ in possibleEdges:
#            if edgeId==missedEdgeId:
#                i=i+1
#                continue
#            
#            maxDistance=CLOSE_EDGE_RANGE
#            if self.otherNearHeading==True:
#                maxDistance=DECISION_EDGE_RANGE
# 
#            heading=edgeHeadings[i]
#            # first check if the heading match the track at all
#            headingDiff=self.osmutils.headingDiffAbsolute(heading, track)
#            if headingDiff<45:
#                # check pos with a close range
#                if self.checkEdgeDataForPos(lat, lon, edgeId, speed, maxDistance):
#                    return edgeId
#            
#            i=i+1
#        return missedEdgeId
    
    def checkEdgeDataForPos(self, lat, lon, edgeId, speed, maxDistance):
        edgeId, startRef, endRef, _, wayId, _, _, _, _=self.osmParserData.getEdgeEntryForEdgeId(edgeId)
#        if length<self.getToCrossingCheckDistance(speed):
#            return True
                    
        edgeId, wayId, _, _, _=self.checkForPosOnEdgeId(lat, lon, edgeId, startRef, endRef, wayId, maxDistance)
        return edgeId!=None
    
    # still use track info if available to select a "good" edge
    def getEdgeIdOnPosForRoutingFallback(self, lat, lon, fromMouse, margin, track, speed, nextEdgeOnRoute):
        # TODO: add fromMouse==False!!!
        if track!=None:                
            edgeId=self.getEdgeIdOnPosWithTrack(lat, lon, track, margin, NORMAL_EDGE_RANGE)
            if edgeId!=None:
                self.currentEdge=self.useNextEdge(lat, lon, track, speed, edgeId, True)
                return self.currentEdge
            else:
                self.lastApproachingRef=None
                self.cleanEdgeCalculations(lat, lon)
                return None, None, None, None, None
            
        self.currentEdge=self.osmParserData.getEdgeIdOnPos(lat, lon, margin, NORMAL_EDGE_RANGE)
        if track!=None:
            if self.currentEdge[0]!=None:
                self.currentEdge=self.useNextEdge(lat, lon, track, speed, self.currentEdge[0], True)
            else:
                self.cleanEdgeCalculations(lat, lon)
                self.lastApproachingRef=None
                
        return self.currentEdge
          
    def cleanEdgeCalculations(self, lat, lon):
        self.lastApproachingRef=self.approachingRef
        self.approachingRef=None
        self.currentPossibleEdgeList.clear()
        self.expectedNextEdgeId=None
        self.possibleEdges=None
        self.distanceToCrossing=None
        self.crossingPassed=False
        self.shortEdge=False
        self.nextEdgeLength=None
        self.otherNearHeading=False
        self.checkCurrentEdge=True
        self.distanceFromCrossing=None
        self.nearCrossing=False
        self.nearPossibleEdges=None
        self.stoppedOnEdge=False
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
    
    # dont check every time
    def checkPosOnCurrentEdge(self, lat, lon, edgeId, startRef, endRef, wayId, maxDistance, speed, length):
        if self.currentEdgeCheckTrigger==1:
#            print("checkPosOnCurrentEdge")
            self.currentEdgeCheckTrigger=0
            refCountry=self.osmParserData.getCountryOfPos(lat, lon)
            if refCountry==None:
                return None, None, None, None, None
            
            (wayId, _, _, streetTypeId, _, _, _, _)=self.osmParserData.getWayEntryForIdAndCountry2(wayId, refCountry)
            
            # larger check distance for motorways
            if streetTypeId==2:
                # motorway
                maxDistance=maxDistance*2
                
            return self.checkForPosOnEdgeId(lat, lon, edgeId, startRef, endRef, wayId, maxDistance)
        else:
            self.currentEdgeCheckTrigger=self.currentEdgeCheckTrigger+1
            return self.currentEdge
        
    def calcNextCrossingEdges(self, edgeId, lat, lon):
        # check if approaching ref is valid
        if self.approachingRef!=None:
            self.debugPrint(lat, lon, "calc next crossing edges at %d"%self.approachingRef)
            self.currentPossibleEdgeList.clear()
            self.possibleEdges, self.edgeHeadings=self.calcNextPossibleEdgesOnCrossing(self.approachingRef, edgeId, lat, lon)
        
    def calcNextEdgeValues(self, lat, lon, edgeId, track, speed):
        edgeId, startRef, endRef, length, wayId, _, _, _, _=self.osmParserData.getEdgeEntryForEdgeId(edgeId)

        self.approachingRef=self.calcApproachingRef(lat, lon, startRef, endRef, track, True)
        
        # check if approaching ref is valid
        # else current edge stays the same
        if self.approachingRef!=None:
            self.debugPrint(lat, lon, "approachingRef %d"%self.approachingRef)
            
            _, country=self.osmParserData.getCountryOfRef(self.approachingRef)
            usedLat, usedLon=self.osmParserData.getCoordsWithRefAndCountry(self.approachingRef, country)
            self.currentEdge=edgeId, wayId, self.approachingRef, (usedLat, usedLon), country
            
            distance=self.getDistanceFromPointToRef(lat, lon, self.approachingRef)
            self.distanceToCrossing=distance
            self.crossingPassed=False
            self.nearCrossing=False
            
            if length<self.getToCrossingCheckDistance(speed):
                self.shortEdge=True
            else:
                self.shortEdge=False
        
    def useNextEdge(self, lat, lon, track, speed, nextEdgeId, cleanLastApproachingRef):
        self.cleanEdgeCalculations(lat, lon)
        
        if cleanLastApproachingRef==True:
            self.debugPrint(lat, lon, "clear self.lastApproachingRef")
            self.lastApproachingRef=None
            
        # immediately calc next crossing to be available on the next call
        # else in case of a short edge we might miss the next crossing
        self.calcNextEdgeValues(lat, lon, nextEdgeId, track, speed)
        self.calcNextCrossingEdges(nextEdgeId, lat, lon)
        
        if self.approachingRef!=None:
            distance=self.getDistanceFromPointToRef(lat, lon, self.approachingRef)
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
        if self.shortEdge==True or distance < self.getToCrossingCheckDistance(speed) or self.expectedNextEdgeId!=None or self.nearCrossing==True: 
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
    
    def getEdgeIdOnPosForRouting2(self, lat, lon, track, currentEdgeOnRoute, nextEdgeOnRoute, margin, fromMouse, speed, trackLog=False):        
        if track==None:
            return self.getEdgeIdOnPosForRoutingFallback(lat, lon, fromMouse, margin, track, speed, nextEdgeOnRoute)

        if currentEdgeOnRoute!=None:
            self.debugPrint(lat, lon, "current edge=%d"%currentEdgeOnRoute)
        if nextEdgeOnRoute!=None:
            self.debugPrint(lat, lon, "next edge=%d"%nextEdgeOnRoute)
        
        if trackLog==False:
            self.logTrack(lat, lon, track, speed, "")
        
        if speed==0:
            self.stoppedOnEdge=True
            
        # final fallback if anything goes wrong
        if self.distanceFromCrossing!=None and self.distanceFromCrossing>MAXIMUM_DECISION_LENGTH:
            self.debugPrint(lat, lon, "too far from crossing  - fallback")
            return self.getEdgeIdOnPosForRoutingFallback(lat, lon, fromMouse, margin, track, speed, nextEdgeOnRoute)

        if currentEdgeOnRoute!=None:
            currentEdgeOnRoute, startRef, endRef, length, wayId, _, _, _, _=self.osmParserData.getEdgeEntryForEdgeId(currentEdgeOnRoute)    
            # check if we are still on the expected edge
            # only used between crossingPassed and nearCrossing
            # use a relative large macDistance to compensate wrong
            # map data and/or gps failures
            
            # TODO: if a expectedNextEdgeId or checkCurrentEdge is set we will 
            # not leave the edge until the MAXIMUM_DECISION_LENGTH is reached
                        
            if self.expectedNextEdgeId==None and self.checkCurrentEdge==True:
                edge=self.checkPosOnCurrentEdge(lat, lon, currentEdgeOnRoute, startRef, endRef, wayId, NORMAL_EDGE_RANGE, speed, length)
                if edge[0]==None:
                    self.debugPrint(lat, lon, "lost current edge")
                    return self.getEdgeIdOnPosForRoutingFallback(lat, lon, fromMouse, margin, track, speed, nextEdgeOnRoute)

            # TODO: if we stop and change the direction
            # approaching ref should be recalculated
#            if self.stoppedOnEdge==True:
#                self.stoppedOnEdge=False
#                if length>SHORT_EDGE_LENGTH:
#                    if self.isChangedApproachRef(lat, lon, startRef, endRef, track):
#                        self.debugPrint(lat, lon, "approaching ref changed after stop")
#                        return self.useNextEdge(lat, lon, track, speed, currentEdgeOnRoute, True)

            if self.expectedNextEdgeId!=None:
                distance=self.getDistanceFromPointToRef(lat, lon, self.approachingRef)
                self.updateCrossingDistances(lat, lon, distance, speed)
                
                if self.crossingPassed==True or self.nearCrossing==True:
                    self.checkCurrentEdge=False
                    
                    if self.isQuickNextEdgeChoices(lat, lon, track, speed, self.expectedNextEdgeId):
                        return self.useNextEdge(lat, lon, track, speed, self.expectedNextEdgeId, False)
                                            
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
                self.debugPrint(lat, lon, "no next crossing possible")
                return self.currentEdge
            
            distance=self.getDistanceFromPointToRef(lat, lon, self.approachingRef)
            self.updateCrossingDistances(lat, lon, distance, speed)
            
            self.calcCurrentBestMatchingEdge(lat, lon, track, speed, distance, nextEdgeOnRoute)

            # immediately check for any quick decisions on the next edge
            # else we have to wait till the next call
            if self.expectedNextEdgeId!=None: 
                if self.crossingPassed==True or self.nearCrossing==True:
                    if self.isQuickNextEdgeChoices(lat, lon, track, speed, self.expectedNextEdgeId):
                        return self.useNextEdge(lat, lon, track, speed, self.expectedNextEdgeId, False)

            return self.currentEdge
                
        return self.getEdgeIdOnPosForRoutingFallback(lat, lon, fromMouse, margin, track, speed, nextEdgeOnRoute)

    def getApproachingRef(self):
        return self.approachingRef
    
    def logTrack(self, lat, lon, track, speed, text):
        if self.trackLog!=None:
            self.trackLog.addTrackLogLine(lat, lon, track, speed, text)

    def debugPrint(self, lat, lon, text):
        if WITH_CROSSING_DEBUG==True:
            print("%f %f %s"%(lat, lon, text))

#    def getNearestRefRangeOnEdgeForPos(self, lat, lon, edgeId, wayId, startRef, endRef):
#        refList=self.osmParserData.getRefListOfEdge(edgeId, wayId, startRef, endRef)
#
#        if len(refList)!=0:
#            i=0
#            for ref in refList[:-1]: 
#                onLine, (tmpLat, tmpLon)=self.osmParserData.isOnLineBetweenRefs(lat, lon, ref, refList[i+1], 5.0)
#                if onLine==True:
#                    return (ref, refList[i+1])
#                i=i+1
#        return (None, None)

    def getEdgeIdOnPosWithTrack(self, lat, lon, track, margin, maxDistance):
        maxNodeDistance=500.0
 
        refCountry=self.osmParserData.getCountryOfPos(lat, lon)
        if refCountry==None:
            return None

        possibleWayList=list()
        nodes=self.osmParserData.getNearNodes(lat, lon, refCountry, maxNodeDistance, margin)
        for refId, _, _, wayIdList in nodes:           
            for wayId in wayIdList:
                (_, _, refs, _, _, _, oneway, _)=self.osmParserData.getWayEntryForIdAndCountry2(wayId, refCountry)
                # use the refs before and after to check
                index=refs.index(refId)
                refList=list()
                if index==0:
                    refList.append(refId)
                    refList.append(refs[index+1])
                elif index==len(refs)-1:
                    refList.append(refs[-1])
                    refList.append(refId)
                else:
                    refList.append(refs[index-1])
                    refList.append(refId)
                    refList.append(refs[index+1])
                                    
                lastRef=refList[0]
                for ref in refList[1:]:
                    onLine, (_, _)=self.osmParserData.isOnLineBetweenRefs(lat, lon, ref, lastRef, maxDistance)
                    if onLine==True:
                        if not (wayId, refs, ref, oneway) in possibleWayList:
                            possibleWayList.append((wayId, refs, ref, oneway))
                        # one for every way is enough
                        break
                    lastRef=ref
                        
        closestEdgeId=None
        if len(possibleWayList)!=0:
#            print(possibleWayList)
            minDistance=maxDistance
            doneEdges=list()
            for wayId, refs, ref, oneway in possibleWayList:
                resultList=self.osmParserData.getEdgeEntryForWayId(wayId)

                for edge in resultList:
                    edgeId, startRef, endRef, _, wayId, _, _, _, _=edge
                    if edgeId in doneEdges:
                        continue
                    doneEdges.append(edgeId)
                    edgeRefList=self.osmParserData.getRefListSubset(refs, startRef, endRef)
                                        
                    if ref in edgeRefList:
                        lastRef=refs[0]
                        for ref in refs[1:]:
                            onLine, distance=self.osmParserData.isMinimalDistanceOnLineBetweenRefs(lat, lon, ref, lastRef, maxDistance)
                            if onLine==True:
                                if oneway==0 or oneway==2:
                                    heading=self.getHeadingForPoints(ref, lastRef)
                                    headingDiff=self.osmutils.headingDiffAbsolute(track, heading)
                                    if headingDiff<CLOSE_HEADING_RANGE:
                                        if distance<minDistance:
                                            minDistance=distance
                                            closestEdgeId=edgeId
                                
                                if oneway==0 or oneway==1:
                                    heading=self.getHeadingForPoints(lastRef, ref)
                                    headingDiff=self.osmutils.headingDiffAbsolute(track, heading)
                                    if headingDiff<CLOSE_HEADING_RANGE:
                                        if distance<minDistance:
                                            minDistance=distance
                                            closestEdgeId=edgeId

                            lastRef=ref
                        
        return closestEdgeId

