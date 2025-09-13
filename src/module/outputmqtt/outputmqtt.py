#!/usr/bin/env python

# This module translates Redis controls to MQTT messages.
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
import string
import sys
import threading
import time
import paho.mqtt.client as mqtt

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


class TriggerThread(threading.Thread):
    def __init__(self, redischannel, name, mqtttopic):
        threading.Thread.__init__(self)
        self.redischannel = redischannel
        self.name = name
        self.mqtttopic = mqtttopic
        self.running = True

    def stop(self):
        self.running = False

    def run(self):
        pubsub = patch.pubsub()
        pubsub.subscribe('OUTPUTMQTT_UNBLOCK')  # this message unblocks the redis listen command
        pubsub.subscribe(self.redischannel)     # this message contains the value of interest
        while self.running:
            for item in pubsub.listen():
                if not self.running or not item['type'] == 'message':
                    break
                if item['channel'] == self.redischannel:
                    # map the Redis values to MQTT values
                    val = float(item['data'])
                    # the scale and offset options are channel specific
                    scale = patch.getfloat('scale', self.name, default=1)
                    offset = patch.getfloat('offset', self.name, default=0)
                    # apply the scale and offset
                    val = EEGsynth.rescale(val, slope=scale, offset=offset)

                    monitor.update(self.mqtttopic, val)
                    with lock:
                        client.publish(self.mqtttopic, payload=val, qos=0, retain=False)


# The callback for when the client receives a CONNACK response from the broker.
def on_connect(client, userdata, flags, rc):
    ("Connected with result code " + str(rc))
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe("$SYS/#")


# The callback for when a PUBLISH message is received from the broker.
def on_message(client, userdata, msg):
    if not msg.topic.startswith('$SYS'):
        monitor.info("MQTT received " + msg.topic + " " + str(msg.payload))


# The callback for when the broker disconnects.
def on_disconnect(client, userdata, rc):
    if rc != 0:
        monitor.info("MQTT disconnected")


def _setup():
    '''Initialize the module
    This adds a set of global variables
    '''
    global patch, name, path, monitor

    # configure and start the patch, this will parse the command-line arguments and the ini file
    patch = EEGsynth.patch(name=name, path=path)

    # there should not be any local variables in this function, they should all be global
    if len(locals()):
        print('LOCALS: ' + ', '.join(locals().keys()))


def _start():
    '''Start the module
    This uses the global variables from setup and adds a set of global variables
    '''
    global patch, name, path, monitor
    global list_input, list_output, list1, list2, list3, i, j, lock, trigger, key1, key2, key3, this, thread, client

    # this shows the splash screen and can be used to track parameters that have changed
    monitor = EEGsynth.monitor(name=name, patch=patch, debug=patch.getint('general', 'debug', default=1), target=patch.get('general', 'logging', default=None))

    # get the options from the configuration file

    # keys should be present in both the input and output section of the *.ini file
    list_input = patch.config.items('input')
    list_output = patch.config.items('output')

    list1 = []  # the key name that matches in the input and output section of the *.ini file
    list2 = []  # the key name in Redis
    list3 = []  # the key name in OSC
    for i in range(len(list_input)):
        for j in range(len(list_output)):
            if list_input[i][0] == list_output[j][0]:
                list1.append(list_input[i][0])  # short name in the ini file
                list2.append(list_input[i][1])  # redis channel
                list3.append(list_output[j][1])  # mqtt topic

    # this is to prevent two messages from being sent at the same time
    lock = threading.Lock()

    # each of the Redis messages is mapped onto a different MQTT topic
    trigger = []
    for key1, key2, key3 in zip(list1, list2, list3):
        this = TriggerThread(key2, key1, key3)
        trigger.append(this)
        monitor.debug(key1 + " trigger configured")

    # start the thread for each of the triggers
    for thread in trigger:
        thread.start()

    # make the connection with the MQTT broker
    try:
        client = mqtt.Client()
        client.connect(patch.get('mqtt', 'hostname'), patch.getint('mqtt', 'port'), patch.getint('mqtt', 'timeout'))
        client.on_connect = on_connect
        client.on_message = on_message
        client.on_disconnect = on_disconnect
    except:
        raise RuntimeError("Cannot connect to MQTT broker")

    # there should not be any local variables in this function, they should all be global
    if len(locals()):
        print('LOCALS: ' + ', '.join(locals().keys()))


def _loop_once():
    '''Run the main loop once
    '''
    pass


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
    global monitor, trigger, r
    monitor.success('Closing threads')
    for thread in trigger:
        thread.stop()
    patch.publish('OUTPUTMQTT_UNBLOCK', 1)
    for thread in trigger:
        thread.join()


if __name__ == '__main__':
    _setup()
    _start()
    try:
        _loop_forever()
    except (SystemExit, KeyboardInterrupt, RuntimeError):
        _stop()
    sys.exit()
