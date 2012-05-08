# Copyright 2012 John Wiseman
# jjwiseman@gmail.com

import logging

from hml.familiar import skills

import mavutil


def main():
  logging.basicConfig(level=logging.INFO)
  mavlink_port = mavutil.mavlink_connection(sys.argv[1], int(sys.argv[2]))
  agent = skills.Agent(mavlink_port=mavlink_port)
  agent.connect()

if __name__ == '__main__':
  main()
  
