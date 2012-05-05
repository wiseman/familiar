import logging
import sys

import arduinoserial
import protocol



def main():
  port_name = sys.argv[1]
  port_bps = 115200
  port = arduinoserial.SerialPort(port_name, port_bps)
  while True:
    message = protocol.read_message(port)
    print message
  

if __name__ == '__main__':
  logging.basicConfig(level=logging.DEBUG)
  main()
  
