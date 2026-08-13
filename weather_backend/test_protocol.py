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
