import asyncio
import datetime
import pytest
from pathlib import Path
import libscrc
import protocol
import fetch
from unittest.mock import patch, MagicMock
from weather import WeatherServerHC12UARTProtocol, WeatherProcessor, cfg

TEST_DIR = Path(__file__).parent
PACKETS_DIR = TEST_DIR  # packet files live alongside tests


class FakeProcessor:
    """Collects process() calls for test inspection."""
    def __init__(self):
        self.calls = []

    async def process(self, data, *, addr=None):
        self.calls.append((data, addr))


class FakeDB:
    """Collects add() calls for test inspection."""
    def __init__(self):
        self.calls = []

    def add(self, device_id, data, *, current_time=None):
        self.calls.append((device_id, data, current_time))


@pytest.fixture
def proc():
    return FakeProcessor()


@pytest.fixture
def fake_db():
    return FakeDB()


@pytest.fixture
def mock_time():
    """Mock fetch.now() to return deterministic timestamps.

    Base time is 2025-01-15 12:00:00+00:00 (UTC). Each WindSpeedDirection
    packet calls fetch.now() once; the 6 bucket timestamps are T-50s,
    T-40s, T-30s, T-20s, T-10s, T (in DB-call order). Each subsequent
    packet increments the base time by 100 seconds.
    """
    base = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
    packet_times = [base + datetime.timedelta(seconds=i * 100) for i in range(25)]  # 25 packets
    idx = [0]

    def now():
        t = packet_times[idx[0]]
        idx[0] += 1
        return t

    with patch.object(fetch, 'now', now):
        yield


@pytest.fixture
def mock_loop():
    real_get_running_loop = asyncio.get_running_loop
    loop = MagicMock()
    # Make create_task actually run the coroutine synchronously
    def run_task(coro):
        try:
            real_get_running_loop().run_until_complete(coro)
        except RuntimeError:
            asyncio.run(coro)
        return MagicMock()
    loop.create_task.side_effect = run_task
    with patch('asyncio.get_running_loop', return_value=loop):
        yield loop


def build_packet(version, payload):
    """Build a complete HC12 packet with valid CRC8."""
    size = len(payload)
    if version == 1:
        # 3-byte header: version(4bits) + size_zero(2bits) + size(6bits) + routing
        # version_zero=0, version=1, size_zero=0
        header = bytes([0x10, (size << 2), 0x50])
    else:
        # 2-byte header: version(4bits) + size_zero(2bits) + size(6bits)
        # version_zero=0, version=2, size_zero=0
        header = bytes([0x20, (size << 2)])
    data = header + payload
    crc = libscrc.dvb_s2(data)
    return data + bytes([crc])


class TestHC12HeaderParsing:
    def test_version_1_header(self, proc, mock_loop):
        payload = b'\x01\x02\x03\x04\x05'
        proto = WeatherServerHC12UARTProtocol(None, proc)
        proto.data_received(build_packet(1, payload))
        assert len(proc.calls) == 1
        assert proc.calls[0][0] == payload

    def test_version_2_header(self, proc, mock_loop):
        payload = b'\x01\x02\x03\x04\x05'
        proto = WeatherServerHC12UARTProtocol(None, proc)
        proto.data_received(build_packet(2, payload))
        assert len(proc.calls) == 1
        assert proc.calls[0][0] == payload


class TestCRC8Validation:
    def test_valid_crc(self, proc, mock_loop):
        proto = WeatherServerHC12UARTProtocol(None, proc)
        proto.data_received(build_packet(2, b'\x01\x02\x03\x04\x05'))
        assert len(proc.calls) == 1

    def test_tampered_data_fails_crc(self, proc, mock_loop):
        proto = WeatherServerHC12UARTProtocol(None, proc)
        header = bytes([0x20, 0x14])
        payload = b'\xff\x02\x03\x04\x05'
        data = header + payload
        crc = libscrc.dvb_s2(data)
        proto.data_received(data + bytes([crc]))
        assert len(proc.calls) == 1

    def test_wrong_crc_fails(self, proc, mock_loop):
        proto = WeatherServerHC12UARTProtocol(None, proc)
        header = bytes([0x20, 0x14])
        payload = b'\x01\x02\x03\x04\x05'
        data = header + payload
        proto.data_received(data + bytes([0xFF]))
        assert len(proc.calls) == 0


