'''
Created on Dec 22, 2011

@author: maxl
'''

import math
import time

TILESIZE=256
M_LN2=0.69314718055994530942    #log_e 2
RADIUS_EARTH = 6371
PI2=2*math.pi

class OSMUtils():
    def deg2rad(self, deg):
        return math.radians(deg)

    def rad2deg(self,  rad):
        return math.degrees(rad)

    def lat2pixel(self, zoom, lat):
        lat_m = math.atanh(math.sin(lat))
        # the formula is
        #
        # pixel_y = -(2^zoom * TILESIZE * lat_m) / 2PI + (2^zoom * TILESIZE) / 2
        #
        z=(1 << zoom)
        pixel_y = -(lat_m * TILESIZE * z ) / PI2 +(z * TILESIZE)/2

        return pixel_y

    def lon2pixel(self, zoom, lon):
        #the formula is
        #
        # pixel_x = (2^zoom * TILESIZE * lon) / 2PI + (2^zoom * TILESIZE) / 2
        #
        z=(1 << zoom)
        pixel_x = ( lon * TILESIZE * z ) / PI2 +(z * TILESIZE)/2
        return pixel_x

    def pixel2lon(self, zoom, pixel_x):
        z=math.exp(zoom * M_LN2)
        lon = (((pixel_x - ( z * (TILESIZE/2) ) ) * PI2) / (TILESIZE * z ))
        return lon

    def pixel2lat(self, zoom, pixel_y):
        z=math.exp(zoom * M_LN2)
        lat_m = ((-( pixel_y - ( z * (TILESIZE/2) ) ) * PI2) /(TILESIZE * z))
        lat = math.asin(math.tanh(lat_m))
        return lat
        
    def distance(self,  lat1, lon1, lat2, lon2 ):
        lat1 = self.deg2rad(lat1)
        lon1 = self.deg2rad(lon1)
        lat2 = self.deg2rad(lat2)
        lon2 = self.deg2rad(lon2)
        
        return self.distanceRad(lat1, lon1, lat2, lon2)

    def distanceRad(self,  lat1, lon1, lat2, lon2 ):
        return int(self.distanceRadRad(lat1, lon1, lat2, lon2) * RADIUS_EARTH *1000)

    def distanceRadRad(self,  lat1, lon1, lat2, lon2 ):
        x = (lon2-lon1) * math.cos((lat1+lat2)/2)
        y = (lat2-lat1)
        return math.sqrt(x*x + y*y)
    
    def linepart(self, lat1, lon1, lat2,  lon2, frac):
        lat1 = self.deg2rad(lat1)
        lon1 = self.deg2rad(lon1)
        lat2 = self.deg2rad(lat2)
        lon2 = self.deg2rad(lon2)
        
        d=self.distanceRadRad(lat1, lon1, lat2, lon2)
        sinD=math.sin(d)
        return self.linepartRad(lat1, lon1, lat2, lon2, d, sinD, frac)

    def linepartRad(self, lat1, lon1, lat2,  lon2, d, sinD, frac):        
        A=math.sin((1-frac)*d)/sinD
        B=math.sin(frac*d)/sinD
        x = A*math.cos(lat1)*math.cos(lon1) +  B*math.cos(lat2)*math.cos(lon2)
        y = A*math.cos(lat1)*math.sin(lon1) +  B*math.cos(lat2)*math.sin(lon2)
        z = A*math.sin(lat1)           +  B*math.sin(lat2)
        lat=math.atan2(z,math.sqrt(x*x+y*y))
        lon=math.atan2(y,x)

        return (self.rad2deg(lat), self.rad2deg(lon))
    
    def heading(self, lat1, lon1, lat2, lon2 ):
        lat1 = self.deg2rad(lat1)
        lon1 = self.deg2rad(lon1)
        lat2 = self.deg2rad(lat2)
        lon2 = self.deg2rad(lon2)
        
        return self.headingRad(lat1, lon1, lat2, lon2)

    def headingRad(self, lat1, lon1, lat2, lon2 ):        
        v1 = math.sin(lon1 - lon2) * math.cos(lat2)
        v2 = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lon1 - lon2)
        if abs(v1) < 1e-15:
            v1 = 0.0
        if abs(v2) < 1e-15:
            v2 = 0.0
        return math.atan2(v1, v2)
    
    def headingDegrees(self,  lat1,  lon1,  lat2,  lon2):
        h = 360.0 - self.rad2deg(self.heading(lat1, lon1, lat2, lon2))
        if h >= 360.0:
            h -= 360.0
        return int(h)
    
    def headingDegreesRad(self,  lat1,  lon1,  lat2,  lon2):
        h = 360.0 - self.rad2deg(self.headingRad(lat1, lon1, lat2, lon2))
        if h >= 360.0:
            h -= 360.0
        return int(h)
    
    def headingDiffAbsolute(self, heading1, heading2):
        return abs((heading1 + 180 -  heading2) % 360 - 180);
       
    def headingDiff(self, heading1, heading2):
        diff=heading1 - heading2+180
        return diff%360
    
    def azimuth(self, crossPoint, fromPoint, toPoint):
        fromDegree=int(self.headingDegrees(fromPoint[0], fromPoint[1], crossPoint[0], crossPoint[1]))
        toDegree=int(self.headingDegrees(crossPoint[0], crossPoint[1], toPoint[0], toPoint[1]))
        return self.headingDiff(fromDegree, toDegree)

    def direction(self, azimuth):
        if azimuth>=1 and azimuth<50:
            return 3
        if azimuth>=50 and azimuth<100:
            return 2
        if azimuth>=100 and azimuth<175:
            return 1
        if azimuth>=175 and azimuth<185:
            return 0
        if azimuth>=185  and azimuth<250:
            return -1
        if azimuth>=250 and azimuth<300:
            return -2
        if azimuth>=300 and azimuth<359:
            return -3
        return 43
    
    def directionName(self, direction):
        if direction==0:
            return "straight"
        if direction==-3:
            return "hard left"
        if direction==-2:
            return "left"
        if direction==-1:
            return "easy left"
        if direction==1:
            return "easy right"
        if direction==2:
            return "right"
        if direction==3:
            return "hard right"
        if direction==39:
            return "motorway exit"
        if direction==40:
            return "roundabout enter"
        if direction==41:
            return "roundabout exit"
        if direction==98:
            return "u-turn"
        if direction==99:
            return "end"
        return "unknown" 

    def createTemporaryPoints(self, lat1, lon1, lat2, lon2, frac=10.0, offsetStart=0.0, offsetEnd=0.0, addStart=True, addEnd=True):
        rlat1 = self.deg2rad(lat1)
        rlon1 = self.deg2rad(lon1)
        rlat2 = self.deg2rad(lat2)
        rlon2 = self.deg2rad(lon2)
        
        rDistance=self.distanceRadRad(rlat1, rlon1, rlat2, rlon2)  
        sinD=math.sin(rDistance)  
        distance=int(rDistance * RADIUS_EARTH *1000)
        
        pointsToIgnoreStart=0
        pointsToIgnoreEnd=0
        
        if offsetStart!=0.0:
            pointsToIgnoreStart=int(offsetStart/frac)
        if offsetEnd!=0.0:
            pointsToIgnoreEnd=int(offsetEnd/frac)
       
        pointsToCreate=int(distance/frac)

        points=list()
        if offsetStart==0.0 and addStart==True:
            points.append((lat1, lon1))
        if distance>frac:
            doneDistance=0
            i=0
            while doneDistance<distance:
                newLat, newLon=self.linepartRad(rlat1, rlon1, rlat2, rlon2, rDistance, sinD, doneDistance/distance)
                if pointsToIgnoreStart!=0:
                    if i>pointsToIgnoreStart:
                        points.append((newLat, newLon))
                if pointsToIgnoreEnd!=0:
                    if i<pointsToCreate-pointsToIgnoreEnd:
                        points.append((newLat, newLon))
                else:
                    points.append((newLat, newLon))
                    
                doneDistance=doneDistance+frac
                i=i+1
        if offsetEnd==0.0 and addEnd==True:
            points.append((lat2, lon2))

