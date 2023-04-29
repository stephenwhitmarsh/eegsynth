"""
FieldTrip buffer (V1) client and server in pure Python

(C) 2010      S. Klanke
(C) 2010-2022 R. Oostenveld

"""

# We need socket, struct, and numpy
import socket
import struct
import numpy
import unicodedata

# We need these for the server
import time
import selectors
import types
import struct
import RingBuffer

##########################################################################################
# general definitions
##########################################################################################

VERSION = 1

PUT_HDR            = 0x0101
PUT_DAT            = 0x0102
PUT_EVT            = 0x0103
PUT_OK             = 0x0104
PUT_ERR            = 0x0105
GET_HDR            = 0x0201
GET_DAT            = 0x0202
GET_EVT            = 0x0203
GET_OK             = 0x0204
GET_ERR            = 0x0205
FLUSH_HDR          = 0x0301
FLUSH_DAT          = 0x0302
FLUSH_EVT          = 0x0303
FLUSH_OK           = 0x0304
FLUSH_ERR          = 0x0305
WAIT_DAT           = 0x0402
WAIT_OK            = 0x0404
WAIT_ERR           = 0x0405
PUT_HDR_NORESPONSE = 0x0501
PUT_DAT_NORESPONSE = 0x0502
PUT_EVT_NORESPONSE = 0x0503

DATATYPE_CHAR    = 0
DATATYPE_UINT8   = 1
DATATYPE_UINT16  = 2
DATATYPE_UINT32  = 3
DATATYPE_UINT64  = 4
DATATYPE_INT8    = 5
DATATYPE_INT16   = 6
DATATYPE_INT32   = 7
DATATYPE_INT64   = 8
DATATYPE_FLOAT32 = 9
DATATYPE_FLOAT64 = 10
DATATYPE_UNKNOWN = 0xFFFFFFFF

CHUNK_UNSPECIFIED        = 0
CHUNK_CHANNEL_NAMES      = 1
CHUNK_CHANNEL_FLAGS      = 2
CHUNK_RESOLUTIONS        = 3
CHUNK_ASCII_KEYVAL       = 4
CHUNK_NIFTI1             = 5
CHUNK_SIEMENS_AP         = 6
CHUNK_CTF_RES4           = 7
CHUNK_NEUROMAG_FIF       = 8
CHUNK_NEUROMAG_ISOTRAK   = 9
CHUNK_NEUROMAG_HPIRESULT = 10

# List for converting FieldTrip datatypes to Numpy datatypes
numpyType = ['int8', 'uint8', 'uint16', 'uint32', 'uint64',
             'int8', 'int16', 'int32', 'int64', 'float32', 'float64']
# Corresponding word sizes
wordSize = [1, 1, 2, 4, 8, 1, 2, 4, 8, 4, 8]
# FieldTrip data type as indexed by numpy dtype.num
# this goes  0 => nothing, 1..4 => int8, uint8, int16, uint16, 7..10 =>
# int32, uint32, int64, uint64  11..12 => float32, float64
dataType = [-1, 5, 1, 6, 2, -1, -1, 7, 3, 8, 4, 9, 10]


def serialize(A):
    """
    Returns FieldTrip data type and string representation of the given
    object, if possible.
    """
    if isinstance(A, str):
        return (0, A)

    if isinstance(A, numpy.ndarray):
        dt = A.dtype
        if not(dt.isnative) or dt.num < 1 or dt.num >= len(dataType):
            return (DATATYPE_UNKNOWN, None)

        ft = dataType[dt.num]
        if ft == -1:
            return (DATATYPE_UNKNOWN, None)

        if A.flags['C_CONTIGUOUS']:
            # great, just use the array's buffer interface
            return (ft, A.tostring())

        # otherwise, we need a copy to C order
        AC = A.copy('C')
        return (ft, AC.tostring())

    if isinstance(A, int):
        return (DATATYPE_INT32, struct.pack('i', A))

    if isinstance(A, float):
        return (DATATYPE_FLOAT64, struct.pack('d', A))

    return (DATATYPE_UNKNOWN, None)


