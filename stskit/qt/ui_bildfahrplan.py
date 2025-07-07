# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'bildfahrplan.ui'
##
## Created by: Qt User Interface Compiler version 6.9.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QAction, QBrush, QColor, QConicalGradient,
    QCursor, QFont, QFontDatabase, QGradient,
    QIcon, QImage, QKeySequence, QLinearGradient,
    QPainter, QPalette, QPixmap, QRadialGradient,
    QTransform)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QFrame,
    QGroupBox, QHBoxLayout, QLabel, QListView,
    QMainWindow, QSizePolicy, QSpinBox, QSplitter,
    QStackedWidget, QToolBar, QVBoxLayout, QWidget)
import stskit.qt.resources_rc

class Ui_BildfahrplanWindow(object):
    def setupUi(self, BildfahrplanWindow):
        if not BildfahrplanWindow.objectName():
            BildfahrplanWindow.setObjectName(u"BildfahrplanWindow")
        BildfahrplanWindow.resize(800, 600)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(BildfahrplanWindow.sizePolicy().hasHeightForWidth())
        BildfahrplanWindow.setSizePolicy(sizePolicy)
        self.actionSetup = QAction(BildfahrplanWindow)
        self.actionSetup.setObjectName(u"actionSetup")
        icon = QIcon()
        icon.addFile(u":/equalizer.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        icon.addFile(u":/equalizer-dis.png", QSize(), QIcon.Mode.Disabled, QIcon.State.Off)
        self.actionSetup.setIcon(icon)
        self.actionAnzeige = QAction(BildfahrplanWindow)
        self.actionAnzeige.setObjectName(u"actionAnzeige")
        icon1 = QIcon()
        icon1.addFile(u":/slots.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        icon1.addFile(u":/slots-dis.png", QSize(), QIcon.Mode.Disabled, QIcon.State.Off)
        self.actionAnzeige.setIcon(icon1)
        self.actionPlusEins = QAction(BildfahrplanWindow)
        self.actionPlusEins.setObjectName(u"actionPlusEins")
        icon2 = QIcon()
        icon2.addFile(u":/clock--plus.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.actionPlusEins.setIcon(icon2)
        self.actionMinusEins = QAction(BildfahrplanWindow)
        self.actionMinusEins.setObjectName(u"actionMinusEins")
        icon3 = QIcon()
        icon3.addFile(u":/clock--minus.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.actionMinusEins.setIcon(icon3)
        self.actionFix = QAction(BildfahrplanWindow)
        self.actionFix.setObjectName(u"actionFix")
        icon4 = QIcon()
        icon4.addFile(u":/clock--pencil.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.actionFix.setIcon(icon4)
        self.actionLoeschen = QAction(BildfahrplanWindow)
        self.actionLoeschen.setObjectName(u"actionLoeschen")
        icon5 = QIcon()
        icon5.addFile(u":/chain--return.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.actionLoeschen.setIcon(icon5)
        self.actionAnkunftAbwarten = QAction(BildfahrplanWindow)
        self.actionAnkunftAbwarten.setObjectName(u"actionAnkunftAbwarten")
        icon6 = QIcon()
        icon6.addFile(u":/chain--arrow-in.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.actionAnkunftAbwarten.setIcon(icon6)
        self.actionAbfahrtAbwarten = QAction(BildfahrplanWindow)
        self.actionAbfahrtAbwarten.setObjectName(u"actionAbfahrtAbwarten")
        icon7 = QIcon()
        icon7.addFile(u":/chain--arrow.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.actionAbfahrtAbwarten.setIcon(icon7)
        self.actionBetriebshaltEinfuegen = QAction(BildfahrplanWindow)
        self.actionBetriebshaltEinfuegen.setObjectName(u"actionBetriebshaltEinfuegen")
        icon8 = QIcon()
        icon8.addFile(u":/node-insert.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.actionBetriebshaltEinfuegen.setIcon(icon8)
        self.actionActionBetriebshaltLoeschen = QAction(BildfahrplanWindow)
        self.actionActionBetriebshaltLoeschen.setObjectName(u"actionActionBetriebshaltLoeschen")
        icon9 = QIcon()
        icon9.addFile(u":/node-delete.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.actionActionBetriebshaltLoeschen.setIcon(icon9)
        self.centralwidget = QWidget(BildfahrplanWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.verticalLayout = QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.stackedWidget = QStackedWidget(self.centralwidget)
        self.stackedWidget.setObjectName(u"stackedWidget")
        self.settings_page = QWidget()
        self.settings_page.setObjectName(u"settings_page")
        self.horizontalLayout_3 = QHBoxLayout(self.settings_page)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.horizontalLayout_2 = QHBoxLayout()
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.strecke_group = QGroupBox(self.settings_page)
        self.strecke_group.setObjectName(u"strecke_group")
        self.verticalLayout_4 = QVBoxLayout(self.strecke_group)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.strecke_layout = QVBoxLayout()
        self.strecke_layout.setObjectName(u"strecke_layout")
        self.vordefiniert_label = QLabel(self.strecke_group)
        self.vordefiniert_label.setObjectName(u"vordefiniert_label")

        self.strecke_layout.addWidget(self.vordefiniert_label)

        self.vordefiniert_combo = QComboBox(self.strecke_group)
        self.vordefiniert_combo.setObjectName(u"vordefiniert_combo")

        self.strecke_layout.addWidget(self.vordefiniert_combo)

        self.von_label = QLabel(self.strecke_group)
        self.von_label.setObjectName(u"von_label")

        self.strecke_layout.addWidget(self.von_label)

        self.von_combo = QComboBox(self.strecke_group)
        self.von_combo.setObjectName(u"von_combo")

        self.strecke_layout.addWidget(self.von_combo)

        self.via_label = QLabel(self.strecke_group)
        self.via_label.setObjectName(u"via_label")

        self.strecke_layout.addWidget(self.via_label)

        self.via_combo = QComboBox(self.strecke_group)
        self.via_combo.setObjectName(u"via_combo")

        self.strecke_layout.addWidget(self.via_combo)

        self.nach_label = QLabel(self.strecke_group)
        self.nach_label.setObjectName(u"nach_label")

        self.strecke_layout.addWidget(self.nach_label)

        self.nach_combo = QComboBox(self.strecke_group)
        self.nach_combo.setObjectName(u"nach_combo")

        self.strecke_layout.addWidget(self.nach_combo)

        self.strecke_label = QLabel(self.strecke_group)
        self.strecke_label.setObjectName(u"strecke_label")

        self.strecke_layout.addWidget(self.strecke_label)

        self.strecke_list = QListView(self.strecke_group)
        self.strecke_list.setObjectName(u"strecke_list")
        self.strecke_list.setAlternatingRowColors(True)
        self.strecke_list.setSelectionBehavior(QAbstractItemView.SelectRows)

        self.strecke_layout.addWidget(self.strecke_list)


        self.verticalLayout_4.addLayout(self.strecke_layout)


        self.horizontalLayout_2.addWidget(self.strecke_group)

        self.darstellung_group = QGroupBox(self.settings_page)
        self.darstellung_group.setObjectName(u"darstellung_group")
        self.verticalLayout_5 = QVBoxLayout(self.darstellung_group)
        self.verticalLayout_5.setObjectName(u"verticalLayout_5")
        self.darstellung_layout = QVBoxLayout()
        self.darstellung_layout.setObjectName(u"darstellung_layout")
        self.vorlaufzeit_label = QLabel(self.darstellung_group)
        self.vorlaufzeit_label.setObjectName(u"vorlaufzeit_label")

        self.darstellung_layout.addWidget(self.vorlaufzeit_label)

        self.vorlaufzeit_spin = QSpinBox(self.darstellung_group)
        self.vorlaufzeit_spin.setObjectName(u"vorlaufzeit_spin")
        self.vorlaufzeit_spin.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.vorlaufzeit_spin.setMinimum(15)
        self.vorlaufzeit_spin.setMaximum(120)
        self.vorlaufzeit_spin.setSingleStep(5)
        self.vorlaufzeit_spin.setValue(55)

        self.darstellung_layout.addWidget(self.vorlaufzeit_spin)

        self.nachlaufzeit_label = QLabel(self.darstellung_group)
        self.nachlaufzeit_label.setObjectName(u"nachlaufzeit_label")

        self.darstellung_layout.addWidget(self.nachlaufzeit_label)

        self.nachlaufzeit_spin = QSpinBox(self.darstellung_group)
        self.nachlaufzeit_spin.setObjectName(u"nachlaufzeit_spin")
        self.nachlaufzeit_spin.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.nachlaufzeit_spin.setMinimum(5)
        self.nachlaufzeit_spin.setMaximum(120)
        self.nachlaufzeit_spin.setSingleStep(5)
        self.nachlaufzeit_spin.setValue(5)

        self.darstellung_layout.addWidget(self.nachlaufzeit_spin)

        self.darstellung_stretch = QWidget(self.darstellung_group)
        self.darstellung_stretch.setObjectName(u"darstellung_stretch")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.darstellung_stretch.sizePolicy().hasHeightForWidth())
        self.darstellung_stretch.setSizePolicy(sizePolicy1)

        self.darstellung_layout.addWidget(self.darstellung_stretch)


        self.verticalLayout_5.addLayout(self.darstellung_layout)


        self.horizontalLayout_2.addWidget(self.darstellung_group)


        self.horizontalLayout_3.addLayout(self.horizontalLayout_2)

        self.stackedWidget.addWidget(self.settings_page)
        self.display_page = QWidget()
        self.display_page.setObjectName(u"display_page")
        self.horizontalLayout = QHBoxLayout(self.display_page)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.displaySplitter = QSplitter(self.display_page)
        self.displaySplitter.setObjectName(u"displaySplitter")
        self.displaySplitter.setOrientation(Qt.Vertical)
        self.grafikWidget = QWidget(self.displaySplitter)
        self.grafikWidget.setObjectName(u"grafikWidget")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.grafikWidget.sizePolicy().hasHeightForWidth())
        self.grafikWidget.setSizePolicy(sizePolicy2)
        self.displaySplitter.addWidget(self.grafikWidget)
        self.zuginfoLabel = QLabel(self.displaySplitter)
        self.zuginfoLabel.setObjectName(u"zuginfoLabel")
        sizePolicy3 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.zuginfoLabel.sizePolicy().hasHeightForWidth())
        self.zuginfoLabel.setSizePolicy(sizePolicy3)
        self.zuginfoLabel.setMaximumSize(QSize(16777215, 50))
        self.zuginfoLabel.setBaseSize(QSize(0, 0))
        self.zuginfoLabel.setFrameShape(QFrame.Box)
        self.zuginfoLabel.setFrameShadow(QFrame.Sunken)
        self.zuginfoLabel.setTextFormat(Qt.AutoText)
        self.zuginfoLabel.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.displaySplitter.addWidget(self.zuginfoLabel)

        self.horizontalLayout.addWidget(self.displaySplitter)

        self.stackedWidget.addWidget(self.display_page)

        self.verticalLayout.addWidget(self.stackedWidget)

        BildfahrplanWindow.setCentralWidget(self.centralwidget)
        self.toolBar = QToolBar(BildfahrplanWindow)
        self.toolBar.setObjectName(u"toolBar")
        self.toolBar.setMovable(False)
        self.toolBar.setIconSize(QSize(16, 16))
        self.toolBar.setFloatable(False)
        BildfahrplanWindow.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolBar)
#if QT_CONFIG(shortcut)
        self.vordefiniert_label.setBuddy(self.vordefiniert_combo)
        self.von_label.setBuddy(self.von_combo)
        self.via_label.setBuddy(self.via_combo)
        self.nach_label.setBuddy(self.nach_combo)
        self.strecke_label.setBuddy(self.strecke_list)
        self.vorlaufzeit_label.setBuddy(self.vorlaufzeit_spin)
        self.nachlaufzeit_label.setBuddy(self.nachlaufzeit_spin)
#endif // QT_CONFIG(shortcut)

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

        self.retranslateUi(BildfahrplanWindow)

        self.stackedWidget.setCurrentIndex(1)


        QMetaObject.connectSlotsByName(BildfahrplanWindow)
    # setupUi

    def retranslateUi(self, BildfahrplanWindow):
        BildfahrplanWindow.setWindowTitle(QCoreApplication.translate("BildfahrplanWindow", u"Bildfahrplan", None))
        self.actionSetup.setText(QCoreApplication.translate("BildfahrplanWindow", u"Setup", None))
#if QT_CONFIG(tooltip)
        self.actionSetup.setToolTip(QCoreApplication.translate("BildfahrplanWindow", u"Streckendefinition (S)", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(shortcut)
        self.actionSetup.setShortcut(QCoreApplication.translate("BildfahrplanWindow", u"S", None))
#endif // QT_CONFIG(shortcut)
        self.actionAnzeige.setText(QCoreApplication.translate("BildfahrplanWindow", u"Grafik", None))
#if QT_CONFIG(tooltip)
        self.actionAnzeige.setToolTip(QCoreApplication.translate("BildfahrplanWindow", u"Grafik anzeigen (G)", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(shortcut)
        self.actionAnzeige.setShortcut(QCoreApplication.translate("BildfahrplanWindow", u"G", None))
#endif // QT_CONFIG(shortcut)
        self.actionPlusEins.setText(QCoreApplication.translate("BildfahrplanWindow", u"+1", None))
#if QT_CONFIG(tooltip)
        self.actionPlusEins.setToolTip(QCoreApplication.translate("BildfahrplanWindow", u"Feste Versp\u00e4tung +1 Minute auf ausgew\u00e4hltem Segment (+)", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(shortcut)
        self.actionPlusEins.setShortcut(QCoreApplication.translate("BildfahrplanWindow", u"+", None))
#endif // QT_CONFIG(shortcut)
        self.actionMinusEins.setText(QCoreApplication.translate("BildfahrplanWindow", u"-1", None))
#if QT_CONFIG(tooltip)
        self.actionMinusEins.setToolTip(QCoreApplication.translate("BildfahrplanWindow", u"Feste Versp\u00e4tung -1 Minute auf ausgew\u00e4hltem Segment (-)", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(shortcut)
        self.actionMinusEins.setShortcut(QCoreApplication.translate("BildfahrplanWindow", u"-", None))
#endif // QT_CONFIG(shortcut)
        self.actionFix.setText(QCoreApplication.translate("BildfahrplanWindow", u"Fix", None))
#if QT_CONFIG(tooltip)
        self.actionFix.setToolTip(QCoreApplication.translate("BildfahrplanWindow", u"Feste Versp\u00e4tung auf ausgew\u00e4hltem Segment festlegen (V)", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(shortcut)
        self.actionFix.setShortcut(QCoreApplication.translate("BildfahrplanWindow", u"V", None))
#endif // QT_CONFIG(shortcut)
        self.actionLoeschen.setText(QCoreApplication.translate("BildfahrplanWindow", u"L\u00f6schen", None))
#if QT_CONFIG(tooltip)
        self.actionLoeschen.setToolTip(QCoreApplication.translate("BildfahrplanWindow", u"Korrekturen auf ausgew\u00e4hltem Segment l\u00f6schen (Del)", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(shortcut)
        self.actionLoeschen.setShortcut(QCoreApplication.translate("BildfahrplanWindow", u"Del", None))
#endif // QT_CONFIG(shortcut)
        self.actionAnkunftAbwarten.setText(QCoreApplication.translate("BildfahrplanWindow", u"Ankunft", None))
#if QT_CONFIG(tooltip)
        self.actionAnkunftAbwarten.setToolTip(QCoreApplication.translate("BildfahrplanWindow", u"Kreuzung/Ankunft von zweitem gew\u00e4hlten Zug abwarten (K)", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(shortcut)
        self.actionAnkunftAbwarten.setShortcut(QCoreApplication.translate("BildfahrplanWindow", u"K", None))
#endif // QT_CONFIG(shortcut)
        self.actionAbfahrtAbwarten.setText(QCoreApplication.translate("BildfahrplanWindow", u"Abfahrt", None))
#if QT_CONFIG(tooltip)
        self.actionAbfahrtAbwarten.setToolTip(QCoreApplication.translate("BildfahrplanWindow", u"\u00dcberholung/Abfahrt von zweitem gew\u00e4hlten Zug abwarten (F)", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(shortcut)
        self.actionAbfahrtAbwarten.setShortcut(QCoreApplication.translate("BildfahrplanWindow", u"F", None))
#endif // QT_CONFIG(shortcut)
        self.actionBetriebshaltEinfuegen.setText(QCoreApplication.translate("BildfahrplanWindow", u"Betriebshalt", None))
#if QT_CONFIG(tooltip)
        self.actionBetriebshaltEinfuegen.setToolTip(QCoreApplication.translate("BildfahrplanWindow", u"Betriebshalt einf\u00fcgen (B)", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(shortcut)
        self.actionBetriebshaltEinfuegen.setShortcut(QCoreApplication.translate("BildfahrplanWindow", u"B", None))
#endif // QT_CONFIG(shortcut)
        self.actionActionBetriebshaltLoeschen.setText(QCoreApplication.translate("BildfahrplanWindow", u"Betriebshalt l\u00f6schen", None))
#if QT_CONFIG(tooltip)
        self.actionActionBetriebshaltLoeschen.setToolTip(QCoreApplication.translate("BildfahrplanWindow", u"Betriebshalt l\u00f6schen (Shift+B)", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(shortcut)
        self.actionActionBetriebshaltLoeschen.setShortcut(QCoreApplication.translate("BildfahrplanWindow", u"Shift+B", None))
#endif // QT_CONFIG(shortcut)
        self.strecke_group.setTitle(QCoreApplication.translate("BildfahrplanWindow", u"Strecke", None))
        self.vordefiniert_label.setText(QCoreApplication.translate("BildfahrplanWindow", u"Vordefinierte &Strecke", None))
        self.von_label.setText(QCoreApplication.translate("BildfahrplanWindow", u"&Von", None))
        self.via_label.setText(QCoreApplication.translate("BildfahrplanWindow", u"V&ia", None))
        self.nach_label.setText(QCoreApplication.translate("BildfahrplanWindow", u"&Nach", None))
        self.strecke_label.setText(QCoreApplication.translate("BildfahrplanWindow", u"S&trecke", None))
        self.darstellung_group.setTitle(QCoreApplication.translate("BildfahrplanWindow", u"Darstellung", None))
        self.vorlaufzeit_label.setText(QCoreApplication.translate("BildfahrplanWindow", u"V&orlaufzeit", None))
        self.vorlaufzeit_spin.setSuffix(QCoreApplication.translate("BildfahrplanWindow", u" Min.", None))
        self.nachlaufzeit_label.setText(QCoreApplication.translate("BildfahrplanWindow", u"N&achlaufzeit", None))
        self.nachlaufzeit_spin.setSuffix(QCoreApplication.translate("BildfahrplanWindow", u" Min.", None))
        self.zuginfoLabel.setText(QCoreApplication.translate("BildfahrplanWindow", u"Zuginfo: (keine Auswahl)", None))
        self.toolBar.setWindowTitle(QCoreApplication.translate("BildfahrplanWindow", u"Tool Bar", None))
    # retranslateUi

