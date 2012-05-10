# Copyright 2012 John Wiseman
# jjwiseman@gmail.com

import logging
import sys
import time

from hml.familiar import skills

import mavutil


def main():
  logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(module)s:%(lineno)d: %(message)s')
  mavlink_port = mavutil.mavlink_connection(sys.argv[1], int(sys.argv[2]))
  agent = skills.Agent(mavlink_port=mavlink_port)
  agent.connect()
  time.sleep(7)
  print '\n' * 10
  #print 'WOOJJW Waiting for GPS'
  #print 'WOOJJW %s' % (agent.get_location())
  print '\n' * 10
  neutral = {1: 1500, 2: 1500, 3: 1500, 4: 1500,
             5: 1500, 6: 1500, 7: 1500, 8: 1500}
  radio_control = {1: 0, 2: 0, 3: 0, 4: 0,
                   5: 0, 6: 0, 7: 0, 8: 0}
  agent.override_rc(neutral)
  try:
    agent.override_rc({3: 1000, 4: 2000})
    print '\n' * 10
    print 'WOOJJW ARMING MOTORS'
    print '\n' * 10
    time.sleep(6)
    agent.override_rc({3: 1150})
    print '\n' * 10
    print 'WOOJJW THROTTLE UP'
    print '\n' * 10
    for i in range(1150, 1500, 25):
      agent.override_rc({3: i})
      time.sleep(0.5)
  finally:
    agent.override_rc(radio_control)


if __name__ == '__main__':
  main()
