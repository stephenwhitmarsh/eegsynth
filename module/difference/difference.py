#!/usr/bin/env python

# This module records Redis messages (i.e. triggers) to a TSV file
#
# This software is part of the EEGsynth project, see <https://github.com/eegsynth/eegsynth>.
#
# Copyright (C) 2018-2019, Robert Oostenveld for the EEGsynth project, http://www.eegsynth.org
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
import datetime
import os
import redis
import sys
import time
import threading
import math

if hasattr(sys, 'frozen'):
    path = os.path.split(sys.executable)[0]
    file = os.path.split(sys.executable)[-1]
elif sys.argv[0] != '':
    path = os.path.split(sys.argv[0])[0]
    file = os.path.split(sys.argv[0])[-1]
else:
    path = os.path.abspath('')
    file = os.path.split(path)[-1] + '.py'

# eegsynth/lib contains shared modules
sys.path.insert(0, os.path.join(path,'../../lib'))
import EEGsynth
import EDF

parser = argparse.ArgumentParser()
parser.add_argument("-i", "--inifile", default=os.path.join(path, os.path.splitext(file)[0] + '.ini'), help="optional name of the configuration file")
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

# this can be used to show parameters that have changed
monitor = EEGsynth.monitor()

# get the options from the configuration file
debug        = patch.getint('general','debug')
delay        = patch.getfloat('general','delay')

# this is to prevent two triggers from being saved at the same time
lock = threading.Lock()

class TriggerThread(threading.Thread):
    def __init__(self, redischannel):
        threading.Thread.__init__(self)
        self.redischannel = redischannel
        self.running = True
    def stop(self):
        self.running = False
    def run(self):
        pubsub = r.pubsub()
        pubsub.subscribe('DIFFERENCE_UNBLOCK')  # this message unblocks the Redis listen command
        pubsub.subscribe(self.redischannel)        # this message triggers the event
        while self.running:

            for item in pubsub.listen():
                timestamp = datetime.datetime.now().isoformat()
                if not self.running or not item['type'] == 'message':
                    print("Could not track: %s" % (self.redischannel))
                    break
                if item['channel']==self.redischannel:
                    val = float(item['data'])
                    print("%s\t%s\t%s" % (self.redischannel, val, timestamp))

class monitor():
    """Class to monitor control values and print them to screen when they have changed. It also
    prints a boilerplate license upon startup.
    """

    def __init__(self):
        self.previous_value = {}
        self.loop_time = None

    def update(self, key, val, debug=True):
        if (key not in self.previous_value) or (self.previous_value[key]!=val):
            try:
                # the comparison returns false in case both are nan
                a = math.isnan(self.previous_value[key])
                b = math.isnan(val)
                if (a and b):
                    debug = False
            except:
                pass
            if debug:
                printkeyval(key, val)
            self.previous_value[key] = val
            return True
        else:
            return False

def printkeyval(key, val):
    if sys.version_info < (3,0):
        # this works in Python 2, but fails in Python 3
        isstring = isinstance(val, basestring)
    else:
        # this works in Python 3, but fails for unicode strings in Python 2
        isstring = isinstance(val, str)
    if val is None:
        print("%s = None" % (key))
    elif isinstance(val, list):
        print("%s = %s" % (key, str(val)))
    elif isstring:
        print("%s = %s" % (key, val))
    else:
        print("%s = %g" % (key, val))

# create the background threads that deal with the triggers
trigger = []
if debug>1:
    print("Setting up threads for each trigger")
for item in config.items('trigger'):
        trigger.append(TriggerThread(item[0]))
        if debug>1:
            print(item[0], 'OK')

# start the thread for each of the triggers
for thread in trigger:
    thread.start()

# assign the initial values
for item in config.items('trigger'):
    val = patch.getfloat('trigger', item[0])
    patch.setvalue(item[0], val, debug=(debug>0))
    monitor.update(item[0], val)

try:
    while True:
        time.sleep(patch.getfloat('general', 'delay'))


except KeyboardInterrupt:
    print('Closing threads')
    for thread in trigger:
        thread.stop()
    r.publish('DIFFERENCE_UNBLOCK', 1)
    for thread in trigger:
        thread.join()
    sys.exit()
