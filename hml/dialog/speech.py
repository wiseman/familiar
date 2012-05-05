"""Implements an IOManager that uses Microsoft's speech recognition
and speech synthesis APIs.

In order to use this module you must do the following:

  1. Download and install the Speech SDK 5.1 from
     <http://www.microsoft.com/downloads/details.aspx?FamilyId=5E86EC97-40A7-453F-B0EE-6583171B4530&displaylang=en>

  2. Download and install a version of PythonWin corresponding to the
     version of Python that's installed on your machine (i.e., if you
     have Python 2.4 installed, you need PythonWin 2.4).  I use Python
     2.4, but this should work in Python 2.5 too.

  3. Open a command prompt, cd to the win32com client subdirectory in
     your Python's site-packages directory, and run makepy.py on the
     sapi.dll from the Speech SDK:

       C:\>cd \Python24\Lib\site-packages\win32com\client

       C:\Python24\Lib\site-packages\win32com\client>python makepy.py "C:\Program Files\Common Files\Microsoft Shared\Speech\sapi.dll"
       Generating to c:\Python22\lib\site-packages\win32com\gen_py\C866CA3A-32F7-11D2-9602-00C04F8EE628x0x5x0.py
       Building definitions from type library...
       Generating...
       Importing module

     This seems to be the only way to get makepy to see the correct
     version of the DLL; The makepy GUI only displays version 5.0 of
     "Microsoft Speech Objects", which will not work.

  4. Download and install wxPython from
     <http://www.wxpython.org/download.php#binaries>.  Again you'll
     need the version that corresponds to your version of Python.  In
     addition there's an ANSI version and a unicode version; I used
     the unicode version.

"""
       

from win32com.client import constants
import win32com.client
import pythoncom
import winsound
import threading
import sys
import time
import array
import StringIO
import wx
import wx.lib.newevent

from energid import iomanager
from energid import filter
from energid import utils


# Define some new custom wx events.

(UpdateStatusEvent, EVT_UPDATE_STATUS) = wx.lib.newevent.NewEvent()
(TranscriptEvent, EVT_UPDATE_TRANSCRIPT) = wx.lib.newevent.NewEvent()
(HypothesisEvent, EVT_HYPOTHESIS) = wx.lib.newevent.NewEvent()
(SwitchModeEvent, EVT_SWITCH_MODE) = wx.lib.newevent.NewEvent()
(InterferenceEvent, EVT_INTERFERENCE) = wx.lib.newevent.NewEvent()

# The constants we need to define PART_OF_SPEECH_MAP below aren't
# available until we force the MakePy-generated module to be loaded,
# which is what the following line does (and hopefully that's about
# all it does).
win32com.client.Dispatch("SAPI.SpVoice")


INTERFERENCE_MAP = {constants.SINone:     'none',
                    constants.SINoise:    'Too Much Noise',
                    constants.SINoSignal: 'No Signal',
                    constants.SITooLoud:  'Speak More Softly',
                    constants.SITooQuiet: 'Speak Louder',
                    constants.SITooFast:  'Speaking Too Fast',
                    constants.SITooSlow:  'Speaking Too Slowly'}

def interference_description(interference):
  if interference in INTERFERENCE_MAP:
    return INTERFERENCE_MAP[interference]
  else:
    return "unknown"
  
