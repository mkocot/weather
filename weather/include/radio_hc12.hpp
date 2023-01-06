#ifndef W_RADIO_HC12_H
#define W_RADIO_HC12_H

#include <stdint.h>
#include <stddef.h>

int radio_hc12_id(uint8_t *data);
int radio_hc12_setup();
int radio_hc12_send_all(const uint8_t *data, size_t len);
int radio_hc12_send(const char *str);

#endif