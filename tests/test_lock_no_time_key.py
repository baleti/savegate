"""c5x-rvtread2 item 113: a lock file that is valid JSON but has no 'time' key was judged to be from the epoch (time 0 = ancient) and taken over at once, even when it had just been written by
a live saver. It must be judged by its mtime like an empty/garbage lock (fresh = busy, old = stale)."""
import os, json, time, socket, pytest
from savegate import guard


def _lock(tmp_path, content, age=0):
    target = str(tmp_path / 'm.rvt'); open(target, 'wb').write(b'x')
    lp = guard._lock_path(target); open(lp, 'w').write(content)
    if age: t = time.time() - age; os.utime(lp, (t, t))
    return target


@pytest.mark.parametrize('content', [json.dumps({'host': socket.gethostname()}), json.dumps({'pid': 999999, 'host': 'otherhost'}), json.dumps({})])
def test_fresh_lock_without_time_is_busy(tmp_path, content):
    target = _lock(tmp_path, content)
    with pytest.raises(guard.Locked): guard.Lock(target).acquire()


def test_old_lock_without_time_is_taken_over(tmp_path):
    target = _lock(tmp_path, json.dumps({'host': socket.gethostname()}), age=3600)
    l = guard.Lock(target).acquire(); l.release()
