"""c7x-rvtread2 595: mtime-only change (touch by sync/backup tool) between open_doc and save, content identical: save must still succeed (no false refusal), result == new bytes."""
import os, sys, shutil, time, pytest
import savegate as sg
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
@pytest.mark.parametrize('delta', [5, -86400, 10**9])
def test_touch(tmp_path, delta):
    import wledit
    f = str(tmp_path / 'a.rfa'); shutil.copy(F, f)
    ed = wledit.Editor(f); ed.set_strings([(7, 'FillPattern.m_name', 'Touch probe')]); o = str(tmp_path / 'o.tmp'); ed.save(o); new = open(o, 'rb').read(); os.remove(o)
    doc = sg.open_doc(f, None, sg.Config(allow_overwrite=True, require_gate=False))
    t = time.time() + delta; os.utime(f, (t, t))
    sg.save(doc, new, {'modified': ['stream:Partitions/67', 'el:7']})
    assert open(f, 'rb').read() == new
