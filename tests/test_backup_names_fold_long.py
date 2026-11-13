"""c7x-rvtread2 item 544: backup name rules. (1) names over 150 bytes are shortened to 60 chars + '~' + sha1[:12]: two long names with the same first 60 chars must NOT share backups;
(2) a backup of 'a.rvt' must not be listed for 'a.rvt.v2' or the reverse; (3) with _CASE_INSENSITIVE forced (Windows/macOS) 'Model.rvt' and 'model.RVT' share backups, on case-sensitive systems they do not.
Synthetic small files, no Autodesk sample needed."""
import os
import pytest
from savegate import backup


def _mk(path, data=b'x' * 100):
    with open(path, 'wb') as f: f.write(data)


def test_long_names_same_prefix_do_not_share(tmp_path):
    a = str(tmp_path / ('A' * 70 + 'one' + 'z' * 100 + '.rvt')); b = str(tmp_path / ('A' * 70 + 'two' + 'z' * 100 + '.rvt'))
    assert len(os.path.basename(a).encode()) > 150 and backup._bn(a) != backup._bn(b)
    _mk(a); _mk(b, b'y' * 100)
    pa = backup.make_backup(a, 5, None); pb = backup.make_backup(b, 5, None)
    assert [x[1] for x in backup.list_backups(a)] == [pa] and [x[1] for x in backup.list_backups(b)] == [pb]
    assert len(os.path.basename(pa)) < 255


def test_prefix_named_files_do_not_share(tmp_path):
    a = str(tmp_path / 'a.rvt'); b = str(tmp_path / 'a.rvt.v2')
    _mk(a); _mk(b, b'y' * 100)
    pa = backup.make_backup(a, 5, None); pb = backup.make_backup(b, 5, None)
    assert [x[1] for x in backup.list_backups(a)] == [pa] and [x[1] for x in backup.list_backups(b)] == [pb]


@pytest.mark.parametrize('ci', [False, True])
def test_case_folding(tmp_path, monkeypatch, ci):
    monkeypatch.setattr(backup, '_CASE_INSENSITIVE', ci)
    a = str(tmp_path / 'Model.rvt'); _mk(a)
    pa = backup.make_backup(a, 5, None)
    found = [x[1] for x in backup.list_backups(str(tmp_path / 'model.RVT'))]
    assert (found == [pa]) if ci else (found == [])


@pytest.mark.parametrize('ci', [False, True])
def test_cache_store_key_folds_case(monkeypatch, ci):
    """c7x-rvtread2 item 545: fallback (cache) store key must not depend on the spelling of the folder on a case-insensitive file system"""
    monkeypatch.setattr(backup, '_CASE_INSENSITIVE', ci)
    a = backup.backup_dirs('/tmp/Proj/Sub/m.rvt'); b = backup.backup_dirs('/tmp/proj/sub/M.RVT')
    assert (a[1] == b[1]) == ci
    assert a[-1] == backup.backup_dirs('/tmp/Proj/Sub/m.rvt')[-1]   # deterministic


def test_legacy_key_fallback_backup_still_found_and_restored(tmp_path, monkeypatch):
    """c7x-rvtread2 item 547: a backup stored by an older version under the unfolded cache key (mixed-case folder, case-insensitive FS) must still be listed and restorable"""
    import hashlib
    monkeypatch.setenv('SAVEGATE_CACHE', str(tmp_path / 'cache'))
    monkeypatch.setattr(backup, '_CASE_INSENSITIVE', True)
    d = tmp_path / 'Proj'; d.mkdir(); f = str(d / 'Model.rvt'); _mk(f, b'NEW' * 50)
    legacy = os.path.join(str(tmp_path / 'cache'), hashlib.sha1(os.path.abspath(str(d)).encode()).hexdigest()[:12])
    old = b'OLD' * 50; h = hashlib.sha256(old).hexdigest()
    os.makedirs(legacy); name = 'Model.rvt.20260101-000000-000-%s' % h[:8]
    with open(os.path.join(legacy, name), 'wb') as g: g.write(old)
    found = backup.list_backups(f)
    assert [os.path.basename(x[1]) for x in found] == [name]
    backup.restore(f)
    assert open(f, 'rb').read() == old
