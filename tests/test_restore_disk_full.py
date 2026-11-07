"""c5x-rvtread2 item 136: sg.restore on a full volume raised a raw OSError [Errno 28]. It must be a DiskError (the usual save error family) that says the file was not touched, and the file must be intact."""
import errno, pytest
import savegate as sg
from savegate import backup
from savegate.adapters import RawAdapter
from savegate.errors import DiskError


def test_restore_on_full_volume_is_a_diskerror_and_leaves_the_file(tmp_path, monkeypatch):
    p = str(tmp_path / 'f.bin'); open(p, 'wb').write(b'ORIGINAL')
    with sg.open_doc(p, RawAdapter(), sg.Config(allow_overwrite=True, require_gate=False)) as doc:
        sg.save(doc, b'EDITED', {'modified': ['file']})
    def full(dest, data): raise OSError(errno.ENOSPC, 'No space left on device')
    monkeypatch.setattr(backup, 'write_temp', full)
    with pytest.raises(DiskError) as ei: sg.restore(p, len(sg.list_backups(p)) - 1)
    assert 'not touched' in str(ei.value)
    assert open(p, 'rb').read() == b'EDITED'
