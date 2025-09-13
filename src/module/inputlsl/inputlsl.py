#!/usr/bin/env python

# This module translates LSL string markers to Redis control values and and events.
#
# This software is part of the EEGsynth project, see <https://github.com/eegsynth/eegsynth>.
#
# Copyright (C) 2019 EEGsynth project
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

import os
import sys
import time
import pylsl as lsl

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
    global delay, timeout, lsl_name, lsl_type, lsl_format, output_prefix, start, selected, streams, stream, inlet, type, source_id, match, lsl_id

    # get the options from the configuration file
    delay = patch.getfloat('general', 'delay')
    timeout = patch.getfloat('lsl', 'timeout', default=30)
    lsl_name = patch.getstring('lsl', 'name')
    lsl_type = patch.getstring('lsl', 'type')
    lsl_format = patch.getstring('lsl', 'format')
    output_prefix = patch.getstring('output', 'prefix')

    monitor.info("looking for an LSL stream...")
    start = time.time()
    selected = []
    while len(selected) < 1:
        if (time.time() - start) > timeout:
            monitor.error("Error: timeout while waiting for LSL stream")
            raise SystemExit

        # find the desired stream on the lab network
        streams = lsl.resolve_streams()
        for stream in streams:
            inlet = lsl.StreamInlet(stream)
            name = inlet.info().name()
            type = inlet.info().type()
            source_id = inlet.info().source_id()
            # determine whether this stream should be further processed
            match = True
            if len(lsl_name):
                match = match and lsl_name == name
            if len(lsl_type):
                match = match and lsl_type == type
            if match:
                # select this stream for further processing
                selected.append(stream)
                monitor.info('-------- STREAM(*) ------')
            else:
                monitor.info('-------- STREAM ---------')
            monitor.info("name = " + name)
            monitor.info("type = " + type)
        monitor.info('-------------------------')

    # create a new inlet from the first (and hopefully only) selected stream
    inlet = lsl.StreamInlet(selected[0])

    # give some feedback
    lsl_name = inlet.info().name()
    lsl_type = inlet.info().type()
    lsl_id = inlet.info().source_id()
    monitor.success('connected to LSL stream %s (type = %s, id = %s)' % (lsl_name, lsl_type, lsl_id))

    # there should not be any local variables in this function, they should all be global
    if len(locals()):
        print('LOCALS: ' + ', '.join(locals().keys()))


def _loop_once():
    '''Run the main loop once
    This uses the global variables from setup and start, and adds a set of global variables
    '''
    global patch, name, path, monitor
    global delay, timeout, lsl_name, lsl_type, lsl_format, output_prefix, start, selected, streams, stream, inlet, type, source_id, match, lsl_id
    global sample, timestamp

    sample, timestamp = inlet.pull_sample(timeout=delay)
    if not sample == None:

        if lsl_format == 'value':
            # interpret the LSL marker string as a numerical value
            try:
                val = float(sample[0])
            except ValueError:
                val = float('nan')
            # the scale and offset options can be changed on the fly
            scale = patch.getfloat('lsl', 'scale', default=1. / 127)
            offset = patch.getfloat('lsl', 'offset', default=0.)
            val = EEGsynth.rescale(val, slope=scale, offset=offset)
            name = '%s.%s.%s' % (output_prefix, lsl_name, lsl_type)
        else:
            # use the marker string as the name, and use an arbitrary value
            name = '%s.%s.%s.%s' % (output_prefix, lsl_name, lsl_type, sample[0])
            val = 1.

        # send the Redis message
        patch.setvalue(name, val)
        monitor.update(name, val)

    # there should not be any local variables in this function, they should all be global
    if len(locals()):
        print('LOCALS: ' + ', '.join(locals().keys()))


def _loop_forever():
    '''Run the main loop forever
    '''
    global monitor
    while True:
        monitor.loop()
        _loop_once()


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
