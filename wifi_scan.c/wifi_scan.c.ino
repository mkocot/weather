/*
    This sketch demonstrates how to scan WiFi networks.
    The API is almost the same as with the WiFi Shield library,
    the most obvious difference being the different file you need to include:
*/

#include <ESP8266WiFi.h> /* wifi */
#include <Adafruit_BME280.h> /* include Adafruit library for BMP280 sensor */
#include <WiFiUdp.h> /* UDP */

#define WIFI_NAME "TP-LINK_FE2E84"
#define WIFI_PASS "LoboToJednakLobo"

Adafruit_BME280  bme;
// TODO: Put correct value
#define SEALEVELPRESSURE_HPA (1013.25)
unsigned long delayTime;


WiFiUDP Udp;
#define REPLY_PACKET_SIZE 32
#define HEADER_SIZE 8

char replyPacket[REPLY_PACKET_SIZE];
#define UDP_PORT 9696
/* broadcast */
#define UDP_ADDR 0xFFFFFFFF

void setupWiFi() {
  WiFi.begin(WIFI_NAME, WIFI_PASS);

  Serial.print("Connecting");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();

  Serial.print("Connected, IP address: ");
  Serial.println(WiFi.localIP());
}

void setupBME280() {
  Serial.println(F("\nBLAH BLAH TEMPERATURE"));

  // Enable i2c device (is this required?)
  Wire.begin(4, 0); // SDA=GPIO4 (D2), SCL=GPIO0 (D3)
  int sesnor_ok = bme.begin(BME280_ADDRESS_ALTERNATE);
  if (!sesnor_ok) {
    while (1) {
      Serial.println("Could not find a valid BME280 sensor, check wiring!");
      delay(1000);
    }
  }

  // For more details on the following scenarious, see chapter
  // 3.5 "Recommended modes of operation" in the datasheet
#if 1
  // weather monitoring
  Serial.println("-- Weather Station Scenario --");
  Serial.println("forced mode, 1x temperature / 1x humidity / 1x pressure oversampling,");
  Serial.println("filter off");
  bme.setSampling(Adafruit_BME280::MODE_FORCED,
                  Adafruit_BME280::SAMPLING_X1, // temperature
                  Adafruit_BME280::SAMPLING_X1, // pressure
                  Adafruit_BME280::SAMPLING_X1, // humidity
                  Adafruit_BME280::FILTER_OFF   );

  // suggested rate is 1/60Hz (1m)
  delayTime = 60000; // in milliseconds
#endif

#if 0
  // humidity sensing
  Serial.println("-- Humidity Sensing Scenario --");
  Serial.println("forced mode, 1x temperature / 1x humidity / 0x pressure oversampling");
  Serial.println("= pressure off, filter off");
  bme.setSampling(Adafruit_BME280::MODE_FORCED,
                  Adafruit_BME280::SAMPLING_X1,   // temperature
                  Adafruit_BME280::SAMPLING_NONE, // pressure
                  Adafruit_BME280::SAMPLING_X1,   // humidity
                  Adafruit_BME280::FILTER_OFF );

  // suggested rate is 1Hz (1s)
  delayTime = 1000;  // in milliseconds
#endif

#if 0
  // indoor navigation
  Serial.println("-- Indoor Navigation Scenario --");
  Serial.println("normal mode, 16x pressure / 2x temperature / 1x humidity oversampling,");
  Serial.println("0.5ms standby period, filter 16x");
  bme.setSampling(Adafruit_BME280::MODE_NORMAL,
                  Adafruit_BME280::SAMPLING_X2,  // temperature
                  Adafruit_BME280::SAMPLING_X16, // pressure
                  Adafruit_BME280::SAMPLING_X1,  // humidity
                  Adafruit_BME280::FILTER_X16,
                  Adafruit_BME280::STANDBY_MS_0_5 );

  // suggested rate is 25Hz
  // 1 + (2 * T_ovs) + (2 * P_ovs + 0.5) + (2 * H_ovs + 0.5)
  // T_ovs = 2
  // P_ovs = 16
  // H_ovs = 1
  // = 40ms (25Hz)
  // with standby time that should really be 24.16913... Hz
  delayTime = 41;
#endif

#if 0
  // gaming
  Serial.println("-- Gaming Scenario --");
  Serial.println("normal mode, 4x pressure / 1x temperature / 0x humidity oversampling,");
  Serial.println("= humidity off, 0.5ms standby period, filter 16x");
  bme.setSampling(Adafruit_BME280::MODE_NORMAL,
                  Adafruit_BME280::SAMPLING_X1,   // temperature
                  Adafruit_BME280::SAMPLING_X4,   // pressure
                  Adafruit_BME280::SAMPLING_NONE, // humidity
                  Adafruit_BME280::FILTER_X16,
                  Adafruit_BME280::STANDBY_MS_0_5 );

  // Suggested rate is 83Hz
  // 1 + (2 * T_ovs) + (2 * P_ovs + 0.5)
  // T_ovs = 1
  // P_ovs = 4
  // = 11.5ms + 0.5ms standby
  delayTime = 12;
#endif

}

