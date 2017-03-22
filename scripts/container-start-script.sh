#!/usr/bin/env bash
# This script needs to run in the container

MY_IP_ADDR=$(/bin/hostname -i)

echo 'Starting Peer'
MY_IP_ADDR=($MY_IP_ADDR)
echo "${MY_IP_ADDR[0]}"

dstat_pid=0
app_pid=0

mkdir -p /data/capture

signal_handler() {

    if [ $dstat_pid -ne 0 ]; then
        kill $dstat_pid
    fi

    if [ $app_pid -ne 0 ]; then
        kill $app_pid
    fi
    echo "KILLED PROCESSES"

    while true
    do
      tail -f /dev/null & wait ${!}
    done
}

trap 'signal_handler' SIGUSR1

dstat -n -N eth0 --output "/data/capture/${MY_IP_ADDR[0]}.csv" &
dstat_pid=${!}

# <APP COMMAND> & Example: <java -jar HelloWorld.jar &>
app_pid=${!}

wait ${app_pid}
kill ${dstat_pid}
