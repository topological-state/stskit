# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'gleisnetz.ui'
##
## Created by: Qt User Interface Compiler version 6.9.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QCheckBox, QFrame, QMainWindow,
    QPushButton, QScrollArea, QSizePolicy, QSpacerItem,
    QSplitter, QTabWidget, QVBoxLayout, QWidget)

class Ui_GleisnetzWindow(object):
    def setupUi(self, GleisnetzWindow):
        if not GleisnetzWindow.objectName():
            GleisnetzWindow.setObjectName(u"GleisnetzWindow")
        GleisnetzWindow.resize(800, 600)
        self.centralwidget = QWidget(GleisnetzWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.verticalLayout = QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.tabWidget = QTabWidget(self.centralwidget)
        self.tabWidget.setObjectName(u"tabWidget")
        self.signal_tab = QWidget()
        self.signal_tab.setObjectName(u"signal_tab")
        self.verticalLayout_7 = QVBoxLayout(self.signal_tab)
        self.verticalLayout_7.setObjectName(u"verticalLayout_7")
        self.widget_2 = QWidget(self.signal_tab)
        self.widget_2.setObjectName(u"widget_2")
        self.verticalLayout_6 = QVBoxLayout(self.widget_2)
        self.verticalLayout_6.setObjectName(u"verticalLayout_6")
        self.splitter_2 = QSplitter(self.widget_2)
        self.splitter_2.setObjectName(u"splitter_2")
        self.splitter_2.setOrientation(Qt.Horizontal)
        self.scrollArea = QScrollArea(self.splitter_2)
        self.scrollArea.setObjectName(u"scrollArea")
        self.scrollArea.setWidgetResizable(True)
        self.signal_graph_area = QWidget()
        self.signal_graph_area.setObjectName(u"signal_graph_area")
        self.signal_graph_area.setGeometry(QRect(0, 0, 68, 515))
        self.scrollArea.setWidget(self.signal_graph_area)
        self.splitter_2.addWidget(self.scrollArea)
        self.signal_settings_frame = QFrame(self.splitter_2)
        self.signal_settings_frame.setObjectName(u"signal_settings_frame")
        self.signal_settings_frame.setFrameShape(QFrame.StyledPanel)
        self.signal_settings_frame.setFrameShadow(QFrame.Sunken)
        self.verticalLayout_5 = QVBoxLayout(self.signal_settings_frame)
        self.verticalLayout_5.setObjectName(u"verticalLayout_5")
        self.signal_weichen_check = QCheckBox(self.signal_settings_frame)
        self.signal_weichen_check.setObjectName(u"signal_weichen_check")

        self.verticalLayout_5.addWidget(self.signal_weichen_check)

        self.signal_anschluss_check = QCheckBox(self.signal_settings_frame)
        self.signal_anschluss_check.setObjectName(u"signal_anschluss_check")

        self.verticalLayout_5.addWidget(self.signal_anschluss_check)

        self.signal_bahnsteig_check = QCheckBox(self.signal_settings_frame)
        self.signal_bahnsteig_check.setObjectName(u"signal_bahnsteig_check")

        self.verticalLayout_5.addWidget(self.signal_bahnsteig_check)

        self.signal_paar_check = QCheckBox(self.signal_settings_frame)
        self.signal_paar_check.setObjectName(u"signal_paar_check")

        self.verticalLayout_5.addWidget(self.signal_paar_check)

        self.signal_zwischen_check = QCheckBox(self.signal_settings_frame)
        self.signal_zwischen_check.setObjectName(u"signal_zwischen_check")

        self.verticalLayout_5.addWidget(self.signal_zwischen_check)

        self.signal_schleifen_check = QCheckBox(self.signal_settings_frame)
        self.signal_schleifen_check.setObjectName(u"signal_schleifen_check")

        self.verticalLayout_5.addWidget(self.signal_schleifen_check)

        self.signal_nachbarn_check = QCheckBox(self.signal_settings_frame)
        self.signal_nachbarn_check.setObjectName(u"signal_nachbarn_check")

        self.verticalLayout_5.addWidget(self.signal_nachbarn_check)

        self.signal_reserve1_check = QCheckBox(self.signal_settings_frame)
        self.signal_reserve1_check.setObjectName(u"signal_reserve1_check")

        self.verticalLayout_5.addWidget(self.signal_reserve1_check)

        self.signal_aktualisieren_button = QPushButton(self.signal_settings_frame)
        self.signal_aktualisieren_button.setObjectName(u"signal_aktualisieren_button")

        self.verticalLayout_5.addWidget(self.signal_aktualisieren_button)

        self.verticalSpacer_2 = QSpacerItem(20, 413, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_5.addItem(self.verticalSpacer_2)

        self.splitter_2.addWidget(self.signal_settings_frame)

        self.verticalLayout_6.addWidget(self.splitter_2)


        self.verticalLayout_7.addWidget(self.widget_2)

        self.tabWidget.addTab(self.signal_tab, "")
        self.bahnhof_tab = QWidget()
        self.bahnhof_tab.setObjectName(u"bahnhof_tab")
        self.verticalLayout_2 = QVBoxLayout(self.bahnhof_tab)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.widget = QWidget(self.bahnhof_tab)
        self.widget.setObjectName(u"widget")
        self.verticalLayout_4 = QVBoxLayout(self.widget)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.splitter = QSplitter(self.widget)
        self.splitter.setObjectName(u"splitter")
        self.splitter.setOrientation(Qt.Horizontal)
        self.scrollArea_2 = QScrollArea(self.splitter)
        self.scrollArea_2.setObjectName(u"scrollArea_2")
        self.scrollArea_2.setWidgetResizable(True)
        self.bahnhof_graph_area = QWidget()
        self.bahnhof_graph_area.setObjectName(u"bahnhof_graph_area")
        self.bahnhof_graph_area.setGeometry(QRect(0, 0, 68, 515))
        self.scrollArea_2.setWidget(self.bahnhof_graph_area)
        self.splitter.addWidget(self.scrollArea_2)
        self.bahnhof_settings_frame = QFrame(self.splitter)
        self.bahnhof_settings_frame.setObjectName(u"bahnhof_settings_frame")
        self.bahnhof_settings_frame.setFrameShape(QFrame.StyledPanel)
        self.bahnhof_settings_frame.setFrameShadow(QFrame.Sunken)
        self.verticalLayout_3 = QVBoxLayout(self.bahnhof_settings_frame)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.bahnhof_leerverbindung_check = QCheckBox(self.bahnhof_settings_frame)
        self.bahnhof_leerverbindung_check.setObjectName(u"bahnhof_leerverbindung_check")

        self.verticalLayout_3.addWidget(self.bahnhof_leerverbindung_check)

        self.bahnhof_check_1 = QCheckBox(self.bahnhof_settings_frame)
        self.bahnhof_check_1.setObjectName(u"bahnhof_check_1")

        self.verticalLayout_3.addWidget(self.bahnhof_check_1)

        self.bahnhof_check_2 = QCheckBox(self.bahnhof_settings_frame)
        self.bahnhof_check_2.setObjectName(u"bahnhof_check_2")

        self.verticalLayout_3.addWidget(self.bahnhof_check_2)

        self.bahnhof_check_3 = QCheckBox(self.bahnhof_settings_frame)
        self.bahnhof_check_3.setObjectName(u"bahnhof_check_3")

        self.verticalLayout_3.addWidget(self.bahnhof_check_3)

        self.bahnhof_aktualisieren_button = QPushButton(self.bahnhof_settings_frame)
        self.bahnhof_aktualisieren_button.setObjectName(u"bahnhof_aktualisieren_button")

        self.verticalLayout_3.addWidget(self.bahnhof_aktualisieren_button)

        self.verticalSpacer = QSpacerItem(20, 364, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_3.addItem(self.verticalSpacer)

        self.splitter.addWidget(self.bahnhof_settings_frame)

        self.verticalLayout_4.addWidget(self.splitter)


        self.verticalLayout_2.addWidget(self.widget)

        self.tabWidget.addTab(self.bahnhof_tab, "")
        self.linien_tab = QWidget()
        self.linien_tab.setObjectName(u"linien_tab")
        self.verticalLayout_10 = QVBoxLayout(self.linien_tab)
        self.verticalLayout_10.setObjectName(u"verticalLayout_10")
        self.widget_3 = QWidget(self.linien_tab)
        self.widget_3.setObjectName(u"widget_3")
        self.verticalLayout_9 = QVBoxLayout(self.widget_3)
        self.verticalLayout_9.setObjectName(u"verticalLayout_9")
        self.splitter_3 = QSplitter(self.widget_3)
        self.splitter_3.setObjectName(u"splitter_3")
        self.splitter_3.setOrientation(Qt.Horizontal)
        self.scrollArea_3 = QScrollArea(self.splitter_3)
        self.scrollArea_3.setObjectName(u"scrollArea_3")
        self.scrollArea_3.setWidgetResizable(True)
        self.linien_graph_area = QWidget()
        self.linien_graph_area.setObjectName(u"linien_graph_area")
        self.linien_graph_area.setGeometry(QRect(0, 0, 68, 515))
        self.scrollArea_3.setWidget(self.linien_graph_area)
        self.splitter_3.addWidget(self.scrollArea_3)
        self.linien_settings_frame = QFrame(self.splitter_3)
        self.linien_settings_frame.setObjectName(u"linien_settings_frame")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.linien_settings_frame.sizePolicy().hasHeightForWidth())
        self.linien_settings_frame.setSizePolicy(sizePolicy)
        self.linien_settings_frame.setFrameShape(QFrame.StyledPanel)
        self.linien_settings_frame.setFrameShadow(QFrame.Sunken)
        self.verticalLayout_8 = QVBoxLayout(self.linien_settings_frame)
        self.verticalLayout_8.setObjectName(u"verticalLayout_8")
        self.linien_schleifen_check = QCheckBox(self.linien_settings_frame)
        self.linien_schleifen_check.setObjectName(u"linien_schleifen_check")

        self.verticalLayout_8.addWidget(self.linien_schleifen_check)

        self.linien_check_2 = QCheckBox(self.linien_settings_frame)
        self.linien_check_2.setObjectName(u"linien_check_2")

        self.verticalLayout_8.addWidget(self.linien_check_2)

        self.linien_check_3 = QCheckBox(self.linien_settings_frame)
        self.linien_check_3.setObjectName(u"linien_check_3")

        self.verticalLayout_8.addWidget(self.linien_check_3)

        self.linien_aktualisieren_button = QPushButton(self.linien_settings_frame)
        self.linien_aktualisieren_button.setObjectName(u"linien_aktualisieren_button")

        self.verticalLayout_8.addWidget(self.linien_aktualisieren_button)

        self.verticalSpacer_3 = QSpacerItem(20, 384, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_8.addItem(self.verticalSpacer_3)

        self.splitter_3.addWidget(self.linien_settings_frame)

        self.verticalLayout_9.addWidget(self.splitter_3)


        self.verticalLayout_10.addWidget(self.widget_3)

        self.tabWidget.addTab(self.linien_tab, "")

        self.verticalLayout.addWidget(self.tabWidget)

        GleisnetzWindow.setCentralWidget(self.centralwidget)

        self.retranslateUi(GleisnetzWindow)

        self.tabWidget.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(GleisnetzWindow)
    # setupUi

    def retranslateUi(self, GleisnetzWindow):
        GleisnetzWindow.setWindowTitle(QCoreApplication.translate("GleisnetzWindow", u"Gleisnetz", None))
        self.signal_weichen_check.setText(QCoreApplication.translate("GleisnetzWindow", u"Weichen entfernen", None))
        self.signal_anschluss_check.setText(QCoreApplication.translate("GleisnetzWindow", u"Anschl\u00fcsse pr\u00fcfen", None))
        self.signal_bahnsteig_check.setText(QCoreApplication.translate("GleisnetzWindow", u"Ausfahrsignale entfernen", None))
        self.signal_paar_check.setText(QCoreApplication.translate("GleisnetzWindow", u"Blocksignale entfernen", None))
        self.signal_zwischen_check.setText(QCoreApplication.translate("GleisnetzWindow", u"Zwischensignale entfernen", None))
        self.signal_schleifen_check.setText(QCoreApplication.translate("GleisnetzWindow", u"Schleifen aufl\u00f6sen", None))
        self.signal_nachbarn_check.setText(QCoreApplication.translate("GleisnetzWindow", u"Nachbarbahnsteige vereinen", None))
        self.signal_reserve1_check.setText(QCoreApplication.translate("GleisnetzWindow", u"(keine Funktion)", None))
        self.signal_aktualisieren_button.setText(QCoreApplication.translate("GleisnetzWindow", u"Grafik aktualisieren", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.signal_tab), QCoreApplication.translate("GleisnetzWindow", u"Gleisplan", None))
        self.bahnhof_leerverbindung_check.setText(QCoreApplication.translate("GleisnetzWindow", u"Leere Verbindungen", None))
        self.bahnhof_check_1.setText(QCoreApplication.translate("GleisnetzWindow", u"Keine Funktion", None))
        self.bahnhof_check_2.setText(QCoreApplication.translate("GleisnetzWindow", u"Keine Funktion", None))
        self.bahnhof_check_3.setText(QCoreApplication.translate("GleisnetzWindow", u"Keine Funktion", None))
        self.bahnhof_aktualisieren_button.setText(QCoreApplication.translate("GleisnetzWindow", u"Grafik aktualisieren", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.bahnhof_tab), QCoreApplication.translate("GleisnetzWindow", u"Bahnhofplan", None))
        self.linien_schleifen_check.setText(QCoreApplication.translate("GleisnetzWindow", u"Schleifen aufl\u00f6sen", None))
        self.linien_check_2.setText(QCoreApplication.translate("GleisnetzWindow", u"Keine Funktion", None))
        self.linien_check_3.setText(QCoreApplication.translate("GleisnetzWindow", u"Keine Funktion", None))
        self.linien_aktualisieren_button.setText(QCoreApplication.translate("GleisnetzWindow", u"Grafik aktualisieren", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.linien_tab), QCoreApplication.translate("GleisnetzWindow", u"Liniennetz", None))
    # retranslateUi

