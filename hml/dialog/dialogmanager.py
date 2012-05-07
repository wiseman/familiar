from energid import logic
from energid import parser
from energid import fdl
from energid import pilotmodel
from energid import generation
from energid import iomanager
from energid import utils
from energid import filter

import energid.actions

import sys
import getopt
import cgi
import time
import random
import threading
import traceback
import pprint
import re
import os.path
from xml.sax import saxutils

if sys.platform == 'win32':
  from energid import speech


class Attention:
  def __init__(self):
    self.focus = None

  def set_focus(self, object):
    self.focus = object



class LineNotValid(Exception):
  def __init__(self, line, constraint, object):
    self.line = line
    self.constraint = constraint
    self.object = object

  def __str__(self):
    return "%s is not acceptable for a %s on line %s" % (self.object, self.constraint, self.line)


class NineLine:
  CONSTRAINTS = {"IP": None,
                 "heading": ["c-heading", "c-heading-with-offset"],
                 "distance": "c-linear-measurement",
                 "target elevation": "c-linear-measurement",
                 "target description": "c-thing",
                 "target location": "c-mgrs-coords",
                 "type mark": "c-target-designation-mark",
                 "location of friendlies": "c-vector",
                 "egress": None}
  ORDER = ["IP", "heading", "distance", "target elevation",
           "target description", "target location", "type mark",
           "location of friendlies", "egress"]

  def __init__(self, kb):
    self.kb = kb
    self.reset()
    
  def reset(self):
    self.values = [None] * 9
    self.raw_text = [None] * 9
    self.remarks = ""
    self.next_line = 0
    self.needs_acknowledgement = False
    self.acknowledged = False

  def mark_as_needs_acknowledgement(self):
    self.needs_acknowledgement = True

  def mark_as_acknowledged(self):
    self.acknowledged = True
    
  def object_satisfies_constraints(self, object, constraints):
    if constraints is None:
      return True
    object = logic.expr(object)
    if not isinstance(constraints, list):
      return self.kb.isa(object, logic.expr(constraints))
    else:
      for constraint in constraints:
        if self.kb.isa(object, logic.expr(constraint)):
          return True
      return False

  def object_is_valid_for_next_line(self, object):
    if self.next_line > 8:
      return False
    return self.object_satisfies_constraints(object, self.current_constraint())
    
  def object_is_valid_for_line(self, object, line):
    assert line >= 0 and line <= 8
    return self.object_satisfies_constraints(object, self.constraint(line))

  def any_object_is_valid_for_line(self, objects, line):
    assert line >= 0 and line <= 8
    for object in objects:
      if self.object_is_valid_for_line(object, line):
        return True
    return False

  def set_line(self, object, line, force_accept = False):
    if line > 8:
      raise TooManyLines

    if force_accept == False:
      constraint = self.constraint(line)
      if not self.object_satisfies_constraints(object, constraint):
        raise LineNotValid(line + 1, constraint, object)
      self.values[line] = object
    else:
      # hack to put some data in here
      self.values[line] = object

  def get_line(self, line):
    if isinstance(line, basestring):
      for index, value in enumerate(self.ORDER):
        if value == line:
          return self.values[index]
    else:
      return self.values[line + 1]
  
  def set_raw_text(self, text, line):
    # 4/25 mrh: special purpose hack!  I wasn't able to make a good parser 
    #           pattern for "NV 299 942", because there were major ambiguity
    #           issues given the way we do numbers (is that 2 + 99942, or 29 + ...)
    #           so, one big number comes from the nine line.  what's the hack?
    #           munging them apart here in the "raw text".
    
    if line == 5:
      # only munge lines we think look like ours; exact match necessary
      pattern = "^[A-Z]{2} [0-9]{6}$"
      if re.match(pattern, text):
	text =  text[:6] + " " + text[6:]
    self.raw_text[line] = text
    
  def get_raw_text(self, line):
    return self.raw_text[line]
  
  def set_remarks(self, remarks):
    self.remarks = remarks
  
  def get_remarks(self):
    return self.remarks

  def is_complete(self):
    return ((not self.needs_acknowledgement) or self.acknowledged) and self.has_data()
  
  def has_data(self):
    for object in self.values:
      if object is None:
        return False
    return True
  
  def is_pending_acknowledge(self):
    return self.has_data() and self.needs_acknowledgement and (not self.acknowledged)

  def current_line(self):
    return self.next_line + 1

  def current_constraint(self):
    return self.CONSTRAINTS[self.ORDER[self.next_line]]

  def constraint(self, line):
    return self.CONSTRAINTS[self.ORDER[line]]

  def current_line_description(self):
    return self.ORDER[self.next_line]

  def description(self, line):
    return self.ORDER[line]

  def debug_line(self, line):
    return "9-line now waiting for %s on line %s (%s)" % \
           (self.constraint(line), line + 1, self.description(line))



