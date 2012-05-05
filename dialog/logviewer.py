import wx
from xml.dom import minidom
import winsound
import os.path
import wave
import sys
import zipfile
import tempfile

import utils


def get_text(node):
  text = ""
  for child in node.childNodes:
    if child.nodeType == child.TEXT_NODE:
      text = text + child.data
  return text


def play_wav_file(path):
  # windows only! but that's pretty obvious.
  if os.path.exists(path):
    wx.BeginBusyCursor()
    winsound.PlaySound(path, winsound.SND_FILENAME)
    wx.EndBusyCursor()

def compute_wav_length(path):
  if os.path.exists(path) == False:
    print "File {%s} does not exist" % (path,)
    return -1
  else:
    f = wave.open(path, "r")
    try:
      duration = float(f.getnframes()) / f.getframerate()
      return duration
    finally:
      f.close()

def unzip_log_file(path):
  zf = zipfile.ZipFile(path)
  tempdir = tempfile.mkdtemp()
  sys.stderr.write("Extracting %s to %s" % (path, tempdir))
  for i, name in enumerate(zf.namelist()):
    if not name.endswith("/"):
      sys.stderr.write(".")
      outfile = open(os.path.join(tempdir, os.path.basename(name)), 'wb')
      outfile.write(zf.read(name))
      outfile.close()
  sys.stderr.write(" done.\n")
  new_path = os.path.join(tempdir, "log.xml")
  return new_path


class InputRecord:
  def __init__(self, text, audio_file, audio_length):
    self.text = text
    self.audio_file = audio_file
    self.audio_length = audio_length

class LogViewer:
  def __init__(self):
    self.zip_path = None
    self.clear()

  def cleanup(self):
    self.clear()
    
  def clear(self):
    self.input_records = []
    if self.zip_path:
      utils.removeall(os.path.dirname(self.zip_path))
      self.zip_path = None

  def load_log(self, path):
    if path.endswith(".zip"):
      self.zip_path = unzip_log_file(path)
      return self.load_log(self.zip_path)
        
    fin = open(path, "r")
    try:
      xml = fin.read()
      xml = "<log>" + xml + "</log>"
      doc = minidom.parseString(xml).documentElement
      for node in doc.childNodes:
        if node.nodeType == node.ELEMENT_NODE:
          if node.nodeName == 'input' or \
             node.nodeName == 'false-recognition':
            if node.nodeName == 'input':
              recognized_text = get_text(node)
            else:
              recognized_text = "[...]"
            audio_file = None
            audio_length = 0.0
            if node.hasAttributes():
              audio_file = node.attributes[u"audio"].value
              audio_file = os.path.join(os.path.dirname(path), audio_file)
              audio_length = compute_wav_length(audio_file)
              if audio_length == -1:
                audio_length = 0.0
                recognized_text = "[no file!]  " + recognized_text
            self.input_records.append(InputRecord(recognized_text, audio_file, audio_length))
    finally:
      fin.close()

BASE_NAME = "Dialog Manager Log Browser"

class LogViewerFrame(wx.Frame):
  def __init__(self, parent, id, title, path=None):
    wx.Frame.__init__(self, parent, id, title)

    file_menu = wx.Menu()
    file_menu.Append(wx.ID_OPEN, "&Open File...", "Open a log file.")
    file_menu.Append(wx.ID_COPY, "&Copy current log to clipboard.")
    file_menu.Append(wx.ID_EXIT, "E&xit", "Terminate the program.")

    menu_bar = wx.MenuBar()
    menu_bar.Append(file_menu, "&File")
    self.SetMenuBar(menu_bar)

    self.listbox = wx.ListBox(self)
    self.listbox.Bind(wx.EVT_LISTBOX, self.on_listbox_select)

    wx.EVT_MENU(self, wx.ID_OPEN, self.file_menu_open)
    wx.EVT_MENU(self, wx.ID_COPY, self.file_menu_copy)
    wx.EVT_MENU(self, wx.ID_EXIT, self.file_menu_exit)

    self.log_viewer = LogViewer()

    if path != None:
      wx.BeginBusyCursor()
      self.load_log_file(path)
      wx.EndBusyCursor()

  def cleanup(self):
    self.log_viewer.cleanup()

  def file_menu_exit(self, event):
    self.cleanup()
    self.Close(True)

  def file_menu_open(self, event):
    dialog = wx.FileDialog(None, style=wx.OPEN)
    if dialog.ShowModal() == wx.ID_OK:
      wx.BeginBusyCursor()
      path = dialog.GetPath()
      self.load_log_file(path)
      self.SetLabel(BASE_NAME + " - " + os.path.basename(path))
      wx.EndBusyCursor()
  
  def file_menu_copy(self, event):
    """Copy current log info (if any) to clipboard."""
    if wx.TheClipboard.Open() == True:
      cbdata = wx.PyTextDataObject()
      cbdata.SetText("\n".join(self.listbox.GetItems()))
      wx.TheClipboard.SetData(cbdata)
      wx.TheClipboard.Flush()
      wx.TheClipboard.Close()
    else:
      print "Could not open clipboard for export."
    

  def on_listbox_select(self, event):
    selected = self.listbox.GetSelection()
    audio_path = self.log_viewer.input_records[selected].audio_file
    if audio_path != None:
      play_wav_file(audio_path)

  def load_log_file(self, path):
    print "loading %s" % (path,)
    self.listbox.Clear()
    self.log_viewer.clear()
    self.log_viewer.load_log(path)
    self.log_dir = os.path.dirname(path)

    for i, record in enumerate(self.log_viewer.input_records):
      item_string = "%.1f s: %s" % (record.audio_length, record.text)
      self.listbox.Insert(item_string, i)
    


class LogViewerApplication(wx.App):
  def OnInit(self):
    path = None
    if len(sys.argv) > 1:
      path = sys.argv[1]
    self.frame = LogViewerFrame(None, -1, BASE_NAME, path=path)
    self.frame.Show(True)
    self.SetTopWindow(self.frame)
    return True


def main():
  app = LogViewerApplication(0)
  app.MainLoop()
  

if __name__ == '__main__':
  main()
  
