'''
Created on Jan 17, 2012

@author: maxl
'''

#from fnmatch import fnmatch
from utils.fnmatch import fnmatch
import re
import os

from PyQt5.QtWidgets import QCommonStyle, QPushButton, QWidget, QVBoxLayout, QDialog, QTabWidget, QStyle, QHBoxLayout, QTreeView, QRadioButton, QTabWidget, QFormLayout, QComboBox, QAbstractItemView, QCommonStyle, QStyle, QProgressBar, QInputDialog, QLineEdit, QHeaderView, QTableView, QDialog, QHBoxLayout, QApplication, QLabel, QMenu, QAction, QMainWindow, QTabWidget, QCheckBox, QVBoxLayout, QPushButton, QWidget, QSizePolicy
from PyQt5.QtCore import QThreadPool, QRunnable, pyqtSignal, QUrl, QModelIndex, QVariant, QAbstractItemModel, QAbstractTableModel, Qt, QPoint, QSize, pyqtSlot, pyqtSignal, QRect, QThread, QItemSelectionModel
from PyQt5.QtGui import QDesktopServices, QValidator, QIcon, QPalette, QPixmap, QPainter, QPen
from osmparser.osmdataaccess import OSMDataAccess, Constants
from osmstyle import OSMStyle
from routing.osmrouting import OSMRoutingPoint, OSMRoute
from dialogs.options import OptionsDialogTab, OptionsDialog
from widgets.utilwidgets import SearchButton, WebButton

settings=dict()

def loadDialogSettings(config):
    section="dialog"
    if config.hasSection(section):
        for key, value in config.items(section):
            if key[:6]==section:
                if len(value)==0:
                    value=None
                elif value=="True":
                    value=True
                elif value=="False":
                    value=False
                elif value=="None":
                    value=None
                elif value[0]=="[":
                    valueList=list()
                    if "," in value:
                        valueItems=value[1:-1].split(", ")
                        for valueItem in valueItems:
                            valueList.append(int(valueItem))
                    else:
                        try:
                            valueList.append(int(value[1:-1]))
                        except ValueError:
                            None
                    value=valueList
                else:
                    try:
                        value=int(value)
                    except ValueError:
                        None

                settings[key[7:]]=value

def saveDialogSettings(config):
    section="dialog"
    config.removeSection(section)
    config.addSection(section)
    for key, value in settings.items():
        config.set(section, section+"."+key, str(value))

class Worker(QRunnable):
    '''
    Worker thread

    Inherits from QRunnable to handler worker thread setup, signals and wrap-up.

    :param callback: The function callback to run on this worker thread. Supplied args and
                     kwargs will be passed through to the runner.
    :type callback: function
    :param args: Arguments to pass to the callback function
    :param kwargs: Keywords to pass to the callback function

    '''

    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    @pyqtSlot()
    def run(self):
        '''
        Initialise the runner function with passed args, kwargs.
        '''
        self.fn(*self.args, **self.kwargs)

class OSMAdressTableModel(QAbstractTableModel):
    def __init__(self, adminAreaDict, reverseAdminAreaDict, parent):
        QAbstractTableModel.__init__(self, parent)
        self.adminAreaDict=adminAreaDict
        self.reverseAdminAreaDict=reverseAdminAreaDict
        self.loading = False

    def rowCount(self, parent):
        return len(self.streetList)

    def columnCount(self, parent):
        return 3

    def data(self, index, role):
        if role == Qt.TextAlignmentRole:
            return Qt.AlignLeft|Qt.AlignVCenter
        elif role != Qt.DisplayRole:
            return None

        if self.loading is True:
            if index.column()==0:
                return self.streetList[0]
            return ""
        if index.row() >= len(self.streetList):
            return ""
        (_, _, _, cityId, _, streetName, houseNumber, lat, lon)=self.streetList[index.row()]
        city=None
        if cityId!=None:
            city=self.adminAreaDict[cityId]

        if index.column()==0:
            return streetName
        elif index.column()==1:
            if houseNumber!=None:
                return houseNumber
            return ""
        elif index.column()==2:
            if city!=None:
                return city
            return ""
#        elif index.column()==3:
#            if postCode!=None:
#                return postCode
#            return ""
    def headerData(self, col, orientation, role):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                if col==0:
                    return "Street"
                elif col==1:
                    return "Number"
                elif col==2:
                    return "City"
#                elif col==3:
#                    return "Post Code"
            elif role == Qt.TextAlignmentRole:
                return Qt.AlignLeft
        return None


    def update(self, streetList):
        self.beginResetModel()
        self.loading = False
        self.streetList=streetList
        self.endResetModel()

    def setLoading(self):
        self.beginResetModel()
        self.loading = True
        self.streetList=list()
        self.streetList.append("Loading...")
        self.endResetModel()

    def isLoading(self):
        return self.loading

class OSMAdressTableModelCity(QAbstractTableModel):
    def __init__(self, parent):
        QAbstractTableModel.__init__(self, parent)

    def rowCount(self, parent):
        return len(self.cityList)

    def columnCount(self, parent):
        return 1

    def data(self, index, role):
        if role == Qt.TextAlignmentRole:
            return Qt.AlignLeft|Qt.AlignVCenter
        elif role != Qt.DisplayRole:
            return None

        if index.row() >= len(self.cityList):
            return ""
        cityId, cityName=self.cityList[index.row()]
        if index.column()==0:
            return cityName
#        elif index.column()==1:
#            return postCode

    def headerData(self, col, orientation, role):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                if col==0:
                    return "City"
#                elif col==1:
#                    return "Post Code"
            elif role == Qt.TextAlignmentRole:
                return Qt.AlignLeft
        return None


    def update(self, cityList, cityModel):
        self.beginResetModel()
        self.cityList=cityList
        self.cityModel=cityModel
        self.endResetModel()

class OSMCityModel():
    def __init__(self, osmParserData, countryId):
        self.root=dict()
        self.countryId=countryId
        self.osmParserData=osmParserData
        self.cityDataCache=dict()
        self.buildModel(self.countryId, self.root)

    def buildModel(self, currentCityId, data):
        cityList=self.osmParserData.getAdminChildsForId(currentCityId)
        for cityId, cityName, adminLevel in cityList:
            childs=dict()
            data[cityId]=(cityId, cityName, currentCityId, childs, adminLevel)
            self.cityDataCache[cityId]=(cityId, cityName, currentCityId, childs, adminLevel)
            self.buildModel(cityId, childs)

    def getRootNodes(self):
        return list(self.root.values())

    def getParent(self, currentCityId):
        cityId, cityName, parentId, childs, adminLevel=self.getCityData(currentCityId, self.root)
        if parentId!=None:
            return parentId
        return None

    def getChilds(self, currentCityId):
        cityId, cityName, parentId, childs, adminLevel=self.getCityData(currentCityId, self.root)
        if parentId!=None:
            return list(childs.values())
        return None

    def getCityData(self, currentCityId, data):
        return self.cityDataCache[currentCityId]

#        cityData=self.getCityDataRecursive(currentCityId, data)
#        self.cityDataCache[currentCityId]=cityData
#        return cityData

#    def getCityDataRecursive(self, currentCityId, data):
#        for (cityId, cityName, parentId, childs) in data.values():
#            if cityId==currentCityId:
#                return (cityId, cityName, parentId, childs)
#
#            foundCityId, foundCityName, foundParent, foundChilds=self.getCityDataRecursive(currentCityId, childs)
#            if foundCityId!=None:
#                return foundCityId, foundCityName, foundParent, foundChilds
#
#        return None, None, None, None

    def hasMatchingChilds(self, currentCityId, filteredCityList):
        cityId, cityName, parentId, childs, adminLevel=self.getCityData(currentCityId, self.root)

        if cityId in filteredCityList:
            return True

        for (cityId, _, _, _, _) in childs.values():
            matching=self.hasMatchingChilds(cityId, filteredCityList)
            if matching==True:
                return matching

        return False

class OSMTreeItem(object):
    def __init__(self, osmId, areaName, parentItem, adminLevel):
        self.osmId=osmId
        self.areaName=areaName
        self.parentItem=parentItem
        self.childItems=[]
        self.adminLevel=adminLevel

    def appendChild(self, item):
        self.childItems.append(item)

    def child(self, row):
        return self.childItems[row]

    def childCount(self):
        return len(self.childItems)

    def data(self, column):
        if column == 0:
            return self.areaName
        if column == 1:
            return self.adminLevel
        return None

    def parent(self):
        return self.parentItem

    def row(self):
        if self.parentItem!=None:
            return self.parentItem.childItems.index(self)
        return 0

    def __repr__(self):
        return "%d:%s"%(self.osmId, self.areaName)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.osmId==other.osmId

class OSMAdressTreeModelCity(QAbstractItemModel):
    def __init__(self, parent):
        QAbstractItemModel.__init__(self, parent)
        self.rootItem=OSMTreeItem(-1, "ALL", None, 0)

    def citySort(self, item):
        return item[1]

    def update(self, filteredCityList, treeModel, saveState=True):
        self.layoutAboutToBeChanged.emit()

        itemList=list()
#        if saveState==True:
#            for index in self.persistentIndexList():
#                if index.isValid():
#                    itemList.append((index.row(), index.column(), index.internalPointer()))

        self.rootItem=OSMTreeItem(-1, "ALL", None, 0)

        filterdCitySet=set()
        for cityId, cityName, adminLevel in filteredCityList:
            filterdCitySet.add(cityId)

        rootNodes=treeModel.getRootNodes()
        rootNodes.sort(key=self.citySort)
        for cityId, cityName, parentId, childs, adminLevel in rootNodes:
            if treeModel.hasMatchingChilds(cityId, filterdCitySet):
                treeItem=OSMTreeItem(cityId, cityName, self.rootItem, adminLevel)
                self.rootItem.appendChild(treeItem)
                self.addChilds(filterdCitySet, treeItem, treeModel)

