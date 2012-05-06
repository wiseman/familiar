#!/usr/bin/env python2.5
"""Conceptual parser.

This module provides two types of natural language parsers:

1. ConceptualParser, a conceptual, frame-based parser in the style of
Charles Martin's Direct Memory Access Parser.

2. IndexedConceptParser, a less strict parser based on the parser in
Will Fitzgerald's thesis "Building Embedded Conceptual Parsers".
"""


from hml.dialog import logic
from hml.dialog import fdl
from hml.dialog import utils
from hml.dialog import stemmer

import time
import re
import string
import sys
from copy import copy
import math
import StringIO

import pprint
import getopt


# We'll be using $constraint internally.
CONSTRAINT_EXPR = logic.expr("$constraint")


def tokenize(string):
  """Tokenizes a string.  Tokens consist of characters that are
  letters, digits or underscores.  This function is primarily intended
  for text typed directly by users or from a speech recognizer.
  """
  regex = re.compile(r'\W+')
  tokens = regex.split(string.lower())
  tokens = filter(lambda token: len(token) > 0, tokens)
  return tokens


class ParserBase:
  """A simple base class for the ConceptualParser and the
  IndexedConceptParser.  Really just provides a tokenize method and a
  parse method.
  """
  def __init__(self):
    self.debug = 0
      
  def tokenize(self, string):
    """Tokenizes a string."""
    tokens = tokenize(string.lower())
    if self.debug > 0:
      print "Tokens: %s" % (tokens,)
    return tokens

  def parse(self, string, debug = 0):
    """Parses a string.  Returns the list of valid parses."""
    if not isinstance(string, basestring):
      raise TypeError, "%s is not a string." % (string,)
    results = self.parse_tokens(self.tokenize(string), debug)
    if len(results) > 1:
      results = utils.remove_duplicates(results)
    for result in results:
      result.text = string
    return results

Cardinals = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
             "six": 6, "seven": 7, "eight": 8, "nine": 9, "niner": 9, "ten": 10}


# ----------------------------------------
# Conceptual Parser
# ----------------------------------------

class ConceptualParser(ParserBase):
  """A DMAP-inspired conceptual memory parser."""

  def __init__ (self, kb, stem=False):
    ParserBase.__init__(self)
    self.kb = kb
    self.kb.define_fluent(CONSTRAINT_EXPR, inherited=True)
    self.syntax_functions = {}
    self.preparsers = []
    self.anytime_predictions = {}
    self.dynamic_predictions = {}
    self.phrasal_patterns = {}
    self.phrasal_pattern_objects = {}
    self.references = []
    self.reference_callback = None
    # Stemming in the ConceptualParser is not well tested; It's really
    # only used when we're a servant of the ICP.
    self.stem = stem
    if stem:
      self.stemmer = stemmer.PorterStemmer()
    self.install_syntax_functions()
    self.install_preparsers()
    self.reset()

  def install_syntax_functions(self):
    """Installs the standard syntax directives."""
    self.syntax_functions[":head"] = head_prediction_generator
    self.syntax_functions[":optional"] = optional_prediction_generator
    self.syntax_functions[":sequence"] = sequence_prediction_generator
    self.syntax_functions[":any"] = any_prediction_generator

  def install_preparsers(self):
    def parse_c_number(token):
      return logic.Description(logic.expr("c-number"),
                               {logic.expr("value"): logic.expr(int(token))})
    self.add_preparser("[0-9]+", parse_c_number)

    def parse_cardinal(token):
      return logic.Description(logic.expr("c-digit"),
                               {logic.expr("value"): logic.expr(Cardinals[token])})
    self.add_preparser("one|two|three|four|five|six|seven|eight|nine|ten|zero",
                       parse_cardinal)

    def parse_mgrs_square(token):
      return logic.Description(logic.expr("c-mgrs-square"),
                               {logic.expr("letters"): logic.expr(token)})
    self.add_preparser("[a-z][a-z]", parse_mgrs_square)

  def add_preparser(self, regex, function):
    matcher = re.compile(regex)
    self.preparsers.append([matcher, function])

  def check_preparsers(self, token):
    """Checks to see if any preparsers would like ot handle the token.
    If not, None is returned, otherwise the result of preparsing the
    token is returned.
    """
    for [matcher, function] in self.preparsers:
      match = matcher.match(token)
      if match == None or match.end() != len(token):
        pass
      else:
        return function(token)
    return None

  def preparse(self, token):
    """Runs the token through any relevant preparser."""
    result = self.check_preparsers(token)
    if result == None:
      return token
    else:
      return result

  def reset (self):
    """Resets the parser state as if it hadn't yet parsed anything."""
    self.dynamic_predictions = {}
    self.position = 0
    self.references = []

  def add_phrasal_pattern (self, base, phrasal_pattern):
    """Adds a phrasal pattern to a class.  The phrasal_pattern
    argument is a string using the phrasal pattern syntax,
    e.g. "<action> the ?:[dang|darn] <object>" (see the
    PhrasalPatternParser class).
    """
    if not base in self.phrasal_patterns:
      self.phrasal_patterns[base] = [phrasal_pattern]
    else:
      self.phrasal_patterns[base].append(phrasal_pattern)
    
    pattern_parser = PhrasalPatternParser(stem=self.stem)
    pp_obj = pattern_parser.parse(phrasal_pattern)
    self.add_phrasal_pattern_object(base, pp_obj)

  def add_phrasal_pattern_object (self, base, phrasal_pattern_obj):
    if not base in self.phrasal_pattern_objects:
      self.phrasal_pattern_objects[base] = [phrasal_pattern_obj]
    else:
      self.phrasal_pattern_objects[base].append(phrasal_pattern_obj)
        
    for pred in self.generate_predictions(base, [phrasal_pattern_obj], None, None, {}, 0.0):
      self.index_anytime_prediction(pred)

  def index_prediction (self, table, prediction):
    target = self.prediction_target(prediction)
    if target in table:
      table[target].append(prediction)
    else:
      table[target] = [prediction]
    
  def index_anytime_prediction(self, prediction):
    """Adds a prediction to the set of anytime predictions."""
    if self.debug > 1:
      print "Indexing anytime prediction %s" % (prediction,)
    self.index_prediction(self.anytime_predictions, prediction)
    
  def index_dynamic_prediction(self, prediction):
    """Adds a prediction to the set of dynamic predictions."""
    if self.debug > 1:
      print "Indexing dynamic prediction %s" % (prediction,)
    self.index_prediction(self.dynamic_predictions, prediction)
      
  def predictions_on(self, item):
    preds = predictions_on(self.dynamic_predictions, item) + predictions_on(self.anytime_predictions, item)
    if self.debug > 1:
      print "Predictions on %s are %s" % (item, preds)
    return preds

  def clear_predictions(self):
    self.anytime_predictions = {}
    self.dynamic_predictions = {}
  
  def pparse(self, string, debug = 0):
    """Parses a string and pretty-prints the results."""
    pprint.pprint(map(logic.Description.dictify,
                      self.parse(string, debug)))
  
  def parse_tokens (self, tokens, debug=0):
    """Parses a sequence of tokens. Returns the list of valid parses."""
    self.reset()
    self.debug = debug
    for position, token in enumerate(tokens):
      if self.stem:
        token = self.stemmer.stem(token)
      if not isinstance(token, basestring):
        raise TypeError, "Only string tokens are allowed; %s is not a string." % (token,)
      self.reference(token, self.position, self.position, 0.0)
      preparse = self.check_preparsers(token)
      if preparse != None:
        self.reference(preparse, self.position, self.position, 0.0)
      self.position = position + 1
    parses = self.complete_parses(len(tokens))
    return self.complete_parses(len(tokens))

  def complete_parses(self, pos):
    """Returns a list of complete parses given the current parser
    state.
    """
    parses = []
    for [item, start, end, value] in self.references:
        if start == 0 and end == pos - 1 and isinstance(item, logic.Description):
          parses.append(item)