class EndExercise(Exception):
  pass

class DialogManager:

  CONCEPTUAL_PARSER = 'conceptual parser'
  INDEXED_CONCEPT_PARSER = 'indexed concept parser'
  
  def __init__(self, sim_host, action_module, run_tests = False):
    self.kb = logic.PropKB()
    self.cp_parser = parser.ConceptualParser(self.kb)
    self.icp_parser = parser.IndexedConceptParser(self.kb)
    self.run_tests = run_tests
    self.lexemes = []
    self.generator = generation.Generator(self.kb)
    self.state_machine = StateMachine(self)   # create the state machine
    self.input_count = 0
    self.log_lock = threading.Lock()

    if sim_host is not None:
      self.pilot_model = pilotmodel.PilotModel(sim_host, self)
    else:
      self.pilot_model = pilotmodel.DisconnectedPilotModel(self)

    self.action_module = action_module

    self.jtac_full_callsign = "Jackknife"
    self.jtac_callsign = "Jackknife"
    self.pilot_callsign = "Hog"
    self.pilot_full_callsign = "Hog 01"
    self.authentication_challenge_code = "Bravo Hotel November"
    self.authentication_response_code = "w"
    self.abort_code = ["b", "f"]
    
    self.unit_of_measure = self.previous_unit_of_measure = None
    self.anchor_point = self.previous_anchor_point = None
    
    self.idler = ConversationIdleThread(self)
    
#    self.reset()

  def set_parser_mode(self, mode):
    self.debug("Setting parser mode to %s" % (mode,))
    if mode == DialogManager.CONCEPTUAL_PARSER:
      self.parser_mode = DialogManager.CONCEPTUAL_PARSER
      self.io_manager.set_grammar_mode()
    elif mode == DialogManager.INDEXED_CONCEPT_PARSER:
      self.parser_mode = DialogManager.INDEXED_CONCEPT_PARSER
      self.io_manager.set_dictation_mode()
    else:
      raise "%s is not a valid parser mode." % (mode,)

  def set_io_manager(self, io_manager):
    self.io_manager = io_manager
    self.io_manager.set_lexicon(self.lexemes)


  def set_focus_of_attention(self, object):
    self.attention.set_focus(object)

  def check_authenticated(self):
    if not self.jtac_is_authenticated:
      raise AuthenticationRequired

  def set_unit_of_measure(self, measure):
    self.debug("Set unit of measure to %s meters" % (measure,))
    self.unit_of_measure = measure
  
  def reset_unit_of_measure(self):
    """Store current unit of measure for later re-use, then reset current."""
    self.previous_unit_of_measure = self.unit_of_measure
    self.unit_of_measure = None

  def set_anchor_point(self, point):
    self.debug("Set anchor point to %s" % (point,))
    self.anchor_point = point
  
  def reset_anchor_point(self):
    """Store current anchor point for later re-use, then reset current."""
    self.previous_anchor_point = self.anchor_point
    self.anchor_point = None

  def load_fdl(self, path):
    fdl_handler = fdl.BaseFrameHandler(self.kb, self.cp_parser, self.icp_parser)
    fdl_parser = fdl.FDLParser(fdl_handler)
    fdl_parser.parse_fdl_file(path)
    self.lexemes = fdl_handler.lexemes
    # optionally, if tests were requested:
    if self.run_tests:
      self.fdl_parser.run_test_phrases(self.cp_parser)

  def getline(self):
    line = self.io_manager.getline()
    assert isinstance(line, iomanager.IORecord)
    self.idler.update_time()
    self.log_input(line)
    # 4/6/07 mrh: when user says anything, even garbage, reset continuous idle count
    self.state_machine.data.reset_idle_count()
    return line

  def handle_false_recognition(self, iorecord):
    self.log_input(iorecord, false_recognition=True)    

  def log_output(self, utterance):
    self.log("==> OUTPUT", utterance)
    utils.log("<output>%s</output>" % (saxutils.escape(utterance),))

  def log_input(self, iorecord, false_recognition=False):
    self.log_lock.acquire()
    try:
      tag = "input"
      if false_recognition:
	tag = 'false-recognition'

      if iorecord.audio == None:
	utils.log("<%s>%s</%s>" % (tag, saxutils.escape(iorecord.text), tag))
      else:
	# Save audio in a wav file
	wav_file = "input-%03d.wav" % (self.input_count,)
	wav_path = os.path.join(utils.GLOBAL_LOGGER.subdir, wav_file)
	self.input_count += 1
	filter.writefile(iorecord.audio, wav_path)
	utils.log("<%s audio='%s'>%s</%s>" % (tag, wav_file, saxutils.escape(iorecord.text), tag))
      self.log("<== %s" % tag.upper(), iorecord.text)
    finally:
      self.log_lock.release()

  def log(self, type, message):
    utils.slog("comms.log", type, message)

  def parse(self, input):
