import socket
import string
import struct
import threading
import time
import xml.dom.minidom
from xml.sax import saxutils

from hml.dialog import utils
from hml.dialog import logic


MN_NAMESPACE = "http://www.energid.com/namespace/mn"
PQR_NAMESPACE = "http://www.energid.com/namespace/pqr"

EVENT_PORT = 5592


def get_node_text(node):
  rc = ""
  for child in node.childNodes:
    if child.nodeType == child.TEXT_NODE:
      rc = rc + child.data
  return rc


class PilotModel:
  """A model of a pilot.  A local interface to a remote pilot model
  connected via TCP; Sends commands and queries and processes replies.
  """

  COMMAND_PORT = 5590
  QUERY_PORT = 5591

  PILOT_POSE_QUERY = """
<pilotPoseQuery>
  <queryId>0</queryId>
</pilotPoseQuery>
"""

  STATUS_QUERY = """
<statusQuery>
  <queryId>0</queryId>
</statusQuery>
"""

  PLAYTIME_QUERY = """
<playtimeQuery>
  <queryId>0</queryId>
</playtimeQuery>
"""

  FUEL_QUERY = """
<fuelQuery>
  <queryId>0</queryId>
</fuelQuery>
"""

  DETAIL_QUERY = """
<detailStringIdQuery>
  <queryId>0</queryId>
</detailStringIdQuery>
"""

  ALL_QUERY = """
<allQuery>
  <queryId>0</queryId>
</allQuery>
"""

  EQUALITY_OBSERVATION_QUERY = """
<booleanEqualityObservationQuery>
  <equalityConditions>
    <mn:integerMap xmlns:mn="http://www.energid.com/namespace/mn">%s    </mn:integerMap>
    <mn:realMap xmlns:mn="http://www.energid.com/namespace/mn">%s    </mn:realMap>
    <mn:stringMap xmlns:mn="http://www.energid.com/namespace/mn">%s    </mn:stringMap>
  </equalityConditions>
  <queryId>0</queryId>
</booleanEqualityObservationQuery>
"""

  AMMO_QUERY = """
<ammoQuery>
  <queryId>0</queryId>
</ammoQuery>
"""

  PILOT_LOOK_COMMAND = """
<lookDirectionCommand mode="$mode">
  <commandId>0</commandId>
  <inWorldCoordinates>1</inWorldCoordinates>
  <lookDirection x="$x" y="$y" z="$z"/>
</lookDirectionCommand>
"""

  PILOT_ZOOM_COMMAND = """
<?xml version="1.0" encoding="ISO-8859-1"?>
<zoomCommand>
 <commandId>0</commandId>
 <zoom>$zoom</zoom>
</zoomCommand>
"""

  # 4/20/07 mrh: changing "pointType" to "status", in line with status
  # query changes
  PILOT_GUIDANCE_COMMAND = """
 <guidanceCommand mode="pursuit" status="$type">
  <commandId>0</commandId>
  <guidance x="$x" y="$y" z="$z"/>
  <inWorldCoordinates>1</inWorldCoordinates>
 </guidanceCommand>
"""

  ATTACK_RUN_COMMAND = """
 <attackRunCommand>
  <approachOffsetAngle>80</approachOffsetAngle>
  <commandId>0</commandId>
  <releaseDistance>1000</releaseDistance>
  <runInAltitude>250</runInAltitude>
  <runInDistance>5000</runInDistance>
  <setUpAltitude>750</setUpAltitude>
  <targetLocation x="$x" y="$y" z="$z"/>
 </attackRunCommand>
"""

  DETAIL_EQUALITY_OBSERVATION_QUERY = """
 <detailEqualityObservationQuery>
  <equalityConditions>
    <mn:integerMap xmlns:mn="http://www.energid.com/namespace/mn">%s    </mn:integerMap>
    <mn:realMap xmlns:mn="http://www.energid.com/namespace/mn">%s    </mn:realMap>
    <mn:stringMap xmlns:mn="http://www.energid.com/namespace/mn">%s    </mn:stringMap>
  </equalityConditions>
  <includeAppearanceDescriptions>0</includeAppearanceDescriptions>
  <includeEntityDescriptions>0</includeEntityDescriptions>
  <includeLocationDescriptions>0</includeLocationDescriptions>
  <queryId>5</queryId>
 </detailEqualityObservationQuery>
"""

  TESTING_NINE_LINE_COMMAND = """
<nineLineCommand>
  <commandId>0</commandId>
</nineLineCommand>
"""

  def __init__(self, host, event_client=None, log_file="comms.log"):
    self.host = host
    self.log_file = log_file
    self.query_connection = None
    self.command_connection = None
    self.event_connection = None
    self.event_client = event_client
    self.default_retry_delay = 0.5   # 5/5/07 mrh: making shorter
    self.default_retry_count = 5
    self.last_look = None
    self.event_listener = None

  def connect(self):
    """Connects to the remote pilot model."""
    self.query_connection = EcConnection(self.host, self.QUERY_PORT)
    self.command_connection = EcConnection(self.host, self.COMMAND_PORT)
    self.event_listener = EventListener(self.host, self)
    self.query_connection.connect()
    self.command_connection.connect()
    self.event_listener.start()
    print "Connected to pilot model at %s" % (self.host,)

  def is_connected(self):
    return self.query_connection != None

  def disconnect(self):
    if self.query_connection != None:
      self.query_connection.disconnect()
      self.command_connection.disconnect()
      self.event_listener.stop()
      self.query_connection = None
      self.command_connection = None
      self.event_listener = None

  def send_command(self, command):
    self.log("==> COMMAND", command)
    utils.log('<pilotmodel-command>%s</pilotmodel-command>' % (
      saxutils.escape(log_summary(command)),))
    self.command_connection.send_message(command)

  def send_query(self, query):
    self.log("==> QUERY", query)
    utils.log('<pilotmodel-query>%s</pilotmodel-query>' % (
      saxutils.escape(log_summary(query)),))
    self.query_connection.send_message(query)
    (unused_msg_type, reply) = self.query_connection.read_message()
    self.log("<== REPLY", reply)
    utils.log('<pilotmodel-reply>%s</pilotmodel-reply>' % (
      saxutils.escape(log_summary(reply))))
    return reply

  def log(self, msg_type, message):
    if self.log_file != None:
      utils.slog(self.log_file, msg_type, message)

  def wrap_query(self, query):
    return """<?xml version="1.0" encoding="ISO-8859-1"?>
<pilotModelQueryContainer xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://www.energid.com/namespace/pqr
  EcPilotModelQueryContainer.pqr.xsd" xmlns="http://www.energid.com/namespace/pqr" version="1.0.0">""" + query + """
  </pilotModelQueryContainer>
  """

  def wrap_command(self, command):
    return """<?xml version="1.0" encoding="ISO-8859-1"?>
<pilotModelCommandContainer xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://www.energid.com/namespace/pmc
  EcPilotModelCommandContainer.pmc.xsd" xmlns="http://www.energid.com/namespace/pmc" version="1.0.0">""" + command + """
  </pilotModelCommandContainer>
  """

  def query_with_auto_retry2(self, querier):
    while querier.query_again():
      result = querier.query()
      if result:
        return result
    return False

  def query_with_auto_retry(self, query, retry_delay=None, retry_count=None):
    if retry_delay == None:
      retry_delay = self.default_retry_delay
    if retry_count == None:
      retry_count = self.default_retry_count

    for unused_i in range(0, retry_count + 1):
      result = query()
      if result:
        return result
      time.sleep(retry_delay)
    return False

  def get_pilot_pose(self):
    """Returns the pilot's current pose: an orientation vector and a
    position vector, and the heading in degrees.
    """
    query = self.wrap_query(self.PILOT_POSE_QUERY)
    reply = self.send_query(query)
    dom = xml.dom.minidom.parseString(reply)
    return parse_pilot_pose(dom)

  def get_ammo(self):
    """Returns information about the quantity of remaining ordnance."""
    try:
      return int(self.__do_simple_query(self.AMMO_QUERY, "ammoCount"))
    except:
      print "Error retrieving ammo; old version of jtacStrike?"
      return 100 # default

  def get_status(self):
    """Returns information about status (inbound to IP, egressing, &c.)"""
    try:
      return self.__do_simple_query(self.STATUS_QUERY, "status")
    except:
      print "Error retrieving status; old version of jtacStrike?"
      return "inbound to ip"

  def get_playtime(self):
    """Returns playtime from the simulator (instead of making it up in the
    DialogManager).  Value is a float on return.
    """
    try:
      return float(self.__do_simple_query(self.PLAYTIME_QUERY, "playtime"))
    except:
      print "Error retrieving playtime; old version of jtacStrike?"
      return 30  # default value

  def get_fuel(self):
    """Return fuel from the sim, which is probably just calculating
    based on playtime."""
    return float(self.__do_simple_query(self.FUEL_QUERY, "fuelPounds"))

  def __do_simple_query(self, query_xml, pqr_element):
    """This method factors out even more commonalities to the simpler
    simulator queries.  Post-processing can happen in the calling function.
    """
    query = self.wrap_query(query_xml)
    reply = self.send_query(query)
    dom = xml.dom.minidom.parseString(reply)
    result = dom.getElementsByTagNameNS(PQR_NAMESPACE, pqr_element)[0]
    return get_node_text(result)

  def get_object_details(self, string_props):
    def do_query():
      response = self.get_detail_equality_observation({}, {}, string_props)
      dom = xml.dom.minidom.parseString(response)
      descriptor_vector = dom.getElementsByTagNameNS(
        PQR_NAMESPACE, "entityDescriptorVector")[0]
      result = self.parse_descriptor_vector(descriptor_vector)
      if len(result) == 0:
        return False
      else:
        return result
    return self.query_with_auto_retry(lambda: do_query())

  def get_object_location(self, string_props):
    def do_query():
      response = self.get_detail_equality_observation({}, {}, string_props)
      dom = xml.dom.minidom.parseString(response)
      location_vector = dom.getElementsByTagNameNS(
        PQR_NAMESPACE, "entityLocationVector")[0]
      result = self.parse_location_vector(location_vector)
      if len(result) == 0:
        return False
      else:
        return result

    details = self.get_object_details(string_props)
    if details != False and len(details) == 1 and 'location' in details[0]:
      return [map(float, details[0]['location'].split(","))]
    else:
      return self.query_with_auto_retry(lambda: do_query())

  def parse_location_vector(self, node):
    def parse_element(element):
      x = float(element.getAttribute("x"))
      y = float(element.getAttribute("y"))
      z = float(element.getAttribute("z"))
      return [x, y, z]

    return map(parse_element, node.getElementsByTagNameNS(
      PQR_NAMESPACE, "element"))

  def parse_descriptor_vector(self, node):
    def parse_descriptor_element(element):
      def parse_mn_element(elementDict, element):
        key = str(get_node_text(element.getElementsByTagNameNS(
          MN_NAMESPACE, "key")[0]))
        value = str(get_node_text(element.getElementsByTagNameNS(
          MN_NAMESPACE, "value")[0]))
        elementDict[key] = value

      string_map = element.getElementsByTagNameNS(MN_NAMESPACE, "stringMap")[0]
      mn_elements = string_map.getElementsByTagNameNS(MN_NAMESPACE, "element")
      string_props = {}
      for mn_element in mn_elements:
        parse_mn_element(string_props, mn_element)
      return string_props
    return map(parse_descriptor_element,
               node.getElementsByTagNameNS(PQR_NAMESPACE, "element"))

  def parse_blob_vector(self, node):
    def parse_blob_element(element):
      blob = {}
      for child in element.childNodes:
        if child.nodeType == child.ELEMENT_NODE:
          name = str(child.localName)
          value = str(get_node_text(child))
          if len(value) == 0:
            blob[name] = None
          else:
            blob[name] = float(value)
      return blob
    return map(parse_blob_element,
               node.getElementsByTagNameNS(PQR_NAMESPACE, "element"))

  def can_see_object_id(self, object_id):
    """Checks whether the pilot can see the object with the specified
    ID (name)."""
    # 2/26/07 mrh: splitting do_query out into private helper fn.
    querier = VisionQueryRetryer(self, {"name": object_id})
    return self.query_with_auto_retry2(querier)

  def can_see_object_type(self, category, obj_type):
    # 2/26/07 mrh: splitting do_query out into private helper fn.
    if obj_type:
      prop_name = "type"
      prop_value = obj_type
    else:
      prop_name = "category"
      prop_value = category
    #if do_query(prop_name, prop_value):
    querier = VisionQueryRetryer(self, {prop_name: prop_value})
    return self.query_with_auto_retry2(querier)

  def can_see_object(self, props):
    """Given a set of property descriptions, returns whether or not
    the pilot can see a matching object.  Similar to other can_see_*
    methods."""
    return self.query_with_auto_retry(
      lambda: self.__can_see_query_helper(props))

  def __can_see_query_helper(self, string_properties):
    # was do_query inside can_see_* methods
    response = self.get_equality_observation({}, {}, string_properties)
    dom = xml.dom.minidom.parseString(response)
    boolean_node = dom.getElementsByTagNameNS(PQR_NAMESPACE, "booleanValue")[0]
    value = get_node_text(boolean_node)
    if value == '0':
      return False
    elif value == '1':
      return True
    else:
      print "Unexpected value returned by query: %s" % (repr(value),)
      assert False

  def get_details(self):
    query = self.wrap_query(self.DETAIL_QUERY)
    reply = self.send_query(query)
    return reply

  def get_all(self):
    query = self.wrap_query(self.ALL_QUERY)
    reply = self.send_query(query)
    dom = xml.dom.minidom.parseString(reply)
    descriptor_vector = dom.getElementsByTagNameNS(
      PQR_NAMESPACE, "entityDescriptorVector")[0]
    blob_vector = dom.getElementsByTagNameNS(
      PQR_NAMESPACE, "entityBlobVector")[0]
    location_vector = dom.getElementsByTagNameNS(
      PQR_NAMESPACE, "entityLocationVector")[0]
    descriptors = self.parse_descriptor_vector(descriptor_vector)
    blobs = self.parse_blob_vector(blob_vector)
    locations = self.parse_location_vector(location_vector)
    for i, e in enumerate(descriptors):
      descriptors[i]["blob"] = blobs[i]
      descriptors[i]["location"] = locations[i]
    descriptors.sort(key=lambda d: d['blob']['size'], reverse=True)
    return descriptors

  def look_direction(self, vector):
    [x, y, z] = vector
    c = string.Template(self.PILOT_LOOK_COMMAND)
    command = self.wrap_command(c.substitute(mode="relative", x=x, y=y, z=z))
    self.send_command(command)
    self.last_look = lambda: self.look_direction(vector)

  def zoom_view(self, zoom_factor):
    c = string.Template(self.PILOT_ZOOM_COMMAND)
    command = self.wrap_command(c.substitute(zoom=zoom_factor))
    self.send_command(command)
    if self.last_look:
      self.last_look()

  def look_at(self, target):
    [x, y, z] = target
    c = string.Template(self.PILOT_LOOK_COMMAND)
    command = self.wrap_command(c.substitute(mode="absolute", x=x, y=y, z=z))
    self.send_command(command)
    self.last_look = lambda: self.look_at(target)

  def fly_to(self, coords, type="inbound to ip"):
    # 4/20/07 mrh: changing to adjust to sim changes to
    # status/guidance commands
    # FIXME: change assertion here!  more types possible.
    assert type in ["inbound to ip", "inbound to target",
                    "egressing", "rtb"]
    [x, y, z] = coords
    if type == "inbound to target":
      c = string.Template(self.ATTACK_RUN_COMMAND)
      command = self.wrap_command(c.substitute(x=x, y=y, z=z))
    else:
      c = string.Template(self.PILOT_GUIDANCE_COMMAND)
      command = self.wrap_command(c.substitute(x=x, y=y, z=z, type=type))
    self.send_command(command)

  def make_element(self, key, value):
    return """      <mn:element>
        <mn:key>%s</mn:key>
        <mn:value>%s</mn:value>
      </mn:element>
""" % (key, value)

  def make_elements(self, properties):
    elements = "\n"
    for prop in properties:
      elements = elements + self.make_element(prop, properties[prop])
    return elements

  def get_equality_observation(self, integerProperties, realProperties,
                               stringProperties):
    query = self.EQUALITY_OBSERVATION_QUERY % (
      self.make_elements(integerProperties),
      self.make_elements(realProperties),
      self.make_elements(stringProperties))
    query = self.wrap_query(query)
    response = self.send_query(query)
    return response

  def get_detail_equality_observation(self, integerProperties, realProperties,
                                      stringProperties):
    query = self.DETAIL_EQUALITY_OBSERVATION_QUERY % (
      self.make_elements(integerProperties),
      self.make_elements(realProperties),
      self.make_elements(stringProperties))
    query = self.wrap_query(query)
    response = self.send_query(query)
    return response

  def handle_event(self, event):
    self.log("<== EVENT", event)
    if self.event_client != None:
      self.event_client.handle_event(event)
    else:
      print "Got event: %s" % (event,)

  def trigger_nine_line(self, unused_target=None):
    self.log("==> COMMAND: triggering nine line event", "")
    self.send_command(self.wrap_command(self.TESTING_NINE_LINE_COMMAND))