#          print "PARSE: %s %s" % (item, value)
    return parses

  def reference (self, item, start, end, value):
    # References an item (a token string or a class).
    assert isinstance(item, basestring) or isinstance(item, logic.Description)
    if self.debug > 0:
      print "referencing %s" % ((item, start, end),)
    self.references.append([item, start, end, value])
    for abst in self.all_abstractions(item):
      if self.reference_callback != None:
        apply(self.reference_callback, [abst, start, end, value])
      for prediction in self.predictions_on(abst):
        self.advance_prediction(prediction, item, start, end)

  def advance_prediction(self, prediction, item, start, end):
    # Advances a prediction.
    if self.debug > 2:
      print "Advancing prediction %s" % ((prediction, item, start, end),)
    if prediction.next == None or prediction.next == start:
      phrasal_pattern = prediction.phrasal_pattern[1:]
      if prediction.start != None:
        start = prediction.start
      if is_head(prediction.phrasal_pattern[0]):
        base = item.base
        try:
          slots = self.merge_slots(prediction.slots, item.slots)
        except DuplicateSlotError:
          return
      else:
        base = prediction.base
        slots = self.extend_slots(prediction, item)
      if phrasal_pattern == []:
        # Prediction has been used up.
#        print "Fulfilled prediction %s" % (prediction,)
        self.reference(self.find_frame(base, slots), start, end, prediction.value)
      else:
        for prediction in self.generate_predictions(base, phrasal_pattern, start, self.position + 1, slots, prediction.value):
          if len(prediction.phrasal_pattern) > 0:
            self.index_dynamic_prediction(prediction)
          else:
            self.reference(self.find_frame(prediction.base, slots), start, end, prediction.value)

  def generate_predictions(self, base, phrasal_pattern, start, position, slots, value):
    predictions = list(self.generate_predictions2(base, phrasal_pattern,
                                                  start, position, slots, value))
    return predictions

  def generate_predictions2(self, base, phrasal_pattern, start, position, slots, value):
    # If there's no syntax directive, it's an implicit sequence.  Make
    # explicit what's implicit.
    if not self.is_syntax_directive(phrasal_pattern[0]):
      phrasal_pattern = [[":sequence"] + phrasal_pattern]

    new_predictions = apply(self.syntax_functions[phrasal_pattern[0][0]],
                            [base, phrasal_pattern, start, position, slots])
    for pred in new_predictions:
      pred.value = pred.value + value
      if len(pred.phrasal_pattern) > 0 and self.is_syntax_directive(pred.phrasal_pattern[0]):
        for p in self.generate_predictions2(base, pred.phrasal_pattern,
                                            start, position, slots, value):
          yield p
      else:
        yield pred

  def is_syntax_directive(self, term):
    # Checks whether a term in a phrasal pattern is a syntax
    # directive, e.g. [":optional" ...].
    if isinstance(term, list):
      if term[0] in self.syntax_functions:
        return True
      raise ValueError, "%s is not a valid syntax function." % (term[0],)
    else:
      return False

  def merge_slots(self, pred_slots, item_slots):
    # Merges two sets of slots into one superduper collection of
    # slots.
    for slot in pred_slots:
      if slot in item_slots:
        raise DuplicateSlotError, "Slot %s already has the value %s." % (slot, item_slots[slot])
    slots = {}
    for slot in pred_slots:
      slots[slot] = pred_slots[slot]
    for slot in item_slots:
      slots[slot] = item_slots[slot]
    return slots

  def find_frame(self, base, slots):
    # Creates a description with the specified base class and slots.
    return logic.Description(base, slots)
  
  def extend_slots(self, prediction, item):
    # If the prediction is waiting for a slot-filler, and the item we
    # saw can fill the slot, add the slot with filler to the
    # predictions slots.
    spec = prediction.phrasal_pattern[0]
    slots = prediction.slots
    if is_role_specifier(spec):
      new_slots = copy(slots)
      new_slot = self.role_specifier(spec)
      if new_slot in new_slots:
        raise DuplicateSlotError, "Slot %s already exists in %s." % (new_slot, prediction)
      new_slots[new_slot] = item
      return new_slots
    else:
      return slots

  def prediction_target(self, prediction):
    assert(not self.is_syntax_directive(prediction.phrasal_pattern[0]),
           "Cannot index on syntax directive %s." % (prediction.phrasal_pattern[0]))
    spec = prediction.phrasal_pattern[0]
    if is_role_specifier(spec):
      base = prediction.base
      value = self.slot_constraint(base, self.role_specifier(spec))
      if value != None:
        return value
      else:
        raise ValueError, "%s has no constraint in %s." % (spec, base)
    elif is_head(spec):
      return prediction.base
    else:
      return spec

  def all_abstractions(self, item):
    if isinstance(item, basestring):
        return [item]
    elif isinstance(item, logic.Expr):
      return self.kb.all_parents(item)
    elif isinstance(item, logic.Description):
      return self.kb.all_parents(logic.expr(item.base))
    else:
      raise ValueError, "%s must be a string or Expr." % (repr(item,))

  def slot_constraint(self, item, role_spec):
    # Looks up the constraint on the specified slot for item.
    return self.kb.slot_value(logic.expr(item), CONSTRAINT_EXPR, logic.expr(role_spec))

  def role_specifier (self, item):
    return logic.expr(item[1:])



