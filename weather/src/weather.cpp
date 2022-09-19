
#include "config.hpp"
#include "radio.hpp"
#include <wtocol.hpp>

#if W_DEBUG
#  define DPRINT(x) Serial.print(x)
#  define DPRINTLN(x) Serial.println(x)
#else
#  define DPRINT(x) W_NOOP
#  define DPRINTLN(x) W_NOOP
#endif

#if W_BME_TYPE != W_BME_OFF

#  if W_BME_TYPE == W_BME_280
#    include <Adafruit_BME280.h> /* include Adafruit library for BMP280 sensor */
#    define W_BME_ADDRESS BME280_ADDRESS_ALTERNATE
Adafruit_BME280 bme;

static void setupBME280() {
  /* Enable i2c device (is this required?)
   * SDA=GPIO4 (D2), SCL=GPIO0 (D3) */
  Wire.begin(4, 0);
  int sesnor_ok = bme.begin(W_BME_ADDRESS);
  if (!sesnor_ok) {
#    if W_VERBOSE
    Serial.println("Could not find a valid BME280 sensor, check wiring!");
#    endif
    blink();
#    if !W_DEBUG
    exitError();
#    endif
  }

  /* For more details on the following scenarious, see chapter
   * 3.5 "Recommended modes of operation" in the datasheet */
  bme.setSampling(Adafruit_BME280::MODE_FORCED,
                  Adafruit_BME280::SAMPLING_X1, /* temperature */
                  Adafruit_BME280::SAMPLING_X1, /* pressure */
                  Adafruit_BME280::SAMPLING_X1, /* humidity */
                  Adafruit_BME280::FILTER_OFF);
}
#  else
#    if 1
#      include <bsec.h>
Bsec bme;
#    else
#      include <Adafruit_BME680.h> /* include Adafruit library for BMP280 sensor */
#      define W_BME_ADDRESS 0x76
// 119
// Adafruit_BME680 bmex(SS, MOSI, MISO, SCK);
// I2C
Adafruit_BME680 bme = {};
#    endif
static void checkStatus() {
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
static float waterSatDensity(float temp) {
		const auto rho_max = (6.112* 100 * exp((17.62 * temp)/(243.12 + temp)))/(461.52 * (temp + 273.15));
		return rho_max;
}

struct state {
  time_t next_send_values;
  time_t next_read_sensor;
};
state state;
static void setupBME280() {
  state.next_read_sensor = millis() + 30000;

  const constexpr auto OVERSAMPLING = BME680_OS_16X;
  Serial.println("Enabling TheWire");
  Wire.begin();

  bme.begin(BME680_I2C_ADDR_SECONDARY, Wire);
  checkStatus();
  bsec_virtual_sensor_t sensor_list[] = {
      // BSEC_OUTPUT_RAW_TEMPERATURE,
      // BSEC_OUTPUT_RAW_PRESSURE,
      // BSEC_OUTPUT_RAW_HUMIDITY,
      BSEC_OUTPUT_RAW_PRESSURE,
      BSEC_OUTPUT_RAW_GAS,
      BSEC_OUTPUT_IAQ, /* so this is somehow scalled ? */
      BSEC_OUTPUT_STATIC_IAQ, /* unscalled */
      BSEC_OUTPUT_CO2_EQUIVALENT,
      // BSEC_OUTPUT_BREATH_VOC_EQUIVALENT,
      BSEC_OUTPUT_SENSOR_HEAT_COMPENSATED_TEMPERATURE,
      BSEC_OUTPUT_SENSOR_HEAT_COMPENSATED_HUMIDITY,
  };
  bme.updateSubscription(
      sensor_list, sizeof(sensor_list) / sizeof(bsec_virtual_sensor_t),
      BSEC_SAMPLE_RATE_ULP);
  checkStatus();
  // bsec.setConfig
#    if 0
  bme.setHumidityOversampling(OVERSAMPLING);
  bme.setTemperatureOversampling(OVERSAMPLING);
  bme.setPressureOversampling(OVERSAMPLING);
  bme.setIIRFilterSize(BME680_FILTER_SIZE_7);
  bme.setODR(BME68X_ODR_NONE);
  bme.setGasHeater(0, 0);
  bme.begin();
#    endif
  Serial.println("BME setup done");
}
#  endif /* W_BME_TYPE */
#endif   /* W_BME_TYPE != W_BME_OFF */

#if ESP8266 && !W_SOIL_MOISTURE
ADC_MODE(ADC_VCC); /* init input voltage mesure */
#endif

uint32_t inVolt;

auto replyPacketNew = SensorsPacketizer<
#if W_BME_TYPE
    VoltageSensor, PressureSensor, HumiditySensor, TemperatureSensor
#  if W_BME_TYPE == W_BME_680
    ,
    GasSensor
#  endif /* W_BME_TYPE == W_BME_680 */
#endif   /* W_BME_TYPE */
#if W_SOIL_MOISTURE
#  if W_BME_TYPE
    ,
#  endif
    SoilMoisture
#endif
    >();


static int readSoilMoisture();
static int readSoilMoisture() {
#if ESP32
  const auto analogValue = analogRead(4);
  Serial.println(analogValue);
  return 0;
#else
  const constexpr auto IN_AIR = 645.0F;
  // value for emerged in water until white line
  const constexpr auto IN_WATER = 268.0F;
  // value for emerged in water until 'V'
  // difference is not big (3% and 97 vs 100 doesn't matter)
  // const constexpr auto IN_WATER_HALF = 276.0F;
  // const constexpr auto SCALE = 1.0F / (IN_WATER - IN_AIR);

  const auto analogValue = analogRead(A0);
  // const auto moistureLevel = (analogValue - IN_AIR) * SCALE;

  const auto moistureLevel = map(analogValue, IN_AIR, IN_WATER, 0, 100);
  return constrain(moistureLevel, 0, 100);
#endif
}

static void printValues();

static void sendValues();

void setup() {
  setupLED();
  enableLED();
#if W_VERBOSE
  Serial.begin(115200);
  // Serial.begin(9600);
  while (!Serial) {
    blink();
    /* wait for serial port to connect. Needed for native USB */
    delay(100);
  }
#endif
#if W_BME_TYPE != W_BME_OFF
  setupBME280();
#endif

  if (radio_setup()) {
#if W_VERBOSE
    Serial.println("setup fialed");
#endif
  }

  disableLED();
  radio_id(&replyPacketNew.mBytes[2]);
}

static int batteryVoltage() {
#if W_SOIL_MOISTURE
  return 0;
#endif
#if ESP32
  return 3300;
#else
  return ESP.getVcc();
#endif
}

void loop() {
  /* NOTE: We are using deepSleep so every iteration starts with setup() */
  inVolt = batteryVoltage();
#if 0
  Serial.println(__LINE__);
  /* USB powered: inVolt ~ 3000
   * We might want detect somehow if battery powered or USB powered
   * use GPIO jumper? */
  if (inVolt < VOLT_THRESHOLD) {
    ESP.deepSleep(ESP.deepSleepMax());
    return;
  }
#endif
/* Only needed in forced mode! In normal mode, you can remove the next line. */
#if W_BME_TYPE == W_BME_280
  bme.takeForcedMeasurement();
#elif W_BME_TYPE == W_BME_680
    bme.run();
#endif

  sendValues();

#if W_VERBOSE
  printValues();
#endif

#if W_DEBUG
// TODO: air quality requires poling very 300s (in ULP mode)
// for now just ask once in minute
delay(299000);
// delay(3000);
  // delay(10000);
#else
#  if W_AC_TYPE == W_AC_DIRECT
  delay(W_REPORT_INTERVAL);
#  else
#    if W_VERBOSE
  Serial.println("going into deep sleep mode");
#    endif
  ESP.deepSleep(W_REPORT_INTERVAL);
  delay(100);
#  endif /* W_AC_TYPE */
#endif   /* W_DEBUG */
}



static void sendValues() {
#if W_BME_TYPE == W_BME_280
  replyPacketNew.set<TemperatureSensor>(bme.readTemperature());
  replyPacketNew.set<PressureSensor>(bme.readPressure());
  replyPacketNew.set<HumiditySensor>(bme.readHumidity());
  replyPacketNew.set<VoltageSensor>(inVolt);
#elif W_BME_TYPE == W_BME_680
  replyPacketNew.set<TemperatureSensor>(bme.temperature);
  replyPacketNew.set<PressureSensor>(bme.pressure);
  replyPacketNew.set<HumiditySensor>(bme.humidity);
  // For now ignore voltage
  replyPacketNew.set<VoltageSensor>(inVolt);
  replyPacketNew.set<GasSensor>(
    GasSensor(bme.gasResistance,
              bme.iaq,
              bme.staticIaq,
              bme.co2Equivalent,
              // each value is from 0 to 2 -> mask 0x03 and is uses 2 bits
              // accuracy in order of emited fields
              // 0, 1 - iaq accuracy
              // 2, 3 - static iaq accuracy
              // 4, 5 - co2accuracy
              (bme.iaqAccuracy & 0x03) 
              | ((bme.staticIaqAccuracy & 0x03) << 2) 
              | ((bme.co2Accuracy & 0x03) << 4)
              )
  );
    // bme.staticIaq,
    // bme.iaq,
    // bme.co2Equivalent
    // });
#else
#  error Bad sensor
#endif

#if W_SOIL_MOISTURE
  replyPacketNew.set<SoilMoisture>(readSoilMoisture());
#endif

  if (radio_send_all(replyPacketNew.mBytes, sizeof(replyPacketNew.mBytes))) {
#if W_VERBOSE
    Serial.println("send_fialed");
#endif
  }
  // radio_rfm69_send_all(replyPacket, REPLY_PACKET_SIZE);
  /* NOTE(m): Required to SEND data over networt */
  delay(300);
  yield();
}

static void printValues() {
#if W_BME_TYPE == W_BME_280
  Serial.print("Temperature = ");
  Serial.print(bme.readTemperature());
  Serial.println(" *C");

  Serial.print("Pressure = ");

  Serial.print(bme.readPressure() / 100.0F);
  Serial.println(" hPa");

  Serial.print("Humidity = ");
  Serial.print(bme.readHumidity());
  Serial.println(" %");

  Serial.print("inVolt = ");
  Serial.print(inVolt);
  Serial.println(" mV");

#elif W_BME_TYPE == W_BME_680
  Serial.print("Temperature = ");
  Serial.print(bme.temperature);
  Serial.println(" *C");

  Serial.print("Pressure = ");

  Serial.print(bme.pressure / 100.0F);
  Serial.println(" hPa");

  Serial.print("Humidity = ");
  Serial.print(bme.humidity);
  Serial.println(" %");

  // Serial.print("bVoc = ");
  // Serial.print(bme.breathVocEquivalent);
  // Serial.print(" acc ");
  // Serial.print(bme.breathVocAccuracy);
  // Serial.println();

  Serial.print("co2 = ");
  Serial.print(bme.co2Equivalent);
  Serial.print(" acc ");
  Serial.print(bme.co2Accuracy);
  Serial.println();

  // Serial.print("compgas = ");
  // Serial.print(bme.compGasValue);
  // Serial.print(" acc ");
  // Serial.print(bme.compGasAccuracy);
  // Serial.println();

  Serial.print("gas% = ");
  Serial.print(bme.gasPercentage);
  Serial.print(" acc ");
  Serial.print(bme.gasPercentageAcccuracy);
  Serial.println();

  Serial.print("iaq = ");
  Serial.print(bme.iaq);
  Serial.print(" acc ");
  Serial.print(bme.iaqAccuracy);
  Serial.println();

  // const auto R_gas = bme.gasResistance;
  // const constexpr auto slope = 0.03;
  // const auto rho_max = waterSatDensity(bme.temperature);
  // const auto hum_abs = bme.humidity * 10 * rho_max;
  // const auto comp_gas = R_gas * exp(slope * hum_abs);

  // Serial.print("iaq (custom) = ");
  // Serial.print(comp_gas);
  // Serial.print(" raw ");
  // Serial.print(R_gas);
  // Serial.println();

  Serial.print("staticiaw ");
  Serial.print(bme.staticIaq);
  Serial.print(" acc ");
  Serial.print(bme.staticIaqAccuracy);
  Serial.println();
#else
#  error Whoops
#endif
  Serial.println();
}
