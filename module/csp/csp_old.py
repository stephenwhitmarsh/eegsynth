#!/usr/bin/env python

# Playback plays back raw data from file to the FieldTrip buffer
#
# This software is part of the EEGsynth project, see <https://github.com/eegsynth/eegsynth>.
#
# Copyright (C) 2017-2020 EEGsynth project
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


# Uses: https://github.com/spolsley/common-spatial-patterns/blob/master/CSP.py

import configparser
import argparse
import numpy as np
import os
import redis
import sys
import time
import wave
import struct
import glob
import scipy.linalg as la

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
import FieldTrip
import EDF


def _setup():
    '''Initialize the module
    This adds a set of global variables
    '''
    global parser, args, config, r, response, patch

    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--inifile', default=os.path.join(path, name + '.ini'), help='name of the configuration file')
    args = parser.parse_args()

    config = configparser.ConfigParser(inline_comment_prefixes=('#', ';'))
    config.read(args.inifile)

    try:
        r = redis.StrictRedis(host=config.get('redis', 'hostname'), port=config.getint('redis', 'port'), db=0, charset='utf-8', decode_responses=True)
        response = r.client_list()
    except redis.ConnectionError:
        raise RuntimeError('cannot connect to Redis server')

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
    global monitor, filename, fileformat, ext, ft_host, ft_port, ft_output, H, MININT8, MAXINT8, MININT16, MAXINT16, MININT32, MAXINT32, f, chanindx, labels, A
    global data_A, filepath_A
    global data_B, filepath_B

    # this can be used to show parameters that have changed
    monitor = EEGsynth.monitor(name=name, debug=patch.getint('general', 'debug'))

    # get the options from the configuration file
    filepath_A = patch.getstring('data', 'conditionA')
    filepath_B = patch.getstring('data', 'conditionB')
    fileformat = patch.getstring('data', 'format')

    if fileformat is None:
        # determine the file format from the file name
        name, ext = os.path.splitext(filepath_A)
        fileformat = ext[1:]

    monitor.info('Reading data from ' + filepath_A)

    try:
        ft_host = patch.getstring('fieldtrip', 'hostname')
        ft_port = patch.getint('fieldtrip', 'port')
        monitor.success('Trying to connect to buffer on %s:%i ...' % (ft_host, ft_port))
        ft_output = FieldTrip.Client()
        ft_output.connect(ft_host, ft_port)
        monitor.success('Connected to FieldTrip buffer')
    except:
        raise RuntimeError('cannot connect to FieldTrip buffer')

    H = FieldTrip.Header()

    MININT8 = -np.power(2., 7)
    MAXINT8 = np.power(2., 7) - 1
    MININT16 = -np.power(2., 15)
    MAXINT16 = np.power(2., 15) - 1
    MININT32 = -np.power(2., 31)
    MAXINT32 = np.power(2., 31) - 1

    # there should not be any local variables in this function, they should all be global
    if len(locals()):
        print('LOCALS: ' + ', '.join(locals().keys()))


