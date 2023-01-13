#ifndef W_BME680_H
#  define W_HME680_H

#  include "config.hpp"

#  if W_BME_TYPE == W_BME_680
#    include <Adafruit_BME680.h>
class BME680 {
  Adafruit_BME680 bme;
  uint8_t mAddress{0xFF};

public:
  BME680(int cs, int mosi, int miso, int sck): bme(cs, mosi, miso, sck) {}
  BME680(uint8_t address = BME68X_DEFAULT_ADDRESS): bme(), mAddress(address) {}

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
    // Using oversampling will invalidate temperature (sometimes overshot by
    // 10*C)
    // Anyway.. something is off with this sensor, without filters on temp < 10
    // it will be around 1 - 2 higher
    // const constexpr auto OVERSAMPLING = BME680_OS_16X;
    // bme.setHumidityOversampling(OVERSAMPLING);
    // bme.setTemperatureOversampling(OVERSAMPLING);
    // bme.setPressureOversampling(OVERSAMPLING);
    // bme.setIIRFilterSize(BME680_FILTER_SIZE_7);
    // bme.setODR(BME68X_ODR_1000_MS);
    // NOTE: humidity is ~10 % HIGHER than it should be bme.setGasHeater(0, 0);
    return true;
  }

  bool measure() { return bme.performReading(); }

  float readTemperature() { return bme.temperature; }

  float readPressure() { return bme.pressure; }

  float readHumidity() { return bme.humidity; }

  uint32_t readGas() { return bme.gas_resistance; }
};
#  endif /* W_BME_TYPE == W_BME_680 */
#endif