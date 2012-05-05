import sys
import threading
import re
import traceback
import time
import StringIO


class IORecord:
  def __init__(self, source, text, audio=None):
    self.source = source
    self.text = text
    self.audio = audio
    assert isinstance(text, basestring)


class HTMLIOManager:
  def __init__(self, dialog_manager):
    self.dialog_manager = dialog_manager
    self.line_count = 0
    self.input_file_stream = None
    self.enable_debug = False

  def set_input_file(self, path):
    self.file_input_path = path
    self.file_input_stream = open(path)

  def startup(self):
    title = cgi.escape("%s %s" % (self.file_input_path, time.asctime()))

    print """
    <html> <head>
<title>%s</title>
<style type="text/css">
.from { color: rgb(145, 0, 0); font-family: georgia;}
.to { color: rgb(0, 145, 0); font-family: georgia;}
.pilot {color: rgb(145, 0, 0); font-family: georgia;}
.jtac { color: rgb(0, 145, 0); font-family: georgia;}
.debug {font-style:italic; padding-left: 2cm; font-family: georgia; font-size: x-small}
.jtacline {font-family: georgia;}
.pilotline { font-family: georgia; }
</style>

</head>

<body>

<h1>
%s
</h1>

<p>
Debug output is in <em>italics</em>.
</p>

<hr>

<table>
    """ % (title, title)

  def shutdown(self):
    print """
    </table>
</body> </html>
    """
    self.file_input_stream.close()
    
  def say(self, who, string):
    self.lineCount = self.lineCount + 1
    sys.stdout.write('<tr><td>%s</td>' % (self.line_count,))
    sys.stdout.write('<td class="from">%s:</td>' % (who,))
    sys.stdout.write('<td class="pilot">%s</td></tr>\n' % (cgi.escape(string),))

  def debug(self, string):
    if self.enable_debug:
      sys.stdout.write('<tr><td colspan="3" class="debug">%s</td></tr>\n' % (cgi.escape(string),))

  def getline(self):
    def get_it():
      line = self.file_input_stream.readline()
      if line == '':
        raise EOFError
      line = line[:-1]
      if len(line) == 0:
        return get_it()
      else:
        self.echo_input(line)
        return line
    return IORecord('JTAC', get_it())

  def set_lexicon(self, lexemes):
    # We don't care about lexicons
    pass

  def set_grammar_mode(self):
    pass

  def set_dictation_mode(self):
    pass

  def set_debug(self, debug):
    self.enable_debug = True

  def echo_input(self, string):
    self.line_count = self.line_count + 1
    sys.stdout.write('<tr><td class="jtacline">%s</td><td class="to">%s:</td><td class="jtac">%s</td></tr>\n' % (self.line_count, self.dialog_manager.jtac_callsign, cgi.escape(string)))

  def write_prompt(self):
    pass


