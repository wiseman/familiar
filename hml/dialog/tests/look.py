#!/usr/bin/env python2.5
from energid import pilotmodel

import sys
import pprint
import time
from optparse import OptionParser

def run():
  parser = OptionParser()
  parser.add_option("-z", "--zoom", dest="zoom", type="float",
                    help="Use this zoom level.", metavar="LEVEL")
  parser.add_option("-d", "--detailed", dest="detailed", action="store_true",
                    help="Print all details on visible objects.")
  parser.add_option("-p", "--position", dest="position", nargs=3, type="float",
                    help="The coordinates to look at.  E.g. -p 1030 -630.5 400.",
                    metavar="X Y Z")
  parser.add_option("-t", "--time-delay", dest="time_delay", type="float",
                    help="Wait this many seconds after looking to query vision.",
                    metavar="SECS")
  parser.usage = "usage: %prog [options] hostname"
  (options, args) = parser.parse_args()
  if len(args) < 1:
    parser.error("You need to supply a hostname argument.")
  elif len(args) > 1:
    parser.error("Too many arguments.")
    
  
  pm = pilotmodel.PilotModel(args[0])
  pm.connect()

  # Need to zoom before doing look_at; If we send any other commands
  # after look_at the endpoint of the pilot's vision will begin moving
  # with the plane, instead of continuing to track the desired
  # coordinates.
  if options.zoom:
    pm.zoom_view(options.zoom)

  if options.position:
    pm.look_at(options.position)

  if options.time_delay:
    time.sleep(options.time_delay)

  seen_objs = pm.get_all()
  if options.detailed:
    pprint.pprint(seen_objs)
  else:
    print_objs(seen_objs)

def print_objs(objs):
  print "%-6s %-45s  %s" % ("Pixels", "Name", "Category/Type")
  print "-------------------------------------------------------------------------------"
  for obj in objs:
    print_obj(obj)
    
def print_obj(obj):
  print "%6s %-45s  %s/%s" % (int(obj['blob']['size']),
                              "name: %s" % (obj['name'],),
                              obj['category'],
                              obj['type'])
  


run()