#    print "*** Parsing mode is %s" % (self.parser_mode,)
    assert isinstance(input, iomanager.IORecord)
    if self.parser_mode == DialogManager.INDEXED_CONCEPT_PARSER:
      results = self.icp_parser.parse(input.text)
      result_strs = map(lambda r: "<ICPResult %s %s %s>" % (r.score, r.target_concept, r.slots), results)
      self.debug("[%s]" % (", ".join(result_strs),))
      return results
    else:
      return self.cp_parser.parse(input.text)

  def parse_with_prompt(self, all_parses = False, invalid_parse_message = None):
    if invalid_parse_message is None:
      invalid_parse_message = "%s did not copy" % (self.pilot_callsign,)

    while True:
      input = self.getline()
      if input is None or len(input.text.strip()) == 0:
	# if input is empty string, just don't bother parsing, go back to top of loop
	continue
      parses = self.parse(input)
      self.debug("Raw parses: %s" % (parses,))
      if len(parses) == 0:
        self.say_unrecorded(invalid_parse_message)
      else:
        if all_parses:
          result = parses
          break
        else:
          if self.parser_mode == DialogManager.CONCEPTUAL_PARSER:
            # Using the concept parser.
            if len(parses) > 1:
              self.debug("Got too many parses: %s" % (parses,))
              pprint.pprint(map(logic.Description.dictify, parses))

              # before giving up, try to filter out unactionable parses:
              action_list = self.filter_actionable_parses(parses)
              self.debug("Actionable parses: %s" % (action_list,))

              if len(action_list) > 1:
                # self.say_unrecorded(invalid_parse_message)
                result = action_list[0]
                break
              else:
                if len(action_list) > 0:
                  result = action_list[0]
                else:
                  result = parses[0]
                break
            else:
              result = parses[0]
              break
          else:
            # using ICP
            if all_parses:
              result = parses
              break
            else:
              # Filter out unactionable parses?
              def is_actionable(concept):
                return self.kb.isa(logic.expr(concept), logic.expr('c-magic-command')) or \
                       (self.kb.slot_value(concept, logic.expr('execute-method')) != None)
              result = [parse for parse in parses if is_actionable(parse.target_concept)]
              break

    if self.parser_mode == DialogManager.CONCEPTUAL_PARSER:
      if len(parses) == 1 and self.kb.isa(logic.expr(parses[0]),
                                          logic.expr("c-magic-command")):
        self.debug("Magic command %s takes priority." % (parses[0],))
        self.handle_parse(parses[0])
        return self.parse_with_prompt(all_parses, invalid_parse_message)
      else:
        return result
    else:
      # FIXME: I don't know.  Do we want to do more than this?
      if len(parses) > 0 and self.kb.isa(logic.expr(parses[0].target_concept),
                                         logic.expr('c-magic-command')):
        self.debug("Magic command %s takes priority." % (parses[0],))
        self.handle_parse(parses[0])
        return self.parse_with_prompt(all_parses, invalid_parse_message)
      else:
        return parses[0]
  
  def filter_actionable_parses(self, parses):
    """Filter the specified list of parses by looking at the ones that are 
    immediately actionable, i.e. are magic commands or have an execute-method.
    """    
    def is_actionable(parse):
      return self.kb.isa(logic.expr(parse), logic.expr("c-magic-command")) or \
             self.kb.slot_value(parse, logic.expr("execute-method")) != None
    
    return [parse for parse in parses if is_actionable(parse)]
    
  def reset(self):
    self.nine_line = NineLine(self.kb)
    self.jtac_is_authenticated = False
    self.jtac_authentication_requested = False
    self.unit_of_measure = None
    self.anchor_point = None
    self.attention = Attention()
    self.session_start_time = time.time()
    self.on_attack_run = False
    self.set_parser_mode(DialogManager.INDEXED_CONCEPT_PARSER)
    if self.pilot_model.is_connected():
      self.fly_to_ip()
      self.pilot_model.zoom_view(4.0)
    
    # blow away all state objs, create new
    self.state_machine.reset()

  def fly_to_ip(self, type="inbound to ip"):
    self.pilot_model.fly_to([-5383, -747, -1126], type)    
    
  def run(self):
    self.io_manager.startup()
    self.pilot_model.connect()
    self.reset()
    self.action_module.init_module(self)
    self.idler.start()
    
    try:
      self.run_input_loop()
    finally:
      try :
        # time.sleep(5)
        print "* DialogManager shutting down"
        self.shutdown()
      except:
        # received exception?  try again.  often happens w/ console app when
        # keyboard interrupt (^c) first returns '' to readline(), causing our
        # code to raise EOFError,and then KeyboardInterrupt is raised later.
        self.shutdown()
  
  def shutdown(self):
    if self.state_machine is not None:
      self.state_machine.shutdown()
    self.state_machine = None
    self.idler.shutdown()
    self.io_manager.shutdown()
    self.pilot_model.disconnect()

  def run_input_loop(self):
    unhandled_exception = False
    while True:
      try:
        # "Gunslinger 42, Hog 01" to start things off
        # (unless exception was just caught)
        if not unhandled_exception:
          self.say_with_full_callsign(self.pilot_full_callsign)
        unhandled_exception = False
        while True:
          if self.jtac_is_authenticated:
            invalid_parse_message = "%s did not copy" % (self.pilot_callsign,)
          else:
            invalid_parse_message = "authenticate %s" % (self.authentication_challenge_code,)
          parse = self.parse_with_prompt(invalid_parse_message = invalid_parse_message)
          # FIXME: this should be handled through conv. state?
          if self.jtac_is_authenticated or \
                 self.kb.isa(logic.expr(parse),
                             logic.expr("c-authentication-response")) or \
                             self.kb.isa(logic.expr(parse),
                                         logic.expr("c-authentication-request")):
            self.handle_parse(parse)
          else:
            self.say("authenticate %s" % (self.authentication_challenge_code,))
            self.jtac_authentication_requested = True
      except energid.dialogmanager.EndExercise, e:
        self.reset()
      except EOFError:
        return
      except (KeyboardInterrupt, SystemExit):
        # allow control-c to quit
        return
      except:
        # MRH: probably don't want this to just crash on exception, right?  but, keep going? 3/15/07
        unhandled_exception = True
        err_info = sys.exc_info()
        trace = traceback.format_tb(err_info[2])
        self.say("sorry, processing error.  Please send following error info to John or Mike.")
        self.debug("Unexpected error: (%s, %s)" % (err_info[0], err_info[1]))
        for i in range(0,len(trace)):
          self.debug("%s" % (trace[i],))
        sys.stderr.write("Unexpected error: (%s, %s)\n" % (err_info[1], err_info[1]))
        for i in range(0,len(trace)):
          sys.stderr.write("%s" % (trace[i],))
        unhandled_exception = True

  def handle_parse(self, parse):
    # 4/16/07 mrh: adding concept_key as way for dialog to be handled by state system
    concept_key = self.kb.slot_value(parse, logic.expr("concept-key"))
    if concept_key is not None:
      # pass it on for the state machine to handle directly
      self.state_machine.handle_parse(concept_key.op, parse)
    else:
      # look up the execute method and act on it, if possible (fall-back)
      functionexpr = self.kb.slot_value(parse, logic.expr("execute-method"))
      if functionexpr is None:
        self.debug("No execute-method for %s and no context." % (parse.base,))
        self.say("you are coming in weak and unreadable, say again")
      else:
        function_name = functionexpr.op
        function = self.lookup_action_function(function_name)
        function(self, parse)

  def handle_event(self, event):
    # 4/18/07 mrh: using state model for events
    event_type = event["type"]
    handler_desc = logic.Description("c-event-handler", {"event-type": event_type})
    handlers = handler_desc.find_all(self.kb)
    if len(handlers) == 0:
      self.debug("Got event of type '%s', but there is no handler defined." % (event_type,))
    else:
      if len(handlers) > 1:
        self.debug("Found %s handlers for %s event (calling first one)." % (len(handlers), event_type))

    self.state_machine.handle_event(event_type, event)

  def lookup_action_function(self, name):
    if name in self.action_module.__dict__:
      utils.log("<action>%s</action>" % (saxutils.escape(name),))
      self.log("==> ACTION", name)
      return self.action_module.__dict__[name]
    else:
      self.debug("No function in action module named '%s'." % (name,))
      return lambda a, b: a.say("Sorry, I don't know how to respond to that.")
  
  
  def generate(self, string, *args):
    generated_args = map(self.generator.generate, args)
    text = string % tuple(generated_args)
    return text

  def say(self, string, *args):
    utterance = self.jtac_callsign + ", " + apply(self.generate, (string,) + args)
    self.__say_helper(utterance)
  
  def say_without_callsign(self, string, *args):
    utterance = apply(self.generate, (string,) + args)
    self.__say_helper(utterance)

  def __say_helper(self, utterance):
    utterance = utterance.strip()
    if len(utterance)>0 and not utterance[-1] in ".!?":
      utterance += "."
    self.idler.update_time()
    self.last_utterance = utterance
    self.io_manager.say(self.pilot_callsign, utterance)
    self.log_output(utterance)

  def say_unrecorded(self, string, *args):
    """This is like the normal say() function, except that the utterance isn't recorded for the future."""
    # could implement this by having both functions point to private helper function, and have say() record
    # the utterance outside.  worth it?
    self.idler.update_time()
    utterance = self.jtac_callsign + ", " + apply(self.generate, (string,) + args)
    utterance = utterance.strip()
    if len(utterance) > 0 and not utterance[-1] in ".!?":
      utterance += "."
    self.io_manager.say(self.pilot_callsign, utterance)
    self.log_output(utterance)
    
  def say_random(self, *options):
    weight_total = 0
    for option in options:
      weight_total = weight_total + option[0]
    x = random.randint(0, weight_total - 1)
    for (option_weight, option) in options:
      x = x - option_weight
      if x < 0:
        apply(self.say, option)
        return
    # FIXME: do remove this.
    self.debug("Failure in say_random: %s, %s" % (x, options))
    apply(self.say, option[0][0])

  def debug(self, string):
    self.io_manager.debug(string)
    self.log("==> DEBUG", string)
    utils.log("<debug>%s</debug>" % (saxutils.escape(string),))

  def say_with_full_callsign(self, string, *args):
    utterance = self.jtac_full_callsign + ", " + apply(self.generate, (string,) + args)
    self.idler.update_time()
    self.last_utterance = utterance
    self.io_manager.say(self.pilot_callsign, utterance)

  def say_again(self):
    self.idler.update_time()
    self.io_manager.say(self.pilot_callsign, self.last_utterance)


