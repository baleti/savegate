"""Versioned backups next to the file (<dir>/.savegate/), falling back to the user cache dir."""
import os, shutil, time, hashlib
from .atomic import long_path, sha256_file, fsync_dir, full_fsync, write_temp, commit_temp
from .errors import DiskError, SaveError


def _cache_dir():
    base = os.environ.get('SAVEGATE_CACHE') or (
        os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'savegate') if os.name == 'nt'
        else os.path.join(os.environ.get('XDG_CACHE_HOME', os.path.expanduser('~/.cache')), 'savegate'))
    return base


def backup_dirs(path):
    d, n = os.path.split(os.path.abspath(path))
    return [os.path.join(d, '.savegate'), os.path.join(_cache_dir(), hashlib.sha1(d.encode('utf-8', 'surrogatepass')).hexdigest()[:12])]


def list_backups(path):
    """newest first: [(name, full_path, size)]"""
    n = os.path.basename(path); out = []
    for bd in backup_dirs(path):
        try: names = os.listdir(bd)
        except OSError: continue
        for x in names:
            if x.startswith(n + '.') and not x.endswith('.part'):
                p = os.path.join(bd, x)
                try: out.append((x, p, os.stat(p).st_size))
                except OSError: pass
    out.sort(key=lambda t: t[0].split('.')[-2] if t[0].count('.') >= 2 else '', reverse=True)
    out.sort(key=lambda t: os.stat(t[1]).st_mtime_ns, reverse=True)
    return out


def make_backup(path, keep=20):
    """copy `path` into the backup store, verify by hash, return backup path. Raises DiskError when no store works."""
    src_hash = sha256_file(path)
    stamp = time.strftime('%Y%m%d-%H%M%S') + '-%03d' % (time.time() * 1000 % 1000)
    name = '%s.%s-%s' % (os.path.basename(path), stamp, src_hash[:8])
    last = None
    for bd in backup_dirs(path):
        try:
            os.makedirs(long_path(bd), exist_ok=True)
            dst = os.path.join(bd, name); part = dst + '.part'
            with open(long_path(path), 'rb') as a, open(long_path(part), 'wb') as b:
                shutil.copyfileobj(a, b, 1 << 22); b.flush(); full_fsync(b.fileno())
            if sha256_file(part) != src_hash:
                os.remove(long_path(part)); raise OSError('backup hash mismatch')
            os.replace(long_path(part), long_path(dst)); fsync_dir(bd)
            _prune(path, keep)
            return dst
        except OSError as e:
            last = e
            try: os.remove(long_path(part))
            except (OSError, UnboundLocalError): pass
    raise DiskError('cannot write a backup of %s: %s' % (path, last))


def _prune(path, keep):
    for name, p, _ in list_backups(path)[keep:]:
        try: os.remove(p)
        except OSError: pass


def restore(path, which=None):
    """restore backup number `which` (0 = newest) over `path`, atomically; the current file is backed up first.
    Returns the backup path used."""
    bl = list_backups(path)
    if not bl: raise SaveError('no backup exists for %s' % path)
    which = which or 0
    if which >= len(bl): raise SaveError('backup %d does not exist (%d available)' % (which, len(bl)))
    use = bl[which][1]
    if os.path.exists(long_path(path)):
        make_backup(path)
    with open(long_path(use), 'rb') as f: data = f.read()
    tmp = write_temp(path, data)
    commit_temp(tmp, path)
    return use
