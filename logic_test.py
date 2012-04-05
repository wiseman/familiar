import logic
import unittest


def makeBindings(b):
  if b == False:
    return b
  bindings = {}
  for var in b:
    bindings[logic.expr(var)] = logic.expr(b[var])
  return bindings


class KBTest(unittest.TestCase):

  def assertBindingsEqual(self, a, b):
    bindingsa = makeBindings(a)
    bindingsb = makeBindings(b)
    #    self.failUnless(bindingsEqual(bindingsa, bindingsb), "%s != %s" % (bindingsa, bindingsb))
    self.assertEqual(bindingsa, bindingsb)

  def assertAllBindingsEqual(self, a, b):
    bindingsa = map(makeBindings, a)
    bindingsb = map(makeBindings, b)
    for x in bindingsa:
      if not x in bindingsb:
        self.fail("%s != %s" % (bindingsa, bindingsb))
    for x in bindingsb:
      if not x in bindingsa:
        self.fail("%s != %s" % (bindingsa, bindingsb))

  def testSimpleAssertions(self):
    kb = logic.PropKB()
    kb.tell(logic.expr("Color(Cat, Black)"))
    self.assertBindingsEqual(kb.ask(logic.expr("Color(Cat, Black)")), {})
    kb.tell(logic.expr("Age(Cat, 35)"))
    self.assertBindingsEqual(kb.ask(logic.expr("Age(Cat, 35)")), {})

  def testSimpleErasures(self):
    kb = logic.PropKB()
    kb.tell(logic.expr("Color(Cat, Black)"))
    kb.tell(logic.expr("Age(Cat,35)"))
    self.assertBindingsEqual(kb.ask(logic.expr("Color(Cat, Black)")), {})
    kb.retract(logic.expr("Color(Cat, Black)"))
    self.assertBindingsEqual(kb.ask(logic.expr("Color(Cat, Black)")), False)

  def testErasures(self):
    kb = logic.PropKB()
    kb.tell(logic.expr("Has(John, Cat)"))
    kb.tell(logic.expr("Has(John, Car)"))
    kb.tell(logic.expr("Has(Cat, Toy)"))
    kb.retract(logic.expr("Has(John, t)"))
    self.assertBindingsEqual(kb.ask(logic.expr("Has(John, t)")), False)

  def testSimpleUnification(self):
    kb = logic.PropKB()
    kb.tell(logic.expr("Color(Cat, Black)"))
    kb.tell(logic.expr("Age(Cat, 35)"))
    self.assertBindingsEqual(kb.ask(logic.expr("Color(Cat, x)")), {"x": "Black"})

  def testConjunction(self):
    kb = logic.PropKB()
    kb.tell(logic.expr("Color(Cat, Black)"))
    kb.tell(logic.expr("Age(Cat, 35)"))
    kb.tell(logic.expr("Name(Cat, Ted)"))
    self.assertEqual(kb.ask(logic.expr("(Color(Cat, Black) & Age(Cat, 35))")), {})
    self.assertEqual(kb.ask(logic.expr("(Color(Cat, Black) & (Age(Cat, 35) & Name(Cat, Ted)))")), {})
    self.assertEqual(kb.ask(logic.expr("(Color(Cat, White) & Age(Cat, 35))")), False)
    self.assertEqual(kb.ask(logic.expr("(Color(Cat, Black) & Age(Cat, 34))")), False)
    self.assertEqual(kb.ask(logic.expr("(Color(Cat, c) & Age(Cat, a))")), {logic.expr("a"): logic.expr("35"),
                                                                           logic.expr("c"): logic.expr("Black")})
    self.assertEqual(kb.ask(logic.expr("(Color(Cat, c) & Age(Cat, c))")), False)
    kb.tell(logic.expr("Color(Car, Black)"))
    self.assertEqual(kb.ask(logic.expr("(Color(Cat, b) & Color(Car, b))")), {logic.expr("b"): logic.expr("Black")})

  def testFunctions(self):
    kb = logic.PropKB()
    kb.tell(logic.expr("Color(Cat, Black)"))
    kb.tell(logic.expr("Color(Car, Black)"))
    self.assertEqual(kb.ask(logic.expr("(Cat <=> Cat)")), {})
    self.assertEqual(kb.ask(logic.expr("(Cat <=> Baseball)")), False)
    self.assertEqual(kb.ask(logic.expr("(~(Cat <=> Cat))")), False)
    self.assertEqual(kb.ask(logic.expr("(~(Cat <=> Baseball))")), {})
    self.assertEqual(kb.ask(logic.expr("((Color(Cat, x) & Color(Car, y)) & (x <=> y))")), {logic.expr("x"): logic.expr("Black"),
                                                                                           logic.expr("y"): logic.expr("Black")})
    self.assertEqual(kb.ask(logic.expr("((Color(a, Black) & Color(b, Black)) & (~(a <=> b)))")), {logic.expr("a"): logic.expr("Cat"),
                                                                                                  logic.expr("b"): logic.expr("Car")})
    self.assertEqual(kb.ask(logic.expr("Bind(x, Boo)")), {logic.expr("x"): logic.expr("Boo")})
    self.assertEqual(kb.ask(logic.expr("(Color(Cat, b) & Bind(b, Boo))")), False)

  def testDisjunction(self):
    kb = logic.PropKB()
    kb.tell(logic.expr("Color(Cat, Black)"))
    kb.tell(logic.expr("Age(Cat, 35)"))
    kb.tell(logic.expr("Name(Cat, Ted)"))
    self.assertEqual(kb.ask(logic.expr("(Color(Cat, Black) | Age(Cat, 35))")), {})
    self.assertEqual(kb.ask(logic.expr("(Color(Cat, Black) | Age(Cat, 36))")), {})
    self.assertEqual(kb.ask(logic.expr("(Color(Cat, White) | Age(Cat, 35))")), {})
    self.assertEqual(kb.ask(logic.expr("(Color(Cat, White) | Age(Cat, 36))")), False)
    self.assertEqual(kb.ask_all(logic.expr("(Color(Cat, c) | Age(Cat, a))")), [{logic.expr("c"): logic.expr("Black")},
                                                                               {logic.expr("a"): logic.expr("35")}])
    self.assertEqual(kb.ask_all(logic.expr("(Color(Cat, c) | Age(Cat, 36))")), [{logic.expr("c"): logic.expr("Black")}])

  def testNot(self):
    kb = logic.PropKB()
    kb.tell(logic.expr("Color(Cat, Black)"))
    kb.tell(logic.expr("Age(Cat, 35)"))
    kb.tell(logic.expr("Name(Cat, Ted)"))
    self.assertEqual(kb.ask(logic.expr("(Color(Cat, Black) & (~Age(Cat, 36)))")), {})
    self.assertEqual(kb.ask(logic.expr("(Color(Cat, Black) & (~Age(Cat, 35)))")), False)
    self.assertEqual(kb.ask(logic.expr("((~Age(Cat, 35)) & Color(Cat, Black))")), False)
    self.assertEqual(kb.ask(logic.expr("((~Age(Cat, 36)) & Color(Cat, Black))")), {})
    self.assertEqual(kb.ask(logic.expr("(Color(Cat, Black) & (~Age(Cat, c)))")), False)
    self.assertEqual(kb.ask(logic.expr("((~Age(Cat, c)) & Color(Cat, Black))")), False)
    self.assertEqual(kb.ask(logic.expr("(Color(Cat, c) & (~Age(Cat, a)))")), False)
    self.assertEqual(kb.ask(logic.expr("((~Age(Cat, a)) & Color(Cat, c))")), False)
    self.assertEqual(kb.ask(logic.expr("((~Age(Cat, 36)) & Color(Cat, c))")), {logic.expr("c"): logic.expr("Black")})
    self.assertEqual(kb.ask(logic.expr("(Color(Cat, c) & (~Age(Cat, 36)))")), {logic.expr("c"): logic.expr("Black")})
    self.assertEqual(kb.ask(logic.expr("~Age(Cat, 35)")), False)
    self.assertEqual(kb.ask(logic.expr("~Age(Cat, 36)")), {})
    

  def testConDis(self):
    kb = logic.PropKB()
    kb.tell(logic.expr("Color(Cat, Black)"))
    kb.tell(logic.expr("Age(Cat, 35)"))
    kb.tell(logic.expr("Name(Cat, Ted)"))
    self.assertEqual(kb.ask(logic.expr("(Color(Cat, Black) & (Age(Cat, 36) | Name(Cat, Ted)))")), {})
    self.assertEqual(kb.ask(logic.expr("(Color(Cat, Black) & (Age(Cat, 36) | Name(Cat, John)))")), False)
    self.assertEqual(kb.ask(logic.expr("((Age(Cat, 36) | Name(Cat, Ted)) & Color(Cat, Black))")), {})
    self.assertEqual(kb.ask(logic.expr("((Age(Cat, 36) | Name(Cat, John)) & Color(Cat, Black))")), False)

  def testFluents(self):
    kb = logic.PropKB()
    kb.tell(logic.expr("Has(John, Cat)"))
    kb.tell(logic.expr("Has(John, Computer)"))
    self.assertAllBindingsEqual(kb.ask_all(logic.expr("Has(John, w)")), [{"w": "Computer"}, {"w": "Cat"}])
    kb.defineFluent("Age")
    kb.tell(logic.expr("Age(John, 35)"))
    kb.tell(logic.expr("Age(John, Ancient)"))
    self.assertAllBindingsEqual(kb.ask_all(logic.expr("Age(John, a)")), [{"a": "Ancient"}])

  def testInheritance(self):
    kb = logic.PropKB()
    kb.tell(logic.expr("ISA(Mammal, Animal)"))
    kb.tell(logic.expr("ISA(Cat, Mammal)"))
    kb.tell(logic.expr("ISA(Petunia, Cat)"))
    kb.defineFluent("Size", inherited = True)
    kb.tell(logic.expr("Size(Mammal, Medium)"))
    kb.tell(logic.expr("Size(Petunia, Petite)"))
    kb.defineFluent("Name", inherited = False)
    kb.tell(logic.expr("Name(Animal, Peter)"))
    kb.tell(logic.expr("Name(Petunia, Petunia)"))
    self.assertBindingsEqual(kb.ask(logic.expr("ISA(Petunia, Animal)")), {})
    self.assertAllBindingsEqual(kb.ask_all(logic.expr("ISA(Petunia, x)")), [{"x": "Petunia"}, {"x": "Cat"}, {"x": "Mammal"},
                                                                            {"x": "Animal"}])
