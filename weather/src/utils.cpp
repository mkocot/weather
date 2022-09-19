#include <Arduino.h>
#include "config.hpp"

void exitError() {
  ESP.deepSleep(W_ERROR_SLEEP_INTERVAL);
  delay(100);
}