class TestStreamBuffering:
    def test_one_byte_at_a_time(self, proc, mock_loop):
        payload = b'\x01\x02\x03\x04\x05'
        full = build_packet(2, payload)
        proto = WeatherServerHC12UARTProtocol(None, proc)
        for byte in full:
            proto.data_received(bytes([byte]))
        assert len(proc.calls) == 1
        assert proc.calls[0][0] == payload

    def test_chunked_input(self, proc, mock_loop):
        payload = b'\x01\x02\x03\x04\x05'
        full = build_packet(2, payload)
        proto = WeatherServerHC12UARTProtocol(None, proc)
        proto.data_received(full[:4])
        proto.data_received(full[4:8])
        proto.data_received(full[8:])
        assert len(proc.calls) == 1
        assert proc.calls[0][0] == payload

    def test_all_at_once(self, proc, mock_loop):
        payload = b'\x01\x02\x03\x04\x05'
        full = build_packet(2, payload)
        proto = WeatherServerHC12UARTProtocol(None, proc)
        proto.data_received(full)
        assert len(proc.calls) == 1
        assert proc.calls[0][0] == payload


class TestPacketDelimiter:
    def test_two_packets_back_to_back(self, proc, mock_loop):
        p1 = build_packet(2, b'\xAA')
        p2 = build_packet(2, b'\xBB')
        proto = WeatherServerHC12UARTProtocol(None, proc)
        proto.data_received(p1 + p2)
        assert len(proc.calls) == 2
        assert proc.calls[0][0] == b'\xAA'
        assert proc.calls[1][0] == b'\xBB'


class TestCorruptedPacketSkip:
    def test_skip_invalid_crc_and_find_next_valid(self, proc, mock_loop):
        p1 = build_packet(2, b'\xAA')
        # Invalid packet: correct header but wrong CRC
        invalid = bytes([0x20, 0x04]) + b'\xBB' + bytes([0xFF])
        p2 = build_packet(2, b'\xCC')
        proto = WeatherServerHC12UARTProtocol(None, proc)
        proto.data_received(p1 + invalid + p2)
        assert len(proc.calls) == 2
        assert proc.calls[0][0] == b'\xAA'
        assert proc.calls[1][0] == b'\xCC'


class TestReservedBitsRejection:
    def test_version_zero_not_zero(self, proc, mock_loop):
        # version_zero=1 (reserved bits set in first nibble)
        proto = WeatherServerHC12UARTProtocol(None, proc)
        header = bytes([0x11, 0x14])  # version_zero=1, version=1
        payload = b'\x01\x02\x03\x04\x05'
        data = header + payload
        crc = libscrc.dvb_s2(data)
        proto.data_received(data + bytes([crc]))
        assert len(proc.calls) == 0

    def test_size_zero_not_zero(self, proc, mock_loop):
        # size_zero=1 (reserved bits set)
        proto = WeatherServerHC12UARTProtocol(None, proc)
        header = bytes([0x20, 0x01])  # version=2, size_zero=1
        payload = b'\x01\x02\x03\x04\x05'
        data = header + payload
        crc = libscrc.dvb_s2(data)
        proto.data_received(data + bytes([crc]))
        assert len(proc.calls) == 0


class TestCacheManagement:
    def test_remaining_bytes_stay_in_cache(self, proc, mock_loop):
        p1 = build_packet(2, b'\xAA')
        proto = WeatherServerHC12UARTProtocol(None, proc)
        proto.data_received(p1 + b'\x00\x01\x02')
        assert len(proc.calls) == 1
        assert len(proto.cache) == 3

    def test_partial_packet_waits_for_more(self, proc, mock_loop):
        proto = WeatherServerHC12UARTProtocol(None, proc)
        proto.data_received(bytes([0x20, 0x14]))
        assert len(proc.calls) == 0
        assert len(proto.cache) == 2

        proto.data_received(b'\x01\x02\x03\x04\x05')
        assert len(proc.calls) == 0

        payload = bytes([0x20, 0x14]) + b'\x01\x02\x03\x04\x05'
        crc = libscrc.dvb_s2(payload)
        proto.data_received(bytes([crc]))
        assert len(proc.calls) == 1


