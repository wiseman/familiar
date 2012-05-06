import sys


class Target(object):
  def __init__(self, build_file=None, name=None, srcs=None, deps=None):
    self.build_file = build_file
    self.name = name
    self.srcs = srcs
    self.deps = deps


g_targets = {}


def register_target(target):
  g_targets[target.name] = target


class TestTarget(Target):
  def __init__(self, build_file=None, name=None, srcs=None, deps=None):
    Target.__init__(self, build_file=build_file, name=name, srcs=srcs,
                    deps=deps)


class PythonTestTarget(TestTarget):
  def __init__(self, build_file=None, name=None, srcs=None, deps=None):
    TestTarget.__init__(self, build_file=build_file, name=name, srcs=srcs,
                        deps=deps)


g_build_file = None

g_build_functions = {}


def build_function(fn):
  g_build_functions[fn.__name__] = fn
  return fn


@build_function
def py_unit_test(name=None, srcs=None, deps=None):
  target = PythonTestTarget(build_file=g_build_file,
                            name=name, srcs=srcs, deps=deps)
  register_target(target)
  print target


def build_function_table():
  return g_build_functions.copy()


def read_build_file(path):
  global g_build_file
  g_build_file = path
  global_syms = build_function_table()
  execfile(path, global_syms, {})


if __name__ == '__main__':
  read_build_file(sys.argv[1])
