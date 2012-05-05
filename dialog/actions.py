from energid import logic
from energid import dialogmanager
from energid import iomanager
from energid import utils

import pprint
import time
import math
import random

def position_frame_to_vector(kb, position):
  # Make sure we're working with floats as opposed to, say, ints.
  x = float(kb.slot_value(position, logic.expr("x")).op)
  y = float(kb.slot_value(position, logic.expr("y")).op)
  z = float(kb.slot_value(position, logic.expr("z")).op)
  return [x, y, z]
  
def do_look_at(dm, parse):
  # FIXME: add ability to say "look at the south edge of the lake",
  # and then use this code in do_call_contact_location_obj (?)
  if not parse.has_slot("object"):
    dm.say("You need to tell me what to look at.")
  else:
    objdesc = parse.slot_value("object")
    objects = objdesc.find_instances(dm.kb)
    if len(objects) == 1:
      object = objects[0]
      dm.say("I am going to look at %s", object)
      position = dm.kb.slot_value(object, logic.expr("position"))
      dm.pilot_model.look_at(position_frame_to_vector(dm.kb, position))
    else:
      dm.debug("No instances matching %s" % (objdesc,))
      say_disamb_failure(dm, objects)

def do_fly_to(dm, parse):
  if not parse.has_slot("object"):
    dm.say("You need to tell me what to fly to.")
  else:
    objdesc = parse.slot_value("object")
    objects = objdesc.find_instances(dm.kb)
    if len(objects) == 1:
      object = objects[0]
      dm.say("I am going to fly to %s", object)
      position = dm.kb.slot_value(object, logic.expr("position"))
      dm.pilot_model.fly_to(position_frame_to_vector(dm.kb, position))
    else:
      dm.debug("No instances matching %s" % (objdesc,))
      say_disamb_failure(dm, objects)

    
def do_detail_query(dm, parse):
  print dm.pilot_model.get_details()


def do_all_query(dm, parse):
  print dm.pilot_model.getAll()

def do_tell_observe(dm, parse):
  if not parse.has_slot("object"):
    dm.say("You need to tell me what I'm supposed to see.")
  else:
    objdesc = parse.slot_value("object")
    type = dm.kb.slot_value(logic.expr(objdesc), logic.expr("type"))
    if type == None:
      dm.debug("No type slot on %s" % (objdesc,))
      dm.say("I don't really know what that is.")
    else:
      if dm.pilot_model.can_see_object_type(type.op):
        dm.say("roger")
      else:
        dm.say("negative")


def do_authentication_request(dm, parse):
  if dm.jtac_is_authenticated:
    dm.say("you have already authenticated")
  elif dm.jtac_authentication_requested:
    dm.say("negative")
    event_request_auth(dm, None)
  else:
    dm.say("hog authenticates bravo")
    dm.jtac_is_authenticated = True
  

def letter_to_phonetic_word(dm, letter):
  desc = logic.Description("c-nato-phonetic-word", {"letter": letter})
  words = desc.find_all(dm.kb)
  if len(words) == 0:
    return "unknown"
  else:
    return dm.generate("%s", words[0])
  
  
def do_abort_code_request(dm, parse):
  abort_code_words = map(lambda letter: letter_to_phonetic_word(dm, letter), dm.abort_code)
  abort_code_string = " ".join(abort_code_words)
  dm.say("abort code is %s" % (abort_code_string,))

def do_abort_code_ack(dm, parse):
  for i in range(0, 2):
    response_word = parse.slot_value("letter%s" % (i + 1,))
    response_letter = dm.kb.slot_value(response_word, "letter")
    if response_letter.op != dm.abort_code[i]:
      dm.say("negative %s %s", parse.slot_value("letter1"), parse.slot_value("letter2"))
      do_abort_code_request(dm, None)
      return

def do_nine_line_readiness_prompt(dm, parse):
  if dm.nine_line.is_complete():
    dm.say("you already gave me the nine-line")
  else:
    dm.set_parser_mode(dialogmanager.DialogManager.CONCEPTUAL_PARSER)
    if not dm.nine_line.has_data():
      # data hasn't been posted via any mechanism
      dm.state_machine.set_state(NINE_LINE)
      dm.say("go with 9-line.")
      accept_nine_lines(dm)
    else:
      # data has been posted, but not acknowledged
      event_offer_nine_line(dm)


def accept_nine_lines(dm):
  # First accept nine utterances
  lines = []
  for line in range(0, 9):
    dm.debug(dm.nine_line.debug_line(line))
    parses = dm.parse_with_prompt(all_parses = True)
    if dm.nine_line.any_object_is_valid_for_line(parses, line):
      dm.debug("Parse is valid for line %s" % (line + 1,))
    else:
      dm.debug("Parse is NOT valid for line %s" % (line + 1,))
    lines.append(parses)

  # Then check that the utterances fit the constraint on the
  # corresponding line in the nine-line.
  num_matching_lines = 0
  first_non_matching_line = None
  for line, parses in enumerate(lines):
    parse_matched = False
    if apply_parses_to_line(parses, dm.nine_line, line):
        num_matching_lines = num_matching_lines + 1
    else:
      if first_non_matching_line == None:
        first_non_matching_line = line

  # Respond based on how good a match we have.
  dm.debug("Have %s matching lines" % (num_matching_lines,))
  if num_matching_lines == 9:
    dm.debug("Got complete nine line")
    return
  elif num_matching_lines == 8:
    dm.debug("need line %s" % (first_non_matching_line + 1,))
    dm.say("Say again line %s" % (first_non_matching_line + 1,))
    dm.debug(dm.nine_line.debug_line(first_non_matching_line))
    parses = dm.parse_with_prompt(all_parses = True)
    if dm.nine_line.any_object_is_valid_for_line(parses, first_non_matching_line):
      dm.debug("Parse is valid for line %s" % (first_non_matching_line + 1,))
    else:
      dm.debug("Parse is NOT valid for line %s" % (first_non_matching_line + 1,))

    if apply_parses_to_line(parses, dm.nine_line, first_non_matching_line):
      dm.debug("Got remaining line")
      return
    
  dm.say("I didn't get that, say again all nine lines")
  dm.nine_line.reset()
  accept_nine_lines(dm)

def fake_apply_nine_line_data(nine_line, line, raw_text):
  # lamely accept text as nine-line data
  nine_line.set_line(raw_text, line, force_accept = True)
  nine_line.set_raw_text(raw_text, line)
  return True
  
def apply_parses_to_line(parses, nine_line, line, raw_text=""):
  for parse in parses:
    if nine_line.object_is_valid_for_line(parse, line):
      nine_line.set_line(parse, line)
      nine_line.set_raw_text(raw_text, line)
      return True
  return False
  
def accept_one_line(dm):
  parses = dm.parse_with_prompt(all_parses = True)
  
  
def do_copy_req(dm, parse):
  if dm.nine_line.is_complete():
    dm.say("%s copies all.", dm.pilot_callsign)
    has_remarks = accept_roger_or_negative(dm, dm.generate("Do you have remarks for %s flight?", dm.pilot_callsign))
    if has_remarks:
      accept_remarks(dm)
  else:
    pass


def accept_roger_or_negative(dm, prompt):
  while True:
    dm.say(prompt)
    parse = dm.parse_with_prompt()
    if dm.kb.isa(logic.expr(parse), logic.expr("c-roger")):
      return True
    elif dm.kb.isa(logic.expr(parse), logic.expr("c-negative")):
      return False
    else:
      dm.say("that didn't answer the question.")


def accept_remarks(dm):
  dm.debug("Accepting remarks")
  while True:
    # MRH 3/27/07: we don't need to save these, right?  reading back remarks just
    # data sent from jtac for now.
    parse = dm.parse_with_prompt()
    if dm.kb.isa(logic.expr(parse), logic.expr("c-say-when-ready-for-talkon")):
        dm.debug("Remarks appear to be complete")
        dm.say("go with talk on")
        # dm.conv_state.set_state("talk-on")
        dm.state_machine.set_state(TALK_ON)
        return

def do_endex(dm, parse):
  dm.say("copy endex")
  dm.debug("Resetting exercise.  Should reset sim to initial state.  Resetting dialog.")
  raise dialogmanager.EndExercise

def custom_resolver(dm, desc):
  resolver_name = dm.kb.slot_value(desc, "custom-resolver")
  if resolver_name:
    return dm.lookup_action_function(resolver_name.op)
  else:
    return None

def say_disamb_failure(dm, objects):
  if len(objects) > 1:
    dm.say("sorry, I don't know which one you mean.")
  elif len(objects) == 0:
    dm.say("sorry, I don't know that.")

def do_call_contact(dm, parse):
  objdesc = parse.slot_value("object")
  objects = []
  if custom_resolver(dm, objdesc):
    objects = apply(custom_resolver(dm, objdesc), [dm, objdesc])
  else:
    objects = objdesc.find_instances(dm.kb)
  if len(objects) == 1:
    call_contact_with_resolved_object(dm, objects[0])
  else:
    # FIXME: Think about merging do_call_contact and do_implied_call_contact.
    do_implied_call_contact(dm, parse)