class ConsoleIOManager:
  def __init__(self, dialog_manager):
    self.dialog_manager = dialog_manager
    self.file_input_stream = None
    self.expectation = None
    self.cv = threading.Condition()
    self.enable_debug = False

  def set_input_file(self, path):
    self.file_input_stream = open(path)


  # ----------------
  # IOManager interface
  # ----------------
  def say(self, who, text):
    sys.stdout.write('\n' + text + '\n')
    self.check_expectation(text)

  def startup(self):
    pass

  def shutdown(self):
    if self.file_input_stream is not None:
      self.file_input_stream.close
    self.cv.acquire()
    try:
      self.cv.notifyAll()
    finally:
      self.cv.release()
    
  def debug(self, text):
    if self.enable_debug:
      sys.stdout.write("[debug: %s]\n" % (text,))

  def set_debug(self, debug):
    self.enable_debug = debug

  def getline(self):
    self.wait_for_expectation()
    def read_line():
      if self.file_input_stream is not None:
        # using file for canned transcript test.  ignore lines starting with #. (mrh 2/20/07)
        line = self.file_input_stream.readline()
        if line == '':
          raise EOFError
        line = line.strip() # line[:-1]
        if len(line) == 0 or line.startswith("#"):
          return read_line()
      else:
        line = sys.stdin.readline()
        if line == '':
          raise EOFError
      return line

    if self.file_input_stream is None:
      self.write_prompt()
    line = read_line()
    if is_command(line):
      self.execute_command(line)
      return IORecord('JTAC', self.getline())
    else:
      if self.file_input_stream is not None:
        self.write_prompt()
      self.echo_input(line)
      return IORecord('JTAC', line)

  def set_lexicon(self, lexemes):
    # We don't care about lexicons
    pass

  def set_dictation_mode(self):
    pass

  def set_grammar_mode(self):
    pass

  # ---------------
  # Private methods
  # ---------------

  def write_prompt(self):
    sys.stdout.write("\n> ")
    
  def echo_input(self, string):
    sys.stdout.write(string + "\n")

  def execute_command(self, line):
    pieces = line.split()
    command = pieces[0]
    args = pieces[1:]
    if command == '%EXPECT':
      self.add_expectation(" ".join(args))
    else:
      raise "Bad command '%s' in input file" % (line,)

  def add_expectation(self, regexp):
    self.cv.acquire()
    self.debug("Waiting on expectation '%s'" % (regexp,))
    try:
      print "compiling %s" % (regexp,)
      self.expectation = re.compile(regexp, re.I)
    finally:
      self.cv.release()

  def wait_for_expectation(self):
    self.cv.acquire()
    try:
      if self.expectation is None:
        return
      else:
        self.cv.wait()
        self.expectation = None
    finally:
      self.cv.release()

  def check_expectation(self, text):
    self.cv.acquire()
    try:
      if self.expectation is not None:
        if self.expectation.search(text):
          self.cv.notifyAll()
    finally:
      self.cv.release()

def is_command(line):
  return line[0] == '%'
    

from xml.dom import minidom
import re

# Currently, test scores are tallied in the wrong place (in the TestSuite,
# not in the individual test objects), which means doesn't spit out nice
# error lists at the end, but it's much easier here to look back through the
# output and see what went wrong.  Putting errors in the right place isn't hard.

