import argparse
import sys

from hml.base import app
from hml.dialog import actions
from hml.dialog import dialogmanager
from hml.dialog import iomanager


def main(argv):
  arg_parser = argparse.ArgumentParser()
  arg_parser.add_argument(
    '--debug',
    help='Debug mode.',
    dest='debug_mode',
    action='store_true')
  arg_parser.add_argument(
    '--html',
    help='HTML mode',
    dest='html_mode',
    action='store_true')
  arg_parser.add_argument(
    '--test_mode',
    help=('Test mode (may or may not connect to simulator, runs XML tests, '
          'displays results'))
  arg_parser.add_argument(
    '--run_tests',
    help='Run unit tests',
    dest='run_unit_tests',
    action='store_true')
  arg_parser.add_argument(
    '--speech_grammar',
    help='Use the specified speech grammar file',
    dest='speech_grammar',
    metavar='PATH')
  arg_parser.add_argument(
    '--transcript_file',
    help=('Use the specified transcript file as input for console or test '
          'mode.'),
    dest='transcript_file',
    metavar='PATH')
  group = arg_parser.add_mutually_exclusive_group()
  group.add_argument(
    '--console',
    help='Console mode (run without an active connection to the simulator)',
    dest='console_mode',
    action='store_true')
  group.add_argument(
    '--remote_host',
    default=None,
    help='Remote host to connect to (unless using --console)')
  args = arg_parser.parse_args(argv)

  dialog_manager = dialogmanager.DialogManager(
    args.remote_host, actions, run_tests=args.run_unit_tests)

  if args.html_mode:
    io_manager = iomanager.HTMLIOManager(dialog_manager)
  elif args.speech_grammar:
    io_manager = iomanager.SpeechIOManager(dialog_manager)
    io_manager.set_gramar(args.speech_grammar)
  elif args.test_mode:
    io_manager = iomanager.TestIOManager(dialog_manager)
  else:
    io_manager = iomanager.ConsoleIOManager(dialog_manager)

  io_manager.set_debug(args.debug_mode)
  dialog_manager.set_io_manager(io_manager)
  dialog_manager.load_fdl('hml/familiar/dialogdata/world.fdl')
  dialog_manager.check()
  dialog_manager.run()


if __name__ == '__main__':
  app.App(main).run()
