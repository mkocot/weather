#ifndef W_WTOCOL_H
#define W_WTOCOL_H

//#include <Arduino.h>
#include <cstddef>
#include <cstdint>
#include <stdexcept>

template <int ID, typename T>
class BaseSensor {
public:
  typedef T VALUE_TYPE;
  static constexpr const int SENSOR_ID = ID;
  // TOTAL Size: Sensor required size + Id
  // static constexpr const int SENSOR_DATA_SIZE = SIZE;
  static constexpr const int SENSOR_DATA_SIZE = sizeof(T);
  static constexpr const int SENSOR_SIZE = SENSOR_DATA_SIZE + 1;

  void set(int i) {}
};
// 7 image push
// 6 screen sendor
// 4 - reserverd
// Could be int16_t
class TemperatureSensor : public BaseSensor<0x01, float> {};
class PressureSensor : public BaseSensor<0x02, float> {};
// Could be uint8_t
class HumiditySensor : public BaseSensor<0x03, float> {};

class __attribute__((packed)) GasSensorStorage {
public:
  float gas_raw;    // resistance, Ohm
  float iaq;        // IndexAirQuality, No unit <0; 500>
  float iaq_static; // IndexAurQuality (scaled), No Unit 
  float co2;        // Co2 ppm equivalent, ppm 400 .. 2000
  uint8_t flags; // 6bits

  GasSensorStorage(float gas_raw, float iaq, float iaq_static, float co2,
            uint8_t flags)
      : gas_raw(gas_raw),
        iaq(iaq),
        iaq_static(iaq_static),
        co2(co2),
        flags(flags) {}

  GasSensorStorage(const GasSensorStorage &g)
      : gas_raw(g.gas_raw),
        iaq(g.iaq),
        iaq_static(g.iaq_static),
        co2(g.co2),
        flags(g.flags) {}

  GasSensorStorage(GasSensorStorage &&g)
      : gas_raw(0), iaq(0), iaq_static(0), co2(0), flags(0) {
    gas_raw = g.gas_raw;
    g.gas_raw = 0;

    iaq = g.iaq;
    g.iaq = 0;

    iaq_static = g.iaq_static;
    g.iaq_static = 0;

    co2 = g.co2;
    g.co2 = 0;

    flags = g.flags;
    g.flags = 0;
  }

  GasSensorStorage &operator=(GasSensorStorage &&g) {
    if (this == &g) {
      return *this;
    }

    gas_raw = g.gas_raw;
    g.gas_raw = 0;

    iaq = g.iaq;
    g.iaq = 0;

    iaq_static = g.iaq_static;
    g.iaq_static = 0;

    co2 = g.co2;
    g.co2 = 0;

    flags = g.flags;
    g.flags = 0;

    return *this;
  }
};

class GasSensor : public BaseSensor<0x08, GasSensorStorage> {
};
class VoltageSensor : public BaseSensor<0x05, uint32_t> {};
class SoilMoisture : public BaseSensor<0x09, float> {};

template <size_t A, size_t B>
struct TAssertEquality {
  static_assert(A == B, "Not equal");
  static constexpr bool value = (A == B);
};

template <typename A, typename B>
struct TypeAssertEquality {
  static constexpr bool value = std::is_same_v<A, B>;
  static_assert(value, "Not equal");
};


template <typename A, typename B>
struct TAssertConvertability {
  static constexpr bool value = std::is_convertible_v<A, B>;
  static_assert(value, "Not equal");
};

static_assert(
    TAssertEquality<sizeof(GasSensorStorage), 17>::value, "pack struct");

template <class X, class Tuple>
class Idx;

template <class X, class... T>
class Idx<X, std::tuple<T...>> {
  template <std::size_t... idx>
  static constexpr ssize_t find_idx(std::index_sequence<idx...>) {
    return std::max({static_cast<ssize_t>(std::is_same_v<X, T> ? idx : -1)...});
  }

public:
  static constexpr ssize_t value = find_idx(std::index_sequence_for<T...>{});
  static_assert(value != -1, "type not found in tuple");
};