def call_contact_with_resolved_object(dm, object):
  position = dm.kb.slot_value(object, logic.expr("position"))
  objectID = dm.kb.slot_value(object, logic.expr("objid"))
  if position == None:
    if objectID == None:
      dm.debug("Object %s has position slot, but no objid" % (object,))
    dm.debug("No position")
    say_negative_contact(dm, object)
  else:
    pos = position_frame_to_vector(dm.kb, position)
    dm.debug("Pilot is looking at %s" % (pos,)) 
    dm.pilot_model.look_at(pos)
    if dm.pilot_model.can_see_object_id(objectID.op):
      dm.set_focus_of_attention(object)
      say_positive_contact(dm, object)
    else:
      say_negative_contact(dm, object)
  

def say_positive_contact(dm, object):
  dm.say_random([5, ["contact"]],
                [3, ["contact %s", object]],
                [2, ["visual %s", object]])

def say_negative_contact(dm, object):
  dm.say_random([5, ["negative contact"]],
                [3, ["negative contact %s", object]])

def disambiguate_object(dm, description):
  kb_instances = description.find_instances(dm.kb)
  if len(kb_instances) == 1:
    # There's only one in the world, which is pretty unambiguous.
    dm.debug("%s is unambiguous; there's only one in the world." % (description,))
    return kb_instances[0]
  elif len(kb_instances) == 0:
    # There are none in the world, which is also unambiguous.
    dm.debug("No objects match %s." % (description,))
    return None
  else:
    # There's more than one in the world:
    dm.debug("this path through disambiguate_object is not yet implemented")
    assert False

def do_establish_unit_of_measurement(dm, parse):
  # disambiguate object
  objdesc = parse.slot_value("object")
  object = disambiguate_object(dm, objdesc)
  if object == None:
    dm.say("negative, do not see %s", objdesc)
  else:
    extentdesc = parse.slot_value("extent")
    extent = get_object_extent(dm, object, extentdesc)
    if extent == None:
      dm.debug("Extent %s of %s is not known." % (extentdesc, object))
      dm.say("I can't tell what the %s is.", extentdesc)
    else:
      dm.set_unit_of_measure(extent)
      dm.say("copy")
      
def do_reuse_unit_of_measure(dm, parse):
  """If a unit of measure was previously established, re-use it; otherwise, complain."""
  if dm.previous_unit_of_measure == None:
    dm.say("negative, no previous unit of measure established.")
  else:
    dm.set_unit_of_measure(dm.previous_unit_of_measure)
    dm.say("copy")

def do_reuse_anchor_point(dm, parse):
  """If an anchor point was previously established, re-use it; otherwise, complain."""
  if dm.previous_anchor_point == None:
    dm.say("negative, no previous anchor point established.")
  else:
    dm.set_anchor_point(dm.previous_anchor_point)
    dm.say("copy")

def do_reuse_anchor_point_and_uom(dm, parse):
  """If a unit of measure and anchor point were both previously established, re-use; otherwise, complain."""
  if dm.previous_unit_of_measure == None:
    dm.say("negative, no previous unit of measure established.")
  elif dm.previous_anchor_point == None:
    dm.say("negative, no previous anchor point established.")
  else:
    dm.set_unit_of_measure(dm.previous_unit_of_measure)
    dm.set_anchor_point(dm.previous_anchor_point)
    dm.say("copy")

def do_disregard_unit_of_measure(self, parse):
  # Choosing not to save disregarded unit of measure in previous state, at least for now
  if dm.unit_of_measure == None:
    dm.say("no previous unit of measure established.")
  else:
    dm.set_unit_of_measure(None)
    dm.say("copy")


def get_object_extent(dm, object, extentdesc):
  def axis_name(axis):
    name = dm.kb.slot_value(axis, logic.expr("extent-slot-name"))
    if name != None:
      return name.op
    else:
      return None

  def extent_name(extent):
    name1 = axis_name(dm.kb.slot_value(extent, "axis-origin"))
    name2 = axis_name(dm.kb.slot_value(extent, "axis-destination"))
    if name1 == None or name2 == None:
      dm.debug("axis-origin of %s is %s, axis-destination is %s" % (extent, name1, name2))
      return None
    else:
      names = [name1, name2]
      names.sort()
      name = "%s%sExtent" % (names[0].lower(), names[1].capitalize())
      dm.debug("extent slot is %s" % (name,))
      return name
    
  extent_slot_name = extent_name(extentdesc)
  if extent_slot_name == None:
    return None
  else:
    extent = get_object_sim_property(dm, object, extent_slot_name)
    if extent != None:
      return float(extent)
    else:
      return None

def get_object_sim_property(dm, object, property):
  objid = dm.kb.slot_value(object, "objid")
  if objid == None:
    dm.debug("Unknown objid for %s" % (object,))
    return None
  properties = dm.pilot_model.get_object_details({"name": objid.op})
  if properties == False or len(properties) != 1:
    dm.debug("Got %s back for objid %s; wanted a sequence with 1 element." % (properties, objid.op))
    return None
  properties = properties[0]
  value = properties[property]
  dm.debug("%s of %s is %s" % (property, objid.op, value))
  return value
  
def do_establish_anchor_point1(dm, parse):
  # disambiguate_object
  objdesc = parse.slot_value("object")
  object = disambiguate_object(dm, objdesc)
  if object == None:
    dm.say("I don't know where %s is", objdesc)
  else:
    pointdesc = parse.slot_value("point")
    point = get_object_point(dm, object, pointdesc)
    if point == None:
      dm.debug("Point %s of %s is not known" % (pointdesc, object))
      dm.say("I don't know where the %s is", pointdesc)
    else:
      dm.set_anchor_point(point)
      dm.say("copy")

def do_establish_anchor_point2(dm, parse):
  # disambiguate_object
  objdesc = parse.slot_value("object")
  object = disambiguate_object(dm, objdesc)
  if object == None:
    dm.say("I don't know where %s is", objdesc)
  else:
    pointdesc = parse.slot_value("point")
    point = get_object_point(dm, object, pointdesc)
    if point == None:
      dm.debug("Point %s of %s is not known" % (pointdesc, object))
      dm.say("I don't know where the %s is", pointdesc)
    else:
      dm.set_anchor_point(point)
      dm.say("copy")

def get_object_point(dm, object, pointdesc):
  get_method = dm.kb.slot_value(pointdesc, "get-method")
  if get_method == None:
    dm.debug("%s has no get-method to determine the point" % (pointdesc,))
    return None
  else:
    function = dm.lookup_action_function(get_method.op)
    point = function(dm, pointdesc, object)
    return point

def get_edge_point(dm, pointdesc, object):
  direction = dm.kb.slot_value(pointdesc, "direction").op
  direction_slot_part = dm.kb.slot_value(direction, "extent-slot-name")
  if direction_slot_part == None:
    dm.debug("%s has no extent-slot-name" % (direction,))
    return None
  else:
    limit_slot_name = "%sLimit" % (direction_slot_part.op.lower(),)
    limit_coords = get_object_sim_property(dm, object, limit_slot_name)
    if limit_coords != None:
      limit_coords = eval(limit_coords)
      if len(limit_coords) == 2:
        limit_coords = limit_coords + (0,)
      return limit_coords
    else:
      return None
  

def do_look_based_on_unit_of_measure_from_anchor(dm, parse):
  # Historically, the default has been to look from the currently specified anchor
  # in the direction of the vector.
  # Save memory of where we looked, so we can look based upon that later.
  if dm.unit_of_measure == None:
    dm.say("you didn't give me a unit of measure")
    return
  if dm.anchor_point == None:
    dm.say("you didn't give me an anchor point")
    return

  __look_based_on_unit_of_measure_helper(dm, parse, dm.anchor_point)

def do_look_based_on_unit_of_measure_no_anchor(dm, parse):
  # New option:  look from wherever you're looking now, in the direction.
  # Although, if we'd never looked before, start from the anchor.
  if dm.unit_of_measure == None:
    dm.say("you didn't give me a unit of measure")
    return

  start_point = dm.state_machine.data.last_look_loc
  is_anchor = False
  if start_point is None:
    if dm.anchor_point == None:
      dm.say("you didn't give me an anchor point")
      return
    else:
      is_anchor = True
      start_point = dm.anchor_point

  __look_based_on_unit_of_measure_helper(dm, parse, start_point, is_anchor)

def __look_based_on_unit_of_measure_helper(dm, parse, start_point, is_anchor = True):
  # helper function for the above two methods
  vector = unit_vector_sum_frame_to_vector(dm.kb, parse.slot_value("vector"))
  if vector is None:
    # then something bad happened in doing the vector operations
    dm.say("%s did not copy" % dm.pilot_callsign)
  else:
    vector = vector_mult(vector, dm.unit_of_measure)
    if is_anchor:
      dm.debug("vector is %s from anchor point" % (vector,))
    else:
      dm.debug("vector is %s from current position %s" % (vector, start_point))
    target = vector_add(start_point, vector)
    dm.debug("target coords are %s" % (target,))
    dm.pilot_model.look_at(target)
    dm.state_machine.data.last_look_loc = target
    dm.say("roger")
  