def parse_pilot_pose(pose_node):
  orientation = pose_node.getElementsByTagNameNS(
    MN_NAMESPACE, "orientation")[0]
  q0 = float(orientation.getAttribute("q0"))
  q1 = float(orientation.getAttribute("q1"))
  q2 = float(orientation.getAttribute("q2"))
  q3 = float(orientation.getAttribute("q3"))
  position = pose_node.getElementsByTagNameNS(MN_NAMESPACE, "translation")[0]
  x = float(position.getAttribute("x"))
  y = float(position.getAttribute("y"))
  z = float(position.getAttribute("z"))
  heading_node = pose_node.getElementsByTagName("headingDeg")
  heading = 0  # default
  if heading_node is None or len(heading_node) == 0:
    # this is acceptable for ETA event
    pass
  else:
    # why the int(float(...))? because python doesn't seem to go from
    # string-float to int in one step
    heading = int(float(get_node_text(heading_node[0])))
  return [[q0, q1, q2, q3], [x, y, z], heading]


class VisionQueryRetryer:
  def __init__(self, pilotmodel, string_properties):
    self.pilotmodel = pilotmodel
    self.string_properties = string_properties
    self.try_count = 0
    self.zoom = None
    self.max_tries = 6
    self.retry_delay = 2

  def next_zoom(self):
    retval = self.zoom
    if self.zoom == None:
      self.zoom = 4
    else:
      self.zoom = self.zoom * 2
    return retval

  def query_again(self):
    return self.try_count < self.max_tries

  def query(self):
    if not self.query_again():
      return False
    #print "Trying query again"
    self.try_count += 1
    zoom = self.next_zoom()
    if zoom:
      #print "Zooming to %s" % (zoom,)
      self.pilotmodel.zoom_view(zoom)
    if self.try_count > 1:
      time.sleep(self.retry_delay)
    response = self.pilotmodel.get_equality_observation(
      {}, {}, self.string_properties)
    dom = xml.dom.minidom.parseString(response)
    boolean_node = dom.getElementsByTagNameNS(PQR_NAMESPACE, "booleanValue")[0]
    value = get_node_text(boolean_node)
    if value == '0':
      return False
    elif value == '1':
      return True
    else:
      print "Unexpected value returned by query: %s" % (repr(value),)
      assert False


