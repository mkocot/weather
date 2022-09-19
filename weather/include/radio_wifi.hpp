#if !defined(W_RADIO_WIFI_H)
#define W_RADIO_WIFI_H


#include <stdint.h>
#include <stddef.h>

int radio_wifi_id(uint8_t *data);
int radio_wifi_setup();
int radio_wifi_send_all(const uint8_t *data, size_t len);

#endif