def unit_vector_sum_frame_to_vector(kb, vectordesc):
  if vectordesc == None:
    return [0, 0, 0]
  
  first = kb.slot_value(vectordesc, "first-vector")
  rest = kb.slot_value(vectordesc, "rest-vector")

  if rest == None:
    return vector_frame_to_vector(kb, first)
  else:
    return vector_add(vector_frame_to_vector(kb, first), unit_vector_sum_frame_to_vector(kb, rest))


def number_frame_to_value(kb, frame):
  # Adding rational numbers; need to add integer portion to fractional portion
  if kb.slot_value(frame, "value"):
    v = numberify(kb.slot_value(frame, "value").op)
    print "simple value: %s" % (v,)
    return v
  elif kb.isa(frame, logic.expr("c-rational")):
    int_frame = kb.slot_value(frame, "integer")
    fra_frame = kb.slot_value(frame, "fraction")
    result = number_frame_to_value(kb, int_frame) + number_frame_to_value(kb, fra_frame)
    print "rational: %s" % (result,)
    return result      # FIXME: ugly returning from middle of function, clean up
  else:
    digit = kb.slot_value(frame, "first")
    digit_value = kb.slot_value(digit, "value")
    rest = kb.slot_value(frame, "rest")
    v = 0
    if rest:
      print "first: %s  rest: %s" % (digit_value, rest)
      v = 10 * numberify(digit_value.op) + number_frame_to_value(kb, rest)
    else:
      v = numberify(digit_value.op)
    print "number: %s" % (v,)
    return v

def integer_frame_to_value(kb, frame):
  def frame_to_digits(f):
    first = kb.slot_path_value(f, "first", "value").op
    rest = kb.slot_value(f, "rest")
    if rest:
      return [first,] + frame_to_digits(rest)
    else:
      return [first]
  digits = frame_to_digits(frame)
  value = 0
  for digit in digits:
    value = value * 10
    value = value + digit
  return value
    
  
def number_frame_to_value(kb, frame):
  frame = logic.expr(frame)
  # Adding rational numbers; need to add integer portion to fractional portion
  if kb.slot_value(frame, "value"):
    v = numberify(kb.slot_value(frame, "value").op)
    print "simple value: %s" % (v,)
    return v
  elif kb.isa(frame, logic.expr("c-rational")):
    int_frame = kb.slot_value(frame, "integer")
    fra_frame = kb.slot_value(frame, "fraction")
    result = number_frame_to_value(kb, int_frame) + number_frame_to_value(kb, fra_frame)
    print "rational: %s" % (result,)
    return result      # FIXME: ugly returning from middle of function, clean up
  else:
    return integer_frame_to_value(kb, frame)
  
#    digit = kb.slot_value(frame, "first")
#    digit_value = kb.slot_value(digit, "value")
#    rest = kb.slot_value(frame, "rest")
#    v = 0
#    if rest:
#      print "first: %s  rest: %s" % (digit_value, rest)
#      v = 10 * numberify(digit_value.op) + number_frame_to_value(kb, rest)
#    else:
#      v = numberify(digit_value.op)
#    print "number: %s" % (v,)
#    return v


def vector_frame_to_vector(kb, frame):
  measurement = kb.slot_value(frame, "magnitude")
  direction = kb.slot_value(frame, "direction")
  
  magnitude = kb.slot_value(measurement, "magnitude")
  value = number_frame_to_value(kb, magnitude)
  direction_vector = raw_vector_frame_to_vector(kb, kb.slot_value(direction, "rawvector"))
  return vector_mult(direction_vector, value)

def numberify(value):
  if isinstance(value, str):
    return float(eval(value))
  else:
    return float(value)
  
def raw_vector_frame_to_vector(kb, vector):
  # Make sure we're working with floats as opposed to, say, ints.
  x = numberify(kb.slot_value(vector, logic.expr("x")).op)
  y = numberify(kb.slot_value(vector, logic.expr("y")).op)
  z = numberify(kb.slot_value(vector, logic.expr("z")).op)
  return [x, y, z]
  


def vector_add(v1, v2):
  sum = []
  for i in range(0, len(v1)):
    sum.append(v1[i] + v2[i])
  return sum

def vector_subtract(v1, v2):
  return vector_add(v1, vector_mult(v2, -1))

def vector_mult(vector, scalar):
  product = []
  for i in range(0, len(vector)):
    product.append(vector[i] * scalar)
  return product

def dot_product(v1, v2):
  sum = 0.0
  for i in range(0, len(v1)):
    sum = sum + v1[i] * v2[i]
  return sum

def vector_length(vector):
  sum = 0.0
  for e in vector:
    sum = sum + e*e
  return math.sqrt(sum)
  

def normalize(vector):
  return vector_mult(vector, 1.0 / vector_length(vector))


def do_implied_call_contact(dm, parse):
  # 2/26/07 mrh: Adding use of "can_see_object" method in case where object has no type/subtype.
  found_object = False
  object = parse.slot_value("object")
  type = dm.kb.slot_value(object, "type")
  subtype = dm.kb.slot_value(object, "subtype")
  if type != None:
    # if we have a type available, use it for looking up info
    type = type.op
    if subtype != None:
      subtype = subtype.op
    # dm.debug("** implied call contact looking by type: (%s,%s)" % (type, subtype))
    found_object = dm.pilot_model.can_see_object_type(type, subtype)
  else:
    # Otherwise, just take what properties we're given and look for
    # matching objects.
    props = parse.dictify()  # FIXME: flatten lists properly, this doesn't work
    # dm.debug("** implied call contact looking by properties: %s" % props)
    found_object = dm.pilot_model.can_see_object(props)
  # did we see it?
  if found_object:
    if dm.nine_line.is_complete() and dm.nine_line.get_line("target description").base == object.base:
      tally_and_fly_to_target(dm, object)
    else:
      say_positive_contact(dm, object)
  else:

    dm.say("negative, I do not see %s", object)    

def do_call_contact_location_obj(dm, parse):
  """Experimenting with a new call contact method in which the
  user gives both a location and an object.  The pilot has to first
  look at the location, and then see if the object is there.  This is
  more similar to do_implied_call_contact than do_call_contact.
  The location itself is the relative to some known object in memory.
  
  Also borrows some from do_establish_anchor_point1, which combines
  locations with objects in the right way.
  """
  
  # expect parse to have location & object slots.
  
  # first, get the location.  take it apart, look at it.
  # then, find the proper extent, look at that.  (is that necessary? you'll be looking nearby...)
  # cribbed from do_establish_anchor_point1.
  compound_location = parse.slot_value("location")
  location_obj_desc = compound_location.slot_value("object")
  location_obj = disambiguate_object(dm, location_obj_desc)
  if location_obj == None:
    dm.say("I don't know where %s is", location_obj)
  else:
    # We have the main object of the location; look at it.
    location_obj_pos = dm.kb.slot_value(location_obj, logic.expr("position"))
    location_obj_oid = dm.kb.slot_value(location_obj, logic.expr("objid"))
    if location_obj_oid is None:
      dm.debug("Object %s has no objid propety" % location_obj)
    if location_obj_pos is None:
      dm.say("I don't know where %s is", location_obj)
    if location_obj_pos is not None and location_obj_oid is not None:
      temp_pos = position_frame_to_vector(dm.kb, location_obj_pos)
      dm.pilot_model.look_at(temp_pos)
      # verify
      if dm.pilot_model.can_see_object_id(location_obj_oid.op) == False:
        say_negative_contact(dm, location_obj_desc)
        # early escape
        return
      
    location_point_desc = compound_location.slot_value("point")
    location_point = get_object_point(dm, location_obj, location_point_desc)
    if location_point == None:
      dm.debug("Point %s of %s is not known" % (location_point_desc, location_obj))
      dm.say("I don't know where the %s is", location_point_desc)
    else:
      # step 2: we have a point!  make the pilot look at it.  do they see the object?
      # if so, call contact with it.
      dm.debug("Pilot is looking at %s" % (location_point,))
      dm.pilot_model.look_at(location_point)
      # looking seems to be pretty fast...
      
      # okay, now piggy-back on do-implied-call-contact.  dicc expects an object slot, we've got one naturally.
      dm.debug("Pilot was able to look at location portion of object")
      do_implied_call_contact(dm, parse)

