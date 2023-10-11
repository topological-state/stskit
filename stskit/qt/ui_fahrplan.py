# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'fahrplan.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_FahrplanWidget(object):
    def setupUi(self, FahrplanWidget):
        FahrplanWidget.setObjectName("FahrplanWidget")
        FahrplanWidget.resize(1101, 803)
        self.verticalLayout = QtWidgets.QVBoxLayout(FahrplanWidget)
        self.verticalLayout.setObjectName("verticalLayout")
        self.splitter = QtWidgets.QSplitter(FahrplanWidget)
        self.splitter.setOrientation(QtCore.Qt.Horizontal)
        self.splitter.setObjectName("splitter")
        self.zugliste_widget = QtWidgets.QTabWidget(self.splitter)
        self.zugliste_widget.setObjectName("zugliste_widget")
        self.zugliste_tab = QtWidgets.QWidget()
        self.zugliste_tab.setObjectName("zugliste_tab")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(self.zugliste_tab)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.zugliste_view = QtWidgets.QTableView(self.zugliste_tab)
        self.zugliste_view.setAlternatingRowColors(True)
        self.zugliste_view.setObjectName("zugliste_view")
        self.verticalLayout_2.addWidget(self.zugliste_view)
        self.zugliste_widget.addTab(self.zugliste_tab, "")
        self.tabWidget_2 = QtWidgets.QTabWidget(self.splitter)
        self.tabWidget_2.setObjectName("tabWidget_2")
        self.fahrplan_tab = QtWidgets.QWidget()
        self.fahrplan_tab.setObjectName("fahrplan_tab")
        self.horizontalLayout = QtWidgets.QHBoxLayout(self.fahrplan_tab)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.fahrplan_splitter = QtWidgets.QSplitter(self.fahrplan_tab)
        self.fahrplan_splitter.setOrientation(QtCore.Qt.Vertical)
        self.fahrplan_splitter.setObjectName("fahrplan_splitter")
        self.fahrplan_label = QtWidgets.QLabel(self.fahrplan_splitter)
        self.fahrplan_label.setObjectName("fahrplan_label")
        self.fahrplan_view = QtWidgets.QTableView(self.fahrplan_splitter)
        self.fahrplan_view.setAlternatingRowColors(True)
        self.fahrplan_view.setObjectName("fahrplan_view")
        self.folgezug_label = QtWidgets.QLabel(self.fahrplan_splitter)
        self.folgezug_label.setObjectName("folgezug_label")
        self.folgezug_view = QtWidgets.QTableView(self.fahrplan_splitter)
        self.folgezug_view.setAlternatingRowColors(True)
        self.folgezug_view.setObjectName("folgezug_view")
        self.horizontalLayout.addWidget(self.fahrplan_splitter)
        self.tabWidget_2.addTab(self.fahrplan_tab, "")
        self.grafik_tab = QtWidgets.QWidget()
        self.grafik_tab.setObjectName("grafik_tab")
        self.verticalLayout_3 = QtWidgets.QVBoxLayout(self.grafik_tab)
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.grafik_area = QtWidgets.QScrollArea(self.grafik_tab)
        self.grafik_area.setWidgetResizable(True)
        self.grafik_area.setObjectName("grafik_area")
        self.grafik_widget = QtWidgets.QWidget()
        self.grafik_widget.setGeometry(QtCore.QRect(0, 0, 617, 736))
        self.grafik_widget.setObjectName("grafik_widget")
        self.grafik_area.setWidget(self.grafik_widget)
        self.verticalLayout_3.addWidget(self.grafik_area)
        self.tabWidget_2.addTab(self.grafik_tab, "")
        self.verticalLayout.addWidget(self.splitter)
        self.fahrplan_label.setBuddy(self.fahrplan_view)
        self.folgezug_label.setBuddy(self.folgezug_view)

        self.retranslateUi(FahrplanWidget)
        self.tabWidget_2.setCurrentIndex(0)
        QtCore.QMetaObject.connectSlotsByName(FahrplanWidget)

    def retranslateUi(self, FahrplanWidget):
        _translate = QtCore.QCoreApplication.translate
        FahrplanWidget.setWindowTitle(_translate("FahrplanWidget", "Form"))
        self.zugliste_widget.setTabText(self.zugliste_widget.indexOf(self.zugliste_tab), _translate("FahrplanWidget", "Züge"))
        self.fahrplan_label.setText(_translate("FahrplanWidget", "Fahrplan"))
        self.folgezug_label.setText(_translate("FahrplanWidget", "Folgezug"))
        self.tabWidget_2.setTabText(self.tabWidget_2.indexOf(self.fahrplan_tab), _translate("FahrplanWidget", "Fahrplan"))
        self.tabWidget_2.setTabText(self.tabWidget_2.indexOf(self.grafik_tab), _translate("FahrplanWidget", "Grafik"))

