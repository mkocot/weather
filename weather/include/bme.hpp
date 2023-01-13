#ifndef W_BME_H
#define W_BME_H

#include "config.hpp"

#if W_BME_TYPE == W_BME_280

#  include "bme280.hpp"
using BME = BME280;

#elif W_BME_TYPE == W_BME_680

#  if W_BSEC

#    include "bme680_bsec.hpp"
using BME = BME680_bsec;

#  else

#    include "bme680.hpp"
using BME = BME680;

#  endif /* W_BSEC */

#elif W_BME_TYPE == W_BME_OFF
/* TODO: what should it be on off */
using BME = void;
#else
#  error Unexpected type
#endif /* W_BME_TYPE */

#endif /* W_BME_H */