def tally_and_fly_to_target(dm, target):
  dm.say("tally %s, departing IP at this time", target)
  type = dm.kb.slot_value(target, "type").op
  subtype = dm.kb.slot_value(target, "subtype")
  props = {}

  if subtype == None:
    props["category"] == type
  else:
    props["type"] = subtype.op
  target_locations = dm.pilot_model.get_object_location(props)
  if len(target_locations) == 1:
    target_location = target_locations[0]
    dm.pilot_model.fly_to(target_location, type="inbound to target")
    dm.pilot_model.look_at(target_location)
    dm.on_attack_run = True
    # dm.conv_state.set_state("run-in-begin")
    dm.state_machine.set_state(RUN_IN)
  else:
    dm.debug("bad target locations for target %s of type '%s': %s; Cannot begin attack run" % (target, type, target_locations))

def do_nop(dm, parse):
  pass


def do_target_status_assertion(dm, parse):
  dm.say("copy")


def handle_nine_line_post_event(dm, event):
  """Handle the nine-line data sent from the GUI.  
  Data should be a dictionary with keys 1-9 holding 9-line values, and 
  optionally a "remarks" section.
  """
  # mrh 4/18/07: now, can only get to this function if nine-line is sent while in 
  #              accepting state (mostly NINE_LINE, but also CHECK_IN if sent when
  #              python connects)

  # 5/4 mrh: Update! Only parsing target right now.  Just accept the rest. (FIXME)

  # any reason not to immediately acknowledge nine-line data?
  def handle_nine_line(line_input, line_no):
    # this is the hack:
    if line_no == 4:
      parses = dm.parse(iomanager.IORecord('jtac', line_input))
      dm.debug("%s" % (parses,))
      pprint.pprint(parses)
      # check return value of apply?
      return apply_parses_to_line(parses, dm.nine_line, line_no, line_input)
    else:
      # just accept it, if it's not the target line
      return fake_apply_nine_line_data(dm.nine_line, line_no, line_input)

  # set parser to ICP mode, so it can parse the 9-line
  # 5/4 mrh: changing to use ICP for parsing instead of CP, so it handles "t-55 dug in"
  init_parser_mode = dm.parser_mode
  # dm.set_parser_mode(dialogmanager.DialogManager.CONCEPTUAL_PARSER)
  dm.set_parser_mode(dialogmanager.DialogManager.INDEXED_CONCEPT_PARSER)
  result = True
  for i in range(9):
    line_text = event[str(i+1)]
    if handle_nine_line(line_text, i) == False:
      dm.debug("Failed to post nine-line data on line %d, text {%s}" % (i, line_text))
      result = False
  if event.has_key("remarks"):
    dm.nine_line.set_remarks(event["remarks"])
  if result:
    # print "** Nine line handled successfully"
    dm.nine_line.mark_as_needs_acknowledgement()
    # move to nine line state, since it would be OK for them to say things like
    # "go with readback" and "say when ready for talk on"
    dm.state_machine.set_state(NINE_LINE)
    # dm.set_parser_mode(dialogmanager.DialogManager.CONCEPTUAL_PARSER)
    # 5/13: leave in ICP mode until talk-on?
    event_offer_nine_line(dm)
  else:
    dm.debug("Nine line handling failure!")
    dm.say("there was an error handling the nine line, please re-send")
    # if parser mode different than ICP, reset it
    # if init_parser_mode != dialogmanager.DialogManager.CONCEPTUAL_PARSER:
    if init_parser_mode != dialogmanager.DialogManager.INDEXED_CONCEPT_PARSER:
      dm.set_parser_mode(init_parser_mode)
  return result

def magic_trigger_nine_line(dm, parse=None, target=None):
  dm.pilot_model.trigger_nine_line(target=target)

def magic_fake_nine_line(dm, parse):
  # FIXME: this is really just a convenience hack; remove this later?
  def handle_nine_line(line_input, line_no):
    parses = dm.parse(iomanager.IORecord('pilot', line_input))
    # check return value of apply?
    return apply_parses_to_line(parses, dm.nine_line, line_no, line_input)
  
  data = ("bravo", "346 degrees, offset 30 degrees right", "5 nautical miles",
          "3300 feet", "t-55", "nv 399282", "none", "2 clicks south", "I.P.")
  
  dm.set_parser_mode(dialogmanager.DialogManager.CONCEPTUAL_PARSER)
  result = True
  for (line_no, line_input) in enumerate(data):
    if handle_nine_line(line_input, line_no) == False:
      dm.debug("Failed to fake nine-line data on line %d, text {%s}?" % (line_no, line_input))
      result = False
  if result:
    # dm.conv_state.set_state("nine-line-pending-ack")
    dm.state_machine.set_state(NINE_LINE)
    event_offer_nine_line(dm)

def do_nine_line_readback(dm, parse):
  """Read back the nine-line data we've got."""
  if dm.nine_line.has_data():
    dm.say("affirm.  standby one")
    readback = "I have " + "; ".join(dm.nine_line.raw_text)
    if readback.rstrip().endswith(".") == False:
      readback += "."
    remarks = dm.nine_line.get_remarks()
    if len(remarks.strip()) == 0:
      remarks = None
    readback = readback + "  Remarks: %s" % remarks  # "Remarks: None" is valid
    dm.say(readback)
    # Brian suggested removing the "how copy"; 4/13 mrh
    # dm.say_without_callsign("How copy?")
    if dm.state_machine.current_state is NINE_LINE:
      dm.nine_line.mark_as_acknowledged()
      # 4/27: set as in talk-on state now
      dm.state_machine.set_state(TALK_ON)
  else:
    dm.say("negative, I do not have your nine-line")

CARDINAL_DIRECTION_VECTORS = None

def compute_cardinal_direction_vectors(dm):
  global CARDINAL_DIRECTION_VECTORS
  CARDINAL_DIRECTION_VECTORS = {}
  for direction in dm.kb.all_proper_children(logic.expr("c-cardinal-direction")):
    vector_frame = dm.kb.slot_value(direction, logic.expr("rawvector"))
    if vector_frame != None:
      direction_name = dm.generate("%s", direction)
      vector = raw_vector_frame_to_vector(dm.kb, vector_frame)
      CARDINAL_DIRECTION_VECTORS[direction_name] = vector
  
  
def classify_vector_as_cardinal_direction(dm, vector):
  vector = normalize(vector)
  largest_dot_product = None
  closest_direction = None
  for direction in CARDINAL_DIRECTION_VECTORS:
    dir_vector = CARDINAL_DIRECTION_VECTORS[direction]
    dp = dot_product(vector, dir_vector)
    if largest_dot_product == None or dp > largest_dot_product:
      largest_dot_product = dp
      closest_direction = direction
  return closest_direction


def do_say_again(dm, parse):
  dm.say_again()

def do_standby(dm, parse):
  time.sleep(10)
  dm.say_again()

def do_push_frequency(dm, parse):
  # For now, not really doing anything with this, just acknowledging.
  # Pull out the frequency they mentioned
  freq = parse.slot_value("frequency")
  # Construct an utterance and use it.
  desc = None
  if random.randint(0,1) == 0:
    desc = logic.Description("c-frequency-change-ok",
                             {"from-agent":dm.pilot_callsign,
                              "frequency":freq})
  else:
    desc = logic.Description("c-frequency-change-deny",
                             {"from-agent":dm.pilot_callsign,
                              "frequency":freq})
  dm.say(dm.generate("%s", desc))


def do_what_do_you_see(dm, parse):
  entities = dm.pilot_model.get_all()
  # Determine classes
  for e in entities:
    e['class'] = descriptor_class(dm, e)
  # Sort
  def is_target(desc):
    return 'class' in desc and desc['class'] and dm.kb.isa(logic.expr(desc['class']), logic.expr('c-tank'))
  def desc_key(desc):
    score = desc['blob']['size']
    if is_target(desc):
      score += 1000000
    return score
  def find_closest_desc(desc, descriptors):
    descriptors = descriptors[:]
    loc = desc['location']
    def dist(d):
      return utils.distance(loc[0:2], d['location'][0:2])
    descriptors.sort(key=dist)
    return descriptors[0]

  for e in entities:
    print e['class']
  entities.sort(key=desc_key, reverse=True)
  if len(entities) == 0:
    dm.say("I don't see anything")
  elif len(entities) == 1:
    dm.say("I see %s", entities[0]['class'])
  else:
    e0 = entities[0]
    e1 = entities[1]
    if is_target(e0) and is_target(e1):
      dm.say("I see a %s and a %s", e0['class'], e1['class'])
    elif is_target(e0):
      e1 = find_closest_desc(e0, entities[1:])
      dm.say("I see a %s %s of the %s",
             e0['class'],
             classify_vector_as_cardinal_direction(dm, vector_subtract(e0['location'], e1['location'])),
             e1['class'])
    else:
      dm.say("I see the %s and to the %s of that I see the %s",
             e0['class'],
             classify_vector_as_cardinal_direction(dm, vector_subtract(e1['location'], e0['location'])),
             e1['class'])


def generate_descriptor(dm, descriptor):
  cls = descriptor_class(dm, descriptor)
  if cls:
    return dm.generate("%s", cls)
  if 'alias' in descriptor:
    return descriptor['alias'].split(',')[0].strip()
    
