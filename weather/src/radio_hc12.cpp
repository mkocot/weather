#include "radio_hc12.hpp"

#include <CRC.h>
#include <SoftwareSerial.h>

constexpr auto TX2 = 26;
constexpr auto RX2 = 27;
constexpr auto SET2 = 25;

class HC12 {
  SoftwareSerial &mStream;
  uint8_t mSet_pin{255};
  bool mWaitForResponse{false};
  uint8_t tmp[64] = {0}; // packet is 64 bytes long

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
    // message is at most 62 bytes so 1 for length and 1 for crc
    if (len > 62) {
      return 1;
    }
    if (mWaitForResponse) {
      return 1;
    }
    // 2 bits unused, reserved
    // so if anything is bigger than 63 it's not the start of message
    tmp[0] = len & 0b00111111;
    // copy from 1 to len (both inclusive)
    memcpy(tmp + 1, data, len);
    // put CRC8 at len + 1
    tmp[len + 1] = crc8(tmp, len + 1); // checksum (with length prefix)

#if W_VERBOSE
    Serial.print("Raw data: ");
    for (int i = 0; i < len + 2; i++) {
      if (tmp[i] < 15) {
        Serial.print(' ');
      }
      Serial.print(tmp[i], 16);
    }
    Serial.println();
#endif
    mStream.write(tmp, len + 2);
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

int radio_hc12_send(const char *str) {
  Serial.println("send justring");
  hc2.loop();
  // hc2.send(data, len);
  // uint8_t[]d = {'h'};
  // hc2.send(d, 10);
  // hc2.send(str);
  return 0;
}
int radio_hc12_send_all(const uint8_t *data, size_t len) {
  Serial.println("send all");
  // just in case something is on wire (shouldn't)
  hc2.loop();
  hc2.send(data, len);
  // uint8_t[]d = {'h'};
  // hc2.send(d, 10);
  // hc2.send("Hwllo world");
  return 0;
}
