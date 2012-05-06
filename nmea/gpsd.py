#!/usr/bin/env python
#
# Python GPSD
# Copyright (C) 2008 Tim Savage
#
# Python GPSD is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or at your option)
# any later version.
#
# Python GPSD is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# python GPSD.  If not, see <http://www.gnu.org/licenses/>.

#import nmea
import nmea.gps
import optparse
import sys
import time

__version__ = '0.1'

device="/dev/ttyUSB0"
timeout=3
baud=9600
    
class GpsObject():
    def __init__(self, port):
        self.gps_device = nmea.gps.Gps(port, callbacks={
            'fix_update': self.__fix_update,
            'transit_update': self.__transit_update,
            'satellite_update': self.__satellite_update,
            'satellite_status_update': self.__satellite_status_update,
            'log_error': self.__log_error

        })

    def __log_error(self, msg, info):
        pass
        
    def __fix_update(self, gps_device):
        pass

    def __transit_update(self, gps_device):
        print(time.time())
        print(gps_device.position.get_value())
        print(gps_device.track)
        print(gps_device.speed.kilometers_per_hour())
        print(gps_device.altitude)

    def __satellite_update(self, gps_device):
        pass

    def __satellite_status_update(self, gps_device):
        pass


def gps_object():
    """  Create gps port and dbus object """

    # Create GPS port
    port = gps_port()
    if port is None:
        return None

    # Create GPS object
    return GpsObject(port)


def gps_port():
    """ Create instance of a gps port """
    from nmea.serialport import SerialPort
    return SerialPort(
        device,
        baud,
        timeout)

def main():
    # Create device object
    gps_object0 = gps_object()

    try:
        while True:
            gps_object0.gps_device.handle_io()
    except KeyboardInterrupt:
        pass

    return 0


if __name__ == '__main__':
    sys.exit(main())
