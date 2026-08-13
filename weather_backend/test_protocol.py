import struct
import pytest
import protocol


class TestTempSensor:
    def test_parse_returns_value(self):
        raw = struct.pack('<f', 22.5)
        sensor, size = protocol.TempSensor.parse(raw)
        assert size == 4
        assert isinstance(sensor, protocol.TempSensor)
        assert sensor.value == 22.5

    def test_parse_negative_value(self):
        raw = struct.pack('<f', -10.0)
        sensor, size = protocol.TempSensor.parse(raw)
        assert sensor.value == -10.0

    def test_str(self):
        sensor = protocol.TempSensor(22.5)
        assert str(sensor) == 'temp: 22.5'


class TestHumiditySensor:
    def test_parse_returns_value(self):
        raw = struct.pack('<f', 65.3)
        sensor, size = protocol.HumiditySensor.parse(raw)
        assert size == 4
        assert isinstance(sensor, protocol.HumiditySensor)
        assert sensor.value == pytest.approx(65.3, rel=1e-5)

    def test_str(self):
        sensor = protocol.HumiditySensor(65.3)
        assert str(sensor) == 'hum: 65.3'


class TestPressureSensor:
    def test_parse_float_value(self):
        raw = struct.pack('<f', 101325.0)
        sensor, size = protocol.PressureSensor.parse(raw)
        assert size == 4
        assert isinstance(sensor, protocol.PressureSensor)
        assert sensor.value == pytest.approx(101325.0, rel=1e-5)

    def test_parse_uint_value(self):
        raw = struct.pack('<I', 50000)
        sensor, size = protocol.PressureSensor.parse(raw)
        assert size == 4
        assert isinstance(sensor, protocol.PressureSensor)
        assert sensor.value == 50000

    def test_str(self):
        sensor = protocol.PressureSensor(1013.25)
        assert str(sensor) == 'pres: 1013.25'


class TestVoltSensor:
    def test_parse_returns_value(self):
        raw = struct.pack('<I', 3300)
        sensor, size = protocol.VoltSensor.parse(raw)
        assert size == 4
        assert isinstance(sensor, protocol.VoltSensor)
        assert sensor.value == 3300


class TestSoilMoistureSensor:
    def test_parse_returns_value(self):
        raw = struct.pack('<f', 42.5)
        sensor, size = protocol.SoilMoistureSensor.parse(raw)
        assert size == 4
        assert isinstance(sensor, protocol.SoilMoistureSensor)
        assert sensor.value == 42.5


