# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'rangierplan.ui'
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
    QLineEdit, QPushButton, QSizePolicy, QSpacerItem,
    QSpinBox, QSplitter, QTabWidget, QTableView,
    QVBoxLayout, QWidget)
import stskit.qt.resources_rc

class Ui_RangierplanWidget(object):
    def setupUi(self, RangierplanWidget):
        if not RangierplanWidget.objectName():
            RangierplanWidget.setObjectName(u"RangierplanWidget")
        RangierplanWidget.resize(967, 278)
        self.verticalLayout = QVBoxLayout(RangierplanWidget)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.splitter = QSplitter(RangierplanWidget)
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
        self.splitter.addWidget(self.zugliste_widget)
        self.fahrplan_widget = QTabWidget(self.splitter)
        self.fahrplan_widget.setObjectName(u"fahrplan_widget")
        self.fahrplan_tab = QWidget()
        self.fahrplan_tab.setObjectName(u"fahrplan_tab")
        self.verticalLayout_3 = QVBoxLayout(self.fahrplan_tab)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.fahrplan_label = QLabel(self.fahrplan_tab)
        self.fahrplan_label.setObjectName(u"fahrplan_label")

        self.verticalLayout_3.addWidget(self.fahrplan_label)

        self.fahrplan_view = QTableView(self.fahrplan_tab)
        self.fahrplan_view.setObjectName(u"fahrplan_view")
        self.fahrplan_view.setMinimumSize(QSize(0, 0))
        self.fahrplan_view.setAlternatingRowColors(True)

        self.verticalLayout_3.addWidget(self.fahrplan_view)

        self.fahrplan_widget.addTab(self.fahrplan_tab, "")
        self.splitter.addWidget(self.fahrplan_widget)

        self.verticalLayout.addWidget(self.splitter)

#if QT_CONFIG(shortcut)
        self.vorlaufzeit_label.setBuddy(self.vorlaufzeit_spin)
        self.nachlaufzeit_label.setBuddy(self.nachlaufzeit_spin)
        self.fahrplan_label.setBuddy(self.fahrplan_view)
#endif // QT_CONFIG(shortcut)

        self.retranslateUi(RangierplanWidget)

        self.fahrplan_widget.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(RangierplanWidget)
    # setupUi

    def retranslateUi(self, RangierplanWidget):
        RangierplanWidget.setWindowTitle(QCoreApplication.translate("RangierplanWidget", u"Form", None))
        self.suche_zug_label.setText(QCoreApplication.translate("RangierplanWidget", u"Suche Zug", None))
        self.suche_loeschen_button.setText(QCoreApplication.translate("RangierplanWidget", u"x", None))
#if QT_CONFIG(tooltip)
        self.zugliste_view.setToolTip(QCoreApplication.translate("RangierplanWidget", u"Tasten E/L zum Wechseln des Lokstatus", None))
#endif // QT_CONFIG(tooltip)
        self.vorlaufzeit_label.setText(QCoreApplication.translate("RangierplanWidget", u"V&orlaufzeit", None))
        self.vorlaufzeit_spin.setSpecialValueText(QCoreApplication.translate("RangierplanWidget", u"unbegrenzt", None))
        self.vorlaufzeit_spin.setSuffix(QCoreApplication.translate("RangierplanWidget", u" Min.", None))
        self.nachlaufzeit_label.setText(QCoreApplication.translate("RangierplanWidget", u"N&achlaufzeit", None))
        self.nachlaufzeit_spin.setSpecialValueText(QCoreApplication.translate("RangierplanWidget", u"unbegrenzt", None))
        self.nachlaufzeit_spin.setSuffix(QCoreApplication.translate("RangierplanWidget", u" Min.", None))
        self.zugliste_widget.setTabText(self.zugliste_widget.indexOf(self.zugliste_tab), QCoreApplication.translate("RangierplanWidget", u"Lokwechsel", None))
        self.fahrplan_label.setText(QCoreApplication.translate("RangierplanWidget", u"Zugfahrplan", None))
        self.fahrplan_widget.setTabText(self.fahrplan_widget.indexOf(self.fahrplan_tab), QCoreApplication.translate("RangierplanWidget", u"Fahrplan", None))
    # retranslateUi

