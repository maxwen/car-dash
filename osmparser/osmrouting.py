'''
Created on Feb 22, 2012

@author: maxl
'''

from osmparser.osmutils import OSMUtils

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
        self.currentEdge=None
        
    def getCurrentSearchEdgeList(self):
        return self.currentPossibleEdgeList
    
    def getExpectedNextEdge(self):
        return self.expectedNextEdgeId
    
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
            currentEdgeOnRoute, startRef, endRef, _, wayId, _, _, _, _=self.osmParserData.getEdgeEntryForEdgeId(currentEdgeOnRoute)
        
            if self.expectedNextEdgeId==None:
                if self.approachingRef==None:
                    # find the ref we are aproaching based on track
                    # since we ony check when coming to a crossing 
                    # but not on leaving
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
                        self.approachingRef=startRef
                    else:
                        self.approachingRef=endRef
                
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
                        return usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry
                        
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
    def checkForPosOnEdgeId(self, lat, lon, edgeId, startRef, endRef, wayId, maxDistance=10.0, offset=0.0):
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
            # use offset only for first and last ref
            for ref in refList[1:]: 
#                if i==0 or i==len(refList)-1:
#                    usedOffset=offset
#                else:
#                    usedOffset=0.0
                    
                _, refCountry=self.osmParserData.getCountryOfRef(ref)
                onLine, (tmpLat, tmpLon)=self.osmParserData.isOnLineBetweenRefs(lat, lon, ref, lastRef, maxDistance, offset)
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
#                    print("using edge %d"%(edgeId))

                lastRef=ref  
                i=i+1
        return usedEdgeId, usedWayId, usedRefId, (usedLat, usedLon), usedCountry

    # check first two refs - used on crossings
    # filters out impossible oneways
    def checkForPosOnEdgeIdStart(self, lat, lon, edgeId, startRef, endRef, wayId, crossingRef, maxDistance=10.0, offset=0.0):
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
        if oneway and startRef!=crossingRef:
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
            onLine, (tmpLat, tmpLon)=self.osmParserData.isOnLineBetweenRefs(lat, lon, ref1, ref2, maxDistance, offset)
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
            if self.osmutils.distance(lat1, lon1, lat2, lon2)>5.0:
                break

#        print("getHeadingBetweenPoints:%d"%self.osmutils.distance(lat1, lon1, lat2, lon2))
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
        nodes=self.osmutils.createTemporaryPoint(lat1, lon1, lat2, lon2, offset)
        minDistance=maxDistance
        for tmpLat, tmpLon in nodes:
            distance=self.osmutils.distance(lat, lon, tmpLat, tmpLon)
            if distance<minDistance:
                return True
        
        return False