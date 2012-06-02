'''
Created on Nov 24, 2011

@author: maxl
'''

from PyQt4.QtCore import Qt, QRectF, QPointF, QSize
from PyQt4.QtGui import QApplication, QWidget, QSizePolicy, QPainter, QHBoxLayout
from PyQt4.QtSvg import QSvgRenderer

import sys
import signal

class QtSvgDialGauge(QWidget):
    def __init__(self, parent, skin):
        QWidget.__init__(self, parent)
        self.m_minimum=0
        self.m_maximum=100
        self.m_value=0
        self.m_startAngle=0
        self.m_endAngle=100
        self.m_originX=0.5
        self.m_originY=0.5
        self.m_showOverlay=True
        self.m_skin=skin

        self.init()
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        
    def init(self):
        self.m_backgroundRenderer = QSvgRenderer("images/"+self.m_skin+"/background.svg", self)
        self.m_needleShadowRenderer = QSvgRenderer("images/"+self.m_skin+"/needle_shadow.svg", self)
        self.m_needleRenderer = QSvgRenderer("images/"+self.m_skin+"/needle.svg", self)
        self.m_overlayRenderer = QSvgRenderer("images/"+self.m_skin+"/overlay.svg", self)
        self.updateGeometry()
        self.update()        

    def setValue(self, value):
        if value < self.m_minimum:
            value = self.m_minimum
        elif value > self.m_maximum:
            value = self.m_maximum
    
        self.m_value = value
        self.update()

    def setMinimum(self, minimum):
        self.m_minimum = minimum
        if self.m_value < self.m_minimum:
            self.m_value = self.m_minimum;
    
        self.update()

    def setMaximum(self, maximum):
        self.m_maximum = maximum;
        if self.m_value > self.m_maximum:
            self.m_value = self.m_maximum
    
        self.update()

    def setNeedleOrigin(self, x, y):
        self.m_originX = min(1.0, max(0.0, x))
        self.m_originY = min(1.0, max(0.0, y))

    def setStartAngle(self, angle):
        self.m_startAngle = angle

    def setEndAngle(self, angle):
        self.m_endAngle = angle

    def value(self):
        return self.m_value

    def minimum(self):
        return self.m_minimum

    def maximum(self):
        return self.m_maximum

    def needleOriginX(self):
        return self.m_originX

    def needleOriginY(self):
        return self.m_originY

    def startAngle(self):
        return self.m_startAngle

    def endAngle(self):
        return self.m_endAngle

    def availableRect(self, renderObject):
        svgSize = renderObject.defaultSize()
        svgSize.scale(self.size(), Qt.KeepAspectRatio)
        return QRectF(0.0, 0.0, svgSize.width(), svgSize.height())

    def paintEvent(self, event):
        painter=QPainter(self) 
        angleSpan = self.m_endAngle - self.m_startAngle
        valueSpan = self.m_maximum - self.m_minimum
        rotate = (self.m_value - self.m_minimum) / valueSpan * angleSpan + self.m_startAngle

        targetRect = self.availableRect(self.m_backgroundRenderer)
        painter.translate((self.width() - targetRect.width()) / 2.0, (self.height() - targetRect.height()) / 2.0)
        painter.save()

        self.m_backgroundRenderer.render(painter, targetRect)

        targetRect = self.availableRect(self.m_needleRenderer)
        targetRect.moveTopLeft(QPointF(-targetRect.width() * self.m_originX,
                                  -targetRect.height() * self.m_originY))

        painter.translate(targetRect.width() * self.m_originX,
                      targetRect.height() * self.m_originY)

        painter.save()
        painter.translate(2, 4)
        painter.rotate(rotate)
        self.m_needleShadowRenderer.render(painter, targetRect)

        painter.restore()
        painter.rotate(rotate)
        self.m_needleRenderer.render(painter, targetRect)

        painter.restore();
        if self.m_showOverlay:
            targetRect = self.availableRect(self.m_overlayRenderer)
            self.m_overlayRenderer.render(painter, targetRect)

    def minimumSizeHint(self):
        return QSize(100, 100)

    def sizeHint(self):
        return QSize(400, 400)

    def setShowOverlay(self, show):
        self.m_showOverlay = show
        self.update();

class Example(QWidget):
    
    def __init__(self, parent):
        QWidget.__init__(self, parent)
        
        self.initUI()
        
    def initUI(self):
        hbox = QHBoxLayout()
        gauge=QtSvgDialGauge(self, "tacho")
        gauge.setNeedleOrigin(0.486, 0.466)
        gauge.setMinimum(0)
        gauge.setMaximum(360)
        gauge.setStartAngle(-130)
        gauge.setEndAngle(133)
        gauge.setValue(50)
        gauge.setMaximumSize(200, 200)
        #gauge.setShowOverlay(False)
        hbox.addWidget(gauge)

        gauge1=QtSvgDialGauge(self, "thermometer")
        gauge1.setNeedleOrigin(0.456, 0.459)
        gauge1.setMinimum(0)
        gauge1.setMaximum(360)
        gauge1.setStartAngle(-90)
        gauge1.setEndAngle(90)
        gauge1.setValue(180)
        gauge1.setMaximumSize(200, 200)
        #gauge.setShowOverlay(F2lse)
        hbox.addWidget(gauge1)
        
        gauge2=QtSvgDialGauge(self, "voltmeter")
        gauge2.setNeedleOrigin(0.5, .83596590)
        gauge2.setMinimum(0)
        gauge2.setMaximum(360)
        gauge2.setStartAngle(-42)
        gauge2.setEndAngle(42)
        gauge2.setValue(180)
        gauge2.setMaximumSize(200, 200)
        #gauge.setShowOverlay(False)
        hbox.addWidget(gauge2)
        self.setLayout(hbox)
        
        self.setGeometry(0, 0, 700, 300)
        self.setWindowTitle('Tacho')
        self.show()
        
def main(argv): 
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    _ = Example(None)

    sys.exit(app.exec_())

if __name__ == "__main__":
    main(sys.argv)
   