class TestParseErrors:
    def test_invalid_magic_and_version(self):
        data = bytes([0x41, 0x99, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        with pytest.raises(Exception, match='invalid header'):
            protocol.parse(data)

    def test_too_short(self):
        with pytest.raises(Exception, match='invalid header'):
            protocol.parse(bytes([0x77]))

    def test_unknown_module_id(self):
        data = bytes([0x77, protocol.VERSION, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0xFF])
        with pytest.raises(Exception, match='unknown module id'):
            protocol.parse(data)

    def test_missing_sensor_data(self):
        data = bytes([0x77, protocol.VERSION, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02,
                      0x01, 0x00, 0x00, 0x00, 0x00, 0x03])
        with pytest.raises(Exception):
            protocol.parse(data)


class TestVersion1Header:
    def test_parse_device_id(self):
        device_id = '24a1603048ba'
        data = bytes([0x77, protocol.VERSION]) + bytes.fromhex(device_id) + bytes([0x00])
        df = protocol.parse(data)
        assert df.device_id == device_id
        assert df.version == protocol.VERSION
        assert df.message_to_broker is False

    def test_parse_broker_message(self):
        data = bytes([0x57, protocol.VERSION]) + bytes(6) + bytes([0x00])
        df = protocol.parse(data)
        assert df.message_to_broker is True


class TestVersion2Header:
    def test_parse_device_id(self):
        device_id = 'ec'
        data = bytes([0x77, protocol.VERSION_2]) + bytes.fromhex(device_id) + bytes([0x00])
        df = protocol.parse(data)
        assert df.device_id == device_id
        assert df.version == protocol.VERSION_2
        assert df.message_to_broker is False

    def test_parse_broker_message(self):
        data = bytes([0x57, protocol.VERSION_2]) + b'\x01' + bytes([0x00])
        df = protocol.parse(data)
        assert df.message_to_broker is True


class TestWindSpeedDirection:
    def test_get_speed_dir_v2_index_0(self):
        # direction = bits 0-7, speed = bits 8-17
        # direction=64, speed=100
        data = bytes([64, 100, 0])
        speed, direction = protocol.WindSpeedDirection.get_speed_dir_v2(data, 0)
        assert speed == 100
        assert direction == 64

    def test_get_speed_dir_v2_index_5(self):
        data = b'\x00' * 10  # all zeros
        speed, direction = protocol.WindSpeedDirection.get_speed_dir_v2(data, 5)
        assert speed == 0
        assert direction == 0

    def test_parse_creates_decoded_values(self):
        # 6 buckets * 18 bits = 13.5 bytes → round up to 14 bytes
        module_size = protocol.WindSpeedDirection.MODULE_SIZE
        data = bytes(module_size)
        sensor, size = protocol.WindSpeedDirection.parse(data)
        assert size == module_size
        assert isinstance(sensor, protocol.WindSpeedDirection)
        assert len(sensor.value) == 6

    def test_direction_to_angle(self):
        data = bytes(protocol.WindSpeedDirection.MODULE_SIZE)
        sensor, size = protocol.WindSpeedDirection.parse(data)
        # direction 128 → 180 * 128/128 = 180
        # but with all zeros, direction=0 → angle=0
        for speed, direction in sensor.value:
            assert speed == 0.0
            assert direction == 0.0


class TestTHPCompound:
    def setup_method(self):
        # THPCompound.parse() calls _convert_thp() which needs stype2name
        # from weather.py. Patch it for this test.
        class _MockSensor:
            MODULE_ID = 0x01
            def __init__(self, v, *, id=None): self.value = v; self.name = 'temp'
        class _MockSensor2:
            MODULE_ID = 0x02
            def __init__(self, v, *, id=None): self.value = v; self.name = 'pressure'
        class _MockSensor3:
            MODULE_ID = 0x03
            def __init__(self, v, *, id=None): self.value = v; self.name = 'humidity'
        protocol.stype2name = {
            0x01: ('temperature', lambda v, id=None: _MockSensor(v, id=id)),
            0x02: ('pressure', lambda v, id=None: _MockSensor2(v, id=id)),
            0x03: ('humidity', lambda v, id=None: _MockSensor3(v, id=id)),
        }

    def test_parse_valid_packet(self):
        module_size = protocol.THPCompound.MODULE_SIZE
        data = bytearray(module_size)
        data[0] = 1  # 1 entry
        data[1] = 0  # bank_id = 0
        data[2:4] = struct.pack('<H', 1)  # t=1
        data[4] = 50  # h=50
        data[5:7] = struct.pack('<H', 300)  # p=300
        sensor, size = protocol.THPCompound.parse(data)
        assert size == module_size
        assert isinstance(sensor, protocol.THPCompound)
        assert len(sensor.values) == 1


class TestTHPCompoundV2:
    def test_parse_empty_config(self):
        data = bytes([0x00, 0x00, 0x00, 0x00])  # temp cfg=0, pressure cfg=0, humidity cfg=0
        values, size = protocol.THPCompoundV2.parse(data)
        assert isinstance(values, list)
        assert size == protocol.THPCompoundV2.MODULE_SIZE


class TestSerializeDeserialize:
    def test_roundtrip(self):
        df = protocol.DataFrame()
        df.device_id = '24a1603048ba'
        df.version = protocol.VERSION
        df.message_to_broker = False
        df.modules = [protocol.TempSensor(22.5)]
        # serialize requires modules to have serialize() method
        # TempSensor doesn't implement serialize, use a custom approach
        # Build the bytes manually for a simple roundtrip
        device_id = 'ec'
        raw = bytes([0x77, protocol.VERSION_2]) + bytes.fromhex(device_id) + bytes([0x01, 0x01]) + struct.pack('<f', 22.5)
        df2 = protocol.parse(raw)
        assert df2.device_id == device_id
        assert len(df2.modules) == 1
        assert isinstance(df2.modules[0], protocol.TempSensor)
        assert df2.modules[0].value == pytest.approx(22.5, rel=1e-5)
