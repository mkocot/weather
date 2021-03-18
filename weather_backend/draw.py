import os
import sys
import PIL
import io
from PIL import Image, ImageDraw, ImageFont
import socket
import time
import fetch
from datetime import datetime

WHITE = 0
BLACK = 1

WIDTH = 128
HEIGHT = 32 # but screen has 64 lines, and displays it every 2nd
font  = ImageFont.load("fonts/ter-x12n.pil")

image = Image.new('1', (WIDTH, HEIGHT), color=BLACK)
canvas = ImageDraw.Draw(image)
fonts = ["helvB18", "helvR18", "luBS18",  "luRS18", "lutBS18", "lutRS18", "10x20",
         # slashed 0
         "ter-x18b", "ter-x18n", "terminus-18-bold", "terminus-18"]

def draw_graph(title, name, data):
    _clean()
    canvas.text((0,0), name + ":" + title, fill=WHITE, font=font)
    # data from sensor
    data_max = max(data)
    data_min = min(data)
    data_max -= data_min
    # 20 is MAX height for screen
    if data_max == 0:
        data_max = 0.0001
    factor = 20/data_max
    # now values are from 0..20 (but Y axis is reverted)
    normalized = [
        HEIGHT - (x - data_min) * factor for x in data
    ]
    graph = []
    graph.append((0, 32))
    xpos = 0
    xstep = WIDTH / len(data)
    for n in normalized:
        graph.append((xpos, n))
        xpos += xstep
    graph.append((128, 32))
    # draw graph
    canvas.polygon(graph, fill=WHITE)
    return _bytise()



buffer = io.BytesIO()
#image.show()
buffer.truncate()
image.save(buffer, format="PPM")
raw_image = buffer.getvalue()
data_start = len(raw_image) - WIDTH * HEIGHT // 8

def _clean():
    canvas.rectangle(((0,0), (128, 32)), fill=BLACK)

def _bytise():
    #image.show()
    buffer.truncate()
    image.save(buffer, format="PPM")
    raw_image = buffer.getvalue()
    data_start = len(raw_image) - WIDTH * HEIGHT // 8
    return raw_image[data_start:]

def draw_overview(name, hum=None, temp=None, press=None, volt=None, time=None):
    _clean()
    canvas.text((0,0), name, fill=WHITE, font=font)
    labels = []
    if temp:
        labels.append("%d°C" % temp)
    if hum:
        labels.append("%d%%" % hum)
    if press:
        labels.append("%dhPa" % press)
    text = " | ".join(labels)
    time_text = str(datetime.fromtimestamp(time))
    canvas.text((0, 12), text, fill=WHITE, font=font)
    canvas.text((0, 22), time_text, fill=WHITE, font=font)
    return _bytise()

def draw_humidity(name):
    _clean()
    return _bytise()

def draw_pressure(name):
    _clean()
    return _bytise()

def draw_temperature(name):
    _clean()
    return _bytise()

def draw_voltage(name):
    _clean()
    return _bytise()
