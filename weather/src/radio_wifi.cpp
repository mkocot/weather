#include "config.hpp"
#include "radio_wifi.hpp"

#if W_RADIO_MODE == W_RADIO_WIFI

#include <ESP8266WiFi.h> /* wifi */
#include <WiFiUdp.h>     /* UDP */

#define UDP_PORT 9696

#define W_MAX_ADDR 0xFFFFFFFF
/* broadcast ADDR */
#define UDP_ADDR W_MAX_ADDR

/* see: https://tools.ietf.org/html/rfc6890
 * 255.255.255.255/32 Limited Broadcast IP would be good but not working
 * 127.127.127.127/32 is reserved for loobpack, but we use broadcast, and it's works */
#define W_WIFI_IP      IPAddress(10, 'W', 'T', 'R')
#define W_WIFI_NETMASK IPAddress(255, 0, 0, 0)
#define W_WIFI_GATEWAY W_WIFI_IP
#define W_WIFI_MULTICAST      IPAddress(239, 'W', 'T', 'R')
/* 25 tries by 400ms interval = 10s */
#define W_WIFI_MAX_TRIES 25

WiFiUDP Udp;

int radio_wifi_id(uint8_t *data) {
  WiFi.macAddress(data);
  return 0;
}

int radio_wifi_setup() {
  int i = 0;
  WiFi.mode(WIFI_STA);

  /* assign static IP */
  if (!WiFi.config(W_WIFI_IP, W_WIFI_GATEWAY, W_WIFI_NETMASK)) {
#if W_VERBOSE
    Serial.println("STA Failed to configure");
#endif
  }
  WiFi.begin(WIFI_NAME, WIFI_PASS);
#if W_VERBOSE
  Serial.print("Connecting");
#endif
  while (WiFi.status() != WL_CONNECTED) {
    delay(400);
#if W_VERBOSE
    Serial.print(".");
#endif
    blink();
    
    if (++i >= W_WIFI_MAX_TRIES) {
#if W_VERBOSE
      Serial.println("Wifi Failed. Emergency exit");
#endif
      exitError();
    }
  }
#if W_VERBOSE
  Serial.println();
  
  Serial.print("Connected, IP address: ");
  Serial.println(WiFi.localIP());
#endif
    return 0;
}

int radio_wifi_send_all(const uint8_t* data, size_t len) {
  #if W_WIFI_PACKET == W_WIFI_PACKET_BROADCAST
  Udp.beginPacket(UDP_ADDR, UDP_PORT);
  #else
  Udp.beginPacketMulticast(W_WIFI_MULTICAST, UDP_PORT, W_WIFI_IP, 1 /*TTL*/);
  #endif
  Udp.write(data, len);
  auto status = Udp.endPacket() == 0;
  // radio_rfm69_send_all(replyPacket, REPLY_PACKET_SIZE);
  /* NOTE(m): Required to SEND data over networt */
  delay(300);
  return status;
}
#endif