from energid import logic
from energid import fdl
from energid import parser

kb = logic.PropKB()
handler = fdl.BaseFrameHandler(kb, parser.ConceptualParser(kb), parser.IndexedConceptParser(kb))
fdlp = fdl.FDLParser(handler)
fdlp.parse_fdl_file("../../../data/dialog/world.fdl")
print kb.isa(logic.expr("i-Northern-Mountains"), logic.expr("c-thing"))
print kb.all_parents(logic.expr("i-Northern-Mountains"))
print kb.ask_all(logic.expr("objid(i-Northern-Mountains, ?x)"))