def descriptor_class(dm, descriptor):
  def gen_ids(s):
    s = s.replace(" ", "-").replace(",", "-")
    ids = [s, s.lower(),
           "i-" + s, ("i-" + s).lower(),
           "c-" + s, ("c-" + s).lower()]
    return [logic.expr(id) for id in ids]
  def gen_ids_for_prop(prop):
    if prop in descriptor:
      return gen_ids(descriptor[prop])
    else:
      return []
  def classp(id):
    return len(dm.kb.all_proper_parents(id)) > 0

  for id in gen_ids_for_prop('name'):
    if classp(id):
      return id
  for id in gen_ids_for_prop('type'):
    if classp(id):
      return id
  for id in gen_ids_for_prop('category'):
    if classp(id):
      return id
  dm.debug("Unknown class for descriptor %s" % (descriptor,))
  return None

  
  
def init_module(dm):
  print "Initializing actions module"
  compute_cardinal_direction_vectors(dm)


def testing_skip_to_talkon(dm, target_type="t-55"):
  """Skip past nine-line, set up current state so that we're ready for talk-on."""
  # HACK: this is just for doing XML-based testing.
  # Circumventing the DM.NineLine class to do this manually breaks OO rules pretty
  # badly, but let's just see if the rest of the mechanism will work for now.
  def skip_helper(line_num, phrase):
    inputrecord = iomanager.IORecord('pilot', phrase)
    apply_parses_to_line(dm.parse(inputrecord), dm.nine_line, line_num, phrase)
  # authentication?
  if not dm.jtac_is_authenticated:
    # FIXME: should also write in auth code
    dm.jtac_is_authenticated = True
    # dm.conv_state.set_state("nine-line-no-data")
    dm.state_machine.set_state(NINE_LINE)
    
  dm.nine_line.reset()
  dm.set_parser_mode(dialogmanager.DialogManager.CONCEPTUAL_PARSER)
  
  # parameterize target type
  lines = ["Denver", "three three zero degrees", "five nauticals",
           "two zero zero zero feet",
           target_type,
           "hotel kilo four zero four six six", 
           "none", "one kilometer south", "IP"]
  
  for line_num, phrase in enumerate(lines):
    skip_helper(line_num, phrase)


def do_respond_to_nine_line_query(dm, parse):
  if dm.nine_line.is_complete():
    dm.say("roger, I have your nine-line")
  else:
    dm.say("negative, I do not have your nine-line")
  

def do_status_query_position_helper(dm):
  # function for use both by do_status_query_position, and do_authentication_response
  # returns (distance, direction) to IP Bravo
  pilot_pose = dm.pilot_model.get_pilot_pose()
  if pilot_pose is None:
    dm.debug("failed to retrieve pilot pose")
    return None
  else:
    heading = pilot_pose[0]
    position = pilot_pose[1]
    # get the IP Bravo position from the kb
    bravo_pos_desc = logic.Description("i-ip-bravo-position")
    bravo_pos = position_frame_to_vector(dm.kb, bravo_pos_desc)
    relative_vector = vector_subtract(position, bravo_pos)
    relative_direction = classify_vector_as_cardinal_direction(dm, relative_vector)
    # now, assuming that the coordinates are in meters...
    dist = utils.distance((bravo_pos[0], bravo_pos[1]), (position[0], position[1]))
    # if that's in meters, let's round to half a kilometer?
    dist2 = int(dist/500.0)/2.0
    return (dist2, relative_direction)
  
def magic_switch_to_concept_parser(dm, parse):
  """Switch to the CP."""
  dm.set_parser_mode(dialogmanager.DialogManager.CONCEPTUAL_PARSER)
  
def magic_switch_to_indexed_parser(dm, parse):
  """Switch to the ICP."""
  dm.set_parser_mode(dialogmanager.DialogManager.INDEXED_CONCEPT_PARSER)

# ---------------------------------------------------------------------------
# Code called from state functions handling events

def event_request_auth(dm, event):
  dm.say("authenticate %s" % (dm.authentication_challenge_code,))


def event_offer_nine_line(dm, from_go_ahead=False):
  """Depending on state in the data object, either prompt
  the user for a nine-line, or ask if they want to read back
  the data that's been sent, or perhaps do nothing.
  """
  
  if dm.nine_line.has_data():
    # should probably keep track of whether not we've said this?
    dm.say("I have the nine-line you sent, say when ready for read-back")
  elif dm.state_machine.data.requested_nine_line == False or \
          from_go_ahead == True:
    dm.say("do you have a nine-line for me?")
    dm.state_machine.data.requested_nine_line = True



# ---------------------------------------------------------------------------
# States

# why make these objects here?  excellent question.  probably being un-pythonic
# in my attempt to make the language do error checking for me.  --mrh
CHECK_IN = None
NINE_LINE = None
TALK_ON = None
RUN_IN = None
RADIO_CHECK = None
BOGEY_ID = None
BULLSEYE_RUN_IN = None

def populate_states(machine):
  """Create the state objects we'll use, tying them to the 
  specified State Machine."""

  # create state objects up front, making it more direct for them to share data
  # (is it bad to use caps for emphasis when they're not constants?)
  global CHECK_IN, NINE_LINE, TALK_ON, RUN_IN, RADIO_CHECK, BOGEY_ID, BULLSEYE_RUN_IN
  CHECK_IN = CheckInState(machine)
  NINE_LINE = NineLineState(machine)
  TALK_ON = TalkOnState(machine)
  RUN_IN = RunInState(machine)
  RADIO_CHECK = RadioCheckState(machine)
  BOGEY_ID = BogeyIDState(machine)
  BULLSEYE_RUN_IN = BullseyeRunInState(machine)
  
  # set initial state, too
  machine.set_state(CHECK_IN)

def cleanup_states():
  # at all necessary?  don't know.  -mrh
  global CHECK_IN, NINE_LINE, TALK_ON, RUN_IN
  CHECK_IN = None
  NINE_LINE = None
  TALK_ON = None
  RUN_IN = None
  RADIO_CHECK = None

class StateData:
  """Holds data in a repository separate from the StateMachine or DialogManager
  classes."""
  
  def __init__(self):
    self.reset()
  
  def reset(self):
    self.idle_count = 0               # no. of times idle in a row
    self.requested_nine_line = False  # have not asked the user for a nine-line yet
    self.eta_given = False            # has the ETA been given?
    self.run_in_hot = False           # is the run-in hot?
    self.saved_nine_line = None       # nine-line event data sent prior to checkin?
    self.last_look_loc = None         # last location we looked at; None or (x,y,z)
  
  def reset_idle_count(self):
    self.idle_count = 0
  
  def increment_idle_count(self):
    self.idle_count += 1
    # print "** New idle count: %d" % self.idle_count
  
  
