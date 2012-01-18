'''
Created on Jan 17, 2012

@author: maxl
'''

import fnmatch

from PyQt4.QtCore import QAbstractTableModel, Qt, QPoint, QSize, pyqtSlot, SIGNAL, QRect, QThread
from PyQt4.QtGui import QValidator, QFormLayout, QComboBox, QAbstractItemView, QCommonStyle, QStyle, QProgressBar, QItemSelectionModel, QInputDialog, QLineEdit, QHeaderView, QTableView, QDialog, QIcon, QLabel, QMenu, QAction, QMainWindow, QTabWidget, QCheckBox, QPalette, QVBoxLayout, QPushButton, QWidget, QPixmap, QSizePolicy, QPainter, QPen, QHBoxLayout, QApplication
from osmparser.osmparserdata import OSMParserData, OSMRoutingPoint, OSMRoute

class OSMAdressTableModel(QAbstractTableModel):
    def __init__(self, parent):
        QAbstractTableModel.__init__(self, parent)
        
    def rowCount(self, parent): 
        return len(self.streetList)
    
    def columnCount(self, parent): 
        return 2
      
    def data(self, index, role):
        if role == Qt.TextAlignmentRole:
            return Qt.AlignLeft|Qt.AlignVCenter
        elif role != Qt.DisplayRole:
            return None
        
        if index.row() >= len(self.streetList):
            return ""
        (id, streetName, houseNumber, lat, lon)=self.streetList[index.row()]

        if index.column()==0:
            return streetName
        elif index.column()==1:
            return houseNumber
        
    def headerData(self, col, orientation, role):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                if col==0:
                    return "Street"
                elif col==1:
                    return "Number"
            elif role == Qt.TextAlignmentRole:
                return Qt.AlignLeft
        return None
    
   
    def update(self, streetList):
        self.streetList=streetList
        self.reset()
        
class OSMAdressTableModelCity(QAbstractTableModel):
    def __init__(self, parent):
        QAbstractTableModel.__init__(self, parent)
        
    def rowCount(self, parent): 
        return len(self.cityList)
    
    def columnCount(self, parent): 
        return 2
      
    def data(self, index, role):
        if role == Qt.TextAlignmentRole:
            return Qt.AlignLeft|Qt.AlignVCenter
        elif role != Qt.DisplayRole:
            return None
        
        if index.row() >= len(self.cityList):
            return ""
        city, postCode=self.cityList[index.row()]

        if index.column()==0:
            return city
        elif index.column()==1:
            return postCode

    def headerData(self, col, orientation, role):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                if col==0:
                    return "City"
                elif col==1:
                    return "PostCode"
            elif role == Qt.TextAlignmentRole:
                return Qt.AlignLeft
        return None
    
   
    def update(self, cityList):
        self.cityList=cityList
        self.reset()
        
