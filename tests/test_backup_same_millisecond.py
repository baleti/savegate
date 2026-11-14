"""c2x-rvtgap 153: two backups of one target made in the same millisecond (clock frozen): different contents keep both files (the hash tag differs), identical contents collapse to one identical file; no backup is ever overwritten by different bytes."""
import os, time
from savegate import backup
def test_same_ms(tmp_path, monkeypatch):
    t = str(tmp_path / 'x.rfa'); monkeypatch.setattr(time, 'time', lambda: 1700000000.123); monkeypatch.setattr(time, 'strftime', lambda f, *a: '20261114-000000')
    open(t, 'wb').write(b'A' * 5000); a = backup.make_backup(t, keep=20)
    open(t, 'wb').write(b'B' * 5000); b = backup.make_backup(t, keep=20)
    assert a != b and open(a, 'rb').read() == b'A' * 5000 and open(b, 'rb').read() == b'B' * 5000
    c = backup.make_backup(t, keep=20)       # same bytes as b in the same ms
    assert c == b and open(b, 'rb').read() == b'B' * 5000 and all(backup.verify_backup(p) for _, p, _ in backup.list_backups(t))
    assert len(backup.list_backups(t)) == 2
