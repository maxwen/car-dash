'''
Created on Dec 22, 2011

@author: maxl
'''

import math

TILESIZE=256
M_LN2=0.69314718055994530942    #log_e 2
RADIUS_EARTH = 6371

class OSMUtils():
    def deg2rad(self, deg):
        return (deg * math.pi / 180.0)

    def rad2deg(self,  rad):
        return (rad / math.pi * 180.0)

    def lat2pixel(self, zoom, lat):
        lat_m = math.atanh(math.sin(lat))
        # the formula is
        #
        # pixel_y = -(2^zoom * TILESIZE * lat_m) / 2PI + (2^zoom * TILESIZE) / 2
        #
        pixel_y = -(lat_m * TILESIZE * (1 << zoom) ) / (2*math.pi) +((1 << zoom) * TILESIZE)/2

        return pixel_y

    def lon2pixel(self, zoom, lon):
        #the formula is
        #
        # pixel_x = (2^zoom * TILESIZE * lon) / 2PI + (2^zoom * TILESIZE) / 2
        #
        pixel_x = ( lon * TILESIZE * (1 << zoom) ) / (2*math.pi) +((1 << zoom) * TILESIZE)/2
        return pixel_x

    def pixel2lon(self, zoom, pixel_x):
        lon = (((pixel_x - ( math.exp(zoom * M_LN2) * (TILESIZE/2) ) ) *2*math.pi) / 
            (TILESIZE * math.exp(zoom * M_LN2) ))
        return lon

    def pixel2lat(self, zoom, pixel_y):
        lat_m = ((-( pixel_y - ( math.exp(zoom * M_LN2) * (TILESIZE/2) ) ) * (2*math.pi)) /
            (TILESIZE * math.exp(zoom * M_LN2)))

        lat = math.asin(math.tanh(lat_m))
        return lat
    
    def distance(self, oldLat, oldLon, newLat, newLon):
        dLat = self.deg2rad(oldLat-newLat)
        dLon = self.deg2rad(oldLon-newLon)
        lat1 = self.deg2rad(oldLat)
        lat2 = self.deg2rad(newLat)

        a = math.pow(math.sin(dLat/2), 2) + math.pow(math.sin(dLon/2),2) * math.cos(lat1) * math.cos(lat2) 
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        d = (RADIUS_EARTH * c)*1000
        return d
    
 
    def crossproduct(self, x1, y1, z1, x2, y2, z2):
        xa = y1*z2-y2*z1
        ya = z1*x2-z2*x1
        za = x1*y2-y1*x2
        return (xa, ya, za)

    def dotproduct(self, x1, y1, z1, x2, y2, z2 ):
        return (x1*x2+y1*y2+z1*z2);
    
    #  Compute the position of a point partially along the geodesic from 
    #  lat1,lon1 to lat2,lon2
    #  
    #  Ref: http://mathworld.wolfram.com/RotationFormula.html
    
    def linepart(self, lat1, lon1, lat2,  lon2, frac):
        x1=0.0
        y1=0.0
        z1=0.0
        x2=0.0
        y2=0.0
        z2=0.0
        xa=0.0
        ya=0.0
        za=0.0
        la=0.0
        xr=0.0
        yr=0.0
        zr=0.0
        xx=0.0
        yx=0.0
        zx=0.0
        reslat=0.0
        reslon=0.0
        theta = 0.0
        phi = 0.0
        cosphi = 0.0
        sinphi = 0.0
        
          
        lat1 = self.deg2rad(lat1)
        lon1 = self.deg2rad(lon1)
        lat2 = self.deg2rad(lat2)
        lon2 = self.deg2rad(lon2)
        
        x1 = math.cos(lon1)*math.cos(lat1)
        y1 = math.sin(lat1)
        z1 = math.sin(lon1)*math.cos(lat1)
        x2 = math.cos(lon2)*math.cos(lat2) 
        y2 = math.sin(lat2)
        z2 = math.sin(lon2)*math.cos(lat2)
        
        (xa, ya, za)=self.crossproduct( x1, y1, z1, x2, y2, z2)
        la = math.sqrt(xa*xa+ya*ya+za*za)
        
        if la!=0.0:
            xa=xa/la
            ya=ya/la
            za=za/la
          
        if la!=0.0:
            (xx, yx, zx)=self.crossproduct( x1, y1, z1, xa, ya, za)
           
            theta = math.atan2( self.dotproduct(xx,yx,zx,x2,y2,z2),
                   self.dotproduct(x1,y1,z1,x2,y2,z2))
            
            phi = frac * theta
            cosphi = math.cos(phi)
            sinphi = math.sin(phi)
            
            
            xr = x1*cosphi + xx * sinphi
            yr = y1*cosphi + yx * sinphi
            zr = z1*cosphi + zx * sinphi
            
            if xr > 1:
                xr = 1
            if xr < -1: 
                xr = -1
            if yr > 1:
                yr = 1
            if yr < -1: 
                yr = -1
            if zr > 1:
                zr = 1
            if zr < -1:
                zr = -1
            
            reslat = self.rad2deg(math.asin(yr))
            if xr == 0 and zr == 0:
                reslon = 0.0;
            else:
                reslon = self.rad2deg(math.atan2( zr, xr ))
            
        return (reslat, reslon)
    
    def heading(self, lat1, lon1, lat2, lon2 ):
        lat1 = self.deg2rad(lat1)
        lon1 = self.deg2rad(lon1)
        lat2 = self.deg2rad(lat2)
        lon2 = self.deg2rad(lon2)
        
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
        return h;
    
    def azimuth(self, crossPoint, fromPoint, toPoint):
        fromDegree=int(self.headingDegrees(fromPoint[0], fromPoint[1], crossPoint[0], crossPoint[1]))
        toDegree=int(self.headingDegrees(crossPoint[0], crossPoint[1], toPoint[0], toPoint[1]))
        diff=fromDegree - toDegree+180
        return diff%360

    def direction(self, azimuth):
        # 45 to 135=right=1
        # 135 to 225=straight=0
        # 225 to 315=left=-1

        if azimuth>=0 and azimuth<135:
            return 1
        if azimuth>=135 and azimuth<225:
            return 0
        if azimuth>=225 and azimuth<360:
            return -1
