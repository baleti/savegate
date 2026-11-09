"""c4x-rvtgap 296: a clone (added element) in a 2026 family is accepted but the report says the 22-byte partition index was not extended (weakened note, never a refusal);
a plain string edit produces no such note."""
import os, sys, shutil, subprocess, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2026.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no public sample')
def test_clone_note_and_plain_edit_clean(tmp_path):
    import savegate as sg, wledit
    cfg = sg.Config(allow_overwrite=True, require_gate=False)
    r = subprocess.run([sys.executable, os.path.expanduser('~/rvt-research/write-lab/e7.py'), SRC, str(tmp_path / 'o.rfa'), '4065'], env=dict(os.environ, MODE='min', COUNTER='1'), capture_output=True, text=True); assert r.returncode == 0, r.stderr
    nid = int(r.stdout.split('new id')[1].split()[0]); cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur)
    res = sg.save(sg.open_doc(cur, None, cfg), open(tmp_path / 'o.rfa', 'rb').read(), {'added': ['el:%d' % nid], 'modified': ['stream:Partitions/69', 'stream:Global/ElemTable']})
    assert res.ok and any('partition index' in w for w in res.report.get('weakened', []))
    from test_rvt_last_record_string_edit import _last_string_records
    q, eid, fn, old, pn = _last_string_records(wledit.Editor(SRC), 1)[0]
    ed = wledit.Editor(SRC); ed.set_strings([(eid, fn, 'N')]); ed.save(str(tmp_path / 'p.rfa')); cur2 = str(tmp_path / 'c2.rfa'); shutil.copy(SRC, cur2)
    res2 = sg.save(sg.open_doc(cur2, None, cfg), open(tmp_path / 'p.rfa', 'rb').read(), {'modified': ['stream:' + pn, 'el:%d' % eid]})
    assert res2.ok and not any('partition index' in w for w in res2.report.get('weakened', []))