class Prediction:
  """Represents a prediction the parser has made about what the next
  token might be and what frame it is part of.
  """
  def __init__(self, base, phrasal_pattern, start, next, slots, value):
    self.base = base
    self.phrasal_pattern = phrasal_pattern
    self.start = start
    self.next = next
    self.slots = slots
    self.value = value

  def __repr__(self):
    return "<%s base: %s start: %s next: %s slots: %s pattern: %s value: %s>" % \
           (self.__class__.__name__, repr(self.base), self.start, self.next,
            repr(self.slots), self.phrasal_pattern, self.value)

  # We make phrasal_pattern a somewhat fancy attribute of this class;
  # When it's set to a sequence, we automatically tokenize the first
  # element.
  #
  # pred.phrasal_pattern = ["how are you", "john?"]
  #
  # pred.phrasal_pattern -> ["how", "are", "you", "john?"]
  #
  # FIXME: This doesn't feel like the best place to do this.
  def __setattr__(self, name, value):
    if name == 'phrasal_pattern':
      if len(value) > 0 and isinstance(value[0], basestring) and value[0][0] != ':' and value[0][0] != '?':
        tokens = self.tokenize(value[0])
        self.__dict__[name] = tokens + value[1:]
      else:
        self.__dict__[name] = value
    else:
      self.__dict__[name] = value

  def __getattr__(self, name):
    if name == "phrasal_pattern":
      return self._phrasal_pattern
    else:
      raise AttributeError, name

  def tokenize(self, string):
    return tokenize(string)


def predictions_on(prediction_table, item):
  if item in prediction_table:
    predictions = prediction_table[item]
  else:
    predictions = []
  return predictions


# These *_prediction_generator functions are used for syntax directive
# processing.  They return a list of new predictions.

def head_prediction_generator(base, phrasal_pattern, start, position, slots):
  # Generates predictions for :head.
  return [Prediction(base, [":head"] + phrasal_pattern[1:], start, position, slots)]

def sequence_prediction_generator(base, phrasal_pattern, start, position, slots):
  # Generates predictions for :sequence.
  return [Prediction(base, phrasal_pattern[0][1:] + phrasal_pattern[1:],
                     start, position, slots, 1.0)]

def optional_prediction_generator(base, phrasal_pattern, start, position, slots):
  # Generates predictions for :optional.
  return [Prediction(base, phrasal_pattern[1:], start, position, slots, 0.2),
          Prediction(base, phrasal_pattern[0][1:] + phrasal_pattern[1:], start, position, slots, 0.0)]

def any_prediction_generator(base, phrasal_pattern, start, position, slots):
  # Generates predictions for :any.
  preds = map(lambda pat: Prediction(base, [pat,] + phrasal_pattern[1:],
                                     start, position, slots, 0.0),
              phrasal_pattern[0][1:])
  return preds
  

