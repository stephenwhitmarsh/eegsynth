from scipy.signal import butter, lfilter
import time
import pyqtgraph as pg
from pyqtgraph.Qt import QtGui, QtCore

def butter_bandpass(lowcut, highcut, fs, order=9):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype='band')
    return b, a


def butter_lowpass(lowcut, fs, order=9):
    nyq = 0.5 * fs
    low = lowcut / nyq
    b, a = butter(order, low, btype='lowpass')
    return b, a


def butter_highpass(highcut, fs, order=9):
    nyq = 0.5 * fs
    high = highcut / nyq
    b, a = butter(order, high, btype='highpass')
    return b, a


def butter_bandpass_filter(data, lowcut, highcut, fs, order=9):
    b, a = butter_bandpass(lowcut, highcut, fs, order=order)
    y = lfilter(b, a, data)
    return y


def butter_lowpass_filter(data, lowcut, fs, order=9):
    b, a = butter_lowpass(lowcut, fs, order=order)
    y = lfilter(b, a, data)
    return y


def butter_highpass_filter(data, highcut, fs, order=9):
    b, a = butter_highpass(highcut, fs, order=order)
    y = lfilter(b, a, data)
    return y


## start of code from script

class plotsignal_object():

    def __init__(self, patch, ft_input):
        self.patch = patch


        hdr_input = None
        start = time.time()
        while hdr_input is None:
            if patch.getint('general', 'debug') > 0:
                print "Waiting for data to arrive..."
            if (time.time() - start) > patch.getfloat('fieldtrip', 'timeout'):
                print "Error: timeout while waiting for data"
                raise SystemExit
            hdr_input = ft_input.getHeader()
            time.sleep(0.2)

        if patch.getint('general', 'debug') > 0:
            print "Data arrived"
        if patch.getint('general', 'debug') > 1:
            print hdr_input
            print hdr_input.labels

        # read variables from ini/redis
        chanarray = patch.getint('arguments', 'channels', multiple=True)
        chanarray = [chan - 1 for chan in chanarray] # since python using indexing from 0 instead of 1

        chan_nrs    = len(chanarray)
        window      = patch.getfloat('arguments', 'window')        # in seconds
        window      = int(round(window * hdr_input.fSample))       # in samples
        clipsize    = patch.getfloat('arguments', 'clipsize')      # in seconds
        clipsize    = int(round(clipsize * hdr_input.fSample))     # in samples
        stepsize    = patch.getfloat('arguments', 'stepsize')      # in seconds
        winx        = patch.getfloat('display', 'xpos')
        winy        = patch.getfloat('display', 'ypos')
        winwidth    = patch.getfloat('display', 'width')
        winheight   = patch.getfloat('display', 'height')
        lrate       = patch.getfloat('arguments', 'learning_rate')

        # lowpass, highpass and bandpass are optional, but mutually exclusive
        filtorder = 9
        if patch.hasitem('arguments', 'bandpass'):
            freqrange = patch.getfloat('arguments', 'bandpass', multiple=True)
        elif patch.hasitem('arguments', 'lowpass'):
            freqrange = patch.getfloat('arguments', 'lowpass')
            freqrange = [np.nan, freqrange]
        elif patch.hasitem('arguments', 'highpass'):
            freqrange = patch.getfloat('arguments', 'highpass')
            freqrange = [freqrange, np.nan]
        else:
            freqrange = [np.nan, np.nan]

        # initialize graphical window
        app = QtGui.QApplication([])

        win = pg.GraphicsWindow(title="EEGsynth plotsignal")
        win.setWindowTitle('EEGsynth plotsignal')
        win.setGeometry(winx, winy, winwidth, winheight)

        # Enable antialiasing for prettier plots
        pg.setConfigOptions(antialias=True)

        # Initialize variables
        timeplot = []
        curve    = []
        curvemax = []

        # Create panels for each channel
        for ichan in range(chan_nrs):
            channr = int(chanarray[ichan]) + 1

            timeplot.append(win.addPlot(title="%s%s" % ('Channel ', channr)))
            timeplot[ichan].setLabel('left', text='Amplitude')
            timeplot[ichan].setLabel('bottom', text='Time (s)')
            curve.append(timeplot[ichan].plot(pen='w'))
            win.nextRow()

            # initialize as list
            curvemax.append(0.0)

#        QtGui.QApplication.instance().exec_()

         ew.instance().exec_()

    def update():
        global curvemax, counter

        # get the last available data
        last_index = ft_input.getHeader().nSamples
        begsample = (last_index - window)  # the clipsize will be removed from both sides after filtering
        endsample = (last_index - 1)

        if debug > 0:
            print "reading from sample %d to %d" % (begsample, endsample)

        data = ft_input.getData([begsample, endsample])

        # detrend data before filtering to reduce edge artefacts and to center timecourse
        if patch.getint('arguments', 'detrend', default=1):
            data = detrend(data, axis=0)

        # apply the user-defined filtering
        if not np.isnan(freqrange[0]) and not np.isnan(freqrange[1]):
            data = butter_bandpass_filter(data.T, freqrange[0], freqrange[1], int(hdr_input.fSample), filtorder).T
        elif not np.isnan(freqrange[1]):
            data = butter_lowpass_filter(data.T, freqrange[1], int(hdr_input.fSample), filtorder).T
        elif not np.isnan(freqrange[0]):
            data = butter_highpass_filter(data.T, freqrange[0], int(hdr_input.fSample), filtorder).T

        # remove the filter padding
        if clipsize > 0:
            data = data[clipsize:-clipsize]

        for ichan in range(chan_nrs):
            channr = int(chanarray[ichan])

            # time axis
            timeaxis = np.linspace(-window / hdr_input.fSample, 0, len(data))

            # update timecourses
            curve[ichan].setData(timeaxis, data[:, channr])

            # adapt the vertical scale to the running mean of max
            curvemax[ichan] = curvemax[ichan] * (1 - lrate) + lrate * max(abs(data[:, channr]))
            timeplot[ichan].setYRange(-curvemax[ichan], curvemax[ichan])


    # keyboard interrupt handling
    def sigint_handler(*args):
        QtGui.QApplication.quit()


        signal.signal(signal.SIGINT, sigint_handler)

        # Set timer for update
        timer = QtCore.QTimer()
        timer.timeout.connect(update)
        timer.setInterval(10)                       # timeout in milliseconds
        timer.start(int(round(stepsize * 1000)))    # in milliseconds

        # Wait until there is enough data
        begsample = -1
        while begsample < 0:
            hdr_input = ft_input.getHeader()
            begsample = int(hdr_input.nSamples - window)

    def start(self):
        QtGui.QApplication.instance().exec_()


if __name__ == "__main__":

    main()