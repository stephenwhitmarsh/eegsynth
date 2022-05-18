#!/usr/bin/env python

# Delaytrigger sends a triggers after a certain delay
#
# This software is part of the EEGsynth project, see <https://github.com/eegsynth/eegsynth>.
#
# Copyright (C) 2022 EEGsynth project
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
import os
import redis
import sys
import time
import threading

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


class TriggerThread(threading.Thread):
    def __init__(self, input, delay, output, value):
        threading.Thread.__init__(self)
        self.redischannel = input
        self.delay = delay
        self.output = output
        self.value = value
        self.running = True
        self.timer = []

    def stop(self):
        # cancel all timers that are still running
        monitor.debug('flushing %d timers' % len(self.timer))
        for t in self.timer:
            t.cancel()
        self.timer = []
        self.running = False

    def run(self):
        global r, monitor, lock
        pubsub = r.pubsub()
        pubsub.subscribe('DELAYTRIGGER_UNBLOCK')   # this message unblocks the Redis listen command
        pubsub.subscribe(self.redischannel)        # this message triggers the event
        while self.running:
            for item in pubsub.listen():
                if not self.running or not item['type'] == 'message':
                    break
                if item['channel'] == self.redischannel:
                    # schedule the ouput trigger, it gets the specified value
                    monitor.debug('scheduling %s after %g seconds' % (self.output, self.delay))
                    if self.value==None:
                        # send the value of the incoming trigger itself
                        t = threading.Timer(self.delay, patch.setvalue, args=[self.output, item['data']])
                    else:
                        # send the value specified in the ini file
                        t = threading.Timer(self.delay, patch.setvalue, args=[self.output, self.value])
                    t.start()
                    self.timer.append(t)


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
    global monitor, prefix, item, val, input_name, input_variable, output_name, output_variable, lock, trigger, thread

    # this can be used to show parameters that have changed
    monitor = EEGsynth.monitor(name=name, debug=patch.getint('general', 'debug'))

    # get the options from the configuration file
    debug = patch.getint('general', 'debug')

    # create the background threads that deal with the input triggers
    trigger = []
    monitor.debug("Setting up threads")
    for item in config.items('input'):
        input = item[1]
        delay = patch.getfloat("delay", item[0])
        output = patch.getstring("output", item[0])
        value = patch.getfloat("value", item[0]) # when not specified this will return None
        monitor.info(input, '->', delay, '->', output)
        trigger.append(TriggerThread(input, delay, output, value))

    # start the thread for each of the triggers
    for thread in trigger:
        thread.start()

    # there should not be any local variables in this function, they should all be global
    if len(locals()):
        print("LOCALS: " + ", ".join(locals().keys()))


def _loop_once():
    '''Run the main loop once
    '''
    pass


def _loop_forever():
    '''Run the main loop forever
    '''
    while True:
        monitor.loop()
        time.sleep(patch.getfloat('general', 'delay'))


def _stop():
    '''Stop and clean up on SystemExit, KeyboardInterrupt
    '''
    global monitor, trigger, r
    monitor.success('Closing threads')
    for thread in trigger:
        thread.stop()
    r.publish('DELAYTRIGGER_UNBLOCK', 1)
    for thread in trigger:
        thread.join()
    sys.exit()


if __name__ == '__main__':
    _setup()
    _start()
    try:
        _loop_forever()
    except (SystemExit, KeyboardInterrupt, RuntimeError):
        _stop()