class Header:
    """Class for storing header information."""

    def __init__(self):
        self.nChannels = 0
        self.nSamples = 0
        self.nEvents = 0
        self.fSample = 0.0
        self.dataType = 0
        self.chunks = {}
        self.labels = []

    def __str__(self):
        return ('Channels.: %i\nSamples..: %i\nEvents...: %i\nSampFreq.: '
                '%f\nDataType.: %s\n'
                % (self.nChannels, self.nSamples, self.nEvents,
                   self.fSample, numpyType[self.dataType]))


class Chunk:
    """Class for storing additional chunks with header information."""

    def __init__(self):
        self.type = 0
        self.size = 0
        self.buf = ''


class Event:
    """Class for storing events."""

    def __init__(self, S=None):
        if S is None:
            self.type = ''
            self.value = ''
            self.sample = 0
            self.offset = 0
            self.duration = 0
        else:
            self.deserialize(S)

    def __str__(self):
        return ('Type.....: %s\nValue....: %s\nSample...: %i\nOffset...: '
                '%i\nDuration.: %i\n' % (str(self.type), str(self.value),
                                         self.sample, self.offset,
                                         self.duration))

    def deserialize(self, buf):
        bufsize = len(buf)
        if bufsize < 32:
            return 0

        (type_type, type_numel, value_type, value_numel, sample,
         offset, duration, bsiz) = struct.unpack('IIIIIiiI', buf[0:32])

        self.sample = sample
        self.offset = offset
        self.duration = duration

        st = type_numel * wordSize[type_type]
        sv = value_numel * wordSize[value_type]

        if bsiz + 32 > bufsize or st + sv > bsiz:
             IOError(
                'Invalid event definition -- does not fit in given buffer')

        raw_type = buf[32:32 + st]
        raw_value = buf[32 + st:32 + st + sv]

        if type_type == 0:
            self.type = raw_type
        else:
            self.type = numpy.ndarray(
                (type_numel), dtype=numpyType[type_type], buffer=raw_type)

        if value_type == 0:
            self.value = raw_value
        else:
            self.value = numpy.ndarray(
                (value_numel), dtype=numpyType[value_type], buffer=raw_value)

        return bsiz + 32

    def serialize(self):
        """
        Returns the contents of this event as a string, ready to
        send over the network, or None in case of conversion problems.
        """
        type_type, type_buf = serialize(self.type)
        if type_type == DATATYPE_UNKNOWN:
            return None
        type_size = len(type_buf)
        type_numel = type_size / wordSize[type_type]

        value_type, value_buf = serialize(self.value)
        if value_type == DATATYPE_UNKNOWN:
            return None
        value_size = len(value_buf)
        value_numel = value_size / wordSize[value_type]

        bufsize = type_size + value_size

        S = struct.pack('IIIIIiiI', type_type, type_numel, value_type,
                        value_numel, int(self.sample), int(self.offset),
                        int(self.duration), bufsize)
        return S + type_buf + value_buf


##########################################################################################
# Class for managing a client connection
##########################################################################################


