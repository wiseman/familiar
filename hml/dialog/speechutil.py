#!/usr/bin/env python2.5
"""This module generates a Microsoft Speech Recognition grammar file
from an FDL file.
"""

import logging
import operator
import os.path
import sys
import time

from hml.dialog import parser
from hml.dialog import logic
from hml.dialog import fdl
from hml.dialog import utils


class Rule:
  def __init__(self, name, xml, references):
    def c(e):
      if isinstance(e, logic.Expr):
        return e.op
      else:
        return e
    self.name = c(name)
    self.xmls = [xml]
    self.references = utils.unique(map(c, references))
    if self.name in self.references:
      self.references.remove(self.name)
    self.referencers = []

  def __str__(self):
    return "<Rule %s>" % (self.name)

  def __repr__(self):
    return "<Rule %s %s>" % (self.name, self.references)

  def combine(self, other_rule):
    self.xmls = self.xmls + other_rule.xmls
    self.references = utils.unique(self.references + other_rule.references)
    self.referencers = self.referencers + other_rule.referencers

  def to_xml(self):
    xml = '  <RULE NAME="%s" TOPLEVEL="ACTIVE">\n' % (self.name,)
    if len(self.xmls) == 1:
      xml = xml + self.xmls[0]
    else:
      xml = xml + '  <L>\n'
      xml = xml + "".join(self.xmls)
      xml = xml + '  </L>\n'
    xml = xml + '  </RULE>\n\n'
    return xml


class MicrosoftSRGrammarGenerator:
  def __init__(self, p):
    self.parser = p
    self.ppp = parser.PhrasalPatternParser()
    self.isa_generated = []
    self.rules = {}
    self.output_dir = ""

  def add_rule(self, rule):
    base = rule.name
    if base in self.rules:
      # If we already have a rule for this class, combine the
      # two rules.
      self.rules[base].combine(rule)
    else:
      self.rules[base] = rule

  def to_xml(self):
    # The grammar compiler seems touchy about having RULEs defined
    # before they're referenced with RULEREF; sometimes it doesn't
    # seem to mind, other times it does.  To be safe, we
    # topologically sort the rules so we never reference a rule
    # that hasn't been defined.
    rules = self.tsort_rules(self.rules)
    gs = ""
    gs = gs + '<!--\n     This recognition grammar was automatically generated\n     by speechutil.py on %s\n-->\n\n' % \
         (time.asctime(),)
    gs = gs + '<GRAMMAR LANGID="409">\n'
    for rule in rules:
      gs = gs + rule.to_xml()
    gs = gs + '</GRAMMAR>\n'
    return gs

  def tsort_rules(self, rules):
    # This is the algorithm from p. 22 of Bentley's _More
    # Programming Pearls_.

    # First some setup: calculate successors and predecessor
    # counts.
    rules = rules.values()
    predecessor_count = {}
    successor_count = {}
    successors = {}
    for rule in rules:
      predecessor_count[rule.name] = len(rule.references)
      successor_count[rule.name] = 0
      successors[rule.name] = []
      for ref in rule.references:
        assert ref in self.rules, "No rule defined for %s" % (ref,)
    for rule in rules:
      for ref in rule.references:
        if ref in successors:
          successors[ref].append(rule.name)
        else:
          successors[ref] = [rule.name]
        successor_count[ref] = successor_count.get(ref, 0) + 1

    queue = []
    # Find all rules with no predecessors and enqueue them.
    for name in predecessor_count:
      if predecessor_count[name] == 0:
        queue.append(name)
    # (Sort the rules by class name; it just looks nicer.)
    queue.sort(key=lambda r: r)

    # Now we do the real sorting.
    result = []
    while (len(queue) > 0):
      k = queue.pop(0)
      result.append(k)
      for successor in successors.get(k, []):
        predecessor_count[successor] = predecessor_count[successor] - 1
        if predecessor_count[successor] == 0:
          queue.append(successor)

    result = map(lambda name: self.rules[name], result)

    if not len(result) == len(self.rules):
      self.output_debug_info(self.rules, result)
      logging.warn('Apparent cycle in rules.  Not throwing assertion.  '
                   'See grammar_debug.txt for details.')
    return result

  def output_debug_info(self, orig_list, sorted_list):
    """To help with debugging, output two lists of rules to a debug file:
    the original rules, and the new topologically sorted list.
    """
    debug_file = os.path.join(self.output_dir, "grammar_debug.txt")
    out = open(debug_file, "w")
    out.write(('Debugging problem where original rule set had %d entries, '
               'and sorted set has %d\n') % (len(orig_list), len(sorted_list)))

    only_in_orig = []
    for name in orig_list:
      if (name not in [elem.name for elem in sorted_list
                       if elem.name == name]):
        only_in_orig.append(name)

    out.write("Rules missing from the sorted list:\n")
    for name in only_in_orig:
      out.write(name + "\n")
    out.close()

  def generate_direct_phrasal_rules(self):
    for name in self.parser.phrasal_patterns:
      sys.stdout.write(".")
      sys.stdout.flush()
      for obj in self.parser.phrasal_patterns[name]:
        tree = self.ppp.parse_tree(obj)
        (xml, refs) = self.phrase_tree_to_grammar(name, tree)
        rule = Rule(name, '    ' + xml + '\n', refs)
        self.add_rule(rule)

  def generate_indirect_phrasal_rules(self):
    for base in self.parser.phrasal_patterns:
      sys.stdout.write(".")
      sys.stdout.flush()
      self.generate_isa_rules(base)

  def generate_grammar(self):
    self.isa_generated = []
    self.rules = {}

    # First create a rule for every class that has a phrasal
    # pattern attached directly to it.
    self.generate_direct_phrasal_rules()

    # Then create rules for classes that don't have phrases
    # directly attached, but have children with phrases.
    self.generate_indirect_phrasal_rules()

    # Generate the special number rules
    self.generate_number_rules()

    logging.info('Grammar has %s rules.\n', len(self.rules))
    return self.to_xml()

  def generate_isa_rules(self, base):
    for parent in self.parser.kb.all_proper_parents(base):
      if not parent in self.isa_generated:
        sys.stdout.write(".")
        self.isa_generated.append(parent)
        xml = ''
        children = self.parser.kb.all_proper_children(parent)
        children = filter(self.children_have_language, children)
        if len(children) > 1:
          xml = xml + '    <L>\n'
          for child in children:
            xml = xml + '      <RULEREF NAME="%s"/>\n' % (child.op,)
          xml = xml + '    </L>\n'
        else:
          xml = xml + '    <RULEREF NAME="%s"/>\n' % (children[0].op,)
        rule = Rule(parent, xml, children)
        self.add_rule(rule)

  def children_have_language(self, base):
    # Returns True if the class has a child with a phrasal pattern
    # attached.
    #
    # Note that it's much faster to use the all_children_generator
    # here because we usually find a child with a phrase, at which
    # point we can short circuit without having to look at or even
    # generate any more children.
    for child in self.parser.kb.all_children_generator(logic.expr(base)):
      if child in self.parser.phrasal_patterns:
        return True
    return False

  def phrase_tree_to_grammar(self, base, tree):
    def xform_objs(objs):
      refs = []
      xmls = []
      for obj in objs:
        (newxml, newrefs) = self.phrase_tree_to_grammar(base, obj)
        xmls.append(newxml)
        refs = refs + newrefs
      return (" ".join(xmls), refs)

    type = tree[0]
    if type == ":sequence":
      (xml, refs) = xform_objs(tree[1:])
      return  ("<P>%s</P>" % (xml,), refs)
    elif type == ":symbol":
      return ("<P>%s</P>" % (tree[1],), [])
    elif type == ":slotref":
      slot = tree[1][1]
      if slot == ":head":
        return ('<RULEREF NAME="%s"/>' % (base.op,), [base])
      else:
        name = self.parser.slot_constraint(base, tree[1][1])
        return ('<RULEREF NAME="%s"/>' % (name.op,), [name])
    elif type == ":optional":
      (xml, refs) = xform_objs(tree[1:])
      return ("<O>%s</O>" % (xml,), refs)
    elif type == ":any":
      (xml, refs) = xform_objs(tree[1:])
      return ("<L>%s</L>" % (xml,), refs)
    else:
      raise SyntaxError('Unknown element %s. (%s)' % (type, tree))

  def generate_number_rules(self):
    # Generates rules corresponding to the Parser's pre-parser for
    # numbers.
    xml = "<L>"
    digits = zip(parser.Cardinals.values(), parser.Cardinals.keys())
    digits = sorted(digits, key=operator.itemgetter(0))
    for digit in digits:
      unused_value, name = digit
      xml = xml + "<P>%s</P>" % (name,)
    xml = xml + "</L>"
    rule = Rule('c-digit', xml, [])
    self.add_rule(rule)

    xml = '<L><P><RULEREF NAME="c-digit"/></P><P>' + \
          '<RULEREF NAME="c-digit"/><RULEREF NAME="c-integer"/></P></L>'
    rule = Rule('c-integer', xml, ['c-digit'])
    self.add_rule(rule)


