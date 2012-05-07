import unittest

from hml.dialog import logic


def cookBindings(b):
  """Converts a set of bindings made of strings (e.g., {"?x":
  "Petunia"}) to one containing Expr's (e.g., {logic.expr("?x"):
  logic.expr("Petunia")}.  Saves a lot of wordiness in the tests."""

  if b == False:
    return b
  bindings = {}
  for var in b:
    bindings[logic.expr(var)] = logic.expr(b[var])
  return bindings


def descriptify(a):
  if isinstance(a, str):
    return logic.Description(a)
  elif isinstance(a, logic.Expr):
    return descriptify(a.op)
  elif isinstance(a, logic.Description):
    newslots = {}
    for slot in a.slots:
      newslots[slot] = descriptify(a.slots[slot])
    return logic.Description(a.base, newslots)
  else:
    return a


def parse_equal(a, b):
  return descriptify(a) == descriptify(b)


#class TestCase(unittest.TestCase):
#    """Version of TestCase that can be easily run independently of the
#    testing framework."""
#
#    __stopOnError__ = 1
#
#    def __init__(self, *args, **kw):
#        if args: apply(unittest.TestCase.__init__, (self,) + args, kw)
#
#    def throwsException(self, test_function, expected_exc):
#        """True if  'test_function()' throws 'expected_exc'"""
#        try: test_function()
#        except expected_exc: return 1
#
#    def __call__(self, result=None):
#        if self.__stopOnError__:
#            result.startTest(self)
#            self.setUp(); self.__testMethod(); self.tearDown();
#            print
#        else:
#            unittest.TestCase.__call__(self, result)


class DMTestCase(unittest.TestCase):

  def assertBindingsEqual(self, a, b):
    """Checks that two sets of bindings are equivalent."""

    bindingsa = cookBindings(a)
    bindingsb = cookBindings(b)
    #    self.failUnless(bindingsEqual(bindingsa, bindingsb), "%s != %s" % (bindingsa, bindingsb))
    self.assertEqual(bindingsa, bindingsb)

  def assertAllBindingsEqual(self, a, b):
    """Checks that two sets of solutions (i.e. collections of
    bindings) are equivalent."""

    if a == False:
      self.failUnless(b == False, "%s != %s" % (a, b))
    if b == False:
      self.failUnless(a == False, "%s != %s" % (a, b))

    bindingsa = map(cookBindings, a)
    bindingsb = map(cookBindings, b)
    for x in bindingsa:
      if not x in bindingsb:
        self.fail("%s != %s" % (bindingsa, bindingsb))
    for x in bindingsb:
      if not x in bindingsa:
        self.fail("%s != %s" % (bindingsa, bindingsb))

  def assertParseEqual(self, parses, results):
    self.failUnless(len(parses) == len(results),
                    "%s != %s" % (parses, results))
    for (parse, result) in zip(parses, results):
      self.failUnless(
        parse_equal(parse, result),
        "%s != %s (in particular, %s != %s)" % (
          parses, results, parse, result))

  def assertApproxEqual(self, a, b, epsilon):
    if abs(a - b) > epsilon:
      self.fail("%s is not within %s of %s" % (a, epsilon, b))


