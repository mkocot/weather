#include <ESP8266WiFi.h> /* wifi */
#include <Adafruit_BME280.h> /* include Adafruit library for BMP280 sensor */
#include <WiFiUdp.h> /* UDP */
#include "config.h"

Adafruit_BME280  bme;
// TODO: Put correct value
#define SEALEVELPRESSURE_HPA (1013.25)
unsigned long delayTime;


WiFiUDP Udp;
#define REPLY_PACKET_SIZE 32
#define HEADER_SIZE 8
#define VOLT_THRESHOLD 2000


uint8_t replyPacket[REPLY_PACKET_SIZE];
#define UDP_PORT 9696
/* broadcast */
#define UDP_ADDR 0xFFFFFFFF

ADC_MODE(ADC_VCC); /* init input voltage mesure */
uint32_t inVolt;

void blink() {
  #if 1
  digitalWrite(LED_BUILTIN,!digitalRead(LED_BUILTIN));
  #endif
}

void setupWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_NAME, WIFI_PASS);
  Serial.print("Connecting");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    blink();
  }
  Serial.println();

  Serial.print("Connected, IP address: ");
  Serial.println(WiFi.localIP());
  // Enable light sleep?
  // WiFi.setSleepMode(WIFI_LIGHT_SLEEP);
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
      blink();
    }
  }

  // For more details on the following scenarious, see chapter
  // 3.5 "Recommended modes of operation" in the datasheet
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
  // change to 5mins
  delayTime = 300000;
}

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW); /* enable LED */
  Serial.begin(115200);
  while (!Serial) {
    blink();
    delay(100); // wait for serial port to connect. Needed for native USB
  }

  setupBME280();
  setupWiFi();
  digitalWrite(LED_BUILTIN, HIGH); /* disable LED */

  /* clear packet */
  memset(replyPacket, 0, REPLY_PACKET_SIZE);
  /* setup header */
    
  /* just magic 'id' */
  replyPacket[0] = 'W';
  /* version */
  replyPacket[1] = 1;
    
  /* store device MAC 2..7 */
  WiFi.macAddress(&replyPacket[2]);
}

void loop() {
  // TODO: Check this in setup()
  // We are using deepSleep so every iteration starts with setup()
  inVolt = ESP.getVcc();
  // USB powered: inVolt ~ 3000
  // We might want detect somehow if battery powered or USB powered
  // use GPIO jumper?
  if (inVolt < VOLT_THRESHOLD) {
    ESP.deepSleep(ESP.deepSleepMax());
    return;
  }
  // Only needed in forced mode! In normal mode, you can remove the next line.
  bme.takeForcedMeasurement(); // has no effect in normal mode

  sendValues();
  printValues();

  //delay(delayTime);
  Serial.println("going into deep sleep mode");
  ESP.deepSleep(delayTime * 1000); 
}

void sendValues() {
  static union {
    int32_t ival;
    uint32_t uval;
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
    
  /* 0x04 time (deprecated) */

  replyPacket[idx++] = 0x05; /* voltage */
  f2bytes.uval = inVolt;
  replyPacket[idx++] = f2bytes.bval[0];
  replyPacket[idx++] = f2bytes.bval[1];
  replyPacket[idx++] = f2bytes.bval[2];
  replyPacket[idx++] = f2bytes.bval[3];

  Udp.write(replyPacket, REPLY_PACKET_SIZE);
  Udp.endPacket();
  Serial.println("delay to send packet");
  delay(2000);
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
  
  Serial.print("inVolt = ");
  Serial.print(inVolt);
  Serial.println(" mV");

  Serial.println();
}
