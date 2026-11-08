"""c4x-rvtgap: if the destination does not hold the verified bytes after the rename, the pre-save file is put back (was: DiskError and a damaged original left in place)."""
import os, shutil, pytest
import savegate as sg
from savegate import core
def test_mismatch_after_rename_restores(tmp_path, monkeypatch):
    f = str(tmp_path / 'a.rfa'); src = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
    if not os.path.exists(src): pytest.skip('no sample')
    shutil.copy(src, f); before = open(f, 'rb').read()
    doc = sg.open_doc(f, None, sg.Config(allow_overwrite=True, require_gate=False))
    def lying(dest, nb):
        open(dest, 'wb').write(b'damaged by the filesystem')          # what the rename left behind
        raise core.DiskError('destination content differs after rename')
    monkeypatch.setattr(core, '_finish_check', lying)
    with pytest.raises(core.DiskError) as ei: sg.save(doc, before + b'\0' * 0, {})
    assert 'restored' in str(ei.value)
    assert open(f, 'rb').read() == before

def test_damaged_backup_is_not_written_back(tmp_path, monkeypatch):
    f = str(tmp_path / 'a.rfa'); src = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
    if not os.path.exists(src): pytest.skip('no sample')
    shutil.copy(src, f); before = open(f, 'rb').read()
    doc = sg.open_doc(f, None, sg.Config(allow_overwrite=True, require_gate=False))
    def lying(dest, nb):
        b = core.list_backups(f)[0][1]; open(b, 'wb').write(b'\0' * len(before))      # backup damaged (same size)
        open(dest, 'wb').write(b'damaged by the filesystem')
        raise core.DiskError('destination content differs after rename')
    monkeypatch.setattr(core, '_finish_check', lying)
    with pytest.raises(core.DiskError) as ei: sg.save(doc, before, {})
    assert 'restored' not in str(ei.value).replace('NOT restored', '') and 'FAILED' in str(ei.value)
    assert open(f, 'rb').read() != b'\0' * len(before)