class OSMAdressDialog(QDialog):
    def __init__(self, parent, osmParserData):
        QDialog.__init__(self, parent) 

        self.osmParserData=osmParserData
        font = self.font()
        font.setPointSize(14)
        self.setFont(font)

        self.countryList=sorted(self.osmParserData.getAdressCountryList())
        self.cityList=list()
        self.filteredCityList=list()
        self.filteredStreetList=list()
        self.streetList=list()
        
        self.currentCountry=-1
        self.currentCity=None
        
        self.pointType=0
        self.startPointIcon=QIcon("images/source.png")
        self.endPointIcon=QIcon("images/target.png")
        self.wayPointIcon=QIcon("images/waypoint.png")
        self.selectedAddress=None
        self.initUI()
         
    def updateAdressListForCity(self):
        if self.currentCity!=None:
            self.streetList=sorted(self.osmParserData.getAdressListForCity(self.currentCountry, self.currentCity), key=self.streetNameSort)
        else:
            self.streetList=list()
        
        self.filteredStreetList=self.streetList

    def updateCityListForCountry(self):
        if self.currentCountry!=-1:
            self.cityList=self.osmParserData.getAdressCityList(self.currentCountry)
        else:
            self.cityList=list()
        
        self.filteredCityList=self.cityList
        
    def streetNameSort(self, item):
        return item[1]

    def houseNumberSort(self, item):
        return item[2]
   
    def citySort(self, item):
        return item[0]
    
    def getResult(self):
        return (self.selectedAddress, self.pointType)

    def initUI(self):
        top=QVBoxLayout()
        top.setAlignment(Qt.AlignTop)
        
        self.countryCombo=QComboBox(self)
        for country in self.countryList:
            countryName=self.osmParserData.getCountryNameForId(country)
            self.countryCombo.addItem(countryName)
        self.countryCombo.activated.connect(self._countryChanged)
        top.addWidget(self.countryCombo)
        
        self.currentCountry=self.countryList[0]
        self.updateCityListForCountry()

        self.cityFilterEdit=QLineEdit(self)
        self.cityFilterEdit.textChanged.connect(self._applyFilterCity)
        top.addWidget(self.cityFilterEdit)
        
        self.cityView=QTableView(self)
        top.addWidget(self.cityView)
        
        self.cityViewModel=OSMAdressTableModelCity(self)
        self.cityViewModel.update(self.filteredCityList)
        self.cityView.setModel(self.cityViewModel)
        header=QHeaderView(Qt.Horizontal, self.cityView)
        header.setStretchLastSection(True)
        self.cityView.setHorizontalHeader(header)
        self.cityView.setColumnWidth(0, 300)
        self.cityView.setSelectionBehavior(QAbstractItemView.SelectRows)

        self.streetFilterEdit=QLineEdit(self)
        self.streetFilterEdit.textChanged.connect(self._applyFilterStreet)
        top.addWidget(self.streetFilterEdit)
        
        self.streetView=QTableView(self)
        top.addWidget(self.streetView)
        
        self.streetViewModel=OSMAdressTableModel(self)
        self.streetViewModel.update(self.filteredStreetList)
        self.streetView.setModel(self.streetViewModel)
        header=QHeaderView(Qt.Horizontal, self.streetView)
        header.setStretchLastSection(True)
        self.streetView.setHorizontalHeader(header)
        self.streetView.setColumnWidth(0, 300)
        self.streetView.setSelectionBehavior(QAbstractItemView.SelectRows)

        actionButtons=QHBoxLayout()
        actionButtons.setAlignment(Qt.AlignBottom|Qt.AlignRight)
        
        self.showPointButton=QPushButton("Show", self)
        self.showPointButton.clicked.connect(self._showPoint)
        self.showPointButton.setEnabled(False)
        actionButtons.addWidget(self.showPointButton)

        self.setStartPointButton=QPushButton("Start", self)
        self.setStartPointButton.clicked.connect(self._setStartPoint)
        self.setStartPointButton.setIcon(self.startPointIcon)
        self.setStartPointButton.setEnabled(False)
        actionButtons.addWidget(self.setStartPointButton)
        
        self.setEndPointButton=QPushButton("End", self)
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
                
        self.cancelButton=QPushButton("Close", self)
        self.cancelButton.setIcon(style.standardIcon(QStyle.SP_DialogCloseButton))
        self.cancelButton.clicked.connect(self._cancel)
        buttons.addWidget(self.cancelButton)

#        self.okButton=QPushButton("End Point", self)
#        self.okButton.clicked.connect(self._ok)
#        self.okButton.setIcon(style.standardIcon(QStyle.SP_DialogOkButton))
#        self.okButton.setEnabled(False)
#        self.okButton.setDefault(True)
#        buttons.addWidget(self.okButton)

        top.addLayout(buttons)
        
        self.connect(self.streetView.selectionModel(),
                     SIGNAL("selectionChanged(const QItemSelection &, const QItemSelection &)"), self._selectionChanged)

        self.connect(self.cityView.selectionModel(),
                     SIGNAL("selectionChanged(const QItemSelection &, const QItemSelection &)"), self._cityChanged)

        self.setLayout(top)
        self.setWindowTitle('Way Search')
        self.setGeometry(0, 0, 700, 600)
                
    @pyqtSlot()
    def _countryChanged(self):
        self._clearCityTableSelection()
        self._clearStreetTableSelection()

        country=self.countryCombo.currentText()
        self.currentCountry=self.osmParserData.getCountryIdForName(country)
        self.updateCityListForCountry()
        self.cityViewModel.update(self.cityList)
        
        self.currentCity=None
        self.updateAdressListForCity()
        self._applyFilterStreet()
        self._applyFilterCity()
        
    @pyqtSlot()
    def _cityChanged(self):
        self._clearStreetTableSelection(
                                        )
        selmodel = self.cityView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self.currentCity, postCode=self.filteredCityList[current.row()]
            self.updateAdressListForCity()
            self._applyFilterStreet()
        
    @pyqtSlot()
    def _selectionChanged(self):
        selmodel = self.streetView.selectionModel()
        current = selmodel.currentIndex()
