"""Versioned backups next to the file (<dir>/.savegate/), falling back to the user cache dir."""
import re, os, sys, shutil, time, hashlib
from .atomic import long_path, sha256_file, fsync_dir, full_fsync, write_temp, commit_temp
from .errors import DiskError, SaveError, Conflict


def _cache_dir():
    base = os.environ.get('SAVEGATE_CACHE') or (
        os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'savegate') if os.name == 'nt'
        else os.path.join(os.environ.get('XDG_CACHE_HOME', os.path.expanduser('~/.cache')), 'savegate'))
    return base


def backup_dirs(path):
    d, n = os.path.split(os.path.abspath(path))
    return [os.path.join(d, '.savegate'), os.path.join(_cache_dir(), hashlib.sha1(d.encode('utf-8', 'surrogatepass')).hexdigest()[:12])]


_CASE_INSENSITIVE = sys.platform in ('win32', 'darwin')      # c4x-rvtgap: 'Model.rvt' and 'model.RVT' are one file there; on Linux they are two and must NOT share backups (wrong-file restore)


def _bn(path):
    """file name used in backup names; long names are shortened (c7x-rvtread2 199: name + stamp + hash + .part must stay under 255 bytes)"""
    n = os.path.basename(path)
    if len(n.encode('utf-8', 'surrogatepass')) <= 150: return n
    import hashlib
    return n[:60] + '~' + hashlib.sha1(n.encode('utf-8', 'surrogatepass')).hexdigest()[:12]


def _fold(x):
    return x.lower() if _CASE_INSENSITIVE else x


def list_backups(path):
    """newest first: [(name, full_path, size)]"""
    n = _bn(path); out = []
    for bd in backup_dirs(path):
        try: names = os.listdir(bd)
        except OSError: continue
        for x in names:
            if _fold(x).startswith(_fold(n) + '.') and re.fullmatch(r'\d{8}-\d{6}-\d{3}-[0-9a-f]{8}', x[len(n) + 1:]):      # c4x-rvtgap: exact stamp, so 'm.rvt.v2' backups are never taken for 'm.rvt' (prune deleted them, restore could write them into m.rvt)
                p = os.path.join(bd, x)
                try: out.append((x, p, os.stat(p).st_size))
                except OSError: pass
    out.sort(key=lambda t: t[0].split('.')[-2] if t[0].count('.') >= 2 else '', reverse=True)
    out.sort(key=lambda t: os.stat(t[1]).st_mtime_ns, reverse=True)
    return out


def make_backup(path, keep=20, max_bytes=0, expect_sha=None):
    """copy `path` into the backup store, verify by hash, return backup path. Raises DiskError when no store works."""
    src_hash = sha256_file(path)
    stamp = time.strftime('%Y%m%d-%H%M%S') + '-%03d' % (time.time() * 1000 % 1000)
    name = '%s.%s-%s' % (_bn(path), stamp, src_hash[:8])
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
            _prune(path, keep, max_bytes)
            if expect_sha and src_hash != expect_sha:     # the file changed after the last fingerprint check: keep its copy, refuse to replace it
                raise Conflict('%s changed on disk while it was being saved; nothing was replaced (a copy of that version is kept as %s)' % (path, dst))
            return dst
        except OSError as e:
            last = e
            try: os.remove(long_path(part))
            except (OSError, UnboundLocalError): pass
    raise DiskError('cannot write a backup of %s: %s' % (path, last))


def backup_bytes(path, data):
    """store `data` as a backup of `path` (same naming and hash tag as make_backup, so list/restore/verify work); used to rescue a version that was just replaced"""
    h = hashlib.sha256(data).hexdigest(); stamp = time.strftime('%Y%m%d-%H%M%S') + '-%03d' % (time.time() * 1000 % 1000)
    last = None
    for bd in backup_dirs(path):
        try:
            os.makedirs(long_path(bd), exist_ok=True); dst = os.path.join(bd, '%s.%s-%s' % (_bn(path), stamp, h[:8])); part = dst + '.part'
            with open(long_path(part), 'wb') as b: b.write(data); b.flush(); full_fsync(b.fileno())
            os.replace(long_path(part), long_path(dst)); fsync_dir(bd); return dst
        except OSError as e: last = e
    raise DiskError('cannot write a backup of %s: %s' % (path, last))


