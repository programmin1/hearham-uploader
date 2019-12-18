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
import re

class Recognizer(Thread):
    def __init__(self, parent):
        Thread.__init__(self)
        self.config = parent.config
        self.parent = parent
        
    def run(self):
        cfg = self.config['julia']
        cmd = [cfg['juliabinary'], '-C', cfg['jconffile']]
        if 'dnnconffile' in cfg:
            cmd.append( '-dnnconf' )
            cmd.append(cfg['dnnconffile'])
        
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
        
class RTLSDRRun(Thread):
    def __init__(self, cmd, parent):
        Thread.__init__(self)
        self.config = parent.config
        self.cmd = cmd
        self.parent = parent
        
    def run(self):
        #cmd = 'rtl_fm -M fm -f '+self.freq+'M -l 202 | play -r 24k -t raw -e s -b 16 -c 1 -V1 -'
        cmds = self.cmd.split('|')
        self.proc = subprocess.Popen(cmds[0].split(),
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
        subprocess.check_output(cmds[1].split(),stdin=self.proc.stdout)
        for line in iter(self.proc.stdout.readline, b''):
            line = line.decode('utf-8')
            print(line)

        

class MainWin:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read('hear.config')
        self.uploadkey = None
        self.isconnected = None
        self.rtllistener = None
        self.VERSION = '0.0.1'
        self.SENDDOMAIN = self.config['http']['uploadto']
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
            'loopbackOff' : self.loopbackOff,
            'playRTLSDR' : self.playRTLSDR,
            'stopRTLSDR' : self.stopRTLSDR
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
            self.writeConf()
            dialog.destroy()
            
        #Try listening and uploading:
        try:
            if self.config['RTLSDR']['cmd']:
                self.rtllistener = RTLSDRRun( self.config['RTLSDR']['cmd'], self )
                self.rtllistener.start()
                nums = re.compile(r"[+-]?\d+(?:\.\d+)?")
                frequency = nums.search(self.config['RTLSDR']['cmd']).group(0)
                self.builder.get_object('freqEntry').set_text( frequency )
        except KeyError:
            print('No RTLSDR setting')
            
        try:
            if self.config['http']['uploadsecret']:
                self.getStation(self.config['http']['uploadsecret'])
        except KeyError:
            print('No uploading')
            
                
        #pabutton = self.builder.get_object("buttonConfAudio")
        self.window.set_size_request(600,300)
        
    def writeConf(self):
        """ Writes config preferences to file. """
        with open('hear.config','w') as conffile:
            self.config.write(conffile)
        
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
               "For help please see "+self.SENDDOMAIN+"/help.\n"
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
                self.config['http']['uploadsecret'] = text
                self.writeConf()
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
        
    def playRTLSDR(self, obj):
        if self.rtllistener:
            self.rtllistener.proc.kill()
        cmd = 'rtl_fm -M fm -f '+self.builder.get_object('freqEntry').get_text()+'M -l 202 | play -r 24k -t raw -e s -b 16 -c 1 -V1 -'
        print(cmd)
        self.config['RTLSDR'] = {'cmd' : cmd }
        self.writeConf()
        self.rtllistener = RTLSDRRun( cmd, self )
        self.rtllistener.start()
        
    def stopRTLSDR(self, obj):
        if self.rtllistener:
            self.rtllistener.proc.kill()
    
    def onDelete(self, window, event):
        self.recog.proc.kill()
        if self.rtllistener:
            self.rtllistener.proc.kill()
        Gtk.main_quit()

if __name__ == '__main__':
    app = MainWin()
    Gtk.main()
    import sys
    sys.exit()
