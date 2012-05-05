from energid import logic
from energid import parser
from energid import fdl

import time


COUNT = 100


def timeParse(p, phrase):
  start = time.time()
  startp = time.clock()
  for i in range(1, COUNT):
    p.parse(phrase)
  endp = time.clock()
  end = time.time()
  
  print "Parsing '%s' took %s (%s) seconds." % (phrase,
                                                (endp - startp) / COUNT,
                                                (end - start) / COUNT)

def timeAskAll(kb, query):
  start = time.time()
  startp = time.clock()
  for i in range(1, COUNT):
    kb.ask_all(query)
  endp = time.clock()
  end = time.time()
  print "Query %s took %s (%s) seconds." % (repr(query),
                                       (endp - startp) / COUNT,
                                       (end - start) / COUNT)

def timeFindInstances(kb, description):
  start = time.time()
  startp = time.clock()
  for i in range(1, COUNT):
    description.find_instances(kb)
  end = time.time()
  endp = time.clock()
  print "find_instances on %s took %s (%s) seconds." % (description,
                                                   (endp - startp) / COUNT,
                                                   (end - start) / COUNT)


class DummyIOManager:
  def add_lexicon(self, lexemes):
    pass
  
kb = logic.PropKB()
cp = parser.ConceptualParser(kb)
icp = parser.IndexedConceptParser(kb)
fdl_handler = fdl.BaseFrameHandler(kb, cp, icp)
fp = fdl.FDLParser(fdl_handler)

fp.parse_fdl_file("benchmark.fdl")


timeParse(cp, "two")
timeParse(cp, "two zero zero")
timeParse(cp, "Take the unit of measure and go three units to the west and two units to the north")


timeAskAll(kb, logic.expr("execute-method(c-loud-and-clear, foo)"))
timeAskAll(kb, logic.expr("execute-method(c-loud-and-clear, ?x)"))
timeAskAll(kb, logic.expr("$constraint(c-full-callsign, callsign, ?x)"))
timeAskAll(kb, logic.expr("ISA(?x, c-addressed-utterance)"))
timeAskAll(kb, logic.expr("ISA(c-loud-and-clear, ?x)"))
timeAskAll(kb, logic.expr("$ISA(?x, c-addressed-utterance)"))
timeAskAll(kb, logic.expr("$ISA(c-loud-and-clear, ?x)"))
d = logic.Description(logic.expr("i-kampton-city"))
timeFindInstances(kb, d)
