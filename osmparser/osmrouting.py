'''
Created on Feb 22, 2012

@author: maxl
'''

from osmparser.osmutils import OSMUtils

SHORT_EDGE_LENGTH=20.0
MAXIMUM_DECISION_LENGTH=100.0
NORMAL_EDGE_RANGE=20.0
CLOSE_EDGE_RANGE=10.0
DECISION_EDGE_RANGE=5.0
WITH_CROSSING_DEBUG=True

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
        self.getPosTrigger=0
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
        
    def getCurrentSearchEdgeList(self):
        return self.currentPossibleEdgeList
    
    def getExpectedNextEdge(self):
        return self.expectedNextEdgeId
    
    def calcApproachingRef(self, lat, lon, startRef, endRef, track, useLastValue):
        # find the ref we are aproaching based on track
        # since we ony check when coming to a crossing 
        # but not on leaving
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
            
            if headingDiff1<45 or headingDiff2<45:
                if headingDiff1<headingDiff2:
                    ref=startRef
                else:
                    ref=endRef
            else:
                return None
        else:
            if self.lastApproachingRef==startRef:
                ref=endRef
            elif self.lastApproachingRef==endRef:
                ref=startRef
                            
        return ref
    
    def getEdgeIdOnPosForRoutingWOTrack(self, lat, lon, track, currentEdgeOnRoute, nextEdgeOnRoute, margin, fromMouse):        
        usedEdgeId=None
        usedWayId=None
        usedRefId=None
        usedLat=None
        usedLon=None
        usedCountry=None
                
        # in routing mode us the next on the route as expected
        if nextEdgeOnRoute!=None:
            nextEdgeOnRoute, startRef, endRef, _, wayId, _, _, _, _=self.osmParserData.getEdgeEntryForEdgeId(nextEdgeOnRoute)
            usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry=self.checkForPosOnEdgeId(lat, lon, nextEdgeOnRoute, startRef, endRef, wayId, maxDistance=10.0)
            if usedEdgeId!=None:
                self.debugPrint("use nextEdgeId on route")
                self.currentEdge=usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry
                self.getPosTrigger=0
                return self.currentEdge

        # check current edge
        if currentEdgeOnRoute!=None:
            currentEdgeOnRoute, startRef, endRef, _, wayId, _, _, _, _=self.osmParserData.getEdgeEntryForEdgeId(currentEdgeOnRoute)
            nearerRef=self.getNearerRefToPoint(lat, lon, startRef, endRef)
                
            # are we on the same edge
            usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry=self.checkForPosOnEdgeId(lat, lon, currentEdgeOnRoute, startRef, endRef, wayId, maxDistance=10.0)
            if usedEdgeId!=None:
                self.currentEdge=usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry
                self.getPosTrigger=0
                return self.currentEdge
                                                 
            possibleEdges=list()
            
            # does not include currentEdgeOnRoute
            resultList=self.osmParserData.getDifferentEdgeEntryForStartOrEndPoint(nearerRef, currentEdgeOnRoute)
            if len(resultList)!=0:                    
                for result in resultList:
                    nextEdgeId, startRef, endRef, _, wayId, _, _, _, _=result
                    edgeId, wayId, refId, (lat1, lon1), country=self.checkForPosOnEdgeIdStart(lat, lon, nextEdgeId, startRef, endRef, wayId, nearerRef, maxDistance=10.0)
                    if edgeId!=None:
                        possibleEdges.append((edgeId, wayId, refId, (lat1, lon1), country))   

            if len(possibleEdges)!=0:
                if len(possibleEdges)==1:
                    self.currentEdge=possibleEdges[0]
                    self.getPosTrigger=0
                    return self.currentEdge
               
                maxDistance=20.0
                shortestEntry=None
                i=0
                for possibleEdge in possibleEdges:
                    _, _, _, (lat1, lon1), _=possibleEdge
                    distance=self.osmutils.distance(lat, lon, lat1, lon1)
                    if distance<maxDistance:
                        maxDistance=distance
                        shortestEntry=i
                    i=i+1
                if shortestEntry!=None:
                    self.currentEdge=possibleEdges[shortestEntry]
                    self.getPosTrigger=0
                    return self.currentEdge
                
        if fromMouse==True:
            return self.osmParserData.getEdgeIdOnPos(lat, lon, margin)
            
        # wait 4 gps calculations until fallback to global search
        if self.getPosTrigger==3:
            self.getPosTrigger=0
            self.currentEdge=None
            # use smaller search aerea
            return self.osmParserData.getEdgeIdOnPos(lat, lon, 0.001)
        
        self.getPosTrigger=self.getPosTrigger+1
        
        # keep the last known edge until
        if self.currentEdge!=None:
            return self.currentEdge
        
        return usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry
      
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
    def checkForPosOnEdgeIdStart(self, lat, lon, edgeId, startRef, endRef, wayId, crossingRef, maxDistance=10.0):
