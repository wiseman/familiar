import difflib

from hml.base import unittest
from hml.dialog import logic
from hml.dialog import speechutil
from hml.dialog import parser
from hml.dialog import fdl


class TestCase(unittest.TestCase):

  def testMicrosoftParserGenerator(self):
    xml = """
<frames>

<frame id="c-action-request">
  <parent id="c-utterance" />
  <constraint slot="addressee" type="c-name" />
  <constraint slot="action" type="c-action" />
  <constraint slot="object" type="c-thing" />
  <phrase>
    {addressee} ?:[let's|let us|why don't we]
    {action} ?:[with|on] ?:the {object}
  </phrase>
</frame>

<frame id="c-hog">
  <parent id="c-name" />
  <phrase>hog</phrase>
</frame>

<frame id="c-gunslinger">
  <parent id="c-name" />
  <phrase>gunslinger</phrase>
</frame>

<frame id="c-restart">
  <parent id="c-action" />
  <phrase>[restart|start over]</phrase>
</frame>

<frame id="c-talkon">
  <parent id="c-thing" />
  <phrase>[talk on|talkon]</phrase>
</frame>

<frame id="i-petunia">
  <parent id="c-cat" instanceof="true" />
  <slot name="color" value="i-gray" />
</frame>

</frames>
"""
    kb = logic.PropKB()
    cp = parser.ConceptualParser(kb)
    icp = parser.IndexedConceptParser(kb)
    fdl_parser = fdl.FDLParser(fdl.BaseFrameHandler(kb, cp, icp))
    fdl_parser.parse_fdl_string(xml)
    gen = speechutil.MicrosoftSRGrammarGenerator(cp)

    correct_grammar = """<GRAMMAR LANGID="409">
  <RULE NAME="c-digit" TOPLEVEL="ACTIVE">
<L><P>zero</P><P>one</P><P>two</P><P>three</P><P>four</P><P>five</P><P>six</P><P>seven</P><P>eight</P><P>niner</P><P>nine</P><P>ten</P></L>  </RULE>

  <RULE NAME="c-gunslinger" TOPLEVEL="ACTIVE">
    <P>gunslinger</P>
  </RULE>

  <RULE NAME="c-hog" TOPLEVEL="ACTIVE">
    <P>hog</P>
  </RULE>

  <RULE NAME="c-restart" TOPLEVEL="ACTIVE">
    <L><P>restart</P> <P><P>start</P> <P>over</P></P></L>
  </RULE>

  <RULE NAME="c-talkon" TOPLEVEL="ACTIVE">
    <L><P><P>talk</P> <P>on</P></P> <P>talkon</P></L>
  </RULE>

  <RULE NAME="c-integer" TOPLEVEL="ACTIVE">
<L><P><RULEREF NAME="c-digit"/></P><P><RULEREF NAME="c-digit"/><RULEREF NAME="c-integer"/></P></L>  </RULE>

  <RULE NAME="c-name" TOPLEVEL="ACTIVE">
    <L>
      <RULEREF NAME="c-hog"/>
      <RULEREF NAME="c-gunslinger"/>
    </L>
  </RULE>

  <RULE NAME="c-action" TOPLEVEL="ACTIVE">
    <RULEREF NAME="c-restart"/>
  </RULE>

  <RULE NAME="c-thing" TOPLEVEL="ACTIVE">
    <RULEREF NAME="c-talkon"/>
  </RULE>

  <RULE NAME="c-action-request" TOPLEVEL="ACTIVE">
    <P><RULEREF NAME="c-name"/> <O><L><P>let's</P> <P><P>let</P> <P>us</P></P> <P><P>why</P> <P>don't</P> <P>we</P></P></L></O> <RULEREF NAME="c-action"/> <O><L><P>with</P> <P>on</P></L></O> <O><P>the</P></O> <RULEREF NAME="c-thing"/></P>
  </RULE>

  <RULE NAME="c-utterance" TOPLEVEL="ACTIVE">
    <RULEREF NAME="c-action-request"/>
  </RULE>

</GRAMMAR>
"""

    generated_grammar = gen.generate_grammar()

    # Remove the initial comment, which includes a timestamp that will
    # cause a mismatch.
    generated_grammar = generated_grammar[
      generated_grammar.index("-->\n") + 5:]

    if generated_grammar != correct_grammar:
      # Print a diff!
      for line in difflib.unified_diff(
          correct_grammar.split('\n'),
          generated_grammar.split('\n')):
        print line

    self.assertEqual(generated_grammar, correct_grammar)


if __name__ == "__main__":
  unittest.main()
