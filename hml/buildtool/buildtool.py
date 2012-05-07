import argparse
import os.path
import subprocess


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


def get_targets_in_dir(directory):
  targets = []
  for target in g_targets:
    package_dir, package_name = split_package_spec(target)
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
      test_args += ['--log_level', args.log_level]
      #test_args += ['-v']
      if args.fail_fast:
        test_args.append('--failfast')
      subprocess.call(test_args)


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


def expand_package_spec(package_spec):
  dir, base = split_package_spec(package_spec)
  if base != 'all':
    return package_spec
  else:
    load_build_file_for_dir(dir)
    return get_targets_in_dir(dir)


directories_read = []


def load_build_file_for_dir(directory):
  if not directory in directories_read:
    read_build_file(os.path.join(directory, 'BUILD'))
    directories_read.append(directory)


def split_package_spec(package_spec):
  colon_pos = package_spec.rfind(':')
  return package_spec[0:colon_pos], package_spec[colon_pos + 1:]


def dir_of_package(package_spec):
  (dir, unused_name) = split_package_spec(package_spec)
  return dir


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
      '--log_level',
      dest='log_level',
      choices=['DEBUG', 'INFO', 'ERROR'],
      default='ERROR',
      help='The logging level to run tests with.')
    subparser.add_argument(
      '--fail_fast',
      action='store_true',
      dest='fail_fast',
      help='Stop after the first failure.')
    subparser.set_defaults(func=self)

  def execute(self, args):
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
  arg_parser.add_argument('-v', '--verbose', action='store_true',
                          help='Run in verbose mode.')

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
  args.func.execute(args)


if __name__ == '__main__':
  main()