class SpeechRecognizer:
  """Interface to the Microsoft speech recognition automation API."""

  AMERICAN_ENGLISH = 1033

  # Maps from part-of-speech tags to SAPI constants.
  PART_OF_SPEECH_MAP = {'unknown':      constants.SPSUnknown,
                        'noun':         constants.SPSNoun,
                        'verb':         constants.SPSVerb,
                        'modifier':     constants.SPSModifier,
                        'function':     constants.SPSFunction,
                        'interjection': constants.SPSInterjection}

  def __init__(self, io_manager, grammar_path, retain_audio=True):
    """grammar_path must be the complete path to a .xml or .cfg
    (compiled) grammar file.
    """
    self.io_manager = io_manager
    pythoncom.CoInitialize()
    # For text-to-speech.
    self.speaker = win32com.client.Dispatch("SAPI.SpVoice")
    # For speech recognition - first create a listener.
    self.listener = win32com.client.Dispatch("SAPI.SpSharedRecognizer")
    # Then a recognition context.
    self.context = self.listener.CreateRecoContext()
    self.context.EventInterests = constants.SRERecognition | constants.SREAudioLevel
    if retain_audio:
      self.context.RetainedAudio = constants.SRAORetainAudio
    else:
      self.context.RetainedAudio = constants.SRAONone
    # ...which has an associated grammar.
    self.grammar = self.context.CreateGrammar()
    # Do not allow free word recognition - only command and control
    # recognizing the words in the grammar only.
    self.grammar.DictationSetState(constants.SGDSInactive)

    loaded_grammar = False
    try:
      self.grammar.CmdLoadFromFile(grammar_path, constants.SLODynamic)
      loaded_grammar = True
    finally:
      if not loaded_grammar:
        print "Unable to load grammar from '%s'" % (grammar_path,)
      
    self.retain_audio = retain_audio

  def start(self):
    self.grammar.CmdSetRuleIdState(0, constants.SGDSActive)
    # And add an event handler that's called back when recognition occurs
    self.eventHandler = ContextEvents(self.context, self, self.retain_audio)

  def add_lexicon(self, lexemes):
    lexicon = win32com.client.Dispatch("SAPI.SpLexicon")
    for lexeme in lexemes:
      spelling = lexeme.spelling
      for phonemes in lexeme.phonetic_pronunciation:
        lexicon.AddPronunciation(lexeme.spelling,
                                 self.AMERICAN_ENGLISH,
                                 self.PART_OF_SPEECH_MAP[lexme.part_of_speech],
                                 phonemes)

  def set_dictation_mode(self):
    self.grammar.CmdSetRuleIdState(0, constants.SGDSInactive)
    self.grammar.DictationSetState(constants.SGDSActive)

  def set_grammar_mode(self):
    self.grammar.CmdSetRuleIdState(0, constants.SGDSActive)
    self.grammar.DictationSetState(constants.SGDSInactive)

  def say(self, phrase):
    """Speak a word or phrase"""
    self.context.State = constants.SRCS_Disabled
    time.sleep(.1)
    self.filter_and_say(phrase)
    time.sleep(.1)
    self.context.State = constants.SRCS_Enabled

  def filter_and_say(self, phrase):
    # Uses the TTS API to convert the phrase string to raw audio data,
    # runs the audio samples through our "radioifier", then plays the
    # resulting audio data.
    wavebuf = win32com.client.Dispatch("SAPI.SpMemoryStream")
    wavebuf.Format.Type = constants.SAFT16kHz16BitMono
    self.speaker.AudioOutputStream = wavebuf
    self.speaker.Speak(phrase)
    data = wavebuf.GetData()
    data = filter.radioify(self.buffer_to_array(data))
    data = filter.writebuffer(data)
    # Play the audio synchronously.
    winsound.PlaySound(data, winsound.SND_MEMORY)

  def buffer_to_array(self, buffer):
    return array.array('h', str(buffer))

  def step(self):
    """This method must be called periodically to let the speech
    recognizer get CPU time.
    """
    pythoncom.PumpWaitingMessages()
  