class Client:
    """Class for managing a client connection to a FieldTrip buffer server."""

    def __init__(self):
        self.isConnected = False
        self.sock = []

    def connect(self, hostname, port=1972):
        """
        connect(hostname [, port]) -- make a connection, default port is 1972.
        """

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((hostname, port))
        self.sock.setblocking(True)
        self.isConnected = True

    def disconnect(self):
        """disconnect() -- close a connection."""

        if self.isConnected:
            self.sock.close()
            self.sock = []
            self.isConnected = False

    def sendRaw(self, request):
        """Send all bytes of the string 'request' out to socket."""

        if not(self.isConnected):
            raise IOError('Not connected to FieldTrip buffer')

        N = len(request)
        nw = self.sock.send(request)
        while nw < N:
            nw += self.sock.send(request[nw:])

    def sendRequest(self, command, payload=None):
        if payload is None:
            request = struct.pack('HHI', VERSION, command, 0)
        else:
            request = struct.pack(
                'HHI', VERSION, command, len(payload)) + payload
        self.sendRaw(request)

    def receiveResponse(self, minBytes=0):
        """
        Receive response from server on socket 's' and return it as
        (status,bufsize,payload).
        """

        resp_hdr = self.sock.recv(8)
        while len(resp_hdr) < 8:
            resp_hdr += self.sock.recv(8 - len(resp_hdr))

        (version, command, bufsize) = struct.unpack('HHI', resp_hdr)

        if version != VERSION:
            self.disconnect()
            raise IOError('Bad response from buffer server - disconnecting')

        if bufsize > 0:
            payload = self.sock.recv(bufsize)
            while len(payload) < bufsize:
                payload += self.sock.recv(bufsize - len(payload))
        else:
            payload = None
        return (command, bufsize, payload)

    def getHeader(self):
        """
        getHeader() -- grabs header information from the buffer an returns
        it as a Header object.
        """

        self.sendRequest(GET_HDR)
        (status, bufsize, payload) = self.receiveResponse()

        if status == GET_ERR:
            return None

        if status != GET_OK:
            self.disconnect()
            raise IOError('Bad response from buffer server - disconnecting')

        if bufsize < 24:
            self.disconnect()
            raise IOError('Invalid HEADER packet received (too few bytes) - '
                          'disconnecting')

        (nchans, nsamp, nevt, fsamp, dtype, bfsiz) = struct.unpack('IIIfII', payload[0:24])

        H = Header()
        H.nChannels = nchans
        H.nSamples = nsamp
        H.nEvents = nevt
        H.fSample = fsamp
        H.dataType = dtype

        if bfsiz > 0:
            offset = 24
            while offset + 8 < bufsize:
                (chunk_type, chunk_len) = struct.unpack('II', payload[offset:offset + 8])
                offset += 8
                if offset + chunk_len > bufsize:
                    break
                H.chunks[chunk_type] = payload[offset:offset + chunk_len]
                offset += chunk_len

            if CHUNK_CHANNEL_NAMES in H.chunks:
                L = H.chunks[CHUNK_CHANNEL_NAMES].split(b'\0')
                numLab = len(L)
                if numLab >= H.nChannels:
                    H.labels = [x.decode('utf-8') for x in L[0:H.nChannels]]

        return H

    def putHeader(self, nChannels, fSample, dataType, labels=None, chunks=None, reponse=True):
        haveLabels = False
        extras = b''

        if (type(labels)==list) and (len(labels)==0):
            labels=None

        if not(labels is None):
            serLabels = b''
            for n in range(0, nChannels):
                # ensure that labels are ascii strings, not unicode
                serLabels += labels[n].encode('ascii', 'ignore') + b'\0'
            try:
                pass
            except:
                raise ValueError('Channels names (labels), if given, must be a list of N=numChannels strings')

            extras = struct.pack('II', CHUNK_CHANNEL_NAMES, len(serLabels)) + serLabels
            haveLabels = True

        if not(chunks is None):
            for chunk_type, chunk_data in chunks:
                if haveLabels and chunk_type == CHUNK_CHANNEL_NAMES:
                    # ignore channel names chunk in case we got labels
                    continue
                extras += struct.pack('II', chunk_type,
                                      len(chunk_data)) + chunk_data

        sizeChunks = len(extras)

        if reponse:
            command = PUT_HDR
        else:
            command = PUT_HDR_NORESPONSE

        hdef = struct.pack('IIIfII', nChannels, 0, 0,
                           fSample, dataType, sizeChunks)
        request = struct.pack('HHI', VERSION, command,
                              sizeChunks + len(hdef)) + hdef + extras
        self.sendRaw(request)

        if reponse:
            (status, bufsize, resp_buf) = self.receiveResponse()
            if status != PUT_OK:
                raise IOError('Header could not be written')

    def getData(self, index=None):
        """
        getData([indices]) -- retrieve data samples and return them as a
        Numpy array, samples in rows(!). The 'indices' argument is optional,
        and if given, must be a tuple or list with inclusive, zero-based
        start/end indices.
        """

        if index is None:
            request = struct.pack('HHI', VERSION, GET_DAT, 0)
        else:
            indS = int(index[0])
            indE = int(index[1])
            request = struct.pack('HHIII', VERSION, GET_DAT, 8, indS, indE)
        self.sendRaw(request)

        (status, bufsize, payload) = self.receiveResponse()
        if status == GET_ERR:
            return None

        if status != GET_OK:
            self.disconnect()
            raise IOError('Bad response from buffer server - disconnecting')

        if bufsize < 16:
            self.disconnect()
            raise IOError('Invalid DATA packet received (too few bytes)')

        (nchans, nsamp, datype, bfsiz) = struct.unpack('IIII', payload[0:16])

        if bfsiz < bufsize - 16 or datype >= len(numpyType):
            raise IOError('Invalid DATA packet received')

        raw = payload[16:bfsiz + 16]
        D = numpy.ndarray((nsamp, nchans), dtype=numpyType[datype], buffer=raw)

        return D

    def getEvents(self, index=None):
        """
        getEvents([indices]) -- retrieve events and return them as a list
        of Event objects. The 'indices' argument is optional, and if given,
        must be a tuple or list with inclusive, zero-based start/end indices.
        The 'type' and 'value' fields of the event will be converted to strings
        or Numpy arrays.
        """

        if index is None:
            request = struct.pack('HHI', VERSION, GET_EVT, 0)
        else:
            indS = int(index[0])
            indE = int(index[1])
            request = struct.pack('HHIII', VERSION, GET_EVT, 8, indS, indE)
        self.sendRaw(request)

        (status, bufsize, resp_buf) = self.receiveResponse()
        if status == GET_ERR:
            return []

        if status != GET_OK:
            self.disconnect()
            raise IOError('Bad response from buffer server - disconnecting')

        offset = 0
        E = []
        while 1:
            e = Event()
            nextOffset = e.deserialize(resp_buf[offset:])
            if nextOffset == 0:
                break
            E.append(e)
            offset = offset + nextOffset

        return E

    def putEvents(self, E, reponse=True):
        """
        putEvents(E) -- writes a single or multiple events, depending on
        whether an 'Event' object, or a list of 'Event' objects is
        given as an argument.
        """

        if isinstance(E, Event):
            buf = E.serialize()
        else:
            buf = ''
            num = 0
            for e in E:
                if not(isinstance(e, Event)):
                    raise 'Element %i in given list is not an Event' % num
                buf = buf + e.serialize()
                num = num + 1

        if reponse:
            command = PUT_EVT
        else:
            command = PUT_EVT_NORESPONSE

        self.sendRequest(command, buf)

        if reponse:
            (status, bufsize, resp_buf) = self.receiveResponse()
            if status != PUT_OK:
                raise IOError('Events could not be written.')

    def putData(self, D, response=True):
        """
        putData(D) -- writes samples that must be given as a NUMPY array,
        samples x channels. The type of the samples (D) and the number of
        channels must match the corresponding quantities in the FieldTrip
        buffer.
        """

        if not(isinstance(D, numpy.ndarray)) or len(D.shape) != 2:
            raise ValueError(
                'Data must be given as a NUMPY array (samples x channels)')

        nSamp = D.shape[0]
        nChan = D.shape[1]

        (dataType, dataBuf) = serialize(D)

        dataBufSize = len(dataBuf)

        if response:
            command = PUT_DAT
        else:
            command = PUT_DAT_NORESPONSE

        request = struct.pack('HHI', VERSION, command, 16 + dataBufSize)
        dataDef = struct.pack('IIII', nChan, nSamp, dataType, dataBufSize)
        self.sendRaw(request + dataDef + dataBuf)

        if response:
            (status, bufsize, resp_buf) = self.receiveResponse()
            if status != PUT_OK:
                raise IOError('Samples could not be written.')

    def poll(self):
        request = struct.pack('HHIIII', VERSION, WAIT_DAT, 12, 0, 0, 0)
        self.sendRaw(request)

        (status, bufsize, resp_buf) = self.receiveResponse()

        if status != WAIT_OK or bufsize < 8:
            raise IOError('Polling failed.')

        return struct.unpack('II', resp_buf[0:8])

    def wait(self, nsamples, nevents, timeout):
        request = struct.pack('HHIIII', VERSION, WAIT_DAT, 12, int(nsamples), int(nevents), int(timeout))
        self.sendRaw(request)

        (status, bufsize, resp_buf) = self.receiveResponse()

        if status != WAIT_OK or bufsize < 8:
            raise IOError('Wait request failed.')

        return struct.unpack('II', resp_buf[0:8])


