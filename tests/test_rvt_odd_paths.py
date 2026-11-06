"""c5x-rvtgap: in-place gate save when the file name/folder has spaces, non-ASCII, a leading dot, brackets, or a 200-char name: saved correctly, backup present, no stray files."""
import os, sys, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no public sample')
NAMES = ['my model v2 (final).rfa', 'München_Straße_中文_ж.rfa', '.hidden model.rfa', 'a[1]{2}\'3\'&;$x.rfa', ('n' * 190) + '.rfa', 'UPPER.RFA', 'trail space .rfa']


@pytest.mark.parametrize('name', NAMES)
def test_odd_names(tmp_path, name):
    import savegate as sg, wledit
    ed = wledit.Editor(SRC); ed.set_strings([(7, 'FillPattern.m_name', 'Zed')]); o = str(tmp_path / 'o.rfa'); ed.save(o); new = open(o, 'rb').read()
    d = tmp_path / 'dir with é space'; d.mkdir(); cur = str(d / name); shutil.copy(SRC, cur)
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    sg.save(doc, new, {'modified': ['stream:Partitions/67', 'el:7']})
    assert open(cur, 'rb').read() == new
    from savegate.backup import list_backups
    assert any(open([v for v in t if isinstance(v, str) and os.sep in v][0], 'rb').read() == open(SRC, 'rb').read() for t in list_backups(cur))
    assert not [f for f in os.listdir(d) if f.endswith(('.sgtmp', '.part'))]
