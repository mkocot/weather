#ifndef W_BME_TUNNEL_H
#define W_BME_TUNNEL_H

#include <ProtocolParser.hpp>
#include <vector>
#include <tuple>

class BmeTunnel
{
    bool requestPending = false;
    std::vector<std::tuple<float, float, float>> readings;
    ProtocolParser parser;

    public:
    BmeTunnel(int cs, int mosi, int miso, int sck)
    {
        // Use HW Serial, but configure it at
        // alternate pins
        // MISO = RX (wire to TX on translator)
        // MOSI = TX (wire to RX on translator)
        // MOSI (on MCU) to SDI (on chip)
        // MISO (on MCU) to SDO (on chip)
        // yellow   SDO     white (MISO)
        // orange   CSB     yellow (SS) (not connected)
        // purple   SDA     blue (MOSI)
        // green    SCL     brown (SCLK) (not connected)
        // black    GND     black (GND)
        // red      VCC     red (VCC 3.3)
        Serial.printf("tunel: RX=%d TX=%d\n", miso, mosi);
        Serial1.begin(9600, SERIAL_8N1, miso, mosi);
        Serial1.setTimeout(500);
    }
    bool begin()
    {
        return true;
    }
    
    bool measure()
    {
        requestPending = true;
        readings.clear();

        // drain any data on serial
        auto now = millis();
        while(Serial1.available() > 0)
        {
            Serial1.read();
            delay(1);
            if (millis() - now > 1000)
            {
                Serial.println("Suspicious data flood on Serial");
                break;
            }
        }

        static constexpr uint8_t request[] = {0x01, ProtocolParser::GET_SENSOR_DATA, 0x0B};
        Serial1.write(request, sizeof(request));
        Serial1.flush();
        // Wait up to 1s for result
        now = millis();
        while(millis() - now < 1000)
        {
            uint8_t data = 0xFF;
            if (Serial1.readBytes(&data, 1) != 1) {
                delay(1);
                Serial.println("No data from serial");
                continue;
            }

#if W_VERBOSE > 1
            Serial.printf("Data from serial: 0x%02X\r\n", data);
#endif

            const auto feed_status = parser.feed(data);
            if (feed_status != ProtocolParser::feed_result_t::PARSED)
            {
                // If not parsed yet, conitnue
                continue;
            }

            const auto message_status = parser.msg_status();
            if (message_status != ProtocolParser::status_t::OK)
            {
                Serial.println("Message parsed, but invalid");
                // Parsed, but result is flawed, try again
                continue;
            }

            if (parser.message() != ProtocolParser::message_t::RET_SENSOR_DATA)
            {
                Serial.print("Unexpected message: ");
                Serial.println(parser.message());
                // unexpected message, old data on line? continue
                continue;
            }

            Serial.println("Parsed, moving on");
            break;
        }

        if (parser.msg_status() != ProtocolParser::status_t::OK || parser.message() != ProtocolParser::message_t::RET_SENSOR_DATA)
        {
           Serial.println("Unable to read response");
           return false; 
        }

        const uint8_t *data = parser.buffer();
        const uint8_t *payload_start = data + 1;

        // should not happen on proper external device
        if (parser.msg_len() <= 1)
        {
            Serial.println("payload too short");
            return false;
        }

        const uint8_t payload_len = parser.msg_len() - 1;
        uint8_t entries = payload_len / (sizeof(float) * 3);
        
        // should not happen on proper external device
        if (entries * (sizeof(float) * 3) != payload_len)
        {
            Serial.println("invalid payload size");
            return false;
        }

        while(entries--)
        {
            readings.push_back(std::make_tuple(
                *reinterpret_cast<const float*>(payload_start), // TEMP
                *reinterpret_cast<const float*>(payload_start + sizeof(float)), // HUMIDITY
                *reinterpret_cast<const float*>(payload_start + sizeof(float) * 2) // PRESSURE
            ));

            payload_start += sizeof(float) * 3;
#if W_VERBOSE
        const auto &last = readings.at(readings.size() - 1);
        Serial.print("Parsing response: temp=");
        Serial.print(std::get<0>(last));
        Serial.print(" hum=");
        Serial.print(std::get<1>(last));
        Serial.print(" pres=");
        Serial.println(std::get<2>(last));
#endif
        }


        return true;
    }

    template<uint8_t index>
    float readMeasure() const
    {
        for (auto &r : readings)
        {
            float t = std::get<index>(r);
            if (t != NAN)
            {
                return t;
            }
        }

        return NAN;
    }

    float readTemperature() const
    {
        return readMeasure<0>();
    }
    float readHumidity() const
    {
        return readMeasure<1>();
    }
    float readPressure() const
    {
        return readMeasure<2>();
    }

    const std::vector<std::tuple<float, float, float>> &obtainReadings() const
    {
        return readings;
    }
};
#endif