#    self.assertBindingsEqual(kb.ask(logic.expr("Size(Animal, x)")), False)
#    self.assertBindingsEqual(kb.ask(logic.expr("Size(Mammal, s)")), {"s": "Medium"})
#    self.assertBindingsEqual(kb.ask(logic.expr("Size(Cat, s)")), {"s": "Medium"})
#    self.assertBindingsEqual(kb.ask(logic.expr("Size(Petunia, s)")), {"s": "Petite"})
#    self.assertBindingsEqual(kb.ask(logic.expr("Name(Animal, n)")), {"n": "Peter"})
#    self.assertBindingsEqual(kb.ask(logic.expr("Name(Cat, n)")), False)
#    self.assertBindingsEqual(kb.ask(logic.expr("Name(Petunia, n)")), {"n": "Petunia"})
#    self.assertBindingsEqual(kb.ask(logic.expr("(Bind(x, Petunia) & Size(x, s))")), {"x": "Petunia", "s": "Petite"})
#    self.assertBindingsEqual(kb.ask(logic.expr("Size(x, Petite)")), {})
#    self.assertBindingsEqual(kb.ask(logic.expr("Size(x, Medium)")), {})
#    self.assertBindingsEqual(kb.ask(logic.expr("Name(x, Peter)")), {})
#    self.assertBindingsEqual(kb.ask(logic.expr("Name(x, Petunia)")), {})
#    self.assertBindingsEqual(kb.ask(logic.expr("(Bind(x, Petite) & Size(t, x))")), {})
#    self.assertBindingsEqual(kb.ask(logic.expr("Size(x, y)")), {})
    
    

  
if __name__ == "__main__":
  unittest.main()