class GrammarConverterApp:
  def __init__(self, args):
    if len(args) != 3:
      self.usage()
      sys.exit(1)
    else:
      self.fdlPath = args[1]
      self.grammarPath = args[2]

  def handle_fdl_frame(self, frame):
    class_name = frame['class_name']
    parent = frame['parent']
    constraints = frame['constraints']

    if parent != None:
      if frame['is_instance']:
        self.kb.assert_instanceof(logic.expr(class_name), logic.expr(parent))
      else:
        self.kb.assert_isa(logic.expr(class_name), logic.expr(parent))

    for name in constraints:
      self.kb.tell(logic.expr("$constraint")(logic.expr(class_name),
                                             logic.expr(name),
                                             logic.expr(constraints[name])))

    for phrase in frame['phrases']:
      self.parser.add_phrasal_pattern(logic.expr(class_name), phrase)

  def handle_lexicon(self, lexemes):
    pass

  def run(self):
    self.kb = logic.PropKB()
    self.parser = parser.ConceptualParser(self.kb)
    f = fdl.FDLParser(self)
    f.parse_fdl_file(self.fdlPath)
    gen = MicrosoftSRGrammarGenerator(self.parser)
    gen.output_dir = os.path.dirname(self.grammarPath)

    # FIXME: make it write to temp file first, so that it doesn't clobber
    # original grammar file in case of error.
    sys.stdout.write("generating")
    out = open(self.grammarPath, "w")
    out.write(gen.generate_grammar())

  def usage(self):
    sys.stderr.write("Usage: \n")
    sys.stderr.write("speechutil.py <fdl path> <SR grammar path>\n")


if __name__ == '__main__':
  app = GrammarConverterApp(sys.argv)
  app.run()