#        print(refList)
        usedEdgeId=None
        usedRefId=None
        usedWayId=None
        usedLat=None
        usedLon=None                            
        usedCountry=None
        
        _, country=self.osmParserData.getCountryOfRef(crossingRef) 
        (wayId, _, refs, streetTypeId, _, _, oneway, roundabout)=self.osmParserData.getWayEntryForIdAndCountry2(wayId, country)
       
        # ignore certain types for crossing expectations
        if streetTypeId==0 or streetTypeId==1 or streetTypeId==13 or streetTypeId==14:
            return usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry
            
        # filter out onways with wrong start
        if oneway!=0:
            if not self.osmParserData.isValidOnewayEnter(oneway, crossingRef, startRef, endRef):
                return usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry

        # TODO: filter roundabouts?
#        if roundabout:
#            return usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry

        refList=self.osmParserData.getRefListSubset(refs, startRef, endRef)
        if len(refList)>1:
            if crossingRef==endRef:
                refList.reverse()
            ref1=refList[0]
            ref2=refList[1]
            onLine, (tmpLat, tmpLon)=self.osmParserData.isOnLineBetweenRefs(lat, lon, ref1, ref2, maxDistance)
            if onLine==True:
                _, refCountry=self.osmParserData.getCountryOfRef(ref1)
                usedEdgeId=edgeId
                usedRefId=ref1
                usedWayId=wayId
                usedLat=tmpLat
                usedLon=tmpLon                            
                usedCountry=refCountry
        
        return usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry

    # check pos in on the first track positions (first edge)
    def checkForPosOnTracklist(self, lat, lon, trackList, maxDistance=20.0):
        coords=self.osmParserData.getCoordsOfTrackItem(trackList[0])
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
            heading=self.getHeadingBetweenPoints(refList)
            return heading
        
        return None
    
    def getHeadingBetweenPoints(self, refs):
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
            # use refs with distanmce more the 5m to calculate heading
            if self.osmutils.distance(lat1, lon1, lat2, lon2)>20.0:
                break

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
    
    def calcNextPossibleEdgesOnCrossing(self, crossingRef, currentEdgeOnRoute):
        possibleEdges=list()
        edgeHeadings=list()
        _, country=self.osmParserData.getCountryOfRef(crossingRef) 
        
        # does not include currentEdgeOnRoute
        resultList=self.osmParserData.getDifferentEdgeEntryForStartOrEndPoint(crossingRef, currentEdgeOnRoute)
        if len(resultList)!=0: 
            for result in resultList:
                nextEdgeId, startRef, endRef, length, wayId, _, _, _, _=result
                (wayId, _, _, streetTypeId, _, _, oneway, _)=self.osmParserData.getWayEntryForIdAndCountry2(wayId, country)
       
                # ignore certain types for crossing expectations
                if streetTypeId==0 or streetTypeId==1 or streetTypeId==13 or streetTypeId==14:
                    continue
            
                # filter out onways with wrong start
                if oneway!=0:
                    if not self.osmParserData.isValidOnewayEnter(oneway, crossingRef, startRef, endRef):
                        continue

                self.currentPossibleEdgeList.append(nextEdgeId)
                heading=self.getHeadingOnEdgeId(nextEdgeId, crossingRef)
                edgeHeadings.append(heading)
                possibleEdges.append((nextEdgeId, length))

        return possibleEdges, edgeHeadings
    
    def getBestMatchingNextEdgeForHeading(self, track, possibleEdges, edgeHeadings):
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
        
        if minHeadingEntry!=None:
            i=0
            for heading in edgeHeadings:
                if heading!=None and heading!=edgeHeadings[minHeadingEntry]:
                    headingDiff=self.osmutils.headingDiffAbsolute(edgeHeadings[minHeadingEntry], heading)
                    if headingDiff<45:
                        # next best heading is near to best matching
                        self.debugPrint("heading diff < 45 %f"%(headingDiff))
                        nearPossibleEdges.append(possibleEdges[i][0])
                        otherNearHeading=True
                i=i+1
            expectedNextEdgeId=possibleEdges[minHeadingEntry][0]
            nextEdgeLength=possibleEdges[minHeadingEntry][1]
            return expectedNextEdgeId, nextEdgeLength, otherNearHeading, nearPossibleEdges

        return None, None, None, None
    
    def getBestMatchingOtherEdgeForHeading(self, lat, lon, possibleEdges, edgeHeadings, missedEdgeId, speed, track):            
        i=0
        for edgeId, _ in possibleEdges:
            if edgeId==missedEdgeId:
                i=i+1
                continue
            
            maxDistance=CLOSE_EDGE_RANGE
            if self.otherNearHeading==True:
                maxDistance=DECISION_EDGE_RANGE
 
            if self.checkEdgeDataForPos(lat, lon, edgeId, speed, maxDistance):
                heading=edgeHeadings[i]
                # even if we match distance check track
                # else return still the missed edge
                headingDiff=self.osmutils.headingDiffAbsolute(heading, track)
                if headingDiff<45:
                    return edgeId
            
            i=i+1
        return missedEdgeId
    
    def checkEdgeDataForPos(self, lat, lon, edgeId, speed, maxDistance):
        edgeId, startRef, endRef, length, wayId, _, _, _, _=self.osmParserData.getEdgeEntryForEdgeId(edgeId)
        if length<self.getToCrossingCheckDistance(speed):
            return True
                    
        edgeId, wayId, _, _, _=self.checkForPosOnEdgeId(lat, lon, edgeId, startRef, endRef, wayId, maxDistance)
        return edgeId!=None
    
    def getEdgeIdOnPosForRoutingFallback(self, lat, lon, fromMouse, margin, track, speed):
        if fromMouse==False:
            # use smaller search aerea
            margin=0.001
            
        self.currentEdge=self.osmParserData.getEdgeIdOnPos(lat, lon, margin)
        if self.currentEdge[0]!=None:
            self.currentEdge=self.useNextEdge(lat, lon, track, speed, self.currentEdge[0], True)
        else:
            self.cleanEdgeCalculations()
            self.lastApproachingRef=None
        return self.currentEdge
          
    def cleanEdgeCalculations(self):
        self.debugPrint("cleanEdgeCalculations")
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

    def getToCrossingCheckDistance(self, speed):
        if speed < 30:
            return 30.0
        if speed < 50:
            return 50.0
        if speed < 80:
            return 80.0
        if speed < 100:
            return 100.0
        if speed > 100:
            return 150.0
        return 30.0
    
    def getFromCrossingCheckDistance(self, speed):
        if speed < 30:
            return 5.0
        if speed < 50:
            return 8.0
        return 30.0
    
    def isShortEdgeForSpeed(self, length, speed):
        if length < SHORT_EDGE_LENGTH and speed > 30:
            return True
        return False
    
    def isSpeedHighEnoughForNoCrossing(self, speed):
        if speed > 50:
            return True
        return False
    
    def updateCrossingDistances(self, lat, lon, distance, speed):
        if self.distanceToCrossing==None:
            return
            
        if distance <= self.distanceToCrossing:
            self.distanceToCrossing=distance
            crossingRange=self.getToCrossingCheckDistance(speed)
            # near crossing
            if self.distanceToCrossing < crossingRange:
                self.nearCrossing=True
                self.debugPrint("near crossing %d"%self.distanceToCrossing)

            return

        self.distanceFromCrossing=distance        
        
        # past crossing
        crossingRange=self.getFromCrossingCheckDistance(speed)
        if self.distanceFromCrossing > crossingRange:
            self.crossingPassed=True
            self.debugPrint("past crossing %d"%self.distanceFromCrossing)
            return
        
        return
    
    def isQuickNextEdgeChoices(self, lat, lon, track, speed, edgeId):
        if len(self.possibleEdges)==1:
            # only one possible edge
            self.debugPrint("next edge only one possible")
            return True
        
        if self.otherNearHeading==False:
            if self.isSpeedHighEnoughForNoCrossing(speed):
                self.debugPrint("speed large - assume pass through")
                return True
            
            if self.isShortEdgeForSpeed(self.nextEdgeLength, speed):
                # short edge passed with speed - just use it
                self.debugPrint("next edge is short edge and speed large - assume pass through")
                return True

        return False
    
    def checkForPosOnEdgeIdWithSpeed(self, lat, lon, edgeId, startRef, endRef, wayId, maxDistance, speed):
        if speed > 30:
            # dont assume we have left the edge
            return self.currentEdge
        return self.checkForPosOnEdgeId(lat, lon, edgeId, startRef, endRef, wayId, maxDistance)
    
    def calcNextCrossingEdges(self, edgeId):
        # check if approaching ref is valid
        if self.approachingRef!=None:
            self.debugPrint("calc next crossing edges at %d"%self.approachingRef)
            self.currentPossibleEdgeList.clear()
            self.possibleEdges, self.edgeHeadings=self.calcNextPossibleEdgesOnCrossing(self.approachingRef, edgeId)
        
    def calcNextEdgeValues(self, lat, lon, edgeId, track, speed):
        edgeId, startRef, endRef, length, wayId, _, _, _, _=self.osmParserData.getEdgeEntryForEdgeId(edgeId)

        self.approachingRef=self.calcApproachingRef(lat, lon, startRef, endRef, track, True)
        
        # check if approaching ref is valid
        # else current edge stays the same
        if self.approachingRef!=None:
            self.debugPrint("approachingRef %d"%self.approachingRef)
            
            _, country=self.osmParserData.getCountryOfRef(self.approachingRef)
            usedLat, usedLon=self.osmParserData.getCoordsWithRefAndCountry(self.approachingRef, country)
            self.currentEdge=edgeId, wayId, self.approachingRef, (usedLat, usedLon), country
            
            distance=self.getDistanceFromPointToRef(lat, lon, self.approachingRef)
            self.distanceToCrossing=distance
            self.crossingPassed=False
            self.nearCrossing=False
            
            if length<SHORT_EDGE_LENGTH:
                self.shortEdge=True
            else:
                self.shortEdge=False
        
    def useNextEdge(self, lat, lon, track, speed, nextEdgeId, cleanLastApproachingRef):
        self.cleanEdgeCalculations()
        
        if cleanLastApproachingRef==True:
            self.debugPrint("clear self.lastApproachingRef")
            self.lastApproachingRef=None
            
        # immediately calc next crossing
        self.calcNextEdgeValues(lat, lon, nextEdgeId, track, speed)
        self.calcNextCrossingEdges(nextEdgeId)

        return self.currentEdge

    def isOnlyMatchingOnEdge(self, lat, lon, speed):
        matchExpected=self.checkEdgeDataForPos(lat, lon, self.expectedNextEdgeId, speed, DECISION_EDGE_RANGE)
        
        for otherPossible in self.nearPossibleEdges:
            matchOther=self.checkEdgeDataForPos(lat, lon, otherPossible, speed, DECISION_EDGE_RANGE)
            print(matchExpected)
            print(matchOther)
            if matchOther==True and matchExpected==True:
                return False
                
        return True
            
    def isChangedApproachRef(self, lat, lon, startRef, endRef, track):
        if self.approachingRef!=None:
            approachingRef=self.calcApproachingRef(lat, lon, startRef, endRef, track, False)
            if approachingRef!=None and approachingRef!=self.approachingRef:
                return True
        
        return False
    
    def calcCurrentBestMatchingEdge(self, lat, lon, track, speed, distance):
        if self.shortEdge==True or distance < self.getToCrossingCheckDistance(speed) or self.expectedNextEdgeId!=None or self.nearCrossing==True: 
            self.debugPrint("check possible crossings - distance %d"%(distance))   
            expectedNextEdgeId, nextEdgeLength, otherNearHeading, nearPossibleEdges=self.getBestMatchingNextEdgeForHeading(track, self.possibleEdges, self.edgeHeadings)
            if expectedNextEdgeId!=None:
                self.expectedNextEdgeId=expectedNextEdgeId
                self.nextEdgeLength=nextEdgeLength
                self.otherNearHeading=otherNearHeading
                self.nearPossibleEdges=nearPossibleEdges

    def checkEdge(self, lat, lon, track, speed):
        maxDistance=CLOSE_EDGE_RANGE
        if self.otherNearHeading==True:
            maxDistance=DECISION_EDGE_RANGE
            
        if not self.checkEdgeDataForPos(lat, lon, self.expectedNextEdgeId, speed, maxDistance):
            # something went wrong
            # or we havnt reached the edge in the time
            if self.distanceFromCrossing>self.nextEdgeLength or self.distanceFromCrossing>MAXIMUM_DECISION_LENGTH:
                self.debugPrint("too far from crossing  - use expected")
                return self.useNextEdge(lat, lon, track, speed, self.expectedNextEdgeId, False)

            otherEdgeId=self.getBestMatchingOtherEdgeForHeading(lat, lon, self.possibleEdges, self.edgeHeadings, self.expectedNextEdgeId, speed, track)
            if otherEdgeId!=self.expectedNextEdgeId:
                self.debugPrint("next edge not confirmed - fallback to other possible")
            else:
                self.debugPrint("next edge not confirmed - no better fallback found still use expected")
                
            return self.useNextEdge(lat, lon, track, speed, otherEdgeId, False)

        else:
            self.debugPrint("pos on edge confirmed")
            return self.useNextEdge(lat, lon, track, speed, self.expectedNextEdgeId, False)

        # no decision possible
        return None, None, None, None, None
    
    def getEdgeIdOnPosForRouting2(self, lat, lon, track, currentEdgeOnRoute, nextEdgeOnRoute, margin, fromMouse, speed):        
        if track==None:
            return self.getEdgeIdOnPosForRoutingWOTrack(lat, lon, track, currentEdgeOnRoute, nextEdgeOnRoute, margin, fromMouse)

        if speed==0:
            self.stoppedOnEdge=True
            
        if currentEdgeOnRoute!=None:
            currentEdgeOnRoute, startRef, endRef, _, wayId, _, _, _, _=self.osmParserData.getEdgeEntryForEdgeId(currentEdgeOnRoute)
                                                    
            # check if we are still on the expected edge
            if self.expectedNextEdgeId==None and self.checkCurrentEdge==True:
                edge=self.checkForPosOnEdgeIdWithSpeed(lat, lon, currentEdgeOnRoute, startRef, endRef, wayId, NORMAL_EDGE_RANGE, speed)
                if edge[0]==None:
                    self.debugPrint("lost current edge")
                    return self.getEdgeIdOnPosForRoutingFallback(lat, lon, fromMouse, margin, track, speed)

            # TODO: must wait until crossingPassed else check for changed
            # approching can fail
