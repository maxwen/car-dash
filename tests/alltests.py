'''
Created on Feb 29, 2012

@author: maxl
'''

import unittest
from tests.crossings import *
from tests.routing import *

if __name__ == '__main__':
    suite=unittest.TestSuite()
    suite.addTest(crossingsSuite())
    suite.addTest(routingSuite())
    unittest.TextTestRunner(verbosity=2).run(suite)
