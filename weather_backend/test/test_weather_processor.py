import asyncio
import struct
import pytest
from unittest.mock import patch, MagicMock
from weather import WeatherProcessor, cfg
from weather import WeatherServerHC12UARTProtocol as HC12Proto
import protocol
import libscrc


class FakeDB:
    """Collects add() calls for test inspection."""
    def __init__(self):
        self.calls = []

    def add(self, device_id, data, *, current_time=None):
        self.calls.append((device_id, data, current_time))


class FakeSocketTracker:
    """Fake socket tracker for ScreenSensor tests."""
    def __init__(self):
        self.calls = []

    async def add_screen(self, device_id, addr):
        self.calls.append((device_id, addr))


@pytest.fixture
def fake_db():
    return FakeDB()


@pytest.fixture
def fake_st():
    return FakeSocketTracker()


@pytest.fixture
def mock_loop():
    real_get_running_loop = asyncio.get_running_loop
    loop = MagicMock()
    def run_task(coro):
        try:
            real_get_running_loop().run_until_complete(coro)
        except RuntimeError:
            asyncio.run(coro)
        return MagicMock()
    loop.create_task.side_effect = run_task
    with patch('asyncio.get_running_loop', return_value=loop):
        yield loop


def make_protocol_payload(magic='W', version=2, device_id=0x02, sensors_num=1, modules=b''):
    """Build inner protocol payload."""
    magic_byte = ord(magic)
    if version == 2:
        header = bytes([magic_byte, version, device_id, sensors_num])
    else:
        import codecs
        # v1: device_id is 3 raw bytes encoded as 6 hex chars
        device_bytes = device_id.to_bytes(3, 'big')
        device_hex = codecs.encode(device_bytes, "hex").decode("ascii")
        header = bytes([magic_byte, version]) + device_hex.encode('ascii') + bytes([sensors_num])
    return header + modules


def build_hc12_packet(version, payload):
    """Build complete HC12 packet with valid CRC8."""
    size = len(payload)
    if version == 1:
        header = bytes([0x10, (size << 2), 0x50])
    else:
        header = bytes([0x20, (size << 2)])
    data = header + payload
    crc = libscrc.dvb_s2(data)
    return data + bytes([crc])


def float32_bytes(value):
    """Pack a float as 4 bytes little-endian."""
    return struct.pack('<f', value)


class TestTemperatureSensor:
    def test_simple_temp(self, fake_db, mock_loop):
        # TempSensor: module_id=0x01, value=float32(2.5)
        modules = bytes([0x01]) + float32_bytes(2.5)  # 5 bytes total
        payload = make_protocol_payload(magic='W', version=2, device_id=0x02, sensors_num=1, modules=modules)
        full = build_hc12_packet(2, payload)

        proto = HC12Proto(None, None)
        proc = WeatherProcessor(cfg, db=fake_db, sockets=[])
        proto.processor = proc

        proto.data_received(full)
        assert len(fake_db.calls) == 1
        device_id, data, _ = fake_db.calls[0]
        assert device_id == '02'

    def test_negative_temp(self, fake_db, mock_loop):
        # Temperature: -3.4°C
        modules = bytes([0x01]) + float32_bytes(-3.4)
        payload = make_protocol_payload(magic='W', version=2, device_id=0x02, sensors_num=1, modules=modules)
        full = build_hc12_packet(2, payload)

        proto = HC12Proto(None, None)
        proc = WeatherProcessor(cfg, db=fake_db, sockets=[])
        proto.processor = proc

        proto.data_received(full)
        assert len(fake_db.calls) == 1


class TestHumiditySensor:
    def test_humidity(self, fake_db, mock_loop):
        # HumiditySensor: module_id=0x03, value=float32(45.6)
        modules = bytes([0x03]) + float32_bytes(45.6)
        payload = make_protocol_payload(magic='W', version=2, device_id=0x02, sensors_num=1, modules=modules)
        full = build_hc12_packet(2, payload)

        proto = HC12Proto(None, None)
        proc = WeatherProcessor(cfg, db=fake_db, sockets=[])
        proc.st = FakeSocketTracker()
        proto.processor = proc

        proto.data_received(full)
        assert len(fake_db.calls) == 1


