from win32com.client import constants
import win32com.client
import pythoncom
import sys
import struct
import winsound

import radioify

speaker = win32com.client.Dispatch("SAPI.SpVoice")


def speak(text):
  wavebuf = win32com.client.Dispatch("SAPI.SpMemoryStream")
  wavebuf.Format.Type = constants.SAFT16kHz16BitMono
  speaker.AudioOutputStream = wavebuf
  speaker.Speak(text)
  data = wavebuf.GetData()

  fmt = "%sh" % (len(data)/2,)
  data = struct.unpack(fmt, data)
  data = radioify.radioify(data)
  radioify.writefile(data, "temp.wav")
  winsound.PlaySound("temp.wav", winsound.SND_FILENAME)


while True:
  line = sys.stdin.readline()
  speak(line)
  






