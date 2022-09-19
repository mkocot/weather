#ifndef W_RADIO_H
#define W_RADIO_H

#if W_RADIO_MODE == W_RADIO_RFM69
#include "radio_rfm69.hpp"
#define radio_setup radio_rfm69_setup
#define radio_id radio_rfm69_id
#define radio_send_all radio_rfm69_send_all
#else
#include "radio_wifi.hpp"
#define radio_setup radio_wifi_setup
#define radio_id radio_wifi_id
#define radio_send_all radio_wifi_send_all
#endif /* W_RADIO_MODE */

struct radio {
    void *ctx;
    int (*setup) (void);
    int (*id) (uint8_t *out);
    int (*send_all) (const uint8_t *data, size_t len);
};

typedef struct radio radio_t;

#endif