class BaseState(object):
  """This state is meant to be the inherited ("abstract") parent of the states
  that actually get used in the system.  This provides methods and actions for
  dealing with the standard/anytime language like "get playtime".  Child classes
  will pass the buck up to this class when they don't want to handle something.
  
  Reference to the StateMachine object is held here for all child classes.
  """
  
  CONST_IDLE_MAX = 10   # 5 minutes of idle for the "radio check"
  
  def __init__(self, machine):
    self.machine = machine
    self.data = machine.data    # direct reference
    self.dm = machine.dm        # direct ref.

  def name(self):
    return "Base State"
  
  def enter(self):
    """This method allows states to have custom behavior on state entry."""
    pass
  
  def exit(self):
    """This method allows states to have custom behavior on state exit."""
    pass
  
  # called from outside
  def handle_event(self, event_type, event_obj):
    # print "** BaseState: event %s" % event_type
    if event_type == "conversation-idle":
      self.base_idle_behavior()
    
    elif event_type == "nine-line":
      self.dm.say("I already have a nine-line for this mission.")
      
    else:
      self.dm.debug("BaseState received event %s, ignoring." % event_type)
  
  # called from outside
  def handle_parse(self, concept_key, parse):
    # standard queries
    if concept_key == "do-query-position":
      self.do_status_query_position(self.dm, parse)
    elif concept_key == "do-query-status":
      self.do_status_query_status(self.dm, parse)
    elif concept_key == "do-query-playtime":
      self.do_status_query_playtime(self.dm, parse)
    elif concept_key == "do-query-fuel":
      self.do_status_query_fuel(self.dm, parse)
    elif concept_key == "do-query-ammo":
      self.do_status_query_ammo(self.dm, parse)
    elif concept_key == "do-query-altitude":
      self.do_status_query_altitude(self.dm, parse)
    elif concept_key == "do-query-heading":
      self.do_status_query_heading(self.dm, parse)

    elif concept_key == "do-greeting":
      self.do_standard_greeting(self.dm, parse)
    
    elif concept_key == "abort-code-request":
      # call out into action module code
      do_abort_code_request(self.dm, parse)
    
    elif concept_key == "loud-and-clear":
      self.dm.say("roger")  # was "I have you loud and clear too"
    elif concept_key == "weak-but-readable":
      self.dm.say("roger")  # was "I have you loud and clear"
    
    elif concept_key == "cleared-hot":
      self.dm.debug("if they say 'you are cleared hot' in a bad context, what should we do?")
      # self.dm.say("you are coming in weak and unreadable, say again")
      self.dm.say("negative, I am not engaging a target at this time")
    
    elif concept_key == "do-roger" or concept_key == "do-copy-ack":
      pass

    elif concept_key == "do-rtb":
      self.dm.fly_to_ip("rtb")
      self.dm.say("roger, I am returning to base")

    elif concept_key == "continue":
      if self.dm.nine_line.is_pending_acknowledge():
        do_nine_line_readback(self.dm, parse)
      else:
        self.dm.say_again()
    
    else:
      # unknown concept
      self.dm.debug("Concept key %s unknown, failing to handle" % concept_key)
      self.dm.say("you are coming in weak and unreadable, say again")
  
  # called from inside by children
  def base_idle_behavior(self):
    """This is called in response to a conversation-idle event.  Update the 
    idle count, and if it's been idle too long, do the "radio check" behavior.
    If the radio check is done, return True; otherwise, return False, indicating
    the state object should go forward with any custom behavior.
    """
    
    self.dm.debug("Conversation gone idle.")
    self.data.increment_idle_count()
    if self.data.idle_count >= BaseState.CONST_IDLE_MAX:
      self.do_idle_radio_check(self.dm)
      #self.data.asked_radio_check = True
      self.machine.set_state(RADIO_CHECK)
      return True
    else:
      return False
  
  def do_idle_radio_check(self, dm):
    dm.say("%s, radio check" % dm.pilot_full_callsign)
  
  def do_status_query_position(self, dm, parse):
    """Speak the pilot's current position relative to IP Bravo."""
    pos_tuple = do_status_query_position_helper(dm)
    if pos_tuple is None:
      dm.say("sorry, cannot retrieve pilot position")
    else:
      (distance, direction) = pos_tuple
      if distance <= 0.5:
        dm.say("%s is currently established at IP Bravo" % dm.pilot_callsign)
      else:
        dm.say("%s is currently %s clicks %s of IP Bravo" % (dm.pilot_callsign, distance, direction))
      # FIXME: we have heading information, could also say that 
  
  def do_status_query_status(self, dm, parse):
    """Speak the pilot's status (inbound to target, egressing, &c.)"""
    status = dm.pilot_model.get_status()
    if status is None:
      dm.say("sorry, cannot retrieve pilot status.")
    else:
      if status == "inbound to ip":
        dm.say("I am inbound to I.P.")
      elif status == "holding at ip":
        dm.say("I am holding at I.P.")
      elif status == "rtb":
        dm.say("I am returning to base")
      else:
        dm.say("I am %s" % status)

  def do_status_query_playtime(self, dm, parse):
    playtime = self.get_playtime()
    dm.say_random([1, ["about %s mikes", playtime]],
                  [1, ["%s mikes", playtime]],
                  [1, ["playtime is %s mikes", playtime]],
                  [1, ["playtime is about %s mikes", playtime]])
  
  def do_status_query_fuel(self, dm, parse):
    fuel = self.dm.pilot_model.get_fuel()
    if fuel is None:
      dm.say("sorry, cannot retrieve fuel status.")
    else:
      # round fuel to 100's, since the speech system will say that like a normal human being
      fuel = max(int(fuel/100)*100, 0)   # don't speak negative numbers...
      dm.say("fuel is %d pounds" % fuel)

  def do_status_query_altitude(self, dm, parse):
    pose = self.dm.pilot_model.get_pilot_pose()
    if pose is None:
      dm.say("sorry, cannot retrieve altitude")
    else:
      altitude = pose[1][2]
      # as of 4/23, this looks like "-6101.003".  massage a little bit.
      altitude = abs(altitude)
      # this is in meters, so convert to feet
      alt_feet = altitude * 3.2808399
      alt_feet = int(alt_feet/1000)
      dm.say("altitude is %d thousand" % alt_feet)

  def do_status_query_heading(self, dm, parse):
    pose = self.dm.pilot_model.get_pilot_pose()
    if pose is None:
      dm.say("sorry, cannot retrieve heading")
    else:
      heading = pose[2]
      # this comes in as a value from {0-180,-180-0}.
      # jtac binocs say 0-360.  massaging this too.
      if heading < 0:
        heading += 360
      dm.say("heading is %d degrees" % heading)

  def do_status_query_ammo(self, dm, parse):
    # FIXME: instead of asking sim, just say something verbatim for now
    # currently, ammo would just send back "100".  presumably percentage.
    # ammo = dm.pilot_model.get_ammo()
    # if ammo is None:
    #   dm.say("sorry, cannot retrieve ammo status.")
    # else:
    #   dm.say("ammo is %s" % ammo)
    
    # dm.say("I have two by maverick, two by mark 82s, and gun")
    # FIXME: "eighty twos" the only way to pronounce 82s?  this is a double-fixme!  attempted lexicon fix failed for now.
    dm.say("I have two by maverick, two by mark eighty twos, and gun")
  
  def do_authentication_response(self, dm, parse):
    # this is the uniform catch all for all states apart from the
    # check-in state.  if they've gotten past check-in, they should
    # absolutely be authenticated.
    if dm.jtac_is_authenticated:
      dm.say("you have already authenticated")
    else:
      dm.debug("BaseState authentication: should be impossible?")
  
  def get_playtime(self):
    playtime = self.dm.pilot_model.get_playtime()
    # Then round off to nearest 5 minutes.
    playtime = int(round(playtime / 5) * 5)
    # FIXME: we don't do anything when low yet, but don't go negative!
    return max(playtime, 0)

  def get_fuel(self):
    fuel = self.dm.pilot_model.get_fuel()
    # FIXME: we don't do anything when low yet, but don't go negative!
    return max(fuel, 0)

  def do_standard_greeting(self, dm, parse):
    # 5/3: Adding to attempt to handle a phrase Yuri revers to in times of stress.
    # Not completely sure this is a good idea.
    dm.say("copy")
    

class CheckInState(BaseState):
  """This state controls the behavior when in the check-in mode."""
  
  def __init__(self, machine):
    BaseState.__init__(self, machine)
  
  
  def name(self):
    return "Check-In State"
  
  def enter(self):
    """Overrides base enter() method to do custom event handling on startup.
    The nine-line event may be sent immediately when the Dialog Manager connects
    to jtacStrike, and if so, we want to pay attention to it.  No other events
    or language actions are important at this time.
    """
    
    # check DM for queued events, parses
    qp = self.machine.get_queued_parses()
    if len(qp) > 0:
      self.dm.debug("CheckInState: sees %d queued parses on entry, how did that happen?" % len(qp))
    
    qe = self.machine.get_queued_events()
    if len(qe) > 0:
      # the only one we care about is the nine line
      # items in event list are (event_type, event_obj) tuples
      # go *backwards* through list?  just in case they sent the nine line twice?
      qe.reverse()
      handled_nine_line = False
      for (event_type, event_obj) in qe:
        if event_type == "nine-line" and handled_nine_line == False:
          self.dm.debug("CheckIn handling queued nine line event")
          handled_nine_line = True
          self.handle_event(event_type, event_obj) 


  def handle_event(self, event_type, event_obj):
    if event_type == "conversation-idle":
      if self.dm.jtac_is_authenticated == False:
        # ignore any default idle behavior if we're in check-in
        event_request_auth(self.dm, event_obj)
      else:
        # see if base state handles it specially; otherwise, tackle here
        if BaseState.base_idle_behavior(self) == False:
          event_offer_nine_line(self.dm)
    
    elif event_type == "nine-line":
      if self.dm.jtac_is_authenticated:
        # call function out in action module
        handle_nine_line_post_event(self.dm, event_obj)
      else:
        # if not authenticated, save event data for later, and process once we're able
        # more interesting would be following BOF's lead and incorporating nine-line in check-in greeting.
        self.data.saved_nine_line = event_obj

    else:
      # print "** CheckInState, passing on event: %s" % event_type
      BaseState.handle_event(self, event_type, event_obj)
  
  def handle_parse(self, concept_key, parse):
    # current DM makes sure that any language is created with the auth
    # request.  shouldn't need to worry about *that* here.
    #
    # FIXME: is abort code acknowledgement required?  no, but it's good practice. what does that mean for us?
    
    if concept_key == "go-ahead":
      event_offer_nine_line(self.dm)
    
    elif concept_key == "go-talk-on":
      self.dm.say("negative, give me the nine line first")

    elif concept_key == 'do_id_bogey_call':
      do_bogey_id(self.dm, parse)
    
    elif concept_key == "do-authentication-response":
      self.do_authentication_response(self.dm, parse)
      # did authentication work?  if so, and we've got saved nine-line, use it.
      if self.data.saved_nine_line is not None and self.dm.jtac_is_authenticated:
        handle_nine_line_post_event(self.dm, self.data.saved_nine_line)
        self.data.saved_nine_line = None
        
    else:
      # print "** CheckInState, passing on language: %s" % concept_key
      BaseState.handle_parse(self, concept_key, parse)

  
  def do_authentication_response(self, dm, parse):
    if dm.jtac_is_authenticated:
      dm.say("you have already authenticated")
    else:
      codeword = parse.slot_value("codeword")
      codeletter = dm.kb.slot_value(codeword, "letter")
      
      if codeletter.op == dm.authentication_response_code:
        dm.jtac_is_authenticated = True
        self.dm.set_parser_mode(dialogmanager.DialogManager.CONCEPTUAL_PARSER)

        # get position from pilot model
        pos_tuple = do_status_query_position_helper(dm)
        if pos_tuple is None or pos_tuple[0] <= 0.5:
          dm.say("%s is checking in as-fragged, currently established at IP Bravo",
                 dm.pilot_callsign)
        else:
          (distance, direction) = pos_tuple
          dm.say("%s is checking in as-fragged, current position %s clicks %s of IP Bravo.",
                 dm.pilot_callsign, distance, direction)
        # query pilot model for playtime
        playtime = self.get_playtime()
        dm.say("playtime is %s mikes", playtime)
      else:
        event_request_auth(dm, None)


