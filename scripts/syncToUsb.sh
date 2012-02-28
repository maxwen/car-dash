#!/bin/sh
cd $HOME/workspaces/pydev/car-dash
mkdir /media/CORSAIR/pydev/car-dash/
rsync -r -a --exclude ".svn" --exclude "__pycache__" --progress * /media/CORSAIR/pydev/car-dash/ --size-only