def _loop_once():
    '''Run the main loop once
    This uses the global variables from setup and start, and adds a set of global variables
    '''
    global parser, args, config, r, response, patch
    global monitor, H, A
    global D, stepsize
    global data_A, filepath_A
    global data_B, filepath_B

    if fileformat == 'edf':

        for filenr, filename in enumerate(glob.glob(filepath_A)):
            with open(filename, 'r') as f:
                monitor.info('Condition A: adding file ' + filename)
                f = EDF.EDFReader()
                f.open(filename)
                for chanindx in range(f.getNSignals()):
                    if f.getSignalFreqs()[chanindx] != f.getSignalFreqs()[0]:
                        raise AssertionError('unequal SignalFreqs')
                    if f.getNSamples()[chanindx] != f.getNSamples()[0]:
                        raise AssertionError('unequal NSamples')

                H.nChannels = len(f.getSignalFreqs())
                H.fSample = f.getSignalFreqs()[0]
                H.nSamples = f.getNSamples()[0]
                H.nEvents = 0
                H.dataType = FieldTrip.DATATYPE_FLOAT32

                # the channel labels will be written to the buffer
                labels = f.getSignalTextLabels()

                # read all the data from the file
                temp_A = np.ndarray(shape=(H.nSamples, H.nChannels), dtype=np.float32)
                for chanindx in range(H.nChannels):
                    monitor.debug('reading channel ' + str(chanindx))
                    temp_A[:, chanindx] = f.readSignal(chanindx)
                f.close()

                # concatinate data from files
                if filenr > 0:
                    data_A = np.concatenate((data_A, temp_A))
                else:
                    data_A = temp_A

        for filenr, filename in enumerate(glob.glob(filepath_B)):
            with open(filename, 'r') as f:
                monitor.info('Condition B: adding file ' + filename)
                f = EDF.EDFReader()
                f.open(filename)
                for chanindx in range(f.getNSignals()):
                    if f.getSignalFreqs()[chanindx] != f.getSignalFreqs()[0]:
                        raise AssertionError('unequal SignalFreqs')
                    if f.getNSamples()[chanindx] != f.getNSamples()[0]:
                        raise AssertionError('unequal NSamples')

                H.nChannels = len(f.getSignalFreqs())
                H.fSample = f.getSignalFreqs()[0]
                H.nSamples = f.getNSamples()[0]
                H.nEvents = 0
                H.dataType = FieldTrip.DATATYPE_FLOAT32

                # the channel labels will be written to the buffer
                labels = f.getSignalTextLabels()

                # read all the data from the file
                temp_B = np.ndarray(shape=(H.nSamples, H.nChannels), dtype=np.float32)
                for chanindx in range(H.nChannels):
                    monitor.debug('reading channel ' + str(chanindx))
                    temp_B[:, chanindx] = f.readSignal(chanindx)
                f.close()

                # concatinate data from files
                if filenr > 0:
                    data_B = np.concatenate((data_B, temp_B))
                else:
                    data_B = temp_B

    else:
        raise NotImplementedError('unsupported file format')

    if data_A.shape[0] > data_B.shape[0]:
        monitor.info('Condition A has %d more samples that Condition B! Trimming Condition B data to size.' % (data_A.shape[0] - data_B.shape[0]))
        data_A = data_A[0:data_B.shape[0], :]
    if data_A.shape[0] < data_B.shape[0]:
        monitor.info('Condition A has %d less samples that Condition B! Trimming Condition B data to size.' % (data_B.shape[0] - data_A.shape[0]))
        data_B = data_B[0:data_A.shape[0], :]

    print(data_A.shape)
    print(data_B.shape)
    type(data_A)

    filters = CSP(data_A, data_B)
    print(filters)

    monitor.debug('nChannels = ' + str(H.nChannels))
    monitor.debug('nSamples = ' + str(H.nSamples))
    monitor.debug('fSample = ' + str(H.fSample))
    monitor.debug('labels = ' + str(labels))

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

def CSP(*tasks):
	if len(tasks) < 2:
		print("Must have at least 2 tasks for filtering.")
		return (None,) * len(tasks)
	else:
		filters = ()
		# CSP algorithm
		# For each task x, find the mean variances Rx and not_Rx, which will be used to compute spatial filter SFx
		iterator = range(0,len(tasks))
		for x in iterator:
			# Find Rx
			Rx = covarianceMatrix(tasks[x][0])
			for t in range(1,len(tasks[x])):
				Rx += covarianceMatrix(tasks[x][t])
			Rx = Rx / len(tasks[x])

			# Find not_Rx
			count = 0
			not_Rx = Rx * 0
			for not_x in [element for element in iterator if element != x]:
				for t in range(0,len(tasks[not_x])):
					not_Rx += covarianceMatrix(tasks[not_x][t])
					count += 1
			not_Rx = not_Rx / count

			# Find the spatial filter SFx
			SFx = spatialFilter(Rx,not_Rx)
			filters += (SFx,)

			# Special case: only two tasks, no need to compute any more mean variances
			if len(tasks) == 2:
				filters += (spatialFilter(not_Rx,Rx),)
				break
		return filters

# covarianceMatrix takes a matrix A and returns the covariance matrix, scaled by the variance
def covarianceMatrix(A):
    print(A.shape)
    Ca = np.dot(A,np.transpose(A))/np.trace(np.dot(A,np.transpose(A)))
    return Ca

# spatialFilter returns the spatial filter SFa for mean covariance matrices Ra and Rb
def spatialFilter(Ra,Rb):
	R = Ra + Rb
	E,U = la.eig(R)

	# CSP requires the eigenvalues E and eigenvector U be sorted in descending order
	ord = np.argsort(E)
	ord = ord[::-1] # argsort gives ascending order, flip to get descending
	E = E[ord]
	U = U[:,ord]

	# Find the whitening transformation matrix
	P = np.dot(np.sqrt(la.inv(np.diag(E))),np.transpose(U))

	# The mean covariance matrices may now be transformed
	Sa = np.dot(P,np.dot(Ra,np.transpose(P)))
	Sb = np.dot(P,np.dot(Rb,np.transpose(P)))

	# Find and sort the generalized eigenvalues and eigenvector
	E1,U1 = la.eig(Sa,Sb)
	ord1 = np.argsort(E1)
	ord1 = ord1[::-1]
	E1 = E1[ord1]
	U1 = U1[:,ord1]

	# The projection matrix (the spatial filter) may now be obtained
	SFa = np.dot(np.transpose(U1),P)
	return SFa.astype(np.float32)

if __name__ == '__main__':
    _setup()
    _start()
    try:
        _loop_forever()
    except (SystemExit, KeyboardInterrupt, RuntimeError):
        _stop()