class ConversationIdleThread(threading.Thread):
  """A thread running in the background which can raise events up to the
  dialog manager based on how long it's been since the last conversational
  interaction.  This allows the simulator to suggest courses of interaction
  if the JTAC isn't sure what to do next.
  """
  def __init__(self, dialog_manager, idle=30):
    threading.Thread.__init__(self)
    self.dm = dialog_manager
    self.last_time = time.time()   # seconds since epoch
    self.keep_running = True
    self.status_cv = threading.Condition()
    self.check_interval = 0.2  # seconds
    self.idle_time = idle    # seconds
    self.setDaemon(True)
    
  def update_time(self):
    """Update time of last interaction to 'now'."""
    # do I really need a lock for this?  seems pretty darned atomic... 
    # what's the worst that can happen, thread gets notified late?
    self.status_cv.acquire()
    self.last_time = time.time()
    self.status_cv.release()
    
  def shutdown(self):
    """Signal that the thread should stop running.  Make take up
    to self.check_interval seconds.
    """
    self.keep_running = False
    
  def run(self):
    """Run in a loop, waking up periodically to see if the system has been idle
    for 'long enough'.  If so, send an event to the dialog manager.
    """
    while True:
      time.sleep(self.check_interval)
      # should we shut down?
      self.status_cv.acquire()
      # acquiring lock here synchronizes data between threads
      try:
        if self.keep_running == False:
          break
      finally:
        self.status_cv.release()
      # otherwise, is it time yet?
      if time.time() > self.last_time + self.idle_time:
        # tell dialog manager we're bored
        self.dm.handle_event({"type": "conversation-idle"})
        self.update_time()
      # otherwise, loop around and go back to sleep.



