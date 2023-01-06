
#include "config.hpp"
#include "radio.hpp"
#include <TaskScheduler.h>
#include <wtocol.hpp>

#include <AsyncElegantOTA.h>
#include <AsyncTCP.h>
#include <ESPAsyncWebServer.h>
#include <WiFi.h>

struct {
  time_t last_send{0};
  time_t last_send_end{0};
  time_t last_read{0};
  time_t last_read_end{0};
  int radio_statue{0};
  int radio_send{0};
} status;

AsyncWebServer server(80);
#define W_BSEC (0)
static void handle_read_sensor();
static void handle_send_message();

// Read sensor once per 5 minutes (if 680) or 10minutes (if 280)
const constexpr auto READ_INTERVAL =
    W_BME_TYPE == W_BME_680 ? 300000 : W_REPORT_INTERVAL / 1000;
// send interval is equal to read interval on 280, or 1min on 680
const constexpr auto SEND_INTERVAL =
    W_BME_TYPE == W_BME_680 ? READ_INTERVAL / 2 : READ_INTERVAL;

Scheduler scheduler;
Task task_read_sensor(READ_INTERVAL, TASK_FOREVER, handle_read_sensor,
                      &scheduler, true);
// Send message once overy 2minutes
Task task_send_message(SEND_INTERVAL, TASK_FOREVER, handle_send_message,
                       &scheduler, true);

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
#    if W_BSEC
#      include <bsec.h>
Bsec bme;
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
#    else
#      include <Adafruit_BME680.h> /* include Adafruit library for BMP280 sensor */
#      define W_BME_ADDRESS 0x76
// 119
// Adafruit_BME680 bmex(SS, MOSI, MISO, SCK);
// I2C
Adafruit_BME680 bme = {};
#    endif
static float waterSatDensity(float temp) {
  const auto rho_max = (6.112 * 100 * exp((17.62 * temp) / (243.12 + temp))) /
                       (461.52 * (temp + 273.15));
  return rho_max;
}

static void setupBME280() {
  Serial.println("Enabling TheWire");
  Wire.begin();
#    if W_BSEC
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
  // bsec.setConfig
#    else
  bme.begin();
  // Using oversampling will invalidate temperature (sometimes overshot by 10*C)
  // const constexpr auto OVERSAMPLING = BME680_OS_16X;
  // bme.setHumidityOversampling(OVERSAMPLING);
  // bme.setTemperatureOversampling(OVERSAMPLING);
  // bme.setPressureOversampling(OVERSAMPLING);
  // bme.setIIRFilterSize(BME680_FILTER_SIZE_7);
  // bme.setODR(BME68X_ODR_1000_MS);
  bme.setGasHeater(0, 0);
#    endif
  Serial.println("BME setup done");
}
#  endif /* W_BME_TYPE */
#endif   /* W_BME_TYPE != W_BME_OFF */

#if ESP8266 && !W_SOIL_MOISTURE
ADC_MODE(ADC_VCC); /* init input voltage mesure */
#endif

uint32_t inVolt;

// split into 2 packets? 'base' and 'extra'?
#if W_BME_TYPE == W_BME_680
#  define W_EXTRA_PACKET (0)
auto extraPacket = SensorsPacketizer<GasSensor>();
#endif

auto replyPacketNew = SensorsPacketizer<
#if W_BME_TYPE
    PressureSensor, HumiditySensor, TemperatureSensor
#  if W_BME_TYPE == W_BME_280
    ,
    VoltageSensor
#  endif /* W_BME_TYPE == W_BME_280 */
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
}

static void printValues();

static void sendValues();

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

static void handle_read_sensor() {
  status.last_read = micros();
  /* NOTE: We are using deepSleep so every iteration starts with setup() */
  inVolt = batteryVoltage();
#if 0
  /* USB powered: inVolt ~ 3000
   * We might want detect somehow if battery powered or USB powered
   * use GPIO jumper? */
  if (inVolt < VOLT_THRESHOLD) {
    ESP.deepSleep(ESP.deepSleepMax());
    return;
  }
#endif

#if W_BME_TYPE == W_BME_280
  /* Only needed in forced mode! In normal mode, you can remove the next line.
   */
  bme.takeForcedMeasurement();
  replyPacketNew.set<TemperatureSensor>(bme.readTemperature());
  replyPacketNew.set<PressureSensor>(bme.readPressure());
  replyPacketNew.set<HumiditySensor>(bme.readHumidity());
  replyPacketNew.set<VoltageSensor>(inVolt);
#elif W_BME_TYPE == W_BME_680
#  if W_BSEC
  bme.run();
#  else
  bme.performReading();
#  endif
  replyPacketNew.set<TemperatureSensor>(bme.temperature);
  replyPacketNew.set<PressureSensor>(bme.pressure);
  replyPacketNew.set<HumiditySensor>(bme.humidity);
// For now ignore voltage
// replyPacketNew.set<VoltageSensor>(inVolt);
#  if W_BSEC
  extraPacket.set<GasSensor>(GasSensorStorage(
      bme.gasResistance, bme.iaq, bme.staticIaq, bme.co2Equivalent,
      // each value is from 0 to 2 -> mask 0x03 and is uses 2 bits
      // accuracy in order of emited fields
      // 0, 1 - iaq accuracy
      // 2, 3 - static iaq accuracy
      // 4, 5 - co2accuracy
      (bme.iaqAccuracy & 0x03) | ((bme.staticIaqAccuracy & 0x03) << 2) |
          ((bme.co2Accuracy & 0x03) << 4)));
#  else
  extraPacket.set<GasSensor>(
      {static_cast<float>(bme.gas_resistance), 0, 0, 0, 0xFF});
#  endif
#endif

#if W_SOIL_MOISTURE
  replyPacketNew.set<SoilMoisture>(readSoilMoisture());
#endif
#if W_VERBOSE
  printValues();
#endif
  status.last_read_end = micros();
}