class DuplicateSlotError(Exception):
  pass


def is_role_specifier (item):
  return item[0] == '?'
  
def is_head(item):
  return item == ":head"


class PhrasalPatternParser:
  """Parses phrasal patterns.

  <color> is a reference to a slot named color.
  <:head> is special, and refers to the phrase head.
  ?:thing means that thing is optional.
  [thing-a|thing-b] means that either thing-a or thing-b are acceptable.

  Examples:

  "pick up ?:the <object>"
  "?:<name>, ?:[please|would you] clean my <object>"
  """

  def __init__(self, stem=False):
    # We do the stemming of literal tokens in this class.  Is that
    # weird?
    if stem:
      self.stemmer = stemmer.PorterStemmer()
    else:
      self.stemmer = False

  # We do this thing where we parse into an intermediate
  # representation (as returned by parse_tree), then convert that into
  # the final form.  I don't remember how that came about and it
  # should perhaps be examined in the future.
  #
  # Pattern string:
  #   "?:[let's|let us] <action>"
  #
  # Intermediate representation:
  #   [':sequence',
  #    [':optional',
  #     [':any',
  #      [':symbol', "let's"],
  #      [':sequence', [':symbol', 'let'], [':symbol', 'us']]]],
  #    [':slotref', [':symbol', 'action']]]
  #
  # Final form:
  #   [':sequence',
  #    [':optional',
  #     [':any', [':sequence', 'let', 's'], [':sequence', 'let', 'us']]],
  #    '?action']

  def parse(self, pattern):
    """Parses a string containing a phrasal pattern into a tree
    representation.
    """
    phrasal_pattern = self.convert_parse_tree_to_phrasal_pattern(self.parse_tree(pattern))
    return phrasal_pattern

  def parse_tree(self, input):
    [object, position] = self.read_sequence(input, 0)
    return object

  def read(self, input, position):
    position = self.skip_whitespace(input, position)
    if position >= len(input):
      return [None, position]

    char = input[position]
    if char == '<':
      return self.read_slot(input, position + 1)
    elif char == '{':
      return self.read_slot(input, position + 1, "{", "}")
    elif char == '?' and input[position+1] == ':':
      return self.read_optional(input, position + 2)
    elif char == '[':
      return self.read_choice(input, position + 1)
    elif self.is_symbol_char(char):
      return self.read_token(input, position)
    else:
      raise SyntaxError, \
            "Illegal character '%s' at position %s in '%s'." % (char, position, repr(input))

  def read_sequence(self, input, position, terminators = ''):
    objects = []
    [object, position] = self.read(input, position)
    if object != None:
      objects.append(object)
    while object != None and (position >= len(input) or not input[position] in terminators):
      [object, position] = self.read(input, position)
      if object != None:
        objects.append(object)
    return [self.make_sequence(objects), position]

  def read_slot(self, input, position, slot_char='<', terminator='>'):
    [symbol, position] = self.read_symbol(input, position)
    position = self.skip_whitespace(input, position)
    if not position < len(input):
      raise SyntaxError, \
            "Unterminated '%s' in phrasal pattern '%s'." % (slot_char, input)
    if input[position] != terminator:
      raise SyntaxError, \
            "Unexpected character '%s' in slot reference in phrasal pattern '%s'" % (input[position], input)
    return [self.make_slot(symbol), position + 1]

  def read_optional(self, input, position):
    [object, position] = self.read(input, position)
    return [self.make_optional(object), position]

  def read_choice(self, input, position):
    choices = []
    while input[position] != ']':
      [object, position] = self.read_sequence(input, position, '|]')
      position = self.skip_whitespace(input, position)
      if position >= len(input):
        raise SyntaxError, "Unterminated '[' in '%s'." % (input,)
      if not (input[position] == ']' or input[position] == '|'):
        raise SyntaxError, "Illegal character '%s' in '%s'." % (input[character], input)
      if input[position] == '|':
        position = position + 1
      choices.append(object)
    return [self.make_choice(choices), position + 1]

  def read_symbol(self, input, position):
    position = self.skip_whitespace(input, position)
    start_position = position
    while position < len(input) and self.is_symbol_char(input[position]):
      position = position + 1
    return [self.make_symbol(input[start_position:position]), position]

  def read_token(self, input, position):
    position = self.skip_whitespace(input, position)
    start_position = position
    while position < len(input) and self.is_symbol_char(input[position]):
      position = position + 1
    return [self.make_symbol(self.maybe_stem(input[start_position:position])), position]
    

  def make_symbol(self, string):
    return [":symbol", string]

  def make_sequence(self, objects):
    if len(objects) == 1:
      return objects[0]
    else:
      return [":sequence"] + objects
  
  def make_optional(self, object):
    return [":optional", object]

  def make_choice(self, objects):
    if len(objects) == 1:
      return objects[0]
    else:
      return [":any"] + objects

  def make_slot(self, symbol):
    return [":slotref", symbol]

  def skip_whitespace(self, input, position):
    while position < len(input) and (input[position] == ' ' or input[position] == '\n'):
      position = position + 1
    return position

  def is_symbol_char(self, char):
    return char in string.digits or char in string.letters or char in "-'?:"

  def convert_parse_tree_to_phrasal_pattern(self, tree):
    type = tree[0]
    if type == ':sequence':
      return [":sequence"] + map(self.convert_parse_tree_to_phrasal_pattern, tree[1:])
    elif type == ':symbol':
      if tree[1][0] == '?' and tree[1][1] in string.letters:
        return tree[1]
      else:
        symbols = tokenize(tree[1])
        if len(symbols) == 1:
          return symbols[0]
        else:
          return [":sequence"] + symbols
    elif type == ':slotref':
      symbol_str = tree[1][1]
      if symbol_str == ":head":
        return ":head"
      else:
        return "?" + symbol_str
    elif type == ':optional':
      return [":optional"] + map(self.convert_parse_tree_to_phrasal_pattern, tree[1:])
    elif type == ':any':
      return [":any"] + map(self.convert_parse_tree_to_phrasal_pattern, tree[1:])
    else:
      raise SyntaxError, "Unknown element %s. (%s)" % (type, tree)

  def maybe_stem(self, token):
    if self.stemmer:
      return self.stemmer.stem(token)
    else:
      return token
    

