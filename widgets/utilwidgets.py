'''
Created on Jun 21, 2012

@author: maxl
'''

from PyQt4.QtCore import QUrl, pyqtSlot
from PyQt4.QtGui import QLabel, QTabWidget, QDesktopServices, QPushButton


class LinkLabel(QLabel):
    def __init__(self, parent):
        QLabel.__init__(self, parent)
        self.setOpenExternalLinks(True)
    
    def searchGoogle(self, searchString):
        self.setText('<a href="http://www.google.com/search?q=%s">Google %s</a>'%(searchString, searchString))

class MyTabWidget(QTabWidget):
    def __init__(self, parent):
        QTabWidget.__init__(self, parent)
        self.setTabPosition(QTabWidget.East)
        font = self.font()
        font.setPointSize(14)
        self.setFont(font)
        
class SearchButton(QPushButton):
    def __init__(self, parent):
        QPushButton.__init__(self, parent)
        self.clicked.connect(self._search)

    def setSearchString(self, searchString):
        self.searchString=searchString
        
    @pyqtSlot()
    def _search(self):
        if self.searchString!=None:
            QDesktopServices.openUrl(QUrl("http://www.google.com/search?q=%s"%(self.searchString), QUrl.TolerantMode))
