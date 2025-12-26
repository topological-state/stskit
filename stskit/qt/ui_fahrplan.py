# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'fahrplan.ui'
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
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPushButton, QScrollArea, QSizePolicy,
    QSpacerItem, QSpinBox, QSplitter, QTabWidget,
    QTableView, QVBoxLayout, QWidget)
import stskit.qt.resources_rc

class Ui_FahrplanWidget(object):
    def setupUi(self, FahrplanWidget):
        if not FahrplanWidget.objectName():
            FahrplanWidget.setObjectName(u"FahrplanWidget")
        FahrplanWidget.resize(1101, 803)
        self.horizontalLayout_5 = QHBoxLayout(FahrplanWidget)
        self.horizontalLayout_5.setObjectName(u"horizontalLayout_5")
        self.splitter = QSplitter(FahrplanWidget)
        self.splitter.setObjectName(u"splitter")
        self.splitter.setOrientation(Qt.Horizontal)
        self.zugliste_widget = QTabWidget(self.splitter)
        self.zugliste_widget.setObjectName(u"zugliste_widget")
        self.zugliste_tab = QWidget()
        self.zugliste_tab.setObjectName(u"zugliste_tab")
        self.verticalLayout_2 = QVBoxLayout(self.zugliste_tab)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.horizontalLayout_2 = QHBoxLayout()
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.suche_zug_label = QLabel(self.zugliste_tab)
        self.suche_zug_label.setObjectName(u"suche_zug_label")

        self.horizontalLayout_2.addWidget(self.suche_zug_label)

        self.suche_zug_edit = QLineEdit(self.zugliste_tab)
        self.suche_zug_edit.setObjectName(u"suche_zug_edit")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.suche_zug_edit.sizePolicy().hasHeightForWidth())
        self.suche_zug_edit.setSizePolicy(sizePolicy)

        self.horizontalLayout_2.addWidget(self.suche_zug_edit)

        self.suche_loeschen_button = QPushButton(self.zugliste_tab)
        self.suche_loeschen_button.setObjectName(u"suche_loeschen_button")
        sizePolicy.setHeightForWidth(self.suche_loeschen_button.sizePolicy().hasHeightForWidth())
        self.suche_loeschen_button.setSizePolicy(sizePolicy)
        self.suche_loeschen_button.setMaximumSize(QSize(23, 16777215))

        self.horizontalLayout_2.addWidget(self.suche_loeschen_button)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_2.addItem(self.horizontalSpacer)


        self.verticalLayout_2.addLayout(self.horizontalLayout_2)

        self.zugliste_view = QTableView(self.zugliste_tab)
        self.zugliste_view.setObjectName(u"zugliste_view")
        self.zugliste_view.setAlternatingRowColors(True)

        self.verticalLayout_2.addWidget(self.zugliste_view)

        self.horizontalLayout_3 = QHBoxLayout()
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.vorlaufzeit_label = QLabel(self.zugliste_tab)
        self.vorlaufzeit_label.setObjectName(u"vorlaufzeit_label")

        self.horizontalLayout_3.addWidget(self.vorlaufzeit_label)

        self.vorlaufzeit_spin = QSpinBox(self.zugliste_tab)
        self.vorlaufzeit_spin.setObjectName(u"vorlaufzeit_spin")
        self.vorlaufzeit_spin.setWrapping(True)
        self.vorlaufzeit_spin.setMinimum(0)
        self.vorlaufzeit_spin.setMaximum(120)
        self.vorlaufzeit_spin.setSingleStep(5)
        self.vorlaufzeit_spin.setValue(60)

        self.horizontalLayout_3.addWidget(self.vorlaufzeit_spin)

        self.nachlaufzeit_label = QLabel(self.zugliste_tab)
        self.nachlaufzeit_label.setObjectName(u"nachlaufzeit_label")

        self.horizontalLayout_3.addWidget(self.nachlaufzeit_label)

        self.nachlaufzeit_spin = QSpinBox(self.zugliste_tab)
        self.nachlaufzeit_spin.setObjectName(u"nachlaufzeit_spin")
        self.nachlaufzeit_spin.setWrapping(True)
        self.nachlaufzeit_spin.setMinimum(0)
        self.nachlaufzeit_spin.setMaximum(120)
        self.nachlaufzeit_spin.setSingleStep(5)
        self.nachlaufzeit_spin.setValue(60)

        self.horizontalLayout_3.addWidget(self.nachlaufzeit_spin)

        self.horizontalSpacer_2 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_3.addItem(self.horizontalSpacer_2)


        self.verticalLayout_2.addLayout(self.horizontalLayout_3)

        self.zugliste_widget.addTab(self.zugliste_tab, "")
        self.dispo_tab = QWidget()
        self.dispo_tab.setObjectName(u"dispo_tab")
        self.horizontalLayout_4 = QHBoxLayout(self.dispo_tab)
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.dispo_table = QTableView(self.dispo_tab)
        self.dispo_table.setObjectName(u"dispo_table")

        self.horizontalLayout_4.addWidget(self.dispo_table)

        self.zugliste_widget.addTab(self.dispo_tab, "")
        self.splitter.addWidget(self.zugliste_widget)
        self.tabWidget_2 = QTabWidget(self.splitter)
        self.tabWidget_2.setObjectName(u"tabWidget_2")
        self.fahrplan_tab = QWidget()
        self.fahrplan_tab.setObjectName(u"fahrplan_tab")
        self.horizontalLayout = QHBoxLayout(self.fahrplan_tab)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.fahrplan_splitter = QSplitter(self.fahrplan_tab)
        self.fahrplan_splitter.setObjectName(u"fahrplan_splitter")
        self.fahrplan_splitter.setOrientation(Qt.Vertical)
        self.fahrplan_label = QLabel(self.fahrplan_splitter)
        self.fahrplan_label.setObjectName(u"fahrplan_label")
        self.fahrplan_splitter.addWidget(self.fahrplan_label)
        self.fahrplan_view = QTableView(self.fahrplan_splitter)
        self.fahrplan_view.setObjectName(u"fahrplan_view")
        self.fahrplan_view.setAlternatingRowColors(True)
        self.fahrplan_splitter.addWidget(self.fahrplan_view)
        self.folgezug_label = QLabel(self.fahrplan_splitter)
        self.folgezug_label.setObjectName(u"folgezug_label")
        self.fahrplan_splitter.addWidget(self.folgezug_label)
        self.folgezug_view = QTableView(self.fahrplan_splitter)
        self.folgezug_view.setObjectName(u"folgezug_view")
        self.folgezug_view.setAlternatingRowColors(True)
        self.fahrplan_splitter.addWidget(self.folgezug_view)

        self.horizontalLayout.addWidget(self.fahrplan_splitter)

        self.tabWidget_2.addTab(self.fahrplan_tab, "")
        self.grafik_tab = QWidget()
        self.grafik_tab.setObjectName(u"grafik_tab")
        self.verticalLayout_3 = QVBoxLayout(self.grafik_tab)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.grafik_area = QScrollArea(self.grafik_tab)
        self.grafik_area.setObjectName(u"grafik_area")
        self.grafik_area.setWidgetResizable(True)
        self.grafik_widget = QWidget()
        self.grafik_widget.setObjectName(u"grafik_widget")
        self.grafik_widget.setGeometry(QRect(0, 0, 387, 733))
        self.grafik_area.setWidget(self.grafik_widget)

        self.verticalLayout_3.addWidget(self.grafik_area)

        self.tabWidget_2.addTab(self.grafik_tab, "")
        self.splitter.addWidget(self.tabWidget_2)

        self.horizontalLayout_5.addWidget(self.splitter)

