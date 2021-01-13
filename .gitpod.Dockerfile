FROM gitpod/workspace-full

# Install custom tools, runtimes, etc.
# For example "bastet", a command-line tetris clone:
# RUN brew install bastet
#
# More information: https://www.gitpod.io/docs/config-docker/

ENV PATH="${HOME}/local/bin:${PATH}"
RUN mkdir -p ${HOME}/local/bin \
    ; curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | BINDIR=${HOME}/local/bin sh \
    && arduino-cli config init \
    && arduino-cli config add board_manager.additional_urls https://arduino.esp8266.com/stable/package_esp8266com_index.json \
    && arduino-cli core update-index \
    && arduino-cli core install esp8266:esp8266 \
    && arduino-cli lib install 'Adafruit BME280 Library'