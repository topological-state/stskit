# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'bildfahrplan.ui'
#
# Created by: PyQt5 UI code generator 5.15.10
#
# WARNING: Any manual changes made to this file will be lost when pyuic5 is
# run again.  Do not edit this file unless you know what you are doing.


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_BildfahrplanWindow(object):
    def setupUi(self, BildfahrplanWindow):
        BildfahrplanWindow.setObjectName("BildfahrplanWindow")
        BildfahrplanWindow.resize(800, 600)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(BildfahrplanWindow.sizePolicy().hasHeightForWidth())
        BildfahrplanWindow.setSizePolicy(sizePolicy)
        self.centralwidget = QtWidgets.QWidget(BildfahrplanWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName("verticalLayout")
        self.stackedWidget = QtWidgets.QStackedWidget(self.centralwidget)
        self.stackedWidget.setObjectName("stackedWidget")
        self.settings_page = QtWidgets.QWidget()
        self.settings_page.setObjectName("settings_page")
        self.horizontalLayout_3 = QtWidgets.QHBoxLayout(self.settings_page)
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.strecke_group = QtWidgets.QGroupBox(self.settings_page)
        self.strecke_group.setObjectName("strecke_group")
        self.verticalLayout_4 = QtWidgets.QVBoxLayout(self.strecke_group)
        self.verticalLayout_4.setObjectName("verticalLayout_4")
        self.strecke_layout = QtWidgets.QVBoxLayout()
        self.strecke_layout.setObjectName("strecke_layout")
        self.vordefiniert_label = QtWidgets.QLabel(self.strecke_group)
        self.vordefiniert_label.setObjectName("vordefiniert_label")
        self.strecke_layout.addWidget(self.vordefiniert_label)
        self.vordefiniert_combo = QtWidgets.QComboBox(self.strecke_group)
        self.vordefiniert_combo.setObjectName("vordefiniert_combo")
        self.strecke_layout.addWidget(self.vordefiniert_combo)
        self.von_label = QtWidgets.QLabel(self.strecke_group)
        self.von_label.setObjectName("von_label")
        self.strecke_layout.addWidget(self.von_label)
        self.von_combo = QtWidgets.QComboBox(self.strecke_group)
        self.von_combo.setObjectName("von_combo")
        self.strecke_layout.addWidget(self.von_combo)
        self.via_label = QtWidgets.QLabel(self.strecke_group)
        self.via_label.setObjectName("via_label")
        self.strecke_layout.addWidget(self.via_label)
        self.via_combo = QtWidgets.QComboBox(self.strecke_group)
        self.via_combo.setObjectName("via_combo")
        self.strecke_layout.addWidget(self.via_combo)
        self.nach_label = QtWidgets.QLabel(self.strecke_group)
        self.nach_label.setObjectName("nach_label")
        self.strecke_layout.addWidget(self.nach_label)
        self.nach_combo = QtWidgets.QComboBox(self.strecke_group)
        self.nach_combo.setObjectName("nach_combo")
        self.strecke_layout.addWidget(self.nach_combo)
        self.strecke_label = QtWidgets.QLabel(self.strecke_group)
        self.strecke_label.setObjectName("strecke_label")
        self.strecke_layout.addWidget(self.strecke_label)
        self.strecke_list = QtWidgets.QListWidget(self.strecke_group)
        self.strecke_list.setAlternatingRowColors(True)
        self.strecke_list.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.strecke_list.setObjectName("strecke_list")
        self.strecke_layout.addWidget(self.strecke_list)
        self.verticalLayout_4.addLayout(self.strecke_layout)
        self.horizontalLayout_2.addWidget(self.strecke_group)
        self.darstellung_group = QtWidgets.QGroupBox(self.settings_page)
        self.darstellung_group.setObjectName("darstellung_group")
        self.verticalLayout_5 = QtWidgets.QVBoxLayout(self.darstellung_group)
        self.verticalLayout_5.setObjectName("verticalLayout_5")
        self.darstellung_layout = QtWidgets.QVBoxLayout()
        self.darstellung_layout.setObjectName("darstellung_layout")
        self.vorlaufzeit_label = QtWidgets.QLabel(self.darstellung_group)
        self.vorlaufzeit_label.setObjectName("vorlaufzeit_label")
        self.darstellung_layout.addWidget(self.vorlaufzeit_label)
        self.vorlaufzeit_spin = QtWidgets.QSpinBox(self.darstellung_group)
        self.vorlaufzeit_spin.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.vorlaufzeit_spin.setMinimum(15)
        self.vorlaufzeit_spin.setMaximum(120)
        self.vorlaufzeit_spin.setSingleStep(5)
        self.vorlaufzeit_spin.setProperty("value", 55)
        self.vorlaufzeit_spin.setObjectName("vorlaufzeit_spin")
        self.darstellung_layout.addWidget(self.vorlaufzeit_spin)
        self.nachlaufzeit_label = QtWidgets.QLabel(self.darstellung_group)
        self.nachlaufzeit_label.setObjectName("nachlaufzeit_label")
        self.darstellung_layout.addWidget(self.nachlaufzeit_label)
        self.nachlaufzeit_spin = QtWidgets.QSpinBox(self.darstellung_group)
        self.nachlaufzeit_spin.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.nachlaufzeit_spin.setMinimum(5)
        self.nachlaufzeit_spin.setMaximum(120)
        self.nachlaufzeit_spin.setSingleStep(5)
        self.nachlaufzeit_spin.setProperty("value", 5)
        self.nachlaufzeit_spin.setObjectName("nachlaufzeit_spin")
        self.darstellung_layout.addWidget(self.nachlaufzeit_spin)
        self.beschriftung_group = QtWidgets.QGroupBox(self.darstellung_group)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.beschriftung_group.sizePolicy().hasHeightForWidth())
        self.beschriftung_group.setSizePolicy(sizePolicy)
        self.beschriftung_group.setObjectName("beschriftung_group")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(self.beschriftung_group)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.name_button = QtWidgets.QRadioButton(self.beschriftung_group)
        self.name_button.setObjectName("name_button")
        self.verticalLayout_2.addWidget(self.name_button)
        self.nummer_button = QtWidgets.QRadioButton(self.beschriftung_group)
        self.nummer_button.setChecked(True)
        self.nummer_button.setObjectName("nummer_button")
        self.verticalLayout_2.addWidget(self.nummer_button)
        self.darstellung_layout.addWidget(self.beschriftung_group)
        self.darstellung_stretch = QtWidgets.QWidget(self.darstellung_group)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.darstellung_stretch.sizePolicy().hasHeightForWidth())
        self.darstellung_stretch.setSizePolicy(sizePolicy)
        self.darstellung_stretch.setObjectName("darstellung_stretch")
        self.darstellung_layout.addWidget(self.darstellung_stretch)
        self.verticalLayout_5.addLayout(self.darstellung_layout)
        self.horizontalLayout_2.addWidget(self.darstellung_group)
        self.horizontalLayout_3.addLayout(self.horizontalLayout_2)
        self.stackedWidget.addWidget(self.settings_page)
        self.display_page = QtWidgets.QWidget()
        self.display_page.setObjectName("display_page")
        self.horizontalLayout = QtWidgets.QHBoxLayout(self.display_page)
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.displaySplitter = QtWidgets.QSplitter(self.display_page)
        self.displaySplitter.setOrientation(QtCore.Qt.Vertical)
        self.displaySplitter.setObjectName("displaySplitter")
        self.grafikWidget = QtWidgets.QWidget(self.displaySplitter)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.grafikWidget.sizePolicy().hasHeightForWidth())
        self.grafikWidget.setSizePolicy(sizePolicy)
        self.grafikWidget.setObjectName("grafikWidget")
        self.zuginfoLabel = QtWidgets.QLabel(self.displaySplitter)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.zuginfoLabel.sizePolicy().hasHeightForWidth())
        self.zuginfoLabel.setSizePolicy(sizePolicy)
        self.zuginfoLabel.setMaximumSize(QtCore.QSize(16777215, 50))
        self.zuginfoLabel.setBaseSize(QtCore.QSize(0, 0))
        self.zuginfoLabel.setFrameShape(QtWidgets.QFrame.Box)
        self.zuginfoLabel.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.zuginfoLabel.setTextFormat(QtCore.Qt.AutoText)
        self.zuginfoLabel.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.zuginfoLabel.setObjectName("zuginfoLabel")
        self.horizontalLayout.addWidget(self.displaySplitter)
        self.stackedWidget.addWidget(self.display_page)
        self.verticalLayout.addWidget(self.stackedWidget)
        BildfahrplanWindow.setCentralWidget(self.centralwidget)
        self.toolBar = QtWidgets.QToolBar(BildfahrplanWindow)
        self.toolBar.setMovable(False)
        self.toolBar.setIconSize(QtCore.QSize(16, 16))
        self.toolBar.setFloatable(False)
        self.toolBar.setObjectName("toolBar")
        BildfahrplanWindow.addToolBar(QtCore.Qt.TopToolBarArea, self.toolBar)
        self.actionSetup = QtWidgets.QAction(BildfahrplanWindow)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(":/equalizer.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        icon.addPixmap(QtGui.QPixmap(":/equalizer-dis.png"), QtGui.QIcon.Disabled, QtGui.QIcon.Off)
        self.actionSetup.setIcon(icon)
        self.actionSetup.setObjectName("actionSetup")
        self.actionAnzeige = QtWidgets.QAction(BildfahrplanWindow)
        icon1 = QtGui.QIcon()
        icon1.addPixmap(QtGui.QPixmap(":/slots.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        icon1.addPixmap(QtGui.QPixmap(":/slots-dis.png"), QtGui.QIcon.Disabled, QtGui.QIcon.Off)
        self.actionAnzeige.setIcon(icon1)
        self.actionAnzeige.setObjectName("actionAnzeige")
        self.actionPlusEins = QtWidgets.QAction(BildfahrplanWindow)
        icon2 = QtGui.QIcon()
        icon2.addPixmap(QtGui.QPixmap(":/clock--plus.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.actionPlusEins.setIcon(icon2)
        self.actionPlusEins.setObjectName("actionPlusEins")
        self.actionMinusEins = QtWidgets.QAction(BildfahrplanWindow)
        icon3 = QtGui.QIcon()
        icon3.addPixmap(QtGui.QPixmap(":/clock--minus.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.actionMinusEins.setIcon(icon3)
        self.actionMinusEins.setObjectName("actionMinusEins")
        self.actionFix = QtWidgets.QAction(BildfahrplanWindow)
        icon4 = QtGui.QIcon()
        icon4.addPixmap(QtGui.QPixmap(":/clock--pencil.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.actionFix.setIcon(icon4)
        self.actionFix.setObjectName("actionFix")
        self.actionLoeschen = QtWidgets.QAction(BildfahrplanWindow)
        icon5 = QtGui.QIcon()
        icon5.addPixmap(QtGui.QPixmap(":/chain--return.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.actionLoeschen.setIcon(icon5)
        self.actionLoeschen.setObjectName("actionLoeschen")
        self.actionAnkunftAbwarten = QtWidgets.QAction(BildfahrplanWindow)
        icon6 = QtGui.QIcon()
        icon6.addPixmap(QtGui.QPixmap(":/chain--arrow-in.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.actionAnkunftAbwarten.setIcon(icon6)
        self.actionAnkunftAbwarten.setObjectName("actionAnkunftAbwarten")
        self.actionAbfahrtAbwarten = QtWidgets.QAction(BildfahrplanWindow)
        icon7 = QtGui.QIcon()
        icon7.addPixmap(QtGui.QPixmap(":/chain--arrow.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.actionAbfahrtAbwarten.setIcon(icon7)
        self.actionAbfahrtAbwarten.setObjectName("actionAbfahrtAbwarten")
        self.actionBetriebshaltEinfuegen = QtWidgets.QAction(BildfahrplanWindow)
        icon8 = QtGui.QIcon()
        icon8.addPixmap(QtGui.QPixmap(":/node-insert.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.actionBetriebshaltEinfuegen.setIcon(icon8)
        self.actionBetriebshaltEinfuegen.setObjectName("actionBetriebshaltEinfuegen")
        self.actionActionBetriebshaltLoeschen = QtWidgets.QAction(BildfahrplanWindow)
        icon9 = QtGui.QIcon()
        icon9.addPixmap(QtGui.QPixmap(":/node-delete.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.actionActionBetriebshaltLoeschen.setIcon(icon9)
        self.actionActionBetriebshaltLoeschen.setObjectName("actionActionBetriebshaltLoeschen")
        self.toolBar.addAction(self.actionSetup)
        self.toolBar.addAction(self.actionAnzeige)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.actionPlusEins)
        self.toolBar.addAction(self.actionMinusEins)
        self.toolBar.addAction(self.actionFix)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.actionAnkunftAbwarten)
        self.toolBar.addAction(self.actionAbfahrtAbwarten)
        self.toolBar.addAction(self.actionLoeschen)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.actionBetriebshaltEinfuegen)
        self.toolBar.addAction(self.actionActionBetriebshaltLoeschen)
        self.vordefiniert_label.setBuddy(self.vordefiniert_combo)
        self.von_label.setBuddy(self.von_combo)
        self.via_label.setBuddy(self.via_combo)
        self.nach_label.setBuddy(self.nach_combo)
        self.strecke_label.setBuddy(self.strecke_list)
        self.vorlaufzeit_label.setBuddy(self.vorlaufzeit_spin)
        self.nachlaufzeit_label.setBuddy(self.nachlaufzeit_spin)

        self.retranslateUi(BildfahrplanWindow)
        self.stackedWidget.setCurrentIndex(1)
        QtCore.QMetaObject.connectSlotsByName(BildfahrplanWindow)

    def retranslateUi(self, BildfahrplanWindow):
        _translate = QtCore.QCoreApplication.translate
        BildfahrplanWindow.setWindowTitle(_translate("BildfahrplanWindow", "Bildfahrplan"))
        self.strecke_group.setTitle(_translate("BildfahrplanWindow", "Strecke"))
        self.vordefiniert_label.setText(_translate("BildfahrplanWindow", "Vordefinierte &Strecke"))
        self.von_label.setText(_translate("BildfahrplanWindow", "&Von"))
        self.via_label.setText(_translate("BildfahrplanWindow", "V&ia"))
        self.nach_label.setText(_translate("BildfahrplanWindow", "&Nach"))
        self.strecke_label.setText(_translate("BildfahrplanWindow", "S&trecke"))
        self.darstellung_group.setTitle(_translate("BildfahrplanWindow", "Darstellung"))
        self.vorlaufzeit_label.setText(_translate("BildfahrplanWindow", "V&orlaufzeit"))
        self.vorlaufzeit_spin.setSuffix(_translate("BildfahrplanWindow", " Min."))
        self.nachlaufzeit_label.setText(_translate("BildfahrplanWindow", "N&achlaufzeit"))
        self.nachlaufzeit_spin.setSuffix(_translate("BildfahrplanWindow", " Min."))
        self.beschriftung_group.setTitle(_translate("BildfahrplanWindow", "&Beschriftung"))
        self.name_button.setText(_translate("BildfahrplanWindow", "Zugname (Gattung + Nummer)"))
        self.nummer_button.setText(_translate("BildfahrplanWindow", "Zugnummer"))
        self.zuginfoLabel.setText(_translate("BildfahrplanWindow", "Zuginfo: (keine Auswahl)"))
        self.toolBar.setWindowTitle(_translate("BildfahrplanWindow", "Tool Bar"))
        self.actionSetup.setText(_translate("BildfahrplanWindow", "Setup"))
        self.actionSetup.setToolTip(_translate("BildfahrplanWindow", "Streckendefinition (S)"))
        self.actionSetup.setShortcut(_translate("BildfahrplanWindow", "S"))
        self.actionAnzeige.setText(_translate("BildfahrplanWindow", "Grafik"))
        self.actionAnzeige.setToolTip(_translate("BildfahrplanWindow", "Grafik anzeigen (G)"))
        self.actionAnzeige.setShortcut(_translate("BildfahrplanWindow", "G"))
        self.actionPlusEins.setText(_translate("BildfahrplanWindow", "+1"))
        self.actionPlusEins.setToolTip(_translate("BildfahrplanWindow", "Feste Verspätung +1 Minute auf ausgewähltem Segment (+)"))
        self.actionPlusEins.setShortcut(_translate("BildfahrplanWindow", "+"))
        self.actionMinusEins.setText(_translate("BildfahrplanWindow", "-1"))
        self.actionMinusEins.setToolTip(_translate("BildfahrplanWindow", "Feste Verspätung -1 Minute auf ausgewähltem Segment (-)"))
        self.actionMinusEins.setShortcut(_translate("BildfahrplanWindow", "-"))
        self.actionFix.setText(_translate("BildfahrplanWindow", "Fix"))
        self.actionFix.setToolTip(_translate("BildfahrplanWindow", "Feste Verspätung auf ausgewähltem Segment festlegen (V)"))
        self.actionFix.setShortcut(_translate("BildfahrplanWindow", "V"))
        self.actionLoeschen.setText(_translate("BildfahrplanWindow", "Löschen"))
        self.actionLoeschen.setToolTip(_translate("BildfahrplanWindow", "Korrekturen auf ausgewähltem Segment löschen (Del)"))
        self.actionLoeschen.setShortcut(_translate("BildfahrplanWindow", "Del"))
        self.actionAnkunftAbwarten.setText(_translate("BildfahrplanWindow", "Ankunft"))
        self.actionAnkunftAbwarten.setToolTip(_translate("BildfahrplanWindow", "Kreuzung/Ankunft von zweitem gewählten Zug abwarten (K)"))
        self.actionAnkunftAbwarten.setShortcut(_translate("BildfahrplanWindow", "K"))
        self.actionAbfahrtAbwarten.setText(_translate("BildfahrplanWindow", "Abfahrt"))
        self.actionAbfahrtAbwarten.setToolTip(_translate("BildfahrplanWindow", "Überholung/Abfahrt von zweitem gewählten Zug abwarten (F)"))
        self.actionAbfahrtAbwarten.setShortcut(_translate("BildfahrplanWindow", "F"))
        self.actionBetriebshaltEinfuegen.setText(_translate("BildfahrplanWindow", "Betriebshalt"))
        self.actionBetriebshaltEinfuegen.setToolTip(_translate("BildfahrplanWindow", "Betriebshalt einfügen (B)"))
        self.actionBetriebshaltEinfuegen.setShortcut(_translate("BildfahrplanWindow", "B"))
        self.actionActionBetriebshaltLoeschen.setText(_translate("BildfahrplanWindow", "Betriebshalt löschen"))
        self.actionActionBetriebshaltLoeschen.setToolTip(_translate("BildfahrplanWindow", "Betriebshalt löschen (Shift+B)"))
        self.actionActionBetriebshaltLoeschen.setShortcut(_translate("BildfahrplanWindow", "Shift+B"))
import stskit.resources_rc
