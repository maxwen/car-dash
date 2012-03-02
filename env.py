'''
Created on Mar 2, 2012

@author: maxl
'''

import os

DEFAULT_ROOT= os.path.join(os.environ['HOME'], "workspaces", "pydev", "car-dash")
defaultTileHome=os.path.join("Maps", "osm", "tiles")

def getRoot():
    if "CARDASH_ROOT" in os.environ:
        return os.environ["CARDASH_ROOT"]
    return DEFAULT_ROOT

def getImageRoot():
    return os.path.join(getRoot(), "images")

def getTileRoot():
    return os.environ['HOME']

        