class EcConnection:
  """A TCP connection with length-prefixed messages."""
  def __init__(self, host, port):
    self.host = host
    self.port = port
    self.rawsocket = None
    self.socket = None

  def connect(self):
    """Opens the connection."""
    self.rawsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.rawsocket.connect((self.host, self.port))
    self.socket = self.rawsocket.makefile()

  def disconnect(self):
    if self.socket != None:
      self.socket.close()
      self.socket = None
      self.rawsocket = None

  def send_message(self, message):
    """Sends a message."""
    id_buf = struct.pack("!L", 0)
    length = struct.pack("!L", len(message))
    self.rawsocket.send(id_buf + length)
    self.socket.write(message)
    self.socket.flush()

  def read_message(self):
    """Receives a message. Returns a tuple consisting of the message
    ID and the message body.
    """
    header = self.rawsocket.recv(8)
    if len(header) == 0:
      raise Exception("Remote pilot model disconnected.")
    if len(header) != 8:
      raise ValueError('Expecting 8 byte header, got %s bytes.' % (
        len(header),))
    msg_id = struct.unpack("!L", header[0:4])[0]
    length = struct.unpack("!L", header[4:])[0]
    message = ""
    num_bytes_to_read = length
    while num_bytes_to_read > 0:
      data = self.rawsocket.recv(min(1024, num_bytes_to_read))
      if not data:
        break
      message = message + data
      num_bytes_to_read = num_bytes_to_read - len(data)
    return (msg_id, message)

  def disconnect(self):
    """Closes the connection."""
    self.rawsocket.close()


