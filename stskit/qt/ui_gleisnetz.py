# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'gleisnetz.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_GleisnetzWindow(object):
    def setupUi(self, GleisnetzWindow):
        GleisnetzWindow.setObjectName("GleisnetzWindow")
        GleisnetzWindow.resize(800, 600)
        self.centralwidget = QtWidgets.QWidget(GleisnetzWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName("verticalLayout")
        self.scrollArea = QtWidgets.QScrollArea(self.centralwidget)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setObjectName("scrollArea")
        self.scrollAreaWidgetContents = QtWidgets.QWidget()
        self.scrollAreaWidgetContents.setGeometry(QtCore.QRect(0, 0, 780, 580))
        self.scrollAreaWidgetContents.setObjectName("scrollAreaWidgetContents")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(self.scrollAreaWidgetContents)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.scrollArea.setWidget(self.scrollAreaWidgetContents)
        self.verticalLayout.addWidget(self.scrollArea)
        GleisnetzWindow.setCentralWidget(self.centralwidget)

        self.retranslateUi(GleisnetzWindow)
        QtCore.QMetaObject.connectSlotsByName(GleisnetzWindow)

    def retranslateUi(self, GleisnetzWindow):
        _translate = QtCore.QCoreApplication.translate
        GleisnetzWindow.setWindowTitle(_translate("GleisnetzWindow", "Gleisnetz"))

