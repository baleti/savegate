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
