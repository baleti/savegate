"""c5x-rvtgap 135: in-place gate save of files with odd names; backup + restore work and nothing stray is left."""
import os, sys, shutil, pytest
import savegate as sg
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
NAMES = ['with space.rfa', 'ünï©ode-日本語.rfa', 'a' * 200 + '.rfa', "quo'te;&$(x).rfa", '.hidden.rfa', 'dots..in.name.rfa', 'NOEXT', '-dash.rfa']
@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
@pytest.mark.parametrize('name', NAMES)
def test_name(tmp_path, name):
    sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
    import wledit
    t = tmp_path / name; shutil.copy(F, t); orig = t.read_bytes()
    ed = wledit.Editor(str(t)); ed.set_strings([(7, 'FillPattern.m_name', 'Edited')]); o = str(tmp_path / 'o.bin'); ed.save(o)
    new = open(o, 'rb').read(); os.remove(o)
    doc = sg.open_doc(str(t), None, sg.Config(allow_overwrite=True, require_gate=False, journal_dir=str(tmp_path / 'j')))
    r = sg.save(doc, new, {'modified': ['el:7']}); assert r.ok and t.read_bytes() == new
    assert len(sg.backup.list_backups(str(t))) == 1
    sg.restore(str(t), which=0); assert t.read_bytes() == orig
    stray = [n for n in os.listdir(tmp_path) if n not in (name, '.savegate', 'j') and not n.endswith('savegate-lock')]
    assert stray == [], stray
