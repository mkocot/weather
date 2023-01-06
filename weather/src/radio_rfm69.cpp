#include <stddef.h>
#include <stdint.h>

#define RADIO_A (1)

#if RADIO_A
#  include <RFM69.h>
#else
#  include <RadioLib.h>
#endif

#include "radio_rfm69.hpp"

#if ESP32

// czarny gnd - gnd
// bialt 3.3 - vcc
// czerwony (kolo bialego) DIO0 - D4
// szary ss - d5
// niebieski sck - d18
// brazowy mosi - d23
// czerwony miso - d19

// SPI: Default pins
#  if RADIO_A
// RFM69 radio(SS /* chip select */, D2 /* DIO0 */);
// D2 is LED
static RFM69 radio(SS /* chip select */, 4 /* DIO0 */, true);
#  else
static RF69 radio = new Module(SS, 4, 0xFF);
#  endif

constexpr const uint8_t NETWORKID = 0x69;
constexpr const uint8_t TARGET_ID = 0x0;

static uint64_t send_start = 0;
static uint64_t send_end = 0;
static TaskHandle_t rfm_watchdog = nullptr;
constexpr const auto WATCHDOG_LIMIT = 15 /* minutes */ * 60 /* seconds */ *
                                      1000 /* milisenonds */ *
                                      1000 /* microseconds */;

static RTC_NOINIT_ATTR int hacky_restart;
static RTC_NOINIT_ATTR int watchdog_restarts;

constexpr const int EXPECTED_HACKY_RESTART = 0x69133796;

int radio_rfm69_reset_hacky_restart() {
  Serial.println("reset to 42");
  hacky_restart = 42;
  return 0;
}

static void radio_rfm69_reset_watchdog_restart() {
  Serial.println("reset to 0");
  watchdog_restarts = 0;
}

int radio_rfm69_watchdog_restarts() {
  return watchdog_restarts;
}

int radio_rfm69_setup() {
  if (esp_reset_reason() != ESP_RST_SW) {
    radio_rfm69_reset_hacky_restart();
    radio_rfm69_reset_watchdog_restart();
  }

  if (rfm_watchdog != nullptr) {
    Serial.println("removing old watchdog task");
    vTaskDelete(rfm_watchdog);
    rfm_watchdog = nullptr;
  }

  send_end = send_start = micros();

  xTaskCreateUniversal(
      [](void *unused) {
        while (true) {
          // dalay first execution
          delay(5 * 60000 /* poke every 5 minutes*/);
          const auto now = micros();
          const auto elapsed = now - send_end;
          Serial.printf("loop %lu %lu %lu\n", now, send_end, elapsed);
          if (elapsed > WATCHDOG_LIMIT) {
            radio_rfm69_reset_hacky_restart();
            ++watchdog_restarts;
            Serial.println("watchdog: rfm69 deadlock in send: restart ESP");
            // ESP.restart();
          }
        }
        vTaskDelete(nullptr);
      },
      "rfm_watchdog", 1024, nullptr, 3, &rfm_watchdog, -1);

  const uint16_t myNodeId = ESP.getEfuseMac() & 0xFFFF;
#  if RADIO_A
  if (!radio.initialize(RF69_433MHZ, myNodeId, NETWORKID)) {
    Serial.println("failed radio");
    return 1;
  }
  radio.setHighPower(); // ALWAYS for HCW or experience mysterious  failures
  // Serial.println("Start calibration");
  // radio.rcCalibration();
  // Serial.println("Calibration done");
  // Serial.printf("PowerLevel = %d\n", radio.getPowerLevel());
  const auto boot_reason = esp_reset_reason();
  if (boot_reason != ESP_RST_SW) {
    // if reset reason is NOT software, set variable to 0
    // this should ensure we don't hit expected value by chance
    // one day whan all bits align
    hacky_restart = 0;
  }
#    if 0
  if (hacky_restart != EXPECTED_HACKY_RESTART) {
    Serial.println("Invoking HACKY RESTART!");
    hacky_restart = EXPECTED_HACKY_RESTART;
    ESP.restart();
  } else {
    Serial.println("HACKY RESTART already invoked");
  }
#    endif
  return 0;
#  else
  int state = radio.begin();
  Serial.printf("begin: %d\n", state);
  state |= radio.setOutputPower(20, true);
  Serial.printf("out: %d\n", state);
  uint8_t syncWord[2] = {
      0x96 /* change default SYN packet */, NETWORKID /* NetworkID */
  };
  state |= radio.setSyncWord(syncWord, sizeof(syncWord));
  Serial.printf("sync: %d\n", state);
  // packet mode and variable encoding is default
  // state |= radio.packetMode();
  // Serial.printf("packet: %d\n", state);
  // state |= radio.variablePacketLengthMode();
  // Serial.printf("varlen: %d\n", state);

  // state |= radio.setNodeAddress(myNodeId);
  // Serial.printf("addr: %d\n", state);
  // state |= radio.setDataShaping(0);
  // state |= radio.packetMode();
  Serial.printf("chipID: %d\n", radio.getChipVersion());
  Serial.printf("temo: %d\n", radio.getTemperature());
  return state;
#  endif
}

int radio_rfm69_send_all(const uint8_t *data, size_t len) {
#  if RADIO_A
  // Serial.printf("mode=%d, %d\n", radio._mode, RF69_MODE_RX);
  // Serial.printf("len=%d\n", radio.PAYLOADLEN);
  // Serial.printf("rssi=%d < %d", radio.readRSSI(), CSMA_LIMIT);
  // if (_mode == RF69_MODE_RX && PAYLOADLEN == 0 && readRSSI() < CSMA_LIMIT) //
  // if signal stronger than -100dBm is detected assume channel activity
  send_start = micros();
  radio.send(TARGET_ID, data, len, false);
  send_end = micros();
  return 0;
#  else
  return radio.transmit(const_cast<uint8_t *>(data), len, TARGET_ID);
#  endif
}

int radio_rfm69_id(uint8_t *data) {
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