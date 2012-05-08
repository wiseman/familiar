# Copyright 2012 John Wiseman
# jjwiseman@gmail.com

"""
Low-level interface to a drone via MAVLink.
"""

import hml

import logging
import sys
import threading
import time

import mavlink
import mavutil


class Agent(object):
  def __init__(self, mavlink_port=None):
    self.agent_comm_thread = AgentCommThread(
      mavlink_port=mavlink_port, message_delegate=self)
    self.agent_comm_thread.daemon = True

  def connect(self):
    self.agent_comm_thread.start()
    self.agent_comm_thread.wait_until_connected()

  def handle_agent_message(self, message):
    logging.info('Got message %s', message)

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


class Timer(object):
  def __init__(self):
    self.start_time = None
    self.end_time = None

  def start(self):
    self.start_time = time.time()
    return self

  def elapsed_time(self):
    return time.time() - self.start_time


class AgentCommThread(threading.Thread):
  def __init__(self, mavlink_port=None, message_delegate=None):
    self.mavlink_port = mavlink_port
    self.message_delegate = message_delegate
    self.connection_condvar = threading.Condition()
    self.is_connected = False
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
    if self.message_delegate:
      self.message_delegate.handle_message(message)

  def connect(self):
    # Wait to get a couple heartbeats
    logging.info('Connecting to familiar...')
    timer = Timer().start()
    logging.debug('Waiting for 1st heartbeat')
    self.mavlink_port.wait_heartbeat()
    logging.debug('Got 1st heartbeat, Waiting for 2nd heartbeat')
    self.mavlink_port.wait_heartbeat()
    logging.info('Connected in %.3f seconds', timer.elapsed_time())
    with self.connection_condvar:
      self.is_connected = True
      self.connection_condvar.notify_all()

  def wait_until_connected(self):
    with self.connection_condvar:
      while not self.is_connected:
        self.connection_condvar.wait()

  def initialize(self):
    mavlink_port = self.mavlink_port
    self.connect()
    # Tell the drone to send us telemetry at 3 Hz.
    mavlink_port.mav.request_data_stream_send(
      mavlink_port.target_system, mavlink_port.target_component,
      mavlink.MAV_DATA_STREAM_ALL, 3, 1)


def main():
  logging.basicConfig(level=logging.DEBUG)
  mavlink_port = mavutil.mavlink_connection(sys.argv[1], 115200)
  comm_thread = AgentCommThread(mavlink_port=mavlink_port)
  comm_thread.daemon = True
  comm_thread.start()
  time.sleep(10)

if __name__ == '__main__':
  main()