#        print("%d %s %d"%(pointsToCreate, str(pointsToIgnore), len(points)))
        return points
            
    def degToMeter(self, meter):
        deg_to_meter = (40000 * 1000) / 360
        return meter / deg_to_meter
    
    def mod(self, y, x):
        return y - x*math.floor(y/x)
    
#     lat=asin(sin(lat1)*cos(d)+cos(lat1)*sin(d)*cos(tc))
#     IF (cos(lat)=0)
#        lon=lon1      // endpoint a pole
#     ELSE
#        lon=mod(lon1+asin(sin(tc)*sin(d)/cos(lat))+pi,2*pi)-pi
#     ENDIF
    def getPosInDistanceAndTrack(self, lat1, lon1, distance, track):
        trackRad=self.deg2rad(track)
        distanceRad=(distance/(RADIUS_EARTH *1000))
        rLat1=self.deg2rad(lat1)
        rLon1=self.deg2rad(lon1)
        lat=math.asin(math.sin(rLat1)*math.cos(distanceRad)+math.cos(rLat1)*math.sin(distanceRad)*math.cos(trackRad))
        if math.cos(lat)==0:
            lon=rLon1
        else:
            lon=self.mod(rLon1+math.asin(math.sin(trackRad)*math.sin(distanceRad)/math.cos(rLat1))+math.pi, 2*math.pi)-math.pi
     
        return (self.rad2deg(lat), self.rad2deg(lon))

    def getPosInDistanceAndTrackRad(self, rLat1, rLon1, distance, track):
        trackRad=self.deg2rad(track)
        distanceRad=(distance/(RADIUS_EARTH *1000))
        lat=math.asin(math.sin(rLat1)*math.cos(distanceRad)+math.cos(rLat1)*math.sin(distanceRad)*math.cos(trackRad))
        if math.cos(lat)==0:
            lon=rLon1
        else:
            lon=self.mod(rLon1+math.asin(math.sin(trackRad)*math.sin(distanceRad)/math.cos(rLat1))+math.pi, 2*math.pi)-math.pi
     
        return (self.rad2deg(lat), self.rad2deg(lon))
    
