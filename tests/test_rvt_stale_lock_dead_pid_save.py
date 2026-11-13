"""c2x-rvtgap 126: a lock file left by a dead pid on this host (killed save) is taken over and the gate save of an rfa succeeds; a lock of a LIVE pid makes the save fail with Locked and leaves the original untouched."""
import os, sys, shutil, json, time, socket, subprocess, pytest
import savegate as sg
from savegate import guard
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
def _edit(t, tmp):
    sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
    import wledit
    ed = wledit.Editor(t); ed.set_strings([(7, 'FillPattern.m_name', 'Lk')]); o = str(tmp / 'o.tmp'); ed.save(o)
    b = open(o, 'rb').read(); os.remove(o); return b
@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
def test_dead_and_live_lock(tmp_path):
    t = str(tmp_path / 'x.rfa'); shutil.copy(F, t); orig = open(t, 'rb').read(); new = _edit(t, tmp_path)
    man = {'modified': ['stream:Partitions/67', 'el:7']}
    p = subprocess.Popen([sys.executable, '-c', 'pass']); p.wait()
    lp = guard._lock_path(t)
    json.dump({'pid': p.pid, 'host': socket.gethostname(), 'time': time.time()}, open(lp, 'w'))
    doc = sg.open_doc(t, None, sg.Config(allow_overwrite=True, require_gate=False))
    live = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
    try:
        json.dump({'pid': live.pid, 'host': socket.gethostname(), 'time': time.time()}, open(lp, 'w'))
        with pytest.raises(Exception) as ei:
            sg.save(doc, new, man)
        assert 'ock' in type(ei.value).__name__ + str(ei.value) and open(t, 'rb').read() == orig
    finally:
        live.kill(); live.wait()
    json.dump({'pid': p.pid, 'host': socket.gethostname(), 'time': time.time()}, open(lp, 'w'))
    assert sg.save(doc, new, man).ok
    assert open(t, 'rb').read() == new and not os.path.exists(lp)
