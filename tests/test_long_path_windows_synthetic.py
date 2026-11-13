"""c7x-rvtread2 item 543: atomic.long_path on synthetic Windows paths (no Windows needed: _WIN forced, ntpath.abspath substituted).
Guards the extended-length prefix rules: UNC -> \\\\?\\UNC\\..., drive paths >= 248 chars -> \\\\?\\C:\\..., short paths unchanged, already prefixed unchanged, mixed slashes normalised."""
import ntpath
import pytest
from savegate import atomic


@pytest.fixture
def win(monkeypatch):
    monkeypatch.setattr(atomic, '_WIN', True)
    monkeypatch.setattr(atomic.os.path, 'abspath', ntpath.abspath)


def test_short_drive_path_unchanged(win):
    assert atomic.long_path('C:\\Projects\\m.rvt') == 'C:\\Projects\\m.rvt'


def test_unc_gets_unc_prefix(win):
    assert atomic.long_path('\\\\srv\\share\\dir\\m.rvt') == '\\\\?\\UNC\\srv\\share\\dir\\m.rvt'


def test_prefixed_untouched(win):
    p = '\\\\?\\C:\\' + 'a' * 300 + '\\m.rvt'
    assert atomic.long_path(p) == p


@pytest.mark.parametrize('n, prefixed', [(200, False), (247, False), (248, True), (300, True)])
def test_length_threshold(win, n, prefixed):
    tail = '\\m.rvt'; p = 'C:\\' + 'd' * (n - len('C:\\') - len(tail)) + tail
    assert len(p) == n
    r = atomic.long_path(p)
    assert r.startswith('\\\\?\\') == prefixed and r.endswith('m.rvt')


def test_forward_slashes_normalised(win):
    r = atomic.long_path('C:/Projects/' + 'd' * 300 + '/m.rvt')
    assert r.startswith('\\\\?\\C:\\Projects\\') and '/' not in r


def test_unc_long(win):
    r = atomic.long_path('//srv/share/' + 'd' * 300 + '/m.rvt')
    assert r.startswith('\\\\?\\UNC\\srv\\share\\') and '/' not in r
