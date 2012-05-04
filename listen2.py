import logging
import optparse
import random
import sys

import mavlink
import mavutil


def main():
  parser = optparse.OptionParser()
  parser.add_option('--device', dest='device', default=None,
                    help='USB device name, e.g. /dev/tty.usbserial-AH00M6K1')
  parser.add_option('--input_log', dest='input_log', default=None,
                    help='Mavlink log file to read.')
  (opts, args) = parser.parse_args()

  if not opts.device and not opts.input_log:
    sys.stderr.write('You must specify a device using --device or an '
                     'input log file with --input_log.\n')
    sys.exit(1)

  
  port_bps = 115200
  port_bps = 57600
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
    msg = mav_link.mav.request_data_stream_send(
      mav_link.target_system, mav_link.target_component,
      mavlink.MAV_DATA_STREAM_ALL, 1, 1)
  while True:
    message = mav_link.recv_msg()
    if message:
      print message



if __name__ == '__main__':
  logging.basicConfig(level=logging.DEBUG)
  main()
  
