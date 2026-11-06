"""c5x-rvtgap: .part files left by a save killed during the backup copy are removed by a later backup once they are idle; a fresh .part (live copy) is kept."""
import os, time
from savegate.backup import make_backup, backup_dirs


def test_old_orphan_part_removed_fresh_kept(tmp_path):
    f = tmp_path / 'm.rvt'; f.write_bytes(b'abc' * 1000)
    bd = backup_dirs(str(f))[0]; os.makedirs(bd, exist_ok=True)
    old = os.path.join(bd, 'm.rvt.20200101-000000-000-deadbeef.part'); new = os.path.join(bd, 'm.rvt.20200101-000000-001-cafebabe.part'); other = os.path.join(bd, 'other.rvt.x.part')
    for p in (old, new, other): open(p, 'wb').write(b'x')
    t = time.time() - 3600; os.utime(old, (t, t)); os.utime(other, (t, t))
    make_backup(str(f), 20, 0, None)
    from savegate.backup import _prune; _prune(str(f), 20)
    assert not os.path.exists(old) and os.path.exists(new) and os.path.exists(other)