#        self.okButton.setEnabled(current.isValid())
        self.setEndPointButton.setEnabled(current.isValid())
        self.setStartPointButton.setEnabled(current.isValid())
        self.setWayPointButton.setEnabled(current.isValid())
        self.showPointButton.setEnabled(current.isValid())

        
    @pyqtSlot()
    def _cancel(self):
        self.done(QDialog.Rejected)
        
    @pyqtSlot()
    def _showPoint(self):
        selmodel = self.streetView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self.selectedAddress=self.filteredStreetList[current.row()]
            self.pointType=-1
        self.done(QDialog.Accepted)

#    def _ok(self):
#        selmodel = self.streetView.selectionModel()
#        current = selmodel.currentIndex()
#        if current.isValid():
##            print(self.filteredStreetList[current.row()])
#            self.selectedAddress=self.filteredStreetList[current.row()]
##            print(self.selectedAddress)
#        self.done(QDialog.Accepted)
        
    @pyqtSlot()
    def _setWayPoint(self):
        selmodel = self.streetView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self.selectedAddress=self.filteredStreetList[current.row()]
            self.pointType=2
        self.done(QDialog.Accepted)

    @pyqtSlot()
    def _setStartPoint(self):
        selmodel = self.streetView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self.selectedAddress=self.filteredStreetList[current.row()]
            self.pointType=0
        self.done(QDialog.Accepted)

    @pyqtSlot()
    def _setEndPoint(self):
        selmodel = self.streetView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self.selectedAddress=self.filteredStreetList[current.row()]
            self.pointType=1
        self.done(QDialog.Accepted)
        
    @pyqtSlot()
    def _clearStreetTableSelection(self):
        self.streetView.clearSelection()
#        self.okButton.setEnabled(False)
        self.setWayPointButton.setEnabled(False)
        self.setStartPointButton.setEnabled(False)
        self.setEndPointButton.setEnabled(False)
        self.showPointButton.setEnabled(False)

    @pyqtSlot()
    def _clearCityTableSelection(self):
        self.cityView.clearSelection()
        
    @pyqtSlot()
    def _applyFilterStreet(self):
        self._clearStreetTableSelection()
        filterValue=self.streetFilterEdit.text()
        if len(filterValue)!=0:
            if filterValue[-1]!="*":
                filterValue=filterValue+"*"
            self.filteredStreetList=list()
            filterValueMod=filterValue.replace("ue","ü").replace("ae","ä").replace("oe","ö")
            
            for (id, streetName, houseNumber, lat, lon) in self.streetList:
                if not fnmatch.fnmatch(streetName.upper(), filterValue.upper()) and not fnmatch.fnmatch(streetName.upper(), filterValueMod.upper()):
                    continue
                self.filteredStreetList.append((id, streetName, houseNumber, lat, lon))
        else:
            self.filteredStreetList=self.streetList
        
        self.streetViewModel.update(self.filteredStreetList)
    
    @pyqtSlot()
    def _applyFilterCity(self):
        self._clearCityTableSelection()
        filterValue=self.cityFilterEdit.text()
        if len(filterValue)!=0:
            if filterValue[-1]!="*":
                filterValue=filterValue+"*"
            self.filteredCityList=list()
            filterValueMod=filterValue.replace("ue","ü").replace("ae","ä").replace("oe","ö")
            
            for (city, postCode) in self.cityList:
                if not fnmatch.fnmatch(city.upper(), filterValue.upper()) and not fnmatch.fnmatch(city.upper(), filterValueMod.upper()):
                    continue
                self.filteredCityList.append((city, postCode))
        else:
            self.filteredCityList=self.cityList
        
        self.cityViewModel.update(self.filteredCityList)

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
        self.favoriteList=favoriteList
        self.reset()
        
