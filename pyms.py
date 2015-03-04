"""
PyMS
By David Shipman, 2012

Provides a convenient interface for accessing Metastock databases
in python (with additional support for PremiumData).

Based on part ms2txt by themech
https://github.com/themech/ms2txt

GPL Licensed : Please read the enclosed license in COPYING

"""

import struct
import datetime
import os.path
from StringIO import StringIO


def reader(incoming_bytes):
    return lambda fh: fh.read(incoming_bytes)


def clampindex(idx, size):
    if (type(idx) == slice):
        raise Exception('slicing unsupported')
    if (idx < 0):
        idx = size + idx
    if ((idx > size - 1) | (idx < 0)):
        raise IndexError('index out of range')
    return idx


def fmsbin2ieee(bytes):
    """
    Convert an array of 4 bytes containing Microsoft Binary floating point
    number to IEEE floating point format (which is used by Python)
    """
    as_int = struct.unpack("i", bytes)
    if not as_int:
        return 0.0
    man = long(struct.unpack('H', bytes[2:])[0])
    if not man:
        return 0.0
    exp = (man & 0xff00) - 0x0200
    man = man & 0x7f | (man << 8) & 0x8000
    man |= exp >> 1

    bytes2 = bytes[:2]
    bytes2 += chr(man & 255)
    bytes2 += chr((man >> 8) & 255)
    return struct.unpack("f", bytes2)[0]


def float2date(date):
    """
    Metastock stores date as a float number.
    Here we convert it to a python datetime.date object.
    """
    date = int(date)
    year = 1900 + (date / 10000)
    month = (date % 10000) / 100
    day = date % 100
    return datetime.date(year, month, day)


def float2time(time):
    """
    Metastock stores date as a float number.
    Here we convert it to a python datetime.time object.
    """
    time = int(time)
    hour = time / 10000
    minute = (time % 10000) / 100
    return datetime.time(hour, minute)


def int2date(in_date):
    date = str(in_date)
    year = int(date[0:4])
    month = int(date[4:6])
    day = int(date[6:8])
    return datetime.date(year, month, day)


def c_uchar(x):
    return struct.unpack("B", x)[0]


def c_ushort(x):
    return struct.unpack("H", x)[0]


def c_uint(x):
    return struct.unpack("I", x)[0]


def ms_str(x):
    return x.strip('\x00 \t\nda')


def ms_em_date(x):
    return float2date(struct.unpack("f", x)[0])


def ms_xm_date(x):
    return int2date(struct.unpack("I", x)[0])


def ms_dat_date(x):
    return float2date(fmsbin2ieee(x))


def ms_binfloat(x):
    return fmsbin2ieee(x)


class RecordFormat(dict):
    """
    Mapping of field names to binary data
    Keys : field names
    Values : DataMap types
    len : record length in bytes
    """

    def __init__(self, length, records={}):
        self.length = length
        self.read = reader(length)
        dict.__init__(self, records)


class DataMap:
    """
        Class mapping a datum in a binary record to
        its eventual output.
        i : index slice containing the binary data
        f : function to convert into native python type
    """
    def __init__(self, start, length, f):
        self.start = start
        self.length = length
        self.i = slice(start, start + length)
        self.f = f


class MSIndexFileFormat:

    def __init__(self, header, record):
        self.header = header
        self.record = record

EMasterHeader = RecordFormat(192,
    {
        'record_count': DataMap(0, 2, c_ushort),
        'last_record': DataMap(2, 2, c_ushort)
    }
)

EMasterRecord = RecordFormat(192,
    {
        'filenum': DataMap(2, 1, c_uchar),
        'numfields': DataMap(6, 1, c_uchar),
        'symbol': DataMap(11, 14, ms_str),
        'name': DataMap(32, 16, ms_str),
        'first_date': DataMap(64, 4, ms_em_date),
        'last_date': DataMap(72, 4, ms_em_date)
    }
)

XMasterHeader = RecordFormat(150,
    {
        'record_count': DataMap(10, 2, c_ushort),
    }
)

XMasterRecord = RecordFormat(150,
    {
        'filenum': DataMap(65, 2, c_ushort),
        'symbol': DataMap(1, 15, ms_str),
        'name': DataMap(16, 46, ms_str),
        'first_date': DataMap(108, 4, ms_xm_date),
        'last_date': DataMap(116, 4, ms_xm_date)
    }
)

DATHeader = RecordFormat(28,
    {
        'record_count': DataMap(2, 2, lambda x: c_ushort(x) - 1)
    }
)

