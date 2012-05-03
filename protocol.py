import logging

import arduinoserial


DEFAULT_PORT = ''
DEFAULT_BPS = 57600


def comm(port, bps):
  port = arduinoserial.SerialPort(port, bps)
  

def read_until_preamble(port):
  port.read_until('4')
  if port.read(1) == 'D':
    return
  else:
    read_until_preamble(port)


class Fletcher8Checksum(object):
  def __init__(self):
    self.sum1 = 0
    self.sum2 = 0

  def add_byte(self, b):
    self.sum1 = (self.sum1 + b) % 255
    self.sum2 = (self.sum2 + self.sum1) % 255

  def add_string(self, s):
    for char in s:
      self.add_byte(ord(char))

  def get_value(self):
    return (self.sum1, self.sum2)
  

class Message(object):
  def __init__(self, message_id, message_version, payload):
    self.message_id = message_id
    self.message_version = message_version
    self.payload = payload

  def compute_checksum(self):
    checksum = Fletcher8Checksum()
    checksum.add_byte(len(self.payload))
    checksum.add_byte(self.message_id)
    checksum.add_byte(self.message_version)
    checksum.add_string(self.payload)
    return checksum.get_value()
    

def read_message(port):
  read_until_preamble(port)
  logging.debug('Read preamble')
  payload_length = port.read_uint8()
  logging.debug('Read payload_length=%s', payload_length)
  message_id = port.read_uint8()
  logging.debug('Read message_id=%s', message_id)
  message_version = port.read_uint8()
  logging.debug('Read message_version=%s', message_version)
  payload = port.read(payload_length)
  logging.debug('Read payload=%r', payload)
  checksum = port.read(2)
  logging.debug('Read checksum=%s', checksum)
  logging.info('Read complete message')
  message = Message(message_id=message_id,
                    message_version=message_version,
                    payload=payload)
  computed_checksum = message.compute_checksum()
  if not (computed_checksum[0] == ord(checksum[0]) and
          computed_checksum[1] == ord(checksum[1])):
    logging.warn('Bad message checksum: %s computed, %s read.',
                 computed_checksum, list(map(ord, checksum)))
  return message