class FrameHandler(fdl.BaseFrameHandler):
  def __init__(self, kb, cp, icp):
    fdl.BaseFrameHandler.__init__(self, kb, cp, icp)
    self.constraints = {}
    
  def handle_constraints(self, frame, constraints):
    fdl.BaseFrameHandler.handle_constraints(self, frame, constraints)
    if len(constraints) > 0:
      self.constraints[frame['class_name']] = constraints
      

class InteractiveParserApp:
  """Lets you interactively play with a ConceptualParser."""
  def __init__(self, argv):
    self.debug = 0
    self.run_tests = False
    self.transcript_path = None
    self.test_classes = []
    optlist, args = getopt.getopt(argv[1:], 'td:f:c:')
    for o, v in optlist:
      if o == '-d':
        self.debug = v
      elif o == '-t':
        self.run_tests = True
      elif o == '-c':
        self.test_classes = v.split(",")
      elif o == '-f':
        self.transcript_path = v
    self.fdl_file = args[0]

  def run(self):
    self.kb = logic.PropKB()
    self.cp_parser = ConceptualParser(self.kb)
    self.icp_parser = IndexedConceptParser(self.kb)
    self.fdl_handler = FrameHandler(self.kb, self.cp_parser, self.icp_parser)
    self.fdl_parser = fdl.FDLParser(self.fdl_handler)
    self.fdl_parser.parse_fdl_file(self.fdl_file, self.debug)

    if self.run_tests:
      self.check_constraints()
      self.fdl_parser.run_test_phrases(self.test_classes, self.cp_parser, self.icp_parser)

    if self.transcript_path:
      for line in open(self.transcript_path):
        line = line[0:-1]
        if len(line) > 0:
          print "\n*** %s" % (line,)
          parses = self.cp_parser.parse(line)
          print "  %s:" % (len(parses),)
          pprint.pprint(parses)
        
    if not self.run_tests and not self.transcript_path:
      self.do_parse_loop()


  def check_constraints(self):
    def can_be_constraint(concept):
      for c in self.kb.all_children(logic.expr(concept)):
        if c in self.cp_parser.phrasal_patterns:
          return True
      return False
  
    for class_name in self.fdl_handler.constraints:
      constraints = self.fdl_handler.constraints[class_name]
      for name in constraints:
        type = constraints[name]
        if not can_be_constraint(type):
          print "Warning: %s has constraint '%s IS-A %s' which has no phrasal patterns" % \
                (class_name, name, type)
        sv = self.kb.slot_value(logic.expr(class_name), logic.expr(name))
        if sv:
          if not self.kb.isa(sv, logic.expr(type)):
            print "Warning: %s has constraint '%s IS-A %s' which is not consistent with slot value %s" % \
                  (class_name, name, type, sv)

  def do_parse_loop(self):
    while True:
      sys.stdout.write("\n\n? ")
      input = sys.stdin.readline()
      if len(input) == 0:
        break
      if input[0] == '#':
        print "CP: " + self.cp_parser.predictions_on(eval(input[1:]))
        print "ICP: " + self.icp_parser.predictions_on(eval(input[1:]))
      elif input[0] == '%':
        print "CP: " + self.cp_parser.anytime_predictions
        print "ICP: " + self.icp_parser.anytime_predictions
      else:
        print "\nCP:  ==> \n%s" % pprint.pformat((self.cp_parser.parse(input, debug=self.debug),))
        print "\nICP: ==> \n%s" % pprint.pformat((self.icp_parser.parse(input, debug=self.debug),))



# --------------------------------------------------
# Indexed Concept Parser
# --------------------------------------------------

# Only parse results with a score greater than this will be returned.
CUTOFF_ICP_SCORE = -1000000
MIN_PROBABILITY = -100.0/CUTOFF_ICP_SCORE
MIN_INFORMATION_VALUE = -100.0/CUTOFF_ICP_SCORE


