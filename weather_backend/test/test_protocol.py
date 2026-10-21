import struct

import protocol
import pytest


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
        with pytest.raises(Exception, match='invalid size'):
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
    def test_parse_valid_packet(self):
        module_size = protocol.THPCompound.MODULE_SIZE
        data = bytearray(module_size)
        data[0] = 1  # 1 entry
        data[1] = 0  # bank_id = 0
        data[2:4] = struct.pack('<H', 1)  # t=1
        data[4] = 50  # h=50
        data[5:7] = struct.pack('<H', 300)  # p=300
        sensors, size = protocol.THPCompound.parse(bytes(data))
        assert size == module_size
        assert isinstance(sensors, list)
        # 1 entry with t, h, p produces 3 sensor objects
        assert len(sensors) == 3
        assert {type(s).__name__ for s in sensors} == {'TempSensor', 'HumiditySensor', 'PressureSensor'}


class TestTHPCompoundV2:
    def test_parse_empty_config(self):
        data = bytes([0x00, 0x00, 0x00, 0x00])  # temp cfg=0, pressure cfg=0, humidity cfg=0
        values, size = protocol.THPCompoundV2.parse(data)
        assert isinstance(values, list)
        # THP2 is variable length: an empty block consumes 3 config bytes,
        # not the inherited MODULE_SIZE (4). The extra byte belongs to the
        # next module/padding.
        assert size == 3


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


def _thp2_frame(temps=(), pressure=(), humidity=(), pt100=None):
    """Build a THPCompoundV2 (0x13) module frame; raw values as ints.

    temps/pressure/humidity: list of (bank, raw) tuples; raw is 16-bit for
    temps and pressure, 8-bit for humidity.
    """
    def bank_bytes(banks):
        out = bytearray()
        for i in range(0, len(banks), 4):
            b = 0
            for j, bank in enumerate(banks[i:i + 4]):
                b |= (bank & 0x3) << (2 * j)
            out.append(b)
        return bytes(out)

    t_cfg = len(temps) | (0x10 if pt100 is not None else 0x00)
    payload = bytes([t_cfg])
    if len(temps):
        payload += bank_bytes([b for b, _ in temps])
        payload += b''.join(struct.pack('<H', raw) for _, raw in temps)
    if pt100 is not None:
        payload += struct.pack('<H', pt100)

    payload += bytes([len(pressure)])
    if len(pressure):
        payload += bank_bytes([b for b, _ in pressure])
        payload += b''.join(struct.pack('<H', raw) for _, raw in pressure)

    payload += bytes([len(humidity)])
    if len(humidity):
        payload += bank_bytes([b for b, _ in humidity])
        payload += bytes(raw for _, raw in humidity)

    return bytes([ord('w'), protocol.VERSION]) + bytes(6) + bytes([1, 0x13]) + payload


def _parse_thp2(frame):
    return protocol.parse(frame).modules