class ContextEvents(win32com.client.getevents("SAPI.SpSharedRecoContext")):
  """This is the callback class that handles the events raised by the
  speech recognition context object.  See "Automation |
  SpSharedRecoContext (Events)" in the MS Speech SD online help for
  documentation on the events and their parameters.
  """

  def __init__(self, context, recognizer, retain_audio):
    win32com.client.getevents("SAPI.SpSharedRecoContext").__init__(self, context)
    self.recognizer = recognizer
    self.retain_audio = retain_audio
    self.recognized_wav_count = 0

  def get_audio_data(self, audio):
    done_reading = False
    buffer = StringIO.StringIO()
    while not done_reading:
      (len, data) = audio.Read(None, 16384)
      if len < 16384:
        done_reading = True
      buffer.write(data)
    return array.array('h', buffer.getvalue())

  def OnRecognition(self, StrtkeamNumber, StreamPosition, RecognitionType, Result):
    """Called when a word/phrase is successfully recognized - i.e. it
    is found in a currently open grammar with a sufficiently high
    confidence.
    """
    newResult = win32com.client.Dispatch(Result)
    text = newResult.PhraseInfo.GetText()
    audio = None
    if self.retain_audio:
      audio_obj = newResult.Audio()
      audio = self.get_audio_data(audio_obj)

    self.recognizer.io_manager.handle_utterance(text, audio)

  def OnFalseRecognition(self, StreamNumber, StreamPosition, Result):
    """Occurs when the SR engine produces a false recognition."""
    newResult = win32com.client.Dispatch(Result)
    self.recognizer.io_manager.debug("False recognition: %s" % (newResult.PhraseInfo.GetText(),))
    self.recognizer.io_manager.set_status(SpeechUI.READY)

    text = newResult.PhraseInfo.GetText()
    audio = None
    if self.retain_audio:
      audio_obj = newResult.Audio()
      audio = self.get_audio_data(audio_obj)
    self.recognizer.io_manager.handle_false_recognition(text, audio)

  def OnHypothesis(self, StreamNumber, StreamPosition, Result):
    """Occurs when the SR engine produces a hypothesis.  Multiple
    hypotheses are produced as speaking is being done and the
    recognition engine moves toward a final result.
    """
    newResult = win32com.client.Dispatch(Result)
    self.recognizer.io_manager.handle_hypothesis(newResult.PhraseInfo.GetText())

  def OnAudioLevel(self, StreamNumber, StreamPosition, AudioLevel):
    """Occurs when the SAPI audio object detects a change in audio
    level.  Doesn't seem to work from Python reliably.
    """
    pass

  def OnSoundStart(self, StreamNumber, StreamPosition):
    """Occurs when the SR engine encounters the start of sound in the
    audio input stream.
    """
    self.recognizer.io_manager.set_status(SpeechUI.PROCESSING)

  def OnSoundEnd(self, StreamNumber, StreamPosition):
    """Occurs when the SR engine encounters an end of sound in the
    audio input stream.
    """
    self.recognizer.io_manager.set_status(SpeechUI.READY)

  def OnPhraseStart(self, StreamNumber, StreamPosition):
    """Occurs when the SR engine identifies the start of a phrase."""
    pass

  def OnInterference(self, StreamNumber, StreamPosition, Interference):
    """Occurs when the SR engine encounters interference in the input
    audio stream.
    """
    print "speech: Got Interference event from SR engine %s" % (interference_description(Interference),)
    self.recognizer.io_manager.handle_interference(Interference)


