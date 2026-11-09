"""c4x-rvtgap: save_as target hygiene: existing dest refused (overwrite=False) and untouched; read-only directory fails cleanly with no partial file; overwrite=True backs up the old dest; post-commit mismatch never leaves a damaged destination."""
import os, sys, shutil, stat, pytest
import savegate as sg
from savegate import core
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(F), reason='no sample')
def _doc(tmp_path):
    f = str(tmp_path / 'src.rfa'); shutil.copy(F, f); return f, sg.open_doc(f, None, sg.Config(allow_overwrite=True, require_gate=False)), open(f, 'rb').read()
def test_existing_dest_refused(tmp_path):
    f, doc, raw = _doc(tmp_path); d = tmp_path / 'dst.rfa'; d.write_bytes(b'precious')
    with pytest.raises(sg.SaveError): sg.save_as(doc, raw, str(d), {})
    assert d.read_bytes() == b'precious' and sorted(os.listdir(tmp_path)) == ['dst.rfa', 'src.rfa']
@pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory modes')
def test_readonly_dir_fails_cleanly(tmp_path):
    f, doc, raw = _doc(tmp_path); ro = tmp_path / 'ro'; ro.mkdir(); os.chmod(ro, stat.S_IRUSR | stat.S_IXUSR)
    try:
        with pytest.raises(sg.SaveError): sg.save_as(doc, raw, str(ro / 'x.rfa'), {})
        assert os.listdir(ro) == []
    finally: os.chmod(ro, 0o700)
    assert open(f, 'rb').read() == raw
def test_overwrite_true_backs_up_old_dest(tmp_path):
    f, doc, raw = _doc(tmp_path); d = tmp_path / 'dst.rfa'; shutil.copy(F, d); old = d.read_bytes()
    r = sg.save_as(doc, raw, str(d), {}, overwrite=True)
    assert r.backup and open(r.backup, 'rb').read() == old and d.read_bytes() == raw
@pytest.mark.parametrize('existing', [False, True])
def test_mismatch_after_commit_leaves_no_damaged_dest(tmp_path, monkeypatch, existing):
    f, doc, raw = _doc(tmp_path); d = tmp_path / 'dst.rfa'
    if existing: shutil.copy(F, d)
    old = d.read_bytes() if existing else None
    def lying(dest, nb):
        open(dest, 'wb').write(b'damaged by the filesystem'); raise core.DiskError('destination content differs after rename')
    monkeypatch.setattr(core, '_finish_check', lying)
    with pytest.raises(core.DiskError): sg.save_as(doc, raw, str(d), {}, overwrite=existing)
    if existing: assert d.read_bytes() == old
    else: assert not d.exists()
    assert open(f, 'rb').read() == raw
