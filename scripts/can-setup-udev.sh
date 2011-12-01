#!/bin/sh

sleep 3 
TTY=ttyUSB0
if [ -e /dev/ttyUSB1 ]; then
	TTY=ttyUSB1
fi

/bin/stty -F /dev/$TTY ispeed 3000000 ospeed 3000000 
/opt/socketcan/slcan_attach -o -s3 /dev/$TTY
/opt/socketcan/slcand $TTY
/sbin/ifconfig slcan0 up

