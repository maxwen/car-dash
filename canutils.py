#!/usr/bin/env python3

import struct
import socket

from PyQt4.QtCore import QThread, SIGNAL
from collections import deque

canIdleState="idle"
canRunState="run"
canStoppedState="stopped"
        
class CANDecoder:
    def __init__(self, widget):
        self.widget = widget
        self.rpmValueList=deque([0 ,0, 0], 3)
        
    def hex2binary(self, hexValue):
        return bin(hexValue)[2:].rjust(8, '0')

#    def testBit(self, hexValue, bit):
#        return self.hex2binary(hexValue)[:-bit] != '0'

    def getBit(self, hexValue, bit):
        b=self.hex2binary(hexValue);
        return int(b[len(b)-1-bit])
    
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
        rpm=((data[2] << 8) + data[1]) / 4
        self.rpmValueList.append(rpm)
        rpmValue=self.rpmValueList[0]+self.rpmValueList[1]+self.rpmValueList[2]
        rpmValueAverage=int((rpmValue/len(self.rpmValueList))/10)*10
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
        self.widget.addToLogView2([canId, dlc, data])
       
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
        #- Unbekannt, evtl. Wegstreckenimpuls unter Wert
        #Byte 5:
        #- Unbekannt, evtl. Wegstreckenimpuls oberer Wert
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
            self.widget.displayIntValue(canId, "2", data[3], "%d")
            self.widget.displayIntValue(canId, "3", data[4], "%d")
            
        elif canId==0x3e5:
#            Byte 1
#            Bit 0: SH/SL via Funk eingeschaltet (Der Moment des Einschaltens! Wird 5x gesendet).
#            Bit 1: SH/SL via Funk ausgeschaltet (Der Moment des Ausschaltens! Wird 5x gesendet)
#            Bit 2: Explizit SH via Funk einschalten (Der Moment des Einschaltens! Wird 5x gesendet)
#            Bit 3: Explizit SL via Funk einschalten (Der Moment des Einschaltens! Wird 5x gesendet)
#            Bit 4: Befehl "Klimaanlage ausschalten"
#            Bit 5: SH-modus wird gerade aktiviert
#            Bit 6: SH wird gerade programmiert
#            Bit 7: Komfort CAN aufwecken
#                      
#            Byte 2
#            Bit 0: Fzg.- Gebläse einschalten. (0=Geb. aus; 1=Geb. an)
#            Bit 1: Kontroll LED einschalten.
#            Bit 2: Verbrennungszuheizer einschalten (0=Aus; 1=an)
#            Bit 3: Wasserpumpe einschalten (Nur der befehl zur Climatic / Climatronic um die Pumpe einzuschalten. Klimaanlage regelt den Rest ohne CAN )
#            Bit 4 bis 6: Fehlerstatus der SH: 0=Kein Fehler; 1=Battrie Leer; 2=Wenig Sprit im Tank; 3=Heizgerät defekt; 4=Crash erkannt; 5=sonstige Störung; 6=Überhitzung;
#            Bit 7: Fehler im Fehlerspeicher abgelegt.
#            
#            Byte 3 und Byte 4
#            Bit 0 bis 7 (Byte3) und Bit 0 bis 5 (Byte 4):Kraftstoffvorrat / Kraftstoffverbrauch.
#            Anmerkung: Kraftstoffvorrat / Verbrauch in 1ml Schritten. Ist echt sau genau das Teil.
#            
#            Byte 4
#            Bit 6: SH Status: 1 = Steuergerät ist Standheizung (Kann auch ohne Klemme 15 betrieben werden); 0 = Steuergerät ist ein Zuheizer und kann ausschließlich mit Klemme 15 Betrieben werden.
#            Bit 7: Standard = 0; Wenn 1, liegt ein Fehler vor (Kemme 30 war kurz weg)
#            
#            Byte 5
#            Bit 0 bis Bit 7: Heizleistung in 1 Watt Schritten.
#            
#            
#            Byte 6
#            Bit 0: Heizkreistemperatur -> Bereich von Minus 48°C bis Plus 142,5°C, Teilung 0,75 °C; Wird 0xFF gesendet, so liegt ein Fehler vor.
#            Bit 1 bis 7: Nicht verwendet.
#            
#            Byte 7
#            Bit 0: Kraftstoffpumpe eingeschaltet.
#            Bit 1: Wasser wurde erwärmt und ist nun warm.
#            Bit 2 bis Bit 7: Nicht verwendet
#            
#            Byte 8
#            Bit 0: 1 = SL ist aktiv; 0 = SL nicht aktiv.
#            Bit 1 bis 7: Nicht verwendet
#            self.widget.displayIntValue(canId, "0", data[1], "%d")
            self.widget.displayBinValue(canId, "0", self.hex2binary(data[0]), "%8s")
            self.widget.displayBinValue(canId, "1", self.hex2binary(data[1]), "%8s")
            self.widget.displayBinValue(canId, "2", self.hex2binary(data[2]), "%8s")
            self.widget.displayBinValue(canId, "3", self.hex2binary(data[3]), "%8s")
            self.widget.displayBinValue(canId, "4", self.hex2binary(data[4]), "%8s")
            
            value=self.getBit(data[1], 1) + self.getBit(data[1], 2)
            self.widget.displayIntValue(canId, "5", value, "%d")

        elif canId==0x591:
            value=0
            if data[1]==0x02:
                value=1
            if data[1]==0x04:
                value=2

            self.widget.displayIntValue(canId, "0", value, "%d")

        elif canId==0x5d1:
            # scheibnwischer
            # byte 1 
            # 0x0 
            # 0x1 interval
            # 0x5 inormale geschwindigkeit
            # 0x9 schnelle geschwindigkeit
            value=0
            if data[0]==0x01:
                value=1
            if data[0]==0x05:
                value=2
            if data[0]==0x09:
                value=2
            self.widget.displayIntValue(canId, "0", value, "%d")
        
        elif canId==0x621:
            self.widget.displayBinValue(canId, "0", self.hex2binary(data[0]), "%8s")
            self.widget.displayIntValue(canId, "1", data[1], "%d")
            self.widget.displayIntValue(canId, "2", data[2], "%d")
        #else:
        #   print(self.dump(canId, dlc, data))
           
