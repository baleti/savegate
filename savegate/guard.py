"""Fingerprint (concurrent-modification guard) and advisory lock file."""
import os, time, json, socket
from collections import namedtuple
from .atomic import sha256_file, long_path, full_fsync
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
    n = n.lower()
    if len(n.encode('utf-8', 'surrogatepass')) > 150:      # c7x-rvtread2 199: keep the lock name under the 255-byte name limit
        import hashlib; n = hashlib.sha1(n.encode('utf-8', 'surrogatepass')).hexdigest()
    return os.path.join(d, '.' + n + '.savegate-lock')      # c4x-rvtgap: on case-insensitive filesystems (Windows, macOS) 'Model.rvt' and 'model.RVT' are one file and must share one lock


def _pid_alive(pid):
    if pid <= 0: return False
    if os.name == 'nt':      # os.kill(pid, 0) is not a probe on Windows (generic OSError / console control event): ask the OS
        import ctypes
        from ctypes import wintypes
        k = ctypes.WinDLL('kernel32', use_last_error=True)
        k.OpenProcess.restype = wintypes.HANDLE
        h = k.OpenProcess(0x1000, False, pid)     # PROCESS_QUERY_LIMITED_INFORMATION
        if not h: return ctypes.get_last_error() == 5      # access denied = exists
        try:
            code = wintypes.DWORD()
            k.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
            return bool(k.GetExitCodeProcess(h, ctypes.byref(code))) and code.value == 259     # STILL_ACTIVE
        finally: k.CloseHandle(h)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class Lock:
    """O_EXCL lock file with pid/host/time. Stale = same host and pid dead, or older than `stale_after` s."""
    def __init__(self, path, stale_after=6 * 3600):
        self.target = path; self.lp = _lock_path(path); self.stale_after = stale_after; self.held = False

    def acquire(self):
        denied = 0
        for _ in range(2):
            while True:
                try:
                    fd = os.open(long_path(self.lp), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    break
                except PermissionError as e:
                    # Windows: creating a name whose previous file is still delete-pending (another process holds a handle) fails with access
                    # denied for a few milliseconds: that is "somebody else is on it", not a broken folder. Retry briefly, then report busy.
                    if os.name == 'nt' and os.access(os.path.dirname(os.path.abspath(self.lp)), os.W_OK):
                        denied += 1
                        if denied > 100: raise Locked('%s is busy (lock file stays delete-pending)' % self.target) from e
                        time.sleep(0.01 * min(denied, 10)); continue
                    raise DiskError('cannot create lock file %s: %s' % (self.lp, e)) from e
                except FileExistsError:
                    fd = None; break
            if fd is None:
                    verdict = self._stale()
                    if verdict is None: continue                     # the lock vanished while we looked: just try to create it again
                    if verdict:
                        self._take_over_stale()
                        continue
                    raise Locked('%s is being saved by another process (%s)' % (self.target, self._owner()))
            self.held = True
            try:
                with os.fdopen(fd, 'w') as f:
                    json.dump({'pid': os.getpid(), 'host': socket.gethostname(), 'time': time.time()}, f)
                    f.flush(); full_fsync(f.fileno())
            except OSError as e:
                self.release(); raise DiskError('cannot write lock file %s: %s' % (self.lp, e)) from e
            return self
        raise Locked('could not take lock for %s' % self.target)

    def _owner(self):
        try:
            with open(long_path(self.lp)) as f: return f.read()
        except OSError: return '?'

    def _read_raw(self):
        with open(long_path(self.lp)) as f: return f.read()

    def _stale(self):
        """True = stale, False = live, None = the lock file disappeared while we looked"""
        try: raw = self._read_raw()
        except FileNotFoundError: return None
        except OSError: return False                                  # cannot read it right now (Windows sharing): treat as live
        try:
            d = json.loads(raw)
            if not isinstance(d, dict): raise ValueError('lock content is not an object')       # c5x-rvtgap: '999999' or '[]' crashed the stale check
        except ValueError:
            # empty / partial: a holder between O_EXCL create and its owner write; only old ones are stale
            try: return time.time() - os.stat(long_path(self.lp)).st_mtime > 10
            except FileNotFoundError: return None
            except OSError: return False
        self._judged = raw
        try:
            if 'time' not in d: raise ValueError('lock without a time')      # c5x-rvtread2: used to count as time 0 = ancient and was stolen at once; judge it by mtime like a garbage lock
            if time.time() - float(d['time']) > self.stale_after: return True
            return d.get('host') == socket.gethostname() and not _pid_alive(int(d.get('pid', 0)))
        except (TypeError, ValueError): return time.time() - os.stat(long_path(self.lp)).st_mtime > 10

    def _take_over_stale(self):
        """move the stale lock aside atomically (only one racer wins the rename); if what we moved is not what we judged, a new holder
        had replaced it in between: put it back when the name is still free"""
        tmp = '%s.stale.%d.%s' % (self.lp, os.getpid(), os.urandom(3).hex())
        try: os.replace(long_path(self.lp), long_path(tmp))
        except OSError: return
        try:
            with open(long_path(tmp)) as f: moved = f.read()
        except OSError: moved = None
        if moved is not None and getattr(self, '_judged', None) is not None and moved != self._judged:
            try: os.link(long_path(tmp), long_path(self.lp))      # fails if somebody created a new lock meanwhile (then theirs wins)
            except OSError: pass
        try: os.remove(long_path(tmp))
        except OSError: pass

    def release(self):
        if self.held:
            # Windows: a racer that is reading the lock file at this very moment makes os.remove fail with a sharing violation; giving up here
            # would leave a lock of a LIVE pid behind forever (everybody waits for us), so retry briefly
            for i in range(200):
                try: os.remove(long_path(self.lp)); break
                except FileNotFoundError: break
                except OSError: time.sleep(0.005 * min(i + 1, 10))
            self.held = False

    def __enter__(self): return self.acquire()
    def __exit__(self, *a): self.release()
