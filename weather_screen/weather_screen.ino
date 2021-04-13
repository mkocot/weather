#include "config.h"

#include <ESP8266WiFi.h> /* wifi */
#include <WiFiUdp.h> /* UDP */
#include <time.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>


#define SCREEN_WIDTH 128 // OLED display width, in pixels
#define SCREEN_HEIGHT 32 // OLED display height, in pixels
#define OLED_RESET     -1 //4 // Reset pin # (or -1 if sharing Arduino reset pin)
#define SCREEN_ADDRESS 0x3C ///< See datasheet for Address; 0x3D for 128x64, 0x3C for 128x32
Adafruit_SSD1306 display;

WiFiUDP Udp;
#define REPLY_PACKET_SIZE 32
#define HEADER_SIZE 8
#define VOLT_THRESHOLD 2000


uint8_t replyPacket[REPLY_PACKET_SIZE];
uint8_t image[512 + HEADER_SIZE + 6];
#define UDP_PORT 9696
/* broadcast */
#define UDP_ADDR 0xFFFFFFFF

#define BROADCAST_INTERVAL 30000
int lastBroadcastTimestamp = -BROADCAST_INTERVAL; /* ensure this will fire ASAP */

int now = 0;

void setupWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_NAME, WIFI_PASS);
  Serial.print("Connecting");
  while (WiFi.status() != WL_CONNECTED) {   
    delay(500);
    Serial.print(".");
  }                    
  Serial.println();
                     
  Serial.print("Connected, IP address: ");
  Serial.println(WiFi.localIP());
  memset(replyPacket, 0, REPLY_PACKET_SIZE);
  replyPacket[0] = 'W';
  replyPacket[1] = 1;
  WiFi.macAddress(&replyPacket[2]);
  Udp.begin(UDP_PORT); // start listening
}

void setupSerial() {
//  Serial.begin(9600);
  Serial.begin(115200);
  while(!Serial) {
    delay(100);
  }
}

void setupScreen() {
  Wire.begin(5, 4);
  display = (SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);
  // SSD1306_SWITCHCAPVCC = generate display voltage from 3.3V internally
  if(!display.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS)) {
    Serial.println(F("SSD1306 allocation failed"));
    for(;;); // Don't proceed, loop forever
  }

  // Show initial display buffer contents on the screen --
  // the library initializes this with an Adafruit splash screen.
  display.display();
  delay(2000); // Pause for 2 seconds

  // Clear the buffer
  display.clearDisplay();
  display.display();
}

void setup() {
  setupSerial();
  setupWiFi();
  setupScreen();
}

void notifyBroker() {
  /* broadcast every 10s */
//  Serial.println("notifyBroker: start");
  if (now - lastBroadcastTimestamp < BROADCAST_INTERVAL) {
//    Serial.println("skip broadcast");
    return; 
  }
  lastBroadcastTimestamp = now;
  int idx = HEADER_SIZE;
  Udp.beginPacket(UDP_ADDR, UDP_PORT);
  replyPacket[idx++] = 1;

  /* send screen size */
  replyPacket[idx++] = 0x06;
  replyPacket[idx++] = 0;
  replyPacket[idx++] = SCREEN_WIDTH;
  replyPacket[idx++] = 0;
  replyPacket[idx++] = SCREEN_HEIGHT;
  
  Udp.write(replyPacket, REPLY_PACKET_SIZE);
  Udp.endPacket();
  delay(100);
//  Serial.println("notifyBroker: end");
}

void waitForData() {
  int packetSize = Udp.parsePacket();
  if (packetSize < sizeof(image)) {
    /* Ignore packet: too short */
//    Serial.println("short");
    return;
  }

  // Unable to check DESTINATION ADDR, source addr is uselessn;
  
  int fetch = Udp.read(image, sizeof(image));
  /* messages from broker to client should have lower 'w' */
  if (image[0] != 'w' && image[1] != 1) {
    /* Ignore packet: invalid version or magic */
        Serial.println("header");
    return;
  }
  /* is target mac our mac? */
  if (memcmp(replyPacket+2, image+2, 6)) {
    /* Ignore packet: ID missmatch */
    Serial.println("ID");
    return;
  }
  if (image[8] != 1) {
    /* Ignore packet: invalid array count
     * Currently only 1 image per packet is supported */
    Serial.println("!= array count");
    return;
  }
  /* let's reserver 0x07 as SHOW_IMAGE */
  if (image[9] != 0x07) {
    /* Ignore packet: invalid data ID */
    Serial.println("!= data id");
    return;
  }
  if (image[11] != SCREEN_WIDTH) {
    /* Ignore packet: invalid width */
    Serial.println("!= WIDTH");
    return;
  }
  if (image[13] != SCREEN_HEIGHT) {
    /* Ignore packet: invalid height */
    Serial.println("!= HEIGHT");
    return;
  }
  Serial.println("ok");
  display.clearDisplay();
  /* +6 as we get 'sensors' count, sensor_id, width, height */
  display.drawBitmap(0, 0, image + HEADER_SIZE + 6, SCREEN_WIDTH, SCREEN_HEIGHT, WHITE);
  display.display();
}

void drainUdp() {
  while(Udp.read(image, sizeof(image))) {
  }
}
void showImage() {}

void loop() {
  now = millis();
  notifyBroker();
  waitForData();
  showImage();
  delay(400);
}
