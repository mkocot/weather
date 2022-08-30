#include <Arduino.h>
#include <RadioLib.h>
#include <RFM69.h>

// RF69 radio = new Module(SS, D2, RADIOLIB_NC);
RFM69 radio2(SS, D2);

uint8_t packet[62]; // RADIOLIB_RF69_MAX_PACKET_LENGTH];

#define DUMB_FORWARDER_DEBUG (0)

void setup()
{
  // put your setup code here, to run once:
  // Serial.begin(9600);
  Serial.begin(115200);

  radio2.initialize(RF69_433MHZ, 0, 69);
  radio2.setHighPower();

  // radio.begin();
  // radio.setOutputPower(20, true);
  // radio.packetMode();
  // radio.variablePacketLengthMode();
}

void loop()
{
  // Super simple protocol
  // PREFIX[data]\n
  // M diagnostic messages
  // D data

  if (!radio2.receiveDone())
  {
    return;
  }
  Serial.printf("M Got data from %d\r\n", radio2.SENDERID);
  size_t length = radio2.DATALEN;

  if (length >= sizeof(packet))
  {
    Serial.printf("D data too big %d\r\n", length);
    return;
  }
  memcpy(packet, radio2.DATA, length);
  if (radio2.ACKRequested())
  {
    Serial.printf("M sending ACK\r\n");
    radio2.sendACK();
  }

  // put your main code here, to run repeatedly:
  //   auto err = radio.receive(packet, sizeof(packet));

  //   if (err != RADIOLIB_ERR_NONE)
  //   {
  // #if DBUM_FORWARDER_DEBUG
  //     Serial.println("M error during packet receive");
  // #endif
  //     return;
  //   }

  //   size_t const length = radio.getPacketLength(false); /* use last known value */

  //   if (length == 0)
  //   {
  //     return;
  //   }

  // #if DBUM_FORWARDER_DEBUG
  //   Serial.print("M packet lenght");
  //   Serial.println(length);
  //   Serial.print("M ");
  //   Serial.print(packet[0], HEX);
  //   Serial.println(packet[3], HEX);
  // #endif

  Serial.print("D");

  for (size_t i = 0; i < length; i++)
  {
    if (packet[i] < 10)
    {
      Serial.print("0");
    }
    Serial.print(packet[i], HEX);
  }

  Serial.println();
}