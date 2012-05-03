import logging
import StringIO
import unittest

import arduinoserial
import protocol


class ProtocolTestError(Exception):
  pass


class MockSerialPort(arduinoserial.SerialPort):
  def __init__(self, input_data):
    s = StringIO.StringIO()
    for byte in input_data:
      s.write(chr(byte))
    self.input_buffer = StringIO.StringIO(s.getvalue())

  def read(self, n):
    data = self.input_buffer.read(n)
    if data == '':
      raise ProtocolTestError('EOF from MockSerialPort')
    logging.info('Read data from port %s: %r', self, data)
    return data
  

class TestMessages(unittest.TestCase):
  def test_message_read(self):
    binary_data = [0x34, 0x44, 0x03, 0x00, 0x01, 0x1A, 0x2B, 0x3C, 0x85, 0xf6]
    port = MockSerialPort(binary_data)
    message = protocol.read_message(port)
    self.assertEqual(0, message.message_id)
    self.assertEqual(1, message.message_version)
    self.assertEqual([0x1a, 0x2b, 0x3c], map(ord, message.payload))
    print message.compute_checksum()


if __name__ == '__main__':
  logging.basicConfig(level=logging.DEBUG)
  unittest.main()