#            if self.stoppedOnEdge==True:
#                self.stoppedOnEdge=False
#                if length>SHORT_EDGE_LENGTH:
#                    if self.isChangedApproachRef(lat, lon, startRef, endRef, track):
#                        self.debugPrint("approaching ref changed after stop")
#                        return self.useNextEdge(lat, lon, track, speed, currentEdgeOnRoute, True)

            if self.expectedNextEdgeId!=None:
                distance=self.getDistanceFromPointToRef(lat, lon, self.approachingRef)
                self.updateCrossingDistances(lat, lon, distance, speed)
                if self.crossingPassed==True or self.nearCrossing==True:
                    self.checkCurrentEdge=False
                    
                    if self.isQuickNextEdgeChoices(lat, lon, track, speed, self.expectedNextEdgeId):
                        return self.useNextEdge(lat, lon, track, speed, self.expectedNextEdgeId, False)
                                            
                    if self.crossingPassed==True:
                        self.debugPrint("crossing passed")

                        if self.otherNearHeading==True and self.nearPossibleEdges!=None:
                            if not self.isOnlyMatchingOnEdge(lat, lon, speed):
                                # delay until we can make sure which edge we are
                                self.debugPrint("current point match more then on possible edge")
                                if self.distanceFromCrossing>self.nextEdgeLength or self.distanceFromCrossing>MAXIMUM_DECISION_LENGTH:
                                    self.debugPrint("too far from crossing  - use expected")
                                    return self.useNextEdge(lat, lon, track, speed, self.expectedNextEdgeId, False)
                            else:
                                edge=self.checkEdge(lat, lon, track, speed)
                                if edge[0]!=None:
                                    return self.currentEdge
                                
                        else:
                            edge=self.checkEdge(lat, lon, track, speed)
                            if edge[0]!=None:
                                return self.currentEdge
                                
            if self.approachingRef==None:
                self.calcNextEdgeValues(lat, lon, currentEdgeOnRoute, track, speed)

            if self.possibleEdges==None:
                self.calcNextCrossingEdges(currentEdgeOnRoute)

            if self.possibleEdges==None or len(self.possibleEdges)==0:
                self.debugPrint("no next crossing possible")
                return self.currentEdge
            
            distance=self.getDistanceFromPointToRef(lat, lon, self.approachingRef)
            self.updateCrossingDistances(lat, lon, distance, speed)
            
            self.calcCurrentBestMatchingEdge(lat, lon, track, speed, distance)

            if self.expectedNextEdgeId!=None: 
                if self.crossingPassed==True or self.nearCrossing==True:
                    if self.isQuickNextEdgeChoices(lat, lon, track, speed, self.possibleEdges[0][0]):
                        return self.useNextEdge(lat, lon, track, speed, self.possibleEdges[0][0], False)

            return self.currentEdge
                
        return self.getEdgeIdOnPosForRoutingFallback(lat, lon, fromMouse, margin, track, speed)

    def getApproachingRef(self):
        return self.approachingRef
    
    def debugPrint(self, text):
        if WITH_CROSSING_DEBUG==True:
            print(text)