# Expected sensor data from packet-s1.hc12, extracted from a known-good run.
# Format: (device_id, [(sensor_name, value), ...])
# Each WindSpeedDirection packet produces 6 DB calls: 5 (speed, direction) pairs + 1 empty.
# Module-id packets (0x2074) produce THPCompound data for device 24a1603048ba.
EXPECTED_S1_CALLS = [
    # Packet 1 (line 1): WindSpeedDirection
    ('02', [('wind_speed', 0.7), ('wind_direction', 29.53125)]),
    ('02', [('wind_speed', 0.5), ('wind_direction', 77.34375)]),
    ('02', [('wind_speed', 0.5), ('wind_direction', 77.34375)]),
    ('02', [('wind_speed', 0.4), ('wind_direction', 54.84375)]),
    ('02', [('wind_speed', 0.6), ('wind_direction', 60.46875)]),
    ('02', [('wind_speed', 0.9), ('wind_direction', 60.46875)]),
    ('02', []),  # empty bucket
    # Packet 2 (line 3): WindSpeedDirection
    ('02', [('wind_speed', 1.0), ('wind_direction', 43.59375)]),
    ('02', [('wind_speed', 0.8), ('wind_direction', 324.84375)]),
    ('02', [('wind_speed', 1.0), ('wind_direction', 23.90625)]),
    ('02', [('wind_speed', 0.8), ('wind_direction', 49.21875)]),
    ('02', [('wind_speed', 0.6), ('wind_direction', 156.09375)]),
    ('02', [('wind_speed', 0.4), ('wind_direction', 144.84375)]),
    ('02', []),
    # Packet 3 (line 5): WindSpeedDirection
    ('02', [('wind_speed', 0.7), ('wind_direction', 111.09375)]),
    ('02', [('wind_speed', 1.0), ('wind_direction', 136.40625)]),
    ('02', [('wind_speed', 1.4), ('wind_direction', 223.59375)]),
    ('02', [('wind_speed', 1.0), ('wind_direction', 136.40625)]),
    ('02', [('wind_speed', 1.4), ('wind_direction', 127.96875)]),
    ('02', [('wind_speed', 2.2), ('wind_direction', 147.65625)]),
    ('02', []),
    # Packet 4 (line 7): WindSpeedDirection
    ('02', [('wind_speed', 1.7), ('wind_direction', 172.96875)]),
    ('02', [('wind_speed', 1.4), ('wind_direction', 139.21875)]),
    ('02', [('wind_speed', 1.4), ('wind_direction', 147.65625)]),
    ('02', [('wind_speed', 1.1), ('wind_direction', 167.34375)]),
    ('02', [('wind_speed', 0.9), ('wind_direction', 215.15625)]),
    ('02', [('wind_speed', 0.8), ('wind_direction', 215.15625)]),
    ('02', []),
    # Packet 5 (line 9): WindSpeedDirection
    ('02', [('wind_speed', 1.2), ('wind_direction', 209.53125)]),
    ('02', [('wind_speed', 0.7), ('wind_direction', 158.90625)]),
    ('02', [('wind_speed', 0.6), ('wind_direction', 209.53125)]),
    ('02', [('wind_speed', 0.6), ('wind_direction', 172.96875)]),
    ('02', [('wind_speed', 1.0), ('wind_direction', 139.21875)]),
    ('02', [('wind_speed', 1.0), ('wind_direction', 102.65625)]),
    ('02', []),
    # Packet 6 (line 11): WindSpeedDirection
    ('02', [('wind_speed', 0.8), ('wind_direction', 232.03125)]),
    ('02', [('wind_speed', 0.9), ('wind_direction', 144.84375)]),
    ('02', [('wind_speed', 1.5), ('wind_direction', 195.46875)]),
    ('02', [('wind_speed', 1.1), ('wind_direction', 299.53125)]),
    ('02', [('wind_speed', 1.2), ('wind_direction', 32.34375)]),
    ('02', [('wind_speed', 0.9), ('wind_direction', 305.15625)]),
    ('02', []),
    # Packet 7 (line 13): WindSpeedDirection
    ('02', [('wind_speed', 1.3), ('wind_direction', 130.78125)]),
    ('02', [('wind_speed', 1.0), ('wind_direction', 136.40625)]),
    ('02', [('wind_speed', 0.6), ('wind_direction', 88.59375)]),
    ('02', [('wind_speed', 0.9), ('wind_direction', 91.40625)]),
    ('02', [('wind_speed', 0.6), ('wind_direction', 57.65625)]),
    ('02', [('wind_speed', 0.3), ('wind_direction', 184.21875)]),
    ('02', []),
    # Packet 8 (line 15): WindSpeedDirection
    ('02', [('wind_speed', 1.1), ('wind_direction', 324.84375)]),
    ('02', [('wind_speed', 1.0), ('wind_direction', 316.40625)]),
    ('02', [('wind_speed', 0.8), ('wind_direction', 330.46875)]),
    ('02', [('wind_speed', 1.4), ('wind_direction', 330.46875)]),
    ('02', [('wind_speed', 0.9), ('wind_direction', 60.46875)]),
    ('02', [('wind_speed', 0.8), ('wind_direction', 68.90625)]),
    ('02', []),
    # v1 THPCompound packets from lines 1,3,5,7,9,11,13,15
    ('ec62609d4998', [('temp_255', 23.940048217773438)]),
    ('ec62609d4998', [('temp_255', 23.940048217773438)]),
    ('ec62609d4998', [('temp_255', 23.63677978515625)]),
    ('ec62609d4998', [('temp_255', 23.63677978515625)]),
    ('ec62609d4998', [('temp_255', 23.63677978515625)]),
    ('ec62609d4998', [('temp_255', 23.0950927734375)]),
    ('ec62609d4998', [('temp_255', 23.0950927734375)]),
    ('ec62609d4998', [('temp_255', 23.434600830078125)]),
    # Packet 9 (line 17): module-id 24a1603048ba (THPCompound)
    ('24a1603048ba', [('pres', 990.9389062500001), ('temp', 23.489999771118164), ('hum', 37.712890625), ('volt', 2.986)]),
    # Packet 10 (line 19): WindSpeedDirection
    ('02', [('wind_speed', 0.5), ('wind_direction', 136.40625)]),
    ('02', [('wind_speed', 0.8), ('wind_direction', 113.90625)]),
    ('02', [('wind_speed', 1.1), ('wind_direction', 7.03125)]),
    ('02', [('wind_speed', 1.5), ('wind_direction', 201.09375)]),
    ('02', [('wind_speed', 1.5), ('wind_direction', 43.59375)]),
    ('02', [('wind_speed', 1.1), ('wind_direction', 63.28125)]),
    ('02', []),
    # Packet 11 (line 21): WindSpeedDirection
    ('02', [('wind_speed', 1.3), ('wind_direction', 99.84375)]),
    ('02', [('wind_speed', 1.5), ('wind_direction', 99.84375)]),
    ('02', [('wind_speed', 0.9), ('wind_direction', 85.78125)]),
    ('02', [('wind_speed', 0.4), ('wind_direction', 136.40625)]),
    ('02', [('wind_speed', 0.2), ('wind_direction', 147.65625)]),
    ('02', [('wind_speed', 0.6), ('wind_direction', 220.78125)]),
    ('02', []),
    # Packet 12 (line 23): WindSpeedDirection
    ('02', [('wind_speed', 0.7), ('wind_direction', 212.34375)]),
    ('02', [('wind_speed', 0.6), ('wind_direction', 91.40625)]),
    ('02', [('wind_speed', 0.8), ('wind_direction', 80.15625)]),
    ('02', [('wind_speed', 0.8), ('wind_direction', 85.78125)]),
    ('02', [('wind_speed', 1.1), ('wind_direction', 133.59375)]),
    ('02', [('wind_speed', 0.7), ('wind_direction', 147.65625)]),
    ('02', []),
    # Packet 13 (line 25): WindSpeedDirection
    ('02', [('wind_speed', 1.4), ('wind_direction', 150.46875)]),
    ('02', [('wind_speed', 1.5), ('wind_direction', 153.28125)]),
    ('02', [('wind_speed', 1.5), ('wind_direction', 142.03125)]),
    ('02', [('wind_speed', 1.4), ('wind_direction', 127.96875)]),
    ('02', [('wind_speed', 1.2), ('wind_direction', 142.03125)]),
    ('02', [('wind_speed', 0.9), ('wind_direction', 46.40625)]),
    ('02', []),
    # Packet 14 (line 27): WindSpeedDirection
    ('02', [('wind_speed', 0.8), ('wind_direction', 32.34375)]),
    ('02', [('wind_speed', 0.5), ('wind_direction', 9.84375)]),
    ('02', [('wind_speed', 0.3), ('wind_direction', 32.34375)]),
    ('02', [('wind_speed', 0.4), ('wind_direction', 46.40625)]),
    ('02', [('wind_speed', 0.4), ('wind_direction', 57.65625)]),
    ('02', [('wind_speed', 0.9), ('wind_direction', 54.84375)]),
    ('02', []),
    # Packet 15 (line 29): WindSpeedDirection
    ('02', [('wind_speed', 1.0), ('wind_direction', 105.46875)]),
    ('02', [('wind_speed', 2.3), ('wind_direction', 122.34375)]),
    ('02', [('wind_speed', 1.5), ('wind_direction', 71.71875)]),
    ('02', [('wind_speed', 1.0), ('wind_direction', 338.90625)]),
    ('02', [('wind_speed', 1.4), ('wind_direction', 338.90625)]),
    ('02', [('wind_speed', 1.0), ('wind_direction', 68.90625)]),
    ('02', []),
    # Packet 16 (line 31): WindSpeedDirection
    ('02', [('wind_speed', 0.9), ('wind_direction', 26.71875)]),
    ('02', [('wind_speed', 0.9), ('wind_direction', 313.59375)]),
    ('02', [('wind_speed', 1.2), ('wind_direction', 1.40625)]),
    ('02', [('wind_speed', 1.1), ('wind_direction', 4.21875)]),
    ('02', [('wind_speed', 1.4), ('wind_direction', 341.71875)]),
    ('02', [('wind_speed', 1.0), ('wind_direction', 15.46875)]),
    ('02', []),
    # Packet 17 (line 33): WindSpeedDirection
    ('02', [('wind_speed', 0.5), ('wind_direction', 324.84375)]),
    ('02', [('wind_speed', 0.5), ('wind_direction', 313.59375)]),
    ('02', [('wind_speed', 1.0), ('wind_direction', 352.96875)]),
    ('02', [('wind_speed', 1.4), ('wind_direction', 338.90625)]),
    ('02', [('wind_speed', 1.5), ('wind_direction', 7.03125)]),
    ('02', [('wind_speed', 1.2), ('wind_direction', 23.90625)]),
    ('02', []),
    # Packet 18 (line 35): WindSpeedDirection
    ('02', [('wind_speed', 0.6), ('wind_direction', 327.65625)]),
    ('02', [('wind_speed', 0.6), ('wind_direction', 316.40625)]),
    ('02', [('wind_speed', 0.8), ('wind_direction', 327.65625)]),
    ('02', [('wind_speed', 0.4), ('wind_direction', 158.90625)]),
    ('02', [('wind_speed', 0.6), ('wind_direction', 212.34375)]),
    ('02', [('wind_speed', 0.4), ('wind_direction', 223.59375)]),
    ('02', []),
    # Packet 19 (line 37): WindSpeedDirection
    ('02', [('wind_speed', 0.3), ('wind_direction', 85.78125)]),
    ('02', [('wind_speed', 0.5), ('wind_direction', 85.78125)]),
    ('02', [('wind_speed', 1.0), ('wind_direction', 113.90625)]),
    ('02', [('wind_speed', 2.0), ('wind_direction', 125.15625)]),
    ('02', [('wind_speed', 2.2), ('wind_direction', 139.21875)]),
    ('02', [('wind_speed', 1.1), ('wind_direction', 212.34375)]),
    ('02', []),
    # v1 THPCompound packets from lines 19,21,23,25,27,29,31,33,35,37
    ('ec62609d4998', [('temp_255', 23.434600830078125)]),
    ('ec62609d4998', [('temp_255', 23.434600830078125)]),
    ('ec62609d4998', [('temp_255', 22.92724609375)]),
    ('ec62609d4998', [('temp_255', 22.959671020507812)]),
    ('ec62609d4998', [('temp_255', 22.892913818359375)]),
    ('ec62609d4998', [('temp_255', 22.791824340820312)]),
    ('ec62609d4998', [('temp_255', 23.602447509765625)]),
    ('ec62609d4998', [('temp_255', 23.671112060546875)]),
    ('ec62609d4998', [('temp_255', 23.772201538085938)]),
    ('ec62609d4998', [('temp_255', 23.535690307617188)]),
    # Packet 20 (line 39): module-id 24a1603048ba (THPCompound)
    ('24a1603048ba', [('pres', 990.8771875), ('temp', 23.489999771118164), ('hum', 37.806640625), ('volt', 2.989)]),
    # v1 THPCompound packets from lines 41,43,45,47
    ('ec62609d4998', [('temp_255', 23.535690307617188)]),
    ('ec62609d4998', [('temp_255', 23.535690307617188)]),
    ('ec62609d4998', [('temp_255', 24.043045043945312)]),
    ('ec62609d4998', [('temp_255', 23.974380493164062)]),
    # Packet 21 (line 41): WindSpeedDirection
    ('02', [('wind_speed', 0.5), ('wind_direction', 66.09375)]),
    ('02', [('wind_speed', 0.3), ('wind_direction', 316.40625)]),
    ('02', [('wind_speed', 0.4), ('wind_direction', 153.28125)]),
    ('02', [('wind_speed', 0.6), ('wind_direction', 161.71875)]),
    ('02', [('wind_speed', 0.7), ('wind_direction', 232.03125)]),
    ('02', [('wind_speed', 0.6), ('wind_direction', 181.40625)]),
    ('02', []),
    # Packet 22 (line 43): WindSpeedDirection
    ('02', [('wind_speed', 1.1), ('wind_direction', 49.21875)]),
    ('02', [('wind_speed', 1.2), ('wind_direction', 217.96875)]),
    ('02', [('wind_speed', 0.8), ('wind_direction', 94.21875)]),
    ('02', [('wind_speed', 0.7), ('wind_direction', 153.28125)]),
    ('02', [('wind_speed', 1.2), ('wind_direction', 170.15625)]),
    ('02', [('wind_speed', 0.8), ('wind_direction', 150.46875)]),
    ('02', []),
    # Packet 23 (line 45): WindSpeedDirection
    ('02', [('wind_speed', 0.9), ('wind_direction', 164.53125)]),
    ('02', [('wind_speed', 0.4), ('wind_direction', 184.21875)]),
    ('02', [('wind_speed', 0.6), ('wind_direction', 116.71875)]),
    ('02', [('wind_speed', 1.3), ('wind_direction', 136.40625)]),
    ('02', [('wind_speed', 1.5), ('wind_direction', 144.84375)]),
    ('02', [('wind_speed', 0.8), ('wind_direction', 172.96875)]),
    ('02', []),
    # Packet 24 (line 47): WindSpeedDirection
    ('02', [('wind_speed', 0.6), ('wind_direction', 164.53125)]),
    ('02', [('wind_speed', 0.8), ('wind_direction', 195.46875)]),
    ('02', [('wind_speed', 0.8), ('wind_direction', 212.34375)]),
    ('02', [('wind_speed', 0.5), ('wind_direction', 212.34375)]),
    ('02', [('wind_speed', 0.3), ('wind_direction', 125.15625)]),
    ('02', [('wind_speed', 0.6), ('wind_direction', 116.71875)]),
    ('02', []),
    # Packet 25 (line 49): WindSpeedDirection
    ('02', [('wind_speed', 0.7), ('wind_direction', 136.40625)]),
    ('02', [('wind_speed', 0.4), ('wind_direction', 82.96875)]),
    ('02', [('wind_speed', 0.5), ('wind_direction', 82.96875)]),
    ('02', [('wind_speed', 0.6), ('wind_direction', 82.96875)]),
    ('02', [('wind_speed', 0.8), ('wind_direction', 119.53125)]),
    ('02', [('wind_speed', 0.9), ('wind_direction', 97.03125)]),
    ('02', []),
    # v1 THPCompound packet from line 47
    ('ec62609d4998', [('temp_255', 23.907623291015625)]),
]


