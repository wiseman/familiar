import argparse
import logging
import os.path
import subprocess

from hml.base import unittest


class Target(object):
  def __init__(self, build_file=None, name=None, srcs=None, deps=None):
    self.build_file = build_file
    self.name = name
    self.srcs = srcs
    self.deps = deps

  def key(self):
    return path_to_package_prefix(self.build_file) + ':' + self.name


def path_to_package_prefix(path):
  hml_pos = path.rfind('hml')
  prefix = os.path.dirname(path[hml_pos:])
  return prefix


g_targets = {}


def register_target(target):
  logging.debug('Registering target %s', target.key())
  g_targets[target.key()] = target


def get_target(target_name):
  return g_targets[target_name]


def get_targets_in_dir(directory):
  targets = []
  for target in g_targets:
    package_dir, unused_package_name = split_package_spec(target)
    if package_dir == directory:
      targets.append(target)
  return targets


class TestTarget(Target):
  def __init__(self, build_file=None, name=None, srcs=None, deps=None):
    Target.__init__(self, build_file=build_file, name=name, srcs=srcs,
                    deps=deps)


class PythonTestTarget(TestTarget):
  def __init__(self, build_file=None, name=None, srcs=None, deps=None):
    TestTarget.__init__(self, build_file=build_file, name=name, srcs=srcs,
                        deps=deps)

  def run_tests(self, args):
    for src in self.srcs:
      test_runner_path = os.path.join(os.path.dirname(self.build_file),
                                      src)
      test_args = ['python', test_runner_path]
      test_args += ['--log_level', args.test_log_level]
      #test_args += ['-v']
      if args.fail_fast:
        test_args.append('--failfast')
      subprocess.call(test_args)


class BuildFileContext(object):
  _build_file = None

  @classmethod
  def build_file(klass):
    return klass._build_file

  @classmethod
  def set_build_file(klass, path):
    klass._build_file = path

  @classmethod
  def clear_build_file(klass):
    klass._build_file = None

_build_functions = {}


def build_function(fn):
  _build_functions[fn.__name__] = fn
  return fn


_commands = {}


def register_command(command_name, fn):
  _commands[command_name] = fn


def get_command(command_name):
  return _commands[command_name]


def buildtool_command(fn):
  register_command(fn.__name__, fn)
  return fn


@build_function
def py_unit_test(name=None, srcs=None, deps=None):
  target = PythonTestTarget(build_file=BuildFileContext.build_file(),
                            name=name, srcs=srcs, deps=deps)
  register_target(target)


def build_function_table():
  return _build_functions.copy()


def read_build_file(path):
  try:
    BuildFileContext.set_build_file(path)
    global_syms = build_function_table()
    execfile(path, global_syms, {})
  finally:
    BuildFileContext.clear_build_file()


def expand_package_spec(package_spec):
  logging.info('Expanding package spec %r', package_spec)
  directory, base = split_package_spec(package_spec)
  if base != 'all':
    result = [package_spec]
  else:
    load_build_file_for_dir(directory)
    result = get_targets_in_dir(directory)
  logging.info('Expansion result is %s', result)
  return result


directories_read = []


def load_build_file_for_dir(directory):
  if not directory in directories_read:
    build_path = os.path.join(directory, 'BUILD')
    logging.info('Loading %s', build_path)
    read_build_file(build_path)
    directories_read.append(directory)


def split_package_spec(package_spec):
  colon_pos = package_spec.rfind(':')
  return package_spec[0:colon_pos], package_spec[colon_pos + 1:]


def dir_of_package(package_spec):
  (directory, unused_name) = split_package_spec(package_spec)
  return directory


class Command(object):
  command_registry = {}

  @classmethod
  def get_command_by_name(klass, name):
    return klass.command_registry[name]

  @classmethod
  def register(klass, command_name, command):
    klass.command_registry[command_name] = command

  @classmethod
  def get_all(klass):
    return klass.command_registry.values()

  def __init__(self, name):
    self.name = name

  def initialize_arg_parser(self, subparsers):
    subparser = subparsers.add_parser(
      self.name,
      help='help for %s' % (self.name,))
    self.setup_arg_subparser(subparser)

  def setup_arg_subparser(self, subparser):
    pass


class TestCommand(Command):
  def __init__(self):
    Command.__init__(self, name='test')

  def setup_arg_subparser(self, subparser):
    subparser.add_argument(
      'target_spec',
      metavar='<target_spec>',
      help='The target package spec to test on.')
    subparser.add_argument(
      '--test_log_level',
      dest='test_log_level',
      choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
      default='WARNING',
      help='The logging level to run tests with.')
    subparser.add_argument(
      '--fail_fast',
      action='store_true',
      dest='fail_fast',
      help='Stop after the first failure.')
    subparser.set_defaults(func=self)

  def execute(self, args):
    logging.info('Executing test on target spec %s', args.target_spec)
    load_build_file_for_dir(
      dir_of_package(args.target_spec))
    for target_name in expand_package_spec(args.target_spec):
      target = get_target(target_name)
      if isinstance(target, TestTarget):
        target.run_tests(args)


Command.register('test', TestCommand())


def setup_arg_parser():
  arg_parser = argparse.ArgumentParser(
    description='Build tool.')
  arg_parser.add_argument(
    '--log_level',
    dest='log_level',
    choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
    default='WARNING',
    help='The logging level to use.')
  subparsers = arg_parser.add_subparsers(
    title='Commands',
    description='valid subcommands',
    help='Command help')
  for command in Command.get_all():
    command.initialize_arg_parser(subparsers)
  return arg_parser


def main():
  arg_parser = setup_arg_parser()
  args = arg_parser.parse_args()
  logging.basicConfig(level=unittest.get_logging_level_by_name(args.log_level))
  args.func.execute(args)


if __name__ == '__main__':
  main()
