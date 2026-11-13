"""c5x-rvtread2 item 143: a sync tool rewrites the file between the backup and the rename. The save may finish, but the foreign version must survive as a backup and be reported (no silent loss)."""
import os, sys, shutil, hashlib, pytest
import savegate as sg
from savegate import core
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SAMPLES = [os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-%s.rfa' % y) for y in ('2024', '2026')]
SAMPLES = [s for s in SAMPLES if os.path.exists(s)]
pytestmark = pytest.mark.skipif(not SAMPLES, reason='no sample')
@pytest.mark.parametrize('F', SAMPLES)
def test_rewrite_after_backup_is_kept(tmp_path, monkeypatch, F):
    import wledit
    f = str(tmp_path / 'a.rfa'); shutil.copy(F, f)
    ed = wledit.Editor(f); ed.set_strings([(7, 'FillPattern.m_name', 'Sync probe')]); o = str(tmp_path / 'o.tmp'); ed.save(o); new = open(o, 'rb').read(); os.remove(o)
    MAN = {'modified': ['stream:' + wledit.Editor(F).trace(7)[0], 'el:7']}
    doc = sg.open_doc(f, None, sg.Config(allow_overwrite=True, require_gate=False))
    foreign = bytearray(open(f, 'rb').read()); foreign[2000] ^= 0xFF; foreign = bytes(foreign)
    real = core.make_backup
    def mb(*a, **k):
        r = real(*a, **k); open(f, 'wb').write(foreign); return r      # sync tool lands right after our backup
    monkeypatch.setattr(core, 'make_backup', mb)
    try: rep = sg.save(doc, new, MAN)
    except sg.SaveError: rep = None            # refusing is also safe
    cur = open(f, 'rb').read()
    if rep is None:
        assert cur == foreign or cur == open(F, 'rb').read()
        return
    assert cur == new
    assert any('another program changed' in w for w in rep.report.get('warnings', [])), rep.report
    shas = set()
    for root, _, fs in os.walk(tmp_path):
        for n in fs:
            shas.add(hashlib.sha256(open(os.path.join(root, n), 'rb').read()).hexdigest())
    assert hashlib.sha256(foreign).hexdigest() in shas, 'foreign version lost'