class TestIOManager:
  """An IO manager which reads utterances and expected responses from
  XML files.  TestSuite object maintains own state machine, deciding when
  a particular test is done or not; TestIOManager is merely glue between
  the DialogManager and the TestSuite code.
  
  Approximate schema format:
  
  <testsuite name="descriptive name">
    <include>relative-file-path</include>*
    <test name="test-name">
      [<setup>python to eval?</setup>]
      <input>input phrase</input>
      <output [should-fail="True|False"]>expected output, may include regexp</output>
    </test>*
  </testsuite>
  """
  
  def __init__(self, dialog_manager):
    self.dialog_manager = dialog_manager
    self.input_file = None
    self.test_suite = None
    self.last_who = None
    self.enable_debug = False

  def set_input_file(self, path):
    # save for when we start up
    self.input_file = path
  
  # ----------------
  # IOManager interface
  # ----------------
  
  def say(self, who, text):
    # one of the two important calls...
    #if self.last_who != 'pilot':
    #  sys.stdout.write('\n')
    print "==> Pilot says: %s" % text
    self.last_who = 'pilot'
    self.test_suite.next_output(text)
  
  def getline(self):
    # the other important call.
    tmp_input = self.test_suite.next_input()
    if not tmp_input:
      return self.getline()
    #if self.last_who != 'jtac':
    #  sys.stdout.write('\n')
    print "<== JTAC says: %s" % tmp_input
    self.last_who = 'jtac'
    return IORecord('JTAC', tmp_input)
  
  def debug(self, text):
    # whether or not to test debug output is a very interesting question, I think.
    # it seems valuable, but let's not start with it.
    if self.enable_debug:
      sys.stdout.write("[debug: %s]\n" % (text,))

  def set_debug(self, debug):
    self.enable_debug = debug
  
  def startup(self):
    # load the XML and set up test structure here
    self.test_suite = self.TestSuite(self.input_file, self.dialog_manager)
  
  def shutdown(self):
    # print results
    success_count = 0
    failure_count = 0
    exception_count = 0
    for test in self.test_suite.tests:
      if test.is_complete():
        if test.exception:
          exception_count += 1
        elif test.success:
          success_count += 1
        else:
          failure_count += 1
      
    print "\nTest results:"
    print "  # success:    %d" % success_count
    print "  # failure:    %d" % failure_count
    print "  # exceptions: %d" % exception_count

    num_tests_run = success_count + \
                    failure_count + \
                    exception_count
    if num_tests_run != len(self.test_suite.tests):
      print "  #\n  # tests not run: %s" % (len(self.test_suite.tests) - num_tests_run,)
    
    
      
  def set_lexicon(self, lexemes):
    # Like the ConsoleIOManager, we don't care about lexicons
    pass

  def set_grammar_mode(self):
    pass

  def set_dictation_mode(self):
    pass

  
  # -----------------------------
  # Private methods (and classes)
  # -----------------------------
  
  class TestSuite:
    """Class which holds the parsed representation of a test suite."""
    def __init__(self, file_path, dialog_manager):
      """Load up the specified XML test file."""
      self.file_path = file_path
      self.dialog_manager = dialog_manager
      self.name = "Unnamed Test Suite"
      self.current_test_idx = 0
          
      self.input_lock = threading.Condition()   # condition variable for waiting until input is available
      self.input_ready = True                   # is the current test done for the moment?

      self.tests = [ ]
      # what are they python guidelines about doing lots of computation in the constructor?
      # no matter for now, just load up stuff.
      self.load_tests()
      
    def next_output(self, text):
      # The pilot has said something, handle  it.
      # more or less assume that outputs govern when one test is done and the
      # next should be set up.
      if self.current_test_idx >= len(self.tests):
        print "** Uh oh, still getting output but we're out of tests: {%s}" % text
        # bail
        return

      test_obj = self.current_test()
      assert(isinstance(test_obj, TestIOManager.TestNode))  # for WingIDE context help
      try:
        # print "test %d, (%d,%d,%d), text to match: {%s}" % (self.current_test, self.success_count, self.failure_count, 
        #                                                     self.exception_count, text)
        test_obj.match_output(text)
        if test_obj.is_complete():
          #print "test %s complete"  % test_obj.name
          self.advance_to_next_test()
      except Exception, e:
        self.print_test_exception("Test '%s' failed with an exception when matching output." % (self.name,),
                                  sys.exc_info())
        test_obj.exception = True
        self.advance_to_next_test()
      
    def next_input(self):
      """Return the next utterance to speak to the pilot.  May be None,
      in special cases.
      """
      # if the previous test is finished (output all matched or failed), get the new test
      self.wait_for_input_ready()

      if self.current_test_idx >= len(self.tests):
        # not an error, this will normally happen.  raise EOFError to signal we're done.
        raise EOFError
      
      result = self.current_test().get_input()
      # block other input calls after this one
      self.assert_input_not_ready()
      
      # if it requires some setup code before the input, check that now
      if self.current_test().setup_code is not None:
        try:
          exec self.current_test().setup_code in globals(), locals()
        except:
          self.print_test_exception("Test '%s' failed with an exception in the setup code." % (self.name,),
                                    sys.exc_info())
          self.current_test().exception = True
      
      # if the current test expects no output, advance it here
      if self.current_test().is_complete():
        self.advance_to_next_test()
      return result

    def current_test(self):
      return self.tests[self.current_test_idx]

    def advance_to_next_test(self):
      #print "-- Advancing from"
      #print "       %s" % (self.current_test(),)
      #print "    to %s" % (self.tests[self.current_test_idx+1],)
      self.current_test_idx += 1
      try:
        print "%s:" % (self.current_test().name,)
      except IndexError:
        pass
      self.assert_input_ready()
      return self.current_test_idx < len(self.tests)

    def print_test_exception(self, message, e):
      print ""
      print "########################################"
      print "# %s" % (message,)
      print "#"
      for line in traceback.format_exception(e[0], e[1], e[2]):
        print "#  %s" % (line.strip('\n'),)
      print "########################################"
  
    def wait_for_input_ready(self, timeout=None):
      """Block until input is ready."""
      self.input_lock.acquire()
      try:
        try:
          now = time.time()
          too_late = None
          if timeout:
            too_late = now + timeout
          # Waiting with a timeout allows ctrl-c/ctrl-break to interrupt us.
          while not self.input_ready and ((not too_late) or time.time() >= too_late):
            self.input_lock.wait(0.1)
        except Exception, e:
          sys.stderr.write("Exception in test %s\n" % (self.current_test().name,))
          raise e
      finally:
        self.input_lock.release()
    
    def assert_input_ready(self):
      """Say that an old test is done, so presumably input is ready."""
      self.input_lock.acquire()
      try:
        self.input_ready = True
        self.input_lock.notifyAll()
      finally:
        self.input_lock.release()
    
    def assert_input_not_ready(self):
      """Say that the input for the current test is over."""
      self.input_lock.acquire()
      try:
        self.input_ready = False
      finally:
        self.input_lock.release()
    
    def load_tests(self):
      """Load the test suite we were given when we were created."""
      input_stream = open(self.file_path)
      xmldoc = minidom.parse(input_stream).documentElement
      input_stream.close()
    
      # now parse.  first one should absolutely be <testsuite>.
      # assert line mostly to give WingIDE some context for introspection
      assert(isinstance(xmldoc, minidom.Element))
      # print xmldoc.toxml()
      # there should only be one child, <testsuite>.  (err, why?  I suppose we could have multiple suites per file...)
      self.name = xmldoc.attributes["name"].value
      # suite itself has no other properties.  walk through all child nodes.
      for node in xmldoc.childNodes:
        if isinstance(node, minidom.Element):
          assert(isinstance(node, minidom.Element))
          if node.nodeName == "test":
            self.handle_test_node(node)
          elif node.nodeName == "include":
            self.handle_include_node(node)
          else:
            raise Exception, "Unknown node type: %s" % node.nodeName
      print "Done loading test suite; %d test(s).\n" % len(self.tests)
  
    def handle_test_node(self, node):
      """Turn a test node into a useful structure."""
      test_node = TestIOManager.TestNode(node)
      # print "Successfully loaded test node: %s" % test_node.name
      self.tests.append(test_node)
    
    def handle_include_node(self, node):
      """Handle an include node?  Means having sub-suites."""
      print "... skipping include node"
      pass
  
  class TestNode:
    """Data structure for holding test node and determining whether a given
    response is a success or a failure according to this test."""
    def __init__(self, xml_node):
      self.name = None
      self.input = None
      self.outputs = [ ]
      self.should_fail = False
      self.setup_code = None
      self.current_output = 0
      self.is_complete_flag = False
      self.success = True     # assume test succeeds, until told otherwise
      self.exception = False  # assume test didn't produce exception
      
      self.parse_xml(xml_node)
      # print "... success loading test node %s, input = %s, output = %s, setup = %s" %  \
      # (self.name, self.input, self.outputs, self.setup_code)
      
    def __str__(self):
      """Attempt at returning a nice printable string representation."""
      s = StringIO.StringIO()
      s.write("<TestNode %s" % (self.name,))
      if self.input:
        s.write(" input: '%s'" % (self.input,))
      for output in self.outputs:
        s.write(" output: '%s'" % (output,))
      if self.setup_code:
        s.write(" setup: '%s'" % (self.setup_code,))
      s.write(">")
      return s.getvalue()
    
    def parse_xml(self, node):
      from xml.dom import minidom
      assert(isinstance(node, minidom.Element))
      self.name = node.attributes["name"].value
      for tmp_node in node.childNodes:
        if isinstance(tmp_node, minidom.Element):
          if tmp_node.nodeName == "input":
            if self.input is not None:
              raise Exception, "Extra input node in " + node.toxml()
            self.input = tmp_node.firstChild.nodeValue
          elif tmp_node.nodeName == "output":
            # in the past, it was convenient to have multiple output nodes.
            # want extra flag on output to say whether it's a regexp? 
            self.outputs.append(tmp_node.firstChild.nodeValue)
            # "should-fail" seems ill-considered at the moment, but...
            if tmp_node.hasAttribute("should-fail"):
              self.should_fail = (tmp_node.attributes["should-fail"].value == "True")
          elif tmp_node.nodeName == "setup":
            if self.setup_code is not None:
              raise Exception, "Extra setup node in " + node.toxml()
            self.setup_code = tmp_node.firstChild.nodeValue
          else:
            raise Exception, "Extra unknown node in " + node.toxml()
      # should we do any post-processing to say "a test node _must_ have this?"
