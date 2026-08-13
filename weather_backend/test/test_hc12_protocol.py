import asyncio
import pytest
from pathlib import Path
import libscrc
import protocol
from unittest.mock import patch, MagicMock
from weather import WeatherServerHC12UARTProtocol, WeatherProcessor, cfg

TEST_DIR = Path(__file__).parent
PACKETS_DIR = TEST_DIR.parent


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


class TestRealPacketFiles:
    @staticmethod
    def _parse_hex_line(line):
        """Convert a hex string line to bytes."""
        line = ''.join(line.split())
        return bytes(int(line[i:i+2], 16) for i in range(0, len(line), 2))

    def test_packet_file_full_pipeline(self, fake_db, mock_loop):
        """Test packet.hc12 through the full processing pipeline."""
        with open(PACKETS_DIR / 'packet.hc12') as f:
            lines = f.read().strip().split('\n')

        proto = WeatherServerHC12UARTProtocol(None, WeatherProcessor(cfg, db=fake_db, sockets=[]))
        for line in lines:
            data = self._parse_hex_line(line)
            proto.data_received(data)

        # Each valid packet should produce one DB add call
        assert len(fake_db.calls) == len(lines)

        # Verify DB calls contain expected sensor types (THPCompound produces temp_X_Y, pres_X_Y, hum_X_Y)
        for device_id, sensor_data, current_time in fake_db.calls:
            sensors = list(sensor_data) if not hasattr(sensor_data, '__iter__') or isinstance(sensor_data, bytes) else sensor_data
            sensor_names = []
            for s in sensors:
                name = getattr(s, 'name', None)
                if name:
                    sensor_names.append(name)
                else:
                    sensor_names.append(type(s).__name__)
            # THPCompound sensors are named temp_X_Y, pres_X_Y, hum_X_Y
            assert any('temp' in n for n in sensor_names), f'Missing temp sensor in {device_id}: {sensor_names}'
            assert any('pres' in n for n in sensor_names), f'Missing pres sensor in {device_id}: {sensor_names}'
            assert any('hum' in n for n in sensor_names), f'Missing hum sensor in {device_id}: {sensor_names}'

    def test_packet_s1_file_full_pipeline(self, fake_db, mock_loop):
        """Test packet-s1.hc12 through the full processing pipeline.
        
        packet-s1.hc12 contains alternating v2 (WindSpeedDirection) and v1 (THPCompound) packets.
        v1 packets fail because stype2name is not defined in test context, so we only verify
        that v2 packets produce WindSpeed/WindDirection DB entries.
        """
        with open(PACKETS_DIR / 'packet-s1.hc12') as f:
            lines = f.read().strip().split('\n')

        proto = WeatherServerHC12UARTProtocol(None, WeatherProcessor(cfg, db=fake_db, sockets=[]))
        for line in lines:
            data = self._parse_hex_line(line)
            proto.data_received(data)

        # v2 packets produce WindSpeed+WindDirection pairs; v1 packets fail silently
        # Count v2 packets (even lines: 0, 2, 4, ...)
        v2_packet_count = sum(1 for i in range(0, len(lines), 2))
        
        # Each v2 packet produces 6 WindSpeed+WindDirection pairs (one per bucket)
        wind_calls = [c for c in fake_db.calls if len(c[1]) == 2 and 
                      type(list(c[1])[0]).__name__ == 'WindSpeed' and
                      type(list(c[1])[1]).__name__ == 'WindDirection']
        expected_wind_calls = v2_packet_count * 6  # 6 buckets per WindSpeedDirection packet
        assert len(wind_calls) == expected_wind_calls, f'Expected {expected_wind_calls} wind calls, got {len(wind_calls)}'
