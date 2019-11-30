#!/bin/bash

INGRESS_IP=$1
INTERVAL_SECONDS=$2

if [ -z "$INGRESS_IP" ]; then
    echo "Ingress gateway IP is required"
    exit 1
fi

if [ -z "$INTERVAL_SECONDS" ]; then
    echo "Interval is required"
    exit 1
fi

URL="$INGRESS_IP/productpage"

echo "Calling $URL every $INTERVAL_SECONDS seconds"

while true
	do curl -s -o /dev/null -w "%{http_code}" $URL
	sleep $INTERVAL_SECONDS
	echo ""
done
