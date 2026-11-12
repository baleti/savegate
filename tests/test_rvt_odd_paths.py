"""c2x-rvtgap item 33 (path cases): in-place gated save and restore on files whose directory/name has spaces, non-ASCII, a leading dash, a long name (200 chars), several dots.
Original must be replaced by exactly the new bytes, backup restorable, folder = file + .savegate only."""
import os, sys, shutil, pytest
import savegate as sg
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
NAMES = ['my family (v2).rfa', 'Familie über äö 墓.rfa', '-dash.rfa', 'a' * 200 + '.rfa', 'dots.in.name.v1.2.rfa', 'UPPER.RFA']
pytestmark = pytest.mark.skipif(not os.path.exists(F), reason='no sample')


@pytest.mark.parametrize('name', NAMES, ids=range(len(NAMES)))
def test_odd_name(tmp_path, name):
    import wledit
    d = tmp_path / 'dir with space é'; d.mkdir(); f = str(d / name)
    try: shutil.copy(F, f)
    except OSError as e: pytest.skip('fs refuses name: %s' % e)
    orig = open(f, 'rb').read()
    ed = wledit.Editor(f); ed.set_strings([(7, 'FillPattern.m_name', 'Odd path')]); o = str(tmp_path / 'o.tmp'); ed.save(o); new = open(o, 'rb').read()
    doc = sg.open_doc(f, None, sg.Config(allow_overwrite=True, require_gate=False))
    r = sg.save(doc, new, {'modified': ['stream:Partitions/67', 'el:7']}); assert r.ok
    assert open(f, 'rb').read() == new
    assert sorted(os.listdir(d)) == sorted(['.savegate', name]), os.listdir(d)
    sg.restore(f); assert open(f, 'rb').read() == orig