class OSMFavoritesDialog(QDialog):
    def __init__(self, parent, favoriteList):
        QDialog.__init__(self, parent) 
        font = self.font()
        font.setPointSize(14)
        self.setFont(font)

        self.favoriteList=sorted(favoriteList)
        self.filteredFavoriteList=self.favoriteList

        self.selectedFavorite=None
        self.pointType=0
        self.startPointIcon=QIcon("images/source.png")
        self.endPointIcon=QIcon("images/target.png")
        self.wayPointIcon=QIcon("images/waypoint.png")

        self.initUI()
         
#    def nameSort(self, item):
#       (name, ref)=item
#       return name
   
    def getResult(self):
        return (self.selectedFavorite, self.pointType)
    
    def initUI(self):
        top=QVBoxLayout()
        top.setAlignment(Qt.AlignTop)
        
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
        self.favoriteView.setColumnWidth(0, 300)

        actionButtons=QHBoxLayout()
        actionButtons.setAlignment(Qt.AlignBottom|Qt.AlignRight)
        
        self.showPointButton=QPushButton("Show", self)
        self.showPointButton.clicked.connect(self._showPoint)
        self.showPointButton.setEnabled(False)
        actionButtons.addWidget(self.showPointButton)

        self.setStartPointButton=QPushButton("Start", self)
        self.setStartPointButton.clicked.connect(self._setStartPoint)
        self.setStartPointButton.setIcon(self.startPointIcon)
        self.setStartPointButton.setEnabled(False)
        actionButtons.addWidget(self.setStartPointButton)
        
        self.setEndPointButton=QPushButton("End", self)
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

        self.closeButton=QPushButton("Close", self)
        self.closeButton.clicked.connect(self._cancel)
        self.closeButton.setIcon(style.standardIcon(QStyle.SP_DialogCloseButton))
        self.closeButton.setDefault(True)
        buttons.addWidget(self.closeButton)
        top.addLayout(buttons)

        self.connect(self.favoriteView.selectionModel(),
                     SIGNAL("selectionChanged(const QItemSelection &, const QItemSelection &)"), self._selectionChanged)

        self.setLayout(top)
        self.setWindowTitle('Favorites')
        self.setGeometry(0, 0, 400, 400)
        
    @pyqtSlot()
    def _selectionChanged(self):
        selmodel = self.favoriteView.selectionModel()
        current = selmodel.currentIndex()
        self.setEndPointButton.setEnabled(current.isValid())
        self.setStartPointButton.setEnabled(current.isValid())
        self.setWayPointButton.setEnabled(current.isValid())
        self.showPointButton.setEnabled(current.isValid())
        
    @pyqtSlot()
    def _cancel(self):
        self.done(QDialog.Rejected)
        
    @pyqtSlot()
    def _showPoint(self):
        selmodel = self.favoriteView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self.selectedFavorite=self.filteredFavoriteList[current.row()]
            self.pointType=-1
        self.done(QDialog.Accepted)
        
    @pyqtSlot()
    def _setWayPoint(self):
        selmodel = self.favoriteView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self.selectedFavorite=self.filteredFavoriteList[current.row()]
            self.pointType=2
        self.done(QDialog.Accepted)

    @pyqtSlot()
    def _setStartPoint(self):
        selmodel = self.favoriteView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self.selectedFavorite=self.filteredFavoriteList[current.row()]
            self.pointType=0
        self.done(QDialog.Accepted)

    @pyqtSlot()
    def _setEndPoint(self):
        selmodel = self.favoriteView.selectionModel()
        current = selmodel.currentIndex()
        if current.isValid():
            self.selectedFavorite=self.filteredFavoriteList[current.row()]
            self.pointType=1
        self.done(QDialog.Accepted)
        
    @pyqtSlot()
    def _clearTableSelection(self):
        self.favoriteView.clearSelection()
        self.setWayPointButton.setEnabled(False)
        self.setStartPointButton.setEnabled(False)
        self.setEndPointButton.setEnabled(False)
        self.showPointButton.setEnabled(False)
        
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
                if not fnmatch.fnmatch(name.upper(), self.filterValue.upper()) and not fnmatch.fnmatch(name.upper(), filterValueMod.upper()):
                    continue
                self.filteredFavoriteList.append(point)
        else:
            self.filteredFavoriteList=self.favoriteList
        
        self.favoriteViewModel.update(self.filteredFavoriteList)
        
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
        self.routeList=routeList
        self.reset()

