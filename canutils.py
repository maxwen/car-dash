#!/usr/bin/env python3

import struct
import socket

from PyQt4.QtCore import QThread, SIGNAL
from collections import deque

class CANDecoder:
    def __init__(self, widget):
        self.widget = widget
        self.rpmValueList=deque([0 ,0, 0], 3)
        
    def hex2binary(self, hexValue):
        return bin(hexValue)[2:].rjust(8, '0')

    def testBit(self, hexValue, bit):
        return self.hex2binary(hexValue)[bit] != '0'
        
#    def dump(self, id, dlc, data):
#        line="%04X:%04X:"% (id, dlc)
#        dataLine="".join(["%02X " % x for x in data])
#        return line+":"+dataLine
    
    # return tuple (id, dlc, data)
    def unpack_can_frame(self, can_frame):
        # attention: 'data' is 8-byte-aligned
        canId, dlca, data = struct.unpack("I4s8s", can_frame)
        dlc = dlca[0]
        return canId, dlc, data[:dlc]
    
    def calcVolt(self, data):
        return (data[0] / 2 + 50)/10
    
    def calcRpm(self, data):
        rpm=int((((data[2] << 8) + data[1]) / 4)/10)*10
        self.rpmValueList.append(rpm)
        rpmValue=self.rpmValueList[0]+self.rpmValueList[1]+self.rpmValueList[2]
        rpmValueAverage=int(rpmValue/len(self.rpmValueList))
        return rpmValueAverage
    
    def calcOilTemp(self, data):
        return data[3] - 80
    
    def calcVelocity(self, data):
        return ((data[2] << 8) + data[1] - 1) / 190
    
    def calcOuterTemp(self, data):
        return data[5] / 2 - 50

    # pretty print can_frame struct
    def scan_can_frame(self, can_frame):
        canId, dlc, data = self.unpack_can_frame(can_frame)
        
        self.widget.addToLogView([canId, dlc, data])
        
        if canId == 0x571:
            self.widget.displayFloatValue(canId, "0", self.calcVolt(data), "%.2f")            
        elif canId == 0x623:
            hour=str(hex(data[1])).lstrip("0x") if data[1]!=0 else "0"
            minutes=str(hex(data[2])).lstrip("0x") if data[2]!=0 else "0"
            seconds=str(hex(data[3])).lstrip("0x") if data[3]!=0 else "0"
            self.widget.displayIntValue(canId,"0", int(hour, 10), "%02d")
            self.widget.displayIntValue(canId,"1", int(minutes, 10), "%02d")
            self.widget.displayIntValue(canId,"2", int(seconds, 10), "%02d")
        elif canId == 0x371:
        #ID 0x371, 3 Bytes
        #Byte 1:
        #- C0, Alle Türen geschlossen
        #- Bit 1: Tür Vorne Links
        #- Bit 2: Tür Vorne Rechts
        #- Bit 3: Schiebetür Links
        #- Bit 4: Schiebetür Rechts
        #Byte 2:
        #- Bit 4: Motorhaube
        #- Bit 2: Heckklappe
        #Byte 3:
        #Blinkerstatus, alternierend im Blinkerrhytmus
        #- Bit 1: Links
        #- Bit 2: Rechts
        #88/8F: Alternierend bei Warnblinker ein 
            self.widget.displayBinValue(canId, "0", self.hex2binary(data[0]), "%8s")
            self.widget.displayBinValue(canId, "1", self.hex2binary(data[1]), "%8s")
            self.widget.displayBinValue(canId, "2", self.hex2binary(data[2]), "%8s")
        elif canId == 0x271:
        #0x271 Zuendung, 1 byte, Meldung ca. alle 100ms
        #Status in Byte 1:
        #0x10: Fzg. unverschlossen, Schluessel steckt nicht
        #0x11: Fzg. unverschlossen, Schluessel steckt in Pos. 0, Zuendung aus
        #0x01: Fzg. unverschlossen, Schluessel steckt in Pos. 1, Zuendung aus
        #0x05: Fzg. unverschlossen, Schluessel steckt in Pos. 2, Zuendung aus
        #0x07: Fzg. unverschlossen, Schluessel steckt in Pos. 3, Zuendung an
        #0x0B: Fzg. unverschlossen, Schluessel steckt in Pos. 4, Zuendung an, Anlasser an
        #0x87: Fzg. unverschlossen, Schluessel steckt in Pos. 3, Zuendung an, Motor läuft 
            self.widget.displayIntValue(canId, "0", data[0], "%d")    
        elif canId == 0x635:
        #die ID 0x635 enthält in Byte 1 die Instrumentenhelligkeit bei eingeschaltetem Licht, ansonsten ist der Wert 0. Der Wertebereich liegt zwischen ca. 13 und 5D.
        #Byte 2 enthält immer FF.
            self.widget.displayIntValue(canId, "0", data[0], "%d")
        elif canId == 0x353: 
        #       ID 0x353, 6 Bytes
        #Byte 1:
        #- Status ???
        #Byte 2:
        #- Drehzahl unterer Wert UW
        #Byte 3:
        #- Drehzahl oberer Wert OW
        #Byte 4
        #- Ölthemperatur
        #Byte 5:
        #- Unbekannt
        #Byte 6:
        #- Unbekannt, jedoch zählt der Wert im Stand hoch auf 32 und geht bei Fahrt langsam und abhängig von der Standzeit auf 19 
            rpm=self.calcRpm(data)
            self.widget.displayIntValue(canId, "0", rpm, "%d")
            self.widget.setValueDashDisplayRPM(rpm)
            self.widget.displayIntValue(canId, "1", self.calcOilTemp(data), "%d")

        elif canId == 0x351:
        #ID 0x351, 8 Bytes
        #
        #Byte 1:
        #- 75 Zündung aus
        #- 80 Zündung ein
        # 82 Zündung ein, Rückwärtsgang eingelegt
        #Byte 2:
        #- Geschwindigkeit unterer Wert UW
        #Sobald der Motor läuft ändert sich der untere Wert auf 01 bei stehendem Fahrzeug!
        #Byte 3:
        #- Geschwindigkeit oberer Wert OW
        #Byte 4
        #- Unbekannt
        #Byte 5:
        #- Unbekannt
        #Byte 6:
        #- Außentemperatur 1 -> Dezimalwert von Byte 6 geteilt durch 2 minus 40
        #Byte 7:
        #- Außentemperatur 2 -> Dezimalwert von Byte 7 geteilt durch 2 minus 40
        #Byte 8:
        #- Schaltstufe bei Automatikgetriebe ? 
            vel=self.calcVelocity(data)
            self.widget.displayIntValue(canId, "0", vel, "%d")
            self.widget.setValueDashDisplayVel(vel)
            self.widget.displayFloatValue(canId, "1", self.calcOuterTemp(data), "%.1f")
            
        #else:
        #   print(self.dump(canId, dlc, data))
           
