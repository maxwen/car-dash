'''
Created on Nov 25, 2011

@author: maxl
'''

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.QtSvg import *

import sys
import signal
import math

class QtBasicDialGauge(QWidget):
    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.init()
        self.update()

    def init(self):
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.m_value = 0
        self.m_minimum = 0
        self.m_maximum = 100


    def paintEvent(self, event):
        spacing = 15
        contentRect = self.rect().adjusted(spacing, spacing, -spacing, -spacing)

        painter=QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        pen=QPen()
        pen.setCapStyle(Qt.RoundCap);
        pen.setWidthF(1.0 + self.width() / 15.0)
        pen.setColor(Qt.white)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)


        painter.drawArc(contentRect, (-45)*16, (2*135)*16)
        valueInPercent = (self.m_value - self.m_minimum) / (self.m_maximum - self.m_minimum)
        math_pi = 3.14159265358979323846
        degree = (135 + 90) - valueInPercent * 2.0 * 135.0
        degree = degree * math_pi / 180.0
        radius = (contentRect.width() - spacing * 0.5) * 0.5
        vec=QPoint(radius * math.cos(degree),
                radius * -math.sin(degree))
        painter.drawLine(contentRect.center(), contentRect.center() + vec)

    def sizeHint(self):
        return QSize(50, 50)

    def maximum(self):
        return self.m_maximum

    def minimum(self):
        return self.m_minimum

    def value(self):
        return self.m_value
    
    def setValue(self, value):
        if value >= self.m_minimum and value <= self.m_maximum:
            self.m_value = value
            self.update()
    
    def setMaximum(self, maximum):
        self.m_maximum = maximum
        if self.m_maximum < self.m_minimum:
            self.m_minimum = self.m_maximum
    
        self.update()

    def setMinimum(self, minimum):
        self.m_minimum = minimum
        if self.m_minimum > self.m_maximum:
            self.m_maximum = self.m_minimum
        self.update()

    def setRange(self, minimum, maximum):
        if minimum < maximum:
            self.setMinimum(minimum)
            self.setMaximum(maximum)

class Example(QWidget):
    
    def __init__(self):
        super(Example, self).__init__()
        
        self.initUI()
        
    def initUI(self):
        vbox = QVBoxLayout()
        gauge=QtBasicDialGauge(self)
        gauge.setRange(0, 100)
        gauge.setValue(50)
        gauge.setMaximumSize(500, 500)
        vbox.addWidget(gauge)

        self.setLayout(vbox)
        
        self.setGeometry(0, 0, 500, 500)
        self.setWindowTitle('Tacho')
        self.show()
        
def main(argv): 
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    ex = Example()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main(sys.argv)