import struct
import codecs
from io import BytesIO
import math
from typing import Any, final
from collections import OrderedDict

VERSION = 1
VERSION_2 = 2

MAGIC_TO_CLIENT = ord('w')
MAGIC_TO_BROKER = ord('W')


class BaseModule():
    MODULE_ID = 0x0
    MODULE_SIZE = 4

    def __init__(self, id : str | int | None = None):
        self._id = id

    @classmethod
    def parse(cls, data: bytes):
        raise NotImplementedError("parse")

    def serialize(self):
        raise NotImplementedError("serialize")

    @property
    def value(self):
        raise NotImplementedError('value')

    @property
    def id(self) -> str | int | None:
        return self._id

# don't use directly


class Simple4Bytes(BaseModule):
    BYTE_FORMAT = ""

    def __init__(self, value, **kwargs):
        super().__init__(**kwargs)

        self._value = value

    @property
    def value(self):
        return self._value

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

    def __init__(self, value, **kwargs):
        super().__init__(value, **kwargs)

    @classmethod
    def parse(cls, data: bytes):
        value, size = super().parse(data)
        return cls(value), size

# don't use directly


class SimpleUint32(Simple4Bytes):
    BYTE_FORMAT = "I"

    def __init__(self, value, **kwargs):
        super().__init__(value, **kwargs)

    @classmethod
    def parse(cls, data):
        value, size = super().parse(data)
        return cls(value), size


class SimpleInt32(Simple4Bytes):
    BYTE_FORMAT = "i"

    def __init__(self, value, **kwargs):
        super().__init__(value, **kwargs)

    @classmethod
    def parse(cls, data):
        value, size = super().parse(data)
        return cls(value), size


class VoltSensor(SimpleUint32):
    MODULE_ID = 0x05

    def __init__(self, value, **kwargs):
        super().__init__(value, **kwargs)


class TempSensor(SimpleFloat32):
    MODULE_ID = 0x01

    def __init__(self, value, **kwargs):
        super().__init__(value, **kwargs)

    def __str__(self):
        return f'temp: {self.value}'


class HumiditySensor(SimpleFloat32):
    MODULE_ID = 0x03

    def __init__(self, value, **kwargs):
        super().__init__(value, **kwargs)

    def __str__(self):
        return f'hum: {self.value}'


class PressureSensor(BaseModule):
    MODULE_ID = 0x02

    def __init__(self, value: float, **kwargs):
        super().__init__(**kwargs)

        self._value = value

    @property
    def value(self):
        return self._value

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
        # return VOCSensor(gas_raw, iaq, iaq_static, co2, flags), 17

        iaq_static._id = 'iaq_static'
        iaq._id = 'iaq'
        co2._id = 'co2'
        gas_raw = 'gas_raw'

        return (
            iaq_static,
            iaq,
            co2,
            gas_raw
        ), cls.MODULE_SIZE

        # sensors['iaq_static'] = fetch.StaticIaq(sid.iaq_static)
        # sensors['iaq'] = fetch.Iaq(sid.iaq)
        # sensors['co2'] = fetch.Co2(sid.co2)
        # sensors['gas_raw'] = fetch.GasResistance(sid.gas_raw)


class SoilMoistureSensor(SimpleFloat32):
    MODULE_ID = 0x09

# deprecated sensors
class TimeSensor(SimpleInt32):
    MODULE_ID = 0x4

class WindSensor(BaseModule):
    MODULE_ID = 0x10
    MODULE_SIZE = 6

    _value = [0 for _ in range(MODULE_SIZE)]

    def __init__(self, ticks: list[float]):
        if len(ticks) != len(self.value):
            raise Exception('invalid size')

        for i, v in enumerate(ticks):
            self._value[i] = int(v)

    @property
    def value(self):
        return self._value

    @classmethod
    def parse(cls, data):
        if len(data) < cls.MODULE_SIZE:
            raise Exception("too short")
        # SCALE TICKS !
        # scale incorrecly pased 2x ticks
        # sensor reads 2 ticks per revolution
        # and scale bucket size revolutions to revolution per second
        data = [v / (2 * (60 / cls.MODULE_SIZE)) for v in data]

        return cls(data), cls.MODULE_SIZE