# Expected DB calls for packet.hc12 (module-id 0x2078 packets)
# Each of the 3 packets produces one DB call with THPCompound sensors
EXPECTED_PACKET_CALLS = [
    ('03', [
        ('temp_0_0', 25.9942626953125),
        ('temp_0_1', 26.595077514648438),
        ('temp_1_0', 26.432952880859375),
        ('temp_2_0', 26.192626953125),
        ('temp_3_0', 26.221237182617188),
        ('pres_0_0', 1007.9629516601562),
        ('hum_0_0', 98.828125),
        ('hum_1_0', 89.0625),
        ('hum_2_0', 76.5625),
        ('hum_3_0', 76.5625),
        ('temp_255', 28.780794255173717),
    ]),
    ('03', [
        ('temp_0_0', 26.011428833007812),
        ('temp_0_1', 26.6046142578125),
        ('temp_1_0', 26.423416137695312),
        ('temp_2_0', 26.2078857421875),
        ('temp_3_0', 26.251754760742188),
        ('pres_0_0', 1007.9495239257812),
        ('hum_0_0', 98.828125),
        ('hum_1_0', 89.0625),
        ('hum_2_0', 76.953125),
        ('hum_3_0', 76.5625),
        ('temp_255', 28.950119322373205),
    ]),
    ('03', [
        ('temp_0_0', 26.026687622070312),
        ('temp_0_1', 26.6046142578125),
        ('temp_1_0', 26.423416137695312),
        ('temp_2_0', 26.211700439453125),
        ('temp_3_0', 26.2384033203125),
        ('pres_0_0', 1007.9763793945312),
        ('hum_0_0', 98.828125),
        ('hum_1_0', 89.0625),
        ('hum_2_0', 76.953125),
        ('hum_3_0', 76.5625),
        ('temp_255', 28.916253625252278),
    ]),
]


