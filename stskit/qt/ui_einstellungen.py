# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'einstellungen.ui'
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
from PySide6.QtWidgets import (QAbstractButton, QAbstractItemView, QApplication, QComboBox,
    QDialogButtonBox, QGroupBox, QHBoxLayout, QHeaderView,
    QLabel, QListView, QMainWindow, QPushButton,
    QSizePolicy, QSpacerItem, QSplitter, QTabWidget,
    QTableView, QTextEdit, QVBoxLayout, QWidget)

import stskit.qt.resources_rc

class Ui_EinstellungenWindow(object):
    def setupUi(self, EinstellungenWindow):
        if not EinstellungenWindow.objectName():
            EinstellungenWindow.setObjectName(u"EinstellungenWindow")
        EinstellungenWindow.resize(700, 766)
        self.centralwidget = QWidget(EinstellungenWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.horizontalLayout_3 = QHBoxLayout(self.centralwidget)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.widget = QWidget(self.centralwidget)
        self.widget.setObjectName(u"widget")
        self.verticalLayout_3 = QVBoxLayout(self.widget)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.tab_widget = QTabWidget(self.widget)
        self.tab_widget.setObjectName(u"tab_widget")
        self.anst_tab = QWidget()
        self.anst_tab.setObjectName(u"anst_tab")
        self.anst_tab.setEnabled(True)
        self.verticalLayout_15 = QVBoxLayout(self.anst_tab)
        self.verticalLayout_15.setObjectName(u"verticalLayout_15")
        self.anst_splitter = QSplitter(self.anst_tab)
        self.anst_splitter.setObjectName(u"anst_splitter")
        self.anst_splitter.setOrientation(Qt.Horizontal)
        self.agl_table_view = QTableView(self.anst_splitter)
        self.agl_table_view.setObjectName(u"agl_table_view")
        self.agl_table_view.setAlternatingRowColors(True)
        self.agl_table_view.setSelectionMode(QAbstractItemView.MultiSelection)
        self.agl_table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.agl_table_view.setSortingEnabled(True)
        self.anst_splitter.addWidget(self.agl_table_view)
        self.anst_control_widget = QWidget(self.anst_splitter)
        self.anst_control_widget.setObjectName(u"anst_control_widget")
        self.verticalLayout_10 = QVBoxLayout(self.anst_control_widget)
        self.verticalLayout_10.setObjectName(u"verticalLayout_10")
        self.agl_group = QGroupBox(self.anst_control_widget)
        self.agl_group.setObjectName(u"agl_group")
        self.verticalLayout_11 = QVBoxLayout(self.agl_group)
        self.verticalLayout_11.setObjectName(u"verticalLayout_11")
        self.agl_combo = QComboBox(self.agl_group)
        self.agl_combo.setObjectName(u"agl_combo")
        self.agl_combo.setEditable(True)

        self.verticalLayout_11.addWidget(self.agl_combo)

        self.agl_filter_button = QPushButton(self.agl_group)
        self.agl_filter_button.setObjectName(u"agl_filter_button")

        self.verticalLayout_11.addWidget(self.agl_filter_button)


        self.verticalLayout_10.addWidget(self.agl_group)

        self.anst_group = QGroupBox(self.anst_control_widget)
        self.anst_group.setObjectName(u"anst_group")
        self.verticalLayout_14 = QVBoxLayout(self.anst_group)
        self.verticalLayout_14.setObjectName(u"verticalLayout_14")
        self.anst_combo = QComboBox(self.anst_group)
        self.anst_combo.setObjectName(u"anst_combo")
        self.anst_combo.setEditable(True)

        self.verticalLayout_14.addWidget(self.anst_combo)

        self.anst_group_button = QPushButton(self.anst_group)
        self.anst_group_button.setObjectName(u"anst_group_button")

        self.verticalLayout_14.addWidget(self.anst_group_button)

        self.anst_ungroup_button = QPushButton(self.anst_group)
        self.anst_ungroup_button.setObjectName(u"anst_ungroup_button")

        self.verticalLayout_14.addWidget(self.anst_ungroup_button)

        self.anst_rename_button = QPushButton(self.anst_group)
        self.anst_rename_button.setObjectName(u"anst_rename_button")

        self.verticalLayout_14.addWidget(self.anst_rename_button)


        self.verticalLayout_10.addWidget(self.anst_group)

        self.verticalSpacer_2 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_10.addItem(self.verticalSpacer_2)

        self.anst_splitter.addWidget(self.anst_control_widget)

        self.verticalLayout_15.addWidget(self.anst_splitter)

        self.tab_widget.addTab(self.anst_tab, "")
        self.bahnhof_tab = QWidget()
        self.bahnhof_tab.setObjectName(u"bahnhof_tab")
        self.bahnhof_tab.setEnabled(True)
        self.verticalLayout_8 = QVBoxLayout(self.bahnhof_tab)
        self.verticalLayout_8.setObjectName(u"verticalLayout_8")
        self.bf_splitter = QSplitter(self.bahnhof_tab)
        self.bf_splitter.setObjectName(u"bf_splitter")
        self.bf_splitter.setOrientation(Qt.Horizontal)
        self.gl_table_view = QTableView(self.bf_splitter)
        self.gl_table_view.setObjectName(u"gl_table_view")
        self.gl_table_view.setAlternatingRowColors(True)
        self.gl_table_view.setSelectionMode(QAbstractItemView.MultiSelection)
        self.gl_table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.gl_table_view.setSortingEnabled(True)
        self.bf_splitter.addWidget(self.gl_table_view)
        self.bf_control_widget = QWidget(self.bf_splitter)
        self.bf_control_widget.setObjectName(u"bf_control_widget")
        self.verticalLayout = QVBoxLayout(self.bf_control_widget)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.gl_group = QGroupBox(self.bf_control_widget)
        self.gl_group.setObjectName(u"gl_group")
        self.verticalLayout_7 = QVBoxLayout(self.gl_group)
        self.verticalLayout_7.setObjectName(u"verticalLayout_7")
        self.gl_combo = QComboBox(self.gl_group)
        self.gl_combo.setObjectName(u"gl_combo")
        self.gl_combo.setEditable(True)

        self.verticalLayout_7.addWidget(self.gl_combo)

        self.gl_filter_button = QPushButton(self.gl_group)
        self.gl_filter_button.setObjectName(u"gl_filter_button")

        self.verticalLayout_7.addWidget(self.gl_filter_button)


        self.verticalLayout.addWidget(self.gl_group)

        self.bs_group = QGroupBox(self.bf_control_widget)
        self.bs_group.setObjectName(u"bs_group")
        self.verticalLayout_4 = QVBoxLayout(self.bs_group)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.bs_combo = QComboBox(self.bs_group)
        self.bs_combo.setObjectName(u"bs_combo")
        self.bs_combo.setEditable(True)

        self.verticalLayout_4.addWidget(self.bs_combo)

        self.bs_group_button = QPushButton(self.bs_group)
        self.bs_group_button.setObjectName(u"bs_group_button")

        self.verticalLayout_4.addWidget(self.bs_group_button)

        self.bs_ungroup_button = QPushButton(self.bs_group)
        self.bs_ungroup_button.setObjectName(u"bs_ungroup_button")

        self.verticalLayout_4.addWidget(self.bs_ungroup_button)

        self.bs_rename_button = QPushButton(self.bs_group)
        self.bs_rename_button.setObjectName(u"bs_rename_button")

        self.verticalLayout_4.addWidget(self.bs_rename_button)


        self.verticalLayout.addWidget(self.bs_group)

        self.bft_group = QGroupBox(self.bf_control_widget)
        self.bft_group.setObjectName(u"bft_group")
        self.verticalLayout_5 = QVBoxLayout(self.bft_group)
        self.verticalLayout_5.setObjectName(u"verticalLayout_5")
        self.bft_combo = QComboBox(self.bft_group)
        self.bft_combo.setObjectName(u"bft_combo")
        self.bft_combo.setEditable(True)

        self.verticalLayout_5.addWidget(self.bft_combo)

        self.bft_group_button = QPushButton(self.bft_group)
        self.bft_group_button.setObjectName(u"bft_group_button")

        self.verticalLayout_5.addWidget(self.bft_group_button)

        self.bft_ungroup_button = QPushButton(self.bft_group)
        self.bft_ungroup_button.setObjectName(u"bft_ungroup_button")

        self.verticalLayout_5.addWidget(self.bft_ungroup_button)

        self.bft_rename_button = QPushButton(self.bft_group)
        self.bft_rename_button.setObjectName(u"bft_rename_button")

        self.verticalLayout_5.addWidget(self.bft_rename_button)


        self.verticalLayout.addWidget(self.bft_group)

        self.bf_group = QGroupBox(self.bf_control_widget)
        self.bf_group.setObjectName(u"bf_group")
        self.verticalLayout_6 = QVBoxLayout(self.bf_group)
        self.verticalLayout_6.setObjectName(u"verticalLayout_6")
        self.bf_combo = QComboBox(self.bf_group)
        self.bf_combo.setObjectName(u"bf_combo")
        self.bf_combo.setEditable(True)

        self.verticalLayout_6.addWidget(self.bf_combo)

        self.bf_group_button = QPushButton(self.bf_group)
        self.bf_group_button.setObjectName(u"bf_group_button")

        self.verticalLayout_6.addWidget(self.bf_group_button)

        self.bf_ungroup_button = QPushButton(self.bf_group)
        self.bf_ungroup_button.setObjectName(u"bf_ungroup_button")

        self.verticalLayout_6.addWidget(self.bf_ungroup_button)

        self.bf_rename_button = QPushButton(self.bf_group)
        self.bf_rename_button.setObjectName(u"bf_rename_button")

        self.verticalLayout_6.addWidget(self.bf_rename_button)


        self.verticalLayout.addWidget(self.bf_group)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout.addItem(self.verticalSpacer)

        self.bf_splitter.addWidget(self.bf_control_widget)

        self.verticalLayout_8.addWidget(self.bf_splitter)

        self.tab_widget.addTab(self.bahnhof_tab, "")
        self.strecken_tab = QWidget()
        self.strecken_tab.setObjectName(u"strecken_tab")
        self.strecken_tab.setEnabled(True)
        self.verticalLayout_19 = QVBoxLayout(self.strecken_tab)
        self.verticalLayout_19.setObjectName(u"verticalLayout_19")
        self.verticalLayout_18 = QVBoxLayout()
        self.verticalLayout_18.setObjectName(u"verticalLayout_18")
        self.verticalLayout_17 = QVBoxLayout()
        self.verticalLayout_17.setObjectName(u"verticalLayout_17")
        self.strecken_name_label = QLabel(self.strecken_tab)
        self.strecken_name_label.setObjectName(u"strecken_name_label")

        self.verticalLayout_17.addWidget(self.strecken_name_label)

        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.strecken_name_combo = QComboBox(self.strecken_tab)
        self.strecken_name_combo.setObjectName(u"strecken_name_combo")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.strecken_name_combo.sizePolicy().hasHeightForWidth())
        self.strecken_name_combo.setSizePolicy(sizePolicy)
        self.strecken_name_combo.setEditable(True)

        self.horizontalLayout.addWidget(self.strecken_name_combo)

        self.strecken_erstellen_button = QPushButton(self.strecken_tab)
        self.strecken_erstellen_button.setObjectName(u"strecken_erstellen_button")

        self.horizontalLayout.addWidget(self.strecken_erstellen_button)

        self.strecken_loeschen_button = QPushButton(self.strecken_tab)
        self.strecken_loeschen_button.setObjectName(u"strecken_loeschen_button")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.strecken_loeschen_button.sizePolicy().hasHeightForWidth())
        self.strecken_loeschen_button.setSizePolicy(sizePolicy1)

        self.horizontalLayout.addWidget(self.strecken_loeschen_button)


        self.verticalLayout_17.addLayout(self.horizontalLayout)


        self.verticalLayout_18.addLayout(self.verticalLayout_17)

        self.horizontalLayout_4 = QHBoxLayout()
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.verticalLayout_13 = QVBoxLayout()
        self.verticalLayout_13.setObjectName(u"verticalLayout_13")
        self.strecken_auswahl_label = QLabel(self.strecken_tab)
        self.strecken_auswahl_label.setObjectName(u"strecken_auswahl_label")

        self.verticalLayout_13.addWidget(self.strecken_auswahl_label)

        self.strecken_auswahl_list = QListView(self.strecken_tab)
        self.strecken_auswahl_list.setObjectName(u"strecken_auswahl_list")
        self.strecken_auswahl_list.setDragEnabled(True)
        self.strecken_auswahl_list.setDragDropMode(QAbstractItemView.DragDrop)
        self.strecken_auswahl_list.setDefaultDropAction(Qt.MoveAction)
        self.strecken_auswahl_list.setAlternatingRowColors(True)
        self.strecken_auswahl_list.setSelectionMode(QAbstractItemView.MultiSelection)

        self.verticalLayout_13.addWidget(self.strecken_auswahl_list)


        self.horizontalLayout_4.addLayout(self.verticalLayout_13)

        self.verticalLayout_12 = QVBoxLayout()
        self.verticalLayout_12.setObjectName(u"verticalLayout_12")
        self.verticalSpacer_3 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_12.addItem(self.verticalSpacer_3)

        self.strecken_auswahl_button = QPushButton(self.strecken_tab)
        self.strecken_auswahl_button.setObjectName(u"strecken_auswahl_button")
        sizePolicy1.setHeightForWidth(self.strecken_auswahl_button.sizePolicy().hasHeightForWidth())
        self.strecken_auswahl_button.setSizePolicy(sizePolicy1)

        self.verticalLayout_12.addWidget(self.strecken_auswahl_button)

        self.strecken_abwahl_button = QPushButton(self.strecken_tab)
        self.strecken_abwahl_button.setObjectName(u"strecken_abwahl_button")
        sizePolicy1.setHeightForWidth(self.strecken_abwahl_button.sizePolicy().hasHeightForWidth())
        self.strecken_abwahl_button.setSizePolicy(sizePolicy1)

        self.verticalLayout_12.addWidget(self.strecken_abwahl_button)

        self.strecken_hoch_button = QPushButton(self.strecken_tab)
        self.strecken_hoch_button.setObjectName(u"strecken_hoch_button")
        sizePolicy1.setHeightForWidth(self.strecken_hoch_button.sizePolicy().hasHeightForWidth())
        self.strecken_hoch_button.setSizePolicy(sizePolicy1)

        self.verticalLayout_12.addWidget(self.strecken_hoch_button)

        self.strecken_runter_button = QPushButton(self.strecken_tab)
        self.strecken_runter_button.setObjectName(u"strecken_runter_button")
        sizePolicy1.setHeightForWidth(self.strecken_runter_button.sizePolicy().hasHeightForWidth())
        self.strecken_runter_button.setSizePolicy(sizePolicy1)

        self.verticalLayout_12.addWidget(self.strecken_runter_button)

        self.strecken_ordnen_button = QPushButton(self.strecken_tab)
        self.strecken_ordnen_button.setObjectName(u"strecken_ordnen_button")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.strecken_ordnen_button.sizePolicy().hasHeightForWidth())
        self.strecken_ordnen_button.setSizePolicy(sizePolicy2)

        self.verticalLayout_12.addWidget(self.strecken_ordnen_button)

        self.verticalSpacer_4 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_12.addItem(self.verticalSpacer_4)


        self.horizontalLayout_4.addLayout(self.verticalLayout_12)

        self.verticalLayout_16 = QVBoxLayout()
        self.verticalLayout_16.setObjectName(u"verticalLayout_16")
        self.strecken_abwahl_label = QLabel(self.strecken_tab)
        self.strecken_abwahl_label.setObjectName(u"strecken_abwahl_label")

        self.verticalLayout_16.addWidget(self.strecken_abwahl_label)

        self.strecken_abwahl_list = QListView(self.strecken_tab)
        self.strecken_abwahl_list.setObjectName(u"strecken_abwahl_list")
        self.strecken_abwahl_list.setDragEnabled(True)
        self.strecken_abwahl_list.setDragDropMode(QAbstractItemView.DragDrop)
        self.strecken_abwahl_list.setAlternatingRowColors(True)
        self.strecken_abwahl_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.strecken_abwahl_list.setSelectionBehavior(QAbstractItemView.SelectItems)

        self.verticalLayout_16.addWidget(self.strecken_abwahl_list)


        self.horizontalLayout_4.addLayout(self.verticalLayout_16)


        self.verticalLayout_18.addLayout(self.horizontalLayout_4)


        self.verticalLayout_19.addLayout(self.verticalLayout_18)

        self.tab_widget.addTab(self.strecken_tab, "")
        self.zugschema_tab = QWidget()
        self.zugschema_tab.setObjectName(u"zugschema_tab")
        self.horizontalLayout_2 = QHBoxLayout(self.zugschema_tab)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.verticalLayout_2 = QVBoxLayout()
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.zugschema_name_label = QLabel(self.zugschema_tab)
        self.zugschema_name_label.setObjectName(u"zugschema_name_label")

        self.verticalLayout_2.addWidget(self.zugschema_name_label)

        self.zugschema_name_combo = QComboBox(self.zugschema_tab)
        self.zugschema_name_combo.setObjectName(u"zugschema_name_combo")

        self.verticalLayout_2.addWidget(self.zugschema_name_combo)

        self.zugschema_details_label = QLabel(self.zugschema_tab)
        self.zugschema_details_label.setObjectName(u"zugschema_details_label")

        self.verticalLayout_2.addWidget(self.zugschema_details_label)

        self.zugschema_details_table = QTableView(self.zugschema_tab)
        self.zugschema_details_table.setObjectName(u"zugschema_details_table")
        self.zugschema_details_table.setSelectionBehavior(QAbstractItemView.SelectRows)

        self.verticalLayout_2.addWidget(self.zugschema_details_table)


        self.horizontalLayout_2.addLayout(self.verticalLayout_2)

        self.tab_widget.addTab(self.zugschema_tab, "")
        self.hilfe_tab = QWidget()
        self.hilfe_tab.setObjectName(u"hilfe_tab")
        self.verticalLayout_9 = QVBoxLayout(self.hilfe_tab)
        self.verticalLayout_9.setObjectName(u"verticalLayout_9")
        self.hilfe_text = QTextEdit(self.hilfe_tab)
        self.hilfe_text.setObjectName(u"hilfe_text")
        self.hilfe_text.setReadOnly(True)

        self.verticalLayout_9.addWidget(self.hilfe_text)

        self.tab_widget.addTab(self.hilfe_tab, "")

        self.verticalLayout_3.addWidget(self.tab_widget)

        self.dialog_button_box = QDialogButtonBox(self.widget)
        self.dialog_button_box.setObjectName(u"dialog_button_box")
        self.dialog_button_box.setOrientation(Qt.Horizontal)
        self.dialog_button_box.setStandardButtons(QDialogButtonBox.Apply|QDialogButtonBox.Cancel|QDialogButtonBox.Ok|QDialogButtonBox.Reset)

        self.verticalLayout_3.addWidget(self.dialog_button_box)


        self.horizontalLayout_3.addWidget(self.widget)

        EinstellungenWindow.setCentralWidget(self.centralwidget)
