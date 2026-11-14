"""c2x-rvtgap 154 (needs a filesystem whose listdir order is not creation order, hence ~/c4x-work on ext4; fails on HEAD before the fix, in a tmpfs it passes by luck): backups with identical mtime (coarse-timestamp filesystems, copied store) are listed newest-stamp first, deterministically, so restore(which=0) is the latest save."""
import os, time
from savegate import backup
def test_equal_mtime(monkeypatch):
    import tempfile; tmp_path = __import__("pathlib").Path(tempfile.mkdtemp(dir=os.path.expanduser("~/c4x-work")))
    t = str(tmp_path / 'x.rfa'); stamps = iter(['20261114-0000%02d' % i for i in range(1, 13)])
    monkeypatch.setattr(time, 'strftime', lambda f, *a: next(stamps))
    made = []
    for ch in [bytes([65 + i]) for i in range(12)]:
        open(t, 'wb').write(ch * 3000); made.append(backup.make_backup(t, keep=20))
    for p in made: os.utime(p, ns=(1700000000_000000000, 1700000000_000000000))
    order = [p for _, p, _ in backup.list_backups(t)]
    assert order == made[::-1]
    for _ in range(5): assert [p for _, p, _ in backup.list_backups(t)] == order
    __import__('shutil').rmtree(tmp_path)
