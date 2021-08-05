/* Remeber to connect D0 with RST
 * Disconnect when flashing */
#include <ESP8266WiFi.h> /* wifi */
#include <Adafruit_BME280.h> /* include Adafruit library for BMP280 sensor */
#include <WiFiUdp.h> /* UDP */
#include "config.h"

Adafruit_BME280  bme;
WiFiUDP Udp;
ADC_MODE(ADC_VCC); /* init input voltage mesure */
uint32_t inVolt;

#define REPLY_PACKET_SIZE 32
uint8_t replyPacket[REPLY_PACKET_SIZE];

#define HEADER_SIZE 8
#define VOLT_THRESHOLD 2000
/* Interval in us: 600s (10m) */
#define W_REPORT_INTERVAL 600000000
/* Interval in us: 300s (5m) */
#define W_ERROR_SLEEP_INTERVAL (300000000)

#define UDP_PORT 9696

#define W_MAX_ADDR 0xFFFFFFFF
/* broadcast ADDR */
#define UDP_ADDR W_MAX_ADDR

/* see: https://tools.ietf.org/html/rfc6890
 * 255.255.255.255/32 Limited Broadcast IP would be good but not working
 * 127.127.127.127/32 is reserved for loobpack, but we use broadcast, and it's works */
#define W_WIFI_IP      IPAddress(127, 255, 255, 255)
#define W_WIFI_NETMASK IPAddress(255, 255, 255, 255)
#define W_WIFI_GATEWAY W_WIFI_IP
/* 25 tries by 400ms interval = 10s */
#define W_WIFI_MAX_TRIES 25
/* Enable (1) silent mode */
#define W_SILENT (1)
/* Enable (1) LED blinking */
#define W_BLINK (0)

#define W_NOOP do {} while(0)

#if W_SILENT
#define dprintln(...) W_NOOP
#define dprintf(...) W_NOOP
#define dprint(msg) W_NOOP
#else
#define dprintln(...) Serial.println(__VA_ARGS__)
#define dprintf(...) Serial.printf(__VA_ARGS__)
#define dprint(msg) Serial.print(msg)
#endif

#if W_BLINK
void blink() {
  digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));
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
#define blink() W_NOOP
#define setupLED() W_NOOP
#define enableLED() W_NOOP
#define disableLED() W_NOOP
#endif

void exitError() {
  ESP.deepSleep(W_ERROR_SLEEP_INTERVAL);
  delay(100);
}

void setupWiFi() {
  int i = 0;
  WiFi.mode(WIFI_STA);

  /* assign static IP */
  if (!WiFi.config(W_WIFI_IP, W_WIFI_GATEWAY, W_WIFI_NETMASK)) {
    dprintln("STA Failed to configure");
  }
  WiFi.begin(WIFI_NAME, WIFI_PASS);
  dprint("Connecting");
  while (WiFi.status() != WL_CONNECTED) {
    delay(400);
    dprint(".");
    blink();
    
    if (++i >= W_WIFI_MAX_TRIES) {
      dprintln("Wifi Failed. Emergency exit");
      exitError();
    }
  }

  dprintln();
  
  dprint("Connected, IP address: ");
  dprintln(WiFi.localIP());

}

void setupBME280() {
  /* Enable i2c device (is this required?)
   * SDA=GPIO4 (D2), SCL=GPIO0 (D3) */
  Wire.begin(4, 0); 
  int sesnor_ok = bme.begin(BME280_ADDRESS_ALTERNATE);
  if (!sesnor_ok) {
      dprintln("Could not find a valid BME280 sensor, check wiring!");
      blink();
      exitError();
  }

  /* For more details on the following scenarious, see chapter
   * 3.5 "Recommended modes of operation" in the datasheet */
  bme.setSampling(Adafruit_BME280::MODE_FORCED,
                  Adafruit_BME280::SAMPLING_X1, /* temperature */
                  Adafruit_BME280::SAMPLING_X1, /* pressure */
                  Adafruit_BME280::SAMPLING_X1, /* humidity */
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

  printValues();
  dprintln("going into deep sleep mode");

  ESP.deepSleep(W_REPORT_INTERVAL);
  delay(100);
}

void sendValues() {
  static union {
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
  delay(400);
}

#define SEALEVELPRESSURE_HPA (1013.25)

void printValues() {
  dprint("Temperature = ");
  dprint(bme.readTemperature());
  dprintln(" *C");

  dprint("Pressure = ");

  dprint(bme.readPressure() / 100.0F);
  dprintln(" hPa");

  dprint("Approx. Altitude = ");
  dprint(bme.readAltitude(SEALEVELPRESSURE_HPA));
  dprintln(" m");

  dprint("Humidity = ");
  dprint(bme.readHumidity());
  dprintln(" %");
  
  dprint("inVolt = ");
  dprint(inVolt);
  dprintln(" mV");

  dprintln();
}
