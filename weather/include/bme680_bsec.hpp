#ifndef W_BME680_H
#  define W_HME680_H

#  include "config.hpp"

/* will work fine util it dosn't with deadlock */
#  if W_BSEC

#    include <bsec.h>

class BME680_bsec {
  Bsec bme;
  uint8_t mAddress{0xFF};
void checkStatus() {
  if (bme.status != BSEC_OK) {
    if (bme.status < BSEC_OK) {
      auto output = "BSEC error code : " + String(bme.status);
      Serial.println(output);
      // for (;;)
      //   errLeds(); /* Halt in case of failure */
    } else {
      auto output = "BSEC warning code : " + String(bme.status);
      Serial.println(output);
    }
  }

  if (bme.bme680Status != BME680_OK) {
    if (bme.bme680Status < BME680_OK) {
      auto output = "BME680 error code : " + String(bme.bme680Status);
      Serial.println(output);
      // for (;;)
      //   errLeds(); /* Halt in case of failure */
    } else {
      auto output = "BME680 warning code : " + String(bme.bme680Status);
      Serial.println(output);
    }
  }
}

public:
  BME680_bsec(int cs, int mosi, int miso, int sck): bme(cs, mosi, miso, sck) {}
  BME680_bsec(uint8_t address): bme(), mAddress(address) {}

  bool begin() {
  bme.begin(BME680_I2C_ADDR_SECONDARY, Wire);
  checkStatus();
  bsec_virtual_sensor_t sensor_list[] = {
      // BSEC_OUTPUT_RAW_TEMPERATURE,
      // BSEC_OUTPUT_RAW_PRESSURE,
      // BSEC_OUTPUT_RAW_HUMIDITY,
      BSEC_OUTPUT_RAW_PRESSURE,
      BSEC_OUTPUT_RAW_GAS,
      BSEC_OUTPUT_IAQ,        /* so this is somehow scalled ? */
      BSEC_OUTPUT_STATIC_IAQ, /* unscalled */
      BSEC_OUTPUT_CO2_EQUIVALENT,
      // BSEC_OUTPUT_BREATH_VOC_EQUIVALENT,
      BSEC_OUTPUT_SENSOR_HEAT_COMPENSATED_TEMPERATURE,
      BSEC_OUTPUT_SENSOR_HEAT_COMPENSATED_HUMIDITY,
  };
  bme.updateSubscription(sensor_list,
                         sizeof(sensor_list) / sizeof(bsec_virtual_sensor_t),
                         BSEC_SAMPLE_RATE_ULP);
  checkStatus();
  }

  bool measure() { return bme.run(); }

  float readTemperature() { return bme.temperature; }

  float readPressure() { return bme.pressure; }

  float readHumidity() { return bme.humidity; }

  float readGas() { return bme.gasResistance; }
  float iaq() { return bme.iaq; }
  float staticIaq() { return bme.staticIaq; }
  float co2Equivalent() { return bme.co2Equivalent; }
  uint32_t accuracy() {
      // each value is from 0 to 2 -> mask 0x03 and is uses 2 bits
      // accuracy in order of emited fields
      // 0, 1 - iaq accuracy
      // 2, 3 - static iaq accuracy
      // 4, 5 - co2accuracy
      (bme.iaqAccuracy & 0x03) | ((bme.staticIaqAccuracy & 0x03) << 2) |
          ((bme.co2Accuracy & 0x03) << 4)));
  }
};

#  endif
#endif