def sweep_orphan_parts(path, idle=300):
    """c5x-rvtgap: a save killed during the backup copy leaves NAME.part behind for ever; remove .part files of this file's backups that nobody has written to for `idle` s
    (a live copy keeps touching its mtime)."""
    base = _bn(path) + '.'
    for bd in backup_dirs(path):
        try: names = os.listdir(long_path(bd))
        except OSError: continue
        for n in names:
            if n.endswith('.part') and n.startswith(base):
                p = os.path.join(bd, n)
                try:
                    if time.time() - os.stat(long_path(p)).st_mtime > idle: os.remove(long_path(p))
                except OSError: pass


def _prune(path, keep, max_bytes=0):
    """keep the newest `keep` backups; with max_bytes also drop the oldest until the total fits (the newest is always kept)."""
    keep = max(1, keep)       # c4x-rvtgap: keep=0 (or negative) dropped the backup that was JUST made, leaving nothing to restore from
    sweep_orphan_parts(path)
    bl = list_backups(path)
    pinned = bl[-1][1] if keep >= 2 and bl else None      # c5x-rvtread2 (HB2): the pristine original is also exempt from the byte cap
    # c2x-rvtgap: the OLDEST backup is the pristine original of the first overwrite; plain 'newest N' pruning deleted it after N+1 saves (25 saves with keep=20 left no copy of the
    # original). It is pinned: the window is the newest keep-1 plus the oldest (keep>=2; with keep<2 behaviour is unchanged).
    if keep >= 2 and len(bl) > keep:
        drop = bl[keep - 1:-1]; bl = bl[:keep - 1] + bl[-1:]; keep = len(bl)
    else:
        drop = bl[keep:]
    if max_bytes:
        tot = 0
        for i, (name, p, sz) in enumerate(bl[:keep]):
            tot += sz
            if tot > max_bytes and i > 0: drop += bl[i:keep]; break
    for name, p, _ in drop:
        if p == pinned: continue
        try: os.remove(p)
        except OSError: pass


def verify_backup(p):
    """True when the backup's SHA-256 starts with the 8 hex digits recorded in its file name (written at backup time)."""
    tag = os.path.basename(p).rsplit('-', 1)[-1]
    return len(tag) == 8 and sha256_file(p).startswith(tag)


def restore(path, which=None):
    """restore backup number `which` (0 = newest) over `path`, atomically; the current file is backed up first.
    Returns the backup path used."""
    bl = list_backups(path)
    if not bl: raise SaveError('no backup exists for %s' % path)
    which = which or 0
    if which >= len(bl): raise SaveError('backup %d does not exist (%d available)' % (which, len(bl)))
    use = bl[which][1]
    if not verify_backup(use): raise SaveError('backup %s is damaged (hash differs from its recorded hash); not restored, %s untouched' % (use, path))
    if os.path.exists(long_path(path)):
        make_backup(path)
    with open(long_path(use), 'rb') as f: data = f.read()
    try: tmp = write_temp(path, data)
    except OSError as e:      # c5x-rvtread2: a full or unwritable volume surfaced as a raw OSError; the file is untouched (the temp is removed by write_temp)
        raise DiskError('cannot write the restored copy next to %s: %s; the file was not touched, the backup %s is intact' % (path, e, use)) from e
    try: commit_temp(tmp, path)
    except OSError as e:      # c5x-rvtread2: a failing replace left the temp file behind and surfaced as a raw OSError
        try: os.remove(long_path(tmp))
        except OSError: pass
        raise DiskError('cannot replace %s with the restored copy: %s; the file was not touched, the backup %s is intact' % (path, e, use)) from e
    return use