class StateMachine:
  """This class holds state data, the current state object, and more."""
  # 4/25/07 mrh: Adding queued events (at startup), enter() and exit() methods
  #              for state transitions.  Enter() helps new states process queued
  #              events, and is commonly cited in literature as being useful.
  #              *Not* adding locking for state transitions *yet*, even though now
  #              they're non-atomic; I worry about deadlock w/ the iomanager.

  def __init__(self, dm):
    """Initialize the State Machine.  Includes pointer to parent DialogManager instance."""
    self.dm = dm
    self.current_state = None
    self.previous_state = None
    
    # in case the State Machine is sent data before we're ready for it:
    self.queued_events = []
    self.queued_parses = []
  
  def reset(self):
    """Reset all state, except for the link to the dialog manager."""
    self.current_state = None
    self.previous_state = None
    self.data = self.dm.action_module.StateData()
    
    self.queued_events = []
    self.queued_parses = []
    
    # populate states by asking action module for custom definitions
    self.dm.action_module.populate_states(self)
  
  def set_state(self, new_state): 
    """Change the current state to be the new state; save the previous state
    in case it's needed for something.
    """
    
    if new_state != self.current_state:
      self.previous_state = self.current_state
      self.current_state = new_state
      
      if self.previous_state is None:
        self.dm.debug("Initializing to state {%s}" % self.current_state.name())
      else:
        self.dm.debug("Moving from state {%s} to {%s}" % (self.previous_state.name(), 
                                                     self.current_state.name()))
	# first, call exit on old state
	self.previous_state.exit()
      
      # whether or not old state existed, call enter on new state
      self.current_state.enter()
	
    else:
      self.dm.debug("Asked to move to state {%s} when already in that state?" % self.current_state.name())

  def get_queued_events(self):
    """Return queued events to caller.  Reset queue."""
    qe = self.queued_events
    self.qeueued_events = [] 
    return qe
  
  def get_queued_parses(self):
    """Return queued language to caller.  Reset queue."""
    qp = self.queued_parses
    self.queued_parses = []
    return qp
  
  def handle_event(self, event_type, event_obj):
    """Hand off to current state object.  If no current state, store event up
    for later processing.
    """

    if self.current_state is not None:
      self.current_state.handle_event(event_type, event_obj)
    else:
      self.dm.debug("StateMachine queueing up event for later: %s" % event_type)
      self.queued_events.append((event_type, event_obj))
  
  def handle_parse(self, concept_key, parse):
    """Hand off to current state object.  If no current state, store parse up
    for later processing.
    """
    if self.current_state is not None:
      self.current_state.handle_parse(concept_key, parse)
    else:
      self.queued_parses.append((concept_key, parse))
  
  def shutdown(self):
    self.dm.action_module.cleanup_states()
  
  def get_previous_state(self):
    return self.previous_state


  

