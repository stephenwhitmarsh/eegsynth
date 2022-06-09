#!/usr/bin/env python

# Generatecontrol creates user-defined signals and writes these to Redis
#
# This software is part of the EEGsynth project, see <https://github.com/eegsynth/eegsynth>.
#
# Copyright (C) 2017-2022 EEGsynth project
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

import configparser
import argparse
import numpy as np
import os
import redis
import sys
import time
from scipy import signal

if hasattr(sys, 'frozen'):
    path = os.path.split(sys.executable)[0]
    file = os.path.split(sys.executable)[-1]
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

# eegsynth/lib contains shared modules
sys.path.insert(0, os.path.join(path, '../../lib'))
import EEGsynth

def _setup():
    """Initialize the module
    This adds a set of global variables
    """
    global parser, args, config, r, response, patch

    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--inifile", default=os.path.join(path, name + '.ini'), help="name of the configuration file")
    args = parser.parse_args()

    config = configparser.ConfigParser(inline_comment_prefixes=('#', ';'))
    config.read(args.inifile)

    try:
        r = redis.StrictRedis(host=config.get('redis', 'hostname'), port=config.getint('redis', 'port'), db=0, charset='utf-8', decode_responses=True)
        response = r.client_list()
    except redis.ConnectionError:
        raise RuntimeError("cannot connect to Redis server")

    # combine the patching from the configuration file and Redis
    patch = EEGsynth.patch(config, r)

    # there should not be any local variables in this function, they should all be global
    if len(locals()):
        print("LOCALS: " + ", ".join(locals().keys()))


def _start():
    """Start the module
    This uses the global variables from setup and adds a set of global variables
    """
    global parser, args, config, r, response, patch, name
    global monitor, stepsize, scale_frequency, scale_amplitude, scale_offset, scale_noise, scale_dutycycle, offset_frequency, offset_amplitude, offset_offset, offset_noise, offset_dutycycle, sample, phase

    # this can be used to show parameters that have changed
    monitor = EEGsynth.monitor(name=name, debug=patch.getint('general', 'debug'))

    # get the options from the configuration file
    stepsize = patch.getfloat('generate', 'stepsize')  # in seconds

    # the scale and offset are used to map the Redis values to internal values
    scale_frequency = patch.getfloat('scale', 'frequency', default=1)
    scale_amplitude = patch.getfloat('scale', 'amplitude', default=1)
    scale_offset = patch.getfloat('scale', 'offset', default=1)
    scale_noise = patch.getfloat('scale', 'noise', default=1)
    scale_dutycycle = patch.getfloat('scale', 'dutycycle', default=1)
    offset_frequency = patch.getfloat('offset', 'frequency', default=0)
    offset_amplitude = patch.getfloat('offset', 'amplitude', default=0)
    offset_offset = patch.getfloat('offset', 'offset', default=0)
    offset_noise = patch.getfloat('offset', 'noise', default=0)
    offset_dutycycle = patch.getfloat('offset', 'dutycycle', default=0)

    # the sample number and phase should be 0 upon the start of the signal
    sample = 0
    phase = 0

    # there should not be any local variables in this function, they should all be global
    if len(locals()):
        print("LOCALS: " + ", ".join(locals().keys()))


def _loop_once():
    """Run the main loop once
    This uses the global variables from setup and start, and adds a set of global variables
    """
    global parser, args, config, r, response, patch
    global monitor, stepsize, scale_frequency, scale_amplitude, scale_offset, scale_noise, scale_dutycycle, offset_frequency, offset_amplitude, offset_offset, offset_noise, offset_dutycycle, sample, phase
    global frequency, amplitude, offset, noise, dutycycle, key, val, elapsed, naptime

    if patch.getint('signal', 'rewind', default=0):
        monitor.info("Rewind pressed, jumping back to start of signal")
        # the sample number and phase should be 0 upon the start of the signal
        sample = 0
        phase = 0

    if not patch.getint('signal', 'play', default=1):
        monitor.info("Stopped")
        time.sleep(0.1)
        # the sample number and phase should be 0 upon the start of the signal
        sample = 0
        phase = 0
        return

    if patch.getint('signal', 'pause', default=0):
        monitor.info("Paused")
        time.sleep(0.1)
        return

    frequency = patch.getfloat('signal', 'frequency', default=0.2)
    amplitude = patch.getfloat('signal', 'amplitude', default=0.3)
    offset = patch.getfloat('signal', 'offset', default=0.5)
    noise = patch.getfloat('signal', 'noise', default=0.1)
    dutycycle = patch.getfloat('signal', 'dutycycle', default=0.5)   # for the square wave

    # map the Redis values to signal parameters
    frequency = EEGsynth.rescale(
        frequency, slope=scale_frequency, offset=offset_frequency)
    amplitude = EEGsynth.rescale(
        amplitude, slope=scale_amplitude, offset=offset_amplitude)
    offset = EEGsynth.rescale(offset, slope=scale_offset, offset=offset_offset)
    noise = EEGsynth.rescale(noise, slope=scale_noise, offset=offset_noise)
    dutycycle = EEGsynth.rescale(
        dutycycle, slope=scale_dutycycle, offset=offset_dutycycle)

    monitor.update("frequency", frequency)
    monitor.update("amplitude", amplitude)
    monitor.update("offset   ", offset)
    monitor.update("noise    ", noise)
    monitor.update("dutycycle", dutycycle)

    # compute the phase of this sample
    phase = phase + 2 * np.pi * frequency * stepsize

    key = patch.getstring('output', 'prefix') + '.sin'
    val = np.sin(phase) * amplitude + offset + np.random.randn(1) * noise
    patch.setvalue(key, val[0])

    key = patch.getstring('output', 'prefix') + '.square'
    val = signal.square(phase, dutycycle) * amplitude + offset + np.random.randn(1) * noise
    patch.setvalue(key, val[0])

    key = patch.getstring('output', 'prefix') + '.triangle'
    val = signal.sawtooth(phase, 0.5) * amplitude + offset + np.random.randn(1) * noise
    patch.setvalue(key, val[0])

    key = patch.getstring('output', 'prefix') + '.sawtooth'
    val = signal.sawtooth(phase, 1) * amplitude + offset + np.random.randn(1) * noise
    patch.setvalue(key, val[0])

    sample += 1

    # there should not be any local variables in this function, they should all be global
    if len(locals()):
        print("LOCALS: " + ", ".join(locals().keys()))


def _loop_forever():
    """Run the main loop forever
    """
    global monitor, stepsize
    while True:
        # measure the time to correct for the slip
        start = time.time()

        monitor.loop()
        _loop_once()

        # correct for the slip
        elapsed = time.time() - start
        naptime = stepsize - elapsed
        if naptime > 0:
            # this approximates the real time streaming speed
            time.sleep(naptime)



def _stop():
    """Stop and clean up on SystemExit, KeyboardInterrupt
    """
    sys.exit()


if __name__ == "__main__":
    _setup()
    _start()
    try:
        _loop_forever()
    except (SystemExit, KeyboardInterrupt, RuntimeError):
        _stop()
