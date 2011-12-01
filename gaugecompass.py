'''
Created on Nov 24, 2011

@author: maxl
'''

from PyQt4.QtCore import Qt, QSize, QPoint
from PyQt4.QtGui import QWidget, QPixmap, QSizePolicy, QPainter, QPen, QHBoxLayout, QApplication

import sys
import signal
import math

class QtPngCompassGauge(QWidget):
    def __init__(self, parent, skin, tachoImage):
        QWidget.__init__(self, parent)
        self.m_value=0
        self.m_skin=skin
        self.tachoImage=tachoImage
        self.backgroundPic = QPixmap("images/"+self.m_skin+"/"+self.tachoImage)

        self.init()
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        
    def init(self):
        self.updateGeometry()
        self.update()        

    def setValue(self, value):
        self.m_value = value
        self.update()

    def value(self):
        return self.m_value


    def paintEvent(self, event):
        painter=QPainter(self) 

        painter.drawPixmap(self.rect(), self.backgroundPic, self.backgroundPic.rect())

        pen=QPen()
        pen.setCapStyle(Qt.RoundCap);
        pen.setWidthF(4.0)
        pen.setColor(Qt.red)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        spacing = 30
        contentRect = self.rect().adjusted(spacing, spacing, -spacing, -spacing)

        math_pi = 3.14159265358979323846
        degree = self.m_value -90
        degree = degree * math_pi/180
        radius = (contentRect.width() - spacing * 0.5) * 0.5
        vec=QPoint(radius * math.cos(degree),
                radius * math.sin(degree))
        painter.drawLine(contentRect.center(), contentRect.center() + vec)
                    
    def minimumSizeHint(self):
        return QSize(100, 100)

    def sizeHint(self):
        return QSize(400, 400)

    def setShowOverlay(self, show):
        self.m_showOverlay = show
        self.update();

class Example(QWidget):
    
    def __init__(self):
        super(Example, self).__init__()
        
        self.initUI()
        
    def initUI(self):
        hbox = QHBoxLayout()
        gauge=QtPngCompassGauge(self, "compass", "compass.png")
        gauge.setValue(0)
        gauge.setMaximumSize(300, 300)
        #gauge.setShowOverlay(False)
        hbox.addWidget(gauge)

        gauge=QtPngCompassGauge(self, "compass", "compass.png")
        gauge.setValue(45)
        gauge.setMaximumSize(300, 300)
        #gauge.setShowOverlay(F2lse)
        hbox.addWidget(gauge)
#        
        gauge=QtPngCompassGauge(self, "compass", "compass.png")
        gauge.setValue(360)
        gauge.setMaximumSize(300, 300)
        #gauge.setShowOverlay(False)
        hbox.addWidget(gauge)
        self.setLayout(hbox)
        
        self.setGeometry(0, 0, 900, 400)
        self.setWindowTitle('Tacho Test')
        self.show()
        
def main(argv): 
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    _ = Example()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main(sys.argv)
   