class DialogManagerApp:
  def __init__(self, fdl_path, remote_host):
    self.dialog_manager = DialogManager(remote_host, energid.actions)
    self.dialog_manager.load_fdl(fdl_path)
    self.io_manager = ConsoleIOManager(self.dialog_manager)
    
  def set_sr_grammar(self, grammar_path):
    self.io_manager = speech.SpeechRecognition(self.dialog_manager, grammar_path)
    self.dialog_manager.set_io_manager(self.io_manager)
    
  def set_input_file(self, input_path, use_html_output = False):
    if use_html_output:
      self.io_manager = HTMLIOManager(self.dialog_manager)
    else:
      self.io_manager = ConsoleIOManager(self.dialog_manager)
    
    self.io_manager.set_input_file(input_path)
    self.dialog_manager.set_io_manager(self.io_manager)
    
  def run(self):
    self.io_manager.run()



def show_usage():
  """Display usage arguments for dialogmanager when invoked from command line."""
  print "Dialog Manager:"
  print "   -h: HTML mode."
  print "   -d: Display debug messages."
  print "   -n: Console mode (run without an active connection to the simulator)."
  print "   -x: Test mode (may or may not connect to simulator, runs XML tests, displays results)."
  print "   -t: Run unit tests."
  print "   -f <filename>:  Read in transcript file, use this as input for Console or Test mode."
  print "   -s <filename>:  Use specified speech grammar file."
  print "   <remote host>:  Remote host to connect to (unless using -n)."
  print "\nNote: Not all options make sense together."
  # FIXME: is the current "unit test flag" enough?  it might be.  seems to only run FDL tests now,
  # could subvert.