class DisconnectedPilotModel:
  """A PilotModel that doesn't need to connect to a remote pilot model
  process, but fakes it well enough to hopefully let code run without
  throwing exceptions.
  """
  # 5/9/07 mrh: updating so that disconnected model has access to event_client
  def __init__(self, event_client):
    self.event_client = event_client
    self.status = "inbound to ip"
    self.timers = []
    self.all_props = [
      # Kampton City
      {"name": "kampton-city",
       "type":"Kampton",
       "category":"City",
       "limitUnits":"meters",
       "extentUnits":"meters",
       "locationUnits":"meters",
       "northLimit":"1616,-3652",
       "southLimit":"-383,-3652",
       "eastLimit":"616,-2652",
       "westLimit":"616,-4652",
       "northSouthExtent":"2000",
       "eastWestExtent":"2000",
       "location":"616,-3652"},
      # Drinkwater Lake
      {"name": "drinkwater-lake",
       "type":"Dry Lake",
       "category":"Minor Geographic Details",
       "limitUnits":"meters",
       "extentUnits":"meters",
       "locationUnits":"meters",
       "northLimit":"3703,1908",
       "southLimit":"2667,3657",
       "eastLimit":"2770,3793",
       "westLimit":"3412,1086",
       "northSouthExtent":"1036.7",
       "eastWestExtent":"2707.4",
       "location":"3185,2439"},
      # Tank 1
      {"category":"tank",
       "location":"2579,-8561",
       "locationUnits":"meters",
       "name":"target",
       "type":"T-55"},
      # Tank 2
      {"category":"tank",
       "location":"5000,5000",
       "locationUnits":"meters",
       "name":"target",
       "type":"BMP-1"}]

  # MRH: changing (temporarily?) so that it sees everything

  def connect(self):
    print "Using disconnected pilot model!"

  def disconnect(self):
    for timer in self.timers:
      timer.cancel()
    self.timers = []

  def is_connected(self):
    return False

  def get_pilot_pose(self):
    return [[0, 0, 0, 0], [0, 0, 0], 0]

  def can_see_object_id(self, unused_object_id):
    # print "Faking, saying pilot can see object ID %s" % (object_id, )
    return True                # False

  def can_see_object_type(self, unused_category, unused_object_type):
    #print "Faking, saying pilot can see object type: (%s, %s)" % (
    #  category, object_type)
    return True                # False

  def can_see_object(self, props_or_desc):
    # if we get a description object, turn the slots into a nice dictionary
    string_props = None
    if type(props_or_desc) == logic.Description:
      # dictify, and then flatten to a one-level property list?
      # guessing.  -- on second thought, no guessing.  skip for now.
      tmp_dict = logic.Description.dictify(props_or_desc)
      # walk through, flatten out
      #for item in tmp_dict.items():
        #if item[0] == "base":
          #string_props["type"] = item[1]  # replace "base" with "type
        #elif item[0] = "slots
      string_props = tmp_dict
    else:
      # just take what we were given
      string_props = props_or_desc
    # print "Faking, saying pilot can see object w/ props: %s" %
    # (string_props,)
    return True                # False

  def get_details(self):
    # print "Can't fake get_details yet."
    return "<!-- You are connected to a fake pilot model, sorry -->"

  def get_object_details(self, string_props):
    result = self.fake_get_props(string_props)
    # print "Faking get_object_details for (props = %s), returning %s properties" % (string_props, len(result))
    return [result]

  def get_all(self):
    # print "Can't fake get_all yet."
    return "<!-- You are connected to a fake pilot model, sorry -->"

  def look_direction(self, vector):
    # print "Faking, not looking towards %s" % (vector,)
    pass

  def look_at(self, target):
    # print "Faking, not looking at %s" % (target,)
    pass

  def fly_to(self, coords, type="inbound to ip"):
    self.status = type
    if type == 'inbound to target':
      self.install_attack_events()

  def get_status(self):
    return self.status

  def get_playtime(self):
    return 30.0

  def get_fuel(self):
    return 1.0

  def get_object_location(self, string_props):
    obj_props = self.fake_get_props(string_props)
    results = [[0, 0, 0]]    # default
    try:
      results = [obj_props["location"]]
    except:
      pass
    # print "Faking, returning obj. location %s. (props = %s)" % (results, string_props)
    return results

  def fake_get_props(self, string_props):
    """In our props collection, find items with matching key/values in
    their lists."""
    result = {}
    for prop_dict in self.all_props:
      try:
        key = string_props.keys()[0]
        val = string_props[key]
        if prop_dict[key] == val:
          result = prop_dict
          break
      except:
        pass
    return result

  def trigger_nine_line(self, target=None):
    # don't bother logging, just fake the event data
    nine_line_xml = """<pilotModelEventContainer xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://www.energid.com/namespace/pmeTCP.pme.xsd" xmlns="http://www.energid.com/namespace/pme">
  <nineLineEvent>
  <nineLine>
   <element><key>1</key><value>Bravo</value></element>
   <element><key>2</key><value>346 degrees, offset 30 degrees right</value></element>
   <element><key>3</key><value>5 nautical miles</value></element>
   <element><key>4</key><value>3300 feet</value></element>
   <element><key>5</key><value>%s</value></element>
   <element><key>6</key><value>NV 399 282</value></element>
   <element><key>7</key><value>None</value></element>
   <element><key>8</key><value>2 clicks south</value></element>
   <element><key>9</key><value>IP</value></element>
   <element><key>remarks</key><value>call departing; call with direction; clearance on final; no clearance, no drop</value></element>
  </nineLine>
 </nineLineEvent>
 </pilotModelEventContainer>""" % (target,)
    parsed_event = parse_event_string(nine_line_xml)
    assert(parsed_event is not None and parsed_event[0] == True)
    self.event_client.handle_event(parsed_event[1])

  def install_attack_events(self):
    self.add_timer(2, {"type": "eta",
                       "eta": 60,
                       "pilot-pose": [[0, 0, 0, 0], [0, 0, 0], 0],
                       "target-coords": [10, 0, 0, 0]})
    self.add_timer(4, {"type": "eta",
                        "eta": 10,
                        "pilot-pose": [[5, 5, 5, 5], [5, 5, 5], 5],
                        "target-coords": [10, 0, 0, 0]})
    self.add_timer(6, {"type": "attack-run-complete",
                        "status": 1})

  def add_timer(self, delay, event):
    timer = utils.Timer(delay, self.fire_event, args=[event])
    timer.start()

  def fire_event(self, event):
    self.event_client.handle_event(event)

  def handle_event(self, event):
    self.fire_event(event)