class IndexedConceptParser(ParserBase):
  """A Will Fitzgerald-style Indexed Concept Parser."""

  def __init__(self, kb):
    ParserBase.__init__(self)
    self.debug = 0
    self.kb = kb
    self.cp_parser = ConceptualParser(kb, stem=True)
    self.index_sets = {}
    self.target_concepts = {}
    self.appraisers = []
    self.total_appraiser_votes = 0
    self.stemmer = stemmer.PorterStemmer()
    self.index_set_pattern_parser = IndexSetPatternParser(kb)
    self.install_standard_appraisers()
    self.unique_target_concepts = {}

  def add_appraiser(self, appraiser, votes):
    self.appraisers.append([appraiser, votes])
    self.total_appraiser_votes = self.total_appraiser_votes + votes
    
  def install_standard_appraisers(self):
    self.add_appraiser(PredictedScore(self), 1)
    self.add_appraiser(UnpredictedScore(self), 1)
    self.add_appraiser(UnseenScore(self), 1)
    self.add_appraiser(RequiredScore(self), 10)
  
  def stem(self, token):
    if isinstance(token, basestring):
      return self.stemmer.stem(token)
    else:
      return token

  def parse_tokens(self, tokens, debug=0):
    self.debug = debug
    self.cp_parser.debug = debug
    indices = self.find_indices(tokens, self.match_function)
    if debug > 0:
      print "ICP parsing tokens %s" % (tokens,)
    if debug > 1:
      print "ICP found indices %s" % (indices,)
    results = self.score_index_sets(indices)
    results.sort(key=lambda x: x.score, reverse=True)
    results = [result for result in results if result.score > CUTOFF_ICP_SCORE]
    results = utils.remove_duplicates(results,
                                      lambda r1, r2: r1.target_concept == r2.target_concept)
    if debug > 0:
      print "ICP results: %s" % (results,)
    return results

  def find_indices(self, tokens, match_fn):
    return apply(match_fn, [tokens])

  def match_function(self, tokens):
    # Uses the CP to parse tokens and returns a list of the tokens and
    # any concepts that were referenced.
    items = []
    def add_ref(item, start, end, value):
#      print "REFERENCING %s" % (item,)
      if isinstance(item, logic.Description):
        items.append(logic.expr(item))
      else:
        items.append(item)
    self.cp_parser.reference_callback = add_ref
    self.cp_parser.parse_tokens(tokens, debug=self.debug)
    return items

  def score_index_sets(self, found_indices):
    results = []
    for index_set in self.candidate_index_sets(found_indices):
#      print "INDEX SET %s" % (index_set,)
      result = ICPResult(None,
                         self.index_set_score(index_set, found_indices),
                         index_set.target_concept,
                         index_set.indices,
                         self.extract_slot_fillers(index_set, found_indices))
      results.append(result)
    return results

  def extract_slot_fillers(self, index_set, found_indices):
    # found_indices may be something like ["big", c-big, c-size], in
    # which case we want the most specific concept (c-big) to fill our
    # slot.
    def maybe_use_filler(indices, current_filler, candidate_filler):
      if current_filler == None:
        return candidate_filler
      elif self.kb.isa(logic.expr(indices[candidate_filler]),
                       logic.expr(indices[current_filler])):
        return candidate_filler
      else:
        return current_filler
      
    result_slots = {}
    for [slot, constraint] in index_set.slots:
      filler = None
      for i, index in enumerate(found_indices):
        if isinstance(index, logic.Expr) and self.kb.isa(index, constraint) and \
           not (i in result_slots.values()):
          filler = maybe_use_filler(found_indices, filler, i)
      if filler != None:
        result_slots[slot] = filler
    for k, v in result_slots.items():
      result_slots[k] = found_indices[result_slots[k]]
    return result_slots
  
  def candidate_index_sets(self, found_indices):
    candidates = []
    abstractions = []
    for index in found_indices:
      abstractions = abstractions + self.all_abstractions(index)
    for index in abstractions:
      candidates = candidates + self.index_sets.get(index, [])
#    print "candidates for %s are %s" % (found_indices, candidates)
    return utils.remove_duplicates(candidates)

  def all_abstractions(self, item):
    if isinstance(item, basestring):
        return [item]
    elif isinstance(item, logic.Expr):
      return self.kb.all_parents(item)
    elif isinstance(item, logic.Description):
      return self.kb.all_parents(logic.expr(item.base))
    else:
      raise ValueError, "%s must be a string or Expr." % (repr(item,))

  def install(self, index_set):
    """Installs an index set."""
#    print "Installing: %s" % (index_set,)
    index_set.indices = map(self.stem, index_set.indices)
    index_set.required_indices = map(self.stem, index_set.required_indices)
    self.unique_target_concepts[index_set.target_concept] = True
    for index in index_set.indices:
      if not index in self.target_concepts.get(index, []):
        self.target_concepts[index] = [index_set.target_concept] + self.target_concepts.get(index, [])
      if not index_set in self.index_sets.get(index, []):
        self.index_sets[index] = [index_set] + self.index_sets.get(index, [])

  def add_phrasal_pattern (self, base, phrasal_pattern):
    # We keep track of indexsets while we let the CP keep track of
    # phrasal patterns.
    self.cp_parser.add_phrasal_pattern(base, phrasal_pattern)
    
  def add_index_set(self, target_concept, indexsetpattern):
    """Adds an index set to the target concept.  The indexsetpattern
    must be a string containing an indexset pattern (see
    IndexSetPatternParser).
    """
    indexset = self.index_set_pattern_parser.parse(logic.expr(target_concept), indexsetpattern)
    self.install(indexset)

  def index_set_score(self, index_set, found_indices):
    score = 0
    for (appraiser, votes) in self.appraisers:
      if votes > 0:
        appraiser_score = self.call_appraiser(appraiser,
                                              votes / float(self.total_appraiser_votes),
                                              index_set,
                                              found_indices)
