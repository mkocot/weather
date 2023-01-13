#ifndef W_CONFIG_H
#define W_CONFIG_H

#include <Arduino.h>

#define W_OTA 1

#define W_RADIO_WIFI 1
#define W_RADIO_RFM69 69
#define W_RADIO_HC12 12

#ifndef W_RADIO_MODE
#define W_RADIO_MODE (W_RADIO_WIFI)
#endif

#define W_WIFI_PACKET_MULTICAST (1)
#define W_WIFI_PACKET_BROADCAST (0)

#ifndef W_WIFI_PACKET
#define W_WIFI_PACKET W_WIFI_PACKET_BROADCAST
#endif

#if W_RADIO_MODE != W_RADIO_WIFI && W_RADIO_MODE != W_RADIO_RFM69 && W_RADIO_MODE != W_RADIO_HC12
#error Invalid W_RADIO_MODE
#endif

#ifndef W_DEBUG
#define W_DEBUG (0)
#endif

/* Enable (1) verbose mode */
#ifndef W_VERBOSE
#define W_VERBOSE (0)
#endif
/* Enable (1) LED blinking */
#ifndef W_BLINK
#define W_BLINK (0)
#endif

#define W_NOOP do {} while(0)

#define VOLT_THRESHOLD  (2000)
/* Interval in us: 600s (10m) */
#define W_REPORT_INTERVAL (600000000)
/* Interval in us: 60s (1m) */
#define W_ERROR_SLEEP_INTERVAL (60000000)

/* reserver 2 bits for protocol */
#define W_BME_PROT_MASK (0x00000003)
#define W_BME_IC_MASK (0xFFFF0000)
#define W_BME_SPI (0x00000001)
#define W_BME_I2C (0x00000000)

#define W_BME_OFF (0x00000000)
#define W_BME_280 (0x28000000)
#define W_BME_680 (0x68000000)

#define W_BME_280_SPI ((W_BME_280) | (W_BME_SPI))
#define W_BME_680_SPI ((W_BME_680) | (W_BME_SPI))


#define W_BSEC (0)

#ifndef W_BME
#define W_BME W_BME_OFF
#endif

#define W_BME_TYPE ((W_BME) & (W_BME_IC_MASK))
#define W_BME_PROT ((W_BME) & (W_BME_PROT_MASK))

// Validate user supplied values
#if !((W_BME_TYPE == W_BME_280) || (W_BME_TYPE == W_BME_680) || (W_BME_TYPE == W_BME_OFF))
#error Invalid W_BME_TYPE (IC)
#endif

#if W_BSEC && W_BME_TYPE && (W_BME_TYPE != W_BME_680)
#error BSEC supported only on BME680
#endif

#if !((W_BME_PROT == W_BME_SPI) || (W_BME_PROT == W_BME_I2C))
#error Invalid W_BME_TYPE (PROT)
#endif

#define W_AC_BATTERY (1)
#define W_AC_DIRECT (2)

#ifndef W_AC_TYPE
#define W_AC_TYPE W_AC_BATTERY
#endif

#if !(W_AC_TYPE == W_AC_BATTERY || W_AC_TYPE == W_AC_DIRECT)
#error Invalid W_AC_TYPE
#endif

#ifndef W_SOIL_MOISTURE
#define W_SOIL_MOISTURE (0)
#endif

#if W_BLINK
#ifndef LED_BUILTIN
#define LED_BUILTIN 2
#endif
static void blink() {
  digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));
}

static void setupLED() {
  pinMode(LED_BUILTIN, OUTPUT);
}

static void enableLED() {
  constexpr auto LED_ON = ESP32 ? HIGH : LOW;
  digitalWrite(LED_BUILTIN, LED_ON);
}

static void disableLED() {
  constexpr auto LED_OFF = ESP32 ? LOW : HIGH;
  digitalWrite(LED_BUILTIN, LED_OFF);
}
#else
#define blink() W_NOOP
#define setupLED() W_NOOP
#define enableLED() W_NOOP
#define disableLED() W_NOOP
#endif


void exitError();


// GUARD


#include "secrets.h"

#if !defined(W_SECRETS_H)
#error Define SECRETS
#endif

#endif