void setupTime() {
    /* TODO */
}

void setup() {
  Serial.begin(115200);
  while (!Serial) {
    delay(100); // wait for serial port to connect. Needed for native USB
  }

  setupBME280();
  setupWiFi();
  setupTime();
  /* clear packet */
  memset(replyPacket, 0, REPLY_PACKET_SIZE);
  /* setup header */
    
  /* just magic 'id' */
  replyPacket[0] = 'W';
  /* version */
  replyPacket[1] = 1;
    
  /* store device MAC */
  /* TODO: */
  replyPacket[2] = 0;
  replyPacket[3] = 0;
  replyPacket[4] = 0;
  replyPacket[5] = 0;
  replyPacket[6] = 0;
  replyPacket[7] = 0;
  delay(100);
}

void loop() {
  // Only needed in forced mode! In normal mode, you can remove the next line.
  bme.takeForcedMeasurement(); // has no effect in normal mode

  sendValues();
  printValues();

  delay(delayTime);
}

void sendValues() {
  static union {
    int32_t ival;
    float fval;
    byte bval[4];
  } f2bytes;
  
  int idx = HEADER_SIZE;
  Udp.beginPacket(UDP_ADDR, UDP_PORT);


  /* number of sensors */
  replyPacket[idx++] = 4;

  /* sensor type */
  replyPacket[idx++] = 0x01; /* temperature */
  f2bytes.fval = bme.readTemperature();
  replyPacket[idx++] = f2bytes.bval[0];
  replyPacket[idx++] = f2bytes.bval[1];
  replyPacket[idx++] = f2bytes.bval[2];
  replyPacket[idx++] = f2bytes.bval[3];

  replyPacket[idx++] = 0x02; /* pressure */
  f2bytes.fval = bme.readPressure();
  replyPacket[idx++] = f2bytes.bval[0];
  replyPacket[idx++] = f2bytes.bval[1];
  replyPacket[idx++] = f2bytes.bval[2];
  replyPacket[idx++] = f2bytes.bval[3];

  replyPacket[idx++] = 0x03; /* humidity */
  f2bytes.fval = bme.readHumidity();
  replyPacket[idx++] = f2bytes.bval[0];
  replyPacket[idx++] = f2bytes.bval[1];
  replyPacket[idx++] = f2bytes.bval[2];
  replyPacket[idx++] = f2bytes.bval[3];
    
  replyPacket[idx++] = 0x04; /* time */
  f2bytes.ival = 0;
  replyPacket[idx++] = f2bytes.bval[0];
  replyPacket[idx++] = f2bytes.bval[1];
  replyPacket[idx++] = f2bytes.bval[2];
  replyPacket[idx++] = f2bytes.bval[3];  

  Udp.write(replyPacket, REPLY_PACKET_SIZE);
  Udp.endPacket();
}
void printValues() {
  Serial.print("Temperature = ");
  Serial.print(bme.readTemperature());
  Serial.println(" *C");

  Serial.print("Pressure = ");

  Serial.print(bme.readPressure() / 100.0F);
  Serial.println(" hPa");

  Serial.print("Approx. Altitude = ");
  Serial.print(bme.readAltitude(SEALEVELPRESSURE_HPA));
  Serial.println(" m");

  Serial.print("Humidity = ");
  Serial.print(bme.readHumidity());
  Serial.println(" %");

  Serial.println();
}
