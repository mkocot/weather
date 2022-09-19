#include <stddef.h>
#include <stdint.h>
#include <RFM69.h>
// #include <RadioLib.h>

#include "radio_rfm69.hpp"

#if ESP32

// SPI: Default pins
// RFM69 radio(SS /* chip select */, D2 /* DIO0 */);
// D2 is LED
RFM69 radio(SS /* chip select */, 4 /* DIO0 */);
// RF69 radio = new Module(SS, 4, 0xFF);

constexpr const uint8_t NETWORKID = 69;
// constexpr const uint8_t SENDER_ID = 219;
constexpr const uint8_t TARGET_ID = 0;

int radio_rfm69_setup()
{
    const uint16_t myNodeId = ESP.getEfuseMac() & 0xFFFF;
#if 0
    int state = radio.begin();
    state |= radio.setOutputPower(20, true);
    state |= radio.packetMode();
    state |= radio.variablePacketLengthMode();

    // state |= radio.setNodeAddress(myNodeId);
    // state |= radio.setDataShaping(0);
    // state |= radio.packetMode();
    return state;
#else
    if (!radio.initialize(RF69_433MHZ, myNodeId, NETWORKID))
    {
        return 1;
    }
    radio.setHighPower(); // ALWAYS for HCW or experience mysterious  failures
    return 0;
#endif
}

int radio_rfm69_send_all(const uint8_t *data, size_t len)
{
    radio.send(TARGET_ID, data, len, false);
    return 0;
}

int radio_rfm69_id(uint8_t *data)
{
    const auto nodeId = ESP.getEfuseMac();
    data[0] = (nodeId >> 0) & 0xFF;
    data[1] = (nodeId >> 8) & 0xFF;
    data[2] = (nodeId >> 16) & 0xFF;
    data[3] = (nodeId >> 24) & 0xFF;
    data[4] = (nodeId >> 32) & 0xFF;
    data[5] = (nodeId >> 40) & 0xFF;
    return 0;
}
#endif