def unpack(val, p, val_min, val_max):
    if not val:
        return float('NaN')
    val -= 1
    val *= (val_max - val_min) / (1 << p)
    val += val_min

    return val

@final
class THPCompound(BaseModule):
    MODULE_ID = 0x11
    # yup should be dynamic but here it is
    # and received packed is "dumb"
    MAX_SENSORS = 6
    # bank_id(1) temp(2) hum(1) pres(2)
    ENTRY_SIZE = 1 + 1 + 2 + 2
    MODULE_SIZE = MAX_SENSORS * ENTRY_SIZE + 1

    # bank_id 0xFF is special for PT100

    @final
    class THP:
        def __init__(self, bank_id: int, t: float, h: float, p: float):
            self.bank_id = bank_id
            self.t = t
            self.h = h
            self.p = p

    def __init__(self, values: list[THP]):
        super().__init__()
        self.values = values

    @classmethod
    def parse(cls, data):
        if len(data) != cls.MODULE_SIZE:
            raise Exception('INVALID SIZE')

        values: list[THPCompound.THP] = []

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

        values.sort(key = lambda x: x.bank_id)

        intermediate = cls(values)
        converted = intermediate._convert_thp()

        return cls(values), cls.MODULE_SIZE

    def _convert_thp(self):
        # This is just for "presentation" layer
        # it might change in future as it's not straight reauired
        # and might mess something
        required_defaults = set(('temperature', 'pressure', 'humidity'))

        sensors = {}

        for bank_id, sensor in self.decompose():
            module_name, converter = stype2name[sensor.MODULE_ID]
            if not converter:
                print('Unsupported module id:', sid.MODULE_ID)
                continue

            converted = converter(sensor.value, id=bank_id)

            sensors[converted.name] = converted

            if module_name in required_defaults:
                print('Missing default for:', module_name, 'create from', converted.name)
                v = converter(sensor.value)
                sensors[v.name] = v

                required_defaults.remove(module_name)

        return sensors

    def decompose(self):
        # Keep original (already sorted) order of banks
        banks: OrderedDict[int, list[list[BaseModule]]] = OrderedDict()

        for r in self.values:
            converted= []
            if not math.isnan(r.t):
                converted.append(TempSensor(r.t))

            if not math.isnan(r.h):
                converted.append(HumiditySensor(r.h))

            if not math.isnan(r.p):
                converted.append(PressureSensor(r.p))

            banks[r.bank_id] = banks.get(r.bank_id, []) + [converted]

        sensors: list[tuple[tuple[int, int] | int, BaseModule]] = []
        # group by banks
        for bank_id, entries in banks.items():
            print(bank_id, entries)

            if len(entries) == 1:
                sensors.extend((bank_id, e) for e in entries[0])
                continue

            for index, values in enumerate(entries):
                sensors.extend(((bank_id, index), e) for e in values)

        return sensors