// template <int INDEX, class X, class Tuple>
// class Offset;

// template <int INDEX, class X, class... T>
// class Offset<INDEX, X, std::tuple<T...>> {
//   template <std::size_t... idx>
//   static constexpr ssize_t find_idx(std::index_sequence<idx...>, int cntr) {
//     if (idx < INDEX) {
//       return find_idx(std::index_sequence<T...>{}, cntr + X::SENSOR_SIZE);
//     } else {
//       return 0;
//     }
//     //return std::max({static_cast<ssize_t>(std::is_same_v<X, T> ? idx :
//     -1)...}, cntr + X::SENSOR_SIZE);
//   }

// public:
//   static constexpr ssize_t value = find_idx(std::index_sequence_for<T...>{},
//   0); static_assert(value != -1, "type not found in tuple");
// };

template <typename... X>
class SensorsPacketizer {
private:
  typedef std::tuple<X...> Sensors;
  static const constexpr auto SENSOR_NUM = sizeof...(X);

public:
  static const constexpr auto HDR_SIZE = 2 + /* SyncByte + Version */
                                         6 + /* device id */
                                         1;  /* sensors count */
  // static const constexpr std::tuple<X...> mSensors{};
  // Header (HDR_SIZE) + SENSORS_SIZE +
  static const constexpr auto PACKET_SIZE = HDR_SIZE + (X::SENSOR_SIZE + ...);
  uint8_t mBytes[PACKET_SIZE] = {};

  SensorsPacketizer() {
    static_assert(sizeof...(X) <= 255, "too much sensor, only 255 is allowed");
    mBytes[0] = 'W';
    mBytes[1] = 1;
    // device ID
    mBytes[2] = 0xFF;
    mBytes[3] = 0xFF;
    mBytes[4] = 0xFF;
    mBytes[5] = 0xFF;
    mBytes[6] = 0xFF;
    mBytes[7] = 0xFF;
    mBytes[8] = sizeof...(X);

    // thats might not be best way of doing it, but it works...
    // ok... this will need more lowe, sensor MIGHT not have EQUAL size
    // so we need to track somehow offset
    auto init_id = [this](const auto sensor_id, auto offset) {
      mBytes[offset] = sensor_id;
    };
    (init_id(X::SENSOR_ID, sensor_offset<X>()), ...);
  }

  SensorsPacketizer(X... xs): SensorsPacketizer() {}

  /* use 48bits id (aka MAC) */
  void setId(uint64_t nodeId) {
    mBytes[2] = (nodeId >> 0) & 0xFF;
    mBytes[3] = (nodeId >> 8) & 0xFF;
    mBytes[4] = (nodeId >> 16) & 0xFF;
    mBytes[5] = (nodeId >> 24) & 0xFF;
    mBytes[6] = (nodeId >> 32) & 0xFF;
    mBytes[7] = (nodeId >> 40) & 0xFF;
  }

  template <typename S>
  static const constexpr off_t sensor_offset() {
    const auto constexpr idx = Idx<S, Sensors>::value;
    const constexpr auto calc_offset = [](auto index, auto size) {
      if (index < idx) {
        return size;
      }
      return 0;
    };

    return HDR_SIZE +
           (calc_offset(Idx<X, Sensors>::value, X::SENSOR_SIZE) + ...);
  }

  template <typename S>
  void set(const typename S::VALUE_TYPE &&val) {
    set<S>(val);
  }
  template <typename S>
  void set(const typename S::VALUE_TYPE &val) {
    // +1 so we don't overwrite sensor ID
    const auto constexpr offset = sensor_offset<S>() + 1;
#if W_DEBUG
    Serial.print("Storing ");
    Serial.print(S::SENSOR_DATA_SIZE);
    Serial.print(" bytes at offset ");
    Serial.println(offset);
#endif
    auto ptr = mBytes + offset;
    memcpy(ptr, &val, S::SENSOR_DATA_SIZE);
  }
};

#endif
