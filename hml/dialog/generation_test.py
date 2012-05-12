from hml.base import unittest
from hml.dialog import logic
from hml.dialog import generation
from hml.dialog import test_utils


def add_template(kb, concept, template):
  kb.tell(logic.expr(generation.GENERATION_PROPOSITION)(
    logic.expr(concept), logic.Expr(template)))


class TestCase(test_utils.DMTestCase):

  def testGeneration(self):
    """Tests natural language generation"""

    kb = logic.PropKB()
    generator = generation.Generator(kb)

    add_template(kb, "c-cat", "cat")
    self.assertEqual(generator.generate("c-cat"), "cat")
    self.assertEqual(generator.generate(logic.expr("c-cat")), "cat")
    self.assertEqual(generator.generate(logic.Description("c-cat")), "cat")

    add_template(kb, "i-petunia", "the prettiest cat")
    self.assertEqual(generator.generate("i-petunia"), "the prettiest cat")
    self.assertEqual(
      generator.generate(logic.expr("i-petunia")), "the prettiest cat")
    self.assertEqual(
      generator.generate(logic.Description("i-petunia")), "the prettiest cat")

    add_template(kb, "c-dog-1", "{color} dog")
    add_template(kb, "c-dog-2", "the {color} dog")
    add_template(kb, "c-dog-3", "the {color}, dog")
    add_template(kb, "c-dog-4", "the '{color}' dog")
    add_template(kb, "c-dog-5", "the {color}' dog")
    add_template(kb, "c-dog-6", "the {color}{size} dog")
    add_template(kb, "c-dog-7", "the {color}{size}dog")
    add_template(kb, "c-dog-9", "{color}{size}dog")
    add_template(kb, "c-dog-10", "{color}")
    add_template(kb, "c-dog-11", "the dog which is {color}")
    add_template(kb, "c-dog-12", "the dog which is {degree}")
    add_template(kb, "c-dog-13", "the dog which is {degree}, yo")
    add_template(kb, "c-dog-14", "the dog which is {color")
    add_template(kb, "c-dog-15", "{color")

    for i in range(1, 16):
      kb.tell(logic.expr("color(c-dog-%s, black)" % (i,)))
      kb.tell(logic.expr("size(c-dog-%s, small)" % (i,)))

    self.assertEqual(generator.generate("c-dog-1"), "black dog")
    self.assertEqual(generator.generate("c-dog-2"), "the black dog")
    self.assertEqual(generator.generate("c-dog-3"), "the black, dog")
    self.assertEqual(generator.generate("c-dog-4"), "the 'black' dog")
    self.assertEqual(generator.generate("c-dog-5"), "the black' dog")
    self.assertEqual(generator.generate("c-dog-6"), "the blacksmall dog")
    self.assertEqual(generator.generate("c-dog-7"), "the blacksmalldog")
    self.assertEqual(generator.generate("c-dog-9"), "blacksmalldog")
    self.assertEqual(generator.generate("c-dog-10"), "black")
    self.assertEqual(generator.generate("c-dog-11"), "the dog which is black")
    self.assertEqual(generator.generate("c-dog-12"), "the dog which is")
    self.assertEqual(generator.generate("c-dog-13"), "the dog which is , yo")
    self.assertRaises(SyntaxError, lambda: generator.generate("c-dog-14"))
    self.assertRaises(SyntaxError, lambda: generator.generate("c-dog-15"))


if __name__ == "__main__":
  print "Generation tests:"
  unittest.main()
