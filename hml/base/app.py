import argparse
import logging
import sys


LOGGING_LEVELS = {
  'DEBUG': logging.DEBUG,
  'INFO': logging.INFO,
  'WARNING': logging.WARNING,
  'ERROR': logging.ERROR,
  'CRITICAL': logging.CRITICAL
  }


def get_logging_level_by_name(name):
  return LOGGING_LEVELS[name]


class App(object):
  def __init__(self, main=None):
    self.main = main
    assert main

  def run(self, argv=None):
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument(
      '--logging_level',
      dest='logging_level',
      choices=['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG'],
      default='INFO',
      help='The logging level to use.')

    if not argv:
      argv = sys.argv

    args, unknown_args = arg_parser.parse_known_args(args=argv[1:])
    logging.basicConfig(
      level=get_logging_level_by_name(args.logging_level),
      format='%(asctime)s:%(levelname)s:%(module)s:%(lineno)d: %(message)s')
    self.main(unknown_args)
