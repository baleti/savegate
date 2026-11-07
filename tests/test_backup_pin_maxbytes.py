"""c5x-rvtread2 item 131 (c2x-review HB2): the pristine original is pinned against the keep-count pruning, but backup_max_bytes pruning dropped it (12 saves, max_bytes below two backups
left only the newest backup). The pin must hold there too; the byte cap then applies to the other backups."""
import savegate as sg
from savegate.adapters import RawAdapter


def _saves(p, n, **cfg):
    for i in range(n):
        with sg.open_doc(p, RawAdapter(), sg.Config(allow_overwrite=True, require_gate=False, **cfg)) as doc:
            sg.save(doc, (b'v%02d' % i) * 1000, {'modified': ['file']})


def test_pristine_original_survives_max_bytes_pruning(tmp_path):
    p = str(tmp_path / 'f.bin'); open(p, 'wb').write(b'ORIGINAL' * 1000)
    _saves(p, 12, backup_keep=20, backup_max_bytes=9000)           # 8 KB backups: the cap fits about one besides the pin
    bl = sg.list_backups(p)
    assert open(bl[-1][1], 'rb').read() == b'ORIGINAL' * 1000       # oldest = pristine original, still there
    assert open(bl[0][1], 'rb').read() == b'v10' * 1000             # newest is always kept


def test_max_bytes_still_bounds_the_other_backups(tmp_path):
    p = str(tmp_path / 'f.bin'); open(p, 'wb').write(b'ORIGINAL' * 1000)
    _saves(p, 12, backup_keep=20, backup_max_bytes=9000)
    bl = sg.list_backups(p)
    assert sum(sz for _, _, sz in bl[:-1]) <= 9000                  # everything except the pin fits the cap (3 KB backups)
    assert len(bl) < 12
