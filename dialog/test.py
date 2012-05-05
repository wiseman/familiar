import wx
import wx.lib.newevent

import time
import thread


(UpdateStatusEvent, EVT_UPDATE_STATUS) = wx.lib.newevent.NewEvent()
(TranscriptEvent, EVT_UPDATE_TRANSCRIPT) = wx.lib.newevent.NewEvent()



class SpeechUI(wx.Frame):
  PROCESSING = 'processing'
  READY = 'ready'

  def __init__(self, parent, ID, title, pos=wx.DefaultPosition,
               size=(480,480), style=wx.DEFAULT_FRAME_STYLE):
    wx.Frame.__init__(self, parent, ID, title, pos, size, style)
    panel = wx.Panel(self, -1)

    self.transcript = wx.TextCtrl(panel, -1, "foo", pos=(0, 50), size = (480,430),
                                  style = wx.TE_MULTILINE | wx.TE_RICH2)
    
    self.label = wx.StaticText(panel, -1, "OK", size=(480,50),
                               style = wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL)
    self.label.SetBackgroundColour("#FF0000")
    self.Bind(EVT_UPDATE_STATUS, self.onStatusUpdate)
    self.Bind(EVT_UPDATE_TRANSCRIPT, self.onTranscriptUpdate)

  def onStatusUpdate(self, event):
    print "setting status: %s" % (event,)
    self.setStatus(event.status)
    print "set status"

  def setStatus(self, status):
    if status == SpeechUI.PROCESSING:
      self.label.SetBackgroundColour("#FF0000")
      self.label.SetLabel("Processing")
    else:
      self.label.SetBackgroundColour("#00FF00")
      self.label.SetLabel("Ready")
    self.label.SetSize((480, 50))
      
  def onTranscriptUpdate(self, event):
    self.addText(event.who, event.text)

  def addText(self, who, text):
    if who == 'pilot':
      font = self.transcript.GetFont()
      font.SetPointSize(14)
      font.SetFaceName("Georgia")
      font.SetFamily(wx.ROMAN)
      style = wx.TextAttr("#910000", wx.NullColor, font, wx.ALIGN_LEFT)
      self.transcript.SetDefaultStyle(style)
    elif who == 'jtac':
      font = self.transcript.GetFont()
      font.SetPointSize(14)
      font.SetFaceName("Georgia")
      font.SetFamily(wx.ROMAN)
      style = wx.TextAttr("#009100", wx.NullColor, font, wx.ALIGN_LEFT)
      self.transcript.SetDefaultStyle(style)
    else:
      font = self.transcript.GetFont()
      font.SetPointSize(9)
      font.SetFaceName("Georgia")
      font.SetFamily(wx.ROMAN)
      font.SetStyle(wx.FONTSTYLE_ITALIC)
      style = wx.TextAttr("#000000", wx.NullColor, font, wx.ALIGN_CENTER)
      style.SetAlignment(wx.ALIGN_CENTER)
      self.transcript.SetDefaultStyle(style)
      
    self.transcript.WriteText(who)
    self.transcript.SetDefaultStyle(wx.TextAttr("#000000"))
    self.transcript.WriteText(": %s\n" % (text,))



whos = ['pilot', 'debug', 'jtac']

def wait_and_post(ui):
  time.sleep(1)
  print "fire!"
  event = UpdateStatusEvent(status=SpeechUI.READY)
  wx.PostEvent(ui, event)

  for i in range(1, 7):
    time.sleep(1)
    event = TranscriptEvent(who = whos[i % 3], text = "hello %s" % (i,))
    wx.PostEvent(ui, event)

    

try:
  app = wx.PySimpleApp()
  frame = SpeechUI(None, -1, "dhu")
  frame.Show()

  thread.start_new_thread(wait_and_post, (frame,))



  app.MainLoop()

  time.sleep(10)

except Exception, e:
  print e
  
