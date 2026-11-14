"""Atomic file replacement: temp in the destination dir, fsync, os.replace (Windows retry), fsync dir."""
import os, sys, time, stat, errno, hashlib, tempfile

_WIN = sys.platform == 'win32'
_WIN_BUSY = {5, 32, 33, 1224}
# test hook: called with a step name before each step ('tmp_written', 'before_replace', 'after_replace', ...)
_hook = None


def _step(name):
    if _hook is not None:
        _hook(name)


def long_path(p):
    if not _WIN:
        return p
    p = os.path.abspath(p)
    if p.startswith('\\\\?\\'):
        return p
    if p.startswith('\\\\'):
        return '\\\\?\\UNC\\' + p[2:]
    return '\\\\?\\' + p if len(p) >= 248 else p


def _busy(e):
    if isinstance(e, PermissionError):
        return True
    return getattr(e, 'winerror', None) in _WIN_BUSY or (_WIN and e.errno in (errno.EACCES, errno.EBUSY, errno.EPERM))


def replace_retry(src, dst, tries=12, delay=0.02, max_delay=0.5, _sleep=time.sleep):
    src, dst = long_path(src), long_path(dst)
    d = delay
    for i in range(tries):
        try:
            os.replace(src, dst)
            return
        except OSError as e:
            if not (_WIN and _busy(e)) or i == tries - 1:
                raise
            _sleep(d); d = min(d * 2, max_delay)


def full_fsync(fd):
    """os.fsync, but on macOS F_FULLFSYNC (fsync alone does not flush the drive cache there); falls back to os.fsync"""
    if sys.platform == 'darwin':
        try:
            import fcntl
            fcntl.fcntl(fd, fcntl.F_FULLFSYNC); return
        except (ImportError, OSError, AttributeError):
            pass
    os.fsync(fd)


def fsync_dir(path):
    if _WIN:
        return
    try:
        fd = os.open(path or '.', os.O_RDONLY)
        try:
            full_fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass


_PENDING = set()      # temp files written by write_temp and not yet renamed into place (c7x-rvtread2 650)
_ARMED = {}


def _on_term(signum, frame):
    import signal
    for t in list(_PENDING):
        try: os.remove(t)
        except OSError: pass
    signal.signal(signum, signal.SIG_DFL); os.kill(os.getpid(), signum)


def _pending_add(tmp):
    """SIGTERM/SIGHUP/SIGQUIT used to leave the .sgtmp behind (12 of 14 runs). Main thread, POSIX only; only the DEFAULT action is replaced, a handler the host installed stays."""
    import signal, threading
    _PENDING.add(tmp)
    if _WIN or threading.current_thread() is not threading.main_thread(): return
    for n in ('SIGTERM', 'SIGHUP', 'SIGQUIT'):
        g = getattr(signal, n, None)
        if g is None or g in _ARMED: continue
        try:
            if signal.getsignal(g) == signal.SIG_DFL: signal.signal(g, _on_term); _ARMED[g] = True
        except (ValueError, OSError): pass


def _pending_done(tmp):
    _PENDING.discard(tmp)


def write_temp(dest, data):
    """write data to a fresh temp file next to dest, fsynced; returns the temp path"""
    d = os.path.dirname(os.path.abspath(dest))
    fd, tmp = tempfile.mkstemp(prefix='.' + os.path.basename(dest)[:40] + '.', suffix='.sgtmp', dir=long_path(d))
    _pending_add(tmp)
    try:
        with os.fdopen(fd, 'wb') as f:
            mv = memoryview(data)
            for i in range(0, len(mv), 1 << 24):
                f.write(mv[i:i + (1 << 24)])
            f.flush(); full_fsync(f.fileno())
        _step('tmp_written')
    except BaseException:
        try: os.remove(tmp)
        except OSError: pass
        _pending_done(tmp)
        raise
    return tmp


def is_readonly(path):
    st = os.stat(long_path(path))
    if _WIN: return bool(getattr(st, 'st_file_attributes', 0) & 1)      # FILE_ATTRIBUTE_READONLY
    return stat.S_IMODE(st.st_mode) & 0o222 == 0


def _copy_owner_xattrs(src, tmp):
    """a rename-replace makes a new inode: keep the group (shared project folders) and the extended attributes (labels, tags, security context) of the file it replaces. Best effort, POSIX only; the owner cannot be kept without root"""
    if _WIN: return
    try:
        gid = os.stat(src).st_gid
        if gid != os.stat(tmp).st_gid: os.chown(tmp, -1, gid)
    except (OSError, AttributeError): pass
    try:
        for k in os.listxattr(src):
            try: os.setxattr(tmp, k, os.getxattr(src, k))
            except OSError: pass
    except (OSError, AttributeError): pass


def commit_temp(tmp, dest, copy_mode_from=None, keep_readonly=False):
    """rename tmp over dest (atomic), then fsync the directory"""
    if copy_mode_from and os.path.exists(long_path(copy_mode_from)):
        mode = stat.S_IMODE(os.stat(long_path(copy_mode_from)).st_mode)
        try: os.chmod(tmp, mode if keep_readonly else mode | stat.S_IWRITE)
        except OSError: pass
        _copy_owner_xattrs(long_path(copy_mode_from), tmp)
    ro = keep_readonly and os.path.exists(long_path(dest)) and is_readonly(dest)
    if ro and _WIN:
        os.chmod(long_path(dest), stat.S_IWRITE)      # Windows cannot replace a READONLY file
    _step('before_replace')
    replace_retry(tmp, dest)
    _pending_done(tmp)
    if ro and _WIN:
        os.chmod(long_path(dest), stat.S_IREAD)
    _step('after_replace')
    fsync_dir(os.path.dirname(os.path.abspath(dest)))


def link_new(tmp, dest):
    """publish tmp as dest only if dest does not exist (hard link is atomic and O_EXCL-like); fallback for
    filesystems without links: exclusive create check + replace. Removes tmp."""
    _step('before_replace')
    try:
        os.link(long_path(tmp), long_path(dest))
    except FileExistsError:
        raise
    except OSError:
        if os.path.exists(long_path(dest)):
            raise FileExistsError(dest)
        replace_retry(tmp, dest); fsync_dir(os.path.dirname(os.path.abspath(dest)))
        _step('after_replace'); return
    try: os.remove(tmp)
    except OSError: pass
    _step('after_replace')
    fsync_dir(os.path.dirname(os.path.abspath(dest)))


def sha256_file(path, bufsize=1 << 22):
    h = hashlib.sha256()
    with open(long_path(path), 'rb') as f:
        while True:
            b = f.read(bufsize)
            if not b: break
            h.update(b)
    return h.hexdigest()


def sweep_own_temps(dest):
    """remove leftover temp files of THIS target (a killed save); call only while holding the target's lock, so no live save can own them"""
    d, n = os.path.split(os.path.abspath(dest)); pre = '.' + n[:40] + '.'; k = 0
    try:
        for x in os.listdir(long_path(d)):
            if x.startswith(pre) and x.endswith('.sgtmp'):
                try: os.remove(os.path.join(d, x)); k += 1
                except OSError: pass
    except OSError: pass
    return k


def sweep_stale_temps(directory, max_age=3600):
    """remove leftover .*.sgtmp files older than max_age seconds (a crashed save)"""
    n = 0
    try:
        for name in os.listdir(directory):
            if name.startswith('.') and name.endswith('.sgtmp'):
                p = os.path.join(directory, name)
                try:
                    if time.time() - os.stat(p).st_mtime > max_age:
                        os.remove(p); n += 1
                except OSError:
                    pass
    except OSError:
        pass
    return n
