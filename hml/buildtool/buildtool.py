import argparse
import os.path
import subprocess
import sys


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
  g_targets[target.key()] = target


def get_target(target_name):
  return g_targets[target_name]


class TestTarget(Target):
  def __init__(self, build_file=None, name=None, srcs=None, deps=None):
    Target.__init__(self, build_file=build_file, name=name, srcs=srcs,
                    deps=deps)


class PythonTestTarget(TestTarget):
  def __init__(self, build_file=None, name=None, srcs=None, deps=None):
    TestTarget.__init__(self, build_file=build_file, name=name, srcs=srcs,
                        deps=deps)

  def run_tests(self):
    for src in self.srcs:
      test_runner_path = os.path.join(os.path.dirname(self.build_file),
                                      src)
      subprocess.call(['python', test_runner_path])


_build_file = None

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
  target = PythonTestTarget(build_file=_build_file,
                            name=name, srcs=srcs, deps=deps)
  register_target(target)


def build_function_table():
  return _build_functions.copy()


def read_build_file(path):
  global _build_file
  _build_file = path
  global_syms = build_function_table()
  execfile(path, global_syms, {})


def expand_package_spec(spec):
  return [spec]


def load_build_file_for_dir(directory):
  read_build_file(os.path.join(directory, 'BUILD'))


def dir_of_package(package_spec):
  directory = package_spec[0:package_spec.rfind(':')]
  return directory


def test_command(args):
  load_build_file_for_dir(
    dir_of_package(args.target_spec))
  for target_name in expand_package_spec(args.target_spec):
    target = get_target(target_name)
    if isinstance(target, TestTarget):
      target.run_tests()


def setup_arg_parser():
  arg_parser = argparse.ArgumentParser(
    description='Build tool.')
#  arg_parser.add_argument(
#    'command',
#    metavar='<command>',
#    help='The build command to run.')
  arg_parser.add_argument('-v', '--verbose', action='store_true',
                          help='Run in verbose mode.')

  subparsers = arg_parser.add_subparsers(
    title='Commands',
    description='valid subcommands',
    help='Command help')
  parser_test = subparsers.add_parser('test', help='test help')
  parser_test.add_argument(
    'target_spec',
    metavar='<target_spec>',
    help='The target package spec to test on.')
  parser_test.set_defaults(func=test_command)

  parser_build = subparsers.add_parser('build', help='build help')
  parser_build.add_argument(
    'target_spec',
    metavar='<target_spec>',
    help='The target package spec to build on.')
  parser_build.set_defaults(func=test_command)

  return arg_parser


def main():
  arg_parser = setup_arg_parser()
  args = arg_parser.parse_args()
  args.func(args)


if __name__ == '__main__':
  main()
