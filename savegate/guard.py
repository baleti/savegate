"""Fingerprint (concurrent-modification guard) and advisory lock file."""
import os, time, json, socket
from collections import namedtuple
from .atomic import sha256_file, long_path
from .errors import Locked, Conflict, DiskError

Fingerprint = namedtuple('Fingerprint', 'size mtime_ns sha256')


def fingerprint(path, with_hash=True):
    st = os.stat(long_path(path))
    return Fingerprint(st.st_size, st.st_mtime_ns, sha256_file(path) if with_hash else None)


def check_unchanged(path, fp, rehash=True):
    """raise Conflict when the file differs from the fingerprint taken at load"""
    try:
        st = os.stat(long_path(path))
    except FileNotFoundError:
        raise Conflict('%s was deleted since it was loaded' % path)
    if st.st_size != fp.size:
        raise Conflict('%s changed on disk (size %d -> %d)' % (path, fp.size, st.st_size))
    if st.st_mtime_ns != fp.mtime_ns or rehash:
        if fp.sha256 and sha256_file(path) != fp.sha256:
            raise Conflict('%s changed on disk (content hash differs)' % path)


def _lock_path(path):
    d, n = os.path.split(os.path.abspath(path))
    return os.path.join(d, '.' + n + '.savegate-lock')


def _pid_alive(pid):
    if pid <= 0: return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return os.name == 'nt'   # on Windows kill(pid,0) may raise generic errors; assume alive
    return True


class Lock:
    """O_EXCL lock file with pid/host/time. Stale = same host and pid dead, or older than `stale_after` s."""
    def __init__(self, path, stale_after=6 * 3600):
        self.target = path; self.lp = _lock_path(path); self.stale_after = stale_after; self.held = False

    def acquire(self):
        for _ in range(2):
            try:
                fd = os.open(long_path(self.lp), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except PermissionError as e:
                raise DiskError('cannot create lock file %s: %s' % (self.lp, e)) from e
            except FileExistsError:
                if self._stale():
                    try: os.remove(long_path(self.lp))
                    except OSError: pass
                    continue
                raise Locked('%s is being saved by another process (%s)' % (self.target, self._owner()))
            self.held = True
            try:
                with os.fdopen(fd, 'w') as f:
                    json.dump({'pid': os.getpid(), 'host': socket.gethostname(), 'time': time.time()}, f)
                    f.flush(); os.fsync(f.fileno())
            except OSError as e:
                self.release(); raise DiskError('cannot write lock file %s: %s' % (self.lp, e)) from e
            return self
        raise Locked('could not take lock for %s' % self.target)

    def _owner(self):
        try:
            with open(long_path(self.lp)) as f: return f.read()
        except OSError: return '?'

    def _stale(self):
        try:
            with open(long_path(self.lp)) as f: d = json.load(f)
        except (OSError, ValueError):
            return True
        if time.time() - d.get('time', 0) > self.stale_after: return True
        return d.get('host') == socket.gethostname() and not _pid_alive(int(d.get('pid', 0)))

    def release(self):
        if self.held:
            try: os.remove(long_path(self.lp))
            except OSError: pass
            self.held = False

    def __enter__(self): return self.acquire()
    def __exit__(self, *a): self.release()
