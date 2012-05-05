import collections
import curses
import logging
import optparse
import os.path
import StringIO
import string
import sys
import time

import mavlink
import mavutil


class App(object):
  def __init__(self, argv):
    self.argv = argv
    self.opt_parser = self.create_opt_parser()

  def run(self):
    (options, args) = self.opt_parser.parse_args(self.argv)
    self.validate_command_line(options, args)
    self.main(options, args)

  def main(self, options, args):
    raise NotImplementedError()

  def create_opt_parser(self):
    raise NotImplementedError

  def validate_command_line(self, options, args):
    pass

  def exit(self, code):
    sys.exit(code)

  def error(self, message, *fmt_args):
    sys.stdout.flush()
    sys.stderr.write('%s: error: %s\n' % (
      os.path.basename(self.argv[0]),
      message % fmt_args))
    self.exit(2)

  def usage_error(self, message, *fmt_args):
    sys.stdout.flush()
    self.opt_parser.print_help(file=sys.stderr)
    self.error(message, *fmt_args)
    self.exit(2)


class ListenApp(App):
  def create_opt_parser(self):
    parser = optparse.OptionParser()
    parser.add_option('--device', dest='device', default=None,
                      help='USB device name, e.g. /dev/tty.usbserial-AH00M6K1')
    parser.add_option('--bps', dest='bps', default=115200,
                      help='USB device speed, defaults to %default%.')
    parser.add_option('--no_curses', dest='no_curses', default=False,
                      action='store_true')
    parser.add_option('--input_log', dest='input_log', default=None,
                      help='Mavlink log file to read.')
    return parser

  def validate_command_line(self, options, args):
    if not options.device and not options.input_log:
      self.error('You must specify a device using --device or an '
                 'input log file with --input_log.')

  def main(self, options, args):
    if options.device:
      mav_link = mavutil.mavlink_connection(options.device, baud=options.bps)
    else:
      mav_link = mavutil.mavlink_connection(options.input_log)
    if options.device:
      for i in range(2):
        print 'Waiting for heartbeat %s...' % (i,)
        mav_link.wait_heartbeat()
      print 'Requesting extended data stream'
      mav_link.mav.request_data_stream_send(
        mav_link.target_system, mav_link.target_component,
        mavlink.MAV_DATA_STREAM_ALL, 10, 1)
    if options.no_curses:
      self.message_loop(mav_link)
    else:
      self.curses_message_loop(mav_link)

  def message_loop(self, mav_link):
    while True:
      message = mav_link.recv_msg()
      if message:
        print message

  def curses_message_loop(self, mav_link):
    try:
      dirty = False
      window = curses.initscr()
      messages = collections.OrderedDict()
      num_messages = 0
      start_time = time.time()
      while True:
        message = mav_link.recv_msg()
        if message:
          num_messages += 1
          messages[message.get_type()] = message
          dirty = True
        if num_messages >= 100 or not message:
          if dirty:
            window.clear()
            self.display_messages(window, messages)
            self.display_stats(window, num_messages,
                               mav_link.mav.total_bytes_received, start_time)
            window.refresh()
            dirty = False
        if not message:
          time.sleep(0.01)
    finally:
      curses.endwin()

  def display_stats(self, window, num_messages,
                    total_bytes_received, start_time):
    max_y, max_x = window.getmaxyx()
    window.move(max_y - 1, 0)
    window.clrtoeol()
    duration = time.time() - start_time
    mps = num_messages / duration
    bps = total_bytes_received / duration
    window.addstr('%.2f mps %.2f bps' % (mps, bps))

  def display_messages(self, window, messages):
    (unused_max_y, max_x) = window.getmaxyx()
    for i, message_type in enumerate(messages):
      message = messages[message_type]
      message_str = '%s' % (message,)
      message_str = cook_string(message_str[0:min(len(message_str),
                                                  max_x - 1)])
      window.move(i, 0)
      window.clrtoeol()
      window.addstr(message_str)


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
  app = ListenApp(sys.argv)
  app.run()
