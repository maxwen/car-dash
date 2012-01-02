from igraph import *
from igraph.compat import isnan
import testcase

class PathTests():
    def testShortestPaths(self):
        g = Graph(10, [(0,1), (0,2), (0,3), (1,2), (1,4), (1,5), (2,3), (2,6), \
            (3,2), (3,6), (4,5), (4,7), (5,6), (5,8), (5,9), (7,5), (7,8), \
            (8,9), (5,2), (2,1)], directed=True)
        ws = [0,2,1,0,5,2,1,1,0,2,2,8,1,1,3,1,1,4,2,1]
        g.es["weight"] = ws
        inf = float('inf')
        expected = [
          [0, 0, 0, 1, 5, 2, 1, 13, 3, 5],
          [inf, 0, 0, 1, 5, 2, 1, 13, 3, 5],
          [inf, 1, 0, 1, 6, 3, 1, 14, 4, 6],
          [inf, 1, 0, 0, 6, 3, 1, 14, 4, 6],
          [inf, 5, 4, 5, 0, 2, 3, 8, 3, 5],
          [inf, 3, 2, 3, 8, 0, 1, 16, 1, 3],
          [inf, inf, inf, inf, inf, inf, 0, inf, inf, inf],
          [inf, 4, 3, 4, 9, 1, 2, 0, 1, 4],
          [inf, inf, inf, inf, inf, inf, inf, inf, 0, 4],
          [inf, inf, inf, inf, inf, inf, inf, inf, inf, 0]
        ]
        self.failUnless(g.shortest_paths(weights=ws) == expected)
        self.failUnless(g.shortest_paths(weights="weight") == expected)
        self.failUnless(g.shortest_paths(weights="weight", target=[2,3]) ==
                [row[2:4] for row in expected])

    def testGetShortestPaths(self):
        g = Graph(4, [(0,1), (0,2), (1,3), (3,2), (2,1)], directed=True)
        sps = g.get_shortest_paths(0)
        expected = [[0], [0, 1], [0, 2], [0, 1, 3]]
        self.failUnless(sps == expected)
        sps = g.get_shortest_paths(0, output="vpath")
        expected = [[0], [0, 1], [0, 2], [0, 1, 3]]
        self.failUnless(sps == expected)
        sps = g.get_shortest_paths(0, output="epath")
        expected = [[], [0], [1], [0, 2]]
        self.failUnless(sps == expected)
        self.assertRaises(ValueError, g.get_shortest_paths, 0, output="x")

    def testGetAllShortestPaths(self):
        g = Graph(4, [(0,1), (1, 2), (1, 3), (2, 4), (3, 4), (4, 5)], directed=True)

        sps = sorted(g.get_all_shortest_paths(0, 5))
        expected = [[0, 1, 2, 4, 5], [0, 1, 3, 4, 5]]
        self.failUnless(sps == expected)

        sps = sorted(g.get_all_shortest_paths(1, 4))
        expected = [[1, 2, 4], [1, 3, 4]]
        self.failUnless(sps == expected)

        g = Graph.Lattice([5, 5], circular=False)
        
        sps = sorted(g.get_all_shortest_paths(0, 12))
        expected = [[0, 1, 2, 7, 12], [0, 1, 6, 7, 12], [0, 1, 6, 11, 12], \
                    [0, 5, 6, 7, 12], [0, 5, 6, 11, 12], [0, 5, 10, 11, 12]]
        self.failUnless(sps == expected)

        g = Graph.Lattice([100, 100], circular=False)
        sps = sorted(g.get_all_shortest_paths(0, 202))
        expected = [[0, 1, 2, 102, 202], [0, 1, 101, 102, 202], [0, 1, 101, 201, 202], \
                    [0, 100, 101, 102, 202], [0, 100, 101, 201, 202], [0, 100, 200, 201, 202]]
        self.failUnless(sps == expected)

        g = Graph.Lattice([100, 100], circular=False)
        sps = sorted(g.get_all_shortest_paths(0, [0, 202]))
        self.failUnless(sps == [[0]] + expected)

        g = Graph([(0,1), (1,2), (0,2)])
        g.es["weight"] = [0.5, 0.5, 1]
        sps = sorted(g.get_all_shortest_paths(0, weights="weight"))
        self.failUnless(sps == [[0], [0,1], [0,1,2], [0,2]])

        g = Graph.Lattice([4, 4], circular=False)
        g.es["weight"] = 1
        g.es[2,8]["weight"] = 100
        sps = sorted(g.get_all_shortest_paths(0, [3, 12, 15], weights="weight"))
        self.failUnless(len(sps) == 20)
        self.failUnless(sum(1 for path in sps if path[-1] == 3) == 4)
        self.failUnless(sum(1 for path in sps if path[-1] == 12) == 4)
        self.failUnless(sum(1 for path in sps if path[-1] == 15) == 12)


    def testPathLengthHist(self):
        g = Graph.Tree(15, 2)
        h = g.path_length_hist()
        self.failUnless(h.unconnected == 0L)
        self.failUnless([(int(l),x) for l,_,x in h.bins()] == \
          [(1,14),(2,19),(3,20),(4,20),(5,16),(6,16)])
        g = Graph.Full(5)+Graph.Full(4)
        h = g.path_length_hist()
        self.failUnless(h.unconnected == 20)
        g.to_directed()
        h = g.path_length_hist()
        self.failUnless(h.unconnected == 40)
        h = g.path_length_hist(False)
        self.failUnless(h.unconnected == 20)

def suite():
    simple_suite = unittest.makeSuite(SimplePropertiesTests)
    degree_suite = unittest.makeSuite(DegreeTests)
    local_transitivity_suite = unittest.makeSuite(LocalTransitivityTests)
    biconnected_suite = unittest.makeSuite(BiconnectedComponentTests)
    centrality_suite = unittest.makeSuite(CentralityTests)
    path_suite = unittest.makeSuite(PathTests)
    misc_suite = unittest.makeSuite(MiscTests)
    return unittest.TestSuite([simple_suite,
                               degree_suite,
                               local_transitivity_suite,
                               biconnected_suite,
                               centrality_suite,
                               path_suite,
                               misc_suite])

def test():
    t=PathTests()
    t.testShortestPaths()
    t.testGetAllShortestPaths()
    t.testGetShortestPaths()
    t.testPathLengthHist()
    
if __name__ == "__main__":
    test()