class SpeechIOManager:
  """An implementation of the IOManager interface (see the
  dialogmanager module) that uses the Microsoft Speech API for
  recognition and text-to-speech.
  """

  def __init__(self, dialog_manager, retain_audio=True):
    self.dialog_manager = dialog_manager
    self.grammar_path = None
    self.lexicon = []
    self.retain_audio = retain_audio
    self.recognizer = None
    # Need a condition variable to protect access to the utteranced
    # queue.
    self.cv = threading.Condition()
    self.utterances = []
    self.shutting_down = False
    self.enable_debug = False

  def set_grammar(self, grammar_path):
    """Sets the recognition grammar to be used."""
    self.grammar_path = grammar_path

  def set_lexicon(self, lexicon):
    self.lexicon = lexicon

  def set_grammar_mode(self):
    event = SwitchModeEvent(mode=SpeechUI.GRAMMAR)
    wx.PostEvent(self.thread.ui, event)

  def set_dictation_mode(self):
    event = SwitchModeEvent(mode=SpeechUI.DICTATION)
    wx.PostEvent(self.thread.ui, event)

  def start_recognition_thread(self):
    self.thread = RecognitionThread(self)
    self.thread.start()
    if not self.thread.wait_until_ready(5.0):
      raise "Recognition thread failed to run."  

  def set_status(self, status):
    event = UpdateStatusEvent(status=status)
    wx.PostEvent(self.thread.ui, event)

  def handle_hypothesis(self, text):
    event = HypothesisEvent(text=text)
    wx.PostEvent(self.thread.ui, event)

  def handle_utterance(self, text, audio):
    event = TranscriptEvent(who='jtac', text=text)
    wx.PostEvent(self.thread.ui, event)

    # We've been called from the recognition thread; Add the utterance
    # to the queue so it can be retrieved by the dialog manager thread
    # (which will call getline).
    self.cv.acquire()
    try:
      self.utterances.append(iomanager.IORecord('JTAC', text, audio))
      self.cv.notifyAll()
    finally:
      self.cv.release()

  def handle_interference(self, interference):
    utils.log("speech: Posting interference event %s" % (interference,))
    event = InterferenceEvent(interference=interference)
    wx.PostEvent(self.thread.ui, event)


  # --------------------
  # Implementation of IOManager interface follows
  # --------------------
  
  def startup(self):
    """Starts the Speech IO Manager."""
    # We start a separate thread in which to do recognition.
    self.start_recognition_thread()

  def shutdown(self):
    """Shuts down the Speech IO Manager."""
    # Currently, this is invoked twice in a row, but I don't believe that should be harmful. -mrh 3/28
    self.cv.acquire()
    try:
      if not self.shutting_down:
        self.shutting_down = True
        self.thread.shutdown()
        self.cv.notifyAll()
    finally:
      self.cv.release()

  def debug(self, text):
    if self.enable_debug:
      #event = TranscriptEvent(who='debug', text=text)
      #wx.PostEvent(self.thread.ui, event)
      print("debug: %s" % (text,))

  def say(self, who, text):
    event = TranscriptEvent(who='pilot', text=text)
    wx.PostEvent(self.thread.ui, event)

  def getline(self):
    self.cv.acquire()
    try:
      while self.shutting_down == False:
        self.cv.wait()
        if len(self.utterances) > 0:
          utterance = self.utterances.pop()
          return utterance
      if self.shutting_down:
        # dialog manager used to dealing with EOF, so raise that to signify being done
        raise EOFError
    finally:
      self.cv.release()

  def handle_false_recognition(self, text, audio):
    self.dialog_manager.handle_false_recognition(iomanager.IORecord('JTAC', text, audio))


class RecognitionThread(threading.Thread):
  # RecognitionThread creates the SpeechUI, SpeechRecognizer.
  
  def __init__(self, io_manager):
    threading.Thread.__init__(self)
    self.io_manager = io_manager
    self.keep_running = True
    self.status = "NOTREADY"
    self.status_cv = threading.Condition()
    self.shutting_down = False
    self.setDaemon(True)

  def run(self):
    self.status_cv.acquire()
    lock_held = True
    try:
      self.app = wx.PySimpleApp()
      self.ui = SpeechUI(self,
                         self.io_manager.dialog_manager.pilot_callsign,
                         self.io_manager.dialog_manager.jtac_callsign)
      self.ui.Show()
    
      self.recognizer = SpeechRecognizer(self.io_manager,
                                         self.io_manager.grammar_path,
                                         self.io_manager.retain_audio)
      self.recognizer.add_lexicon(self.io_manager.lexicon)
      self.recognizer.start()
      self.ui.set_status(SpeechUI.READY)
      self.status = "RUNNING"
      self.status_cv.notifyAll()
      self.status_cv.release()
      lock_held = False
      self.app.MainLoop()
    finally:
      # if we bailed before releasing the locks properly, do it now
      if lock_held:
        self.status_cv.notifyAll()
        self.status_cv.release()

  def wait_until_ready(self, timeout):
    self.status_cv.acquire()
    try:
      if self.status != "RUNNING":
        self.status_cv.wait(timeout)

      return self.status == "RUNNING"
    finally:
      self.status_cv.release()
    
  def step(self):
    self.recognizer.step()
  
  def shutdown(self):
    # clean up
    self.status_cv.acquire()
    try:
      if not self.shutting_down:
        self.shutting_down = True
        self.app.Exit()
        self.io_manager.shutdown()
    finally:
      self.status_cv.release()

