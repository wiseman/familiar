# Copyright 2012 John Wiseman
# jjwiseman@gmail.com

import logging
import sys
import threading
import time

import mavlink
import mavutil


class Agent(object):
  def __init__(self):
    pass

  def become_safe(self):
    pass

  def turn_to_heading(self, heading):
    pass

  def set_altitude(self, altitude):
    pass

  def takeoff(self):
    pass

  def land(self):
    pass

  def return_to_launch(self):
    pass

  def set_speed(self):
    pass

  def set_home(self):
    pass


class AgentCommThread(threading.Thread):
  def __init__(self, mavlink_port=None):
    assert(mavlink_port)
    self.mavlink_port = mavlink_port
    threading.Thread.__init__(self)

  def run(self):
    self.initialize()
    while self.keep_running():
      message = self.mavlink_port.recv_msg()
      if not message:
        time.sleep(0.01)
      else:
        self.handle_message(message)

  def keep_running(self):
    return True

  def handle_message(self, message):
    logging.info('Handling message %s', message)

  def initialize(self):
    mavlink_port = self.mavlink_port
    # Wait to get a couple heartbeats
    logging.info('Connecting to familiar')
    logging.debug('Waiting for 1st heartbeat')
    mavlink_port.wait_heartbeat()
    logging.debug('Got 1st heartbeat, Waiting for 2nd heartbeat')
    mavlink_port.wait_heartbeat()
    # Tell the drone to send us telemetry at 1 Hz.
    mavlink_port.mav.request_data_stream_send(
      mavlink_port.target_system, mavlink_port.target_component,
      mavlink.MAV_DATA_STREAM_ALL, 1, 1)


def main():
  logging.basicConfig(level=logging.DEBUG)
  mavlink_port = mavutil.mavlink_connection(sys.argv[1], 115200)
  comm_thread = AgentCommThread(mavlink_port=mavlink_port)
  comm_thread.daemon = True
  comm_thread.start()
  time.sleep(10)

if __name__ == '__main__':
  main()
