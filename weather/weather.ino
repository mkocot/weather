#include <ESP8266WiFi.h> /* wifi */
#include <Adafruit_BME280.h> /* include Adafruit library for BMP280 sensor */
#include <WiFiUdp.h> /* UDP */
#include "config.h"

Adafruit_BME280  bme;


WiFiUDP Udp;
#define REPLY_PACKET_SIZE 32
#define HEADER_SIZE 8
#define VOLT_THRESHOLD 2000
// Interval in us: 600s (10m)
#define W_REPORT_INTERVAL 600000000


uint8_t replyPacket[REPLY_PACKET_SIZE];
#define UDP_PORT 9696

#define W_MAX_ADDR 0xFFFFFFFF
/* broadcast ADDR */
#define UDP_ADDR W_MAX_ADDR

/* see: https://tools.ietf.org/html/rfc6890
 * 255.255.255.255/32  Limited Broadcast IP */
#define W_WIFI_IP W_MAX_ADDR
#define W_WIFI_NETMASK W_MAX_ADDR
#define W_WIFI_GATEWAY W_MAX_ADDR

ADC_MODE(ADC_VCC); /* init input voltage mesure */
uint32_t inVolt;

#define W_SILENT (1)
#define W_BLINK (0)

#if W_BLINK
void blink() {
  digitalWrite(LED_BUILTIN,!digitalRead(LED_BUILTIN));
}

void setupLED() {
  pinMode(LED_BUILTIN, OUTPUT);
}

void enableLED() {
  digitalWrite(LED_BUILTIN, LOW);
}

void disableLED() {
  digitalWrite(LED_BUILTIN, HIGH);
}
#else
#define blink() do {} while(0)
#define setupLED() do {} while(0)
#define enableLED() do{} while(0)
#define disableLED() do{} while(0)
#endif

void setupWiFi() {
  WiFi.mode(WIFI_STA);

  /* assign static IP */
  if (!WiFi.config(W_WIFI_IP, W_WIFI_GATEWAY, W_WIFI_NETMASK)) {
#if! W_SILENT
    Serial.println("STA Failed to configure");
#endif
  }
  WiFi.begin(WIFI_NAME, WIFI_PASS);
#if !W_SILENT
  Serial.print("Connecting");
#endif
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
#if !W_SILENT
    Serial.print(".");
#endif
    blink();
  }
#if !W_SILENT
  Serial.println();
  
  Serial.print("Connected, IP address: ");
  Serial.println(WiFi.localIP());
#endif
}

void setupBME280() {
  // Enable i2c device (is this required?)
  Wire.begin(4, 0); // SDA=GPIO4 (D2), SCL=GPIO0 (D3)
  int sesnor_ok = bme.begin(BME280_ADDRESS_ALTERNATE);
  if (!sesnor_ok) {
    while (1) {
#if !W_SILENT
      Serial.println("Could not find a valid BME280 sensor, check wiring!");
#endif
      delay(1000);
      blink();
    }
  }

  // For more details on the following scenarious, see chapter
  // 3.5 "Recommended modes of operation" in the datasheet
  bme.setSampling(Adafruit_BME280::MODE_FORCED,
                  Adafruit_BME280::SAMPLING_X1, // temperature
                  Adafruit_BME280::SAMPLING_X1, // pressure
                  Adafruit_BME280::SAMPLING_X1, // humidity
                  Adafruit_BME280::FILTER_OFF);
}

void setup() {
  setupLED();
  enableLED();
#if !W_SILENT
  Serial.begin(115200);
  while (!Serial) {
    blink();
    /* wait for serial port to connect. Needed for native USB */
    delay(100);
  }
#endif

  setupBME280();
  setupWiFi();

  disableLED();

  /* prepare packet */
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
  /* NOTE: We are using deepSleep so every iteration starts with setup() */
  inVolt = ESP.getVcc();

#if 0
  /* USB powered: inVolt ~ 3000
   * We might want detect somehow if battery powered or USB powered
   * use GPIO jumper? */
  if (inVolt < VOLT_THRESHOLD) {
    ESP.deepSleep(ESP.deepSleepMax());
    return;
  }
#endif
  /* Only needed in forced mode! In normal mode, you can remove the next line. */
  bme.takeForcedMeasurement();

  sendValues();

#if !W_SILENT
  printValues();
  Serial.println("going into deep sleep mode");
#endif

  ESP.deepSleep(W_REPORT_INTERVAL);
  delay(100);
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
  /* NOTE(m): Required to SEND data over networt */
  yield();
}

#define SEALEVELPRESSURE_HPA (1013.25)
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
