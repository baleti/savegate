"""c4x-rvtgap: Config(backup_keep=0) pruned the backup taken for this very save (the returned path did not exist, RESTORE and the post-rename auto-restore had nothing)."""
import os, shutil, pytest
import savegate as sg
@pytest.mark.parametrize('keep', [0, -3, 1])
def test_newest_backup_survives(tmp_path, keep):
    src = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
    if not os.path.exists(src): pytest.skip('no sample')
    f = str(tmp_path / 'a.rfa'); shutil.copy(src, f); orig = open(f, 'rb').read()
    doc = sg.open_doc(f, None, sg.Config(allow_overwrite=True, require_gate=False, backup_keep=keep))
    r = sg.save(doc, orig, {})
    assert r.backup and os.path.exists(r.backup)
    assert open(r.backup, 'rb').read() == orig
