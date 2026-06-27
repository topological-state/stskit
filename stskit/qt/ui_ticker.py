# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'ticker.ui'
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
from PySide6.QtWidgets import (QApplication, QCheckBox, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QPushButton, QSizePolicy,
    QSpacerItem, QSpinBox, QTableView, QVBoxLayout,
    QWidget)

class Ui_EreignisTickerWidget(object):
    def setupUi(self, EreignisTickerWidget):
        if not EreignisTickerWidget.objectName():
            EreignisTickerWidget.setObjectName(u"EreignisTickerWidget")
        EreignisTickerWidget.resize(967, 278)
        self.verticalLayout_2 = QVBoxLayout(EreignisTickerWidget)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.horizontalLayout_2 = QHBoxLayout()
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.filter_zug_label = QLabel(EreignisTickerWidget)
        self.filter_zug_label.setObjectName(u"filter_zug_label")

        self.horizontalLayout_2.addWidget(self.filter_zug_label)

        self.filter_zug_edit = QLineEdit(EreignisTickerWidget)
        self.filter_zug_edit.setObjectName(u"filter_zug_edit")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.filter_zug_edit.sizePolicy().hasHeightForWidth())
        self.filter_zug_edit.setSizePolicy(sizePolicy)

        self.horizontalLayout_2.addWidget(self.filter_zug_edit)

        self.filter_loeschen_button = QPushButton(EreignisTickerWidget)
        self.filter_loeschen_button.setObjectName(u"filter_loeschen_button")
        sizePolicy.setHeightForWidth(self.filter_loeschen_button.sizePolicy().hasHeightForWidth())
        self.filter_loeschen_button.setSizePolicy(sizePolicy)
        self.filter_loeschen_button.setMaximumSize(QSize(23, 16777215))

        self.horizontalLayout_2.addWidget(self.filter_loeschen_button)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_2.addItem(self.horizontalSpacer)


        self.verticalLayout_2.addLayout(self.horizontalLayout_2)

        self.ticker_view = QTableView(EreignisTickerWidget)
        self.ticker_view.setObjectName(u"ticker_view")
        self.ticker_view.setAlternatingRowColors(True)

        self.verticalLayout_2.addWidget(self.ticker_view)

        self.horizontalLayout_3 = QHBoxLayout()
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.nachlaufzeit_label = QLabel(EreignisTickerWidget)
        self.nachlaufzeit_label.setObjectName(u"nachlaufzeit_label")

        self.horizontalLayout_3.addWidget(self.nachlaufzeit_label)

        self.nachlaufzeit_spin = QSpinBox(EreignisTickerWidget)
        self.nachlaufzeit_spin.setObjectName(u"nachlaufzeit_spin")
        self.nachlaufzeit_spin.setWrapping(True)
        self.nachlaufzeit_spin.setMinimum(0)
        self.nachlaufzeit_spin.setMaximum(120)
        self.nachlaufzeit_spin.setSingleStep(5)
        self.nachlaufzeit_spin.setValue(120)

        self.horizontalLayout_3.addWidget(self.nachlaufzeit_spin)

        self.auto_scroll_checkbox = QCheckBox(EreignisTickerWidget)
        self.auto_scroll_checkbox.setObjectName(u"auto_scroll_checkbox")

        self.horizontalLayout_3.addWidget(self.auto_scroll_checkbox)

        self.horizontalSpacer_2 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_3.addItem(self.horizontalSpacer_2)


        self.verticalLayout_2.addLayout(self.horizontalLayout_3)

#if QT_CONFIG(shortcut)
        self.filter_zug_label.setBuddy(self.filter_zug_edit)
        self.nachlaufzeit_label.setBuddy(self.nachlaufzeit_spin)
#endif // QT_CONFIG(shortcut)

        self.retranslateUi(EreignisTickerWidget)

        QMetaObject.connectSlotsByName(EreignisTickerWidget)
    # setupUi

    def retranslateUi(self, EreignisTickerWidget):
        EreignisTickerWidget.setWindowTitle(QCoreApplication.translate("EreignisTickerWidget", u"Ticker", None))
        self.filter_zug_label.setText(QCoreApplication.translate("EreignisTickerWidget", u"Zug&filter", None))
        self.filter_loeschen_button.setText(QCoreApplication.translate("EreignisTickerWidget", u"x", None))
        self.nachlaufzeit_label.setText(QCoreApplication.translate("EreignisTickerWidget", u"N&achlaufzeit", None))
        self.nachlaufzeit_spin.setSpecialValueText(QCoreApplication.translate("EreignisTickerWidget", u"unbegrenzt", None))
        self.nachlaufzeit_spin.setSuffix(QCoreApplication.translate("EreignisTickerWidget", u" Min.", None))
        self.auto_scroll_checkbox.setText(QCoreApplication.translate("EreignisTickerWidget", u"Automatisch &scrollen", None))
    # retranslateUi

