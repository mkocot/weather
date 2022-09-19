#ifndef W_BME_H
#define W_BME_H


enum bme_value {
    BME_TEMPERATURE,
    BME_PRESSURE,
    BME_HYGRO,
    BME_VOC,
};

struct bme {
    void *ctx;
    int (*setup) (void);
    int (*force_read) (void);
    int (*getValue) (bme_value, void*ctx);
};

typedef struct bme bme_t;

#endif