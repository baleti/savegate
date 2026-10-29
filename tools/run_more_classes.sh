#!/bin/sh
# usage: run_more_classes.sh RVT_RD   (own VM; classes not yet in the ledger)
cd ~/src/savegate
export RVT_RD=$1 SG_OPEN_TOOL=$HOME/src/savegate/tools/open_test_own.py SG_SETTLE=5
ulimit -v 9000000
V=""; for x in curt roof vtext level sheet; do V="$V $x=/tmp/sgcl3/2024_$x.rte"; done
rm -rf /tmp/sgcm_2024; python3 tools/matrix_rvt_classes.py /tmp/sgcm_2024 2024 /tmp/sgcl3/2024_a.rte $V --open > /tmp/sgcm_2024.log 2>&1
V=""; for x in stair rail curt roof vtext level sheet; do V="$V $x=/tmp/sgcl3/2026_$x.rte"; done
rm -rf /tmp/sgcm_2026; python3 tools/matrix_rvt_classes.py /tmp/sgcm_2026 2026 /tmp/sgcl3/2026_a.rte $V --open > /tmp/sgcm_2026.log 2>&1
