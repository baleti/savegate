"""c4x-rvtgap: while another process holds the file's lock (a save in progress) restore() and save_as(overwrite=True) onto that file must be refused with Locked, bytes untouched."""
import os, sys, shutil, pytest
import savegate as sg
from savegate.guard import Lock
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(F), reason='no sample')
def test_restore_refused_while_locked(tmp_path):
    f = str(tmp_path / 'a.rfa'); shutil.copy(F, f); raw = open(f, 'rb').read()
    doc = sg.open_doc(f, None, sg.Config(allow_overwrite=True, require_gate=False)); sg.save(doc, raw, {}); open(f, 'ab').write(b'x'); cur = open(f, 'rb').read()
    with Lock(f):
        with pytest.raises(sg.Locked): sg.restore(f)
    assert open(f, 'rb').read() == cur
def test_save_as_overwrite_refused_while_dest_locked(tmp_path):
    src = str(tmp_path / 'src.rfa'); shutil.copy(F, src); raw = open(src, 'rb').read(); d = str(tmp_path / 'dst.rfa'); shutil.copy(F, d); open(d, 'ab').write(b'y'); dcur = open(d, 'rb').read()
    doc = sg.open_doc(src, None, sg.Config(allow_overwrite=True, require_gate=False))
    with Lock(d):
        with pytest.raises(sg.Locked): sg.save_as(doc, raw, d, {}, overwrite=True)
    assert open(d, 'rb').read() == dcur
