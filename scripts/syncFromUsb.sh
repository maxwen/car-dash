#!/bin/sh
cd /media/CORSAIR/pydev/car-dash/
rsync -r -a --exclude ".svn" --exclude "__pycache__" --progress * /home/maxl/workspaces/pydev/car-dash/ --size-only