#      if len(self.outputs) > 1:
#        print "Outputs for test %s, in order: %s" % (self.name, self.outputs)

    # need methods to get input, compare output.
    def match_output(self, text):
      """Does the new utterance match the expected output?  Return True/False."""
      # print "  ** match text = {%s}, current_output = %d, output list = %s" % (text, self.current_output, self.outputs)
      # if a test has no outputs, that can be okay, as long as the user doesn't
      # say anything extra on the previous test.
      if self.current_output >= len(self.outputs):
        expected_text = "<nothing expected>"
        result = False
      else:
        expected_text = self.outputs[self.current_output]
        # clearly, matching will get more complex later.
        result = (expected_text == text)
        if (result == False):
          # okay, simple matching didn't work, try regex matching?
          expected_text_re = expected_text
          if expected_text_re[-1] != '$':
            expected_text_re = expected_text_re + r'\.?$'
          result = (re.match(expected_text_re, text, re.I) is not None)
        self.current_output += 1
        self.is_complete_flag = (self.current_output >= len(self.outputs))
      
      # print results at the time, or print them all later?  not sure.
      if result == False:
        print ""
        print "########################################"
        print "# Test %s failed." % (self.name,)
        print "#"
        print "#    Expected : %s" % (expected_text,)
        print "#    Received : %s" % (text,)
        print "########################################"
        print ""
        # new thought: let's try saying that if there's an error in any of the 
        # the expected output phrases for a given test, then the test is complete.  
        # that may help the system shut down when a multi-output test fails.
        self.is_complete_flag = True
        self.success = False
      else:
        pass
        # print "** Test %s success." % self.name
          
      return result      
    
    def is_complete(self):
      """Return True if this test has run through all expectations, false otherwise."""
      return self.is_complete_flag
    
    def get_input(self):
      """Return the input string for this test."""
      # tests will almost always have input; maybe the first test in a set is an exception.
      # or! tests where the <setup> element causes some event to be triggered. (mrh 4/25/07)
      self.is_complete_flag = (self.current_output >= len(self.outputs))
      return self.input

# See
# http://msdn.microsoft.com/library/default.asp?url=/library/en-us/SAPI51sr/html/English_Phoneme.asp
# for the complete list of phonemes (and other special symbols,
# e.g. syllable boundary markers).

class Lexeme:
  PARTS_OF_SPEECH = ('unknown', 'noun', 'verb', 'modifier', 'function', 'interjection')
  
  def __init__(self, spelling, part_of_speech):
    self.spelling = spelling
    part_of_speech = part_of_speech.lower()
    if not part_of_speech in self.PARTS_OF_SPEECH:
      raise ValueError, \
            "Part of speech is '%s', but must be one of %s." % \
            (part_of_speech, self.PARTS_OF_SPEECH)
    self.part_of_speech = part_of_speech
    self.phonetic_pronunciations = []

  def add_phonetic_pronunciation(self, phonemes):
    self.phonetic_pronunciations.append(phonemes)
  

