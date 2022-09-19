#ifndef W_BME680_H
#define W_HME680_H

class Bme680 {
    private:
    public:
    Bme680() {}
    ~Bme680() {}  
};

struct x {};

int bme680_setup();

int bme680_refreshSensors();
int bme680_temp();
int bme680_press();
int bme680_hig();
int bme680_gas();

#endif