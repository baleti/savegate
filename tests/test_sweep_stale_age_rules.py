"""c7x-rvtread2 653: sweep_stale_temps removes only hidden *.sgtmp older than 1 h: a live temp (30 s, 59 min) stays, 61 min and 2 days go; a non-hidden *.sgtmp and a .part are never touched."""
import os, time
from savegate import atomic
def test_age_rules(tmp_path):
    now = time.time()
    for nm, age in (('.a.live.sgtmp', 30), ('.a.m59.sgtmp', 59 * 60), ('.a.m61.sgtmp', 61 * 60), ('.a.d2.sgtmp', 2 * 86400), ('plain.sgtmp', 2 * 86400), ('.a.keep.part', 2 * 86400)):
        p = tmp_path / nm; p.write_text('x'); os.utime(p, (now - age, now - age))
    assert atomic.sweep_stale_temps(str(tmp_path)) == 2
    assert sorted(os.listdir(tmp_path)) == ['.a.keep.part', '.a.live.sgtmp', '.a.m59.sgtmp', 'plain.sgtmp']
