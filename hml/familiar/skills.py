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

MAV_MODES = {
  'MAV_MODE_UNINIT': 0,  # System is in undefined state
  'MAV_MODE_LOCKED': 1,  # Motors are blocked, system is safe
  'MAV_MODE_MANUAL': 2,  # System is allowed to be active, under manual (RC) control
  'MAV_MODE_GUIDED': 3,  # System is allowed to be active, under autonomous control, manual setpoint
  'MAV_MODE_AUTO': 4,    # System is allowed to be active, under autonomous control and navigation
  'MAV_MODE_TEST1': 5,   # Generic test mode, for custom use
  'MAV_MODE_TEST2': 6,   # Generic test mode, for custom use
  'MAV_MODE_TEST3': 7,   # Generic test mode, for custom use
  'MAV_MODE_READY': 8,   # System is ready, motors are unblocked, but controllers are inactive
  'MAV_MODE_RC_TRAINING': 9  # System is blocked, only RC valued are read and reported back
}

NAV_MODES = {
  'MAV_NAV_GROUNDED': 0,
  'MAV_NAV_LIFTOFF': 1,
  'MAV_NAV_HOLD': 2,
  'MAV_NAV_WAYPOINT': 3,
  'MAV_NAV_VECTOR': 4,
  'MAV_NAV_RETURNING': 5,
  'MAV_NAV_LANDING': 6,
  'MAV_NAV_LOST': 7,
  'MAV_NAV_LOITER': 8,
  'MAV_NAV_FREE_DRIFT': 9,
}  


def decode_mav_mode(mode):
  states = []
  for mode_name in MAV_MODES:
    if mode & MAV_MODES[mode_name]:
      states.append(mode_name)
  return states


def decode_nav_mode(mode):
  for state in NAV_MODES:
    if NAV_MODES[state] == mode:
      return state
  raise KeyError('No such mode %s' % (mode,))


class Agent(object):
  def __init__(self, mavlink_port=None):
    self.agent_comm_thread = AgentCommThread(
      mavlink_port=mavlink_port, message_delegate=self)
    self.agent_comm_thread.daemon = True
    self.rc_state = {1: -1, 2: -1, 3: -1, 4: -1,
                     5: -1, 6: -1, 7: -1, 8: -1}

  def connect(self):
    self.agent_comm_thread.start()
    self.agent_comm_thread.wait_until_connected()

  def handle_message_type_SYS_STATUS(self, message):
    logging.info('States: %s', decode_mav_mode(message.mode))
    logging.info('Mode: %s', mavutil.mode_string_v09(message))
    logging.info('Nav mode: %s', decode_nav_mode(message.nav_mode))

  def handle_agent_message(self, message):
    logging.debug('Got message %s', message)
    if message.get_type() == 'SYS_STATUS':
      self.handle_message_type_SYS_STATUS(message)

  def become_safe(self):
    pass

  def turn_to_heading(self, heading):
    pass

  def set_altitude(self, altitude):
    pass

  def land(self):
    pass

  def return_to_launch(self):
    pass

  def set_speed(self):
    pass

  def set_home(self):
    pass

  def takeoff(self):
    # {MAV_CMD_NAV_TAKEOFF, 0, 0, 3.0, 0, 0}
    self.agent_comm_thread.send_command(
      [mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 3.0, 0, 0])

  def override_rc(self, values):
    self.rc_state.update(values)
    start_time = time.time()
    with self.agent_comm_thread.connection_condvar:
      mav_link = self.agent_comm_thread.mavlink_port
      rc_state = self.rc_state
      logging.info('Override RC: %s', rc_state)
      mav_link.mav.rc_channels_override_send(
        mav_link.target_system, mav_link.target_component,
        rc_state[1],
        rc_state[2],
        rc_state[3],
        rc_state[4],
        rc_state[5],
        rc_state[6],
        rc_state[7],
        rc_state[8])
      logging.info('WOOJJW elapsed time: %s', time.time() - start_time)

  def get_location(self):
    with self.agent_comm_thread.connection_condvar:
      return self.agent_comm_thread.mavlink_port.location()


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

  def send_command(self, command):
    with self.connection_condvar:
      logging.info('Sending command %s', command)
      self.mavlink_port.mav.command_send(
        self.mavlink_port.target_system, self.mavlink_port.target_component,
        *command)

  def run(self):
    self.initialize()
    while self.keep_running():
      with self.connection_condvar:
        message = self.mavlink_port.recv_msg()
      if not message:
        time.sleep(0.01)
      else:
        self.handle_message(message)

  def keep_running(self):
    return True

  def handle_message(self, message):
    logging.debug('Handling message %s', message)
    if self.message_delegate:
      self.message_delegate.handle_agent_message(message)

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