def create_dm_for_bridge(host, action_module, grammar_path, fdl_path):
  dm = DialogManager(host, action_module, False)
  io_manager = speech.SpeechIOManager(dm)
  io_manager.set_grammar(grammar_path)
  dm.set_io_manager(io_manager)
  dm.load_fdl(fdl_path)
  return dm


if __name__ == "__main__":
  transcript = None
  connect = True
  html = False
  grammar = None
  runTests = False
  runXmlTests = False
  debug = False
  
  if len(sys.argv) == 1:
    show_usage()
    sys.exit(1) 
  
  try:
    optlist, args = getopt.getopt(sys.argv[1:], 'dhnxtf:s:')
    for o, v in optlist:
      if o == '-d':
        debug = True
      elif o == '-f':
        transcript = v
      elif o == '-n':
        connect = False
      elif o == '-x':
        runXmlTests = True   # think about this
      elif o == '-h':
        html = True
      elif o == '-s':
        grammar = v
      elif o == '-t':
        runTests = True
  except getopt.GetoptError, e:
    sys.stderr.write("%s: %s\n" % (sys.argv[0], e.msg))
    show_usage()
    sys.exit(1)
    
  # sanity check -- after processing args, do we have a host to connect to?
  if len(args) == 0 and connect == True:
    print "\nError: Invalid arguments, missing remote host for connection.\n"
    show_usage()
    sys.exit(1)
  
  if runXmlTests and transcript is None:
    print "\nError: Cannot run XML tests without a specified transcript file.\n"
    show_usage()
    sys.exit(1)
      
  if connect == False:
    host = None
  else:
    if len(args) != 1:
      show_usage()
      sys.exit(1)
    else:
      host = args[0]

  dmm = DialogManager(host, energid.actions, run_tests = runTests)

  if html:
    io_manager = iomanager.HTMLIOManager(dmm)
  elif grammar is not None:
    io_manager = speech.SpeechIOManager(dmm)
    io_manager.set_grammar(grammar)
  elif runXmlTests:
    io_manager = iomanager.TestIOManager(dmm)
  else:
    io_manager = iomanager.ConsoleIOManager(dmm)
  
  if transcript is not None:
    io_manager.set_input_file(transcript)

  if debug:
    io_manager.set_debug(True)

  dmm.set_io_manager(io_manager)

  dmm.load_fdl("../../../data/dialog/world.fdl")

  #    gen = speechutil.MicrosoftSRGrammarGenerator(dm.parser)
  #    print gen.generate_grammar()
  
  dmm.run()