class NineLineState(BaseState):
  """This state controls the behavior when in the nine-line phase."""
  
  def __init_(self, machine):
    BaseState.__init__(self, machine)

  def name(self):
    return "Nine-Line State"

  def enter(self):
    self.data.requested_nine_line = False

  def handle_event(self, event_type, event_obj):
    if event_type == "conversation-idle":
      if BaseState.base_idle_behavior(self) == False:
        # not handled by base class, so what's the custom behavior for idling?
        event_offer_nine_line(self.dm)
    
    elif event_type == "nine-line":
      # call function out in action module
      handle_nine_line_post_event(self.dm, event_obj)
      
    else:
      # print "** NineLineState, passing on event: %s" % event_type
      BaseState.handle_event(self, event_type, event_obj)

  def handle_parse(self, concept_key, parse):
    if concept_key == "go-ahead":
      self.__maybe_goto_talkon(True)
    
    elif concept_key == "go-talk-on":
      self.__maybe_goto_talkon(False)
    
    else:
      # print "** NineLineState, passing on language: %s" % concept_key
      BaseState.handle_parse(self, concept_key, parse)
  
  def __maybe_goto_talkon(self, from_go_ahead = False):
    """This is called both by "go ahead", and "say when ready for talk-on" language."""
    if self.dm.nine_line.is_complete():
      if from_go_ahead == True:
        self.dm.say("copy, let's continue with the talk-on")
      else:
        self.dm.say("go with talk-on")
      self.machine.set_state(TALK_ON)
    elif self.dm.nine_line.is_pending_acknowledge() and from_go_ahead == True:
      do_nine_line_readback(self.dm, None)
    else:
      if self.dm.nine_line.has_data() == True:
        # FIXME: this probably isn't right phrasing.
        self.dm.say("negative, acknowledge nine line first")
      event_offer_nine_line(self.dm, from_go_ahead)


class TalkOnState(BaseState):
  """State for managing talk-on behavior."""
  
  def __init__(self, machine):
    BaseState.__init__(self, machine)
  
  def name(self):
    return "Talk-On State"

  def enter(self):
    """Override base enter() method to set parser to CP mode."""
    self.dm.set_parser_mode(dialogmanager.DialogManager.CONCEPTUAL_PARSER)

  def handle_event(self, event_type, event_obj):
    # print "** TalkOnState, passing on event: %s" % event_type
    BaseState.handle_event(self, event_type, event_obj)
  
  def handle_parse(self, concept_key, parse):
    if concept_key == "go-ahead":
      # FIXME:
      self.dm.debug("TalkOn: if in talk on, target is not known, so what to do?")
    
    elif concept_key == "go-talk-on":
      # already in talk-on, but this is OK, can happen through valid paths.  accept.
      # FIXME: make same language instance/method as used in nine-line
      self.dm.say("go with talk-on")
    
    else:
      # print "** TalkOnState, passing on language: %s" % concept_key
      BaseState.handle_parse(self, concept_key, parse)


class BogeyIDState(BaseState):
  """State for doing an ID of a bogey as requested by JSTARS."""
  def __init__(self, machine):
    BaseState.__init__(self, machine)
    self.target_num = 0

  def name(self):
    return "Bogey ID state"

  def enter(self):
    pass

  def handle_event(self, event_type, event_obj):
    print "BogeyIDState event %s" % (event_obj,)
    if event_type == "bogey-declare" and event_obj['number'] == self.target_num:
      do_bogey_declare(self.dm, event_obj['target'])
    else:
      # print "** RunInState, passing on event: %s" % event_type
      BaseState.handle_event(self, event_type, event_obj)

  def handle_parse(self, concept_key, parse):
    if concept_key == 'do_id_bogey_call':
      do_bogey_id(self.dm, parse)
    elif concept_key == 'do_kill_target_call':
      do_kill_target(self.dm, parse)
    else:
      BaseState.handle_parse(self, concept_key, parse)


class BullseyeRunInState(BaseState):
  """State for managing run-in behavior."""
  
  def __init__(self, machine):
    BaseState.__init__(self, machine)

  def name(self):
    return "Bullseye Run-In State"

  def enter(self):
    self.last_eta = None
    self.already_got_continue = False
  
  def handle_event(self, event_type, event_obj):
    if event_type == "attack-run-complete":
      self.handle_attack_run_complete_event(self.dm, event_obj)
    
    elif event_type == "eta":
      self.handle_eta_event(self.dm, event_obj)
      
    else:
      # print "** RunInState, passing on event: %s" % event_type
      BaseState.handle_event(self, event_type, event_obj)
  
  def handle_parse(self, concept_key, parse):
    if concept_key == "go-ahead":
      # FIXME:
      self.dm.debug("RunIn: should say 'confirm target is still good'")
    
    elif concept_key == "cleared-hot":
      # FIXME: require this before engaging target!  this is mandatory in our simulation.
      self.dm.say("copy, cleared hot.")

    elif concept_key == "continue":
      if self.already_got_continue:
        return
      if not self.last_eta or self.last_eta > 20:
        self.dm.say("say status of %s", self.target)
        self.already_got_continue = True
    else:
      # print "** RunInState, passing on language: %s" % concept_key
      BaseState.handle_parse(self, concept_key, parse)

  def handle_attack_run_complete_event(self, dm, event):
    # FIXME: possible to be in radio check state and have attack run complete?
    #        not with current timing setup, but...
    
    # 2/22 mrh: decided (based on limited samples) that unit of measure & anchor point should
    #           reset between runs, although the jtac can explicitly reuse the old ones.
    if dm.on_attack_run:
      dm.on_attack_run = False
      dm.nine_line.reset()
      dm.reset_unit_of_measure()
      dm.reset_anchor_point()
      self.data.last_look_loc = None
      dm.say("Rifle!")
      time.sleep(1)
      dm.fly_to_ip("egressing")
      # return to nine-line state
      dm.state_machine.set_state(CHECK_IN)
    else:
      dm.debug("if we're not on the attack run, why are we in this state?")

  def handle_eta_event(self, dm, event):
    # FIXME: wonder what to do if in radio check state and ETA comes in?
    # automatically abort?
    
    eta_time = event["eta"]
    self.last_eta = eta_time
    if eta_time < 11:
      pilot_coords = event['pilot-pose'][1]
      pilot_coords = pilot_coords[0:2] + [0]
      target_coords = event['target-coords']
      target_coords = target_coords[0:2] + [0]
      approach_vector = vector_subtract(pilot_coords, target_coords)
      approach_direction = classify_vector_as_cardinal_direction(dm, approach_vector)
      dm.say("%s is in hot from the %s" % (dm.pilot_full_callsign, approach_direction))
      # dm.conv_state.set_state("run-in-eta-given")
      dm.state_machine.data.eta_given = True
    else:
      approx_eta_time = int((eta_time + 4.0) / 10.0) * 10
      dm.say("%s is %s seconds out" % (dm.pilot_callsign, approx_eta_time))
      # dm.conv_state.set_state("run-in-hot")
      dm.state_machine.data.run_in_hot = True