DATRecord = RecordFormat(28,
    {
        'date': DataMap(0, 4, ms_dat_date),
        'open': DataMap(4, 4, ms_binfloat),
        'high': DataMap(8, 4, ms_binfloat),
        'low': DataMap(12, 4, ms_binfloat),
        'close': DataMap(16, 4, ms_binfloat),
        'volume': DataMap(20, 4, ms_binfloat),
        'unadj': DataMap(24, 4, ms_binfloat),
    }
)


EMasterFileFormat = MSIndexFileFormat(EMasterHeader, EMasterRecord)
XMasterFileFormat = MSIndexFileFormat(XMasterHeader, XMasterRecord)
DATFileFormat = MSIndexFileFormat(DATHeader, DATRecord)


def map_record(record, fmt):
    out = dict()
    for field in fmt:
        dmap = fmt[field]
        out[field] = dmap.f(record[dmap.i])
    return out


class MSFile(object):
    def __init__(self, in_file, fmt):
        if isinstance(in_file, file) or isinstance(in_file, StringIO):
            self.fh = in_file
        else:
            self.fh = open(in_file, 'rb')
        self.fmt = fmt
        self.setup()

    def setup(self):
        self.fh.seek(0)
        fmt = self.fmt.header
        self.cur_record = 0
        self.record_count = map_record(fmt.read(self.fh), fmt)['record_count']

    def __iter__(self):
        # ~ self.fh.seek(0)
        # ~ self.cur_record = 0
        self.setup()
        return (self)

    def next(self):
        if (self.cur_record >= self.record_count):
            raise StopIteration
        else:
            self.cur_record += 1
            fmt = self.fmt.record
            data = fmt.read(self.fh)
            return(map_record(data, fmt))

    def __getitem__(self, idx):
        idx = clampindex(idx, self.record_count)
        self.cur_record = idx
        self.fh.seek(self.fmt.header.length + self.fmt.record.length * idx)
        fmt = self.fmt.record
        data = fmt.read(self.fh)
        return(map_record(data, fmt))


class MSEMasterFile(MSFile):
    def __init__(self, in_file):
        super(MSEMasterFile, self).__init__(in_file, EMasterFileFormat)


class MSXMasterFile(MSFile):
    def __init__(self, in_file):
        super(MSXMasterFile, self).__init__(in_file, XMasterFileFormat)


class MSDATFile(MSFile):
    def __init__(self, in_file):
        super(MSDATFile, self).__init__(in_file, DATFileFormat)


class MSStock(MSDATFile):
    def __init__(self, header, dat_path):
        self.first_date = header['first_date']
        self.last_date = header['last_date']
        self.name = header['name']
        self.symbol = header['symbol']
        filenum = header['filenum']
        ext = '.dat' if filenum < 256 else '.mwd'
        filename = dat_path + 'F' + str(filenum) + ext
        super(MSStock, self).__init__(filename)

    def __repr__(self):
        return 'MSStock :\n' + self.symbol + ' (' + self.name + ')'


class MSDirectory:
    def __init__(self, path):
        try:
            if not os.path.exists(path):
                raise Exception("Invalid Path")
            self.path = path if (path[-1] == '/') else path + '/'
            self.emaster = MSEMasterFile(self.path + 'emaster')
            self.record_count = self.emaster.record_count
            self.xmaster = None
            if os.path.exists(self.path + 'xmaster'):
                self.xmaster = MSXMasterFile(self.path + 'xmaster')
                self.record_count += self.xmaster.record_count
        except Exception as e:
            raise e

    def __iter__(self):
        self.emaster.setup()
        if (self.xmaster is not None):
            self.xmaster.setup()
        return(self)

    def next(self):
        try:
            result = self.emaster.next()
            return(MSStock(result, self.path))
        except StopIteration:
            try:
                if (self.xmaster is not None):
                    result = self.xmaster.next()
                    return(MSStock(result, self.path))
            except StopIteration:
                pass
        raise(StopIteration)

    def __getitem__(self, idx):
        try:
            idx = clampindex(idx, self.record_count)
            if (idx < 256):
                record = self.emaster[idx]
            else:
                record = self.xmaster[idx - 255]
            return MSStock(record, self.path)
        except Exception as e:
            print(e)

    def __repr__(self):
        return "MSDirectory :\n" + self.path


class PremiumDataExchange(dict):

    folders = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    def __init__(self, path, name):
        try:
            if not os.path.exists(path):
                raise Exception("Invalid Path")
            self.path = path if (path[-1] == '/') else path + '/'
            self.name = name
            self.record_count = 0
            for f in PremiumDataExchange.folders:
                self[f] = MSDirectory(self.path + f)
                self.record_count += self[f].record_count
        except:
            raise

    def __iter__(self):
        return self.iter()

    def iter(self):
            for f in PremiumDataExchange.folders:
                for stock in self[f]:
                    yield stock
