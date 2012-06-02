'''
Created on Nov 24, 2011

@author: maxl
'''

from PyQt4.QtCore import Qt, QSize, QPoint, QRect
from PyQt4.QtGui import QWidget, QPixmap, QSizePolicy, QPainter, QPen, QHBoxLayout, QApplication

import sys
import signal
import math

class QtPngDialGauge(QWidget):
    def __init__(self, parent, skin, tachoImage):
        QWidget.__init__(self, parent)
        self.m_minimum=0
        self.m_maximum=100
        self.m_value=0
        self.m_startAngle=0
        self.m_skin=skin
        self.tachoImage=tachoImage
        self.backgroundPic = QPixmap("images/"+self.m_skin+"/"+self.tachoImage)

        self.init()
        
    def init(self):
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)        
        self.updateGeometry()
#        self.update()        

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

    def setStartAngle(self, angle):
        self.m_startAngle = angle

    def value(self):
        return self.m_value

    def minimum(self):
        return self.m_minimum

    def maximum(self):
        return self.m_maximum

    def startAngle(self):
        return self.m_startAngle

    def paintEvent(self, event):
        painter=QPainter(self) 

        minSize=min(self.rect().width(), self.rect().height())
        myRect=QRect(self.rect().x(), self.rect().y(), minSize, minSize)
        painter.drawPixmap(myRect, self.backgroundPic, self.backgroundPic.rect())
        
        pen=QPen()
        pen.setCapStyle(Qt.RoundCap);
        pen.setWidthF(4.0)
        pen.setColor(Qt.red)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        spacing = 40
        contentRect = myRect.adjusted(spacing, spacing, -spacing, -spacing)

        valueInPercent = (self.m_value - self.m_minimum) / (self.m_maximum - self.m_minimum)
        math_pi = 3.14159265358979323846
        degree = (self.m_startAngle + 90) - valueInPercent * 2.0 * self.m_startAngle
        degree = degree * math_pi / 180.0
        radius = (contentRect.width() - spacing * 0.5) * 0.5
        vec=QPoint(radius * math.cos(degree),
                radius * -math.sin(degree))
        painter.drawLine(contentRect.center(), contentRect.center() + vec)
                    
    def minimumSizeHint(self):
        return QSize(200, 200)


    def setShowOverlay(self, show):
        self.m_showOverlay = show
        self.update();

class Example(QWidget):
    
    def __init__(self, parent):
        QWidget.__init__(self, parent)
        
        self.initUI()
        
    def initUI(self):
        hbox = QHBoxLayout()
        gauge=QtPngDialGauge(self, "tacho3", "tacho3.png")
        gauge.setMinimum(20)
        gauge.setMaximum(220)
        gauge.setStartAngle(135)
        gauge.setValue(20)
#        gauge.setMaximumSize(300, 300)
        #gauge.setShowOverlay(False)
        hbox.addWidget(gauge)

        gauge1=QtPngDialGauge(self, "rpm", "rpm.png")
        gauge1.setMinimum(0)
        gauge1.setMaximum(8000)
        gauge1.setStartAngle(125)
        gauge1.setValue(4000)
#        gauge.setMaximumSize(300, 300)
        #gauge.setShowOverlay(F2lse)
        hbox.addWidget(gauge1)
#        
#        gauge=QtPngDialGauge(self, "compass", "compass.png")
#        gauge.setMinimum(0)
#        gauge.setMaximum(360)
#        gauge.setStartAngle(-180)
#        gauge.setValue(245)
##        gauge.setMaximumSize(300, 300)
#        #gauge.setShowOverlay(False)
#        hbox.addWidget(gauge)
        self.setLayout(hbox)
        
        self.setGeometry(0, 0, 600, 300)
        self.setWindowTitle('Tacho Test')
        self.show()
        
def main(argv): 
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    _ = Example(None)

    sys.exit(app.exec_())

if __name__ == "__main__":
    main(sys.argv)
   