class RunInState(BaseState):
  """State for managing run-in behavior."""
  
  def __init__(self, machine):
    BaseState.__init__(self, machine)

  def name(self):
    return "Run-In State"

  def enter(self):
    self.last_eta = None
    self.already_got_continue = False
  
  def handle_event(self, event_type, event_obj):
    if event_type == "attack-run-complete":
      self.handle_attack_run_complete_event(self.dm, event_obj)
    
    elif event_type == "eta":
      self.handle_eta_event(self.dm, event_obj)
      
    else:
      # print "** RunInState, passing on event: %s" % event_type
      BaseState.handle_event(self, event_type, event_obj)
  
  def handle_parse(self, concept_key, parse):
    if concept_key == "go-ahead":
      # FIXME:
      self.dm.debug("RunIn: should say 'confirm target is still good'")
    
    elif concept_key == "cleared-hot":
      # FIXME: require this before engaging target!  this is mandatory in our simulation.
      self.dm.say("copy, cleared hot.")

    elif concept_key == "continue":
      if self.already_got_continue:
        return
      if not self.last_eta or self.last_eta > 20:
        self.dm.say("say status of %s", self.dm.nine_line.get_line("target description"))
        self.already_got_continue = True
    else:
      # print "** RunInState, passing on language: %s" % concept_key
      BaseState.handle_parse(self, concept_key, parse)

  def handle_attack_run_complete_event(self, dm, event):
    # FIXME: possible to be in radio check state and have attack run complete?
    #        not with current timing setup, but...
    
    # 2/22 mrh: decided (based on limited samples) that unit of measure & anchor point should
    #           reset between runs, although the jtac can explicitly reuse the old ones.
    if dm.on_attack_run:
      dm.on_attack_run = False
      dm.nine_line.reset()
      dm.reset_unit_of_measure()
      dm.reset_anchor_point()
      self.data.last_look_loc = None
      dm.say("Rifle!")
      time.sleep(1)
      dm.fly_to_ip("egressing")
      # return to nine-line state
      dm.state_machine.set_state(NINE_LINE)
    else:
      dm.debug("if we're not on the attack run, why are we in this state?")

  def handle_eta_event(self, dm, event):
    # FIXME: wonder what to do if in radio check state and ETA comes in?
    # automatically abort?
    
    eta_time = event["eta"]
    self.last_eta = eta_time
    if eta_time < 11:
      pilot_coords = event['pilot-pose'][1]
      pilot_coords = pilot_coords[0:2] + [0]
      target_coords = event['target-coords']
      target_coords = target_coords[0:2] + [0]
      approach_vector = vector_subtract(pilot_coords, target_coords)
      approach_direction = classify_vector_as_cardinal_direction(dm, approach_vector)
      dm.say("%s is in hot from the %s" % (dm.pilot_full_callsign, approach_direction))
      # dm.conv_state.set_state("run-in-eta-given")
      dm.state_machine.data.eta_given = True
    else:
      approx_eta_time = int((eta_time + 4.0) / 10.0) * 10
      dm.say("%s is %s seconds out" % (dm.pilot_callsign, approx_eta_time))
      # dm.conv_state.set_state("run-in-hot")
      dm.state_machine.data.run_in_hot = True


class RadioCheckState(BaseState):
  """This state controls the behavior after the pilot has asked for a radio
  check.  JTAC must acknowledge radio check before further dialog can progress.
  Return to previous state when successfully exiting state.
  """
  
  def __init__(self, machine):
    BaseState.__init__(self, machine)
  
  def name(self):
    return "Radio Check State"
  
  def handle_event(self, event_type, event_obj):
    if event_type == "conversation-idle":
      self.dm.debug("Repeating radio check request.")
      self.do_idle_radio_check(self.dm)
    
    else:
      # not sure what to do with other events, passing them on
      BaseState.handle_event(self, event_type, event_obj)
  
  def handle_parse(self, concept_key, parse):
    """ Only two utterances are acceptable: loud-and-clear, or 
    weak-but-readable.  Everything else needs a nag response from 
    the pilot.
    """
    
    if concept_key == "loud-and-clear":
      self.dm.say("I have you loud and clear, too.")
      self.machine.set_state(self.machine.get_previous_state())
    
    elif concept_key == "weak-but-readable":
      self.dm.say("roger.  Consider changing frequencies.") # FIXME: better language?
      self.machine.set_state(self.machine.get_previous_state())
    
    else:
      # instead of custom language, for now just repeat basic request
      self.dm.debug("Ignoring user until radio check answered (%s)" % concept_key)
      self.do_idle_radio_check(self.dm)




# Urban ops

def do_assert_urban_layout(dm, parse):
  layout = parse.slot_value("codeword")
  if dm.kb.isa(logic.expr(layout), logic.expr("i-seattle-codeword")):
    dm.say("copy, I have the %s layout", layout)
  else:
    dm.say("negative, I do not have that layout.")
    

def building_designator_string(dm, building):
  letter = dm.generate("%s", dm.kb.slot_path_value(building, "designator", "letter", "letter"))
  number = dm.generate("%s", dm.kb.slot_path_value(building, "designator", "number"))
  s = "%s%s" % (letter, number)
  return s.upper()

def resolve_building_reference(dm, objdesc):
  building_designator = building_designator_string(dm, objdesc)
  # Now find an object in memory with that designator.
  d = logic.Description("c-building", {"objid": building_designator})
  return d.find_instances(dm.kb)


def all_subclasses(x):
  all_subclasses2([x])

def all_subclasses2(classes):
  if len(classes) > 0:
    c = classes[0]
    rest = classes[1:]
    print c
    all_subclasses2(c.__subclasses__() + rest)




def bullseye_vector_position(dm, bullseye_pos_f, bearing, range, fraction=1.0):
  origin = position_frame_to_vector(dm.kb, bullseye_pos_f)

  angle_deg = 90 - bearing
  angle_rads = angle_deg * math.pi / 180.0
  
  range_m = range * 1800.0
  range_m = range_m * fraction

  [vx, vy] = [range_m * math.sin(angle_rads),
              range_m * math.cos(angle_rads)]
  pos = [vx + origin[0], vy + origin[1], origin[2]]
  return pos
  
  
def fly_to_bullseye(dm, parse, fraction=1.0):
  # Slew vision, fly to bullseye.
  bullseye_pos = dm.kb.slot_value('i-Radio-Tower', 'position')
  bearing = number_frame_to_value(dm.kb, parse.slot_value('bearing').slot_value('angle'))
  distance = number_frame_to_value(dm.kb, parse.slot_value('distance'))
  pos = bullseye_vector_position(dm, bullseye_pos, bearing, distance, fraction)
  dm.pilot_model.fly_to(pos, type="inbound to ip")
  pos = bullseye_vector_position(dm, bullseye_pos, bearing, distance)
  dm.pilot_model.look_at(pos)
  return pos

def do_bogey_id(dm, parse):
  dm.say("wilco")
  dm.state_machine.set_state(BOGEY_ID)
  pos = fly_to_bullseye(dm, parse, 0.5)
  pilot_pose = dm.pilot_model.get_pilot_pose()
  pilot_pos = pilot_pose[1]
  dist = utils.distance((pos[0], pos[1]), (pilot_pos[0], pilot_pos[1]))
  target = parse.slot_value('target')
  type = dm.kb.slot_value(logic.expr(target), 'type')
  BOGEY_ID.target = target
  BOGEY_ID.target_num += 1
  BOGEY_ID.target_pos = pos
  if dm.pilot_model.can_see_object_type(type.op, None):
    props = {}
    props['category'] = type.op
    print props
    target_locations = dm.pilot_model.get_object_location(props)
    print "loca %s" % (target_locations,)
    if target_locations and len(target_locations) == 1:
      target_pos = target_locations[0]
      dm.pilot_model.look_at(target_pos)
      BOGEY_ID.target_pos = target_pos
    print dist
    if dist > 4000:
      dm.say("tally %s, unable I.D., maneuvering for a closer look", target)
      utils.Timer(10, dm.pilot_model.handle_event, args=[{"type": "bogey-declare",
                                                          "target": target,
                                                          "number": BOGEY_ID.target_num}]).start()
    else:
      do_bogey_declare(dm, target)
  else:
    say_negative_contact(dm, target)

def do_bogey_declare(dm, target):
  target = logic.expr(target)
  entities = dm.pilot_model.get_all()
  found_target = False
  for e in entities:
    e['class'] = descriptor_class(dm, e)
    if dm.kb.isa(e['class'], target):
      found_target = e
  if found_target:
    dm.say("bogey is %s, declare.", found_target['class'])
  
    
def do_kill_target(dm, parse):
  target = parse.slot_value('target')
  dm.say("copy kill")
  type = dm.kb.slot_value(target, "type").op
  subtype = dm.kb.slot_value(target, "subtype")
  props = {}

  if subtype == None:
    props["category"] == type
  else:
    props["type"] = subtype.op
  target_locations = dm.pilot_model.get_object_location(props)
  if len(target_locations) == 1:
    target_location = target_locations[0]
    dm.pilot_model.fly_to(target_location, type="inbound to target")
    dm.pilot_model.look_at(target_location)
    dm.on_attack_run = True
    # dm.conv_state.set_state("run-in-begin")
    dm.state_machine.set_state(BULLSEYE_RUN_IN)
    BULLSEYE_RUN_IN.target = target
  else:
    dm.debug("bad target locations for target %s of type '%s': %s; Cannot begin attack run" % (target, type, target_locations))
