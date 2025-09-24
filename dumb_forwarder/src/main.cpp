#include <Arduino.h>
#include <crc8.h>

#ifdef RADIO_ESPNOW
#include <WiFi.h>
#include <esp_now.h>
#else
#include <RFM69.h>
#include <RadioLib.h>

#define RADIO_A (1)

// RF69 radio = new Module(SS, D2, RADIOLIB_NC);
RFM69 radio = RFM69(SS, D2, true);

// uint8_t packet[62]; // RADIOLIB_RF69_MAX_PACKET_LENGTH];

volatile bool receivedData = false;
volatile bool enableIrq = true;

IRAM_ATTR void irqPoked() {
  if (!enableIrq) {
    return;
  }
  receivedData = true;
  enableIrq = false;
}

#endif
volatile int receivedData = 0;
uint8_t packet[62];
#define DUMB_FORWARDER_DEBUG (0)

void esp_now_received(const uint8_t *mac, const uint8_t *data, int len)
{
  if (receivedData) {
    // Old data was not used, discard new
    Serial.println("M old data in buffer");
    return;
  }

  memcpy(packet, data, len);
  receivedData = len;
}

void setup() {
  // put your setup code here, to run once:
  // Serial.begin(9600);
  Serial.begin(115200);
  delay(2000);
  Serial.println("SETUP");
#if RADIO_ESPNOW
  WiFi.mode(WIFI_STA);
  Serial.print("M StationID ");
  Serial.println(WiFi.macAddress());
  esp_now_init();
  esp_now_register_recv_cb(esp_now_received);
#else
#if !RADIO_A
  auto ret = radio.begin();
  Serial.printf("M radio.begin() = %d\n", ret);
  // ret = radio.setPromiscuousMode(true);
  // Serial.printf("M radio.begin() = %d\n", ret);
  /* packet mode and variable length is default */
  // transmit power is not required for receiving
  radio.setOutputPower(10, true);
  /* enable filtering, this will remove first byte from
  message */
  // /* 0x2F */ { REG_SYNCVALUE1, 0x2D },      // attempt to make this
  // compatible with sync1 byte of RFM12B lib
  // /* 0x30 */ { REG_SYNCVALUE2, networkID }, // NETWORK ID
  uint8_t syncWord[2] = {
      0x96 /* change default SYN packet */, 0x69 /* NetworkID */
  };
  ret = radio.setSyncWord(syncWord, sizeof(syncWord));
  Serial.printf("M radio.setSyncWord = %d\n", ret);

  // radio.setNodeAddress(0);
  // radio.setBroadcastAddress(0xFF);

  radio.setDio0Action(irqPoked);
  ret = radio.startReceive();
  Serial.printf("M radio.start = %d\n", ret);
  Serial.printf("M chipVersion %d\n", radio.getChipVersion());
  Serial.printf("M temp=%d\n", radio.getTemperature());
#else
  if (radio.initialize(RF69_433MHZ, 0, 0x69)) {
    Serial.println("Radio OK");
  } else {
    Serial.println("Radio BAD");
  }
  radio.setHighPower(true);
  radio.readAllRegs();
#endif
#endif

}
static inline void emitHex(uint8_t val) {
  if (val < 15) {
    Serial.print("0");
  }
  Serial.print(val, HEX);
}

void loop() {
// Super simple protocol
// PREFIX[data]\n
// M diagnostic messages
// D length data (data and length in hex, no space between data and length)
// length is SINGLE byte
#if RADIO_ESPNOW
  if (!receivedData) {
    return;
  }
    #if 1
    uint8_t version = 2 << 4;
    Serial.write(version);
    uint8_t size = receivedData << 2;
    Serial.write(size);

    Serial.write(packet, receivedData);

    uint8_t payload_crc8 = crc8(CRC8_POLY_DVB_S2, 0x00, &version, 1);
    payload_crc8 = crc8(CRC8_POLY_DVB_S2, payload_crc8, &size, 1);
    payload_crc8 = crc8(CRC8_POLY_DVB_S2, payload_crc8, packet, receivedData);
    Serial.write(payload_crc8);

    #else
    Serial.print("D");
    emitHex(receivedData);

    // NOTE: RadioLib emits first byte as TARGET_ID (0)
    // probably, as this is target from sender

    for (size_t i = 0; i < receivedData; i++) {
      emitHex(packet[i]);
    }
    #endif

    Serial.println();
    Serial.flush();

    receivedData = 0;
#else
#if RADIO_A
  if (!radio.receiveDone()) {
    return;
  }

  Serial.print("M Got data from ");
  Serial.print(radio.SENDERID);
  Serial.print(" RSSI=");
  Serial.println(radio.RSSI);

  Serial.print("M length=");
  Serial.println(radio.DATALEN);

  size_t length = radio.DATALEN;

  if (radio.ACKRequested()) {
    Serial.println("M sending ACK");
    radio.sendACK();
  }

  Serial.print("D");
  emitHex(length);

  // NOTE: RadioLib emits first byte as TARGET_ID (0)
  // probably, as this is target from sender
  for (size_t i = 0; i < length; ++i) {
    emitHex(radio.DATA[i]);
  }
  Serial.println();

#elif 0

  if (!receivedData) {
    delay(0);
    return;
  }

  // reset flag
  receivedData = false;
  Serial.println("M PokedByIrq");
  auto err = radio.readData(packet, sizeof(packet));

  if (err == RADIOLIB_ERR_NONE) {
    // Packet should never be aobove 64/61 bytes, but just to be sure in case
    // of some weired issue
    const auto length =
        radio.getPacketLength(false) & 0xFF; /* use last known value */

    Serial.print(F("M RSSI: "));
    Serial.println(radio.getRSSI());

    Serial.print("M Got data: ");
    Serial.println(length);

    Serial.print("D");
    emitHex(length);

    // NOTE: RadioLib emits first byte as TARGET_ID (0)
    // probably, as this is target from sender

    for (size_t i = 0; i < length; i++) {
      emitHex(packet[i]);
    }
    Serial.println();

  } else if (err == RADIOLIB_ERR_CRC_MISMATCH) {
    Serial.println("M invalid CRC");
  } else {
    Serial.println("M error during packet receive");
  }
  radio.startReceive();
  // start listening on intrrupts
  enableIrq = true;
#else
  if (!radio.receiveDone()) {
    return;
  }
  Serial.println("GOT PACKET!");
#endif
#endif
}