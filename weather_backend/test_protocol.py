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
