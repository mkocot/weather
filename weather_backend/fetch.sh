#!/bin/sh

TIME=$((24*60*60))
RRDFILE=sensors_e09806259a.rrd

rrdtool graph graph_temp.svg --imgformat SVG \
	--start now-${TIME} --end now \
	--slope-mode --right-axis 1:0 \
	DEF:temp=${RRDFILE}:temp:AVERAGE \
	LINE1:temp#FF0000:"temp *C\l" \
	GPRINT:temp:LAST:"Cur\: %5.2lf *C" \
	GPRINT:temp:AVERAGE:"Avg\: %5.2lf *C" \
	GPRINT:temp:MAX:"Max\: %5.2lf *C" \
	GPRINT:temp:MIN:"Min\: %5.2lf *C\t\t\t"

rrdtool graph graph_hum.svg --imgformat SVG \
	--start now-${TIME} --end now \
	--slope-mode --right-axis 1:0 \
	DEF:hum=${RRDFILE}:hum:AVERAGE \
	LINE1:hum#00FF00:"hum %\l" \
	GPRINT:hum:LAST:"Cur\: %5.2lf %" \
	GPRINT:hum:AVERAGE:"Avg\: %5.2lf %" \
	GPRINT:hum:MAX:"Max\: %5.2lf %" \
	GPRINT:hum:MIN:"Min\: %5.2lf %\t\t\t"

rrdtool graph graph_pres.svg --imgformat SVG \
	--start now-${TIME} --end now \
	--slope-mode --right-axis 1:0 \
	DEF:pres=${RRDFILE}:pres:AVERAGE \
	LINE1:pres#0000FF:"pres hPa\l" \
	GPRINT:pres:LAST:"Cur\: %5.0lf hPa" \
	GPRINT:pres:AVERAGE:"Avg\: %5.0lf hPa" \
	GPRINT:pres:MAX:"Max\: %5.0lf hPa" \
	GPRINT:pres:MIN:"Min\: %5.0lf hPa\t\t\t"

rrdtool graph graph_volt.svg --imgformat SVG \
	--start now-${TIME} --end now \
	--slope-mode --right-axis 1:0 \
	DEF:volt=${RRDFILE}:volt:AVERAGE \
	LINE1:volt#FF00FF:"volt V\l" \
	GPRINT:volt:LAST:"Cur\: %5.3lf V" \
	GPRINT:volt:AVERAGE:"Avg\: %5.3lf V" \
	GPRINT:volt:MAX:"Max\: %5.3lf V" \
	GPRINT:volt:MIN:"Min\: %5.3lf V\t\t\t"
