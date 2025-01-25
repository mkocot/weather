import struct
import codecs
from io import BytesIO

VERSION = 1
VERSION_2 = 2

MAGIC_TO_CLIENT = ord('w')
MAGIC_TO_BROKER = ord('W')


class BaseModule():
    MODULE_ID = 0x0
    MODULE_SIZE = 4

    def __init__(self):
        pass

    @classmethod
    def parse(cls, data):
        raise NotImplementedError("parse")

    def serialize(self):
        raise NotImplementedError("serialize")

# don't use directly


class Simple4Bytes(BaseModule):
    BYTE_FORMAT = ""

    def __init__(self, value):
        self.value = value

    @classmethod
    def parse(cls, data: bytes):
        if not isinstance(data, bytes):
            raise Exception("expected bytes")
        if len(data) < 4:  # 4 bytes
            raise Exception("invalid sieze")
        return struct.unpack(cls.BYTE_FORMAT, data[:4])[0], 4

# don't use directly


class SimpleFloat32(Simple4Bytes):
    BYTE_FORMAT = "f"

    @classmethod
    def parse(cls, data):
        value, size = super().parse(data)
        return cls(value), size

# don't use directly


class SimpleUint32(Simple4Bytes):
    BYTE_FORMAT = "I"

    @classmethod
    def parse(cls, data):
        value, size = super().parse(data)
        return cls(value), size


class SimpleInt32(Simple4Bytes):
    BYTE_FORMAT = "i"

    @classmethod
    def parse(cls, data):
        value, size = super().parse(data)
        return cls(value), size


class VoltSensor(SimpleUint32):
    MODULE_ID = 0x05


class TempSensor(SimpleFloat32):
    MODULE_ID = 0x01

    def __str__(self):
        return f'temp: {self.value}'


class HumiditySensor(SimpleFloat32):
    MODULE_ID = 0x03

    def __str__(self):
        return f'hum: {self.value}'


class PressureSensor(BaseModule):
    MODULE_ID = 0x02

    def __init__(self, value):
        super().__init__()
        self.value = value

    @classmethod
    def parse(cls, data):
        fval = SimpleFloat32.parse(data[0:4])[0].value
        uval = SimpleUint32.parse(data[0:4])[0].value
        if fval < 30000 or fval > 120000:
            value = uval
        else:
            value = fval
        return cls(value), 4

    def __str__(self):
        return f'pres: {self.value}'


class ScreenSensor(BaseModule):
    MODULE_ID = 0x06

    def __init__(self, width, height):
        self.width = width
        self.height = height

    @classmethod
    def parse(cls, data):
        if len(data) < 4:
            raise Exception("too short")
        # yes, we should parse it as uint16, but whatever
        width = data[1]
        height = data[3]
        return ScreenSensor(width, height), 4

# This is special "module" derived from serial data
class SignalQuality(SimpleFloat32):
    MODULE_ID = 0xFF01


class ImagePush(BaseModule):
    MODULE_ID = 0x07

    def __init__(self, width, height, image):
        self.width = width
        self.height = height
        self.image = image
        if self.width * self.height // 8 != len(image):
            raise Exception("image has invalid size")

    def serialize(self, buffer):
        buffer.write(bytes((0, self.width, 0, self.height)))
        buffer.write(self.image)
        return True

    @classmethod
    def parse(cls, data):
        return None, 512 + 4


class VOCSensor(BaseModule):
    MODULE_ID = 0x08
    MODULE_SIZE = 4 * 4 + 1

    def __init__(self, gas_raw, iaq, iaq_static, co2, flags):
        self.gas_raw = gas_raw
        # Index for Air Quality, especially recommended for mobile
        # devices, since the auto-trim algorithm automatically adopts to
        # different environments.
        self.iaq = iaq
        # “Static” Index for Air Quality, especially recommended for
        # stationary devices (w/ o auto-trimming algorithm)
        self.iaq_static = iaq_static
        self.co2 = co2
        # 2 bits for each iaq, iaq_static, co2
        self.flags = flags

    @classmethod
    def parse(cls, data):
        if len(data) < cls.MODULE_SIZE:
            raise Exception("too short")
        # gas_raw, iaq, iaq_static, co2, flags
        gas_raw = SimpleFloat32.parse(data[0:4])[0].value
        iaq = SimpleFloat32.parse(data[4:8])[0].value
        iaq_static = SimpleFloat32.parse(data[8:12])[0].value
        co2 = SimpleFloat32.parse(data[12:16])[0].value
        flags = data[16]
        return VOCSensor(gas_raw, iaq, iaq_static, co2, flags), 17


class SoilMoistureSensor(SimpleFloat32):
    MODULE_ID = 0x09

# deprecated sensors
class TimeSensor(SimpleInt32):
    MODULE_ID = 0x4

