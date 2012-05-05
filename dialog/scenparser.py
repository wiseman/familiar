#!/usr/bin/env python2.5
from xml.dom.minidom import parse
import sys
import StringIO

A_PRIORI_CATEGORIES = [u'Major Geographic Details',
                       u'Minor Geographic Details',
                       u'Distinct Features',
                       u'Urban',
                       u'MOUT House']

CLASS_TABLE = {u'Major Geographic Details': 'c-major-geographic-feature',
               u'Minor Geographic Details': 'c-minor-geographic-feature',
               u'Distinct Features': 'c-distinct-feature',
               u'Urban': 'c-village',
               u'MOUT House': 'c-building'}



class Context:
  def __init__(self, scendoc, colordoc):
    self.scendoc = scendoc
    self.colordoc = colordoc

  def get_element_with_name(self, name):
    for e in self.colordoc.childNodes[0].childNodes:
      if e.nodeType == e.ELEMENT_NODE:
        n = e.getElementsByTagName('name')
        if len(n) > 0 and get_text(n[0]) == name:
          return e
    return None

  def get_centroid(self, name):
    e = self.get_element_with_name(name)
    centroid_e = e.getElementsByTagName('centroid')
    if len(centroid_e) > 0:
      centroid = centroid_e[0]
      return map(float, get_text(centroid).split(','))
    else:
      return None

  def get_location(self, name):
    e = self.get_element_with_name(name)
    location_e = e.getElementsByTagName('location')
    if len(location_e) > 0:
      location = location_e[0]
      return map(float, get_text(location).split(','))
    else:
      return None

  def get_category(self, element):
    cat = element.getElementsByTagName('category')
    if len(cat) > 0:
      return get_text(cat[0])
    names = element.getElementsByTagName('name')
    if len(names) != 1:
      return None
                 
    element = self.get_element_with_name(get_text(names[0]))
    if element:
      cat = element.getElementsByTagName('category')
      if len(cat) > 0:
        return get_text(cat[0])
    return None

  def get_aliases(self, name):
    e = self.get_element_with_name(name)
    alias_e = e.getElementsByTagName('alias')
    if len(alias_e) > 0:
      aliases = get_text(alias_e[0]).split(',')
      return aliases
    else:
      return None


def get_latitude(self, e):
  return float(get_text(e.getElementsByTagName('latitude')))

def get_longitude(e):
  return float(get_text(e.getElementsByTagName('longitude')))
  

  
def parse_file(scen_file, color_file):
  scendoc = parse(scen_file)
  colordoc = parse(color_file)
  context = Context(scendoc, colordoc)
  print "<fdl>\n"
  for element in scendoc.getElementsByTagName('element'):
    if is_a_priori_entity(context, element):
      xml = entity_to_xml(context, element)
      print xml
  print "\n</fdl>"
    

def has_text(element):
  return len(element.childNodes) > 0 and element.childNodes[0].nodeType == element.TEXT_NODE

def get_text(element):
  data = ""
  for e in element.childNodes:
    data = data + e.data
  return data

def is_a_priori_entity(context, e):
  return context.get_category(e) in A_PRIORI_CATEGORIES


def slot_xml(name, value):
  return '  <slot name="%s" value="%s"/>' % (name, value)

def make_id(name):
  return name.replace(" ", "-")


def entity_to_xml(context, e):
  s = StringIO.StringIO()
  name = get_text(e.getElementsByTagName('name')[0])
  s.write("<!-- %s -->\n" % (name,))
  type = get_text(e.getElementsByTagName('type')[0])
  cat = context.get_category(e)
  centroid = context.get_centroid(name)
  location = context.get_location(name)
  parent = CLASS_TABLE[cat]
  
  s.write("<frame id='i-%s'>\n" % (make_id(name),))
  s.write("  <parent id='%s' instanceof='true'/>\n" % (parent,))
  s.write("  <generate>%s</generate>\n" % (name.lower(),))
  s.write(slot_xml("objid", name) + "\n")
  s.write(slot_xml("type", cat) + "\n")
  s.write(slot_xml("subtype", type) + "\n")
  if centroid:
    position_str = "{'slots': {'x': %s, 'y': %s, 'z': %s}}" % tuple(centroid)
  else:
    position_str = "{'slots': {'x': %s, 'y': %s, 'z': %s}}" % tuple(location)
  s.write(slot_xml("position", position_str) + "\n")
  s.write( "</frame>\n\n")
  return s.getvalue()

call_contact_counter = 0

def print_conv_tests_for_feature(feature):
  global call_contact_counter
  name = get_text(feature.getElementsByTagName('name')[0])
  aliases = get_aliases(name)

  for alias in aliases:
    call_contact_counter += 1
    print "<test name='call-contact-%s'>" % (call_contact_counter,)
    print "  <input>hog, call contact with %s</input>" % (alias,)
    print "  <output>Gunslinger, (contact|visual %s)</output>" % (name.lower(),)
    print "</test>"
    print ""

def print_conv_tests(features):
  for f in features:
    print_conv_tests_for_feature(f)


parse_file(sys.argv[1], sys.argv[2])

#print_features(get_major_features(), "c-major-geographic-feature")
#print_features(get_minor_features(), "c-minor-geographic-feature")
#print_features(get_distinct_features(), "c-distinct-feature")

#print_conv_tests(get_major_features())
#print_conv_tests(get_minor_features())
#print_conv_tests(get_distinct_features())


  
  