@final
class WindSpeedDirection(BaseModule):
    MODULE_ID = 0x12
    BUCKETS = 6
    MODULE_SIZE = int((10 + 8) * BUCKETS / 8 + 0.5)
    _value = [(0.0, 0.0) for _ in range(BUCKETS)]

    def __init__(self, speed_and_dir: list[tuple[float, float]]):
        super().__init__()

        if len(speed_and_dir) != len(self.value):
            raise Exception('invalid size')

        for i, v in enumerate(speed_and_dir):
            self._value[i] = (float(v[0]), float(v[1]))

    @property
    def value(self):
        return self._value

    @staticmethod
    def get_speed_dir_v2(data: bytes|bytearray, index: int) -> tuple[int, int]:
        """
        Read an 18-bit value from a packed byte array at a given index.
        data: bytes or bytearray containing packed 18-bit values
        index: which 18-bit entry to read (0-based)
        Returns: integer value (0–0x3FFFF)
        """
        bit_offset = index * 18
        byte_pos = bit_offset // 8
        bit_pos = bit_offset % 8

        # Read only the bytes that exist, pad with 0 if necessary
        val = 0
        for i in range(4):  # 18 bits can span up to 3 bytes, but read 4 to be safe
            if byte_pos + i < len(data):
                val |= data[byte_pos + i] << (8 * i)
            else:
                val |= 0  # pad with 0 if out-of-bounds


        # Shift down to align desired bits and mask
        val = (val >> bit_pos) & 0x3FFFF
        direction = (val & 0xFF)
        speed = (val >> 8) & 0x3FF

        return (speed, direction)


    @staticmethod
    def get_speed_dir_v1(data: bytes|bytearray, index:int) -> tuple[int, float]:
        """Functional version that works on bytearray/bytes"""
        assert 0 <= index < 6

        # Calculate bit offset: index * 18
        bit_offset = index * 18
        byte_offset = bit_offset // 8
        bit_remainder = bit_offset % 8

        combined = 0

        # Reconstruct the 18-bit value from bytes
        bits_remaining = 18
        for i in range(3):
            current_byte = byte_offset + i
            if current_byte >= len(data):
                break  # Don't go beyond array bounds

            bits_to_take = min(8 - bit_remainder, 18 - i * 8)

            mask = (1 << bits_to_take) - 1
            value = (data[current_byte] >> bit_remainder) & mask

            combined = (combined << bits_to_take) | value
            bit_remainder = 0

            bits_remaining -= bits_to_take
            if not bits_remaining:
                break

        speed = (combined >> 8) & 0x3FF    # Extract speed (10 bits)
        direction = combined & 0xFF        # Extract direction (8 bits)
        return (speed, direction)

    @classmethod
    def parse(cls, data):
        if len(data) < cls.MODULE_SIZE:
            raise Exception("too short")

        decoded: list[tuple[int, float]]= []
        for i in range(cls.BUCKETS):
            speed, dir = cls.get_speed_dir_v2(data, i)
            #speed_v1, dir_v1 = cls.get_speed_dir_v1(data, i)
            #print(f'i={i} speed={speed}({speed_v1}) dir={dir}({dir_v1})')
            # 187 -> 262
            # decode dir where PI == 128 to angle
            dir = 180 * (dir / 128)
            # scale rotations per X seconds to rotations per seconds
            speed /= (60 / cls.BUCKETS)
            decoded.append((speed, dir))

        return cls(decoded), cls.MODULE_SIZE

