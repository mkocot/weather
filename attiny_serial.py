#!/usr/bin/env python3
import serial
import sys
import time
import argparse
from datetime import datetime

parser = argparse.ArgumentParser(description='Serial port data dumper')
parser.add_argument('-r', '--raw', action='store_true', 
                       help='Dump raw data from serial (default)')
parser.add_argument('-x', '--hex', action='store_true',
                       help='Dump hex data from serial')
parser.add_argument('-n', '--newline', action='store_true',
                       help='Add new line when dumping hex data if no data received for more than 1 second')
parser.add_argument('-t', '--timestamp', action='store_true',
                       help='Prefix each message with its receive timestamp [hh:mm:ss.ssss] (requires -n in hex mode)')
parser.add_argument('-b', '--baud', type=int, default=9600,
                       help='Baud rate (default: 9600)')
parser.add_argument('-d', '--device', type=str, 
                       default='/dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller-if00-port0',
                       help='Serial device path')
args = parser.parse_args()
# If neither raw nor hex is specified, default to raw
if not args.raw and not args.hex:
    args.raw = True
if args.timestamp and not (args.hex and args.newline):
    parser.error('-t/--timestamp requires -n (--newline) in hex mode: use -x -n -t')

def timestamp(now):
    """Format a receive time as [hh:mm:ss.ssss] (local wall clock)."""
    t = datetime.fromtimestamp(now)
    return "[%02d:%02d:%02d.%04d] " % (t.hour, t.minute, t.second, t.microsecond // 100)


def dump_serial(ser, args):
    last_received_time = time.time()
    line_buffer = False
    in_message = False
    
    while True:
        data = ser.read(1)
        current_time = time.time()
        
        if data:
            if args.hex:
                data = b'%02x ' % data[0]
                line_buffer = True
                # Timestamp the first byte of each new message
                if args.timestamp and not in_message:
                    sys.stdout.buffer.write(timestamp(current_time).encode())
                    in_message = True
            # Raw mode
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
            
            last_received_time = current_time

            continue
        
        # If in hex mode and newline option is enabled, check for timeout
        if args.hex and args.newline:
            # If no data received for more than 1 second and we have buffered data
            if (current_time - last_received_time) > 1.0 and line_buffer:
                sys.stdout.buffer.write(b'\n')
                sys.stdout.buffer.flush()
                line_buffer = False
                in_message = False

if __name__ == '__main__':
    with serial.Serial(args.device, args.baud, timeout=1) as ser:
        print(f"Connected to {args.device} at {args.baud} baud", file=sys.stderr)
        dump_serial(ser, args)


# BAUD=2400
# BAUD=9600
# DEVICE='/dev/ttyUSB1'
# DEVICE='/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0'
# DEVICE='/dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller-if00-port0'
# 
# with serial.Serial(DEVICE, BAUD, timeout=1) as ser:
#     while True:
#         data = ser.read(1)
#         if data:
#             sys.stdout.buffer.write(b'%02x' % data[0])
#             sys.stdout.buffer.flush()
# 
