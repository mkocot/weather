#include "radio_hc12.hpp"

#include <CRC.h>
#include <SoftwareSerial.h>

constexpr auto TX2 = 26;
constexpr auto RX2 = 27;
constexpr auto SET2 = 25;

struct HC12_HDR {
  // Version
  struct {
    uint8_t version_zero: 4; // reserved should be 0
    uint8_t version: 4; // should be 1
  };
  // Packet specification for version 1
  // Size
  struct {
    uint8_t size_zero: 2; // reserved should be 0
    uint8_t size: 6; // 0..63
  };
  // Let's this surprise me, when i gonna need more more than 15 stations
  // (1 for receiver and 14 for senders)
  struct {
    uint8_t packet_to: 4; // 0..15
    uint8_t packet_from: 4; // 0..15
  };
};

static_assert(std::is_trivial<HC12_HDR>::value, "Header is not trivial");
static_assert(sizeof(HC12_HDR) == 3, "Header shoult be 3");

constexpr auto MAX_PACKET_SIZE = 64;
constexpr auto CRC_SIZE = 1;
constexpr auto MAX_PAYLOAD_SIZE = MAX_PACKET_SIZE - sizeof(HC12_HDR) - CRC_SIZE;


class HC12 {
  SoftwareSerial &mStream;
  uint8_t mSet_pin{255};
  bool mWaitForResponse{false};
  uint8_t tmp[MAX_PACKET_SIZE] = {0}; // packet is 64 bytes long
  uint8_t node_id{1};

  void enterCommandMode() { digitalWrite(mSet_pin, LOW); }
  void exitCommandMode() { digitalWrite(mSet_pin, HIGH); }

  int postCommand(const char *cmd, const size_t len) {
    // if (mWaitForResponse) {
    //   return 1;
    // }
    // ensure we pushed anything remaining in buffer
    mStream.flush();
    mWaitForResponse = true;
    enterCommandMode();
    Serial.printf("SEND: '%s'\n", cmd);
    auto wrote = mStream.write(cmd, len);
    // exitCommandMode();
    Serial.printf("wrote=%d\n", wrote);
    return wrote != len;
  }

public:
  HC12(SoftwareSerial &stream, uint8_t set_pin)
      : mStream(stream), mSet_pin(set_pin) {
    pinMode(mSet_pin, OUTPUT);
    exitCommandMode();

    auto hdr = reinterpret_cast<HC12_HDR*>(tmp);
    memset(hdr, 0, sizeof(*hdr));

    hdr->packet_from = node_id;
    hdr->packet_to = 0xF;
    hdr->version = 1;
  }

  int setChannel(uint8_t channel) {
    if (channel > 127) {
      return 1;
    }
    char tmp[7];
    // "AT+Cxxx"
    snprintf(tmp, sizeof(tmp), "AT+C%02d", channel);
    return postCommand(tmp, sizeof(tmp));
  }

  int setPower(uint8_t power) {
    if (power > 8) {
      return 1;
    }
    char tmp[5];
    snprintf(tmp, sizeof(tmp), "AT+P%d", power);
    return postCommand(tmp, sizeof(tmp));
  }

  int peekaboo() { return postCommand("AT+RX", 5); }

  int version() { return postCommand("AT+V", 4); }

  int send(const uint8_t *data, size_t len) {
    // message is at most MAX_PAYLOAD_SIZE bytes
    if (len > MAX_PAYLOAD_SIZE) {
      return 1;
    }
    if (mWaitForResponse) {
      return 1;
    }
    auto hdr = reinterpret_cast<HC12_HDR*>(tmp);
    hdr->size = len;
    auto index = sizeof(*hdr);
    // copy from 1 to len (both inclusive)
    memcpy(tmp + index, data, len);
    index += len;
    // put CRC8 at len + 1
    // polynome: 0xD5 (DVB-S2), but descriptions incorecly states it's 0x8C
    // (reversed 1-Wire)
    tmp[index] = crc8(tmp, index); // checksum (with header)
    ++index;

#if W_VERBOSE
    Serial.print("Total size: "); Serial.println(index);
    Serial.print("Raw data: ");
    for (int i = 0; i < index; i++) {
      if (tmp[i] < 15) {
        Serial.print('0');
      }
      Serial.print(tmp[i], 16);
      Serial.print(' ');
    }
    Serial.println();
#endif
    mStream.write(tmp, index);
    mStream.flush();
    return 0;
  }

  void loop() {
    // NOTE: exit SET mode AFTER receiving confirmation form AT command
    if (mStream.available()) {
      Serial.printf("SS%d: ", mSet_pin);
      while (mStream.available()) {
        Serial.print(char(mStream.read()));
      }
      Serial.println();
    }
  }
};

SoftwareSerial ss2(TX2, RX2);
HC12 hc2(ss2, SET2);

int radio_hc12_id(uint8_t *data) {
  const auto nodeId = ESP.getEfuseMac();
  data[0] = (nodeId >> 0) & 0xFF;
  data[1] = (nodeId >> 8) & 0xFF;
  data[2] = (nodeId >> 16) & 0xFF;
  data[3] = (nodeId >> 24) & 0xFF;
  data[4] = (nodeId >> 32) & 0xFF;
  data[5] = (nodeId >> 40) & 0xFF;
  return 0;
}

int radio_hc12_setup() {
  ss2.begin(9600); // SWSERIAL_8N1, TX2, RX2);
  return 0;
}

int radio_hc12_send_all(const uint8_t *data, size_t len) {
  // just in case something is on wire (shouldn't)
  hc2.loop();
  hc2.send(data, len);
  return 0;
}
