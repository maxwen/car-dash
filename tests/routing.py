'''
Created on Feb 29, 2012

@author: maxl
'''

import unittest
from osmparser.osmparserdata import OSMParserData, OSMRoute
from config import Config

class RoutingTest(unittest.TestCase):          
    def setUp(self):
        self.p=OSMParserData()
        self.p.initDB()
        self.p.openAllDB()
        
    def tearDown(self):
        self.p.closeAllDB()
        
    def testBasicRouting(self):
#50796
#305151
#[50796, 50795, 50794, 732440, 732441, 423974, 423970, 423969, 423968, 423967, 423966, 423965, 423964, 423963, 423962, 491407, 492733, 2102, 2101, 2100, 2099, 2098, 2097, 2096, 734959, 734958, 677523, 67758, 67759, 677522, 462799, 462800, 462811, 462810, 462801, 462818, 462809, 462814, 2079, 2078, 462805, 462804, 462797, 639903, 639901, 462796, 462798, 462817, 462816, 462815, 462795, 2074, 2073, 462842, 462841, 462832, 462840, 462839, 661905, 661906, 462838, 462837, 462836, 462835, 462834, 462833, 305151]
#67  
        edgeList, cost=self.p.calcRouteForEdges(50796, 305151, 1.0, 1.0)
        self.assertTrue(edgeList!=None and cost!=None, "routing failed")
        self.assertTrue(len(edgeList)==67, "path length does not match expected")

    def loadTestRoutes(self):    
        config=Config("osmtestroutes.cfg")
                
        section="route"
        routeList=list()
        if config.hasSection(section):
            for name, value in config.items(section):
                if name[:5]=="route":
                    route=OSMRoute()
                    route.readFromConfig(value)
                    routeList.append(route)   
        return routeList
    
    def testRoutes(self):
        routeList=self.loadTestRoutes()
        for route in routeList:
            print(route)
            route.resolveRoutingPoints(self.p)
            route.calcRoute(self.p)
            self.assertTrue(route.getEdgeList()!=None, "routing %s failed"%route)
            if route.getEdgeList()!=None:
                print(route.getEdgeList())
                
def routingSuite():
    suite = unittest.TestSuite()
    suite.addTest(RoutingTest('testBasicRouting'))
    suite.addTest(RoutingTest('testRoutes'))
    return suite

if __name__ == '__main__':
    unittest.main()