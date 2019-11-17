#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  MainWin.py
#  Depends on Julius and the Julius models - setup.py, before running

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib
from threading import Thread
import subprocess
import configparser
import urllib
import urllib.request
from urllib.error import HTTPError
from urllib.error import URLError
import json

class Recognizer(Thread):
    def __init__(self, parent):
        Thread.__init__(self)
        self.config = parent.config
        self.parent = parent
        
    def run(self):
        cfg = self.config['julia']
        cmd = [cfg['juliabinary'], '-C', cfg['jconffile'], '-dnnconf', cfg['dnnconffile']]
        self.proc = subprocess.Popen(cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
        for line in iter(self.proc.stdout.readline, b''):
            line = line.decode('utf-8')
            if line.find('sentence1: ')==0:
                found = line.replace('sentence1: <s>','').replace('</s>','').strip()
                print('Found "%s"' % (found,))
                if self.parent.uploadkey:
                    try:
                        value = self.parent.sendHeard(found)
                        print('Server said '+value)
                    except HTTPError:
                        print("oopse http error")
                    except URLError:
                        print("Oopse no connection")
                #Display it
                self.parent.heard(found)
            elif line.find('Warning: strip: ')==0: # = Warning: strip: sample 0-666 is invalid, stripped
                GLib.idle_add(self.parent.disconnected)
            else:
                GLib.idle_add(self.parent.connected)
        #Binary finished
        GLib.idle_add(self.parent.disconnected)
        

class MainWin:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read('hear.config')
        self.uploadkey = None
        self.isconnected = None
        self.VERSION = '0.0.1'
        self.SENDDOMAIN = 'http://hearham.com/'
        self.recog = Recognizer(self)
        self.recog.start()
        self.builder = Gtk.Builder()
        self.builder.add_from_file("MainWin.glade")
        self.builder.connect_signals({
			'configAudio' : self.configAudio,
			'onDelete' : self.onDelete,
            'onDestroy' : self.onDelete,
            'chooseUpload' : self.chooseUpload,
            'help' : self.helpBtn,
            'loopbackOn' : self.loopbackOn,
            'loopbackOff' : self.loopbackOff
		})
        self.window = self.builder.get_object("hearhamwindow")
        self.window.show_all()
        try:
            if self.config['reporting']['sentry']:
                self.initReporting()
        except KeyError:
            dialog = Gtk.MessageDialog(self.window, 0, Gtk.MessageType.QUESTION,
                Gtk.ButtonsType.YES_NO, "Enable crash reporting?")
            dialog.format_secondary_text(
                "Select Yes to help improve the software by reporting exceptions")
            response = dialog.run()
            if response == Gtk.ResponseType.YES:
                self.config['reporting'] = {'sentry':True}
                self.initReporting()
            else:
                self.config['reporting'] = {'sentry':False}
            with open('hear.config','w') as conffile:
                self.config.write(conffile)
            dialog.destroy()
                
        #pabutton = self.builder.get_object("buttonConfAudio")
        self.window.set_size_request(600,300)
        
    def initReporting(self):
        import sentry_sdk
        sentry_sdk.init("https://46ea78b49e3442fbb26b5cd7d6172bc8@sentry.io/1821213")

    def heard(self,text):
        textbox = self.builder.get_object('textviewrecognized')
        txtbuffer = textbox.get_buffer()
        end = txtbuffer.get_end_iter()
        txtbuffer.insert(end, text+'\n')
        
    def configAudio(self,obj):
        subprocess.Popen(['pavucontrol','--tab','2'])
        
    def loopbackOn(self,obj):
        subprocess.Popen(['pactl', 'load-module', 'module-loopback'])
        
    def loopbackOff(self,obj):
        subprocess.Popen(['pactl', 'unload-module', 'module-loopback'])
        
    def helpBtn(self,obj):
        dialog = Gtk.MessageDialog(self.window, 0, Gtk.MessageType.INFO,
            Gtk.ButtonsType.OK, "Hearham uploader version "+self.VERSION+"\n"+
               "For help please see "+self.SENDDOMAIN+"help.\n"
               "User interface by Luke Bryan\nCode and Models under MPL License.\nFor information about Julius recognizer see https://github.com/julius-speech/julius")
        response = dialog.run()
        dialog.destroy()
        
    def disconnected(self):
        if self.isconnected:
            obj = self.builder.get_object("statusImage")
            obj.set_from_stock(Gtk.STOCK_DIALOG_ERROR, Gtk.IconSize.BUTTON)
            label = self.builder.get_object('labelStatus')
            label.set_text('No input!')
            self.isconnected = False
        
    def connected(self):
        if not self.isconnected:
            obj = self.builder.get_object("statusImage")
            obj.set_from_stock(Gtk.STOCK_YES, Gtk.IconSize.BUTTON)
            label = self.builder.get_object('labelStatus')
            label.set_text('Recognizing')
            self.isconnected = True
    
    def chooseUpload(self,obj):
        d = Gtk.MessageDialog(self.window,
              0,
              Gtk.MessageType.QUESTION,
              Gtk.ButtonsType.OK,
              'Enter upload code:')
        entry = Gtk.Entry()
        entry.show()
        d.vbox.pack_end( entry, 1, 1, 10)
        entry.connect('activate', lambda _: d.response(Gtk.ResponseType.OK))
        d.set_default_response(Gtk.ResponseType.OK)
        r = d.run()
        text = entry.get_text()
        d.destroy()
        if r == Gtk.ResponseType.OK:
            try:
                self.getStation(text)
            except HTTPError:
                dialog = Gtk.MessageDialog(self.window, 0, Gtk.MessageType.WARNING,
                    Gtk.ButtonsType.OK, "Invalid key, please try again")
                response = dialog.run()
                dialog.destroy()
            except URLError:
                dialog = Gtk.MessageDialog(self.window, 0, Gtk.MessageType.WARNING,
                    Gtk.ButtonsType.OK, "No connection, please try again")
                response = dialog.run()
                dialog.destroy()
        else:
            return None
            
    def getStation(self, key):
        url = self.SENDDOMAIN+'/api/getstation'
        resource = urllib.request.urlopen(url, data=urllib.parse.urlencode({
            'key': key
        }).encode())
        content =  resource.read().decode('utf-8')
        jsonval = json.loads(content)
        #name and frequency...
        self.builder.get_object('labelStation').set_text(jsonval['name']+"\nMust be set to\n"+str(int(jsonval['frequency'])/1E6)+"M")
        #Success!
        self.uploadkey = key
    
    def sendHeard(self, heard):
        url = self.SENDDOMAIN+'/api/audiolog'
        resource = urllib.request.urlopen(url, data=urllib.parse.urlencode({
            'key': self.uploadkey,
            'hear': heard
        }).encode())
        content =  resource.read().decode('utf-8')
        return content
    
    def onDelete(self, window, event):
        self.recog.proc.kill()
        Gtk.main_quit()
        
        
#TODO  pulseaudiocontrol and https://www.youtube.com/watch?v=RSeINGM68A8
#pactl load-module module-loopback

#pactl unload-module module-loopback

#julius/julius/julius -C mic.jconf -dnnconf dnn.jconf


if __name__ == '__main__':
    app = MainWin()
    Gtk.main()
    import sys
    sys.exit()