#        print "%s score for %s is %s" % (appraiser.__class__.__name__, index_set.target_concept, appraiser_score)
        score = score + appraiser_score
    return score

  def call_appraiser(self, appraiser, weight, index_set, found_indices):
    score = weight * appraiser.score(index_set, found_indices)
    return score

  def probability_of_index(self, index):
    cardinality = self.target_concept_cardinality(index)
    if cardinality == 0:
      # Very small, but > 0
      return MIN_PROBABILITY
    else:
#      print "uniq targets: %s" % (self.unique_target_concepts,)
      return float(cardinality) / len(self.unique_target_concepts)

  def target_concept_cardinality(self, index):
#    print "cardinality of %s: %s" % (index, self.target_concepts.get(index, []))
    return len(self.target_concepts.get(index, []))

  def summed_value(self, base, predicted_set):
    sum = 0.0
    for item in predicted_set:
      sum = sum + self.information_value(item)
#      print "Info value of %s is %s" % (item, self.information_value(item))
#    print "summed value of %s is %s" % (predicted_set, sum)
    return sum

  def information_value(self, index):
    value = -math.log(self.probability_of_index(index), 2)
    if value == 0.0:
      value = MIN_INFORMATION_VALUE
#    print "prob of %s is %s" % (index, self.probability_of_index(index))
    return value


class IndexSet:
  """Represents a set of indices for the IndexedConceptParser.
  Includes the target concept, the indices, and required indices.
  """
  def __init__(self, target=None, indices=None, required_indices=None, slots=None):
    def cond(test, a, b):
      if test:
        return a
      else:
        return b
      
    if isinstance(target, basestring):
      self.target_concept = logic.expr(target)
    else:
      self.target_concept = target
    self.indices = cond(indices == None, [], indices)
    self.required_indices = cond(required_indices == None, [], required_indices)
    self.slots = cond(slots == None, [], slots)

  def __repr__(self):
    s = StringIO.StringIO()
    s.write("<%s target: %s indices: %s" % \
            (self.__class__.__name__, self.target_concept, self.indices))
    if len(self.required_indices) > 0:
      s.write(" required: %s" % (self.required_indices,))
    if len(self.slots) > 0:
      s.write(" slots: %s" % (self.slots,))
    s.write(">")
    return s.getvalue()
          
    return "<%s target: %s indices: %s required: %s slot refs: %s>" % \
           (self.__class__.__name__, self.target_concept, self.indices,
            self.required_indices, self.slots)

  def __cmp__(self, other):
    if (other is self) or (isinstance(other, IndexSet) and
                           self.target_concept == other.target_concept and
                           self.indices == other.indices and
                           self.required_indices == other.required_indices):
      return 0
    else:
      return -1


class ICPResult(logic.Description):
  """Holds an Indexed Concept Parser parse result, which consists of
  the target concept, the score, the index concepts and the input
  text.
  """
  def __init__(self, text, score, target_concept, index_concepts, slots):
    logic.Description.__init__(self, target_concept, slots)
    self.text = text
    self.score = score
    self.index_concepts = index_concepts
    self.target_concept = target_concept
  
  def __repr__(self):
    return "<%s score: %s target: %s slots: %s>" % \
           (self.__class__.__name__, self.score, self.target_concept,
            self.slots)


# --------------------
# ICP Appraisers
# --------------------

class PredictedScore:
  """ICP appraiser that scores up for indices that we've seen that are
  in the indexset.
  """
  def __init__(self, parser):
    self.parser = parser
    
  def score(self, index_set, found_indices):
    predicted = index_set.indices
    pred_items = predicted_items(self.parser.kb, found_indices, predicted)
#    print "  PREDICTED: %s" % (predicted,)
#    print "  PREDICTED ITEMS: %s" % (pred_items,)
    score = (self.parser.summed_value(index_set.target_concept, pred_items) / \
             self.parser.summed_value(index_set.target_concept, predicted))
    return score

    
class UnpredictedScore:
  """ICP appraiser that penalizes for indices that we've seen that
  were not part of the indexset.
  """
  def __init__(self, parser):
    self.parser = parser

  def score(self, index_set, found_indices):
    predicted = index_set.indices
    unpred_items = unpredicted_items(self.parser.kb, found_indices, predicted)
#    print "  PREDICTED: %s" % (predicted,)
#    print "  UNPREDICTED ITEMS: %s" % (unpred_items,)
    score = 1.0 - (self.parser.summed_value(index_set.target_concept, unpred_items) / \
                   self.parser.summed_value(index_set.target_concept, found_indices))
    return score


class UnseenScore:
  """ICP appraiser that penalizes for indices we wanted to see but
  didn't.
  """
  def __init__(self, parser):
    self.parser = parser

  def score(self, index_set, found_indices):
    predicted = index_set.indices
    unseed_items = unseen_items(self.parser.kb, found_indices, predicted)
#    print "  PREDICTED: %s" % (predicted,)
#    print "  UNSEEN ITEMS: %s" % (unseed_items,)
    score = 1.0 - (self.parser.summed_value(index_set.target_concept, unseed_items) / \
                   self.parser.summed_value(index_set.target_concept, found_indices))
    return score