#--------------------------------------------------        
class OSMRouteListDialog(QDialog):
    def __init__(self, parent, routeList, withDelete, withClose):
        QDialog.__init__(self, parent) 
        font = self.font()
        font.setPointSize(14)
        self.setFont(font)

        self.routeList=list()
        self.routeList.extend(routeList)
        sorted(self.routeList, key=self.nameSort)
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
        self.routeView.setColumnWidth(0, 300)

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
        
        style=QCommonStyle()

        self.cancelButton=QPushButton("Cancel", self)
        self.cancelButton.clicked.connect(self._cancel)
        self.cancelButton.setIcon(style.standardIcon(QStyle.SP_DialogCancelButton))
        self.cancelButton.setDefault(True)
        buttons.addWidget(self.cancelButton)
        
        if self.withClose==True:
            self.closeButton=QPushButton("Close", self)
            self.closeButton.clicked.connect(self._close)
            self.closeButton.setIcon(style.standardIcon(QStyle.SP_DialogCloseButton))
            buttons.addWidget(self.closeButton)

        self.okButton=QPushButton("Ok", self)
        self.okButton.clicked.connect(self._ok)
        self.okButton.setDefault(True)
        self.okButton.setEnabled(False)

        self.okButton.setIcon(style.standardIcon(QStyle.SP_DialogOkButton))
        buttons.addWidget(self.okButton)

        top.addLayout(buttons)

        self.connect(self.routeView.selectionModel(),
                     SIGNAL("selectionChanged(const QItemSelection &, const QItemSelection &)"), self._selectionChanged)

        self.setLayout(top)
        self.setWindowTitle('Routes')
        self.setGeometry(0, 0, 400, 400)
        
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
                if not fnmatch.fnmatch(name.upper(), self.filterValue.upper()) and not fnmatch.fnmatch(name.upper(), filterValueMod.upper()):
                    continue
                self.filteredRouteList.append(route)
        else:
            self.filteredRouteList=self.routeList
        
        self.routeViewModel.update(self.filteredRouteList)
#----------------------------
class OSMRouteTableModel(QAbstractTableModel):
    def __init__(self, parent):
        QAbstractTableModel.__init__(self, parent)
        
    def rowCount(self, parent): 
        return len(self.routingPointList)
    
    def columnCount(self, parent): 
        return 1
      
    def data(self, index, role):
        if role == Qt.TextAlignmentRole:
            return Qt.AlignLeft|Qt.AlignVCenter
        elif role != Qt.DisplayRole:
            return None
        
        if index.row() >= len(self.routingPointList):
            return ""
        point=self.routingPointList[index.row()]
        name=point.getName()
        
        if index.column()==0:
            return name
       
    def headerData(self, col, orientation, role):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                if col==0:
                    return "Routing Point"
            elif role == Qt.TextAlignmentRole:
                return Qt.AlignLeft
        return None
    
   
    def update(self, routingPointList):
        self.routingPointList=routingPointList
        self.reset()
        
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
                
        self.routeView=QTableView(self)
        top.addWidget(self.routeView)
        
        self.routeViewModel=OSMRouteTableModel(self)
        self.routeViewModel.update(self.routingPointList)
        self.routeView.setModel(self.routeViewModel)
        header=QHeaderView(Qt.Horizontal, self.routeView)
        header.setStretchLastSection(True)
        self.routeView.setHorizontalHeader(header)
        self.routeView.setColumnWidth(0, 300)

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
        self.cancelButton.setIcon(style.standardIcon(QStyle.SP_DialogCancelButton))
        buttons.addWidget(self.cancelButton)

        self.okButton=QPushButton("Ok", self)
        self.okButton.clicked.connect(self._ok)
        self.okButton.setDefault(True)
        self.okButton.setIcon(style.standardIcon(QStyle.SP_DialogOkButton))
        buttons.addWidget(self.okButton)
        top.addLayout(buttons)
                
        self.connect(self.routeView.selectionModel(),
                     SIGNAL("selectionChanged(const QItemSelection &, const QItemSelection &)"), self._selectionChanged)

        self.setLayout(top)
        self.setWindowTitle('Routing Point')
        self.setGeometry(0, 0, 400, 400)
        
    @pyqtSlot()
    def _saveRoute(self):
        routeNameDialog=QInputDialog(self)
        routeNameDialog.setLabelText("Route Name")
        routeNameDialog.setWindowTitle("Save Route")
        font = self.font()
        font.setPointSize(14)
        routeNameDialog.setFont(font)

        result=routeNameDialog.exec()
        if result==QDialog.Accepted:
            name=routeNameDialog.textValue()
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

            self.routeViewModel.update(self.routingPointList)
            selmodel.setCurrentIndex(self.routeViewModel.index(current.row()+1, current.column()), QItemSelectionModel.ClearAndSelect)

    @pyqtSlot()
    def _clearTableSelection(self):
        self.routeView.clearSelection()
        self.removePointButton.setEnabled(False)
        self.upPointButton.setEnabled(False)
        self.downPointButton.setEnabled(False)
        self.revertPointsButton.setEnabled(False)
        