class TestPressureSensor:
    def test_pressure(self, fake_db, mock_loop):
        # PressureSensor: module_id=0x02, value=float32(1013.25) hPa
        modules = bytes([0x02]) + float32_bytes(1013.25)
        payload = make_protocol_payload(magic='W', version=2, device_id=0x02, sensors_num=1, modules=modules)
        full = build_hc12_packet(2, payload)

        proto = HC12Proto(None, None)
        proc = WeatherProcessor(cfg, db=fake_db, sockets=[])
        proc.st = FakeSocketTracker()
        proto.processor = proc

        proto.data_received(full)
        assert len(fake_db.calls) == 1


class TestVoltSensor:
    def test_voltage(self, fake_db, mock_loop):
        # VoltSensor: module_id=0x05, value=float32(3300) mV -> 3.3V
        modules = bytes([0x05]) + float32_bytes(3300.0)
        payload = make_protocol_payload(magic='W', version=2, device_id=0x02, sensors_num=1, modules=modules)
        full = build_hc12_packet(2, payload)

        proto = HC12Proto(None, None)
        proc = WeatherProcessor(cfg, db=fake_db, sockets=[])
        proc.st = FakeSocketTracker()
        proto.processor = proc

        proto.data_received(full)
        assert len(fake_db.calls) == 1


class TestSoilMoistureSensor:
    def test_soil_moisture(self, fake_db, mock_loop):
        # SoilMoistureSensor: module_id=0x09, value=float32(65.0)
        modules = bytes([0x09]) + float32_bytes(65.0)
        payload = make_protocol_payload(magic='W', version=2, device_id=0x02, sensors_num=1, modules=modules)
        full = build_hc12_packet(2, payload)

        proto = HC12Proto(None, None)
        proc = WeatherProcessor(cfg, db=fake_db, sockets=[])
        proc.st = FakeSocketTracker()
        proto.processor = proc

        proto.data_received(full)
        assert len(fake_db.calls) == 1


class TestInvalidData:
    def test_corrupted_packet(self, fake_db, mock_loop):
        proto = HC12Proto(None, None)
        proc = WeatherProcessor(cfg, db=fake_db, sockets=[])
        proto.processor = proc

        proto.data_received(b'\x00\x01\x02\x03\x04\x05')
        assert len(fake_db.calls) == 0


class TestNonBrokerMessage:
    def test_non_broker_message_dropped(self, fake_db, mock_loop):
        modules = bytes([0x01]) + float32_bytes(2.5)
        payload = make_protocol_payload(magic='w', version=2, device_id=0x02, sensors_num=1, modules=modules)
        full = build_hc12_packet(2, payload)

        proto = HC12Proto(None, None)
        proc = WeatherProcessor(cfg, db=fake_db, sockets=[])
        proto.processor = proc

        proto.data_received(full)
        assert len(fake_db.calls) == 0


class TestMultiSensorPacket:
    def test_two_sensors(self, fake_db, mock_loop):
        # Two sensors: Temperature + Humidity
        modules = (bytes([0x01]) + float32_bytes(2.5)    # Temp = 2.5°C
                   + bytes([0x03]) + float32_bytes(45.6))  # Humidity = 45.6%
        payload = make_protocol_payload(magic='W', version=2, device_id=0x02, sensors_num=2, modules=modules)
        full = build_hc12_packet(2, payload)

        proto = HC12Proto(None, None)
        proc = WeatherProcessor(cfg, db=fake_db, sockets=[])
        proc.st = FakeSocketTracker()
        proto.processor = proc

        proto.data_received(full)
        assert len(fake_db.calls) == 1


class TestVersion1Header:
    def test_v1_packet(self, fake_db, mock_loop):
        # Version 1 header with routing byte
        # v1 device_id is 6 hex bytes (e.g., '000002')
        modules = bytes([0x01]) + float32_bytes(2.5)
        payload = make_protocol_payload(magic='W', version=1, device_id=0x02, sensors_num=1, modules=modules)
        # Verify payload has correct v1 format (6-byte hex device_id)
        assert payload[2:8] == b'000002'
        header = bytes([0x10, (len(payload) << 2), 0x50])  # version=1, routing=0x50
        data = header + payload
        crc = libscrc.dvb_s2(data)
        full = data + bytes([crc])

        proto = HC12Proto(None, None)
        proc = WeatherProcessor(cfg, db=fake_db, sockets=[])
        proto.processor = proc

        proto.data_received(full)
        assert len(fake_db.calls) == 1
