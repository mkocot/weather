#ifndef W_BME_TUNNEL_H
#define W_BME_TUNNEL_H

#include <ProtocolParser.hpp>

class BmeTunnel
{
    bool requestPending = false;
    float temp = NAN;
    float pres = NAN;
    float hum = NAN;
    ProtocolParser parser;
    public:
    BmeTunnel(int cs, int mosi, int miso, int sck)
    {
        // Use HW Serial, but configure it at
        // alternate pins
        // MISO = RX (wire to TX on translator)
        // MOSI = TX (wire to RX on translator)
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
        temp = NAN;
        pres = NAN;
        hum = NAN;

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

        static constexpr uint8_t request[] = {0x01, ProtocolParser::GET_SENSOR_DATA, 0xA8};
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

            if (parser.feed(data) != ProtocolParser::feed_result_t::PARSED)
            {
                // If not parsed yet, conitnue
                continue;
            }

            if (parser.msg_status() != ProtocolParser::status_t::OK)
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
        temp = *reinterpret_cast<const float*>(payload_start);
        hum = *reinterpret_cast<const float*>(payload_start + sizeof(float));
        pres = *reinterpret_cast<const float*>(payload_start + sizeof(float) * 2);

#if W_VERBOSE
        Serial.print("Parsing response: temp=");
        Serial.print(temp);
        Serial.print(" hum=");
        Serial.print(hum);
        Serial.print(" pres=");
        Serial.println(pres);
#endif
        return true;
    }

    constexpr float readTemperature() const
    {
        return temp;
    }
    constexpr float readPressure() const
    {
        return pres;
    }
    constexpr float readHumidity() const
    {
        return hum;
    }
};
#endif
