#!/usr/bin/env python

# Inputmidi records MIDI data to Redis
#
# This software is part of the EEGsynth project, see <https://github.com/eegsynth/eegsynth>.
#
# Copyright (C) 2017-2024 EEGsynth project
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

import mido
from thefuzz import process
import os
import sys
import time

if hasattr(sys, 'frozen'):
    path = os.path.split(sys.executable)[0]
    file = os.path.split(__file__)[-1]
    name = os.path.splitext(file)[0]
elif __name__ == '__main__' and sys.argv[0] != '':
    path = os.path.split(sys.argv[0])[0]
    file = os.path.split(sys.argv[0])[-1]
    name = os.path.splitext(file)[0]
elif __name__ == '__main__':
    path = os.path.abspath('')
    file = os.path.split(path)[-1] + '.py'
    name = os.path.splitext(file)[0]
else:
    path = os.path.split(__file__)[0]
    file = os.path.split(__file__)[-1]
    name = os.path.splitext(file)[0]

# the lib directory contains shared code
sys.path.append(os.path.join(path, '../../lib'))
import EEGsynth


def _setup():
    '''Initialize the module
    This adds a set of global variables
    '''
    global patch, name, path, monitor

    # configure and start the patch, this will parse the command-line arguments and the ini file
    patch = EEGsynth.patch(name=name, path=path)

    # this shows the splash screen and can be used to track parameters that have changed
    monitor = EEGsynth.monitor(name=name, patch=patch, debug=patch.getint('general', 'debug', default=1), target=patch.get('general', 'logging', default=None))

    # there should not be any local variables in this function, they should all be global
    if len(locals()):
        print('LOCALS: ' + ', '.join(locals().keys()))


def _start():
    '''Start the module
    This uses the global variables from setup and adds a set of global variables
    '''
    global patch, name, path, monitor
    global mididevice, output_scale, output_offset, port, inputport

    # check which MIDI devices are accessible
    monitor.info('------- MIDI INPUT ------')
    if not len(mido.get_input_names()):
        raise RuntimeError("no MIDI input devices found")
    for port in mido.get_input_names():
        monitor.info(port)
    monitor.info('-------------------------')
    
    # get the options from the configuration file
    mididevice = patch.getstring('midi', 'device')
    mididevice = EEGsynth.trimquotes(mididevice)
    mididevice = process.extractOne(mididevice, mido.get_input_names())[0]  # select the closest match

    # the scale and offset are used to map MIDI values to Redis values
    output_scale = patch.getfloat('output', 'scale', default=1. / 127)  # MIDI values are from 0 to 127
    output_offset = patch.getfloat('output', 'offset', default=0.)    # MIDI values are from 0 to 127

    try:
        inputport = mido.open_input(mididevice)
        monitor.success('Connected to MIDI input')
    except:
        raise RuntimeError("Cannot connect to MIDI input")

    # there should not be any local variables in this function, they should all be global
    if len(locals()):
        print('LOCALS: ' + ', '.join(locals().keys()))


def _loop_once():
    '''Run the main loop once
    This uses the global variables from setup and start, and adds a set of global variables
    '''
    global patch, name, path, monitor
    global mididevice, output_scale, output_offset, port, inputport

    for msg in inputport.iter_pending():
        monitor.debug(msg)

        if hasattr(msg, "control"):
            # prefix.control000=value
            key = "{}.control{:0>3d}".format(patch.getstring('output', 'prefix'), msg.control)
            val = msg.value
            # map the MIDI values to Redis values between 0 and 1
            val = EEGsynth.rescale(val, slope=output_scale, offset=output_offset)
            patch.setvalue(key, val)

        elif hasattr(msg, "note"):
            # prefix.noteXXX=value
            key = "{}.note{:0>3d}".format(patch.getstring('output', 'prefix'), msg.note)
            val = msg.velocity
            patch.setvalue(key, val)
            key = "{}.note".format(patch.getstring('output', 'prefix'))
            val = msg.note
            patch.setvalue(key, val)

    # there should not be any local variables in this function, they should all be global
    if len(locals()):
        print('LOCALS: ' + ', '.join(locals().keys()))


def _loop_forever():
    '''Run the main loop forever
    '''
    global monitor, patch
    while True:
        monitor.loop()
        _loop_once()
        time.sleep(patch.getfloat('general', 'delay'))


def _stop():
    '''Stop and clean up on SystemExit, KeyboardInterrupt, RuntimeError
    '''
    pass


if __name__ == '__main__':
    _setup()
    _start()
    try:
        _loop_forever()
    except (SystemExit, KeyboardInterrupt, RuntimeError):
        _stop()
    sys.exit()
