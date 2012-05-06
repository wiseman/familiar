import argparse
import logging
import sys
import unittest


TestCase = unittest.TestCase


LOGGING_LEVELS = {
  'DEBUG': logging.DEBUG,
  'INFO': logging.INFO,
  'WARNING': logging.WARNING,
  'ERROR': logging.ERROR,
  'CRITICAL': logging.CRITICAL
  }


def get_logging_level_by_name(name):
  return LOGGING_LEVELS[name]


class TestApp(object):
  def __init__(self):
    self.run()

  def run(self):
    parser = argparse.ArgumentParser(
      description='Test runner.')
    parser.add_argument(
      '--log_level',
      dest='log_level',
      choices=['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG'],
      default='INFO',
      help='The logging level to use while running tests.')
    args = parser.parse_args()
    logging.basicConfig(
      level=get_logging_level_by_name(args.log_level),
      format='%(levelname)s:%(module)s:%(lineno)d: %(message)s')
    unittest.main(argv=[sys.argv[0]])


main = TestApp
