# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'einstellungen.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_EinstellungenWindow(object):
    def setupUi(self, EinstellungenWindow):
        EinstellungenWindow.setObjectName("EinstellungenWindow")
        EinstellungenWindow.resize(951, 781)
        self.centralwidget = QtWidgets.QWidget(EinstellungenWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.horizontalLayout_3 = QtWidgets.QHBoxLayout(self.centralwidget)
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        self.widget = QtWidgets.QWidget(self.centralwidget)
        self.widget.setObjectName("widget")
        self.verticalLayout_3 = QtWidgets.QVBoxLayout(self.widget)
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.tab_widget = QtWidgets.QTabWidget(self.widget)
        self.tab_widget.setObjectName("tab_widget")
        self.einaus_tab = QtWidgets.QWidget()
        self.einaus_tab.setEnabled(False)
        self.einaus_tab.setObjectName("einaus_tab")
        self.einaus_view = QtWidgets.QTreeView(self.einaus_tab)
        self.einaus_view.setGeometry(QtCore.QRect(20, 20, 511, 621))
        self.einaus_view.setObjectName("einaus_view")
        self.einaus_zusammen_button = QtWidgets.QPushButton(self.einaus_tab)
        self.einaus_zusammen_button.setGeometry(QtCore.QRect(590, 30, 80, 23))
        self.einaus_zusammen_button.setObjectName("einaus_zusammen_button")
        self.einaus_teilen_button = QtWidgets.QPushButton(self.einaus_tab)
        self.einaus_teilen_button.setGeometry(QtCore.QRect(590, 60, 80, 23))
        self.einaus_teilen_button.setObjectName("einaus_teilen_button")
        self.einaus_umbenennen_button = QtWidgets.QPushButton(self.einaus_tab)
        self.einaus_umbenennen_button.setGeometry(QtCore.QRect(590, 90, 80, 23))
        self.einaus_umbenennen_button.setObjectName("einaus_umbenennen_button")
        self.einaus_rauf_button = QtWidgets.QPushButton(self.einaus_tab)
        self.einaus_rauf_button.setGeometry(QtCore.QRect(590, 120, 80, 23))
        self.einaus_rauf_button.setObjectName("einaus_rauf_button")
        self.einaus_runter_button = QtWidgets.QPushButton(self.einaus_tab)
        self.einaus_runter_button.setGeometry(QtCore.QRect(590, 150, 80, 23))
        self.einaus_runter_button.setObjectName("einaus_runter_button")
        self.tab_widget.addTab(self.einaus_tab, "")
        self.bahnhof_tab = QtWidgets.QWidget()
        self.bahnhof_tab.setEnabled(False)
        self.bahnhof_tab.setObjectName("bahnhof_tab")
        self.bahnhof_view = QtWidgets.QTreeView(self.bahnhof_tab)
        self.bahnhof_view.setGeometry(QtCore.QRect(20, 20, 601, 611))
        self.bahnhof_view.setObjectName("bahnhof_view")
        self.bahnhof_teilen_button = QtWidgets.QPushButton(self.bahnhof_tab)
        self.bahnhof_teilen_button.setGeometry(QtCore.QRect(670, 130, 80, 23))
        self.bahnhof_teilen_button.setObjectName("bahnhof_teilen_button")
        self.bahnhof_zusammen_button = QtWidgets.QPushButton(self.bahnhof_tab)
        self.bahnhof_zusammen_button.setGeometry(QtCore.QRect(670, 100, 80, 23))
        self.bahnhof_zusammen_button.setObjectName("bahnhof_zusammen_button")
        self.bahnhof_rauf_button = QtWidgets.QPushButton(self.bahnhof_tab)
        self.bahnhof_rauf_button.setGeometry(QtCore.QRect(670, 190, 80, 23))
        self.bahnhof_rauf_button.setObjectName("bahnhof_rauf_button")
        self.bahnhof_runter_button = QtWidgets.QPushButton(self.bahnhof_tab)
        self.bahnhof_runter_button.setGeometry(QtCore.QRect(670, 220, 80, 23))
        self.bahnhof_runter_button.setObjectName("bahnhof_runter_button")
        self.bahnhof_umbenennen_button = QtWidgets.QPushButton(self.bahnhof_tab)
        self.bahnhof_umbenennen_button.setGeometry(QtCore.QRect(670, 160, 80, 23))
        self.bahnhof_umbenennen_button.setObjectName("bahnhof_umbenennen_button")
        self.tab_widget.addTab(self.bahnhof_tab, "")
        self.strecken_tab = QtWidgets.QWidget()
        self.strecken_tab.setEnabled(False)
        self.strecken_tab.setObjectName("strecken_tab")
        self.tab_widget.addTab(self.strecken_tab, "")
        self.zugschema_tab = QtWidgets.QWidget()
        self.zugschema_tab.setObjectName("zugschema_tab")
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout(self.zugschema_tab)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout()
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.zugschema_name_label = QtWidgets.QLabel(self.zugschema_tab)
        self.zugschema_name_label.setObjectName("zugschema_name_label")
        self.verticalLayout_2.addWidget(self.zugschema_name_label)
        self.zugschema_name_combo = QtWidgets.QComboBox(self.zugschema_tab)
        self.zugschema_name_combo.setObjectName("zugschema_name_combo")
        self.verticalLayout_2.addWidget(self.zugschema_name_combo)
        self.zugschema_details_label = QtWidgets.QLabel(self.zugschema_tab)
        self.zugschema_details_label.setObjectName("zugschema_details_label")
        self.verticalLayout_2.addWidget(self.zugschema_details_label)
        self.zugschema_details_table = QtWidgets.QTableView(self.zugschema_tab)
        self.zugschema_details_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.zugschema_details_table.setObjectName("zugschema_details_table")
        self.verticalLayout_2.addWidget(self.zugschema_details_table)
        self.horizontalLayout_2.addLayout(self.verticalLayout_2)
        self.tab_widget.addTab(self.zugschema_tab, "")
        self.verticalLayout_3.addWidget(self.tab_widget)
        self.dialog_button_box = QtWidgets.QDialogButtonBox(self.widget)
        self.dialog_button_box.setOrientation(QtCore.Qt.Horizontal)
        self.dialog_button_box.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
        self.dialog_button_box.setObjectName("dialog_button_box")
        self.verticalLayout_3.addWidget(self.dialog_button_box)
        self.horizontalLayout_3.addWidget(self.widget)
        EinstellungenWindow.setCentralWidget(self.centralwidget)
        self.zugschema_name_label.setBuddy(self.zugschema_name_label)
        self.zugschema_details_label.setBuddy(self.zugschema_details_table)

        self.retranslateUi(EinstellungenWindow)
        self.tab_widget.setCurrentIndex(3)
        self.dialog_button_box.accepted.connect(EinstellungenWindow.accept)
        self.dialog_button_box.rejected.connect(EinstellungenWindow.reject)
        QtCore.QMetaObject.connectSlotsByName(EinstellungenWindow)

    def retranslateUi(self, EinstellungenWindow):
        _translate = QtCore.QCoreApplication.translate
        EinstellungenWindow.setWindowTitle(_translate("EinstellungenWindow", "Einstellungen"))
        self.einaus_zusammen_button.setText(_translate("EinstellungenWindow", "zusammenfassen"))
        self.einaus_teilen_button.setText(_translate("EinstellungenWindow", "aufteilen"))
        self.einaus_umbenennen_button.setText(_translate("EinstellungenWindow", "umbenennen"))
        self.einaus_rauf_button.setText(_translate("EinstellungenWindow", "rauf"))
        self.einaus_runter_button.setText(_translate("EinstellungenWindow", "runter"))
        self.tab_widget.setTabText(self.tab_widget.indexOf(self.einaus_tab), _translate("EinstellungenWindow", "Ein-/Ausfahrten"))
        self.bahnhof_teilen_button.setText(_translate("EinstellungenWindow", "aufteilen"))
        self.bahnhof_zusammen_button.setText(_translate("EinstellungenWindow", "zusammenfassen"))
        self.bahnhof_rauf_button.setText(_translate("EinstellungenWindow", "rauf"))
        self.bahnhof_runter_button.setText(_translate("EinstellungenWindow", "runter"))
        self.bahnhof_umbenennen_button.setText(_translate("EinstellungenWindow", "umbenennen"))
        self.tab_widget.setTabText(self.tab_widget.indexOf(self.bahnhof_tab), _translate("EinstellungenWindow", "Bahnhöfe"))
        self.tab_widget.setTabText(self.tab_widget.indexOf(self.strecken_tab), _translate("EinstellungenWindow", "Strecken"))
        self.zugschema_name_label.setText(_translate("EinstellungenWindow", "Zugschema"))
        self.zugschema_details_label.setText(_translate("EinstellungenWindow", "Kategorien"))
        self.tab_widget.setTabText(self.tab_widget.indexOf(self.zugschema_tab), _translate("EinstellungenWindow", "Zugschema"))

import stskit.resources_rc