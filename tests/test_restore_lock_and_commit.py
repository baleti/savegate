"""c5x-rvtread2 item 137: (1) sg.restore did not take the per-file lock, so it replaced a file that another process was saving; (2) a failing replace in restore raised a raw OSError and left
a .sgtmp temp file next to the file. Restore must refuse while the lock is held and turn a replace failure into a DiskError with the temp removed and the file untouched."""
import errno, os, pytest
import savegate as sg
from savegate import backup, guard
from savegate.adapters import RawAdapter
from savegate.errors import DiskError, Locked


def _edited(tmp_path):
    p = str(tmp_path / 'f.bin'); open(p, 'wb').write(b'ORIGINAL')
    with sg.open_doc(p, RawAdapter(), sg.Config(allow_overwrite=True, require_gate=False)) as doc:
        sg.save(doc, b'EDITED', {'modified': ['file']})
    return p


def test_restore_refuses_while_another_saver_holds_the_lock(tmp_path):
    p = _edited(tmp_path); L = guard.Lock(p).acquire()
    try:
        with pytest.raises(Locked): sg.restore(p, len(sg.list_backups(p)) - 1)
    finally: L.release()
    assert open(p, 'rb').read() == b'EDITED'


@pytest.mark.parametrize('err', [PermissionError(errno.EACCES, 'denied'), OSError(errno.EXDEV, 'cross-device')])
def test_failing_replace_is_a_diskerror_without_litter(tmp_path, monkeypatch, err):
    p = _edited(tmp_path)
    def bad(tmp, dest, **kw): raise err
    monkeypatch.setattr(backup, 'commit_temp', bad)
    with pytest.raises(DiskError): sg.restore(p, len(sg.list_backups(p)) - 1)
    assert open(p, 'rb').read() == b'EDITED'
    assert [f for f in os.listdir(tmp_path) if f.endswith('.sgtmp')] == []
