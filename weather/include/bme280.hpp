#ifndef W_BME280_H
#define W_BME280_H

#include "config.hpp"

#if W_BME_TYPE == W_BME_280
#  define W_BME_ADDRESS BME280_ADDRESS_ALTERNATE

#  include <Adafruit_BME280.h>

class BME280 {
  Adafruit_BME280 bme;
  uint8_t mAddress{0xFF};

public:
  BME280(int cs, int mosi, int miso, int sck): bme(cs, mosi, miso, sck) {}
  BME280(uint8_t address = W_BME_ADDRESS): bme(), mAddress(address) {}

  bool begin() {
    if (mAddress == 0xFF) {
      SPI.begin();
      if (!bme.begin()) {
        return false;
      }
    } else {
      Wire.begin(4, 0);
      if (!bme.begin(mAddress)) {
        return false;
      }
    }
    /* For more details on the following scenarious, see chapter
     * 3.5 "Recommended modes of operation" in the datasheet */
    bme.setSampling(Adafruit_BME280::MODE_FORCED,
                    Adafruit_BME280::SAMPLING_X1, /* temperature */
                    Adafruit_BME280::SAMPLING_X1, /* pressure */
                    Adafruit_BME280::SAMPLING_X1, /* humidity */
                    Adafruit_BME280::FILTER_OFF);
    return true;
  }
  bool measure() { return bme.takeForcedMeasurement(); }

  float readTemperature() { return bme.readTemperature(); }

  float readPressure() { return bme.readPressure(); }

  float readHumidity() { return bme.readHumidity(); }
};

#endif /* W_BME_TYPE == W_BME_280 */

#endif