class CANSocketWorker(QThread):
    def __init__(self, parent): 
        QThread.__init__(self, parent)
        self.exiting = False
        self.test=False
        self.replayMode=False
        self.replayLines=None
        self.connected=False
        self.reconnectTry=0
        self.reconnecting=False
        
    def __del__(self):
        self.exiting = True
        self.wait()
        
    def stop(self):
        self.exiting=True
        if self.connected==True:
            self.disconnectCANDevice()
        self.wait()
        
    def setup(self, app, connect, test, replayMode, replayLines):
        self.updateStatusLabel("CAN thread setup")

        self.exiting = False
        self.app = app
        self.test=test
        self.replayMode=replayMode
        self.replayLines=replayLines
        self.s=None
        if connect and self.replayMode==False:
            self.connectCANDevice()
        
        if self.connected==True or self.replayMode==True:
            self.updateStatusLabel("CAN thread started")
            self.start()
    
    def updateStatusLabel(self, text):
        self.emit(SIGNAL("updateStatus(QString)"), text)
#        print(text)
        
    def updateCANThreadState(self, state):
        self.emit(SIGNAL("updateCANThreadState(QString)"), state)

    def clearAllLCD(self):
        self.emit(SIGNAL("clearAllLCD()"))
        
    def connectCANFailed(self):
        self.emit(SIGNAL("connectCANFailed()"))

    def replayModeDone(self):
        self.emit(SIGNAL("replayModeDone()"))
                 
    def processCANData(self, can_frame):
        self.emit(SIGNAL("processCANData(PyQt_PyObject)"), can_frame)        
         
    def reconnectCANDevice(self):
        self.reconnecting=True
        while self.reconnectTry<42 and self.s==None and self.connected==False and self.exiting==False:
            self.sleep(1)
            self.s=None
            self.connectCANDevice()
            if self.s!=None and self.connected==True:
                self.reconnectTry=0
                self.reconnecting=False
                return
            self.reconnectTry=self.reconnectTry+1

        self.connected=False
        self.s=None
        self.reconnectTry=0
        self.reconnecting=False
        self.exiting=True
        self.connectCANFailed()
        self.updateStatusLabel("CAN reconnect failed - exiting thread")
        
    def disconnectCANDevice(self):
        if self.connected==True:
            if self.test==False:
                if self.s!=None:
                    try:
                        self.s.close()
                        #self.s=None
                        self.updateStatusLabel("CAN disconnect ok")
                    except socket.error:
                        self.updateStatusLabel("CAN disconnect error")
                         
                    self.s=None
                    self.connected=False         
            else:
                self.connected=False
                self.updateStatusLabel("CAN test disconnect")
                             
    def connectCANDevice(self):
        if self.s==None:
            if self.test==False:
                try:
                    # create CAN socket
                    self.s = socket.socket(socket.PF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
                    self.s.settimeout(3)
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
                    self.updateStatusLabel("CAN connect ok")
                    self.connected=True
                except socket.error:
                    if self.reconnecting==True:
                        self.updateStatusLabel("CAN reconnect try "+str(self.reconnectTry))
                        self.s=None
                        self.connected=False
                    else:
                        self.updateStatusLabel("CAN connect error")
                        self.s=None
                        self.connected=False
                        self.connectCANFailed()
            else:
                self.connected=True
                self.updateStatusLabel("CAN test connect")
        
    def run(self):
        self.updateCANThreadState(canRunState)

        while not self.exiting and True:
            if self.replayMode==True:
                self.updateStatusLabel("CAN replay started")
                self.updateCANThreadState(canRunState)

                for x in self.replayLines:
                    self.processCANData(x)
#                    self.canDecoder.scan_can_frame(x);
                    self.msleep(10)
                    if self.exiting==True:
                        break

                self.updateStatusLabel("CAN replay stopped")
                self.replayMode=False
                self.replayLines=list()
                self.replayModeDone()
                self.exiting=True
                continue
            if self.connected==True:
                if self.test==True:
                    cf = struct.pack("IIBBBBBBBB", 0x353, 6, 0x0f, 0xd0, 0x1f, 0xb0, 0x0, 0x0, 0x0, 0x0)
#                    self.canDecoder.scan_can_frame(cf);
                    self.processCANData(cf)

                    cf = struct.pack("IIBBBBBBBB", 0x351, 8, 0x75, 0xad, 0x45, 0x0, 0x0, 0x7d, 0x0, 0x0)
#                    self.canDecoder.scan_can_frame(cf);
                    self.processCANData(cf)

                    cf = struct.pack("IIBBBBBBBB", 0x635, 3, 0x0, 0xff, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0)
#                    self.canDecoder.scan_can_frame(cf);
                    self.processCANData(cf)

                    cf = struct.pack("IIBBBBBBBB", 0x271, 2, 0x01, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0)
#                    self.canDecoder.scan_can_frame(cf);
                    self.processCANData(cf)

                    cf = struct.pack("IIBBBBBBBB", 0x371, 3, 0xc0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0)
#                    self.canDecoder.scan_can_frame(cf);
                    self.processCANData(cf)

                    cf = struct.pack("IIBBBBBBBB", 0x623, 8, 0x04, 0x07, 0x08, 0x09, 0x0, 0x0, 0x0, 0x0)
#                    self.canDecoder.scan_can_frame(cf);
                    self.processCANData(cf)

                    cf = struct.pack("IIBBBBBBBB", 0x571, 6, 0x94, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0)
#                    self.canDecoder.scan_can_frame(cf);
                    self.processCANData(cf)

                    cf = struct.pack("IIBBBBBBBB", 0x3e5, 5, 0xe0, 0x04 , 0x4e, 0xc1, 0x27, 0x0, 0x0, 0x0)
#                    self.canDecoder.scan_can_frame(cf);
                    self.processCANData(cf)

                    cf = struct.pack("IIBBBBBBBB", 0x591, 3, 0x0, 0x4, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0)
#                    self.canDecoder.scan_can_frame(cf);
                    self.processCANData(cf)

                    cf = struct.pack("IIBBBBBBBB", 0x5d1, 2, 0x5, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0)
#                    self.canDecoder.scan_can_frame(cf);
                    self.processCANData(cf)
                    
                    self.msleep(10)
                    self.updateCANThreadState(canIdleState)
                elif self.s!=None:
                    try:
                        cf, addr = self.s.recvfrom(16)
                        self.updateCANThreadState(canRunState)
                    except socket.timeout:
                        self.updateStatusLabel("CAN thread socket.timeout")
                        self.updateCANThreadState(canIdleState)
                        continue
 
                    except socket.error:
                        if self.exiting==True:
                            self.updateStatusLabel("CAN thread stop request")
                            continue
                        self.updateStatusLabel("CAN connection lost")
                        self.updateCANThreadState(canIdleState)
                        self.s=None
                        self.connected=False
                        self.reconnectCANDevice()                        
                        continue
#                    self.canDecoder.scan_can_frame(cf)
                    self.processCANData(cf)
                    #self.msleep(10)
            else:
                self.updateStatusLabel("CAN thread idle")
                self.updateCANThreadState(canIdleState)
                self.clearAllLCD()
                self.msleep(1000) 

        self.updateStatusLabel("CAN thread stopped")
        self.updateCANThreadState(canStoppedState)
        self.clearAllLCD()