##########################################################################################
# Class for a FieldTrip buffer server
##########################################################################################

class Server():
    """Class for a FieldTrip buffer server."""

    def __init__(self):
        self.isConnected = False
        self.sel = None
        self.H = None
        self.D = None
        self.E = None
        self.length = 600       # in seconds, ring buffer length
        self.timeout = 1        # in seconds, this should be 0 if you want to loop over multiple servers
        self.keepalive = True   # whether to raise errors or keep running


    def connect(self, hostname='localhost', port=1972):
        if self.isConnected:
            if self.keepalive:
                print('Already connected.')
                return
            else:
                raise RuntimeError('Already connected.')

        lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        lsock.bind((hostname, port))
        lsock.listen()
        print(f'Listening on {(hostname, port)}')
        lsock.setblocking(False)
        self.sel = selectors.DefaultSelector()
        self.sel.register(lsock, selectors.EVENT_READ, data = None)
        self.isConnected = True


    def disconnect(self):
        if not self.isConnected:
            if self.keepalive:
                print('Not connected.')
                return
            else:
                raise RuntimeError('Not connected.')

        self.sel.close()
        self.sel = None
        self.isConnected = False


    def accept_wrapper(self, sock):
        if not self.isConnected:
            if self.keepalive:
                print('Already connected.')
                return
            else:
                raise RuntimeError('Not connected.')

        conn, addr = sock.accept()  # Should be ready to read
        print(f'Accepted connection from {addr}')
        conn.setblocking(False)
        data = types.SimpleNamespace(addr=addr, inb=b'', outb=b'')
        events = selectors.EVENT_READ
        self.sel.register(conn, events, data=data)


    def service_request(self, key, mask):
        if not self.isConnected:
            if self.keepalive:
                print('Not connected.')
                return
            else:
                raise RuntimeError('Not connected.')

        sock = key.fileobj
        data = key.data

        if mask & selectors.EVENT_READ:
            try:
                message = sock.recv(8)
            except:
                if self.keepalive:
                    print('Cannot read message.')
                    message = [] # this will be handled further down
                else:
                    raise IOError('Cannot read message.')

            if message and len(message)==8:
                (version, command, bufsize) = struct.unpack('HHI', message[0:8])
                if version != VERSION:
                    if self.keepalive:
                        print('Incompatible version.')
                        return
                    else:
                        raise RuntimeError('Incompatible version.')

                try:
                    payload = sock.recv(bufsize)
                except:
                    if self.keepalive:
                        print('Cannot read payload.')
                        return
                    else:
                        raise IOError('Cannot read payload.')

                if command == PUT_HDR:
                    self.H = Header()
                    self.D = None  # this flushes the data
                    self.E = None  # this flushes the events
                    (self.H.nChannels, self.H.nSamples, self.H.nEvents, self.H.fSample, self.H.dataType, bufsize) = struct.unpack('IIIfII', payload[0:24])
                    response = struct.pack('HHI', VERSION, PUT_OK, 0)
                    sock.send(response)

                elif command == PUT_DAT:
                    if self.H != None:
                        (nchans, nsamples, data_type, bufsize) = struct.unpack('IIII', payload[0:16])
                        if nchans != self.H.nChannels:
                            raise RuntimeError('Incorrect number of channels')
                        if data_type != self.H.dataType:
                            raise RuntimeError('Incorrect data type')
                        if self.D == None:
                            nbytes = int(self.H.nChannels * self.H.fSample * self.length * wordSize[self.H.dataType])
                            self.D = RingBuffer.RingBuffer(nbytes)
                            print('Initialized ring buffer with %d bytes' % nbytes)
                        self.D.append(payload[16:])
                        self.H.nSamples += nsamples
                        response = struct.pack('HHI', VERSION, PUT_OK, 0)
                    else:
                        response = struct.pack('HHI', VERSION, PUT_ERR, 0)
                    # send the response to PUT_DAT
                    sock.send(response)

                elif command == PUT_EVT:
                    print('PUT_EVT not implemented')
                    response = struct.pack('HHI', VERSION, PUT_ERR, 0)
                    sock.send(response)

                elif command == GET_HDR:
                    if self.H != None:
                        response = struct.pack('HHI', VERSION, GET_OK, 24)
                        response += struct.pack('IIIfII', self.H.nChannels, self.H.nSamples, self.H.nEvents, self.H.fSample, self.H.dataType, 0)
                    else:
                        response = struct.pack('HHI', VERSION, GET_ERR, 0)
                    # send the response to GET_HDR
                    sock.send(response)

                elif command == GET_DAT:
                    if self.H != None and self.D != None and bufsize == 8:
                        (begsample, endsample) = struct.unpack('II', payload[0:8]) # this uses inclusive, zero-based start/end indices
                        begbyte = int(begsample * self.H.nChannels * wordSize[self.H.dataType])
                        endbyte = int((endsample+1) * self.H.nChannels * wordSize[self.H.dataType])
                        nbytes = endbyte - begbyte
                        try:
                            response = struct.pack('HHI', VERSION, GET_OK, nbytes+16)
                            response += struct.pack('IIII', self.H.nChannels, endsample-begsample+1, self.H.dataType, nbytes)
                            response += self.D.read(begbyte, endbyte) # this uses exclusive, zer0-based start/end indices
                        except Exception as e:
                            response = struct.pack('HHI', VERSION, GET_ERR, 0)
                    else:
                        response = struct.pack('HHI', VERSION, GET_ERR, 0)
                    # send the response to GET_DAT
                    sock.send(response)

                elif command == GET_EVT:
                    print('GET_EVT not implemented')
                    response = struct.pack('HHI', VERSION, GET_ERR, 0)
                    sock.send(response)

                elif command == FLUSH_HDR:
                    if self.H != None:
                        self.H = None
                        self.D = None  # this also flushes the data
                        self.E = None  # this also flushes the events
                        response = struct.pack('HHI', VERSION, FLUSH_OK, 0)
                    else:
                        response = struct.pack('HHI', VERSION, FLUSH_ERR, 0)
                    # send the response to FLUSH_HDR
                    sock.send(response)

                elif command == FLUSH_DAT:
                    if self.D != None:
                        self.D = None
                        response = struct.pack('HHI', VERSION, FLUSH_OK, 0)
                    else:
                        response = struct.pack('HHI', VERSION, FLUSH_ERR, 0)
                    # send the response to FLUSH_DAT
                    sock.send(response)

                elif command == FLUSH_EVT:
                    if E != None:
                        E = None
                        response = struct.pack('HHI', VERSION, FLUSH_OK, 0)
                    else:
                        response = struct.pack('HHI', VERSION, FLUSH_ERR, 0)
                    # send the response to FLUSH_EVT
                    sock.send(response)

                elif command == WAIT_DAT:
                    if self.H != None and bufsize == 12:
                        (nsamples, nevents, timeout) = struct.unpack('III', payload[0:12])
                        timeout /= 1000.0  # in seconds
                        start = time.time()
                        response = struct.pack('HHI', VERSION, WAIT_ERR, 0)
                        while time.time() < (start + timeout):
                            if self.H.nSamples >= nsamples or self.H.nEvents >= nevents:
                                response = struct.pack('HHI', VERSION, WAIT_OK, 8)
                                response += struct.pack('II', self.H.nSamples, self.H.nEvents)
                                break
                            else:
                                time.sleep(0.010)
                    else:
                        response = struct.pack('HHI', VERSION, WAIT_ERR, 0)
                    # send the response to WAIT_DAT
                    sock.send(response)

                else:
                    # unrecognized command
                    print('Command not implemented')
                    response = struct.pack('HHI', VERSION, 0, 0)
                    sock.send(response)

            else:
                print(f'Closing connection to {data.addr}')
                self.sel.unregister(sock)
                sock.close()


    def loop(self):
        if not self.isConnected:
            if self.keepalive:
                print('Not connected.')
                return
            else:
                raise RuntimeError('Not connected.')

        # the timeout is used to return control to the main loop once in a while
        events = self.sel.select(timeout = self.timeout)
        for key, mask in events:
            if key.data is None:
                self.accept_wrapper(key.fileobj)
            else:
                self.service_request(key, mask)