class WindSensor(BaseModule):
    MODULE_ID = 0x10
    MODULE_SIZE = 6
    value = [0 for _ in range(MODULE_SIZE)]
    def __init__(self, ticks):
        if len(ticks) != len(self.value):
            raise Exception('invalid size')

        for i, v in enumerate(ticks):
            self.value[i] = int(v)
    
    @classmethod
    def parse(cls, data):
        if len(data) < cls.MODULE_SIZE:
            raise Exception("too short")
        
        return cls(data), cls.MODULE_SIZE

def unpack(val, p, val_min, val_max):
    if not val:
        return float('NaN')
    val -= 1
    val *= (val_max - val_min) / (1 << p)
    val += val_min

    return val


class THPCompound(BaseModule):
    MODULE_ID = 0x11
    # yup should be dynamic but here it is
    # and received packed is "dumb"
    MAX_SENSORS = 6
    # bank_id(1) temp(2) hum(1) pres(2)
    ENTRY_SIZE = 1 + 1 + 2 + 2
    MODULE_SIZE = MAX_SENSORS * ENTRY_SIZE + 1

    # bank_id 0xFF is special for PT100

    class THP:
        def __init__(self, bank_id, t, h, p):
            self.bank_id = bank_id
            self.t = t
            self.h = h
            self.p = p

    def __init__(self, values):
        self.values = values

    @classmethod
    def parse(cls, data):
        if len(data) != cls.MODULE_SIZE:
            raise Exception('INVALID SIZE')

        values = []

        entries = data[0]
        data = data[1:]

        for i in range(entries):
            bank_id = data[0]
            t = struct.unpack('H', data[1:3])[0]
            h = data[3]
            p = struct.unpack('H', data[4:6])[0]

            print('RAW', bank_id, t, h, p)
            t = unpack(t, 16, -40, 85)
            h = unpack(h, 8, 0, 100)
            p = unpack(p, 16, 300, 110000)
            print('UPK', bank_id, t, h, p)
            values.append(cls.THP(bank_id, t, h, p))

            data = data[6:]

        return cls(entries), cls.MODULE_SIZE

MODULES = [
    VoltSensor,
    TempSensor,
    HumiditySensor,
    PressureSensor,
    ScreenSensor,
    ImagePush,
    TimeSensor,
    VOCSensor,
    SoilMoistureSensor,
    WindSensor,
    THPCompound,
]

_ID_TO_MODULE = {m.MODULE_ID: m for m in MODULES}

# 2 - sync byte + version
# 6 - device id
# 1 - sensors count
HEADER_SIZE = 2 + 6 + 1
HEADER_SIZE_V2 = 2 + 1 + 1

HEADER_SIZES = {
    VERSION: HEADER_SIZE,
    VERSION_2: HEADER_SIZE_V2,
}

class DataFrame:
    def __init__(self):
        self.device_id = ''
        self.modules = []
        self.version = 0
        self.message_to_broker = False


def serialize(df: DataFrame):
    buffer = BytesIO()
    if df.message_to_broker:
        magic = MAGIC_TO_BROKER
    else:
        magic = MAGIC_TO_CLIENT
    buffer.write(bytes([magic, df.version]))
    x = codecs.decode(df.device_id.encode("ascii"), "hex")
    buffer.write(x)
    buffer.write(bytes([len(df.modules)]))
    for m in df.modules:
        buffer.write(bytes([m.MODULE_ID]))
        m.serialize(buffer)

    return buffer.getvalue()


def parse(data: bytes):
    if not isinstance(data, bytes):
        raise Exception("data is not bytes")
    offset = 0

    
    if len(data) < 2: # magic byte + version
        raise Exception("invalid header")

    if (data[0] != MAGIC_TO_CLIENT and data[0] != MAGIC_TO_BROKER) and data[1] not in (VERSION, VERSION_2):
        raise Exception("invalid header")
    df = DataFrame()
    df.message_to_broker = data[0] == MAGIC_TO_BROKER
    df.version = data[1]
    if df.version == VERSION:
        df.device_id = codecs.encode(data[2:8], "hex").decode("ascii")
        sensors_num = data[8]
    elif df.version == VERSION_2:
        df.device_id = codecs.encode(data[2:3], "hex").decode("ascii")
        sensors_num = data[3]
    else:
        raise Exception("check yar code")

    offset = HEADER_SIZES[df.version]

    while sensors_num > 0 and offset < len(data):
        module_id = data[offset]
        print('module-id', module_id)
        offset += 1
        module_factory = _ID_TO_MODULE.get(module_id)
        if not module_factory:
            raise Exception("unknown module id %d" % module_id)
        module, size = module_factory.parse(data[offset:])
        df.modules.append(module)
        offset += size
        sensors_num -= 1
    if sensors_num != 0:
        raise Exception("Missing data for %d modules" % sensors_num)
    return df
