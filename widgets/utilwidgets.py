'''
Created on Jun 21, 2012

@author: maxl
'''

from PyQt5.QtCore import QUrl, pyqtSlot
from PyQt5.QtWidgets import QLabel, QTabWidget, QPushButton
from PyQt5.QtGui import QDesktopServices


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

class WebButton(QPushButton):
    def __init__(self, parent):
        QPushButton.__init__(self, parent)
        self.clicked.connect(self._openURL)

    def setWebTags(self, urlTags):
        self.urlTags=urlTags
        
    @pyqtSlot()
    def _openURL(self):
        if self.urlTags!=None:
            if "website" in self.urlTags:
                QDesktopServices.openUrl(QUrl(self.urlTags["website"], QUrl.TolerantMode))
            if "url" in self.urlTags:
                QDesktopServices.openUrl(QUrl(self.urlTags["url"], QUrl.TolerantMode))
            if "wikipedia" in self.urlTags:
                url="http://www.wikipedia.org/wiki/"+self.urlTags["wikipedia"]
                QDesktopServices.openUrl(QUrl(url, QUrl.TolerantMode))