#---------------------
class OSMPositionValidator(QValidator):
    def __init__(self, parent):
        QValidator.__init__(self, parent) 
#        print(help(QValidator.validate))
        
    def validate(self, input, pos):
        if len(input)==0:
            return (QValidator.Acceptable, input, pos)
        try:
            f=float(input)
        except ValueError:
            return (QValidator.Invalid, input, pos)
        return (QValidator.Acceptable, input, pos)
    
class OSMPositionDialog(QDialog):
    def __init__(self, parent):
        QDialog.__init__(self, parent) 
        self.lat=0.0
        self.lon=0.0
        font = self.font()
        font.setPointSize(14)
        self.setFont(font)

        self.initUI()

    def getResult(self):
        return (self.lat, self.lon)
    
    def initUI(self):
        top=QVBoxLayout()
        top.setAlignment(Qt.AlignTop)
            
        style=QCommonStyle()

        fields=QFormLayout()
        fields.setAlignment(Qt.AlignTop|Qt.AlignLeft)

        label=QLabel(self)
        label.setText("Latitude:")
        
        self.validator=OSMPositionValidator(self)
        self.latField=QLineEdit(self)
        self.latField.setToolTip('Latitude')
        self.latField.textChanged.connect(self._updateEnablement)
        self.latField.setValidator(self.validator)

        fields.addRow(label, self.latField)

        label=QLabel(self)
        label.setText("Longitude:")

        self.lonField=QLineEdit(self)
        self.lonField.setToolTip('Latitude')
        self.lonField.textChanged.connect(self._updateEnablement)
        self.lonField.setValidator(self.validator)

        fields.addRow(label, self.lonField)
        
        top.addLayout(fields)

        buttons=QHBoxLayout()
        buttons.setAlignment(Qt.AlignBottom|Qt.AlignRight)
        
        self.cancelButton=QPushButton("Cancel", self)
        self.cancelButton.clicked.connect(self._cancel)
        self.cancelButton.setIcon(style.standardIcon(QStyle.SP_DialogCancelButton))
        buttons.addWidget(self.cancelButton)

        self.okButton=QPushButton("Ok", self)
        self.okButton.clicked.connect(self._ok)
        self.okButton.setDisabled(True)
        self.okButton.setDefault(True)
        self.okButton.setIcon(style.standardIcon(QStyle.SP_DialogOkButton))
        buttons.addWidget(self.okButton)
        top.addLayout(buttons)
                
        self.setLayout(top)
        self.setWindowTitle('Shiow Position')
        self.setGeometry(0, 0, 400, 100)

    @pyqtSlot()
    def _updateEnablement(self):
        self.okButton.setDisabled(len(self.latField.text())==0 or len(self.lonField.text())==0)
   
    @pyqtSlot()
    def _cancel(self):
        self.done(QDialog.Rejected)
        
    @pyqtSlot()
    def _ok(self):
        self.lat=float(self.latField.text())
        self.lon=float(self.lonField.text())
        self.done(QDialog.Accepted)
