#!/usr/bin/env python2.5
from energid import pilotmodel

import sys
import pprint

pm = pilotmodel.PilotModel(sys.argv[1])
pm.connect()
objs = pm.get_all()
pprint.pprint(objs)

for obj in objs:
  print obj['name']

