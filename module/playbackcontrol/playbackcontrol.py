#!/usr/bin/env python

# This module plays back data from an EDF file to Redis
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
import EDF


def _setup():
    '''Initialize the module
    This adds a set of global variables
    '''
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
        print('LOCALS: ' + ', '.join(locals().keys()))


def _start():
    '''Start the module
    This uses the global variables from setup and adds a set of global variables
    '''
    global parser, args, config, r, response, patch, name
    global monitor, debug, filename, f, chanindx, channels, channelz, fSample, nSamples, replace, i, s, z, blocksize, begsample, endsample, block

    # this can be used to show parameters that have changed
    monitor = EEGsynth.monitor(name=name, debug=patch.getint('general', 'debug'))

    # get the options from the configuration file
    debug = patch.getint('general', 'debug')
    filename = patch.getstring('playback', 'file')

    monitor.info("Reading data from " + filename)

    f = EDF.EDFReader()
    f.open(filename)

    monitor.info("NSignals = " + str(f.getNSignals()))
    monitor.info("SignalFreqs = " + str(f.getSignalFreqs()))
    monitor.info("NSamples = " + str(f.getNSamples()))
    monitor.info("SignalTextLabels = " + str(f.getSignalTextLabels()))

    for chanindx in range(f.getNSignals()):
        if f.getSignalFreqs()[chanindx] != f.getSignalFreqs()[0]:
            raise AssertionError('unequal SignalFreqs')
        if f.getNSamples()[chanindx] != f.getNSamples()[0]:
            raise AssertionError('unequal NSamples')

    channels = f.getSignalTextLabels()
    channelz = f.getSignalTextLabels()

    fSample = f.getSignalFreqs()[0]
    nSamples = f.getNSamples()[0]

    # search-and-replace to reduce the length of the channel labels
    for replace in config.items('replace'):
        monitor.debug(replace)
        for i in range(len(channelz)):
            channelz[i] = channelz[i].replace(replace[0], replace[1])
    for s, z in zip(channels, channelz):
        monitor.info("Writing channel " + s + " as control value " + z)

    # this should write data in one-sample blocks
    blocksize = 1
    begsample = 0
    endsample = blocksize - 1
    block = 0

    # there should not be any local variables in this function, they should all be global
    if len(locals()):
        print('LOCALS: ' + ', '.join(locals().keys()))


def _loop_once():
    '''Run the main loop once
    This uses the global variables from setup and start, and adds a set of global variables
    '''
    global parser, args, config, r, response, patch
    global monitor, debug, filename, f, chanindx, channels, channelz, fSample, nSamples, replace, i, s, z, blocksize, begsample, endsample, block
    global indx, val, stepsize, elapsed, naptime

    if endsample > nSamples - 1:
        monitor.info("End of file reached, jumping back to start")
        begsample = 0
        endsample = blocksize - 1
        block = 0

    if patch.getint('playback', 'rewind', default=0):
        monitor.info("Rewind pressed, jumping back to start of file")
        begsample = 0
        endsample = blocksize - 1
        block = 0

    if not patch.getint('playback', 'play', default=1):
        monitor.info("Stopped")
        time.sleep(0.1)
        return

    if patch.getint('playback', 'pause', default=0):
        monitor.info("Paused")
        time.sleep(0.1)
        return

    monitor.debug("Playing control value", block, 'from', begsample, 'to', endsample)

    for indx in range(len(channelz)):
        # read one sample for a single channel
        val = float(f.readSamples(indx, begsample, endsample))
        patch.setvalue(channelz[indx], val)

    stepsize = blocksize / (fSample * patch.getfloat('playback', 'speed'))
    begsample += blocksize
    endsample += blocksize
    block += 1

    # there should not be any local variables in this function, they should all be global
    if len(locals()):
        print('LOCALS: ' + ', '.join(locals().keys()))


def _loop_forever():
    '''Run the main loop forever
    '''
    global monitor, stepsize
    while True:
        # measure the time to correct for the slip
        start = time.time()

        monitor.loop()
        _loop_once()

        elapsed = time.time() - start
        naptime = stepsize - elapsed
        if naptime > 0:
            # this approximates the real time streaming speed
            time.sleep(naptime)


def _stop():
    '''Stop and clean up on SystemExit, KeyboardInterrupt
    '''
    sys.exit()


if __name__ == '__main__':
    _setup()
    _start()
    try:
        _loop_forever()
    except (SystemExit, KeyboardInterrupt, RuntimeError):
        _stop()
