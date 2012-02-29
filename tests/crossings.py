'''
Created on Feb 29, 2012

@author: maxl
'''

import unittest
from osmparser.osmparserdata import OSMParserData

class CrossingTest(unittest.TestCase):          
    def setUp(self):
        self.p=OSMParserData()
        self.p.initDB()
        self.p.openAllDB()
        
    def tearDown(self):
        self.p.closeAllDB()
        
    def testRoundaboutExit(self):
        self.p.setDBCursorForCountry(0)
        self.p.cursor.execute('SELECT * from crossingTable WHERE wayId=11165735')
        allentries=self.p.cursor.fetchall()
        self.assertTrue(len(allentries)==3, "to few crossings")
        for x in allentries:
            (crossingEntryId, wayid, refId, nextWayIdList)=self.p.crossingFromDB(x)
            if refId==11840512:
                nextWayId, crossingType, crossingInfo=nextWayIdList[0]
                self.assertTrue(nextWayId==27206728 and crossingType==4, "roundabout exit not set")
            if refId==11840534:
                nextWayId, crossingType, crossingInfo=nextWayIdList[0]
                self.assertTrue(nextWayId==10711424 and crossingType==42, "no exit roundabout not set")

def crossingsSuite():
    suite = unittest.TestSuite()
    suite.addTest(CrossingTest('testRoundaboutExit'))
    return suite
    
if __name__ == '__main__':
    unittest.main()