def parse_target_coordinates(coords_node):
  x = float(coords_node.getAttribute("x"))
  y = float(coords_node.getAttribute("y"))
  z = float(coords_node.getAttribute("y"))
  return [x, y, z]

# Changing event model slightly to have event handlers return tuples
# where first value is event parse success (true/false), and second value is
# actual result.  If success is false, a message describing the failure is the
# expected second value.


def parse_eta_event(event_node):
  eta_node = event_node.getElementsByTagName("eta")[0]
  eta = float(get_node_text(eta_node))
  pose_node = event_node.getElementsByTagName("pilotPose")[0]
  pose = parse_pilot_pose(pose_node)
  target_node = event_node.getElementsByTagName("targetCoordinates")[0]
  target_coords = parse_target_coordinates(target_node)
  return [True,
          {"type": "eta",
           "eta": eta,
           "pilot-pose": pose,
           "target-coords": target_coords}]


def parse_attack_run_complete_event(event_node):
  status_node = event_node.getElementsByTagName("attackRunCompleteFlag")[0]
  status = int(get_node_text(status_node))
  return [True,
          {"type": "attack-run-complete", "status": status}]


def parse_nine_line_event(event_node):
  """Returns a dictionary of nine-line information."""
  def parse_mn_element(elementDict, element):
    key = str(get_node_text(element.getElementsByTagName("key")[0]))
    value = str(get_node_text(element.getElementsByTagName("value")[0]))
    # special consideration for target coordinates: massage two
    # numbers into one
    if key == "6":
      pieces = value.split()
      if len(pieces) == 3:
        value = pieces[0] + " " + pieces[1] + pieces[2]
    # clean up strings in general
    if isinstance(value, basestring):
      value = value.strip()
    elementDict[key] = value

  try:
    nine_line = event_node.getElementsByTagName("nineLine")[0]
    mn_elements = nine_line.getElementsByTagName("element")
    string_props = {}
    for mn_element in mn_elements:
      parse_mn_element(string_props, mn_element)

    string_props["type"] = "nine-line"
    return [True, string_props]
  except:
    import sys
    info = sys.exc_info()
    return [False, "Unexpected error: (%s, %s)" % (info[0], info[1])]

