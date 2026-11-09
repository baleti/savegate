"""c4x-rvtgap: restore() and save_as(overwrite=True) replaced the file through a 0600 mkstemp temp WITHOUT copying mode/owner/xattrs (save() did): a shared 0664 model became 0600 (unreadable for other users / services, e.g. a build or Revit service account)."""
import os, sys, shutil, stat, pytest
import savegate as sg
from savegate import core
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(F), reason='no sample')
def mode(p): return stat.S_IMODE(os.stat(p).st_mode)
def test_restore_keeps_mode(tmp_path):
    f = str(tmp_path / 'a.rfa'); shutil.copy(F, f); os.chmod(f, 0o664); raw = open(f, 'rb').read()
    doc = sg.open_doc(f, None, sg.Config(allow_overwrite=True, require_gate=False)); sg.save(doc, raw, {}); assert mode(f) == 0o664
    open(f, 'ab').write(b'x'); sg.restore(f)
    assert open(f, 'rb').read() == raw and mode(f) == 0o664, oct(mode(f))
def test_save_as_overwrite_keeps_mode_of_old_dest(tmp_path):
    f = str(tmp_path / 'src.rfa'); shutil.copy(F, f); raw = open(f, 'rb').read(); d = str(tmp_path / 'dst.rfa'); shutil.copy(F, d); os.chmod(d, 0o664)
    doc = sg.open_doc(f, None, sg.Config(allow_overwrite=True, require_gate=False)); sg.save_as(doc, raw, d, {}, overwrite=True)
    assert mode(d) == 0o664, oct(mode(d))
def test_auto_restore_in_save_as_keeps_mode(tmp_path, monkeypatch):
    f = str(tmp_path / 'src.rfa'); shutil.copy(F, f); raw = open(f, 'rb').read(); d = str(tmp_path / 'dst.rfa'); shutil.copy(F, d); os.chmod(d, 0o664)
    def lying(dest, nb): open(dest, 'wb').write(b'damaged'); raise core.DiskError('destination content differs after rename')
    monkeypatch.setattr(core, '_finish_check', lying)
    doc = sg.open_doc(f, None, sg.Config(allow_overwrite=True, require_gate=False))
    with pytest.raises(core.DiskError): sg.save_as(doc, raw, d, {}, overwrite=True)
    assert open(d, 'rb').read() == raw and mode(d) == 0o664, oct(mode(d))

def test_restore_reads_back(tmp_path, monkeypatch):
    from savegate import backup
    f = str(tmp_path / 'a.rfa'); shutil.copy(F, f); raw = open(f, 'rb').read()
    doc = sg.open_doc(f, None, sg.Config(allow_overwrite=True, require_gate=False)); sg.save(doc, raw, {}); open(f, 'ab').write(b'x')
    real = backup.commit_temp
    def bad(tmp, dest, **kw): real(tmp, dest, **kw); open(dest, 'wb').write(b'garbage')
    monkeypatch.setattr(backup, 'commit_temp', bad)
    with pytest.raises(core.DiskError): sg.restore(f)