class RequiredScore:
  """ICP appraiser that nukes your score if there are required indices
  that were not seen.
  """
  def __init__(self, parser):
    self.parser = parser

  def score(self, index_set, found_indices):
    # Make a copy.
    found_indices = found_indices[:]
    for requirement in index_set.required_indices:
      if not requirement in found_indices:
        # Return something nice and low.
        return CUTOFF_ICP_SCORE*10
      else:
        # Don't want to use a single index to satisfy multiple
        # requirements.
        del found_indices[found_indices.index(requirement)]
    return 0.0


# --------------------
# ICP utilities
# --------------------

def is_concept(thing):
  return isinstance(thing, logic.Description) or isinstance(thing, logic.Expr)

def abst_or_whole_of(kb, big, small):
  if is_concept(big) and is_concept(small):
    return kb.isa(big, small)
  else:
    return big == small

def spec_or_part_of(kb, big, small):
  if is_concept(big) and is_concept(small):
    return kb.isa(small, big)
  else:
    return big == small

def predicted_items(kb, seen_set, predicted_set):
  return utils.intersection(predicted_set,
                            seen_set,
                            lambda e1, e2: abst_or_whole_of(kb, e1, e2))

def unpredicted_items(kb, seen_set, predicted_set):
  return utils.set_difference(seen_set,
                              predicted_set,
                              lambda e1, e2: spec_or_part_of(kb, e1, e2))

def unseen_items(kb, seen_set, predicted_set):
  return utils.set_difference(predicted_set,
                              seen_set,
                              lambda e1, e2: spec_or_part_of(kb, e1, e2))


class IndexSetPatternParser:
  """Parses indexset patterns.

  word     is a literal token.
  $concept is a concept reference.
  !thing   is a required element.
  {slot}   is a slot reference.

  Examples:

  "big $c-dog"
  "!big !$c-dog"
  "{size} !{color}"
  """

  def __init__(self, kb):
    self.kb = kb
    
  def parse(self, target, pattern):
    """Parses a string containing a indexset pattern and returns an
    IndexSet.
    """
    indexset = IndexSet(target)
    return self.read(indexset, pattern, 0)
  
  def read(self, indexset, input, position):
    [index, position] = self.read_one(indexset, input, position)
    while position < len(input):
      [index, position] = self.read_one(indexset, input, position)
    return indexset

  def read_one(self, indexset, input, position):
    position = self.skip_whitespace(input, position)
    if position >= len(input):
      return [None, position]
    char = input[position]
    if char == '$':
      return self.parse_concept(indexset, input, position)
    elif char == '!':
      return self.parse_required(indexset, input, position)
    elif char == '{':
      return self.parse_slot(indexset, input, position)
    elif self.is_symbol_char(char):
      return self.parse_token(indexset, input, position)
    else:
      raise SyntaxError, \
            "Illegal character '%s' at position %s in indexset '%s'." % \
            (char, position, repr(input))

  def parse_token(self, indexset, input, position):
    # -- Token
    [index, position] = self.read_symbol(input, position)
    indexset.indices = indexset.indices + [index]
    return [index, position]
    
  def parse_concept(self, indexset, input, position):
    [index, position] = self.read_concept(input, position + 1)
    if index == None:
      raise SyntaxError, \
            "Lone ! in indexset %s." % (repr(input),)
    indexset.indices = indexset.indices + [index]
    return [index, position]

  def parse_required(self, indexset, input, position):
    # -- Required
    [index, position] = self.read_one(indexset, input, position + 1)
    if index == None:
      raise SyntaxError, \
            "Lone ! in indexset %s." % (repr(input),)
    indexset.required_indices = indexset.required_indices + [index]
    return [index, position]

  def parse_slot(self, indexset, input, position):
    # -- Slot reference
    [slot_name, position] = self.read_slot(input, position + 1)
    if slot_name == None:
      raise SyntaxError, \
            "Empty slot reference in indexset %s." % (repr(input),)
    if slot_name in [slot_ref[0] for slot_ref in indexset.slots]:
      raise SyntaxError, \
            "Duplicate slot reference %s in indexset %s." % (slot_name, repr(input))
    slot_type = self.slot_constraint(indexset.target_concept, slot_name)
    indexset.slots.append([slot_name, slot_type])
    indexset.indices = indexset.indices + [slot_type]
    return [slot_type, position]

  def read_symbol(self, input, position):
    position = self.skip_whitespace(input, position)
    start_position = position
    while position < len(input) and self.is_symbol_char(input[position]):
      position += 1
    return [input[start_position:position], position]

  def read_concept(self, input, position):
    [symbol, position] = self.read_symbol(input, position)
    return [logic.expr(symbol), position]

  def read_slot(self, input, position):
    [symbol, position] = self.read_symbol(input, position)
    position = self.skip_whitespace(input, position)
    if not position < len(input):
      raise SyntaxError, "Unterminated '{' in indexset %s" % (repr(input),)
    if input[position] != '}':
      raise SyntaxError, \
            "Unexpected character '%s' in slot reference in indexset %s." % (input[position], repr(input))
    return [symbol, position + 1]
    
  def skip_whitespace(self, input, position):
    while position < len(input) and (input[position] == ' ' or input[position] == '\n'):
      position += 1
    return position

  def is_symbol_char(self, char):
    return char in string.digits or char in string.letters or char in "-'?:"
      
  def slot_constraint(self, item, slot):
    item = logic.expr(item)
    slot = logic.expr(slot)
    return self.kb.slot_value(item, CONSTRAINT_EXPR, slot)


  

if __name__ == "__main__":
  p = InteractiveParserApp(sys.argv)
  p.run()
