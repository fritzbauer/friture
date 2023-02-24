#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2009 Timoth?Lecomte

# This file is part of Friture.
#
# Friture is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as published by
# the Free Software Foundation.
#
# Friture is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Friture.  If not, see <http://www.gnu.org/licenses/>.

"""Level widget that displays peak and RMS levels for 1 or 2 ports."""

import logging

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtQml import QQmlComponent
from PyQt5.QtQuick import QQuickWindow
from PyQt5.QtCore import QStringListModel
from PyQt5.QtCore import QMetaObject, Q_ARG, QVariant


import numpy as np
from scipy.signal import sosfilt, sosfilt_zi

from friture.store import GetStore
from friture.levels_settings import Levels_Settings_Dialog  # settings dialog
from friture.audioproc import audioproc
from friture.level_view_model import LevelViewModel
from friture.iec import dB_to_IEC, dB_to_SPL
from friture_extensions.exp_smoothing_conv import pyx_exp_smoothed_value
from friture.audiobackend import SAMPLING_RATE, AudioBackend
from friture.qml_tools import qml_url, raise_if_error
from friture.signal.weighting import A_weighting 


SMOOTH_DISPLAY_TIMER_PERIOD_MS = 25
LEVEL_TEXT_LABEL_PERIOD_MS = 250

LEVEL_TEXT_LABEL_STEPS = LEVEL_TEXT_LABEL_PERIOD_MS / SMOOTH_DISPLAY_TIMER_PERIOD_MS