class THPCompoundV2(BaseModule):
    MODULE_ID = 0x13
    class NamedTempSensor(TempSensor):
        def __init__(self, value, label):
            super().__init__(value)
            self.label = label

    class NamedPressureSensor(PressureSensor):
        def __init__(self, value, label):
            super().__init__(value)
            self.label = label

    class NamedHumiditySensor(HumiditySensor):
        def __init__(self, value, label):
            super().__init__(value)
            self.label = label

    '''Raw packet:
        temperature_config(count:4, pt100:1, reserved:3)
        temperature_banks_config(v0:2, v1:2, v2:2, v3:2) if 0 < temperature_config.count <= 4
        temperature_banks_config(v0:2, v1:2, v2:2, v3:2, v4:2, v5:2, v6:2, v7:2) if temperature_config.count > 4
        uint16[temperature_config.count]
        uint16[temperature_config.pt100]
        pressure_config(count:4, reserved: 4)
        pressure_banks_config(v0:2, v1:2, v2:2, v3:2) if 0 < pressure_config.count <= 4
        pressure_banks_config(v0:2, v1:2, v2:2, v3:2, v4:2, v5:2, v6:2, v7:2) if pressure_config.count > 4
        uint16[pressure_config.count]
        humidity_config(count:4, reserved: 4)
        humidity_banks_config(v0:2, v1:2, v2:2, v3:2) if 0 < humidity_config.count <= 4
        humidity_banks_config(v0:2, v1:2, v2:2, v3:2, v4:2, v5:2, v6:2, v7:2) if humidity_config.count > 4
        uint8[humidity_config.count]
    '''

    def __init__(self, bank, t, h, p):
        super().__init__()
        self.t = t
        self.h = h
        self.p = p
        self.bank = bank

    def decompose(self) -> list[list[int, BaseModule]]:

        return None


    @classmethod
    def parse(cls, data) -> tuple[list['THPCompoundV2'], int]:
        T_MIN = -40
        T_MAX = 85
        H_MIN = 0
        H_MAX = 100
        P_MIN = 88000
        P_MAX = 110000

        def parse_t_cfg(data):
            count = data & 0x0F
            pt100 = (data >> 4) & 0x01
            return (count, pt100)

        def parse_r_cfg(data):
            count = data & 0x0F
            return (count,)

        def parse_banks_cfg(data):
            def parse(data):
                banks = []
                for i in range(4):
                    banks.append((data >> (2 * i)) & 0x3)
                return banks

            banks = []
            for d in data:
                banks.extend(parse(d))

            return banks

        def unpack(val, p, val_min, val_max):
            if isinstance(val, bytes):
                if len(val) == 2:
                    val = struct.unpack('<H', val)[0]
                elif len(val) == 1:
                    val = val[0]
                else:
                    raise ValueError('Only 1 or 2 bytes are supported')

            val *= (val_max - val_min) / (1 << p)
            val += val_min

            return val

        def unpack_temp(val):
            return unpack(val, 16, T_MIN, T_MAX)

        def unpack_hum(val):
            return unpack(val, 8, H_MIN, H_MAX)

        def unpack_pres(val):
            return unpack(val, 16, P_MIN, P_MAX)

        t_sensors = []
        pt100_sensor = None
        p_sensors = []
        h_sensors = []

        deserialzers = (
            (parse_t_cfg, t_sensors, ),
            (parse_r_cfg, p_sensors, ),
            (parse_r_cfg, h_sensors, ),
        )

        index = 0
        t_len, pt100 = parse_t_cfg(data[index])
        index += 1

        if t_len:
            size = 2 if t_len > 4 else 1
            banks = parse_banks_cfg(data[index:index+size])
            index += size

            for i in range(t_len):
                t_sensors.append((banks[i], data[index:index+2]))
                index += 2

        if pt100:
            pt100_sensor = data[index:index+2]
            index += 2

        p_len, = parse_r_cfg(data[index])
        index += 1

        if p_len:
            size = 2 if p_len > 4 else 1
            banks = parse_banks_cfg(data[index:index+size])
            index += size

            for i in range(p_len):
                p_sensors.append((banks[i], data[index:index+2]))
                index += 2

        h_len, = parse_r_cfg(data[index])
        index += 1

        if h_len:
            size = 2 if h_len > 4 else 1
            banks = parse_banks_cfg(data[index:index+size])
            index += size

            for i in range(h_len):
                h_sensors.append((banks[i], data[index:index+1]))
                index += 1

        upacker = (
            (t_sensors, unpack_temp, TempSensor),
            (p_sensors, unpack_pres, PressureSensor),
            (h_sensors, unpack_hum, HumiditySensor),
        )

        values = []

        for s, u, c in upacker:
            number = 0
            last_bank_id = 0
            for bank_id, raw in s:
                if bank_id != last_bank_id:
                    last_bank_id = bank_id
                    number = 0

                v = u(raw)
                values.append(c(v, id=(bank_id, number)))

                number +=1

        def pt100_raw_to_temp(rt, ref_resistor=430.0, rtd_nominal=100.0):
            RTD_A                    = 3.9083e-3
            RTD_B                    = -5.775e-7

            rt /= 32768
            rt *= ref_resistor
            z1 = -RTD_A
            z2 = RTD_A * RTD_A - (4 * RTD_B)
            z3 = (4 * RTD_B) / rtd_nominal
            z4 = 2 * RTD_B
            temp = z2 + (z3 * rt)
            temp = (math.sqrt(temp) + z1) / z4
            if (temp >= 0):
                return temp
            rt /= rtd_nominal
            rt *= 100
            rpoly = rt
            temp = -242.02
            temp += 2.2228 * rpoly
            rpoly *= rt
            temp += 2.5859e-3 * rpoly
            rpoly *= rt
            temp -= 4.8260e-6 * rpoly
            rpoly *= rt
            temp -= 2.8183e-8 * rpoly
            rpoly *= rt
            temp += 1.5243e-10 * rpoly

            return temp

        if pt100_sensor:
            raw = struct.unpack('<H', pt100_sensor)[0]
            t = pt100_raw_to_temp(raw)
            values.append(TempSensor(t, id=255))

        return values, cls.MODULE_SIZE


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
    WindSpeedDirection,
    THPCompoundV2,
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
        self.modules:list[BaseModule] = []
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
        if isinstance(module, (list, tuple)):
            df.modules.extend(module)
        else:
            df.modules.append(module)
        offset += size
        sensors_num -= 1
    if sensors_num != 0:
        raise Exception("Missing data for %d modules" % sensors_num)
    return df
