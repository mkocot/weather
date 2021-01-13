
build: weather.ino
	arduino-cli compile --fqbn esp8266:esp8266:generic --warnings all --export-binaries

config:
	echo '#ifndef W_CONFIG_H' > config.h
	echo '#define W_CONFIG_H' >> config.h
	echo '#define WIFI_NAME "WIFI"' >> config.h
	echo '#define WIFI_PASS "12345678"' >> config.h
	echo '#endif' >> config.h