EventParsers = {
  "etaEvent": parse_eta_event,
  "attackRunCompleteEvent": parse_attack_run_complete_event,
  "nineLineEvent": parse_nine_line_event
  }


def parse_event_string(event_container_string):
  doc = xml.dom.minidom.parseString(event_container_string).documentElement
  assert(isinstance(doc, xml.dom.minidom.Element))
  return parse_event(doc)


def parse_event(event_container_node):
  examined_nodes = []
  for event_node in event_container_node.childNodes:
    if event_node.nodeType == xml.dom.minidom.Node.ELEMENT_NODE:
      tag_name = event_node.localName
      if tag_name in EventParsers:
        return apply(EventParsers[tag_name], [event_node])
      else:
        examined_nodes.append(tag_name)
  # return None
  return [False,
          "No event handlers found for these events: %s" % examined_nodes]


class EventListener(threading.Thread):
  def __init__(self, host, client):
    threading.Thread.__init__(self)
    self.host = host
    self.connection = None
    self.client = client
    self.setDaemon(True)
    self.keep_running = True

  def connect(self):
    self.connection = EcConnection(self.host, EVENT_PORT)
    self.connection.connect()

  def disconnect(self):
    if self.connection != None:
      self.connection.disconnect()
      self.connection = None

  def stop(self):
    self.keep_running = False
    time.sleep(1)

  def run(self):
    self.keep_running = True
    self.connect()
    self.process_events()

  def process_events(self):
    while self.keep_running:
      (msg_type, message) = self.connection.read_message()
      if msg_type == 0 and len(message) > 0:
        self.client.log("<== EVENT XML", message)
        event = self.parse_message(message)
        if event != None and event[0] == True:
          self.client.handle_event(event[1])
        else:
          if event is None:
            print "** Event handler returned none?"
          else:
            print "** Event handler failure: %s" % event[1]

    self.disconnect()

  def parse_message(self, message):
    return parse_event_string(message)

  def dispatch_event(self, event):
    print "Got event: %s" % (event,)


def log_summary(xml_string):
  # Find the second >
  start = xml_string.find(">", xml_string.find(">") + 1)
  xml_string = xml_string[start + 1:]
  xml_string = xml_string.replace("<", " ")
  xml_string = xml_string.replace(">", " ")
  xml_string = xml_string.replace("\n", " ")
  xml_string = xml_string.strip()
  return xml_string[0:80]
