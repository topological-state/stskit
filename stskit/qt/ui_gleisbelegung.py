# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'gleisbelegung.ui'
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
from PySide6.QtWidgets import (QApplication, QFrame, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QMainWindow, QSizePolicy,
    QSpinBox, QSplitter, QStackedWidget, QToolBar,
    QTreeView, QVBoxLayout, QWidget)
import stskit.qt.resources_rc

class Ui_GleisbelegungWindow(object):
    def setupUi(self, GleisbelegungWindow):
        if not GleisbelegungWindow.objectName():
            GleisbelegungWindow.setObjectName(u"GleisbelegungWindow")
        GleisbelegungWindow.resize(800, 600)
        self.actionSetup = QAction(GleisbelegungWindow)
        self.actionSetup.setObjectName(u"actionSetup")
        icon = QIcon()
        icon.addFile(u":/equalizer.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        icon.addFile(u":/equalizer-dis.png", QSize(), QIcon.Mode.Disabled, QIcon.State.Off)
        self.actionSetup.setIcon(icon)
        self.actionAnzeige = QAction(GleisbelegungWindow)
        self.actionAnzeige.setObjectName(u"actionAnzeige")
        icon1 = QIcon()
        icon1.addFile(u":/slots.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        icon1.addFile(u":/slots-dis.png", QSize(), QIcon.Mode.Disabled, QIcon.State.Off)
        self.actionAnzeige.setIcon(icon1)
        self.actionPlusEins = QAction(GleisbelegungWindow)
        self.actionPlusEins.setObjectName(u"actionPlusEins")
        icon2 = QIcon()
        icon2.addFile(u":/clock--plus.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.actionPlusEins.setIcon(icon2)
        self.actionMinusEins = QAction(GleisbelegungWindow)
        self.actionMinusEins.setObjectName(u"actionMinusEins")
        icon3 = QIcon()
        icon3.addFile(u":/clock--minus.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.actionMinusEins.setIcon(icon3)
        self.actionFix = QAction(GleisbelegungWindow)
        self.actionFix.setObjectName(u"actionFix")
        icon4 = QIcon()
        icon4.addFile(u":/clock--pencil.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.actionFix.setIcon(icon4)
        self.actionLoeschen = QAction(GleisbelegungWindow)
        self.actionLoeschen.setObjectName(u"actionLoeschen")
        icon5 = QIcon()
        icon5.addFile(u":/chain--return.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.actionLoeschen.setIcon(icon5)
        self.actionAnkunftAbwarten = QAction(GleisbelegungWindow)
        self.actionAnkunftAbwarten.setObjectName(u"actionAnkunftAbwarten")
        icon6 = QIcon()
        icon6.addFile(u":/chain--arrow-in.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.actionAnkunftAbwarten.setIcon(icon6)
        self.actionAbfahrtAbwarten = QAction(GleisbelegungWindow)
        self.actionAbfahrtAbwarten.setObjectName(u"actionAbfahrtAbwarten")
        icon7 = QIcon()
        icon7.addFile(u":/chain--arrow.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.actionAbfahrtAbwarten.setIcon(icon7)
        self.actionWarnungSetzen = QAction(GleisbelegungWindow)
        self.actionWarnungSetzen.setObjectName(u"actionWarnungSetzen")
        icon8 = QIcon()
        icon8.addFile(u":/flag.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.actionWarnungSetzen.setIcon(icon8)
        self.actionWarnungIgnorieren = QAction(GleisbelegungWindow)
        self.actionWarnungIgnorieren.setObjectName(u"actionWarnungIgnorieren")
        icon9 = QIcon()
        icon9.addFile(u":/flag-green.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.actionWarnungIgnorieren.setIcon(icon9)
        self.actionWarnungReset = QAction(GleisbelegungWindow)
        self.actionWarnungReset.setObjectName(u"actionWarnungReset")
        icon10 = QIcon()
        icon10.addFile(u":/flag-white.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.actionWarnungReset.setIcon(icon10)
        self.actionBelegteGleise = QAction(GleisbelegungWindow)
        self.actionBelegteGleise.setObjectName(u"actionBelegteGleise")
        self.actionBelegteGleise.setCheckable(True)
        self.actionBelegteGleise.setChecked(False)
        self.actionBelegteGleise.setEnabled(True)
        icon11 = QIcon()
        icon11.addFile(u":/funnel-small.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        icon11.addFile(u":/funnel-small-dis", QSize(), QIcon.Mode.Disabled, QIcon.State.Off)
        self.actionBelegteGleise.setIcon(icon11)
        self.centralwidget = QWidget(GleisbelegungWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.horizontalLayout_3 = QHBoxLayout(self.centralwidget)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.stackedWidget = QStackedWidget(self.centralwidget)
        self.stackedWidget.setObjectName(u"stackedWidget")
        self.settings_page = QWidget()
        self.settings_page.setObjectName(u"settings_page")
        self.horizontalLayout_2 = QHBoxLayout(self.settings_page)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.gleise_group = QGroupBox(self.settings_page)
        self.gleise_group.setObjectName(u"gleise_group")
        self.verticalLayout = QVBoxLayout(self.gleise_group)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.gleise_label = QLabel(self.gleise_group)
        self.gleise_label.setObjectName(u"gleise_label")

        self.verticalLayout.addWidget(self.gleise_label)

        self.gleisView = QTreeView(self.gleise_group)
        self.gleisView.setObjectName(u"gleisView")
        self.gleisView.setAlternatingRowColors(True)

        self.verticalLayout.addWidget(self.gleisView)


        self.horizontalLayout_2.addWidget(self.gleise_group)

        self.darstellung_group = QGroupBox(self.settings_page)
        self.darstellung_group.setObjectName(u"darstellung_group")
        self.verticalLayout_3 = QVBoxLayout(self.darstellung_group)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.vorlaufzeit_label = QLabel(self.darstellung_group)
        self.vorlaufzeit_label.setObjectName(u"vorlaufzeit_label")

        self.verticalLayout_3.addWidget(self.vorlaufzeit_label)

        self.vorlaufzeit_spin = QSpinBox(self.darstellung_group)
        self.vorlaufzeit_spin.setObjectName(u"vorlaufzeit_spin")
        self.vorlaufzeit_spin.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.vorlaufzeit_spin.setMinimum(15)
        self.vorlaufzeit_spin.setMaximum(120)
        self.vorlaufzeit_spin.setSingleStep(5)
        self.vorlaufzeit_spin.setValue(55)

        self.verticalLayout_3.addWidget(self.vorlaufzeit_spin)

        self.nachlaufzeit_label = QLabel(self.darstellung_group)
        self.nachlaufzeit_label.setObjectName(u"nachlaufzeit_label")

        self.verticalLayout_3.addWidget(self.nachlaufzeit_label)

        self.nachlaufzeit_spin = QSpinBox(self.darstellung_group)
        self.nachlaufzeit_spin.setObjectName(u"nachlaufzeit_spin")
        self.nachlaufzeit_spin.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.nachlaufzeit_spin.setMinimum(5)
        self.nachlaufzeit_spin.setMaximum(120)
        self.nachlaufzeit_spin.setSingleStep(5)
        self.nachlaufzeit_spin.setValue(5)

        self.verticalLayout_3.addWidget(self.nachlaufzeit_spin)

        self.darstellung_stretch = QWidget(self.darstellung_group)
        self.darstellung_stretch.setObjectName(u"darstellung_stretch")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.darstellung_stretch.sizePolicy().hasHeightForWidth())
        self.darstellung_stretch.setSizePolicy(sizePolicy)

        self.verticalLayout_3.addWidget(self.darstellung_stretch)


        self.horizontalLayout_2.addWidget(self.darstellung_group)

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
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.grafikWidget.sizePolicy().hasHeightForWidth())
        self.grafikWidget.setSizePolicy(sizePolicy1)
        self.displaySplitter.addWidget(self.grafikWidget)
        self.zuginfoLabel = QLabel(self.displaySplitter)
        self.zuginfoLabel.setObjectName(u"zuginfoLabel")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.zuginfoLabel.sizePolicy().hasHeightForWidth())
        self.zuginfoLabel.setSizePolicy(sizePolicy2)
        self.zuginfoLabel.setMaximumSize(QSize(16777215, 50))
        self.zuginfoLabel.setBaseSize(QSize(0, 0))
        self.zuginfoLabel.setFrameShape(QFrame.Box)
        self.zuginfoLabel.setFrameShadow(QFrame.Sunken)
        self.zuginfoLabel.setTextFormat(Qt.AutoText)
        self.zuginfoLabel.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.displaySplitter.addWidget(self.zuginfoLabel)

        self.horizontalLayout.addWidget(self.displaySplitter)

        self.stackedWidget.addWidget(self.display_page)

        self.horizontalLayout_3.addWidget(self.stackedWidget)

        GleisbelegungWindow.setCentralWidget(self.centralwidget)
        self.toolBar = QToolBar(GleisbelegungWindow)
        self.toolBar.setObjectName(u"toolBar")
        self.toolBar.setIconSize(QSize(16, 16))
        GleisbelegungWindow.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolBar)
#if QT_CONFIG(shortcut)
        self.gleise_label.setBuddy(self.gleisView)
        self.vorlaufzeit_label.setBuddy(self.vorlaufzeit_spin)
        self.nachlaufzeit_label.setBuddy(self.nachlaufzeit_spin)
#endif // QT_CONFIG(shortcut)

        self.toolBar.addAction(self.actionSetup)
        self.toolBar.addAction(self.actionAnzeige)
        self.toolBar.addAction(self.actionBelegteGleise)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.actionWarnungSetzen)
        self.toolBar.addAction(self.actionWarnungIgnorieren)
        self.toolBar.addAction(self.actionWarnungReset)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.actionPlusEins)
        self.toolBar.addAction(self.actionMinusEins)
        self.toolBar.addAction(self.actionFix)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.actionAnkunftAbwarten)
        self.toolBar.addAction(self.actionAbfahrtAbwarten)
        self.toolBar.addAction(self.actionLoeschen)

        self.retranslateUi(GleisbelegungWindow)

        self.stackedWidget.setCurrentIndex(1)


        QMetaObject.connectSlotsByName(GleisbelegungWindow)
    # setupUi

    def retranslateUi(self, GleisbelegungWindow):
        GleisbelegungWindow.setWindowTitle(QCoreApplication.translate("GleisbelegungWindow", u"MainWindow", None))
        self.actionSetup.setText(QCoreApplication.translate("GleisbelegungWindow", u"Setup", None))
#if QT_CONFIG(tooltip)
        self.actionSetup.setToolTip(QCoreApplication.translate("GleisbelegungWindow", u"Gleisauswahl (S)", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(shortcut)
        self.actionSetup.setShortcut(QCoreApplication.translate("GleisbelegungWindow", u"S", None))
#endif // QT_CONFIG(shortcut)
        self.actionAnzeige.setText(QCoreApplication.translate("GleisbelegungWindow", u"Grafik", None))
#if QT_CONFIG(tooltip)
        self.actionAnzeige.setToolTip(QCoreApplication.translate("GleisbelegungWindow", u"Grafik anzeigen (G)", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(shortcut)
        self.actionAnzeige.setShortcut(QCoreApplication.translate("GleisbelegungWindow", u"G", None))
#endif // QT_CONFIG(shortcut)
        self.actionPlusEins.setText(QCoreApplication.translate("GleisbelegungWindow", u"+1", None))
#if QT_CONFIG(tooltip)
        self.actionPlusEins.setToolTip(QCoreApplication.translate("GleisbelegungWindow", u"Feste Versp\u00e4tung +1 Minute auf ausgew\u00e4hltem Slot (+)", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(shortcut)
        self.actionPlusEins.setShortcut(QCoreApplication.translate("GleisbelegungWindow", u"+", None))
#endif // QT_CONFIG(shortcut)
        self.actionMinusEins.setText(QCoreApplication.translate("GleisbelegungWindow", u"-1", None))
#if QT_CONFIG(tooltip)
        self.actionMinusEins.setToolTip(QCoreApplication.translate("GleisbelegungWindow", u"Feste Versp\u00e4tung -1 Minute auf ausgew\u00e4hltem Slot (-)", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(shortcut)
        self.actionMinusEins.setShortcut(QCoreApplication.translate("GleisbelegungWindow", u"-", None))
#endif // QT_CONFIG(shortcut)
        self.actionFix.setText(QCoreApplication.translate("GleisbelegungWindow", u"Fix", None))
#if QT_CONFIG(tooltip)
        self.actionFix.setToolTip(QCoreApplication.translate("GleisbelegungWindow", u"Feste Versp\u00e4tung auf ausgew\u00e4hltem Slot festlegen (V)", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(shortcut)
        self.actionFix.setShortcut(QCoreApplication.translate("GleisbelegungWindow", u"V", None))
#endif // QT_CONFIG(shortcut)
        self.actionLoeschen.setText(QCoreApplication.translate("GleisbelegungWindow", u"L\u00f6schen", None))
#if QT_CONFIG(tooltip)
        self.actionLoeschen.setToolTip(QCoreApplication.translate("GleisbelegungWindow", u"Korrekturen auf ausgew\u00e4hltem Slot l\u00f6schen (Del)", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(shortcut)
        self.actionLoeschen.setShortcut(QCoreApplication.translate("GleisbelegungWindow", u"Del", None))
#endif // QT_CONFIG(shortcut)
        self.actionAnkunftAbwarten.setText(QCoreApplication.translate("GleisbelegungWindow", u"Ankunft", None))
#if QT_CONFIG(tooltip)
        self.actionAnkunftAbwarten.setToolTip(QCoreApplication.translate("GleisbelegungWindow", u"Kreuzung/Ankunft von zweitem gew\u00e4hlten Zug abwarten (K)", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(shortcut)
        self.actionAnkunftAbwarten.setShortcut(QCoreApplication.translate("GleisbelegungWindow", u"K", None))
#endif // QT_CONFIG(shortcut)
        self.actionAbfahrtAbwarten.setText(QCoreApplication.translate("GleisbelegungWindow", u"Abfahrt", None))
#if QT_CONFIG(tooltip)
        self.actionAbfahrtAbwarten.setToolTip(QCoreApplication.translate("GleisbelegungWindow", u"\u00dcberholung/Abfahrt von zweitem gew\u00e4hlten Zug abwarten (F)", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(shortcut)
        self.actionAbfahrtAbwarten.setShortcut(QCoreApplication.translate("GleisbelegungWindow", u"F", None))
#endif // QT_CONFIG(shortcut)
        self.actionWarnungSetzen.setText(QCoreApplication.translate("GleisbelegungWindow", u"Warnung", None))
#if QT_CONFIG(tooltip)
        self.actionWarnungSetzen.setToolTip(QCoreApplication.translate("GleisbelegungWindow", u"Slot-Warnung setzen (W)", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(shortcut)
        self.actionWarnungSetzen.setShortcut(QCoreApplication.translate("GleisbelegungWindow", u"W", None))
#endif // QT_CONFIG(shortcut)
        self.actionWarnungIgnorieren.setText(QCoreApplication.translate("GleisbelegungWindow", u"Ignorieren", None))
#if QT_CONFIG(tooltip)
        self.actionWarnungIgnorieren.setToolTip(QCoreApplication.translate("GleisbelegungWindow", u"Slot-Warnung ignorieren (I)", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(shortcut)
        self.actionWarnungIgnorieren.setShortcut(QCoreApplication.translate("GleisbelegungWindow", u"I", None))
#endif // QT_CONFIG(shortcut)
        self.actionWarnungReset.setText(QCoreApplication.translate("GleisbelegungWindow", u"Reset", None))
#if QT_CONFIG(tooltip)
        self.actionWarnungReset.setToolTip(QCoreApplication.translate("GleisbelegungWindow", u"Slot-Warnung zur\u00fccksetzen (R)", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(shortcut)
        self.actionWarnungReset.setShortcut(QCoreApplication.translate("GleisbelegungWindow", u"R", None))
#endif // QT_CONFIG(shortcut)
        self.actionBelegteGleise.setText(QCoreApplication.translate("GleisbelegungWindow", u"Belegte Gleise", None))
#if QT_CONFIG(tooltip)
        self.actionBelegteGleise.setToolTip(QCoreApplication.translate("GleisbelegungWindow", u"Nur belegte Gleise anzeigen (B)", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(shortcut)
        self.actionBelegteGleise.setShortcut(QCoreApplication.translate("GleisbelegungWindow", u"B", None))
#endif // QT_CONFIG(shortcut)
        self.gleise_group.setTitle(QCoreApplication.translate("GleisbelegungWindow", u"Gleise", None))
        self.gleise_label.setText(QCoreApplication.translate("GleisbelegungWindow", u"Aus&wahl", None))
        self.darstellung_group.setTitle(QCoreApplication.translate("GleisbelegungWindow", u"Darstellung", None))
        self.vorlaufzeit_label.setText(QCoreApplication.translate("GleisbelegungWindow", u"V&orlaufzeit", None))
        self.vorlaufzeit_spin.setSuffix(QCoreApplication.translate("GleisbelegungWindow", u" Min.", None))
        self.nachlaufzeit_label.setText(QCoreApplication.translate("GleisbelegungWindow", u"N&achlaufzeit", None))
        self.nachlaufzeit_spin.setSuffix(QCoreApplication.translate("GleisbelegungWindow", u" Min.", None))
        self.zuginfoLabel.setText(QCoreApplication.translate("GleisbelegungWindow", u"Zuginfo: (keine Auswahl)", None))
        self.toolBar.setWindowTitle(QCoreApplication.translate("GleisbelegungWindow", u"toolBar", None))
    # retranslateUi