#        if saveState==True:
#            for row, column, item in itemList:
#                toIndex=self.searchModel(item.osmId)
#                if toIndex!=None:
#                    self.changePersistentIndex(self.createIndex(row, column, item), toIndex)

        self.layoutChanged.emit()

    def addChilds(self, filterdCitySet, parentTreeItem, treeModel):
        childNodes=treeModel.getChilds(parentTreeItem.osmId)
        childNodes.sort(key=self.citySort)
        for cityId, cityName, parentId, childs, adminLevel in childNodes:
            if treeModel.hasMatchingChilds(cityId, filterdCitySet):
                treeItem=OSMTreeItem(cityId, cityName, parentTreeItem, adminLevel)
                parentTreeItem.appendChild(treeItem)
                self.addChilds(filterdCitySet, treeItem, treeModel)

    def columnCount(self, parent=None):
        return 1

    def data(self, index, role):
        if not index.isValid():
            return None

        item = index.internalPointer()
        if role == Qt.DisplayRole:
            return item.data(index.column())
        if role == Qt.UserRole:
            return item.osmId
        return None

    def headerData(self, col, orientation, role):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                if col==0:
                    return "City"
                if col==1:
                    return "Admin Level"
            elif role == Qt.TextAlignmentRole:
                return Qt.AlignLeft
        return None

    def index(self, row, column, parent=QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()

        childItem = parentItem.child(row)
        if childItem:
            return self.createIndex(row, column, childItem)
        else:
            return QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()

        childItem = index.internalPointer()
        if not childItem:
            return QModelIndex()

        parentItem = childItem.parent()

        if not parentItem:
            return QModelIndex()

        if parentItem == self.rootItem:
            return QModelIndex()

        return self.createIndex(parentItem.row(), 0, parentItem)

    def rowCount(self, parent=QModelIndex()):
        if parent.column() > 0:
            return 0
        if not parent.isValid():
            p_Item = self.rootItem
        else:
            p_Item = parent.internalPointer()
        return p_Item.childCount()

    def searchModel(self, osmId):
        def searchNode(node):
            for child in node.childItems:
                if osmId == child.osmId:
                    return self.createIndex(child.row(), 0, child)

                if child.childCount() > 0:
                    result = searchNode(child)
                    if result:
                        return result

        return searchNode(self.rootItem)

class OSMDialogWithSettings(QDialog):
    def __init__(self, parent):
        QDialog.__init__(self, parent)
        self.pool = QThreadPool()
        self.pool.setMaxThreadCount(1)

    def clearSettings(self):
        settings=dict()

    def addSetting(self, key, value):
        settings[key]=value

    def getSetting(self, key):
        if key in settings:
            return settings[key]

        return None

class OSMAdressDialog(OSMDialogWithSettings):
    updateUISignal = pyqtSignal()
    updateUICitySignal = pyqtSignal()

    def __init__(self, parent, osmParserData, defaultCountryId):
        OSMDialogWithSettings.__init__(self, parent)

        self.updateUISignal.connect(self.updateUI)
        self.updateUICitySignal.connect(self.updateUICity)
        self.osmParserData=osmParserData
        font = self.font()
        font.setPointSize(14)
        self.setFont(font)

        self.defaultCountryId=defaultCountryId
        self.adminAreaDict, self.reverseAdminAreaDict=osmParserData.getAdminAreaConversion()

        self.countryDict=osmParserData.getAdminCountryList()
        self.reverseCountryDict=dict()
        for osmId, countryName in self.countryDict.items():
            self.reverseCountryDict[countryName]=osmId

        self.cityList=list()
        self.filteredCityList=list()
        self.filteredStreetList=list()
        self.streetList=list()

        self.currentCountryId=None
        self.currentCityId=None

        self.style=OSMStyle()
        self.startPointIcon=QIcon(self.style.getStylePixmap("startPixmap"))
        self.endPointIcon=QIcon(self.style.getStylePixmap("finishPixmap"))
        self.wayPointIcon=QIcon(self.style.getStylePixmap("wayPixmap"))
        self.mapPointIcon=QIcon(self.style.getStylePixmap("mapPointPixmap"))
        self.favoriteIcon=QIcon(self.style.getStylePixmap("favoritesBlackPixmap"))

        self.pointType=None
        self.selectedAddress=None

        self.lastFilterValueText=None
        self.lastFilteredStreetList=None
        self.cityRecursive=False
        self.pointDict=dict()
        self.initUI()

    def updateAdressListForCity(self):
        if self.currentCityId!=None:
            if self.cityRecursive==True:
                self.streetList=self.osmParserData.getAdressListForCityRecursive(self.currentCountryId, self.currentCityId)
            else:
                self.streetList=self.osmParserData.getAdressListForCity(self.currentCountryId, self.currentCityId)
            self.streetList=sorted(self.streetList, key=self.streetNameSort)
        else:
            self.streetList=list()

        self.lastFilterValueText=None
        self.lastFilteredStreetList=None

    def updateAddressListForCountry(self):
        if self.currentCountryId!=None:
            self.streetList=self.osmParserData.getAdressListForCountry(self.currentCountryId)
            self.streetList=sorted(self.streetList, key=self.streetNameSort)
        else:
            self.streetList=list()

        self.lastFilterValueText=None
        self.lastFilteredStreetList=None

    def updateCityListForCountry(self):
        if self.currentCountryId!=None:
            self.cityList=list()
            self.osmParserData.getAdminChildsForIdRecursive(self.currentCountryId, self.cityList)
            self.cityList.sort(key=self.citySort)
        else:
            self.cityList=list()

    def streetNameSort(self, item):
        if item[5]==None:
            return ""
        return item[5]

    def houseNumberSort(self, item):
        if item[6]==None:
            return 0

        houseNumberStr=item[6]
        try:
            houseNumber=int(houseNumberStr)
            return houseNumber
        except ValueError:
            numbers=re.split('\D+',houseNumberStr)
            if len(numbers[0])!=0:
                return int(numbers[0])
        return 0

    def citySort(self, item):
        return item[1]

    def getResult(self):
        return (self.selectedAddress, self.pointType)

    def getResult2(self):
        return self.pointDict

    def initUI(self):
        top=QVBoxLayout()
        top.setAlignment(Qt.AlignTop)
        top.setSpacing(2)

        lastCountryId=self.getSetting("osmadressdialog.country")
        lastCityId=self.getSetting("osmadressdialog.city")
        lastCityFilter=self.getSetting("osmadressdialog.cityfilter")
        lastStreetFilter=self.getSetting("osmadressdialog.streetfilter")
        lastIgnoreCity=self.getSetting("osmadressdialog.ignorecity")
        lastRecursive=self.getSetting("osmadressdialog.recursive")

        self.countryCombo=QComboBox(self)
        defaultCountryName=None

        if lastCountryId==None or not lastCountryId in self.countryDict.keys():
            if self.defaultCountryId!=None:
                defaultCountryName=self.countryDict[self.defaultCountryId]
        else:
            defaultCountryName=self.countryDict[lastCountryId]

        countryList=sorted(self.reverseCountryDict.keys())
        i=0
        defaultIndex=0
        for countryName in countryList:
            self.countryCombo.addItem(countryName)
            if countryName==defaultCountryName:
                defaultIndex=i
            i=i+1

        self.countryCombo.setCurrentIndex(defaultIndex)

        self.countryCombo.activated.connect(self.countryChangedWorker)
        top.addWidget(self.countryCombo)

        self.currentCountryId=self.reverseCountryDict[self.countryCombo.currentText()]

        dataArea=QHBoxLayout()

        cityBox=QVBoxLayout()
        self.cityFilterEdit=QLineEdit(self)
        if lastCityFilter!=None:
            self.cityFilterEdit.setText(lastCityFilter)
        self.cityFilterEdit.textChanged.connect(self._applyFilterCity)
        cityBox.addWidget(self.cityFilterEdit)

        hbox=QHBoxLayout()
        self.ignoreCityButton=QCheckBox("No Area", self)
        if lastIgnoreCity!=None:
            self.ignoreCityButton.setChecked(lastIgnoreCity)
        self.ignoreCityButton.clicked.connect(self.ignoreCityWorker)
        hbox.addWidget(self.ignoreCityButton)

        self.cityRecursiveButton=QCheckBox("Recursive", self)
        if lastRecursive!=None:
            self.cityRecursiveButton.setChecked(lastRecursive)
        self.cityRecursiveButton.clicked.connect(self.setCityRecursiveWorker)
        hbox.addWidget(self.cityRecursiveButton)

        cityBox.addLayout(hbox)

        self.cityView=QTreeView(self)
        cityBox.addWidget(self.cityView)

        self.cityViewModel=OSMAdressTreeModelCity(self)
        self.cityView.setModel(self.cityViewModel)

        header=QHeaderView(Qt.Horizontal, self.cityView)
        header.setStretchLastSection(True)
        self.cityView.setHeader(header)
        self.cityView.setColumnWidth(0, 300)

        dataArea.addLayout(cityBox)

        streetBox=QVBoxLayout()

        self.streetFilterEdit=QLineEdit(self)
        if lastStreetFilter!=None:
            self.streetFilterEdit.setText(lastStreetFilter)
        self.streetFilterEdit.textChanged.connect(self._applyFilterStreet)
        streetBox.addWidget(self.streetFilterEdit)

        self.streetView=QTableView(self)
        streetBox.addWidget(self.streetView)

        dataArea.addLayout(streetBox)

        self.streetViewModel=OSMAdressTableModel(self.adminAreaDict, self.reverseAdminAreaDict, self)
        self.streetViewModel.update(self.filteredStreetList)
        self.streetView.setModel(self.streetViewModel)
        header=QHeaderView(Qt.Horizontal, self.streetView)
        header.setStretchLastSection(True)
        self.streetView.setHorizontalHeader(header)
        self.streetView.setColumnWidth(0, 300)
        self.streetView.setSelectionBehavior(QAbstractItemView.SelectRows)

        dataArea.setStretch(0, 1)
        dataArea.setStretch(1, 3)

        top.addLayout(dataArea)

        actionButtons=QHBoxLayout()
        actionButtons.setAlignment(Qt.AlignBottom|Qt.AlignRight)

        self.addFavButton=QPushButton("Favorite", self)
        self.addFavButton.clicked.connect(self._addFavPoint)
        self.addFavButton.setIcon(self.favoriteIcon)
        self.addFavButton.setEnabled(False)
        actionButtons.addWidget(self.addFavButton)

        self.showPointButton=QPushButton("Show", self)
        self.showPointButton.clicked.connect(self._showPoint)
        self.showPointButton.setIcon(self.mapPointIcon)
        self.showPointButton.setEnabled(False)
        actionButtons.addWidget(self.showPointButton)

        self.setStartPointButton=QPushButton("Start", self)
        self.setStartPointButton.clicked.connect(self._setStartPoint)
        self.setStartPointButton.setIcon(self.startPointIcon)
        self.setStartPointButton.setEnabled(False)
        actionButtons.addWidget(self.setStartPointButton)

        self.setEndPointButton=QPushButton("Finish", self)
        self.setEndPointButton.clicked.connect(self._setEndPoint)
        self.setEndPointButton.setIcon(self.endPointIcon)
        self.setEndPointButton.setEnabled(False)
        actionButtons.addWidget(self.setEndPointButton)

        self.setWayPointButton=QPushButton("Way", self)
        self.setWayPointButton.clicked.connect(self._setWayPoint)
        self.setWayPointButton.setIcon(self.wayPointIcon)
        self.setWayPointButton.setEnabled(False)
        actionButtons.addWidget(self.setWayPointButton)

        top.addLayout(actionButtons)

        buttons=QHBoxLayout()
        buttons.setAlignment(Qt.AlignBottom|Qt.AlignRight)

        style=QCommonStyle()

        #self.cancelButton=QPushButton("Cancel", self)
        #self.cancelButton.clicked.connect(self._cancel)
        #buttons.addWidget(self.cancelButton)

        self.okButton=QPushButton("Close", self)
        self.okButton.clicked.connect(self._ok)
        self.okButton.setDefault(True)
        buttons.addWidget(self.okButton)

        top.addLayout(buttons)

        selectionStreet = self.streetView.selectionModel()
        selectionStreet .selectionChanged.connect(self._selectionChanged)
        selectionCity = self.cityView.selectionModel()
        selectionCity.selectionChanged.connect(self.cityChangedWorker)

        self.setLayout(top)
        self.setWindowTitle('Addresses')
        self.setGeometry(0, 0, 1024, 800)

        self.initCityUI()

        self.countryChangedWorker()
        if lastCityId!=None:
            nodeIndex=self.cityViewModel.searchModel(lastCityId)
            if nodeIndex!=None and nodeIndex.isValid():
                self.cityView.setCurrentIndex(nodeIndex)

    @pyqtSlot()
    def setCityRecursiveWorker(self):
        self.cityRecursive=self.cityRecursiveButton.isChecked()
        selmodel = self.cityView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self.currentCityId=self.cityViewModel.data(current, Qt.UserRole)
            self.streetViewModel.setLoading()
            worker = Worker(self._setCityRecursive)
            self.pool.start(worker)

    def _setCityRecursive(self):
        if self.ignoreCity==True:
            self.updateAddressListForCountry()
        else:
            self.updateAdressListForCity()
        self.updateUICitySignal.emit()

    def initCityUI(self):
        self.ignoreCity=self.ignoreCityButton.isChecked()
        if self.ignoreCity==True:
            self.cityView.setDisabled(True)
            self.cityFilterEdit.setDisabled(True)
            self.cityRecursiveButton.setDisabled(True)
        else:
            self.cityView.setDisabled(False)
            self.cityFilterEdit.setDisabled(False)
            self.cityRecursiveButton.setDisabled(False)

        self.cityRecursive=self.cityRecursiveButton.isChecked()

    @pyqtSlot()
    def ignoreCityWorker(self):
        self._clearStreetTableSelection()
        self.initCityUI()
        self.streetViewModel.setLoading()
        worker = Worker(self._ignoreCity)
        self.pool.start(worker)

    def _ignoreCity(self):
        if self.ignoreCity==True:
            self.updateAddressListForCountry()
        else:
            self.updateAdressListForCity()
        self.updateUICitySignal.emit()

    @pyqtSlot()
    def countryChangedWorker(self):
        self._clearCityTableSelection()
        self._clearStreetTableSelection()
        self.ignoreCity=self.ignoreCityButton.isChecked()
        self.currentCityId=None
        self.currentCountryId=self.reverseCountryDict[self.countryCombo.currentText()]
        self.streetViewModel.setLoading()
        worker = Worker(self._countryChanged)
        self.pool.start(worker)

    def _countryChanged(self):
        self.updateCityListForCountry()
        self.cityModel=OSMCityModel(self.osmParserData, self.currentCountryId)
        if self.ignoreCity==True:
            self.updateAddressListForCountry()
        else:
            self.updateAdressListForCity()
        self.updateUISignal.emit()

    @pyqtSlot()
    def updateUI(self):
        self.cityViewModel.update(self.cityList, self.cityModel, False)
        self._applyFilterCity()
        self._applyFilterStreet()

    @pyqtSlot()
    def cityChangedWorker(self):
        selmodel = self.cityView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self._clearStreetTableSelection()
            self.currentCityId=self.cityViewModel.data(current, Qt.UserRole)
            self.streetViewModel.setLoading()
            worker = Worker(self._cityChanged)
            self.pool.start(worker)

    def _cityChanged(self):
        self.updateAdressListForCity()
        self.updateUICitySignal.emit()

    @pyqtSlot()
    def updateUICity(self):
        self._applyFilterStreet()

    @pyqtSlot()
    def _selectionChanged(self):
        selmodel = self.streetView.selectionModel()
        current = selmodel.currentIndex()
        valid =  current.isValid() and not self.streetViewModel.isLoading()
        self.setEndPointButton.setEnabled(valid)
        self.setStartPointButton.setEnabled(valid)
        self.setWayPointButton.setEnabled(valid)
        self.showPointButton.setEnabled(valid)
        self.addFavButton.setEnabled(valid)

    def done(self, code):
        self.addSetting("osmadressdialog.country", self.currentCountryId)
        self.addSetting("osmadressdialog.city", self.currentCityId)
        self.addSetting("osmadressdialog.cityfilter", self.cityFilterEdit.text())
        self.addSetting("osmadressdialog.streetfilter", self.streetFilterEdit.text())
        self.addSetting("osmadressdialog.ignorecity", self.ignoreCityButton.isChecked())
        self.addSetting("osmadressdialog.recursive", self.cityRecursiveButton.isChecked())

        return super(OSMAdressDialog, self).done(code)

    @pyqtSlot()
    def _cancel(self):
        self.done(QDialog.Rejected)

    @pyqtSlot()
    def _ok(self):
        self.done(QDialog.Accepted)

    @pyqtSlot()
    def _showPoint(self):
        selmodel = self.streetView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self.selectedAddress=self.filteredStreetList[current.row()]
            self.pointType=OSMRoutingPoint.TYPE_MAP
            self.pointDict[self.pointType]=self.selectedAddress
        self.done(QDialog.Accepted)

    @pyqtSlot()
    def _addFavPoint(self):
        selmodel = self.streetView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self.selectedAddress=self.filteredStreetList[current.row()]
            self.pointType=OSMRoutingPoint.TYPE_FAVORITE
            self.pointDict[self.pointType]=self.selectedAddress
#        self.done(QDialog.Accepted)

    @pyqtSlot()
    def _setWayPoint(self):
        selmodel = self.streetView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self.selectedAddress=self.filteredStreetList[current.row()]
            self.pointType=OSMRoutingPoint.TYPE_WAY
            self.pointDict[self.pointType]=self.selectedAddress
#        self.done(QDialog.Accepted)

    @pyqtSlot()
    def _setStartPoint(self):
        selmodel = self.streetView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self.selectedAddress=self.filteredStreetList[current.row()]
            self.pointType=OSMRoutingPoint.TYPE_START
            self.pointDict[self.pointType]=self.selectedAddress
#        self.done(QDialog.Accepted)

    @pyqtSlot()
    def _setEndPoint(self):
        selmodel = self.streetView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self.selectedAddress=self.filteredStreetList[current.row()]
            self.pointType=OSMRoutingPoint.TYPE_END
            self.pointDict[self.pointType]=self.selectedAddress
#        self.done(QDialog.Accepted)

    @pyqtSlot()
    def _clearStreetTableSelection(self):
        self.streetView.clearSelection()
        self.setWayPointButton.setEnabled(False)
        self.setStartPointButton.setEnabled(False)
        self.setEndPointButton.setEnabled(False)
        self.showPointButton.setEnabled(False)
        self.addFavButton.setEnabled(False)

    @pyqtSlot()
    def _clearCityTableSelection(self):
        self.cityView.clearSelection()
        self.currentCityId=None

    @pyqtSlot()
    def _applyFilterStreet(self):
        self._clearStreetTableSelection()
        filterValueText=self.streetFilterEdit.text()
        if len(filterValueText)!=0:
            filterValue=filterValueText
            if filterValue[-1]!="*":
                filterValue=filterValue+"*"
            filterValueMod=None
            if "ue" in filterValue or "ae" in filterValue or "oe" in filterValue:
                filterValueMod=filterValue.replace("ue","ü").replace("ae","ä").replace("oe","ö")

            newFilterList=True
            if self.lastFilterValueText!=None and self.lastFilteredStreetList!=None:
#                print(filterValueText[:len(self.lastFilterValueText)])
#                print(self.lastFilterValueText)
                if filterValueText[:len(self.lastFilterValueText)]==self.lastFilterValueText:
                    newFilterList=False

            if newFilterList==True:
#                print("use all")
                currentStreetList=self.streetList
            else:
#                print("use last")
                currentStreetList=self.lastFilteredStreetList
            self.filteredStreetList=list()
            for (addressId, refId, country, city, postCode, streetName, houseNumber, lat, lon) in currentStreetList:
                match=False
                if fnmatch(streetName.upper(), filterValue.upper()):
                    match=True
                if match==False and filterValueMod!=None and fnmatch(streetName.upper(), filterValueMod.upper()):
                    match=True

                if match==True:
                    self.filteredStreetList.append((addressId, refId, country, city, postCode, streetName, houseNumber, lat, lon))
        else:
            self.filteredStreetList=self.streetList

        self.streetViewModel.update(self.filteredStreetList)
        self.lastFilterValueText=filterValueText
        self.lastFilteredStreetList=self.filteredStreetList

    @pyqtSlot()
    def _applyFilterCity(self):
        self._clearCityTableSelection()
        filterValue=self.cityFilterEdit.text()
        if len(filterValue)!=0:
            if filterValue[-1]!="*":
                filterValue=filterValue+"*"
            self.filteredCityList=list()
            filterValueMod=None
            if "ue" in filterValue or "ae" in filterValue or "oe" in filterValue:
                filterValueMod=filterValue.replace("ue","ü").replace("ae","ä").replace("oe","ö")

            for (cityId, cityName, adminLevel) in self.cityList:
                match=False
                if fnmatch(cityName.upper(), filterValue.upper()):
                    match=True
                if match==False and filterValueMod!=None and fnmatch(cityName.upper(), filterValueMod.upper()):
                    match=True

                if match==True:
                    self.filteredCityList.append((cityId, cityName, adminLevel))

            self.cityViewModel.update(self.filteredCityList, self.cityModel)
            self.cityView.expandAll()

        else:
            self.filteredCityList=self.cityList
            self.cityViewModel.update(self.filteredCityList, self.cityModel)
            self.cityView.expandAll()



#----------------------------
class OSMFavoriteTableModel(QAbstractTableModel):
    def __init__(self, parent):
        QAbstractTableModel.__init__(self, parent)

    def rowCount(self, parent):
        return len(self.favoriteList)

    def columnCount(self, parent):
        return 1

    def data(self, index, role):
        if role == Qt.TextAlignmentRole:
            return Qt.AlignLeft|Qt.AlignVCenter
        elif role != Qt.DisplayRole:
            return None

        if index.row() >= len(self.favoriteList):
            return ""
        point=self.favoriteList[index.row()]
        name=point.getName()

        if index.column()==0:
            return name

    def headerData(self, col, orientation, role):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                if col==0:
                    return "Name"
            elif role == Qt.TextAlignmentRole:
                return Qt.AlignLeft
        return None


    def update(self, favoriteList):
        self.beginResetModel()
        self.favoriteList=favoriteList
        self.endResetModel()

class OSMFavoritesDialog(QDialog):
    def __init__(self, parent, favoriteList):
        QDialog.__init__(self, parent)
        font = self.font()
        font.setPointSize(14)
        self.setFont(font)

        self.favoriteList=list()
        self.favoriteList.extend(favoriteList)
        self.favoriteList=sorted(self.favoriteList, key=self.nameSort)
        self.filteredFavoriteList=self.favoriteList

        self.selectedFavorite=None
        self.pointType=-1
        self.pointDict=dict()
        self.style=OSMStyle()
        self.startPointIcon=QIcon(self.style.getStylePixmap("startPixmap"))
        self.endPointIcon=QIcon(self.style.getStylePixmap("finishPixmap"))
        self.wayPointIcon=QIcon(self.style.getStylePixmap("wayPixmap"))
        self.mapPointIcon=QIcon(self.style.getStylePixmap("mapPointPixmap"))

        self.initUI()

    def nameSort(self, item):
        return item.getName()

    def getResult(self):
        return (self.selectedFavorite, self.pointType, self.favoriteList)

    def getResult2(self):
        return (self.pointDict, self.favoriteList)

    def initUI(self):
        top=QVBoxLayout()
        top.setAlignment(Qt.AlignTop)
        top.setSpacing(2)

        self.filterEdit=QLineEdit(self)
        self.filterEdit.setToolTip('Name Filter')
        self.filterEdit.returnPressed.connect(self._applyFilter)
        self.filterEdit.textChanged.connect(self._applyFilter)
        top.addWidget(self.filterEdit)

        self.favoriteView=QTableView(self)
        top.addWidget(self.favoriteView)

        self.favoriteViewModel=OSMFavoriteTableModel(self)
        self.favoriteViewModel.update(self.filteredFavoriteList)
        self.favoriteView.setModel(self.favoriteViewModel)
        header=QHeaderView(Qt.Horizontal, self.favoriteView)
        header.setStretchLastSection(True)
        self.favoriteView.setHorizontalHeader(header)
        self.favoriteView.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.favoriteView.setColumnWidth(0, 300)

        style=QCommonStyle()

        actionButtons=QHBoxLayout()
        actionButtons.setAlignment(Qt.AlignBottom|Qt.AlignRight)

        self.deleteFavoriteButton=QPushButton("Delete", self)
        self.deleteFavoriteButton.clicked.connect(self._deleteFavorite)
        self.deleteFavoriteButton.setEnabled(False)
        actionButtons.addWidget(self.deleteFavoriteButton)

        top.addLayout(actionButtons)

        actionButtons2=QHBoxLayout()
        actionButtons2.setAlignment(Qt.AlignBottom|Qt.AlignRight)

        self.showPointButton=QPushButton("Show", self)
        self.showPointButton.clicked.connect(self._showPoint)
        self.showPointButton.setIcon(self.mapPointIcon)
        self.showPointButton.setEnabled(False)
        actionButtons2.addWidget(self.showPointButton)

        self.setStartPointButton=QPushButton("Start", self)
        self.setStartPointButton.clicked.connect(self._setStartPoint)
        self.setStartPointButton.setIcon(self.startPointIcon)
        self.setStartPointButton.setEnabled(False)
        actionButtons2.addWidget(self.setStartPointButton)

        self.setEndPointButton=QPushButton("Finish", self)
        self.setEndPointButton.clicked.connect(self._setEndPoint)
        self.setEndPointButton.setIcon(self.endPointIcon)
        self.setEndPointButton.setEnabled(False)
        actionButtons2.addWidget(self.setEndPointButton)

        self.setWayPointButton=QPushButton("Way", self)
        self.setWayPointButton.clicked.connect(self._setWayPoint)
        self.setWayPointButton.setIcon(self.wayPointIcon)
        self.setWayPointButton.setEnabled(False)
        actionButtons2.addWidget(self.setWayPointButton)

        top.addLayout(actionButtons2)

        buttons=QHBoxLayout()
        buttons.setAlignment(Qt.AlignBottom|Qt.AlignRight)

        self.cancelButton=QPushButton("Cancel", self)
        self.cancelButton.clicked.connect(self._cancel)
        self.cancelButton.setDefault(True)
        buttons.addWidget(self.cancelButton)

        self.okButton=QPushButton("Ok", self)
        self.okButton.clicked.connect(self._ok)
        self.okButton.setDefault(True)
        buttons.addWidget(self.okButton)

        top.addLayout(buttons)

        selection = self.favoriteView.selectionModel()
        selection.selectionChanged.connect(self._selectionChanged)

        self.setLayout(top)
        self.setWindowTitle('Favorites')
        self.setGeometry(0, 0, 400, 500)

    @pyqtSlot()
    def _selectionChanged(self):
        selmodel = self.favoriteView.selectionModel()
        current = selmodel.currentIndex()
        self.setEndPointButton.setEnabled(current.isValid())
        self.setStartPointButton.setEnabled(current.isValid())
        self.setWayPointButton.setEnabled(current.isValid())
        self.showPointButton.setEnabled(current.isValid())
        self.deleteFavoriteButton.setEnabled(current.isValid())

    @pyqtSlot()
    def _cancel(self):
        self.done(QDialog.Rejected)

    @pyqtSlot()
    def _ok(self):
        self.done(QDialog.Accepted)

    @pyqtSlot()
    def _showPoint(self):
        selmodel = self.favoriteView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self.selectedFavorite=self.filteredFavoriteList[current.row()]
            self.pointType=OSMRoutingPoint.TYPE_MAP
            self.pointDict[self.pointType]=self.selectedFavorite
        self.done(QDialog.Accepted)

    @pyqtSlot()
    def _setWayPoint(self):
        selmodel = self.favoriteView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self.selectedFavorite=self.filteredFavoriteList[current.row()]
            self.pointType=OSMRoutingPoint.TYPE_WAY
            self.pointDict[self.pointType]=self.selectedFavorite

    @pyqtSlot()
    def _setStartPoint(self):
        selmodel = self.favoriteView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self.selectedFavorite=self.filteredFavoriteList[current.row()]
            self.pointType=OSMRoutingPoint.TYPE_START
            self.pointDict[self.pointType]=self.selectedFavorite

    @pyqtSlot()
    def _setEndPoint(self):
        selmodel = self.favoriteView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self.selectedFavorite=self.filteredFavoriteList[current.row()]
            self.pointType=OSMRoutingPoint.TYPE_END
            self.pointDict[self.pointType]=self.selectedFavorite

    @pyqtSlot()
    def _clearTableSelection(self):
        self.favoriteView.clearSelection()
        self.setWayPointButton.setEnabled(False)
        self.setStartPointButton.setEnabled(False)
        self.setEndPointButton.setEnabled(False)
        self.showPointButton.setEnabled(False)
        self.deleteFavoriteButton.setEnabled(False)

    @pyqtSlot()
    def _applyFilter(self):
        self._clearTableSelection()
        self.filterValue=self.filterEdit.text()
        if len(self.filterValue)!=0:
            if self.filterValue[-1]!="*":
                self.filterValue=self.filterValue+"*"
            self.filteredFavoriteList=list()
            filterValueMod=self.filterValue.replace("ue","ü").replace("ae","ä").replace("oe","ö")

            for point in self.favoriteList:
                name=point.getName()
                if not fnmatch(name.upper(), self.filterValue.upper()) and not fnmatch(name.upper(), filterValueMod.upper()):
                    continue
                self.filteredFavoriteList.append(point)
        else:
            self.filteredFavoriteList=self.favoriteList

        self.favoriteViewModel.update(self.filteredFavoriteList)

    @pyqtSlot()
    def _deleteFavorite(self):
        selmodel = self.favoriteView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            selectedFavorite=self.filteredFavoriteList[current.row()]
            self.favoriteList.remove(selectedFavorite)
            self._applyFilter()

#----------------------------

class OSMSaveFavoritesDialog(QDialog):
    def __init__(self, parent, favoriteList, defaultPointTag):
        QDialog.__init__(self, parent)
        font = self.font()
        font.setPointSize(14)
        self.setFont(font)

        self.favoriteList=sorted(favoriteList, key=self.nameSort)
        self.text=None
        self.defaultPointTag=defaultPointTag

        self.initUI()

    def nameSort(self, item):
        return item.getName()

    def getResult(self):
        return self.text

    def initUI(self):
        top=QVBoxLayout()
        top.setAlignment(Qt.AlignTop)
        top.setSpacing(2)

        fields=QFormLayout()
        fields.setAlignment(Qt.AlignTop|Qt.AlignLeft)

        label=QLabel(self)
        label.setText("Name:")

        self.textField=QLineEdit(self)
        self.textField.setText(self.defaultPointTag)
        self.textField.textChanged.connect(self._updateEnablement)
        self.textField.setMinimumWidth(300)

        fields.addRow(label, self.textField)

        top.addLayout(fields)
        self.favoriteView=QTableView(self)
        top.addWidget(self.favoriteView)

        self.favoriteViewModel=OSMFavoriteTableModel(self)
        self.favoriteViewModel.update(self.favoriteList)
        self.favoriteView.setModel(self.favoriteViewModel)
        header=QHeaderView(Qt.Horizontal, self.favoriteView)
        header.setStretchLastSection(True)
        self.favoriteView.setHorizontalHeader(header)
        self.favoriteView.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.favoriteView.setColumnWidth(0, 300)

        buttons=QHBoxLayout()
        buttons.setAlignment(Qt.AlignBottom|Qt.AlignRight)

        style=QCommonStyle()

        self.cancelButton=QPushButton("Cancel", self)
        self.cancelButton.clicked.connect(self._cancel)
        self.cancelButton.setDefault(True)
        buttons.addWidget(self.cancelButton)

        self.okButton=QPushButton("Ok", self)
        self.okButton.clicked.connect(self._ok)
        self.okButton.setDefault(True)
        self.okButton.setEnabled(False)

        buttons.addWidget(self.okButton)

        top.addLayout(buttons)

        selection = self.favoriteView.selectionModel()
        selection.selectionChanged.connect(self._selectionChanged)

        self.setLayout(top)
        self.setWindowTitle('Save Favorite')
        self.setGeometry(0, 0, 400, 500)
        self._updateEnablement()

    @pyqtSlot()
    def _selectionChanged(self):
        selmodel = self.favoriteView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self.textField.setText(self.favoriteList[current.row()].getName())

        self._updateEnablement()

    @pyqtSlot()
    def _updateEnablement(self):
        self.okButton.setDisabled(len(self.textField.text())==0)

    @pyqtSlot()
    def _cancel(self):
        self.done(QDialog.Rejected)

    @pyqtSlot()
    def _ok(self):
        self.text=self.textField.text()
        self.done(QDialog.Accepted)


#----------------------------

class OSMRouteListTableModel(QAbstractTableModel):
    def __init__(self, parent):
        QAbstractTableModel.__init__(self, parent)

    def rowCount(self, parent):
        return len(self.routeList)

    def columnCount(self, parent):
        return 1

    def data(self, index, role):
        if role == Qt.TextAlignmentRole:
            return Qt.AlignLeft|Qt.AlignVCenter
        elif role != Qt.DisplayRole:
            return None

        if index.row() >= len(self.routeList):
            return ""
        route=self.routeList[index.row()]
        name=route.getName()

        if index.column()==0:
            return name

    def headerData(self, col, orientation, role):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                if col==0:
                    return "Name"
            elif role == Qt.TextAlignmentRole:
                return Qt.AlignLeft
        return None


    def update(self, routeList):
        self.beginResetModel()
        self.routeList=routeList
        self.endResetModel()

#--------------------------------------------------
class OSMRouteListDialog(QDialog):
    def __init__(self, parent, routeList, withDelete, withClose):
        QDialog.__init__(self, parent)
        font = self.font()
        font.setPointSize(14)
        self.setFont(font)

        self.routeList=list()
        self.routeList.extend(routeList)
        self.routeList=sorted(self.routeList, key=self.nameSort)
        self.filteredRouteList=self.routeList

        self.selectedRoute=None
        self.withDelete=withDelete
        self.withClose=withClose
        self.initUI()

    def nameSort(self, item):
        return item.getName()

    def getResult(self):
        return (self.selectedRoute, self.routeList)

    def initUI(self):
        top=QVBoxLayout()
        top.setAlignment(Qt.AlignTop)
        top.setSpacing(2)

        self.filterEdit=QLineEdit(self)
        self.filterEdit.setToolTip('Name Filter')
        self.filterEdit.returnPressed.connect(self._applyFilter)
        self.filterEdit.textChanged.connect(self._applyFilter)
        top.addWidget(self.filterEdit)

        self.routeView=QTableView(self)
        top.addWidget(self.routeView)

        self.routeViewModel=OSMRouteListTableModel(self)
        self.routeViewModel.update(self.filteredRouteList)
        self.routeView.setModel(self.routeViewModel)
        header=QHeaderView(Qt.Horizontal, self.routeView)
        header.setStretchLastSection(True)
        self.routeView.setHorizontalHeader(header)
        self.routeView.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.routeView.setColumnWidth(0, 300)

        style=QCommonStyle()

        if self.withDelete==True:
            actionButtons=QHBoxLayout()
            actionButtons.setAlignment(Qt.AlignBottom|Qt.AlignRight)

            self.deleteRouteButton=QPushButton("Delete", self)
            self.deleteRouteButton.clicked.connect(self._deleteRoute)
            self.deleteRouteButton.setEnabled(False)
            actionButtons.addWidget(self.deleteRouteButton)

            top.addLayout(actionButtons)

        buttons=QHBoxLayout()
        buttons.setAlignment(Qt.AlignBottom|Qt.AlignRight)

        self.cancelButton=QPushButton("Cancel", self)
        self.cancelButton.clicked.connect(self._cancel)
        self.cancelButton.setDefault(True)
        buttons.addWidget(self.cancelButton)

        if self.withClose==True:
            self.closeButton=QPushButton("Close", self)
            self.closeButton.clicked.connect(self._close)
            buttons.addWidget(self.closeButton)

        self.okButton=QPushButton("Ok", self)
        self.okButton.clicked.connect(self._ok)
        self.okButton.setDefault(True)
        self.okButton.setEnabled(False)

        buttons.addWidget(self.okButton)

        top.addLayout(buttons)

        selection = self.routeView.selectionModel()
        selection.selectionChanged.connect(self._selectionChanged)

        self.setLayout(top)
        self.setWindowTitle('Routes')
        self.setGeometry(0, 0, 400, 500)

    @pyqtSlot()
    def _selectionChanged(self):
        selmodel = self.routeView.selectionModel()
        current = selmodel.currentIndex()
        if self.withDelete==True:
            self.deleteRouteButton.setEnabled(current.isValid())
        self.okButton.setEnabled(current.isValid())

    @pyqtSlot()
    def _cancel(self):
        self.done(QDialog.Rejected)

    @pyqtSlot()
    def _close(self):
        self.selectedRoute=None
        self.done(QDialog.Accepted)

    @pyqtSlot()
    def _ok(self):
        selmodel = self.routeView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self.selectedRoute=self.filteredRouteList[current.row()]

        self.done(QDialog.Accepted)

    @pyqtSlot()
    def _deleteRoute(self):
        selmodel = self.routeView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            selectedRoute=self.filteredRouteList[current.row()]
            self.routeList.remove(selectedRoute)
            self._applyFilter()

    @pyqtSlot()
    def _clearTableSelection(self):
        self.routeView.clearSelection()
        if self.withDelete==True:
            self.deleteRouteButton.setEnabled(False)
        self.okButton.setEnabled(False)

    @pyqtSlot()
    def _applyFilter(self):
        self._clearTableSelection()
        self.filterValue=self.filterEdit.text()
        if len(self.filterValue)!=0:
            if self.filterValue[-1]!="*":
                self.filterValue=self.filterValue+"*"
            self.filteredRouteList=list()
            filterValueMod=self.filterValue.replace("ue","ü").replace("ae","ä").replace("oe","ö")

            for route in self.routeList:
                name=route.getName()
                if not fnmatch(name.upper(), self.filterValue.upper()) and not fnmatch(name.upper(), filterValueMod.upper()):
                    continue
                self.filteredRouteList.append(route)
        else:
            self.filteredRouteList=self.routeList

        self.routeViewModel.update(self.filteredRouteList)

#--------------------------------------------------
class OSMRouteSaveDialog(QDialog):
    def __init__(self, parent, routeList):
        QDialog.__init__(self, parent)
        font = self.font()
        font.setPointSize(14)
        self.setFont(font)

        self.routeList=sorted(routeList, key=self.nameSort)
        self.text=None

        self.initUI()

    def nameSort(self, item):
        return item.getName()

    def getResult(self):
        return self.text

    def initUI(self):
        top=QVBoxLayout()
        top.setAlignment(Qt.AlignTop)
        top.setSpacing(2)

        fields=QFormLayout()
        fields.setAlignment(Qt.AlignTop|Qt.AlignLeft)

        label=QLabel(self)
        label.setText("Name:")

        self.textField=QLineEdit(self)
        self.textField.setText("")
        self.textField.textChanged.connect(self._updateEnablement)
        self.textField.setMinimumWidth(300)

        fields.addRow(label, self.textField)

        top.addLayout(fields)

        self.routeView=QTableView(self)
        top.addWidget(self.routeView)

        self.routeViewModel=OSMRouteListTableModel(self)
        self.routeViewModel.update(self.routeList)
        self.routeView.setModel(self.routeViewModel)
        header=QHeaderView(Qt.Horizontal, self.routeView)
        header.setStretchLastSection(True)
        self.routeView.setHorizontalHeader(header)
        self.routeView.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.routeView.setColumnWidth(0, 300)

        buttons=QHBoxLayout()
        buttons.setAlignment(Qt.AlignBottom|Qt.AlignRight)

        style=QCommonStyle()

        self.cancelButton=QPushButton("Cancel", self)
        self.cancelButton.clicked.connect(self._cancel)
        self.cancelButton.setDefault(True)
        buttons.addWidget(self.cancelButton)

        self.okButton=QPushButton("Ok", self)
        self.okButton.clicked.connect(self._ok)
        self.okButton.setDefault(True)
        self.okButton.setEnabled(False)

        buttons.addWidget(self.okButton)

        top.addLayout(buttons)

        selection = self.routeView.selectionModel()
        selection.selectionChanged.connect(self._selectionChanged)

        self.setLayout(top)
        self.setWindowTitle('Save Route')
        self.setGeometry(0, 0, 400, 500)

    @pyqtSlot()
    def _selectionChanged(self):
        selmodel = self.routeView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self.textField.setText(self.routeList[current.row()].getName())

        self._updateEnablement()

    @pyqtSlot()
    def _updateEnablement(self):
        self.okButton.setDisabled(len(self.textField.text())==0)

    @pyqtSlot()
    def _cancel(self):
        self.done(QDialog.Rejected)

    @pyqtSlot()
    def _ok(self):
        self.text=self.textField.text()
        self.done(QDialog.Accepted)

#----------------------------
class OSMRouteTableModel(QAbstractTableModel):
    def __init__(self, parent):
        QAbstractTableModel.__init__(self, parent)
        self.style=OSMStyle()
        self.startPoint=self.style.getStylePixmap("startPixmap")
        self.endPoint=self.style.getStylePixmap("finishPixmap")
        self.wayPoint=self.style.getStylePixmap("wayPixmap")
        self.heightHint=self.startPoint.height()+2

    def rowCount(self, parent):
        return len(self.routingPointList)

    def columnCount(self, parent):
        return 1

    def data(self, index, role):
        if role == Qt.TextAlignmentRole:
            return Qt.AlignLeft|Qt.AlignVCenter

        elif role == Qt.DecorationRole:
            if index.row() >= len(self.routingPointList):
                return None
            point=self.routingPointList[index.row()]
            pointType=point.getType()
            if pointType==OSMRoutingPoint.TYPE_START:
                return self.startPoint
            elif pointType==OSMRoutingPoint.TYPE_END:
                return self.endPoint
            elif pointType==OSMRoutingPoint.TYPE_WAY:
                return self.wayPoint
            return None

        elif role == Qt.DisplayRole:
            if index.row() >= len(self.routingPointList):
                return ""
            point=self.routingPointList[index.row()]
            name=point.getName()

            if index.column()==0:
                return name

        elif role == Qt.SizeHintRole:
            if index.column()==0:
                return QSize(1, self.heightHint)

        return None

    def headerData(self, col, orientation, role):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                if col==0:
                    return "Routing Point"
            elif role == Qt.TextAlignmentRole:
                return Qt.AlignLeft
        return None


    def update(self, routingPointList):
        self.beginResetModel()
        self.routingPointList=routingPointList
        self.endResetModel()

class OSMRouteDialog(QDialog):
    def __init__(self, parent, routingPointList, routeList):
        QDialog.__init__(self, parent)
        font = self.font()
        font.setPointSize(14)
        self.setFont(font)

        self.routingPointList=list()
        self.routingPointList.extend(routingPointList)
        self.selectedRoutePoint=None
        self.routeList=list()
        self.routeList.extend(routeList)

        self.initUI()

    def getResult(self):
        return self.routingPointList, self.routeList

    def getRouteList(self):
        return self.routeList

    def initUI(self):
        top=QVBoxLayout()
        top.setAlignment(Qt.AlignTop)
        top.setSpacing(2)

        self.routeView=QTableView(self)
        top.addWidget(self.routeView)

        self.routeViewModel=OSMRouteTableModel(self)
        self.routeViewModel.update(self.routingPointList)
        self.routeView.setModel(self.routeViewModel)
        header=QHeaderView(Qt.Horizontal, self.routeView)
        header.setStretchLastSection(True)
        self.routeView.setHorizontalHeader(header)
        self.routeView.setColumnWidth(0, 300)
        self.routeView.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.routeView.resizeRowsToContents()

        editButtons=QHBoxLayout()
        editButtons.setAlignment(Qt.AlignBottom|Qt.AlignRight)

        style=QCommonStyle()

        self.removePointButton=QPushButton("Remove", self)
        self.removePointButton.clicked.connect(self._removePoint)
        self.removePointButton.setEnabled(False)
        editButtons.addWidget(self.removePointButton)

        self.upPointButton=QPushButton("Up", self)
        self.upPointButton.clicked.connect(self._upPoint)
        self.upPointButton.setIcon(style.standardIcon(QStyle.SP_ArrowUp))
        self.upPointButton.setEnabled(False)
        editButtons.addWidget(self.upPointButton)

        self.downPointButton=QPushButton("Down", self)
        self.downPointButton.clicked.connect(self._downPoint)
        self.downPointButton.setIcon(style.standardIcon(QStyle.SP_ArrowDown))
        self.downPointButton.setEnabled(False)
        editButtons.addWidget(self.downPointButton)

        self.revertPointsButton=QPushButton("Revert", self)
        self.revertPointsButton.clicked.connect(self._revertRoute)
        self.revertPointsButton.setEnabled(True)
        editButtons.addWidget(self.revertPointsButton)

        top.addLayout(editButtons)

        routeButtons=QHBoxLayout()
        routeButtons.setAlignment(Qt.AlignBottom|Qt.AlignRight)

        style=QCommonStyle()

        self.loadRoutButton=QPushButton("Load...", self)
        self.loadRoutButton.clicked.connect(self._loadRoute)
        routeButtons.addWidget(self.loadRoutButton)

        self.saveRouteButton=QPushButton("Save...", self)
        self.saveRouteButton.clicked.connect(self._saveRoute)
        routeButtons.addWidget(self.saveRouteButton)

        top.addLayout(routeButtons)

        buttons=QHBoxLayout()
        buttons.setAlignment(Qt.AlignBottom|Qt.AlignRight)

        self.cancelButton=QPushButton("Cancel", self)
        self.cancelButton.clicked.connect(self._cancel)
        buttons.addWidget(self.cancelButton)

        self.okButton=QPushButton("Ok", self)
        self.okButton.clicked.connect(self._ok)
        self.okButton.setDefault(True)
        buttons.addWidget(self.okButton)
        top.addLayout(buttons)

        selection = self.routeView.selectionModel()
        selection.selectionChanged.connect(self._selectionChanged)

        self.setLayout(top)
        self.setWindowTitle('Routing Point')
        self.setGeometry(0, 0, 400, 500)

    @pyqtSlot()
    def _saveRoute(self):
        routeNameDialog=OSMRouteSaveDialog(self, self.routeList)
        result=routeNameDialog.exec()
        if result==QDialog.Accepted:
            name=routeNameDialog.getResult()
            route=OSMRoute(name, self.routingPointList)
            self.routeList.append(route)

    @pyqtSlot()
    def _loadRoute(self):
        loadRouteDialog=OSMRouteListDialog(self, self.routeList, False, False)
        result=loadRouteDialog.exec()
        if result==QDialog.Accepted:
            route, routeList=loadRouteDialog.getResult()
            if route!=None:
                self.routeList=routeList
                self.routingPointList=route.getRoutingPointList()
                self.routeViewModel.update(self.routingPointList)
                self._selectionChanged()

    @pyqtSlot()
    def _revertRoute(self):
        self.routingPointList.reverse()
        self.assignPointTypes()
        self.routeViewModel.update(self.routingPointList)
        self._selectionChanged()

    @pyqtSlot()
    def _ok(self):
        self.done(QDialog.Accepted)

    @pyqtSlot()
    def _selectionChanged(self):
        selmodel = self.routeView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            routingPoint=self.routingPointList[current.row()]
            self.removePointButton.setEnabled(len(self.routingPointList)>2)
            index=self.routingPointList.index(routingPoint)
            self.downPointButton.setEnabled(index>=0 and index<=len(self.routingPointList)-2)
            self.upPointButton.setEnabled(index<=len(self.routingPointList)-1 and index>=1)
        else:
            self.removePointButton.setEnabled(current.isValid())
            self.upPointButton.setEnabled(current.isValid())
            self.downPointButton.setEnabled(current.isValid())

    @pyqtSlot()
    def _cancel(self):
        self.done(QDialog.Rejected)

    @pyqtSlot()
    def _removePoint(self):
        selmodel = self.routeView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            routingPoint=self.routingPointList[current.row()]
            self.routingPointList.remove(routingPoint)
            self.assignPointTypes()
            self.routeViewModel.update(self.routingPointList)
            self._selectionChanged()

    @pyqtSlot()
    def _upPoint(self):
        selmodel = self.routeView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            routingPoint=self.routingPointList[current.row()]
            index=self.routingPointList.index(routingPoint)
            if index<=len(self.routingPointList)-1 and index>=1:
                self.routingPointList.remove(routingPoint)
                self.routingPointList.insert(index-1, routingPoint)

            self.assignPointTypes()
            self.routeViewModel.update(self.routingPointList)
            selmodel.setCurrentIndex(self.routeViewModel.index(current.row()-1, current.column()), QItemSelectionModel.ClearAndSelect)


    @pyqtSlot()
    def _downPoint(self):
        selmodel = self.routeView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            routingPoint=self.routingPointList[current.row()]
            index=self.routingPointList.index(routingPoint)
            if index>=0 and index<=len(self.routingPointList)-2:
                self.routingPointList.remove(routingPoint)
                self.routingPointList.insert(index+1, routingPoint)

            self.assignPointTypes()
            self.routeViewModel.update(self.routingPointList)
            selmodel.setCurrentIndex(self.routeViewModel.index(current.row()+1, current.column()), QItemSelectionModel.ClearAndSelect)

    def assignPointTypes(self):
        self.routingPointList[0].changeType(OSMRoutingPoint.TYPE_START)
        self.routingPointList[-1].changeType(OSMRoutingPoint.TYPE_END)
        for point in self.routingPointList[1:-1]:
            point.changeType(OSMRoutingPoint.TYPE_WAY)


    @pyqtSlot()
    def _clearTableSelection(self):
        self.routeView.clearSelection()
        self.removePointButton.setEnabled(False)
        self.upPointButton.setEnabled(False)
        self.downPointButton.setEnabled(False)
        self.revertPointsButton.setEnabled(False)

#---------------------
class FloatValueValidator(QValidator):
    def __init__(self, parent):
        QValidator.__init__(self, parent)

    def validate(self, input, pos):
        if len(input)==0:
            return (QValidator.Acceptable, input, pos)
        try:
            f=float(input)
        except ValueError:
            return (QValidator.Invalid, input, pos)
        return (QValidator.Acceptable, input, pos)

class OSMPositionDialog(QDialog):
    def __init__(self, parent, lat=None, lon=None):
        QDialog.__init__(self, parent)
        self.lat=0.0
        self.lon=0.0
        font = self.font()
        font.setPointSize(14)
        self.setFont(font)

        self.initLat=lat
        self.initLon=lon

        self.initUI()

    def getResult(self):
        return (self.lat, self.lon)

    def initUI(self):
        top=QVBoxLayout()
        top.setAlignment(Qt.AlignTop)
        top.setSpacing(2)

        style=QCommonStyle()

        fields=QFormLayout()
        fields.setAlignment(Qt.AlignTop|Qt.AlignLeft)

        label=QLabel(self)
        label.setText("Latitude:")

        self.validator=FloatValueValidator(self)
        self.latField=QLineEdit(self)
        self.latField.setToolTip('Latitude')
        self.latField.textChanged.connect(self._updateEnablement)
        self.latField.setValidator(self.validator)
        if self.initLat!=None:
            self.latField.setText("%.6f"%self.initLat)

        fields.addRow(label, self.latField)

        label=QLabel(self)
        label.setText("Longitude:")

        self.lonField=QLineEdit(self)
        self.lonField.setToolTip('Latitude')
        self.lonField.textChanged.connect(self._updateEnablement)
        self.lonField.setValidator(self.validator)
        if self.initLon!=None:
            self.lonField.setText("%.6f"%self.initLon)

        fields.addRow(label, self.lonField)

        top.addLayout(fields)

        buttons=QHBoxLayout()
        buttons.setAlignment(Qt.AlignBottom|Qt.AlignRight)

        if self.initLat==None and self.initLon==None:
            self.cancelButton=QPushButton("Cancel", self)
            self.cancelButton.clicked.connect(self._cancel)
            buttons.addWidget(self.cancelButton)

            self.okButton=QPushButton("Ok", self)
            self.okButton.clicked.connect(self._ok)
            self.okButton.setDisabled(True)
            self.okButton.setDefault(True)
            buttons.addWidget(self.okButton)
        else:
            self.closeButton=QPushButton("Close", self)
            self.closeButton.clicked.connect(self._close)
            buttons.addWidget(self.closeButton)

        top.addLayout(buttons)

        self.setLayout(top)
        self.setWindowTitle('Show Position')
        self.setGeometry(0, 0, 400, 100)

    @pyqtSlot()
    def _updateEnablement(self):
        if self.initLat==None and self.initLon==None:
            self.okButton.setDisabled(len(self.latField.text())==0 or len(self.lonField.text())==0)

    @pyqtSlot()
    def _cancel(self):
        self.done(QDialog.Rejected)

    @pyqtSlot()
    def _close(self):
        self.done(QDialog.Rejected)

    @pyqtSlot()
    def _ok(self):
        self.lat=float(self.latField.text())
        self.lon=float(self.lonField.text())
        self.done(QDialog.Accepted)

class IntValueValidator(QValidator):
    def __init__(self, parent):
        QValidator.__init__(self, parent)

    def validate(self, input, pos):
        if len(input)==0:
            return (QValidator.Acceptable, input, pos)
        try:
            f=int(input)
        except ValueError:
            return (QValidator.Invalid, input, pos)
        return (QValidator.Acceptable, input, pos)

class OSMRoutingTab(OptionsDialogTab):
    def __init__(self, optionsConfig, parent):
        OptionsDialogTab.__init__(self, optionsConfig, parent)
        self.setFromOptionsConfig(self.getOptionsConfig())

    def getTabName(self):
        return "Routing"

    def setFromOptionsConfig(self, optionsConfig):
        self.routingModeButtons=list()
        self.routingModes=optionsConfig["routingModes"]
        self.routingModeId=optionsConfig["routingModeId"]

    def setToOptionsConfig(self):
        self.routingMode=None
        i=0
        for button in self.routingModeButtons:
            if button.isChecked():
                self.routingMode=self.routingModes[i]
            i=i+1
        self.optionsConfig["routingMode"]=self.routingMode

    def addToLayout(self, layout):
        for routingMode in self.routingModes:
            routingModeId=routingMode["id"]
            routingModeButton=QRadioButton(routingMode["desc"], self)
            self.routingModeButtons.append(routingModeButton)
            if routingModeId==self.routingModeId:
                routingModeButton.setChecked(True)

            layout.addWidget(routingModeButton)

class OSMDisplayTab(OptionsDialogTab):
    def __init__(self, optionsConfig, parent):
        OptionsDialogTab.__init__(self, optionsConfig, parent)
        self.setFromOptionsConfig(self.getOptionsConfig())

    def getTabName(self):
        return "Display"

    def setFromOptionsConfig(self, optionsConfig):
        self.withShowAreas=optionsConfig["withShowAreas"]
        self.withShowPOI=optionsConfig["withShowPOI"]
        self.tileServer=optionsConfig["tileServer"]
        self.tileHome=optionsConfig["tileHome"]
        self.tileStartZoom=optionsConfig["tileStartZoom"]
        self.displayPOITypeList=optionsConfig["displayPOITypeList"]
        self.displayAreaTypeList=optionsConfig["displayAreaTypeList"]

    def setToOptionsConfig(self):
        self.optionsConfig["withShowAreas"]=self.withShowAreasButton.isChecked()
        self.optionsConfig["withShowPOI"]=self.withShowPOIButton.isChecked()
        self.optionsConfig["tileServer"]=self.tileServerField.text()
        self.optionsConfig["tileHome"]=self.tileHomeField.text()
        self.optionsConfig["tileStartZoom"]=int(self.tileStartZoomField.text())
        self.optionsConfig["displayPOITypeList"]=self.displayPOITypeList
        self.optionsConfig["displayAreaTypeList"]=self.displayAreaTypeList

    def addToLayout(self, layout):
        filler=QLabel(self)
        tab2Layout = QFormLayout()
        tab2Layout.setAlignment(Qt.AlignTop)
        layout.addLayout(tab2Layout)

        label=QLabel(self)
        label.setText("Tile Server:")

        self.validator=IntValueValidator(self)
        self.tileServerField=QLineEdit(self)
        self.tileServerField.setText("%s"%self.tileServer)
        self.tileServerField.setMinimumWidth(200)

        tab2Layout.addRow(label, self.tileServerField)

        label=QLabel(self)
        label.setText("Tile Dir:")

        self.validator=IntValueValidator(self)
        self.tileHomeField=QLineEdit(self)
        self.tileHomeField.setToolTip("Relative to $HOME or absolute")
        self.tileHomeField.setText("%s"%self.tileHome)
        self.tileHomeField.setMinimumWidth(200)

        tab2Layout.addRow(label, self.tileHomeField)

        label=QLabel(self)
        label.setText("Tile Zoom:")

        self.validator=IntValueValidator(self)
        self.tileStartZoomField=QLineEdit(self)
        self.tileStartZoomField.setToolTip('Zoom level until tiles are used')
        self.tileStartZoomField.setValidator(self.validator)
        self.tileStartZoomField.setText("%d"%self.tileStartZoom)

        tab2Layout.addRow(label, self.tileStartZoomField)

        self.configureAreaButton=QPushButton("Configure...", self)
        self.configureAreaButton.clicked.connect(self._configureAreaDisplay)

        self.withShowAreasButton=QCheckBox("Show Environment", self)
        self.withShowAreasButton.setChecked(self.withShowAreas)
        tab2Layout.addRow(self.withShowAreasButton, self.configureAreaButton)

        self.configurePOIButton=QPushButton("Configure...", self)
        self.configurePOIButton.clicked.connect(self._configurePOIDisplay)

        self.withShowPOIButton=QCheckBox("Show POIs", self)
        self.withShowPOIButton.setChecked(self.withShowPOI)
        tab2Layout.addRow(self.withShowPOIButton, self.configurePOIButton)

    @pyqtSlot()
    def _configurePOIDisplay(self):
        dialog=OSMPOIDisplayDialog(self, self.displayPOITypeList)
        result=dialog.exec()

    @pyqtSlot()
    def _configureAreaDisplay(self):
        dialog=OSMAreaDisplayDialog(self, self.displayAreaTypeList)
        result=dialog.exec()

class OSM3DTab(OptionsDialogTab):
    def __init__(self, optionsConfig, parent):
        OptionsDialogTab.__init__(self, optionsConfig, parent)
        self.setFromOptionsConfig(self.getOptionsConfig())

    def getTabName(self):
        return "3D"

    def setFromOptionsConfig(self, optionsConfig):
        self.withShow3D=optionsConfig["withShow3D"]
        self.withShowSky=optionsConfig["withShowSky"]
        self.XAxisRotation=optionsConfig["XAxisRotation"]
        self.startZoom3D=optionsConfig["startZoom3D"]

    def setToOptionsConfig(self):
        self.optionsConfig["withShow3D"]=self.withShow3DButton.isChecked()
        self.optionsConfig["withShowSky"]=self.withShowSkyButton.isChecked()
        self.optionsConfig["XAxisRotation"]=int(self.xAxisRoationField.text())
        self.optionsConfig["startZoom3D"]=int(self.startZoom3DField.text())

    def addToLayout(self, layout):
        filler=QLabel(self)
        tab3Layout = QFormLayout()
        tab3Layout.setAlignment(Qt.AlignTop)
        layout.addLayout(tab3Layout)

        self.withShow3DButton=QCheckBox("Use 3D View", self)
        self.withShow3DButton.setChecked(self.withShow3D)
        tab3Layout.addRow(self.withShow3DButton, filler)

        self.withShowSkyButton=QCheckBox("Show Sky", self)
        self.withShowSkyButton.setChecked(self.withShowSky)
        tab3Layout.addRow(self.withShowSkyButton, filler)

        label=QLabel(self)
        label.setText("XAxis Rotation:")

        self.validator=IntValueValidator(self)
        self.xAxisRoationField=QLineEdit(self)
        self.xAxisRoationField.setToolTip('Value in degrees')
        self.xAxisRoationField.setValidator(self.validator)
        self.xAxisRoationField.setText("%d"%self.XAxisRotation)

        tab3Layout.addRow(label, self.xAxisRoationField)

        label=QLabel(self)
        label.setText("Start Zoom:")

        self.validator=IntValueValidator(self)
        self.startZoom3DField=QLineEdit(self)
        self.startZoom3DField.setValidator(self.validator)
        self.startZoom3DField.setText("%d"%self.startZoom3D)

        tab3Layout.addRow(label, self.startZoom3DField)

tabClassList=[OSMDisplayTab, OSM3DTab, OSMRoutingTab]

class OSMOptionsDialog(OptionsDialog):
    def __init__(self, optionsConfig, parent):
        OptionsDialog.__init__(self, optionsConfig, tabClassList, parent)

class OSMInputDialog(QDialog):
    def __init__(self, parent, defaultValue, windowTitle, labelText):
        QDialog.__init__(self, parent)
        font = self.font()
        font.setPointSize(14)
        self.setFont(font)

        self.text=None
        self.windowTitle=windowTitle
        self.labelText=labelText
        self.defaultValue=defaultValue
        self.initUI()

    def getResult(self):
        return self.text

    def initUI(self):
        top=QVBoxLayout()
        top.setAlignment(Qt.AlignTop)
        top.setSpacing(2)

        style=QCommonStyle()

        fields=QFormLayout()
        fields.setAlignment(Qt.AlignTop|Qt.AlignLeft)

        label=QLabel(self)
        label.setText(self.labelText)

        self.textField=QLineEdit(self)
        self.textField.setText(self.defaultValue)
        self.textField.textChanged.connect(self._updateEnablement)
        self.textField.setMinimumWidth(300)

        fields.addRow(label, self.textField)

        top.addLayout(fields)

        buttons=QHBoxLayout()
        buttons.setAlignment(Qt.AlignBottom|Qt.AlignRight)

        self.cancelButton=QPushButton("Cancel", self)
        self.cancelButton.clicked.connect(self._cancel)
        buttons.addWidget(self.cancelButton)

        self.okButton=QPushButton("Ok", self)
        self.okButton.clicked.connect(self._ok)
        self.okButton.setDisabled(True)
        self.okButton.setDefault(True)
        buttons.addWidget(self.okButton)
        top.addLayout(buttons)

        self.setLayout(top)
        self.setWindowTitle(self.windowTitle)
        self.setGeometry(0, 0, 400, 50)
        self._updateEnablement()

    @pyqtSlot()
    def _updateEnablement(self):
        self.okButton.setDisabled(len(self.textField.text())==0)

    @pyqtSlot()
    def _cancel(self):
        self.done(QDialog.Rejected)

    @pyqtSlot()
    def _ok(self):
        self.text=self.textField.text()
        self.done(QDialog.Accepted)


#----------------------------
class OSMPOITableModel(QAbstractTableModel):
    dataChangedSignal = pyqtSignal(QModelIndex, QModelIndex)
    def __init__(self, parent, displayPOITypeList, withZoom):
        QAbstractTableModel.__init__(self, parent)
        self.style=OSMStyle()
        #  sort by [3]
        self.poiList=sorted(self.style.getPOIDictAsList(),  key=self.poiSort)
        self.displayPOITypeList=displayPOITypeList
        self.withZoom=withZoom
        self.defaultPixmap=self.style.getStylePixmap("poiPixmap")
        self.heightHint=self.defaultPixmap.height()+2

    def poiSort(self, item):
        return item[3]

    def rowCount(self, parent):
        return len(self.poiList)

    def columnCount(self, parent):
        if self.withZoom==True:
            return 2
        return 1

    def data(self, index, role):
        if role == Qt.TextAlignmentRole:
            return Qt.AlignLeft|Qt.AlignVCenter
        elif role == Qt.DecorationRole:
            if index.row() >= len(self.poiList):
                return None

            if index.column()==0:
                pixmapName=self.poiList[index.row()][2]
                if pixmapName!=None:
                    return self.style.getStylePixmap(pixmapName)

            return None
        elif role==Qt.CheckStateRole:
            if index.row() >= len(self.poiList):
                return None

            if index.column()==0:
                poiType=self.poiList[index.row()][1]
                if poiType in self.displayPOITypeList:
                    return Qt.Checked
                return Qt.Unchecked

            return None

        elif role == Qt.DisplayRole:
            if index.row() >= len(self.poiList):
                return ""
            desc=self.poiList[index.row()][3]
            zoom=self.poiList[index.row()][4]

            if index.column()==0:
                return desc
            if index.column()==1:
                return zoom

        elif role == Qt.SizeHintRole:
            if index.column()==0:
                return QSize(1, self.heightHint)

        return None

    def headerData(self, col, orientation, role):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                if col==0:
                    return "POI"
                if self.withZoom==True:
                    if col==1:
                        return "Zoom"
            elif role == Qt.TextAlignmentRole:
                return Qt.AlignLeft
        return None

    def flags (self, index ):
        return Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable

    def setData(self, index, value, role):
        if index.isValid() and role == Qt.CheckStateRole:
            if value==Qt.Unchecked:
                self.displayPOITypeList.remove(self.poiList[index.row()][1])
            elif value==Qt.Checked:
                self.displayPOITypeList.append(self.poiList[index.row()][1])
            self.dataChangedSignal.emit(index, index)
            return True

        return False

    def update(self, poiTypeList):
        self.beginResetModel()
        self.displayPOITypeList=poiTypeList
        self.endResetModel()

class OSMPOIDisplayDialog(QDialog):
    def __init__(self, parent, poiTypeList):
        QDialog.__init__(self, parent)
        font = self.font()
        font.setPointSize(14)
        self.setFont(font)
        self.displayPOITypeList=poiTypeList
        self.initUI()

    def getResult(self):
        return None

    def initUI(self):
        top=QVBoxLayout()
        top.setAlignment(Qt.AlignTop)
        top.setSpacing(2)

        self.poiView=QTableView(self)
        top.addWidget(self.poiView)

        self.poiViewModel=OSMPOITableModel(self, self.displayPOITypeList, True)
        self.poiView.setModel(self.poiViewModel)
        header=QHeaderView(Qt.Horizontal, self.poiView)
        header.setStretchLastSection(True)
        self.poiView.setHorizontalHeader(header)
        self.poiView.setColumnWidth(0, 300)
        self.poiView.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.poiView.resizeRowsToContents()

        style=QCommonStyle()

        buttons=QHBoxLayout()
        buttons.setAlignment(Qt.AlignBottom|Qt.AlignRight)

#        self.cancelButton=QPushButton("Cancel", self)
#        self.cancelButton.clicked.connect(self._cancel)
#        buttons.addWidget(self.cancelButton)

        self.okButton=QPushButton("Ok", self)
        self.okButton.clicked.connect(self._ok)
        self.okButton.setDefault(True)
        buttons.addWidget(self.okButton)
        top.addLayout(buttons)

        self.setLayout(top)
        self.setWindowTitle('POI Display Selection')
        self.setGeometry(0, 0, 500, 500)

    @pyqtSlot()
    def _ok(self):
        self.done(QDialog.Accepted)

    @pyqtSlot()
    def _cancel(self):
        self.done(QDialog.Rejected)

#----------------------------
class OSMAreaTableModel(QAbstractTableModel):
    dataChangedSignal = pyqtSignal(QModelIndex, QModelIndex)
    def __init__(self, parent, displayAreaTypeList):
        QAbstractTableModel.__init__(self, parent)
        self.style=OSMStyle()
        self.areaList=self.style.getAreaDictAsList()
        self.displayAreaTypeList=displayAreaTypeList

    def rowCount(self, parent):
        return len(self.areaList)

    def columnCount(self, parent):
        return 2

    def data(self, index, role):
        if role == Qt.TextAlignmentRole:
            return Qt.AlignLeft|Qt.AlignVCenter

        elif role==Qt.CheckStateRole:
            if index.row() >= len(self.areaList):
                return None

            if index.column()==0:
                areaType=self.areaList[index.row()][1]
                if areaType in self.displayAreaTypeList:
                    return Qt.Checked
                return Qt.Unchecked

            return None

        elif role == Qt.DisplayRole:
            if index.row() >= len(self.areaList):
                return ""
            desc=self.areaList[index.row()][2]
            zoom=self.areaList[index.row()][3]
            if index.column()==0:
                return desc
            if index.column()==1:
                return zoom

        return None

    def headerData(self, col, orientation, role):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                if col==0:
                    return "Areas"
                if col==1:
                    return "Zoom"
            elif role == Qt.TextAlignmentRole:
                return Qt.AlignLeft
        return None

    def flags (self, index ):
        return Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable


    def setData(self, index, value, role):
        if index.isValid() and role == Qt.CheckStateRole:
            if value==Qt.Unchecked:
                self.displayAreaTypeList.remove(self.areaList[index.row()][1])
            elif value==Qt.Checked:
                self.displayAreaTypeList.append(self.areaList[index.row()][1])
            self.dataChangedSignal.emit(index, index)
            return True

        return False

class OSMAreaDisplayDialog(QDialog):
    def __init__(self, parent, areaTypeList):
        QDialog.__init__(self, parent)
        font = self.font()
        font.setPointSize(14)
        self.setFont(font)
        self.displayAreaTypeList=areaTypeList
        self.initUI()

    def getResult(self):
        return None

    def initUI(self):
        top=QVBoxLayout()
        top.setAlignment(Qt.AlignTop)
        top.setSpacing(2)

        self.areaView=QTableView(self)
        top.addWidget(self.areaView)

        self.areaViewModel=OSMAreaTableModel(self, self.displayAreaTypeList)
        self.areaView.setModel(self.areaViewModel)
        header=QHeaderView(Qt.Horizontal, self.areaView)
        header.setStretchLastSection(True)
        self.areaView.setHorizontalHeader(header)
        self.areaView.setColumnWidth(0, 200)
        self.areaView.setSelectionBehavior(QAbstractItemView.SelectRows)

        style=QCommonStyle()

        buttons=QHBoxLayout()
        buttons.setAlignment(Qt.AlignBottom|Qt.AlignRight)

#        self.cancelButton=QPushButton("Cancel", self)
#        self.cancelButton.clicked.connect(self._cancel)
#        buttons.addWidget(self.cancelButton)

        self.okButton=QPushButton("Ok", self)
        self.okButton.clicked.connect(self._ok)
        self.okButton.setDefault(True)
        buttons.addWidget(self.okButton)
        top.addLayout(buttons)

        self.setLayout(top)
        self.setWindowTitle('Environment Display Selection')
        self.setGeometry(0, 0, 400, 500)

    @pyqtSlot()
    def _ok(self):
        self.done(QDialog.Accepted)

    @pyqtSlot()
    def _cancel(self):
        self.done(QDialog.Rejected)
#-------------------------------------------

class OSMPOIListTableModel(QAbstractTableModel):
    def __init__(self, adminAreaDict, reverseAdminAreaDict, nearestMode, style, parent):
        QAbstractTableModel.__init__(self, parent)
        self.adminAreaDict=adminAreaDict
        self.reverseAdminAreaDict=reverseAdminAreaDict
        self.nearestMode=nearestMode
        self.style=style

    def rowCount(self, parent):
        return len(self.poiList)

    def columnCount(self, parent):
        if self.nearestMode==True:
            return 3
        return 2

    def data(self, index, role):
        if role == Qt.TextAlignmentRole:
            return Qt.AlignLeft|Qt.AlignVCenter
        elif role != Qt.DisplayRole:
            return None

        if self.loading is True:
            if index.column()==0:
                return self.poiList[0]
            return ""

        if index.row() >= len(self.poiList):
            return ""
        (refId, nodeLat, nodeLon, tags, nodeType, cityId, distance, displayString)=self.poiList[index.row()]
        city=None
        if cityId!=None:
            city=self.adminAreaDict[cityId]

        if index.column()==0:
            return displayString
        elif index.column()==1:
            if self.nearestMode==True:
                d=int(distance)
                if d < 1000:
                    return str(d) + " m"
                return str(d // 1000) + " km"
            else:
                if city!=None:
                    return city
                return ""

        elif index.column()==2:
            if city!=None:
                return city
            return ""

    def headerData(self, col, orientation, role):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                if col==0:
                    return "Name"
                if col==1:
                    if self.nearestMode==True:
                        return "Distance"
                    return "City"
                if col==2:
                    return "City"
            elif role == Qt.TextAlignmentRole:
                return Qt.AlignLeft
        return None


    def update(self, poiList):
        self.beginResetModel()
        self.loading = False
        self.poiList=poiList
        self.endResetModel()

    def setLoading(self):
        self.beginResetModel()
        self.loading = True
        self.poiList=list()
        self.poiList.append("Loading...")
        self.endResetModel()

class OSMPOISearchDialog(OSMDialogWithSettings):
    updateUISignal = pyqtSignal()
    updateUICitySignal = pyqtSignal()

    def __init__(self, parent, osmParserData, mapPosition, defaultCountryId, nearestMode):
        OSMDialogWithSettings.__init__(self, parent)
        self.updateUISignal.connect(self.updateUI)
        self.updateUICitySignal.connect(self.updateUICity)

        self.osmParserData=osmParserData
        font = self.font()
        font.setPointSize(14)
        self.setFont(font)

        self.nearestMode=nearestMode
        self.currentCountryId=None
        self.defaultCountryId=defaultCountryId
        self.mapPosition=mapPosition
        self.usedPosition=self.mapPosition

        self.currentPOITypeList=list()

        self.adminAreaDict, self.reverseAdminAreaDict=osmParserData.getAdminAreaConversion()

        self.countryDict=osmParserData.getAdminCountryList()
        self.reverseCountryDict=dict()
        for osmId, countryName in self.countryDict.items():
            self.reverseCountryDict[countryName]=osmId

        self.poiList=list()
        self.filteredPOIList=list()

        self.pointType=None
        self.selectedPOI=None
        self.pointDict=dict()

        self.style=OSMStyle()
        self.startPointIcon=QIcon(self.style.getStylePixmap("startPixmap"))
        self.endPointIcon=QIcon(self.style.getStylePixmap("finishPixmap"))
        self.wayPointIcon=QIcon(self.style.getStylePixmap("wayPixmap"))
        self.mapPointIcon=QIcon(self.style.getStylePixmap("mapPointPixmap"))
        self.favoriteIcon=QIcon(self.style.getStylePixmap("favoritesBlackPixmap"))
        self.googleIcon=QIcon(self.style.getStylePixmap("googlePixmap"))

        self.cityList=list()
        self.filteredCityList=list()
        self.currentCityId=None
        self.cityRecursive=False

        self.initUI()

    def initUI(self):
        top=QVBoxLayout()
        top.setAlignment(Qt.AlignTop)
        top.setSpacing(2)

        lastCountryId=self.getSetting("osmpoisearchdialog.country")
        lastCityId=self.getSetting("osmpoisearchdialog.city")
        lastCityFilter=self.getSetting("osmpoisearchdialog.cityfilter")
        lastPOIFilter=self.getSetting("osmpoisearchdialog.poifilter")
        lastPOIList=self.getSetting("osmpoisearchdialog.poilist")
        lastIgnoreCity=self.getSetting("osmpoisearchdialog.ignorecity")
        lastRecursive=self.getSetting("osmpoisearchdialog.recursive")

        if self.nearestMode==False:
            self.countryCombo=QComboBox(self)

            defaultCountryName=None
            if lastCountryId==None or not lastCountryId in self.countryDict.keys():
                if self.defaultCountryId!=None:
                    defaultCountryName=self.countryDict[self.defaultCountryId]
            else:
                defaultCountryName=self.countryDict[lastCountryId]

            countryList=sorted(self.reverseCountryDict.keys())
            i=0
            defaultIndex=0
            for countryName in countryList:
                self.countryCombo.addItem(countryName)
                if countryName==defaultCountryName:
                    defaultIndex=i
                i=i+1

            self.countryCombo.setCurrentIndex(defaultIndex)
            self.countryCombo.activated.connect(self.countryChangedWorker)
            top.addWidget(self.countryCombo)

            self.currentCountryId=self.reverseCountryDict[self.countryCombo.currentText()]

        dataArea=QHBoxLayout()

        poiArea=QVBoxLayout()
        dataArea.addLayout(poiArea)

        poiSelectArea=QHBoxLayout()
        poiArea.addLayout(poiSelectArea)

        self.selectAllPOIButton=QPushButton("All", self)
        self.selectAllPOIButton.clicked.connect(self._selectAllPOI)
        poiSelectArea.addWidget(self.selectAllPOIButton)

        self.selectNonePOIButton=QPushButton("None", self)
        self.selectNonePOIButton.clicked.connect(self._selectNonePOI)
        poiSelectArea.addWidget(self.selectNonePOIButton)

        self.poiView=QTableView(self)
        poiArea.addWidget(self.poiView)

        if lastPOIList!=None:
            self.currentPOITypeList=lastPOIList
        self.poiViewModel=OSMPOITableModel(self, self.currentPOITypeList, False)
        self.poiView.setModel(self.poiViewModel)
        header=QHeaderView(Qt.Horizontal, self.poiView)
        header.setStretchLastSection(True)
        self.poiView.setHorizontalHeader(header)
        self.poiView.setColumnWidth(0, 300)
        self.poiView.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.poiView.resizeRowsToContents()

        if self.nearestMode==False:
            cityBox=QVBoxLayout()
            self.cityFilterEdit=QLineEdit(self)
            if lastCityFilter!=None:
                self.cityFilterEdit.setText(lastCityFilter)
            self.cityFilterEdit.textChanged.connect(self._applyFilterCity)
            cityBox.addWidget(self.cityFilterEdit)

            hbox=QHBoxLayout()
            self.ignoreCityButton=QCheckBox("No Area", self)
            if lastIgnoreCity!=None:
                self.ignoreCityButton.setChecked(lastIgnoreCity)
            self.ignoreCityButton.clicked.connect(self.ignoreCityWorker)
            hbox.addWidget(self.ignoreCityButton)

            self.cityRecursiveButton=QCheckBox("Recursive", self)
            if lastRecursive!=None:
                self.cityRecursiveButton.setChecked(lastRecursive)
            self.cityRecursiveButton.clicked.connect(self.setCityRecursiveWorker)
            hbox.addWidget(self.cityRecursiveButton)

            cityBox.addLayout(hbox)

            self.cityView=QTreeView(self)
            cityBox.addWidget(self.cityView)

            self.cityViewModel=OSMAdressTreeModelCity(self)
            self.cityView.setModel(self.cityViewModel)

            header=QHeaderView(Qt.Horizontal, self.cityView)
            header.setStretchLastSection(True)
            self.cityView.setHeader(header)

            dataArea.addLayout(cityBox)
        else:
            self.cityFilterEdit=None
            self.cityRecursiveButton=None
            self.ignoreCityButton=None

        poiArea=QVBoxLayout()

        self.poiFilterEdit=QLineEdit(self)
        if lastPOIFilter!=None:
            self.poiFilterEdit.setText(lastPOIFilter)
        self.poiFilterEdit.textChanged.connect(self._applyFilterPOI)
        poiArea.addWidget(self.poiFilterEdit)

        self.poiEntryView=QTableView(self)
        poiArea.addWidget(self.poiEntryView)
        dataArea.addLayout(poiArea)

        self.poiEntryViewModel=OSMPOIListTableModel(self.adminAreaDict, self.reverseAdminAreaDict, self.nearestMode, self.style, self)
        self.poiEntryViewModel.update(self.poiList)
        self.poiEntryView.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.poiEntryView.setModel(self.poiEntryViewModel)
        header=QHeaderView(Qt.Horizontal, self.poiEntryView)
        header.setStretchLastSection(True)
        self.poiEntryView.setHorizontalHeader(header)
        self.poiEntryView.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.poiEntryView.setColumnWidth(0, 300)

        if self.nearestMode==False:
            dataArea.setStretch(0, 1)
            dataArea.setStretch(1, 1)
            dataArea.setStretch(2, 2)
        else:
            dataArea.setStretch(0, 1)
            dataArea.setStretch(1, 3)

        top.addLayout(dataArea)

        actionButtons=QHBoxLayout()
        actionButtons.setAlignment(Qt.AlignBottom|Qt.AlignRight)

        self.searchButton=SearchButton(self)
        self.searchButton.setText("Google")
        self.searchButton.setIcon(self.googleIcon)
        self.searchButton.setSearchString(None)
        self.searchButton.setEnabled(False)
        actionButtons.addWidget(self.searchButton)

        self.webButton=WebButton(self)
        self.webButton.setText("WWW")
        self.webButton.setWebTags(None)
        self.webButton.setEnabled(False)
        actionButtons.addWidget(self.webButton)

        self.addFavButton=QPushButton("Favorite", self)
        self.addFavButton.clicked.connect(self._addFavPoint)
        self.addFavButton.setIcon(self.favoriteIcon)
        self.addFavButton.setEnabled(False)
        actionButtons.addWidget(self.addFavButton)

        self.showPointButton=QPushButton("Show", self)
        self.showPointButton.clicked.connect(self._showPoint)
        self.showPointButton.setIcon(self.mapPointIcon)
        self.showPointButton.setEnabled(False)
        actionButtons.addWidget(self.showPointButton)

        self.setStartPointButton=QPushButton("Start", self)
        self.setStartPointButton.clicked.connect(self._setStartPoint)
        self.setStartPointButton.setIcon(self.startPointIcon)
        self.setStartPointButton.setEnabled(False)
        actionButtons.addWidget(self.setStartPointButton)

        self.setEndPointButton=QPushButton("Finish", self)
        self.setEndPointButton.clicked.connect(self._setEndPoint)
        self.setEndPointButton.setIcon(self.endPointIcon)
        self.setEndPointButton.setEnabled(False)
        actionButtons.addWidget(self.setEndPointButton)

        self.setWayPointButton=QPushButton("Way", self)
        self.setWayPointButton.clicked.connect(self._setWayPoint)
        self.setWayPointButton.setIcon(self.wayPointIcon)
        self.setWayPointButton.setEnabled(False)
        actionButtons.addWidget(self.setWayPointButton)

        top.addLayout(actionButtons)

        buttons=QHBoxLayout()
        buttons.setAlignment(Qt.AlignBottom|Qt.AlignRight)

        style=QCommonStyle()

        #self.cancelButton=QPushButton("Cancel", self)
        #self.cancelButton.clicked.connect(self._cancel)
        #buttons.addWidget(self.cancelButton)

        self.okButton=QPushButton("Close", self)
        self.okButton.clicked.connect(self._ok)
        self.okButton.setDefault(True)
        buttons.addWidget(self.okButton)

        top.addLayout(buttons)

        self.setLayout(top)
        self.setWindowTitle('POI Search')
        self.setGeometry(0, 0, 1024, 550)

        self.poiViewModel.dataChangedSignal.connect(self.poiListChangedWorker)
        selectionPOI = self.poiEntryView.selectionModel()
        selectionPOI.selectionChanged.connect(self._selectionChanged)

        if self.nearestMode==False:
            selectionCity = self.cityView.selectionModel()
            selectionCity.selectionChanged.connect(self.cityChangedWorker)

        if self.nearestMode==False:
            self.initCityUI()
            self.countryChangedWorker()
            if lastCityId!=None:
                nodeIndex=self.cityViewModel.searchModel(lastCityId)
                if nodeIndex!=None and nodeIndex.isValid():
                    self.cityView.setCurrentIndex(nodeIndex)

        else:
            self.poiListChangedWorker()

    def initCityUI(self):
        self.ignoreCity=self.ignoreCityButton.isChecked()
        if self.ignoreCity==True:
            self.cityView.setDisabled(True)
            self.cityFilterEdit.setDisabled(True)
            self.cityRecursiveButton.setDisabled(True)
        else:
            self.cityView.setDisabled(False)
            self.cityFilterEdit.setDisabled(False)
            self.cityRecursiveButton.setDisabled(False)

        self.cityRecursive=self.cityRecursiveButton.isChecked()

    def done(self, code):
        self.addSetting("osmpoisearchdialog.poifilter", self.poiFilterEdit.text())
        self.addSetting("osmpoisearchdialog.poilist", self.currentPOITypeList)

        if self.nearestMode==False:
            self.addSetting("osmpoisearchdialog.country", self.currentCountryId)
            self.addSetting("osmpoisearchdialog.city", self.currentCityId)
            self.addSetting("osmpoisearchdialog.cityfilter", self.cityFilterEdit.text())
            self.addSetting("osmpoisearchdialog.ignorecity", self.ignoreCityButton.isChecked())
            self.addSetting("osmpoisearchdialog.recursive", self.cityRecursiveButton.isChecked())

        return super(OSMPOISearchDialog, self).done(code)

    def distanceSort(self, item):
        return item[6]

    def displayStringSort(self, item):
        return item[7]

    @pyqtSlot()
    def _applyFilterPOI(self):
        filterValue=self.poiFilterEdit.text()
        if len(filterValue)!=0:
            if filterValue[-1]!="*":
                filterValue=filterValue+"*"
            self.filteredPOIList=list()
            filterValueMod=None
            if "ue" in filterValue or "ae" in filterValue or "oe" in filterValue:
                filterValueMod=filterValue.replace("ue","ü").replace("ae","ä").replace("oe","ö")

            for (refId, lat, lon, tags, nodeType, cityId, distance, displayString) in self.poiList:
                match=False
                matchValue=displayString
                if fnmatch(matchValue.upper(), filterValue.upper()):
                    match=True
                if match==False and filterValueMod!=None and fnmatch(matchValue.upper(), filterValueMod.upper()):
                    match=True

                if match==True:
                    self.filteredPOIList.append((refId, lat, lon, tags, nodeType, cityId, distance, displayString))

            self.poiEntryViewModel.update(self.filteredPOIList)

        else:
            self.filteredPOIList=self.poiList
            self.poiEntryViewModel.update(self.filteredPOIList)

    @pyqtSlot()
    def _useMapPosition(self):
        self.usedPosition=self.mapPosition
        self.poiListChangedWorker()

    @pyqtSlot()
    def countryChangedWorker(self):
        if self.nearestMode==False:
            self._clearCityTableSelection()
            self.currentCountryId=self.reverseCountryDict[self.countryCombo.currentText()]
            self.poiEntryViewModel.setLoading()
            worker = Worker(self._countryChanged)
            self.pool.start(worker)

    @pyqtSlot()
    def _countryChanged(self):
        self.updateCityListForCountry()
        self.cityModel=OSMCityModel(self.osmParserData, self.currentCountryId)
        self.updatePoiList()
        self.updateUISignal.emit()

    def poiListChangedWorker(self):
        self.poiEntryViewModel.setLoading()
        worker = Worker(self._poiListChanged)
        self.pool.start(worker)

    def _poiListChanged(self):
        self.updatePoiList()
        self.updateUICitySignal.emit()

    @pyqtSlot()
    def updateUI(self):
        if self.nearestMode==False:
            self.cityViewModel.update(self.cityList, self.cityModel, False)
            self._applyFilterCity()
        self._applyFilterPOI()

    @pyqtSlot()
    def updateUICity(self):
        self._applyFilterPOI()

    @pyqtSlot()
    def _cancel(self):
        self.done(QDialog.Rejected)

    @pyqtSlot()
    def _ok(self):
        self.done(QDialog.Accepted)

    def getResult(self):
        return (self.selectedPOI, self.pointType)

    def getResult2(self):
        return self.pointDict

    @pyqtSlot()
    def _showPoint(self):
        selmodel = self.poiEntryView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self.selectedPOI=self.filteredPOIList[current.row()]
            self.pointType=OSMRoutingPoint.TYPE_MAP
            self.pointDict[self.pointType]=self.selectedPOI
        self.done(QDialog.Accepted)

    @pyqtSlot()
    def _addFavPoint(self):
        selmodel = self.poiEntryView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self.selectedPOI=self.filteredPOIList[current.row()]
            self.pointType=OSMRoutingPoint.TYPE_FAVORITE
            self.pointDict[self.pointType]=self.selectedPOI

    @pyqtSlot()
    def _setWayPoint(self):
        selmodel = self.poiEntryView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self.selectedPOI=self.filteredPOIList[current.row()]
            self.pointType=OSMRoutingPoint.TYPE_WAY
            self.pointDict[self.pointType]=self.selectedPOI

    @pyqtSlot()
    def _setStartPoint(self):
        selmodel = self.poiEntryView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self.selectedPOI=self.filteredPOIList[current.row()]
            self.pointType=OSMRoutingPoint.TYPE_START
            self.pointDict[self.pointType]=self.selectedPOI

    @pyqtSlot()
    def _setEndPoint(self):
        selmodel = self.poiEntryView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self.selectedPOI=self.filteredPOIList[current.row()]
            self.pointType=OSMRoutingPoint.TYPE_END
            self.pointDict[self.pointType]=self.selectedPOI

    @pyqtSlot()
    def _selectionChanged(self):
        selmodel = self.poiEntryView.selectionModel()
        current = selmodel.currentIndex()
        self.setEndPointButton.setEnabled(current.isValid())
        self.setStartPointButton.setEnabled(current.isValid())
        self.setWayPointButton.setEnabled(current.isValid())
        self.showPointButton.setEnabled(current.isValid())
        self.addFavButton.setEnabled(current.isValid())

        selmodel = self.poiEntryView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            selectedPOI=self.filteredPOIList[current.row()]
            (refId, nodeLat, nodeLon, tags, nodeType, cityId, distance, displayString)=selectedPOI
            if displayString!=Constants.UNKNOWN_NAME_TAG:
                self.searchButton.setEnabled(True)
                city=self.adminAreaDict[cityId]
                searchString=displayString+" "+city
                if "addr:street" in tags:
                    searchString=searchString+" "+tags["addr:street"]

                self.searchButton.setSearchString(searchString)
            else:
                self.searchButton.setEnabled(False)
                self.searchButton.setSearchString(None)

            webTags=self.osmParserData.getPOIWebTags(tags)
            if len(webTags)!=0:
                self.webButton.setWebTags(webTags)
                self.webButton.setEnabled(True)
            else:
                self.webButton.setWebTags(None)
                self.webButton.setEnabled(False)

    def updatePoiList(self):
        if len(self.currentPOITypeList)!=0:
            if self.nearestMode == True:
                self.poiList=self.osmParserData.getPOIsOfNodeTypeWithDistance(self.usedPosition[0], self.usedPosition[1], self.currentPOITypeList, None, None, self.cityRecursive, 100)
            else:
                if self.ignoreCity == True:
                    self.poiList=self.osmParserData.getPOIsOfNodeTypeWithDistance(self.usedPosition[0], self.usedPosition[1], self.currentPOITypeList, self.currentCountryId, None, self.cityRecursive)
                else:
                    if self.currentCityId != None:
                        self.poiList=self.osmParserData.getPOIsOfNodeTypeWithDistance(self.usedPosition[0], self.usedPosition[1], self.currentPOITypeList, self.currentCountryId, self.currentCityId, self.cityRecursive)
                    else:
                        self.poiList=list()
            if self.nearestMode==True:
                self.poiList=sorted(self.poiList, key=self.distanceSort)
            else:
                self.poiList=sorted(self.poiList, key=self.displayStringSort)
        else:
            self.poiList=list()

    def citySort(self, item):
        return item[1]

    def updateCityListForCountry(self):
        if self.currentCountryId!=None:
            self.cityList=list()
            self.osmParserData.getAdminChildsForIdRecursive(self.currentCountryId, self.cityList)
            self.cityList.sort(key=self.citySort)
        else:
            self.cityList=list()

    @pyqtSlot()
    def _selectAllPOI(self):
        self.currentPOITypeList=self.style.getAllPOIList()
        self.poiViewModel.update(self.currentPOITypeList)
        self.poiListChangedWorker()

    @pyqtSlot()
    def _selectNonePOI(self):
        self.currentPOITypeList=list()
        self.poiViewModel.update(self.currentPOITypeList)
        self.poiListChangedWorker()

    @pyqtSlot()
    def _applyFilterCity(self):
        self._clearCityTableSelection()
        filterValue=self.cityFilterEdit.text()
        if len(filterValue)!=0:
            if filterValue[-1]!="*":
                filterValue=filterValue+"*"
            self.filteredCityList=list()
            filterValueMod=None
            if "ue" in filterValue or "ae" in filterValue or "oe" in filterValue:
                filterValueMod=filterValue.replace("ue","ü").replace("ae","ä").replace("oe","ö")

            for (cityId, cityName, adminLevel) in self.cityList:
                match=False
                if fnmatch(cityName.upper(), filterValue.upper()):
                    match=True
                if match==False and filterValueMod!=None and fnmatch(cityName.upper(), filterValueMod.upper()):
                    match=True

                if match==True:
                    self.filteredCityList.append((cityId, cityName, adminLevel))

            self.cityViewModel.update(self.filteredCityList, self.cityModel)
            self.cityView.expandAll()

        else:
            self.filteredCityList=self.cityList
            self.cityViewModel.update(self.filteredCityList, self.cityModel)
            self.cityView.expandAll()

    @pyqtSlot()
    def cityChangedWorker(self):
        selmodel = self.cityView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self.currentCityId=self.cityViewModel.data(current, Qt.UserRole)
            worker = Worker(self.updatePoiCityList)
            self.pool.start(worker)

    @pyqtSlot()
    def ignoreCityWorker(self):
        self.initCityUI()
        self.poiEntryViewModel.setLoading()
        worker = Worker(self.updatePoiCityList)
        self.pool.start(worker)

    def updatePoiCityList(self):
        self.updatePoiList()
        self.updateUICitySignal.emit()

    @pyqtSlot()
    def setCityRecursiveWorker(self):
        self.cityRecursive=self.cityRecursiveButton.isChecked()
        selmodel = self.cityView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self.currentCityId=self.cityViewModel.data(current, Qt.UserRole)
            worker = Worker(self.updatePoiCityList)
            self.pool.start(worker)

    @pyqtSlot()
    def _clearCityTableSelection(self):
        self.cityView.clearSelection()
        self.currentCityId=None
