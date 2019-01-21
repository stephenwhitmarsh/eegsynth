#!/usr/bin/env python

# Plotsignal plots data from the FieldTrip buffer. Currently it also includes user-defined filtering
#
# This software is part of the EEGsynth project, see https://github.com/eegsynth/eegsynth
#
# Copyright (C) 2017 EEGsynth project
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import ConfigParser  # this is version 2.x specific, on version 3.x it is called "configparser" and has a different API
import redis
import argparse
import numpy as np
import os
import sys
import signal
from scipy.fftpack import fft, fftfreq
from scipy.signal import butter, lfilter, detrend
from scipy.interpolate import interp1d

if hasattr(sys, 'frozen'):
    basis = sys.executable
elif sys.argv[0] != '':
    basis = sys.argv[0]
else:
    basis = './'
installed_folder = os.path.split(basis)[0]

# eegsynth/lib contains shared modules
sys.path.insert(0, os.path.join(installed_folder, '../../lib'))
import EEGsynth
import FieldTrip

parser = argparse.ArgumentParser()
parser.add_argument("-i", "--inifile", default=os.path.join(installed_folder, os.path.splitext(os.path.basename(__file__))[0] + '.ini'), help="optional name of the configuration file")
args = parser.parse_args()

config = ConfigParser.ConfigParser()
config.read(args.inifile)

try:
    r = redis.StrictRedis(host=config.get('redis', 'hostname'), port=config.getint('redis', 'port'), db=0)
    response = r.client_list()
except redis.ConnectionError:
    print "Error: cannot connect to redis server"
    exit()

# combine the patching from the configuration file and Redis
patch = EEGsynth.patch(config, r)
del config

try:
    ftc_host = patch.getstring('fieldtrip', 'hostname')
    print ftc_host
    ftc_port = patch.getint('fieldtrip', 'port')
    if patch.getint('general', 'debug') > 0:
        print 'Trying to connect to buffer on %s:%i ...' % (ftc_host, ftc_port)
    ft_input = FieldTrip.Client()
    ft_input.connect(ftc_host, ftc_port)
    if patch.getint('general', 'debug') > 0:
        print "Connected to input FieldTrip buffer"
except:
    print "Error: cannot connect to input FieldTrip buffer"
    exit()

## Now we have a PATCH and BUFFER object we can give it as argument to the plot object to be run now

from plotsignal_module import *

plotobj = plotsignal_object(patch, ft_input)

plotobj.start()