class CANSocketWorker(QThread):
    def __init__(self, parent=None): 
        QThread.__init__(self, parent)
        self.exiting = False
        self.test=False
        self.replayMode=False
        self.replayLines=None
        self.connected=False
        self.reconnecting=0
        
    def __del__(self):
        self.exiting = True
        self.wait()
        
    def setup(self, app, canMonitor, canDecoder, test):
        self.app = app
        self.canDecoder = canDecoder
        self.canMonitor=canMonitor
        self.test=test
        self.s=None
        self.connected=self.canMonitor.connectEnabled()
        if self.connected:
            self.connectCANDevice()
            if self.s==None:
                #initially failed
                self.canMonitor.connectFailed()
        self.start()
    
    def updateStatusLabel(self, text):
        self.emit(SIGNAL("updateStatus(QString)"), text)
        
    def reconnectCANDevice(self):
        #self.disconnectCANDevice()
        while self.reconnecting<42 and self.s==None and self.connected==False:
            self.sleep(1)
            self.s=None
            self.updateStatusLabel("reconnect try "+str(self.reconnecting))
            self.connectCANDevice()
            if self.s!=None and self.connected==True:
                self.reconnecting=0
                return
            self.reconnecting=self.reconnecting+1

        self.connected=False
        self.s=None
        self.reconnecting=0
        self.canMonitor.forceConnectDisabled()
    
    def setReplayMode(self, replayLines):
        self.replayMode=True
        self.replayLines=replayLines
    
    def disconnectCANDevice(self):
        if self.connected==True:
            if self.test==False:
                if self.s!=None:
                    try:
                        self.updateStatusLabel("disconnect")
                        self.s.close()
                        self.s=None
                        self.updateStatusLabel("disconnect ok")
                        self.canMonitor.connectFailed()
                    except socket.error:
                        self.updateStatusLabel("disconnect error")
                         
                    self.s=None
                    self.connected=False         
            else:
                self.connected=False
                self.updateStatusLabel("test disconnect")
                self.canMonitor.connectFailed()
                 
    def connectCANDevice(self):
        if self.s==None:
            if self.test==False:
                self.updateStatusLabel("connect")
                try:
                    # create CAN socket
                    self.s = socket.socket(socket.PF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
                
                    # setup canId filter
                    canId = 0
                    mask = 0
                    self.s.setsockopt(socket.SOL_CAN_RAW, socket.CAN_RAW_FILTER,
                                 struct.pack("II", canId, mask))
                
                    # enable/disable loopback
                    loopback = 0
                    self.s.setsockopt(socket.SOL_CAN_RAW, socket.CAN_RAW_LOOPBACK,
                                 struct.pack("I", loopback))
                
                    # bind to interface "canX" or "any")
                    # tuple is (interface, reserved(can_addr))
                    self.s.bind(("slcan0",))
                    self.updateStatusLabel("connect ok")
                    self.connected=True
                    self.canMonitor.connectSuccessful()
                except socket.error:
                    self.updateStatusLabel("connect error ")
                    self.s=None
                    self.connected=False
                    self.canMonitor.connectFailed()
                    return
            else:
                self.connected=True
                self.updateStatusLabel("test connect")
                self.canMonitor.connectSuccessful()
        
    def run(self):
        while not self.exiting and True:
            if self.replayMode==True:
                for x in self.replayLines:
                    self.canDecoder.scan_can_frame(x);
#                    self.app.processEvents()
                    self.usleep(1000)
                self.replayMode=False
                #self.replayLines=list()
                self.canMonitor.replayModeDone()
            if self.connected==True:
                if self.test==True:#
                    cf = struct.pack("IIBBBBBBBB", 0x353, 6, 0x0f, 0xd0, 0x1f, 0xb0, 0x0, 0x0, 0x0, 0x0)
                    self.canDecoder.scan_can_frame(cf);
                    cf = struct.pack("IIBBBBBBBB", 0x351, 8, 0x75, 0xad, 0x45, 0x0, 0x0, 0x7d, 0x0, 0x0)
                    self.canDecoder.scan_can_frame(cf);
                    cf = struct.pack("IIBBBBBBBB", 0x635, 3, 0x0, 0xff, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0)
                    self.canDecoder.scan_can_frame(cf);
                    cf = struct.pack("IIBBBBBBBB", 0x271, 2, 0x01, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0)
                    self.canDecoder.scan_can_frame(cf);
                    cf = struct.pack("IIBBBBBBBB", 0x371, 3, 0xc0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0)
                    self.canDecoder.scan_can_frame(cf);
                    cf = struct.pack("IIBBBBBBBB", 0x623, 8, 0x04, 0x07, 0x08, 0x09, 0x0, 0x0, 0x0, 0x0)
                    self.canDecoder.scan_can_frame(cf);
                    cf = struct.pack("IIBBBBBBBB", 0x571, 6, 0x94, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0)
                    self.canDecoder.scan_can_frame(cf);
#                    self.app.processEvents()
                    self.usleep(1000)
                elif self.s!=None:
                    try:
                        cf, addr = self.s.recvfrom(16)
                    except socket.error:
                        self.updateStatusLabel("connect error")
                        self.s=None
                        self.connected=False
                        self.reconnectCANDevice()                        
                        continue
                    self.canDecoder.scan_can_frame(cf)
#                    self.app.processEvents()
                    self.usleep(1000)
            else:
                self.canMonitor.clearAllLCD()
                self.sleep(1) 