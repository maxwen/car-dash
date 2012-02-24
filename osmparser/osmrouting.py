'''
Created on Feb 22, 2012

@author: maxl
'''

from osmparser.osmutils import OSMUtils

SHORT_EDGE_LENGTH=30.0

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
        self.edgeHeadings=None
        self.expectedEdgeTrigger=0
        self.lastDistance=None
        self.crossingPassed=False
        self.shortEdge=False
        self.lastExpectedNextEdgeId=None
        self.nextEdgeLength=None
        self.otherNearHeading=False
        self.lastApproachingRef=None
        self.checkCurrentEdge=True
        
    def getCurrentSearchEdgeList(self):
        return self.currentPossibleEdgeList
    
    def getExpectedNextEdge(self):
        return self.expectedNextEdgeId
    
    def calcApproachingRef(self, lat, lon, startRef, endRef, track):
        # find the ref we are aproaching based on track
        # since we ony check when coming to a crossing 
        # but not on leaving
        if self.lastApproachingRef==None:
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
            
            if headingDiff1<headingDiff2:
                ref=startRef
            else:
                ref=endRef
        else:
            if self.lastApproachingRef==startRef:
                ref=endRef
            elif self.lastApproachingRef==endRef:
                ref=startRef
                            
        return ref
    
    def getEdgeIdOnPosForRouting(self, lat, lon, track, currentEdgeOnRoute, nextEdgeOnRoute, margin, fromMouse):        
        
        if track==None or currentEdgeOnRoute==None:
            return self.getEdgeIdOnPosForRoutingWOTrack(lat, lon, track, currentEdgeOnRoute, nextEdgeOnRoute, margin, fromMouse)
              
        if currentEdgeOnRoute!=None and self.expectedNextEdgeId!=None and self.checkExpectedEdge==True:
            self.checkExpectedEdge=False
            
            if self.expectedHeading!=None:
                headingDiff=self.osmutils.headingDiffAbsolute(track, self.expectedHeading)
                if headingDiff>45:
                    print("current heading is too different to expected - try others")
                    self.expectedNextEdgeId=None
                    self.expectedHeading=None
                    self.currentPossibleEdgeList.clear()
                    self.approachingRef=None
                    # fallback to minDistance
                    return self.getEdgeIdOnPosForRoutingWOTrack(lat, lon, track, currentEdgeOnRoute, nextEdgeOnRoute, margin, fromMouse)

            edgeId, startRef, endRef, _, wayId, _, _, _, _=self.osmParserData.getEdgeEntryForEdgeId(self.expectedNextEdgeId)
            edgeId, wayId, refId, (lat1, lon1), country=self.checkForPosOnEdgeId(lat, lon, self.expectedNextEdgeId, startRef, endRef, wayId, maxDistance=10.0)
            
            self.expectedHeading=None
            self.expectedNextEdgeId=None
            self.currentPossibleEdgeList.clear()
            self.approachingRef=None
 
            if edgeId!=None:
                print("checked expected edge and use it")
                return edgeId, wayId, refId, (lat1, lon1), country
        
        usedEdgeId=None
        usedWayId=None
        usedRefId=None
        usedLat=None
        usedLon=None
        usedCountry=None
        
        self.currentSearchBBox=None
        nearCrossing=False
        
        # in routing mode us the next on the route as expected
        if nextEdgeOnRoute!=None:
            nextEdgeOnRoute, startRef, endRef, _, wayId, _, _, _, _=self.osmParserData.getEdgeEntryForEdgeId(nextEdgeOnRoute)
            usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry=self.checkForPosOnEdgeId(lat, lon, nextEdgeOnRoute, startRef, endRef, wayId, maxDistance=10.0)
            if usedEdgeId!=None:
                print("use nextEdgeId on route")
                self.expectedHeading=None
                self.expectedNextEdgeId=None
                self.currentPossibleEdgeList.clear()
                self.currentEdge=usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry
                return self.currentEdge

        # check current edge
        if currentEdgeOnRoute!=None:
            currentEdgeOnRoute, startRef, endRef, length, wayId, _, _, _, _=self.osmParserData.getEdgeEntryForEdgeId(currentEdgeOnRoute)
        
            if length<10.0:
                print("edge shorter then 10.0m - dont expect")
                self.expectedHeading=None
                self.expectedNextEdgeId=None
                self.currentPossibleEdgeList.clear()
                return self.getEdgeIdOnPosForRoutingWOTrack(lat, lon, track, currentEdgeOnRoute, nextEdgeOnRoute, margin, fromMouse)
            
            if self.expectedNextEdgeId==None:
                if self.approachingRef==None:
                    self.approachingRef=self.calcApproachingRef(lat, lon, startRef, endRef, track)
                
                distance=self.getDistanceFromPointToRef(lat, lon, self.approachingRef)

                if distance<50.0:
                    nearCrossing=True          
                    print("near a crossing to %d"%self.approachingRef)
  
                if nearCrossing==True:
                    # if no other edge is found keep the current one
                    # as long as possible
                    usedRefId=self.approachingRef
                    _, usedCountry=self.osmParserData.getCountryOfRef(self.approachingRef)
                    usedLat, usedLon=self.osmParserData.getCoordsWithRefAndCountry(self.approachingRef, usedCountry)
                    usedEdgeId=currentEdgeOnRoute
                    usedWayId=wayId
                    self.currentEdge=usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry
    
                else:
                    # are we on the same edge
                    # use larger maxDistance to compensate GPS differences
                    maxDistance=20.0                        
                    usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry=self.checkForPosOnEdgeId(lat, lon, currentEdgeOnRoute, startRef, endRef, wayId, maxDistance)
                    if usedEdgeId!=None:
                        print("use same edge")
                        self.expectedNextEdgeId=None
                        self.expectedHeading=None
                        self.currentPossibleEdgeList.clear()
                        self.approachingRef=None
                        self.currentEdge=usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry
                        return self.currentEdge
                        
            if self.expectedNextEdgeId!=None:
                if self.expectedHeading!=None:
                    headingDiff=self.osmutils.headingDiffAbsolute(track, self.expectedHeading)
                    if headingDiff>45:
                        print("current heading is too different to expected - try others")
                        self.expectedNextEdgeId=None
                        self.expectedHeading=None
                        self.currentPossibleEdgeList.clear()
                        self.approachingRef=None
                        # fallback to minDistance
                        return self.getEdgeIdOnPosForRoutingWOTrack(lat, lon, track, currentEdgeOnRoute, nextEdgeOnRoute, margin, fromMouse)

                edgeId, startRef, endRef, _, wayId, _, _, _, _=self.osmParserData.getEdgeEntryForEdgeId(self.expectedNextEdgeId)
                edgeId, wayId, refId, (lat1, lon1), country=self.checkForPosOnEdgeId(lat, lon, self.expectedNextEdgeId, startRef, endRef, wayId, maxDistance=10.0)

                if edgeId!=None:
                    print("use expected next edge")
                    self.checkExpectedEdge=True
                    self.approachingRef=None
                    return self.currentEdge
                else:
                    print("didnt took expected edge till now")
                    distance=self.getDistanceFromPointToRef(lat, lon, self.approachingRef)
                    if distance > 10.0:
                        print("too far from expected edge - try others")
                        self.expectedHeading=None
                        self.expectedNextEdgeId=None
                        self.currentPossibleEdgeList.clear()
                        self.approachingRef=None
                        # fallback to minDistance
                        return self.getEdgeIdOnPosForRoutingWOTrack(lat, lon, track, currentEdgeOnRoute, nextEdgeOnRoute, margin, fromMouse)

                    else:
                        return self.currentEdge
                
            # try edges starting or ending with this edge
            # use track == heading information
            possibleEdges=list()
            edgeHeadings=list()
            self.currentPossibleEdgeList.clear()
            self.expectedHeading=None
            
            # does not include currentEdgeOnRoute
            resultList=self.osmParserData.getDifferentEdgeEntryForStartOrEndPoint(self.approachingRef, currentEdgeOnRoute)
            if len(resultList)!=0: 
                for result in resultList:
                    nextEdgeId, startRef, endRef, _, wayId, _, _, _, _=result
                    edgeId, wayId, refId, (lat1, lon1), country=self.checkForPosOnEdgeIdStart(lat, lon, nextEdgeId, startRef, endRef, wayId, self.approachingRef, maxDistance=20.0)
                    if edgeId!=None:
                        if self.expectedNextEdgeId==edgeId:
                            continue

                        self.currentPossibleEdgeList.append(edgeId)

                        heading=self.getHeadingOnEdgeId(edgeId, self.approachingRef)
                        edgeHeadings.append(heading)
                        possibleEdges.append((edgeId, wayId, refId, (lat1, lon1), country))   

            if len(possibleEdges)!=0:
                if len(possibleEdges)==1:
                    print("only one possible next edge")
                    self.checkExpectedEdge=True
                    self.expectedNextEdgeId=possibleEdges[0][0]
                    return self.currentEdge
                
                maxHeadingDiff=360
                minHeadingEntry=None
                i=0
                for heading in edgeHeadings:
                    if heading!=None:
                        # use best matching heading
                        headingDiff=self.osmutils.headingDiffAbsolute(track, heading)
                        if headingDiff < maxHeadingDiff:
                            maxHeadingDiff=headingDiff
                            minHeadingEntry=i
                        
                    i=i+1
                if minHeadingEntry!=None:
                    if maxHeadingDiff>60:
                        print("heading diff > 60 - dont expect next edge")
                        self.expectedNextEdgeId=None
                        self.expectedHeading=None
                        self.currentPossibleEdgeList.clear()
                        self.approachingRef=None
                        # fallback to minDistance
                        return self.getEdgeIdOnPosForRoutingWOTrack(lat, lon, track, currentEdgeOnRoute, nextEdgeOnRoute, margin, fromMouse)
                    
                    else:
                        minHeadingDiff=edgeHeadings[minHeadingEntry]
                        for heading in edgeHeadings:
                            if heading!=None and heading!=minHeadingDiff:
                                headingDiff=self.osmutils.headingDiffAbsolute(minHeadingDiff, heading)
                                if headingDiff<15:
                                    print("heading diff < 15 - dont expect next edge")
                                    self.expectedNextEdgeId=None
                                    self.expectedHeading=None
                                    self.currentPossibleEdgeList.clear()
                                    self.approachingRef=None
                                    # fallback to minDistance
                                    return self.getEdgeIdOnPosForRoutingWOTrack(lat, lon, track, currentEdgeOnRoute, nextEdgeOnRoute, margin, fromMouse)
                         
                        self.expectedHeading=minHeadingDiff
                        self.expectedNextEdgeId=possibleEdges[minHeadingEntry][0]
                        return self.currentEdge           

        self.expectedNextEdgeId=None
        self.expectedHeading=None
        self.approachingRef=None
        self.currentPossibleEdgeList.clear()
        return self.getEdgeIdOnPosForRoutingWOTrack(lat, lon, track, currentEdgeOnRoute, nextEdgeOnRoute, margin, fromMouse)

    def getEdgeIdOnPosForRoutingWOTrack(self, lat, lon, track, currentEdgeOnRoute, nextEdgeOnRoute, margin, fromMouse):        
        usedEdgeId=None
        usedWayId=None
        usedRefId=None
        usedLat=None
        usedLon=None
        usedCountry=None
        
        self.currentSearchBBox=None
        
        # in routing mode us the next on the route as expected
        if nextEdgeOnRoute!=None:
            nextEdgeOnRoute, startRef, endRef, _, wayId, _, _, _, _=self.osmParserData.getEdgeEntryForEdgeId(nextEdgeOnRoute)
            usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry=self.checkForPosOnEdgeId(lat, lon, nextEdgeOnRoute, startRef, endRef, wayId, maxDistance=10.0)
            if usedEdgeId!=None:
                print("use nextEdgeId on route")
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
      
    # check all refs and find the nearest ref to pos
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
            mindistance=maxDistance
            lastRef=refList[0]
            for ref in refList[1:]:   
                _, refCountry=self.osmParserData.getCountryOfRef(ref)
                onLine, (tmpLat, tmpLon)=self.osmParserData.isOnLineBetweenRefs(lat, lon, ref, lastRef, maxDistance)
                if onLine==True:
                    distance=self.osmutils.distance(lat, lon, tmpLat, tmpLon)
                    if distance<mindistance:
                        mindistance=distance
                        usedEdgeId=edgeId
                        usedRefId=ref
                        usedWayId=wayId
                        usedLat=tmpLat
                        usedLon=tmpLon                            
                        usedCountry=refCountry

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
        if len(possibleEdges)==0:
            return None, None, otherNearHeading

        if len(possibleEdges)==1:
            expectedNextEdgeId=possibleEdges[0][0]
            nextEdgeLength=possibleEdges[0][1]
            return expectedNextEdgeId, nextEdgeLength, otherNearHeading
            
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
            for heading in edgeHeadings:
                if heading!=None and heading!=edgeHeadings[minHeadingEntry]:
                    headingDiff=self.osmutils.headingDiffAbsolute(edgeHeadings[minHeadingEntry], heading)
                    if headingDiff<45:
                        # next best heading is near to best matching
                        print("heading diff < 45 %f"%(headingDiff))
                        otherNearHeading=True

            expectedNextEdgeId=possibleEdges[minHeadingEntry][0]
            nextEdgeLength=possibleEdges[minHeadingEntry][1]
            return expectedNextEdgeId, nextEdgeLength, otherNearHeading

        return None, None, None
    
    def getBestMatchingOtherEdgeForHeading(self, lat, lon, possibleEdges, missedEdgeId, speed):
        for edgeId, _ in possibleEdges:
            if edgeId==missedEdgeId:
                continue
                        
            if self.checkEdgeDataForPos(lat, lon, edgeId, speed):
                return edgeId

        return None
    
    def getEdgeDataForRouting(self, crossingRef, edgeId):
        edgeId, _, _, _, wayId, _, _, _, _=self.osmParserData.getEdgeEntryForEdgeId(edgeId)
        _, country=self.osmParserData.getCountryOfRef(crossingRef)
        usedLat, usedLon=self.osmParserData.getCoordsWithRefAndCountry(crossingRef, country)
        return edgeId, wayId, crossingRef, (usedLat, usedLon), country

    def checkEdgeDataForPos(self, lat, lon, edgeId, speed):
        edgeId, startRef, endRef, length, wayId, _, _, _, _=self.osmParserData.getEdgeEntryForEdgeId(edgeId)
        if length<self.getCrossingCheckDistance(speed):
            return True
        
        maxDistance=10.0
        if self.otherNearHeading==True:
            maxDistance=5.0
            
        edgeId, wayId, _, _, _=self.checkForPosOnEdgeId(lat, lon, edgeId, startRef, endRef, wayId, maxDistance)
        return edgeId!=None
    
    def getEdgeIdOnPosForRoutingFallback(self, lat, lon, fromMouse, margin):
        if fromMouse==True:
            return self.osmParserData.getEdgeIdOnPos(lat, lon, margin)
        
        # use smaller search aerea
        return self.osmParserData.getEdgeIdOnPos(lat, lon, 0.001)
          
    def cleanEdgeCalculations(self):
        print("cleanEdgeCalculations")
        self.lastApproachingRef=self.approachingRef
        self.approachingRef=None
        self.currentPossibleEdgeList.clear()
        self.expectedNextEdgeId=None
        self.possibleEdges=None
        self.expectedEdgeTrigger=0
        self.lastDistance=None
        self.crossingPassed=False
        self.shortEdge=False
        self.lastExpectedNextEdgeId=None
        self.nextEdgeLength=None
        self.otherNearHeading=False
        self.checkCurrentEdge=True

    def getCrossingCheckDistance(self, speed):
        if speed < 30:
            return 30.0
        if speed < 50:
            return 40.0
        if speed < 80:
            return 50.0
        if speed < 100:
            return 60.0
        if speed > 100:
            return 70.0
        return 10.0
    
    def getEdgeConfirmedTriggerValue(self, speed):
        # wait longer until decision
        if self.otherNearHeading==True:
            if speed > 30:
                return 2
            return 4
        
        if speed > 30:
            return 1
        return 2
    
    def isShortEdgeForSpeed(self, length, speed):
        if length < SHORT_EDGE_LENGTH and speed > 30:
            return True
        return False
    
    def isPastCrossing(self, lat, lon, distance):
        if self.lastDistance==None:
            return False
            
        if distance <= self.lastDistance:
            self.lastDistance=distance
            return False

        # past crossing means > 5.0m past
        if distance > 5.0:
            print("past crossing > 5.0m")
            return True
        
        print("past crossing < 5.0m")
        return False
    
    def calcNextCrossingEdges(self, edgeId):
        print("calc next crossing edges at %d"%self.approachingRef)
        self.currentPossibleEdgeList.clear()
        self.possibleEdges, self.edgeHeadings=self.calcNextPossibleEdgesOnCrossing(self.approachingRef, edgeId)
        
    def calcNextEdgeValues(self, lat, lon, edgeId, track, speed):
        print("calc approachingRef")
        edgeId, startRef, endRef, length, _, _, _, _, _=self.osmParserData.getEdgeEntryForEdgeId(edgeId)

        self.approachingRef=self.calcApproachingRef(lat, lon, startRef, endRef, track)
        self.currentEdge=self.getEdgeDataForRouting(self.approachingRef, edgeId)
        
        distance=self.getDistanceFromPointToRef(lat, lon, self.approachingRef)
        self.lastDistance=distance
        self.crossingPassed=False
        
        print(length)
        if length<SHORT_EDGE_LENGTH:
            self.shortEdge=True
        else:
            self.shortEdge=False
                    
    def useNextEdge(self, lat, lon, track, speed, nextEdgeId):
        self.cleanEdgeCalculations()
        
        # immediately calc next crossing
        self.calcNextEdgeValues(lat, lon, nextEdgeId, track, speed)
        self.calcNextCrossingEdges(nextEdgeId)

        return self.currentEdge

    def getEdgeIdOnPosForRouting2(self, lat, lon, track, currentEdgeOnRoute, nextEdgeOnRoute, margin, fromMouse, speed):        
        if track==None:
            return self.getEdgeIdOnPosForRoutingWOTrack(lat, lon, track, currentEdgeOnRoute, nextEdgeOnRoute, margin, fromMouse)

        if currentEdgeOnRoute!=None:

            # check if we are still on the expected edge
            if self.expectedNextEdgeId==None and self.checkCurrentEdge==True:
                currentEdgeOnRoute, startRef, endRef, _, wayId, _, _, _, _=self.osmParserData.getEdgeEntryForEdgeId(currentEdgeOnRoute)
                edge=self.checkForPosOnEdgeId(lat, lon, currentEdgeOnRoute, startRef, endRef, wayId, maxDistance=20.0)
                if edge[0]==None:
                    print("lost current edge")
                    self.cleanEdgeCalculations()
                    self.lastApproachingRef=None         
                    return self.getEdgeIdOnPosForRoutingFallback(lat, lon, fromMouse, margin)

            if self.expectedNextEdgeId!=None:
                if self.crossingPassed==True:
                    print("crossing passed")
                    self.checkCurrentEdge=False
                    if len(self.possibleEdges)==1:
                        # only one possible edge
                        print("only one possible next edge")
                        return self.useNextEdge(lat, lon, track, speed, self.expectedNextEdgeId)
                    
                    if self.isShortEdgeForSpeed(self.nextEdgeLength, speed):
                        # short edge passed with speed - just use it
                        print("next edge is short edge and speed large - assume pass through")
                        return self.useNextEdge(lat, lon, track, speed, self.expectedNextEdgeId)
                    
                    if self.lastExpectedNextEdgeId==None:
                        self.lastExpectedNextEdgeId=self.expectedNextEdgeId
                        
                    if self.lastExpectedNextEdgeId!=self.expectedNextEdgeId:
                        self.lastExpectedNextEdgeId=self.expectedNextEdgeId
                        self.expectedEdgeTrigger=0
                        
                    if not self.checkEdgeDataForPos(lat, lon, self.expectedNextEdgeId, speed):
                        if self.expectedEdgeTrigger==self.getEdgeConfirmedTriggerValue(speed):
                            # something went wrong
                            # or we havnt reached the edge in the time
                            print("next edge not confirmed - fallback to other possible")
                            otherEdgeId=self.getBestMatchingOtherEdgeForHeading(lat, lon, self.possibleEdges, self.expectedNextEdgeId, speed)
                            if otherEdgeId==None:
                                self.cleanEdgeCalculations()
                                return self.getEdgeIdOnPosForRoutingFallback(lat, lon, fromMouse, margin)
                            else:
                                return self.useNextEdge(lat, lon, track, speed, otherEdgeId)
   
                        else:
                            # still chance to change next edge
                            print("confirm step failed %d"%self.expectedEdgeTrigger)
                            self.expectedEdgeTrigger=self.expectedEdgeTrigger+1
                    else:
                        if self.expectedEdgeTrigger==self.getEdgeConfirmedTriggerValue(speed):
                            print("pos on edge confirmed")
                            return self.useNextEdge(lat, lon, track, speed, self.expectedNextEdgeId)
                        else:
                            # still chance to change next edge
                            print("confirm step on edge %d"%self.expectedEdgeTrigger)
                            self.expectedEdgeTrigger=self.expectedEdgeTrigger+1
                else:
                    # still chance to change next edge
                    print("crossing not passed")
                    

            if self.approachingRef==None:
                self.calcNextEdgeValues(lat, lon, currentEdgeOnRoute, track, speed)

            distance=self.getDistanceFromPointToRef(lat, lon, self.approachingRef)

            if self.crossingPassed==False:
                if self.isPastCrossing(lat, lon, distance):
                    print("crossing passed")
                    self.crossingPassed=True
                    self.expectedEdgeTrigger=0
                    self.lastExpectedNextEdgeId=None
                    
                    if self.nextEdgeLength!=None and self.nextEdgeLength<SHORT_EDGE_LENGTH:
                        if len(self.possibleEdges)==1:
                            # only one possible edge
                            print("next edge is short edge and only one possible")
                            return self.useNextEdge(lat, lon, track, speed, self.possibleEdges[0][0])

            if self.possibleEdges==None:
                self.calcNextCrossingEdges(currentEdgeOnRoute)
                
                if self.shortEdge==True:
                    if len(self.possibleEdges)==1:
                        # only one possible edge
                        print("current edge is short and only one possible next edge")
                        return self.useNextEdge(lat, lon, track, speed, self.possibleEdges[0][0])
            
            if self.shortEdge==True or distance < self.getCrossingCheckDistance(speed) or self.expectedNextEdgeId!=None or self.crossingPassed==True: 
                print("check possible crossings - distance %d"%(distance))   
                expectedNextEdgeId, nextEdgeLength, otherNearHeading=self.getBestMatchingNextEdgeForHeading(track, self.possibleEdges, self.edgeHeadings)
                if expectedNextEdgeId!=None:
                    self.expectedNextEdgeId=expectedNextEdgeId
                    self.nextEdgeLength=nextEdgeLength
                    self.otherNearHeading=otherNearHeading
                    return self.currentEdge
            else:
                return self.currentEdge
                
        self.cleanEdgeCalculations()      
        self.lastApproachingRef=None         
        return self.getEdgeIdOnPosForRoutingFallback(lat, lon, fromMouse, margin)
