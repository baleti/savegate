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


def fsync_dir(path):
    if _WIN:
        return
    try:
        fd = os.open(path or '.', os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass


def write_temp(dest, data):
    """write data to a fresh temp file next to dest, fsynced; returns the temp path"""
    d = os.path.dirname(os.path.abspath(dest))
    fd, tmp = tempfile.mkstemp(prefix='.' + os.path.basename(dest)[:40] + '.', suffix='.sgtmp', dir=long_path(d))
    try:
        with os.fdopen(fd, 'wb') as f:
            mv = memoryview(data)
            for i in range(0, len(mv), 1 << 24):
                f.write(mv[i:i + (1 << 24)])
            f.flush(); os.fsync(f.fileno())
        _step('tmp_written')
    except BaseException:
        try: os.remove(tmp)
        except OSError: pass
        raise
    return tmp


def commit_temp(tmp, dest, copy_mode_from=None):
    """rename tmp over dest (atomic), then fsync the directory"""
    if copy_mode_from and os.path.exists(long_path(copy_mode_from)):
        try: os.chmod(tmp, stat.S_IMODE(os.stat(long_path(copy_mode_from)).st_mode) | stat.S_IWRITE)
        except OSError: pass
    _step('before_replace')
    replace_retry(tmp, dest)
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
