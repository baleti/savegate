#!/bin/sh
# wait until remote-host has memory for the oracle VM harness (>= 7 GB free), then run the pending RVT rows once
cd ~/src/savegate
while [ "$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)" -lt 7000 ]; do sleep 60; done
rm -rf /tmp/sgq1
SG_SETTLE=30 python3 tools/matrix_rvt.py /tmp/sgq1 --open 2024_writer_frame2 > /tmp/sgq1.log 2>&1