class Levels_Widget(QtWidgets.QWidget):

    def __init__(self, parent, engine):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.setObjectName("Levels_Widget")

        self.gridLayout = QtWidgets.QVBoxLayout(self)
        self.gridLayout.setObjectName("gridLayout")

        store = GetStore()
        self.level_view_model = LevelViewModel(store)
        store._dock_states.append(self.level_view_model)
        state_id = len(store._dock_states) - 1

        self.quickWindow = QQuickWindow()
        component = QQmlComponent(engine, qml_url("Levels.qml"), self)
        
        scaleModelData = [
            "100", "99", "80", "70", "60", "50", "40", "30", "20", "10", "0"            
        ]
        #scaleModel = QStringListModel()
        #scaleModel.setStringList(scaleModelData)

        #ListModel = [
        #    ListElement { dB: 100 }
        #    ListElement { dB: 90 }
        #    ListElement { dB: 80 }
        #    ListElement { dB: 70 }
        #    ListElement { dB: 60 }
        #    ListElement { dB: 50 }
        #    ListElement { dB: 40 }
        #    ListElement { dB: 30 }
        #    ListElement { dB: 20 }
        #    ListElement { dB: 10 }
        #    ListElement { dB: 0 }
        #]

        engineContext = engine.rootContext()
        #initialProperties = {"parent": self.quickWindow.contentItem(), "stateId": state_id, "levelScale" : scaleModel}
        initialProperties = {"parent": self.quickWindow.contentItem(), "stateId": state_id}
        self.qmlObject = component.createWithInitialProperties(initialProperties, engineContext)
        self.qmlObject.setParent(self.quickWindow)

        self.quickWidget = QtWidgets.QWidget.createWindowContainer(self.quickWindow, self)
        self.quickWidget.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)       
        self.gridLayout.addWidget(self.quickWidget)

        self.qmlObject.widthChanged.connect(self.onWidthChanged)
        self.onWidthChanged()

        #lm = component.findChild(QtWidgets.QWidget, "levelsMeter")
        #print(f"LM: {lm}")
        #ms = lm.findChild(QtWidgets.QWidget, "meterScale")
        #print(f"MS: {ms}")
        #print(component.levelsMeter.meterScale.scaleModel)
        
        raise_if_error(component)

        self.audiobuffer = None

        # initialize the settings dialog
        self.settings_dialog = Levels_Settings_Dialog(self)

        # initialize the class instance that will do the fft
        self.proc = audioproc()

        # time = SMOOTH_DISPLAY_TIMER_PERIOD_MS/1000. #DISPLAY
        # time = 0.025 #IMPULSE setting for a sound level meter
        # time = 0.125 #FAST setting for a sound level meter
        # time = 1. #SLOW setting for a sound level meter
        self.response_time = 0.300  # 300ms is a common value for VU meters
        # an exponential smoothing filter is a simple IIR filter
        # s_i = alpha*x_i + (1-alpha)*s_{i-1}
        # we compute alpha so that the n most recent samples represent 100*w percent of the output
        w = 0.65
        n = self.response_time * SAMPLING_RATE
        N = 5*n
        self.alpha = 1. - (1. - w) ** (1. / (n + 1))
        self.kernel = (1. - self.alpha) ** (np.arange(0, N)[::-1])
        # first channel
        self.old_rms = 1e-30
        self.old_max = 1e-30
        # second channel
        self.old_rms_2 = 1e-30
        self.old_max_2 = 1e-30

        response_time_peaks = 0.025  # 25ms for instantaneous peaks
        n2 = response_time_peaks / (SMOOTH_DISPLAY_TIMER_PERIOD_MS / 1000.)
        self.alpha2 = 1. - (1. - w) ** (1. / (n2 + 1))

        self.two_channels = False

        self.i = 0

        self.weighting_filter = A_weighting(SAMPLING_RATE, output='sos')
        self.weighting_filter_zi = sosfilt_zi(self.weighting_filter)
        self.weighting_filter_zi_2 = self.weighting_filter_zi
        self.logger.info(self.weighting_filter)
        self.counter = 0        

    def findObject(self, objs, objectName):
        for obj in objs.children():
            ms = self.findObject(obj, objectName)
            if ms is not None:
                return ms
            if obj.objectName() == objectName:
                return obj
        return None
            

    def onWidthChanged(self):
        self.quickWidget.setFixedWidth(int(self.qmlObject.width()))

    # method
    def set_buffer(self, buffer):
        self.audiobuffer = buffer

    def print_names(self, ob):        
        for c in ob.children():
            print(c.objectName)
            if "QAbstractListModel" in str(c.objectName):
                print("fffffound")
                self.list = c
            self.print_names(c)

    def handle_new_data(self, floatdata):
        if floatdata.shape[0] > 1 and not self.two_channels:
            self.two_channels = True
            self.level_view_model.two_channels = True
        elif floatdata.shape[0] == 1 and self.two_channels:
            self.two_channels = False
            self.level_view_model.two_channels = False

        # first channel
        y1 = floatdata[0, :]

        if self.counter == 0:
            #sm = self.qmlObject.findChild(qqml)
            sm = self.qmlObject.findChildren(QtCore.QStringListModel)
            #sm = self.qmlObject.findChildren(QtCore.QAbstractListModel)
            print(len(sm))
            #print(QtCore.QStringListModel(sm[0]).rowCount())
            #QQmlListModel
            #print(sm)

            #print(self.qmlObject.dumpObjectTree())
            #ob = self.findMeterScale(self.qmlObject)

            #print("MS: " + ob.objectName())
            #print("MS:" + self.qmlObject.findChild("meterScale"))
            #QMetaObject.invokeMethod(ob, "toggle", Q_ARG(QVariant, "RMS"))
            
            self.print_names(self.qmlObject)
            print("List:")
            #print(self.list.index(3).data(role = QtCore.Qt.DisplayRole))
            #self.list.index(3).data(role = QtCore.Qt.DisplayRole) = 200
                #print(c.objectName)
            #print(f"SM: {sm.levelsMeter}")
            self.counter = 1
            self.logger.info(f"Length: {len(y1)}")


        if(AudioBackend().get_level_mode() == "dbA"):
            if len(y1) < len(self.weighting_filter):
                self.logger.info(f"ERROR: {len(self.weighting_filter)} samples required but received only {len(y1)} samples.")

            y1, self.weighting_filter_zi = sosfilt(self.weighting_filter, y1, zi=self.weighting_filter_zi)
            

        # exponential smoothing for max
        if len(y1) > 0:
            value_max = np.abs(y1).max()
            if value_max > self.old_max * (1. - self.alpha2):
                self.old_max = value_max
            else:
                # exponential decrease
                #self.old_max = value_max
                self.old_max *= (1. - self.alpha2)

        # exponential smoothing for RMS
        value_rms = pyx_exp_smoothed_value(self.kernel, self.alpha, y1 ** 2, self.old_rms)
        self.old_rms = value_rms

        if(AudioBackend().get_level_mode() == "RMS"):
            val = 10. * np.log10(value_rms + 0. * 1e-80)
            #print(f"{val}: {dB_to_IEC(val)}" )
            #print(f"{val}: {dB_to_SPL(val)}" )
            self.level_view_model.level_data.level_rms = 10. * np.log10(value_rms + 0. * 1e-80)
            self.level_view_model.level_data.level_max = 20. * np.log10(self.old_max + 0. * 1e-80)
            self.level_view_model.level_data_ballistic.peak_iec = dB_to_IEC(max(self.level_view_model.level_data.level_max, self.level_view_model.level_data.level_rms))
        else:
            mic_sensitivity = AudioBackend().get_mic_sensitivity()
            val = 94 - mic_sensitivity + 10. * np.log10(value_rms + 0. * 1e-80)
            #print(f"{val}: {dB_to_IEC(val)}" )
            #print(f"{val}: {dB_to_SPL(val)}" )

            self.level_view_model.level_data.level_rms = 94 - mic_sensitivity + 10. * np.log10(value_rms + 0. * 1e-80)
            self.level_view_model.level_data.level_max = 94 - 3 - mic_sensitivity + 20. * np.log10(self.old_max + 0. * 1e-80)
            #if self.counter < 200:
            #    self.logger.info(f"RMS: {self.level_view_model.level_data.level_rms}")
            #    self.counter += 1
            #self.level_view_model.level_data.level_rms = 10. * np.log10(value_rms + 0. * 1e-80)
            #self.level_view_model.level_data.level_max = 20. * np.log10(self.old_max + 0. * 1e-80)
            self.level_view_model.level_data_ballistic.peak_iec = dB_to_SPL(max(self.level_view_model.level_data.level_max, self.level_view_model.level_data.level_rms))

        if self.two_channels:
            # second channel
            y2 = floatdata[1, :]
            
            if(AudioBackend().get_level_mode() == "dbA"):
                y2, self.weighting_filter_zi_2 = sosfilt(self.weighting_filter, y2, zi=self.weighting_filter_zi_2)
            # exponential smoothing for max
            if len(y2) > 0:
                value_max = np.abs(y2).max()
                if value_max > self.old_max_2 * (1. - self.alpha2):
                    self.old_max_2 = value_max
                else:
                    # exponential decrease
                    self.old_max_2 *= (1. - self.alpha2)

            # exponential smoothing for RMS
            value_rms = pyx_exp_smoothed_value(self.kernel, self.alpha, y2 ** 2, self.old_rms_2)
            self.old_rms_2 = value_rms

            if(AudioBackend().get_level_mode() == "RMS"):
                self.level_view_model.level_data_2.level_rms = 10. * np.log10(value_rms + 0. * 1e-80)
                self.level_view_model.level_data_2.level_max = 20. * np.log10(self.old_max_2 + 0. * 1e-80)
                self.level_view_model.level_data_ballistic_2.peak_iec = dB_to_IEC(max(self.level_view_model.level_data_2.level_max, self.level_view_model.level_data_2.level_rms))
            else:                
                self.level_view_model.level_data_2.level_rms = 94 - mic_sensitivity + 10. * np.log10(value_rms + 0. * 1e-80)
                self.level_view_model.level_data_2.level_max = 94 - 3 - mic_sensitivity + 20. * np.log10(self.old_max_2 + 0. * 1e-80)
                self.level_view_model.level_data_ballistic_2.peak_iec = dB_to_SPL(max(self.level_view_model.level_data_2.level_max, self.level_view_model.level_data_2.level_rms))

    # method
    def canvasUpdate(self):
        if not self.isVisible():
            return

        self.i += 1

        if self.i == LEVEL_TEXT_LABEL_STEPS:
            self.level_view_model.level_data_slow.level_rms = self.level_view_model.level_data.level_rms
            self.level_view_model.level_data_slow.level_max = self.level_view_model.level_data.level_max

            if self.two_channels:
                self.level_view_model.level_data_slow_2.level_rms = self.level_view_model.level_data_2.level_rms
                self.level_view_model.level_data_slow_2.level_max = self.level_view_model.level_data_2.level_max
 
        self.i = self.i % LEVEL_TEXT_LABEL_STEPS

        level_mode = AudioBackend().get_level_mode()
        meterScale = self.findObject(self.qmlObject, "meterScale")
        QMetaObject.invokeMethod(meterScale, "setScaleMode", Q_ARG(QVariant, level_mode))
        #levelsMeter = self.findObject(self.qmlObject, "levelsMeter")
        #QMetaObject.invokeMethod(levelsMeter, "setScaleMode", Q_ARG(QVariant, level_mode))

    # slot
    def settings_called(self, checked):       
        self.settings_dialog.show()

    # method
    def saveState(self, settings):
        self.settings_dialog.saveState(settings)

    # method
    def restoreState(self, settings):
        self.settings_dialog.restoreState(settings)
