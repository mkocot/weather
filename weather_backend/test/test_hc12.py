import asyncio
import pytest
from pathlib import Path
import config as config

# monkey patch
config.load_config = lambda x: {
    'storage': {
        'path': '/tmp/weather'
    },
    'bind': []
}

from weather import WeatherServerHC12UARTProtocol, WeatherServerProtocol, WeatherProcessor

TEST_DIR = Path(__file__).parent
PACKETS_DIR = TEST_DIR  # packet files live alongside tests


@pytest.fixture
def patocol():
    return WeatherProcessor(config.load_config(''))


@pytest.mark.asyncio
@pytest.mark.skip(reason="integration test requires packet.udp file")
async def test_udp(patocol):
    loop = asyncio.get_running_loop()
    emergency_stop = loop.create_future()
    prot = WeatherServerProtocol(emergency_stop, patocol)

    with open(PACKETS_DIR / 'packet.udp') as f:
        for line in f:
            data = int(line, 16).to_bytes(32, 'big')
            prot.datagram_received(data, ('127.0.0.1', 6969))
    await emergency_stop


@pytest.mark.asyncio
@pytest.mark.skip(reason="integration test requires real network/serial I/O")
async def test_hc12(patocol):
    loop = asyncio.get_running_loop()
    emergency_stop = loop.create_future()
    prot = WeatherServerHC12UARTProtocol(emergency_stop, patocol)

    for packet_file in ['packet-s1.hc12', 'packet.hc12']:
        with open(PACKETS_DIR / packet_file) as f:
            for line in f:
                line = ''.join(line.split())
                data = int(line, 16).to_bytes(len(line) // 2, 'big')
                prot.data_received(data)
    await emergency_stop


async def main():
    patocol = WeatherProcessor(config.load_config(''))
    await test_hc12(patocol)

if __name__ == '__main__':
    asyncio.run(main())
