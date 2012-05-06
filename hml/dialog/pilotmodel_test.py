from hml.base import unittest
from hml.dialog import pilotmodel


ETA_EVENT_1 = """
<pilotModelEventContainer xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://www.energid.com/namespace/pme
  TCP.pme.xsd" xmlns="http://www.energid.com/namespace/pme">
 <etaEvent>
  <eta>8.7930947296801865</eta>
  <pilotPose>
   <mn:orientation xmlns:mn="http://www.energid.com/namespace/mn" q0="1" q1="0" q2="0" q3="0"/>
   <mn:translation xmlns:mn="http://www.energid.com/namespace/mn" x="0" y="0" z="0"/>
  </pilotPose>
  <targetCoordinates x="-2951" y="-4052.4000000000001" z="-700.39999999999998"/>
 </etaEvent>
</pilotModelEventContainer>
"""

ATTACK_RUN_COMPLETE_EVENT_1 = """
<pilotModelEventContainer xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://www.energid.com/namespace/pme
  TCP.pme.xsd" xmlns="http://www.energid.com/namespace/pme">
 <attackRunCompleteEvent>
  <attackRunCompleteFlag>1</attackRunCompleteFlag>
 </attackRunCompleteEvent>
</pilotModelEventContainer>
"""

ATTACK_RUN_COMPLETE_EVENT_2 = """
<pilotModelEventContainer xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://www.energid.com/namespace/pme
  TCP.pme.xsd" xmlns="http://www.energid.com/namespace/pme">
 <attackRunCompleteEvent>
  <attackRunCompleteFlag>0</attackRunCompleteFlag>
 </attackRunCompleteEvent>
</pilotModelEventContainer>
"""


class TestCase(unittest.TestCase):

  def testEventParsing(self):
    self.assertEqual(pilotmodel.parse_event_string(ETA_EVENT_1),
                     {'type': 'eta',
                      'eta': 8.7930947296801865,
                      'pilot-pose': [[1.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
                      'target-coords': [-2951.0, -4052.4000000000001, -4052.4000000000001]})
    self.assertEqual(pilotmodel.parse_event_string(ATTACK_RUN_COMPLETE_EVENT_1),
                     {'type': 'attack-run-complete',
                      'status': 1})
    self.assertEqual(pilotmodel.parse_event_string(ATTACK_RUN_COMPLETE_EVENT_2),
                     {'type': 'attack-run-complete',
                      'status': 0})
    

  
if __name__ == "__main__":
  unittest.main()
