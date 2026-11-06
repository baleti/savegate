"""c5x-rvtgap: a lock file left behind by a killed save with unexpected content (bare number, list, non-numeric pid) must not crash the stale check
(AttributeError before the fix); once old enough it is taken over and the save proceeds."""
import os, time, pytest
from savegate.guard import Lock


@pytest.mark.parametrize('content', ['999999', '[]', '{"pid": "x", "host": "h", "time": "y"}', 'null'])
def test_garbage_lock_is_judged_stale_when_old(tmp_path, content):
    f = tmp_path / 'a.bin'; f.write_bytes(b'x')
    lk = Lock(str(f)); open(lk.lp, 'w').write(content); os.utime(lk.lp, (time.time() - 60, time.time() - 60))
    assert lk._stale() is True


@pytest.mark.parametrize('content', ['999999', '[]'])
def test_garbage_lock_fresh_is_live(tmp_path, content):
    f = tmp_path / 'a.bin'; f.write_bytes(b'x')
    lk = Lock(str(f)); open(lk.lp, 'w').write(content)
    assert lk._stale() is False