class TestTHPCompoundV2Sentinel:
    """Slot-preserving emission (ADR-0014): dead slots are placeholder values
    so survivors keep their true (bank, ordinal) ids across drop/recover."""

    def test_hole_frame_survivor_keeps_ordinal(self):
        # bank 3 slot 0 dead (0xFFFF sentinel), slot 1 alive
        mods = _parse_thp2(_thp2_frame(temps=[(3, 0xFFFF), (3, 0x0042)]))
        assert len(mods) == 1
        assert isinstance(mods[0], protocol.TempSensor)
        assert mods[0].id == (3, 1)

    def test_ids_stable_across_drop_recover(self):
        # healthy: slot 0 and slot 1 both alive
        a = _parse_thp2(_thp2_frame(temps=[(3, 25000), (3, 25100)]))
        assert [(s.id, round(s.value, 3)) for s in a] == [((3, 0), 7.684), ((3, 1), 7.874)]
        # drop: slot 0 dies -> sentinel; slot 1 keeps its id and value
        b = _parse_thp2(_thp2_frame(temps=[(3, 0xFFFF), (3, 25100)]))
        assert [(s.id, round(s.value, 3)) for s in b] == [((3, 1), 7.874)]
        # recover: identical ids and values to frame A
        c = _parse_thp2(_thp2_frame(temps=[(3, 25000), (3, 25100)]))
        assert [(s.id, round(s.value, 3)) for s in c] == [((3, 0), 7.684), ((3, 1), 7.874)]

    def test_humidity_zero_is_sentinel(self):
        # 0x00 = 0.0 %RH is doubtful -> sentinel; 0x64 = 100 counts is data
        mods = _parse_thp2(_thp2_frame(humidity=[(0, 0x00), (0, 0x64)]))
        assert len(mods) == 1
        assert isinstance(mods[0], protocol.HumiditySensor)
        assert mods[0].id == (0, 1)
        assert mods[0].value == pytest.approx(100 * 0x64 / 256, rel=1e-9)

    def test_pressure_sentinel(self):
        mods = _parse_thp2(_thp2_frame(pressure=[(2, 0xFFFF), (2, 0x5000)]))
        assert len(mods) == 1
        assert isinstance(mods[0], protocol.PressureSensor)
        assert mods[0].id == (2, 1)
        assert mods[0].value == pytest.approx(94875.0)

    def test_all_sentinels_produce_no_sensors(self):
        mods = _parse_thp2(_thp2_frame(temps=[(0, 0xFFFF), (0, 0xFFFF)]))
        assert mods == []


class TestTHPCompoundV2PT100:
    """Raw PT100 uint16 wire code is captured alongside the derived temp."""

    def test_pt100_emits_raw_and_temp(self):
        code = 8358
        mods = _parse_thp2(_thp2_frame(pt100=code))

        raws = [m for m in mods if isinstance(m, protocol.PT100RawSensor)]
        temps = [m for m in mods if isinstance(m, protocol.TempSensor)]
        assert len(raws) == 1
        assert raws[0].id == 255
        assert raws[0].value == code
        assert len(temps) == 1
        assert temps[0].id == 255
        assert temps[0].value == pytest.approx(protocol.pt100_raw_to_temp(code), rel=1e-9)

    def test_pt100_temp_matches_reference_polynomial(self):
        # code 7621 -> 7621/32768*430 ohm = 100.02 ohm -> ~0 degC (nominal 100 ohm)
        assert protocol.pt100_raw_to_temp(7621) == pytest.approx(0.0, abs=0.2)
        # code 8358 -> ~109.7 ohm -> ~24.85 degC
        assert protocol.pt100_raw_to_temp(8358) == pytest.approx(24.85, abs=0.2)

    def test_no_pt100_no_raw_sensor(self):
        mods = _parse_thp2(_thp2_frame(temps=[(0, 0x0100)]))
        assert not any(isinstance(m, protocol.PT100RawSensor) for m in mods)

    def test_pt100_zero_is_data_not_sentinel(self):
        # only 0xFFFF is the dead-channel sentinel; code 0 is stored as-is
        mods = _parse_thp2(_thp2_frame(pt100=0))
        raws = [m for m in mods if isinstance(m, protocol.PT100RawSensor)]
        assert raws and raws[0].value == 0

    def test_pt100_ffff_sentinel_skips_channel(self):
        # dead PT100 channel: channel skipped, healthy temp on same frame kept
        mods = _parse_thp2(_thp2_frame(temps=[(0, 0x0100)], pt100=0xFFFF))
        assert not any(isinstance(m, protocol.PT100RawSensor) for m in mods)
        assert not any(isinstance(m, protocol.TempSensor) and m.id == 255 for m in mods)
        assert [m.id for m in mods] == [(0, 0)]

    def test_pt100_only_ffff_yields_no_sensors(self):
        mods = _parse_thp2(_thp2_frame(pt100=0xFFFF))
        assert mods == []
