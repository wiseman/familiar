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


@buildtool_command
def test(package_spec):
  for target_name in expand_package_spec(package_spec):
    target = get_target(target_name)
    if isinstance(target, TestTarget):
      target.run_tests()


def main():
  command_name = sys.argv[1]
  target_spec = sys.argv[2]
  load_build_file_for_dir(
    dir_of_package(target_spec))
  command = get_command(command_name)(target_spec)


if __name__ == '__main__':
  main()