#        if azimuth>=0 and azimuth<45:
#            return 1
#        if azimuth>=315 and azimuth<360:
#            return -1

def main():    
    # 84194738 
    #47.802747-13.029014 47.802747-13.029014 47.803394-13.028636

    latCross=47.8027471
    lonCross=13.0290138
    
    # 455994015
    latFrom=47.8029724
    lonFrom=13.0299361
    
    # rechts 11840580
    latRight=47.8033938
    lonRight=13.028636
    
    #links 336748981
    latLeft=47.8020688
    lonLeft=13.0294019
    
    # gerade 84194737
    latStraight=47.8026081
    lonStraight=13.0284631
    
    osmutils=OSMUtils()

    # coming from right
    print(osmutils.azimuth((latCross, lonCross), (latFrom, lonFrom), (latRight, lonRight)))
    print(osmutils.azimuth((latCross, lonCross), (latFrom, lonFrom), (latStraight, lonStraight)))
    print(osmutils.azimuth((latCross, lonCross), (latFrom, lonFrom), (latLeft, lonLeft)))
 
    # comming from top
    print(osmutils.azimuth((latCross, lonCross), (latRight, lonRight), (latStraight, lonStraight)))
    print(osmutils.azimuth((latCross, lonCross), (latRight, lonRight), (latLeft, lonLeft)))
    print(osmutils.azimuth((latCross, lonCross), (latRight, lonRight), (latFrom, lonFrom)))

    # comming from left
    print(osmutils.azimuth((latCross, lonCross), (latStraight, lonStraight), (latLeft, lonLeft)))
    print(osmutils.azimuth((latCross, lonCross), (latStraight, lonStraight), (latFrom, lonFrom)))
    print(osmutils.azimuth((latCross, lonCross), (latStraight, lonStraight), (latRight, lonRight)))

    # comming from down
    print(osmutils.azimuth((latCross, lonCross), (latLeft, lonLeft), (latFrom, lonFrom)))
    print(osmutils.azimuth((latCross, lonCross), (latLeft, lonLeft), (latRight, lonRight)))
    print(osmutils.azimuth((latCross, lonCross), (latLeft, lonLeft), (latStraight, lonStraight)))

    latCross=47.8380837
    lonCross=12.9875343
    
    latFrom=47.8387129
    lonFrom=12.9882358
    
    latTo=47.8383155
    lonTo=12.9885131
    
    print(osmutils.azimuth((latCross, lonCross), (latFrom, lonFrom), (latTo, lonTo)))

if __name__ == "__main__":
    main()  


                                   