#if QT_CONFIG(shortcut)
        self.vorlaufzeit_label.setBuddy(self.vorlaufzeit_spin)
        self.nachlaufzeit_label.setBuddy(self.nachlaufzeit_spin)
        self.fahrplan_label.setBuddy(self.fahrplan_view)
        self.folgezug_label.setBuddy(self.folgezug_view)
#endif // QT_CONFIG(shortcut)

        self.retranslateUi(FahrplanWidget)

        self.zugliste_widget.setCurrentIndex(0)
        self.tabWidget_2.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(FahrplanWidget)
    # setupUi

    def retranslateUi(self, FahrplanWidget):
        FahrplanWidget.setWindowTitle(QCoreApplication.translate("FahrplanWidget", u"Form", None))
        self.suche_zug_label.setText(QCoreApplication.translate("FahrplanWidget", u"Suche Zug", None))
        self.suche_loeschen_button.setText(QCoreApplication.translate("FahrplanWidget", u"x", None))
        self.vorlaufzeit_label.setText(QCoreApplication.translate("FahrplanWidget", u"V&orlaufzeit", None))
        self.vorlaufzeit_spin.setSpecialValueText(QCoreApplication.translate("FahrplanWidget", u"unbegrenzt", None))
        self.vorlaufzeit_spin.setSuffix(QCoreApplication.translate("FahrplanWidget", u" Min.", None))
        self.nachlaufzeit_label.setText(QCoreApplication.translate("FahrplanWidget", u"N&achlaufzeit", None))
        self.nachlaufzeit_spin.setSpecialValueText(QCoreApplication.translate("FahrplanWidget", u"unbegrenzt", None))
        self.nachlaufzeit_spin.setSuffix(QCoreApplication.translate("FahrplanWidget", u" Min.", None))
        self.zugliste_widget.setTabText(self.zugliste_widget.indexOf(self.zugliste_tab), QCoreApplication.translate("FahrplanWidget", u"Z\u00fcge", None))
        self.zugliste_widget.setTabText(self.zugliste_widget.indexOf(self.dispo_tab), QCoreApplication.translate("FahrplanWidget", u"Dispo", None))
        self.fahrplan_label.setText(QCoreApplication.translate("FahrplanWidget", u"Fahrplan", None))
        self.folgezug_label.setText(QCoreApplication.translate("FahrplanWidget", u"Folgezug", None))
        self.tabWidget_2.setTabText(self.tabWidget_2.indexOf(self.fahrplan_tab), QCoreApplication.translate("FahrplanWidget", u"Fahrplan", None))
        self.tabWidget_2.setTabText(self.tabWidget_2.indexOf(self.grafik_tab), QCoreApplication.translate("FahrplanWidget", u"Grafik", None))
    # retranslateUi