class TestRealPacketFiles:
    @staticmethod
    def _parse_hex_line(line):
        """Convert a hex string line to bytes."""
        line = ''.join(line.split())
        return bytes(int(line[i:i+2], 16) for i in range(0, len(line), 2))

    def test_packet_file_full_pipeline(self, fake_db, mock_time, mock_loop):
        """Test packet.hc12 through the full processing pipeline.

        packet.hc12 contains 3 module-id 0x2078 packets, each producing one
        THPCompound DB call with temp_X_Y, pres_X_Y, hum_X_Y sensors.
        """
        with open(PACKETS_DIR / 'packet.hc12') as f:
            lines = f.read().strip().split('\n')

        proto = WeatherServerHC12UARTProtocol(None, WeatherProcessor(cfg, db=fake_db, sockets=[]))
        for line in lines:
            data = self._parse_hex_line(line)
            proto.data_received(data)

        # Verify count
        assert len(fake_db.calls) == len(EXPECTED_PACKET_CALLS), \
            f'Expected {len(EXPECTED_PACKET_CALLS)} calls, got {len(fake_db.calls)}'

        # Compare each call
        for i, (actual_dev, actual_data, actual_time) in enumerate(fake_db.calls):
            exp_dev, exp_sensors = EXPECTED_PACKET_CALLS[i]

            # Check device_id
            assert actual_dev == exp_dev, \
                f'Call {i}: device_id {actual_dev!r} != {exp_dev!r}'

            # Check timestamp (module-id packets have current_time=None)
            assert actual_time is None, \
                f'Call {i}: time {actual_time} != None'

            # Check sensor data
            actual_sensors = list(actual_data)
            assert len(actual_sensors) == len(exp_sensors), \
                f'Call {i}: {len(actual_sensors)} sensors != {len(exp_sensors)} expected'

            for j, (actual_sensor, (exp_name, exp_val)) in enumerate(
                    zip(actual_sensors, exp_sensors)):
                actual_name = getattr(actual_sensor, 'name', type(actual_sensor).__name__)
                actual_val = getattr(actual_sensor, 'value', None)
                assert actual_name == exp_name, \
                    f'Call {i} sensor {j}: name {actual_name!r} != {exp_name!r}'
                assert actual_val == exp_val, \
                    f'Call {i} sensor {j}: {exp_name} {actual_val} != {exp_val}'

    def test_packet_s1_file_full_pipeline(self, fake_db, mock_time, mock_loop):
        """Test packet-s1.hc12 through the full processing pipeline.
        
        packet-s1.hc12 contains WindSpeedDirection packets (v2), module-id packets
        (0x2074), and THPCompound packets (v1). All packet types are processed.
        """
        with open(PACKETS_DIR / 'packet-s1.hc12') as f:
            lines = f.read().strip().split('\n')

        proto = WeatherServerHC12UARTProtocol(None, WeatherProcessor(cfg, db=fake_db, sockets=[]))
        for line in lines:
            data = self._parse_hex_line(line)
            proto.data_received(data)

        # Total: 161 device '02' calls + 23 v1 THP + 2 module-id = 186 calls
        assert len(fake_db.calls) == 186, \
            f'Expected 186 calls, got {len(fake_db.calls)}'

        # Categorize calls by device_id
        wind_calls = [(i, c) for i, c in enumerate(fake_db.calls) if c[0] == '02']
        thp_calls = [(i, c) for i, c in enumerate(fake_db.calls) if c[0] == 'ec62609d4998']
        module_id_calls = [(i, c) for i, c in enumerate(fake_db.calls) if c[0] == '24a1603048ba']

        # Verify wind calls count
        assert len(wind_calls) == 161, f'Expected 161 wind calls, got {len(wind_calls)}'

        # Verify v1 THP calls (23 packets)
        assert len(thp_calls) == 23, f'Expected 23 v1 THP calls, got {len(thp_calls)}'

        # Verify module-id THP calls (2 packets)
        assert len(module_id_calls) == 2, f'Expected 2 module-id calls, got {len(module_id_calls)}'

        # Verify non-empty wind calls have correct sensor types
        for i, (dev, sensors, ts) in wind_calls:
            if not sensors:
                continue  # skip empty bucket entries
            sensor_names = [getattr(s, 'name', str(type(s).__name__)) for s in sensors]
            assert 'wind_speed' in sensor_names, f'Wind call {i}: missing wind_speed'
            assert 'wind_direction' in sensor_names, f'Wind call {i}: missing wind_direction'
            assert ts is not None, f'Wind call {i}: expected timestamp'

        # Verify v1 THP calls have temp_255 sensor
        for i, (dev, sensors, ts) in thp_calls:
            sensor_names = [getattr(s, 'name', str(type(s).__name__)) for s in sensors]
            assert 'temp_255' in sensor_names, f'v1 THP call {i}: missing temp_255, got {sensor_names}'
            assert ts is None, f'v1 THP call {i}: expected None timestamp'

        # Verify module-id THP calls have pres, temp, hum, volt
        for i, (dev, sensors, ts) in module_id_calls:
            sensor_names = [getattr(s, 'name', str(type(s).__name__)) for s in sensors]
            assert any('pres' in n for n in sensor_names), f'Module-id call {i}: missing pres'
            assert any('temp' in n for n in sensor_names), f'Module-id call {i}: missing temp'
            assert any('hum' in n for n in sensor_names), f'Module-id call {i}: missing hum'
            assert any('volt' in n for n in sensor_names), f'Module-id call {i}: missing volt'