static void handle_send_message() {
  status.last_send = micros();
  // TODO(m): use extra only for BME680
  int ret;
#if W_EXTRA_PACKET
  static int counter = 0;
  if ((counter++) & 0x1) {
    // send "extra"
    ret = radio_send_all(extraPacket.mBytes, sizeof(extraPacket.mBytes));
  } else
#endif
  {
    // send "normal"
    ret = radio_send_all(replyPacketNew.mBytes, sizeof(replyPacketNew.mBytes));
  }

  status.radio_send = ret;

  if (ret) {
    Serial.print("send finished: ");
    Serial.println(ret);
  }
  status.last_send_end = micros();
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

#  if W_BSEC

  Serial.print("co2 = ");
  Serial.print(bme.co2Equivalent);
  Serial.print(" acc ");
  Serial.print(bme.co2Accuracy);
  Serial.println();

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
#  endif
#else
#  error Whoops
#endif
  Serial.println();
}

// Main entries

void setup() {
  setupLED();
  enableLED();
  Serial.begin(115200);
  // btSerial.begin("wunsz");
  // btSerial.register_callback
  // Serial.begin(9600);
  while (!Serial) {
    blink();
    /* wait for serial port to connect. Needed for native USB */
    delay(100);
  }

#if W_DEBUG
  delay(2000);
#endif
  // enable hidden fifi and ota
  WiFi.mode(WIFI_AP);
  WiFi.softAP(W_OTA_WIFI_NAME, W_OTA_WIFI_PASS, 6, 1);
  WiFi.setTxPower(WIFI_POWER_2dBm);
  Serial.print("WiFi IP: ");
  Serial.println(WiFi.softAPIP());

  server.on("/restart", HTTP_GET, [](AsyncWebServerRequest *request) {
    // radio_rfm69_reset_hacky_restart();
    ESP.restart();
    request->send(200, "text/plain", "should not see this");
  });

  server.on("/", HTTP_GET, [](AsyncWebServerRequest *request) {
    const auto reading_took = status.last_read_end - status.last_read;
    const auto sending_took = status.last_send_end - status.last_send;
    String asd = "Go to /update \nCurrent time: ";
    asd += micros();
    asd += "\nLast read: ";
    asd += status.last_read;
    asd += " read took: ";
    asd += reading_took;
    asd += "\nLast send: ";
    asd += status.last_send;
    asd += " sending took: ";
    asd += sending_took;
    asd += " status init: ";
    asd += status.radio_statue;
    asd += " status send: ";
    asd += status.radio_send;
    asd += "\nWatchdog restarts: ";
    // asd += radio_rfm69_watchdog_restarts();

    request->send(200, "text/plain", asd);
  });

  AsyncElegantOTA.begin(&server);
  server.begin();

#if W_BME_TYPE != W_BME_OFF
  setupBME280();
#endif

  while ((status.radio_statue = radio_setup())) {
#if W_VERBOSE
    Serial.println("setup fialed");
#endif
    delay(500);
  }

  uint64_t device_id = 0;
  radio_id(reinterpret_cast<uint8_t *>(&device_id));
  replyPacketNew.setId(device_id);
#if W_EXTRA_PACKET
  extraPacket.setId(device_id);
#endif

  scheduler.startNow();
  disableLED();
}
void loop() {
  // TODO(m): Invoke directly when battery powered
#if 0
    handle_read_sensor();
    handle_send_message();

#  if W_AC_TYPE == W_AC_DIRECT
#    if W_BME_TYPE == W_BME_680
  delay(299000);
#    else
  delayMicroseconds(W_REPORT_INTERVAL);
#    endif
#  else
#    if W_VERBOSE
  Serial.println("going into deep sleep mode");
#    endif
  ESP.deepSleep(W_REPORT_INTERVAL);
  delay(100);
#  endif /* W_AC_TYPE */
#else
  // scheduler.execute();
  handle_read_sensor();
  for (int i = 0; i < 2; ++i) {
    handle_send_message();
    delay(SEND_INTERVAL);
  }
#endif
}
