import pytest
from savegate import Config

BOOLS = ['allow_overwrite', 'require_gate', 'verify', 'allow_hardlink_break', 'allow_damaged_edit', 'allow_readonly']

@pytest.mark.parametrize('k', BOOLS)
@pytest.mark.parametrize('v', ['false', 'False', 'no', '', 0, 1, None, [], 2.0])
def test_non_bool_flag_refused(k, v):
    with pytest.raises(ValueError):
        Config(**{k: v})

@pytest.mark.parametrize('k', BOOLS)
def test_real_bools_ok(k):
    assert getattr(Config(**{k: True}), k) is True
    assert getattr(Config(**{k: False}), k) is False

@pytest.mark.parametrize('v', [-1, '5', None, 1.5, True, [1]])
def test_backup_max_bytes_bad(v):
    with pytest.raises(ValueError):
        Config(backup_max_bytes=v)

def test_backup_max_bytes_ok():
    assert Config(backup_max_bytes=0).backup_max_bytes == 0
    assert Config(backup_max_bytes=9000).backup_max_bytes == 9000
