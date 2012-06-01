'''
Created on Jun 1, 2012

@author: maxl
'''

from PyQt4.QtCore import Qt, pyqtSlot
from PyQt4.QtGui import QCommonStyle, QPushButton, QWidget, QVBoxLayout, QDialog, QTabWidget, QStyle, QHBoxLayout

class OptionsDialogTab(QWidget):
    def __init__(self, optionsConfig, parent):
        QWidget.__init__(self, parent)
        self.optionsConfig=optionsConfig
        
    def getTabName(self):
        return None
    
    def getOptionsConfig(self):
        return self.optionsConfig
    
    def addToTabWidget(self, tabWidget):
        tabWidget.addTab(self, self.getTabName())
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop)
        self.addToLayout(layout)
        
    def addToLayout(self, layout):
        None
        
    def setToOptionsConfig(self):
        None
        
class OptionsDialogTabManager():
    def __init__(self, optionsConfig, tabClassList, parent):
        self.tabList=list()
        self.tabClassList=tabClassList
        self.parent=parent
        self.optionsConfig=optionsConfig
        self.construct()
    
    def addTab(self, tab):
        self.tabList.append(tab)
        
    def getTabList(self):
        return self.tabList
    
    def addAllTabs(self, tabWidget):
        for tab in self.tabList:
            tab.addToTabWidget(tabWidget)

    def setToOptionsConfig(self):
        for tab in self.tabList:
            tab.setToOptionsConfig()
            
    def construct(self):
        for tabClass in self.tabClassList:
            instance = tabClass(self.optionsConfig, self.parent)
            self.addTab(instance)

class MyTabWidget(QTabWidget):
    def __init__(self, parent):
        QTabWidget.__init__(self, parent)
        self.setTabPosition(QTabWidget.East)
        font = self.font()
        font.setPointSize(14)
        self.setFont(font)
        
class OptionsDialog(QDialog):
    def __init__(self, optionsConfig, tabClassList, parent):
        QDialog.__init__(self, parent) 
        font = self.font()
        font.setPointSize(14)
        self.setFont(font)
        self.tabManager=OptionsDialogTabManager(optionsConfig, tabClassList, self)
        self.initUI()

    def getOptionsConfig(self):
        return self.tabManager.optionsConfig
    
    def initUI(self):
        style=QCommonStyle()
        top=QVBoxLayout()
        top.setSpacing(2)
            
        self.tabs = MyTabWidget(self)
        top.addWidget(self.tabs)
                            
        self.tabManager.addAllTabs(self.tabs)
        
        buttons=QHBoxLayout()
        buttons.setAlignment(Qt.AlignBottom|Qt.AlignRight)
        
        self.cancelButton=QPushButton("Cancel", self)
        self.cancelButton.clicked.connect(self._cancel)
        self.cancelButton.setIcon(style.standardIcon(QStyle.SP_DialogCancelButton))
        buttons.addWidget(self.cancelButton)

        self.okButton=QPushButton("Ok", self)
        self.okButton.clicked.connect(self._ok)
        self.okButton.setDefault(True)
        self.okButton.setIcon(style.standardIcon(QStyle.SP_DialogOkButton))
        buttons.addWidget(self.okButton)
        
        top.addLayout(buttons)
        self.setLayout(top)
        self.setWindowTitle('Options')
        self.setGeometry(0, 0, 400, 500)
                        
    @pyqtSlot()
    def _cancel(self):
        self.done(QDialog.Rejected)
    
    @pyqtSlot()
    def _ok(self):
        self.tabManager.setToOptionsConfig()
        self.done(QDialog.Accepted)    
