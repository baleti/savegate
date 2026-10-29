#!/bin/sh
cd ~/src/savegate
for y in 2024 2026; do
  V=""
  for x in stair rail curt roof vtext level sheet; do V="$V $x=/tmp/sgcl3/${y}_$x.rte"; done
  rm -rf /tmp/sgcm_$y
  ulimit -v 9000000
  python3 tools/matrix_rvt_classes.py /tmp/sgcm_$y $y /tmp/sgcl3/${y}_a.rte $V --open > /tmp/sgcm_$y.log 2>&1
done
