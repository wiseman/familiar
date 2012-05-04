import collections
import curses
import logging
import optparse
import StringIO
import string
import sys
import time

import mavlink
import mavutil


def main():
  parser = optparse.OptionParser()
  parser.add_option('--device', dest='device', default=None,
                    help='USB device name, e.g. /dev/tty.usbserial-AH00M6K1')
  parser.add_option('--input_log', dest='input_log', default=None,
                    help='Mavlink log file to read.')
  (opts, unused_args) = parser.parse_args()

  if not opts.device and not opts.input_log:
    sys.stderr.write('You must specify a device using --device or an '
                     'input log file with --input_log.\n')
    sys.exit(1)

  port_bps = 115200
  if opts.device:
    mav_link = mavutil.mavlink_connection(opts.device, baud=port_bps)
  else:
    mav_link = mavutil.mavlink_connection(opts.input_log)
  print mav_link
  if opts.device:
    for i in range(2):
      print 'Waiting for heartbeat %s...' % (i,)
      mav_link.wait_heartbeat()
    print 'Requesting extended data stream'
    mav_link.mav.request_data_stream_send(
      mav_link.target_system, mav_link.target_component,
      mavlink.MAV_DATA_STREAM_ALL, 5, 1)
  curses_loop(mav_link)


def loop(mav_link):
  while True:
    message = mav_link.recv_msg()
    if message:
      print message


def curses_loop(mav_link):
  try:
    dirty = False
    window = curses.initscr()
    messages = collections.OrderedDict()
    while True:
      window.clear()
      message = mav_link.recv_msg()
      if message:
        messages[message.get_type()] = message
        dirty = True
      else:
        if dirty:
          display_messages(window, messages)
          dirty = False
        time.sleep(0.01)
  finally:
    curses.endwin()


def display_messages(window, messages):
  (unused_max_y, max_x) = window.getmaxyx()
  for i, message_type in enumerate(messages):
    message = messages[message_type]
    message_str = '%s' % (message,)
    message_str = cook_string(message_str[0:min(len(message_str), max_x - 1)])
    window.move(i, 0)
    window.clrtoeol()
    window.addstr(message_str)
  window.refresh()


def cook_string(s):
  sio = StringIO.StringIO()
  for c in s:
    if (c in string.digits or c in string.letters or
        c in string.punctuation or c == ' '):
      sio.write(c)
    else:
      sio.write('.')
  return sio.getvalue()


if __name__ == '__main__':
  logging.basicConfig(level=logging.DEBUG)
  main()