#if QT_CONFIG(shortcut)
        self.strecken_name_label.setBuddy(self.strecken_name_combo)
        self.strecken_auswahl_label.setBuddy(self.strecken_auswahl_list)
        self.strecken_abwahl_label.setBuddy(self.strecken_abwahl_list)
        self.zugschema_name_label.setBuddy(self.zugschema_name_label)
        self.zugschema_details_label.setBuddy(self.zugschema_details_table)
#endif // QT_CONFIG(shortcut)

        self.retranslateUi(EinstellungenWindow)
        self.dialog_button_box.accepted.connect(EinstellungenWindow.accept)
        self.dialog_button_box.rejected.connect(EinstellungenWindow.reject)

        self.tab_widget.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(EinstellungenWindow)
    # setupUi

    def retranslateUi(self, EinstellungenWindow):
        EinstellungenWindow.setWindowTitle(QCoreApplication.translate("EinstellungenWindow", u"Einstellungen", None))
        self.agl_group.setTitle(QCoreApplication.translate("EinstellungenWindow", u"Anschlussgleis (Agl)", None))
#if QT_CONFIG(tooltip)
        self.agl_combo.setToolTip(QCoreApplication.translate("EinstellungenWindow", u"Filterkriterium", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(tooltip)
        self.agl_filter_button.setToolTip(QCoreApplication.translate("EinstellungenWindow", u"Gleistabelle filtern", None))
#endif // QT_CONFIG(tooltip)
        self.agl_filter_button.setText(QCoreApplication.translate("EinstellungenWindow", u"Filter", None))
        self.anst_group.setTitle(QCoreApplication.translate("EinstellungenWindow", u"Anschlussstelle (Anst)", None))
#if QT_CONFIG(tooltip)
        self.anst_combo.setToolTip(QCoreApplication.translate("EinstellungenWindow", u"Ziel-Anschlussstelle", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(tooltip)
        self.anst_group_button.setToolTip(QCoreApplication.translate("EinstellungenWindow", u"Ausgew\u00e4hlte Gleise der Ziel-Anschlussstelle zuordnen", None))
#endif // QT_CONFIG(tooltip)
        self.anst_group_button.setText(QCoreApplication.translate("EinstellungenWindow", u"Zuordnen", None))
#if QT_CONFIG(tooltip)
        self.anst_ungroup_button.setToolTip(QCoreApplication.translate("EinstellungenWindow", u"Ausgew\u00e4hlte Gleise auf eigene Anschlussstellen aufteilen (Anst aufl\u00f6sen)", None))
#endif // QT_CONFIG(tooltip)
        self.anst_ungroup_button.setText(QCoreApplication.translate("EinstellungenWindow", u"Aufteilen", None))
#if QT_CONFIG(tooltip)
        self.anst_rename_button.setToolTip(QCoreApplication.translate("EinstellungenWindow", u"Anschlussstelle umbenennen", None))
#endif // QT_CONFIG(tooltip)
        self.anst_rename_button.setText(QCoreApplication.translate("EinstellungenWindow", u"Umbenennen", None))
        self.tab_widget.setTabText(self.tab_widget.indexOf(self.anst_tab), QCoreApplication.translate("EinstellungenWindow", u"Anschlussstellen", None))
        self.gl_group.setTitle(QCoreApplication.translate("EinstellungenWindow", u"Gleis (Gl)", None))
#if QT_CONFIG(tooltip)
        self.gl_combo.setToolTip(QCoreApplication.translate("EinstellungenWindow", u"Filterkriterium", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(tooltip)
        self.gl_filter_button.setToolTip(QCoreApplication.translate("EinstellungenWindow", u"Gleistabelle filtern", None))
#endif // QT_CONFIG(tooltip)
        self.gl_filter_button.setText(QCoreApplication.translate("EinstellungenWindow", u"Filter", None))
        self.bs_group.setTitle(QCoreApplication.translate("EinstellungenWindow", u"Bahnsteig (Bs)", None))
#if QT_CONFIG(tooltip)
        self.bs_combo.setToolTip(QCoreApplication.translate("EinstellungenWindow", u"Ziel-Bahnsteig", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(tooltip)
        self.bs_group_button.setToolTip(QCoreApplication.translate("EinstellungenWindow", u"Ausgew\u00e4hlte Gleise zu Ziel-Bahnsteig zuordnen", None))
#endif // QT_CONFIG(tooltip)
        self.bs_group_button.setText(QCoreApplication.translate("EinstellungenWindow", u"Zuordnen", None))
#if QT_CONFIG(tooltip)
        self.bs_ungroup_button.setToolTip(QCoreApplication.translate("EinstellungenWindow", u"Ausgew\u00e4hlte Gleise auf eigene Bahnsteige aufteilen (Bahnsteig aufl\u00f6sen)", None))
#endif // QT_CONFIG(tooltip)
        self.bs_ungroup_button.setText(QCoreApplication.translate("EinstellungenWindow", u"Aufteilen", None))
#if QT_CONFIG(tooltip)
        self.bs_rename_button.setToolTip(QCoreApplication.translate("EinstellungenWindow", u"Bahnhsteig umbenennen", None))
#endif // QT_CONFIG(tooltip)
        self.bs_rename_button.setText(QCoreApplication.translate("EinstellungenWindow", u"Umbenennen", None))
        self.bft_group.setTitle(QCoreApplication.translate("EinstellungenWindow", u"Bahnhofteil (Bft)", None))
#if QT_CONFIG(tooltip)
        self.bft_combo.setToolTip(QCoreApplication.translate("EinstellungenWindow", u"Ziel-Bahnhofteil", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(tooltip)
        self.bft_group_button.setToolTip(QCoreApplication.translate("EinstellungenWindow", u"Ausgew\u00e4hlte Gleise zu Ziel-Bahnhofteil zuordnen", None))
#endif // QT_CONFIG(tooltip)
        self.bft_group_button.setText(QCoreApplication.translate("EinstellungenWindow", u"Zuordnen", None))
#if QT_CONFIG(tooltip)
        self.bft_ungroup_button.setToolTip(QCoreApplication.translate("EinstellungenWindow", u"Ausgew\u00e4hlte Gleise auf eigene Bahnhofteile aufteilen (Bahnhofteil aufl\u00f6sen)", None))
#endif // QT_CONFIG(tooltip)
        self.bft_ungroup_button.setText(QCoreApplication.translate("EinstellungenWindow", u"Aufteilen", None))
#if QT_CONFIG(tooltip)
        self.bft_rename_button.setToolTip(QCoreApplication.translate("EinstellungenWindow", u"Bahnhofteil umbenennen", None))
#endif // QT_CONFIG(tooltip)
        self.bft_rename_button.setText(QCoreApplication.translate("EinstellungenWindow", u"Umbenennen", None))
        self.bf_group.setTitle(QCoreApplication.translate("EinstellungenWindow", u"Bahnhof (Bf)", None))
#if QT_CONFIG(tooltip)
        self.bf_combo.setToolTip(QCoreApplication.translate("EinstellungenWindow", u"Ziel-Bahnhof", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(tooltip)
        self.bf_group_button.setToolTip(QCoreApplication.translate("EinstellungenWindow", u"Ausgew\u00e4hlte Gleise zu Ziel-Bahnhof zuordnen", None))
#endif // QT_CONFIG(tooltip)
        self.bf_group_button.setText(QCoreApplication.translate("EinstellungenWindow", u"Zuordnen", None))
#if QT_CONFIG(tooltip)
        self.bf_ungroup_button.setToolTip(QCoreApplication.translate("EinstellungenWindow", u"Ausgew\u00e4hlte Bahnhofteile auf eigene Bahnh\u00f6fe aufteilen (Bahnhof aufl\u00f6sen)", None))
#endif // QT_CONFIG(tooltip)
        self.bf_ungroup_button.setText(QCoreApplication.translate("EinstellungenWindow", u"Aufteilen", None))
#if QT_CONFIG(tooltip)
        self.bf_rename_button.setToolTip(QCoreApplication.translate("EinstellungenWindow", u"Bahnhof umbenennen", None))
#endif // QT_CONFIG(tooltip)
        self.bf_rename_button.setText(QCoreApplication.translate("EinstellungenWindow", u"Umbenennen", None))
        self.tab_widget.setTabText(self.tab_widget.indexOf(self.bahnhof_tab), QCoreApplication.translate("EinstellungenWindow", u"Bahnh\u00f6fe", None))
        self.strecken_name_label.setText(QCoreApplication.translate("EinstellungenWindow", u"Strecke", None))
        self.strecken_name_combo.setPlaceholderText(QCoreApplication.translate("EinstellungenWindow", u"Streckenname", None))
        self.strecken_erstellen_button.setText(QCoreApplication.translate("EinstellungenWindow", u"+", None))
        self.strecken_loeschen_button.setText(QCoreApplication.translate("EinstellungenWindow", u"-", None))
        self.strecken_auswahl_label.setText(QCoreApplication.translate("EinstellungenWindow", u"Gew\u00e4hlte Stationen", None))
        self.strecken_auswahl_button.setText(QCoreApplication.translate("EinstellungenWindow", u"\u2b05\ufe0f", None))
        self.strecken_abwahl_button.setText(QCoreApplication.translate("EinstellungenWindow", u"\u27a1\ufe0f", None))
        self.strecken_hoch_button.setText(QCoreApplication.translate("EinstellungenWindow", u"\u2b06\ufe0f", None))
        self.strecken_runter_button.setText(QCoreApplication.translate("EinstellungenWindow", u"\u2b07\ufe0f", None))
        self.strecken_ordnen_button.setText(QCoreApplication.translate("EinstellungenWindow", u"Ordnen", None))
        self.strecken_abwahl_label.setText(QCoreApplication.translate("EinstellungenWindow", u"\u00fcbrige Stationen", None))
        self.tab_widget.setTabText(self.tab_widget.indexOf(self.strecken_tab), QCoreApplication.translate("EinstellungenWindow", u"Strecken", None))
        self.zugschema_name_label.setText(QCoreApplication.translate("EinstellungenWindow", u"Zugschema", None))
        self.zugschema_details_label.setText(QCoreApplication.translate("EinstellungenWindow", u"Kategorien", None))
        self.tab_widget.setTabText(self.tab_widget.indexOf(self.zugschema_tab), QCoreApplication.translate("EinstellungenWindow", u"Zugschema", None))
        self.tab_widget.setTabText(self.tab_widget.indexOf(self.hilfe_tab), QCoreApplication.translate("EinstellungenWindow", u"Hilfe", None))
    # retranslateUi

