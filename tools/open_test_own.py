#!/usr/bin/env python3
"""open_test_own.py YEAR FILE TAG : like write-lab tools/open_test.py but on MY OWN Revit VM (env RVT_RD = its run dir, CID 31+), without the shared vm.lock.
The guest needs C:/wl/{run.ps1,run_long.ps1,runjob.py} (copied from the oracle guest) and the revit-ballet add-in (ci.sh --hold)."""
import sys, os
WL = os.path.expanduser('~/rvt-research/write-lab'); sys.path.insert(0, WL + '/campaign'); os.environ['STAGEB'] = '1'
assert os.environ.get('RVT_RD'), 'set RVT_RD to your own VM run dir'
import guest
class _NoLock:
    def __enter__(self): return self
    def __exit__(self, *a): pass
guest.vmlock = _NoLock
import stages
r = stages.api_stage(int(sys.argv[1]), os.path.abspath(sys.argv[2]), False, sys.argv[3]); print('OPEN ok=%s err=%s' % (r['ok'], r.get('err')))