def main():    
#    # 841947t38 
#    #47.802747-13.029014 47.802747-13.029014 47.803394-13.028636
#
#    latCross=47.8027471
#    lonCross=13.0290138
#    
#    # 455994015
#    latFrom=47.8029724
#    lonFrom=13.0299361
#    
#    # rechts 11840580
#    latRight=47.8033938
#    lonRight=13.028636
#    
#    #links 336748981
#    latLeft=47.8020688
#    lonLeft=13.0294019
#    
#    # gerade 84194737
#    latStraight=47.8026081
#    lonStraight=13.0284631
#    
    osmutils=OSMUtils()
#
#    # coming from right
#    print(osmutils.azimuth((latCross, lonCross), (latFrom, lonFrom), (latRight, lonRight)))
#    print(osmutils.azimuth((latCross, lonCross), (latFrom, lonFrom), (latStraight, lonStraight)))
#    print(osmutils.azimuth((latCross, lonCross), (latFrom, lonFrom), (latLeft, lonLeft)))
# 
#    # comming from top
#    print(osmutils.azimuth((latCross, lonCross), (latRight, lonRight), (latStraight, lonStraight)))
#    print(osmutils.azimuth((latCross, lonCross), (latRight, lonRight), (latLeft, lonLeft)))
#    print(osmutils.azimuth((latCross, lonCross), (latRight, lonRight), (latFrom, lonFrom)))
#
#    # comming from left
#    print(osmutils.azimuth((latCross, lonCross), (latStraight, lonStraight), (latLeft, lonLeft)))
#    print(osmutils.azimuth((latCross, lonCross), (latStraight, lonStraight), (latFrom, lonFrom)))
#    print(osmutils.azimuth((latCross, lonCross), (latStraight, lonStraight), (latRight, lonRight)))
#
#    # comming from down
#    print(osmutils.azimuth((latCross, lonCross), (latLeft, lonLeft), (latFrom, lonFrom)))
#    print(osmutils.azimuth((latCross, lonCross), (latLeft, lonLeft), (latRight, lonRight)))
#    print(osmutils.azimuth((latCross, lonCross), (latLeft, lonLeft), (latStraight, lonStraight)))
#
    latCross=47.8380837
    lonCross=12.9875343
    
    latFrom=47.8387129
    lonFrom=12.9882358
    
    latTo=47.8383155
    lonTo=12.9885131
