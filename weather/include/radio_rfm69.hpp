#if !defined(W_RADIO_RFM69_H)
#define W_RADIO_RFM69_H

#include <stdint.h>
#include <stddef.h>

int radio_rfm69_id(uint8_t *data);
int radio_rfm69_setup();
int radio_rfm69_send_all(const uint8_t *data, size_t len);

#endif