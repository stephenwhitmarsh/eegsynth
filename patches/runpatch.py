#!/usr/bin/env python

# using relative paths is a bit messy yet, and this works for now:

import sys
sys.path.append('/home/stephen/PycharmProjects/eegsynth/lib/')
sys.path.append('/home/stephen/PycharmProjects/eegsynth/module/inputcontrol/')

import inputcontrol
inifilepath = '/home/stephen/PycharmProjects/eegsynth/module/inputcontrol/inputcontrol.ini'

module1 = inputcontrol.InputControlWindow(inifilepath)
module1.start()