#    
#    print(osmutils.azimuth((latCross, lonCross), (latFrom, lonFrom), (latTo, lonTo)))

#    print(osmutils.headingDiffAbsolute(90, 90))
#    print(osmutils.headingDiffAbsolute(180, 181))
#    print(osmutils.headingDiffAbsolute(181, 180))
#    print(osmutils.headingDiffAbsolute(360, 360))
#    print(osmutils.headingDiffAbsolute(320, 20))
#    print(osmutils.headingDiffAbsolute(20, 320))
#    print(osmutils.headingDiffAbsolute(45, 270))
#    print(osmutils.headingDiffAbsolute(270, 45))

#    start=time.time()
    print("from %f %f"%(latFrom, lonFrom))
    print("to %f %f"%(latTo, lonTo))

    distance=osmutils.distance(latFrom, lonFrom, latTo, lonTo)
    headingDeg=osmutils.headingDegrees(latFrom, lonFrom, latTo, lonTo)
    print("heading %d"%(headingDeg))
    lat1, lon1=osmutils.getPosInDistanceAndTrack(latFrom, lonFrom, distance, headingDeg)
    
    print("%f %f"%(lat1, lon1))
    
    rLatFrom = osmutils.deg2rad(latFrom)
    rLonFrom = osmutils.deg2rad(lonFrom)
    rLatTo = osmutils.deg2rad(latTo)
    rLonTo = osmutils.deg2rad(lonTo)
    headingRad=osmutils.headingRad(rLatFrom, rLonFrom, rLatTo, rLonTo)
    distanceRad=osmutils.distanceRadRad(rLatFrom, rLonFrom, rLatTo, rLonTo)
    lat1, lon1=osmutils.getPosInDistanceAndTrackRad(rLatFrom, rLonFrom, distance, headingDeg)
    
    print("%f %f"%(lat1, lon1))

    
#    for i in range(0, 100000):
#        osmutils.distance(latFrom, lonFrom, latTo, lonTo)
#    print("distance:%f"%(time.time()-start))
#    
#    start=time.time()
#    print(osmutils.distance1(latFrom, lonFrom, latTo, lonTo))
#    for i in range(0, 100000):
#        osmutils.distance1(latFrom, lonFrom, latTo, lonTo)
#    print("distance1:%f"%(time.time()-start))
#
#    start=time.time()
#    print(osmutils.linepart(latFrom, lonFrom, latTo, lonTo, 0.5))
#    for i in range(0, 100000):
#        osmutils.linepart(latFrom, lonFrom, latTo, lonTo, 0.5)
#    print("linepart:%f"%(time.time()-start))
#
#    start=time.time()
#    print(osmutils.linepart1(latFrom, lonFrom, latTo, lonTo, 0.5))
#    for i in range(0, 100000):
#        osmutils.linepart1(latFrom, lonFrom, latTo, lonTo, 0.5)
#    print("linepart1:%f"%(time.time()-start))
#        
#    start=time.time()
#    print(osmutils.createTemporaryPoints(latFrom, lonFrom, latTo, lonTo, 0.1))
#    print("createTemporaryPoints:%f"%(time.time()-start))
#    
#    start=time.time()
#    print(osmutils.createTemporaryPoints1(latFrom, lonFrom, latTo, lonTo, 0.1))
#    print("createTemporaryPoints1:%f"%(time.time()-start))
    
if __name__ == "__main__":
    main()  


                                   