class SpeechUI(wx.Frame):
  """A wxWindows frame that displays the dialog manager GUI."""
  
  PROCESSING = 'processing'
  READY = 'ready'
  GRAMMAR = 'grammar'
  DICTATION = 'dictation'

  PROCESSING_COLOR = "#FF0000"
  READY_COLOR = "#00FF00"
  
  # The pos argument below puts the dialog UI just below the pilot
  # model false color view.
  def __init__(self, thread, pilot_callsign, jtac_callsign, parent=None, ID=-1,
               title="Dialog Manager", pos=(30, 256+30+256+10+10 + 20 + 7), size=(480,280),
               dev_mode=False):
    self.thread = thread
    self.jtac_callsign = jtac_callsign
    self.pilot_callsign = pilot_callsign
    self.dev_mode = dev_mode
    self.interference_timer = DeadmanTimer()
    
    wx.Frame.__init__(self, parent, ID, title, pos=pos, size=size)
    panel = wx.Panel(self, -1)

    subpanel = wx.Panel(panel, -1)
    self.label = wx.StaticText(subpanel, -1, "Processing", size=(480,50), pos=(0,0),
                               style = wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL)
    self.label.SetBackgroundColour(SpeechUI.PROCESSING_COLOR)
    self.warning = wx.StaticText(subpanel, -1, "", size=(480, 25), pos=(0, 25),
                               style = wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL)
    self.warning.SetBackgroundColour(SpeechUI.PROCESSING_COLOR)
    # font type: wx.DEFAULT, wx.DECORATIVE, wx.ROMAN, wx.SCRIPT, wx.SWISS, wx.MODERN
    # slant: wx.NORMAL, wx.SLANT or wx.ITALIC
    # weight: wx.NORMAL, wx.LIGHT or wx.BOLD
    #font1 = wx.Font(10, wx.SWISS, wx.ITALIC, wx.NORMAL)
    # use additional fonts this way ...
    warning_font = wx.Font(12, wx.DEFAULT, wx.NORMAL, wx.BOLD, False)
    self.warning.SetFont(warning_font)

    self.hypothesis = wx.StaticText(panel, -1, "Hearing: ", size=(480, 15))

    sizer = wx.BoxSizer(wx.VERTICAL)
    sizer.Add(subpanel, 0, wx.EXPAND)
    sizer.Add(self.hypothesis, 0, wx.EXPAND)

    if self.dev_mode:
      self.input = wx.TextCtrl(panel, -1, "", size=(480,20), style = wx.TE_PROCESS_ENTER)
    
      # A height of 280 allows the entire window to fit on a 1024x768 screen.
      self.transcript = wx.TextCtrl(panel, -1, "", size = (480,280),
                                    style = wx.TE_MULTILINE | wx.TE_RICH2 | wx.TE_READONLY)

      sizer.Add(self.input, 0, wx.EXPAND)
      sizer.Add(self.transcript, 1, wx.EXPAND)

    panel.SetSizer(sizer)
    sizer.Fit(self)

    self.SetClientSize(panel.GetSize())

    # Set up handlers for our custom events.
    self.Bind(EVT_UPDATE_STATUS, self.on_status_update)
    self.Bind(EVT_UPDATE_TRANSCRIPT, self.on_transcript_update)
    self.Bind(EVT_HYPOTHESIS, self.on_hypothesis)
    self.Bind(EVT_SWITCH_MODE, self.on_mode_switch)
    self.Bind(EVT_INTERFERENCE, self.on_interference)

    # And handlers for some standard events.
    self.Bind(wx.EVT_IDLE, self.on_idle)
    self.Bind(wx.EVT_CLOSE, self.on_close)
    if self.dev_mode:
      self.input.Bind(wx.EVT_TEXT_ENTER, self.on_input)
    
    self.init_styles()
    self.line_count = 0

  def init_styles(self):
    # Creates some predefined styles we use in the rich text box we
    # use to display output.
    self.styles = {}

    font = wx.Font(pointSize=12, family=wx.FONTFAMILY_ROMAN, style=wx.FONTSTYLE_NORMAL,
                   weight=wx.FONTWEIGHT_NORMAL, face="Georgia")
    style = wx.TextAttr("#910000", wx.NullColor, font, wx.ALIGN_LEFT)
    self.styles['pilot'] = style

    font = wx.Font(pointSize=12, family=wx.FONTFAMILY_ROMAN, style=wx.FONTSTYLE_NORMAL,
                   weight=wx.FONTWEIGHT_NORMAL, face="Georgia")
    style = wx.TextAttr("#009100", wx.NullColor, font, wx.ALIGN_LEFT)
    self.styles['jtac'] = style

    font = wx.Font(pointSize=9, family=wx.FONTFAMILY_TELETYPE, style=wx.FONTSTYLE_NORMAL,
                   weight=wx.FONTWEIGHT_NORMAL, face="Courier")
    style = wx.TextAttr("#000000", wx.NullColor, font, wx.ALIGN_CENTER)
    self.styles['debug'] = style

  def on_close(self, event):
    # Let's shut down more nicely than calling sys.exit(0).
    # sys.exit(0)
    self.thread.shutdown()
    
  def on_idle(self, event):
    # Step the recognition thread when we have idle time.
    self.thread.step()

  def on_input(self, event):
    # This is called when the user hits enter in the input text box;
    # presumably they've entered some bit of dialog manually instead
    # of speaking it.
    text = self.input.GetValue()
    self.input.Clear()
    if len(text) > 0:
      self.thread.io_manager.handle_utterance(text, None)
    
  def on_hypothesis(self, event):
    self.hypothesis.SetLabel("Hearing: %s" % (event.text,))
    self.Refresh()

  def on_interference(self, event):
    utils.log("speech: UI got interference event %s" % (event,))
    if event.interference:
      self.warning.SetLabel(interference_description(event.interference))
    else:
      print "CLEARING"
      self.warning.SetLabel("")
    self.warning.SetSize((480, 25))
    self.Refresh()
    if event.interference:
      print "poke!"
      self.interference_timer.poke(lambda: wx.PostEvent(self, InterferenceEvent(interference=None)), (), 1.5)
    
  def on_status_update(self, event):
    self.set_status(event.status)

  def set_status(self, status):
    # Implements that big RED/GREEN light.
    if status == SpeechUI.PROCESSING:
      self.label.SetBackgroundColour(SpeechUI.PROCESSING_COLOR)
      self.warning.SetBackgroundColour(SpeechUI.PROCESSING_COLOR)
      self.label.SetLabel("Processing")
    else:
      self.label.SetBackgroundColour(SpeechUI.READY_COLOR)
      self.warning.SetBackgroundColour(SpeechUI.READY_COLOR)
      self.label.SetLabel("Ready")
    self.label.SetSize((480, 50))
    self.warning.SetSize((480, 25))
    self.label.Refresh()
      
  def on_mode_switch(self, event):
    if event.mode == SpeechUI.GRAMMAR:
      self.thread.recognizer.set_grammar_mode()
    elif event.mode == SpeechUI.DICTATION:
      self.thread.recognizer.set_dictation_mode()
    else:
      print "Unknown recognition mode %s requested." % (event.mode,)
    
  def on_transcript_update(self, event):
    self.add_text(event.who, event.text)

  def add_text(self, who, text):
    if self.dev_mode:
      self.transcript.SetDefaultStyle(self.styles[who])
      self.transcript.AppendText(self.get_callsign_text(who))
      self.transcript.AppendText(" %s\n" % (text,))
      self.Refresh()
    
    if who == 'pilot':
      self.thread.recognizer.say(text)

  def get_callsign_text(self, who):
    if who == 'pilot':
      self.line_count = self.line_count + 1
      return "%s. %s:" % (self.line_count, self.pilot_callsign)
    elif who == 'jtac':
      self.line_count = self.line_count + 1
      return "%s. %s:" % (self.line_count, self.jtac_callsign)
    else:
      return "\t" + who + ":"


class DeadmanTimer:
  def __init__(self):
    self.timer = None
    self.lock = threading.Lock()
    
  def poke(self, fn, args, timeout):
    def timer_func():
      try:
        self.lock.acquire()
        print "deadman!"
        apply(fn, args)
        self.timer = None
      finally:
        self.lock.release()
        
    try:
      self.lock.acquire()
      if self.timer:
        self.timer.cancel()
      self.timer = threading.Timer(timeout, timer_func, ())
      self.timer.start()
    finally:
      self.lock.release()
