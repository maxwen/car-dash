'''
Created on Mar 2, 2012

@author: maxl
'''

import os

DEFAULT_ROOT= os.path.join(os.environ['HOME'], "workspaces", "car-dash")
defaultTileHome=os.path.join("Maps", "osm", "tiles")
defaultDBHome=os.path.join("Maps", "osm", "db")

def getRoot():
    if "CARDASH_ROOT" in os.environ:
        return os.environ["CARDASH_ROOT"]
    return DEFAULT_ROOT

def getDataRoot():
    return getRoot()

def getImageRoot():
    return os.path.join(getRoot(), "images")

def getTileRoot():
    return os.environ['HOME']

def getPolyDataRootSimple():
    return os.path.join(getRoot(), "poly-simple")

def getPolyDataRoot():
    return os.path.join(getRoot(), "poly")

def getDBRoot():
    return os.path.join(os.environ['HOME'], defaultDBHome)
