"""savegate engine: open_doc / save_as / save / restore with verify, backup, lock, journal."""
import os, json, time, hashlib
from dataclasses import dataclass, field
from . import atomic
from .atomic import long_path, sha256_file
from .errors import *
from .guard import fingerprint, check_unchanged, Lock
from .backup import make_backup, restore as _restore, list_backups
from .journal import Journal
from .adapters import pick_adapter


@dataclass
class Config:
    allow_overwrite: bool = False     # SAVE! gate 1 (user config)
    require_gate: bool = True         # SAVE! gate 2 (oracle matrix green for this format/version)
    backup_keep: int = 20
    backup_max_bytes: int = 0         # 0 = unlimited; else drop the oldest backups beyond this total (the newest is always kept)
    gate_file: str = None             # default: <cache>/gate.json or $SAVEGATE_GATE
    journal_dir: str = None
    verify: bool = True
    allow_hardlink_break: bool = False  # c4x-rvtgap: allow overwriting a file that has other hard links (the other names keep the old content)
    allow_damaged_edit: bool = False  # c4x-rvtgap 106: allow Save As of an EDITED copy of a source that is already damaged (unchanged rescue copies are always allowed)
    allow_readonly: bool = False      # overwrite a read-only target (the flag/mode is kept)


@dataclass
class SaveResult:
    ok: bool; dest: str; backup: str; size: int; sha256: str; report: dict; elapsed: float; version: str = ''


def gate_open(fmt, version, cfg):
    p = cfg.gate_file or os.environ.get('SAVEGATE_GATE') or os.path.join(os.path.expanduser('~'), '.config', 'savegate', 'gate.json')
    try:
        with open(p) as f: g = json.load(f)
    except (OSError, ValueError):
        return False
    return g.get(fmt, {}).get(version) == 'open' or g.get(fmt, {}).get('*') == 'open'


class Doc:
    def __init__(self, path, buf, adapter, version, fp, cfg, journal=None):
        self.path = os.path.abspath(path); self.buf = buf; self.adapter = adapter; self.version = version
        self.fingerprint = fp; self.cfg = cfg; self.journal = journal

    def close(self, clean=True):
        if self.journal: self.journal.close(done=clean); self.journal = None

    def __enter__(self): return self
    def __exit__(self, t, v, tb): self.close(clean=t is None)


def open_doc(path, adapter=None, cfg=None, journal=True):
    cfg = cfg or Config()
    if os.path.islink(path): path = os.path.realpath(path)      # in-place save must update the real file, not replace the link
    with open(long_path(path), 'rb') as f: buf = f.read()
    st = os.stat(long_path(path))
    from .guard import Fingerprint
    fp = Fingerprint(len(buf), st.st_mtime_ns, hashlib.sha256(buf).hexdigest())
    ad, ver = pick_adapter(buf, adapter)
    atomic.sweep_stale_temps(os.path.dirname(os.path.abspath(path)))
    j = Journal(path, cfg.journal_dir) if journal else None
    return Doc(path, buf, ad, ver, fp, cfg, j)


def _verify(doc, new_bytes, manifest):
    """Any unexpected exception while reading/judging the OUTPUT means the output is damaged (or the verifier cannot judge it): refuse with a message that says so
    (c4x-dwgreadfuzz item 123: 27/300 random bit flips surfaced as raw IndexError/ValueError/KeyError/AttributeError from lz77_decompress, dwgbits, r2004_open...)."""
    try:
        return _verify_inner(doc, new_bytes, manifest)
    except SaveError:
        raise
    except Exception as e:
        import traceback
        tb = traceback.extract_tb(e.__traceback__)[-1]
        raise VerifyFailed('the saved output could not be read back and checked (%s: %s, in %s); the original file was not touched' % (type(e).__name__, str(e)[:80], tb.name),
                           dict(error=type(e).__name__, where='%s:%s' % (tb.filename.rsplit('/', 1)[-1], tb.name)))


def _verify_inner(doc, new_bytes, manifest):
    ad = doc.adapter
    if manifest.get('writer_ops') and hasattr(ad, 'verify_writer_ops'):
        # c5x-rvtgap RVT-EDIT rungs 2/3: the output is claimed to be exactly what the trusted writer produces for the declared operations; the adapter recomputes that from the source
        bad = ad.verify_writer_ops(doc.buf, new_bytes, manifest)
        rep = dict(objects_src=0, objects_out=0, unexpected=bad[:50], n_unexpected=len(bad), declared_noop=[], writer_ops=manifest['writer_ops'])
        if bad: raise VerifyFailed('verify failed: %d differences outside the declared edit (first: %s)' % (len(bad), bad[0]), rep)
        rep['validate'] = ad.validate(new_bytes) or 'ok'
        return rep
    a, b = ad.snapshot_pair(doc.buf, new_bytes) if hasattr(ad, 'snapshot_pair') else (ad.snapshot(doc.buf), ad.snapshot(new_bytes))
    mod, add, dele = ad.expand(manifest) if hasattr(ad, 'expand') else (set(manifest.get('modified', ())), set(manifest.get('added', ())), set(manifest.get('deleted', ())))
    se = ad.side_effects(manifest) if hasattr(ad, 'side_effects') else set()
    mod = mod | se; add = add | se; dele = dele | se
    allowed_mod = mod
    bad = []
    for k in a.keys() | b.keys():
        if k in a and k in b:
            if a[k] != b[k] and k not in mod: bad.append(('changed', k))
        elif k in a:
            if k not in dele: bad.append(('lost', k))
        else:
            if k not in add: bad.append(('unexpected', k))
    if hasattr(ad, 'filter_changed'): bad = ad.filter_changed(bad, a, b, manifest)
    if hasattr(ad, 'extra_checks'): bad += ad.extra_checks(manifest) or []
    missing = [('not_modified', k) for k in allowed_mod if k in a and k in b and a[k] == b[k]]  # informational
    rep = dict(objects_src=len(a), objects_out=len(b), unexpected=bad[:50], n_unexpected=len(bad), declared_noop=missing[:50])
    if bad:
        raise VerifyFailed('verify failed: %d differences outside the declared edit (first: %s)' % (len(bad), bad[0]), rep)
    ver = ad.validate(new_bytes)    # structure checks (raises on failure)
    rep['validate'] = ver or 'ok'
    return rep


def _produce(doc, new_bytes, manifest, dest, verify):
    """write temp, verify the bytes AS READ BACK FROM DISK; returns (tmp, report)"""
    manifest = manifest or {}; T = {}; t = time.time()
    try:
        tmp = atomic.write_temp(dest, new_bytes)
    except OSError as e:
        raise DiskError('cannot write temp file next to %s: %s' % (dest, e)) from e
    try:
        T['write_tmp'] = time.time() - t; t = time.time()
        with open(long_path(tmp), 'rb') as f: back = f.read()
        if back != new_bytes: raise DiskError('read-back of temp file differs (short write?)')
        T['readback'] = time.time() - t; t = time.time()
        if verify: rep = _verify(doc, back, manifest)
        else:
            rep = {'verify': 'skipped'}      # c2x-rvtgap (c7x finding 242): even with verify off the output must still be a structurally valid container, never a truncated file
            if hasattr(doc.adapter, 'validate'):
                try: doc.adapter.validate(back)
                except SaveError: raise
                except Exception as e: raise VerifyFailed('the output is not a readable file (%s); the original was not touched' % type(e).__name__, dict(error=type(e).__name__))
        T['verify'] = time.time() - t; rep['timing'] = T
        try: w = doc.adapter.weakened()
        except AttributeError: w = []
        if w: rep['weakened'] = w      # c4x-rvtgap 185: env opt-outs that make the gate weaker are never silent
    except BaseException:
        try: os.remove(long_path(tmp))
        except OSError: pass
        raise
    return tmp, rep


def _finish_check(dest, new_bytes):
    h = sha256_file(dest)
    if h != hashlib.sha256(new_bytes).hexdigest():
        raise DiskError('destination content differs after rename (filesystem problem): %s' % dest)
    return h


def save_as(doc, new_bytes, dest, manifest=None, overwrite=False, verify=None):
    if not isinstance(new_bytes, bytes): new_bytes = bytes(new_bytes)      # c4x-rvtgap: snapshot a caller-owned bytearray/memoryview; verified bytes == written bytes == reported hash even if the caller reuses its buffer
    if not __debug__ and not os.environ.get('SAVEGATE_ALLOW_OPTIMIZED'):      # c4x-rvtgap: asserts are the guards of several writer modules; python -O strips them
        raise GateClosed('savegate refuses to write under python -O / PYTHONOPTIMIZE: assert-based guards in the writers are disabled. Run without -O (or set SAVEGATE_ALLOW_OPTIMIZED=1 at your own risk).')
    try:
        return _save_as(doc, new_bytes, dest, manifest, overwrite, verify)
    except OSError as e:
        raise DiskError('save failed, nothing was written: %s' % e) from e


def _check_writable_target(path, cfg):
    try: nl = os.stat(long_path(path)).st_nlink
    except OSError: nl = 1
    if nl > 1 and not cfg.allow_hardlink_break: raise HardlinkTarget('%s has %d hard links: saving would detach the other names (they keep the old content); choose Save As or set allow_hardlink_break' % (path, nl))
    if os.name == 'posix' and os.path.exists(path):      # c7x-rvtread2 193: another process holds an exclusive advisory lock -> replace-by-rename would orphan its handle and silently drop its later writes
        try:
            import fcntl
            with open(path, 'rb') as _f:
                try: fcntl.flock(_f, fcntl.LOCK_SH | fcntl.LOCK_NB)
                except (BlockingIOError, PermissionError): raise Locked('%s is locked by another process (exclusive flock); close it there or choose Save As' % path)
        except (ImportError, OSError): pass
    if not cfg.allow_readonly and os.path.exists(long_path(path)) and atomic.is_readonly(path):
        raise ReadOnlyTarget('%s is read-only: clear the flag, choose Save As, or set allow_readonly' % path)


def _save_as(doc, new_bytes, dest, manifest, overwrite, verify):
    if overwrite and os.path.abspath(dest) != doc.path and os.path.exists(long_path(os.path.abspath(dest))):
        with Lock(os.path.abspath(dest)):      # c4x-rvtgap: replacing an existing file takes its lock like save()/restore() do (a save of that file in another process must not interleave)
            return _save_as_locked(doc, new_bytes, dest, manifest, overwrite, verify)
    return _save_as_locked(doc, new_bytes, dest, manifest, overwrite, verify)


def _save_as_locked(doc, new_bytes, dest, manifest, overwrite, verify):
    t0 = time.time(); verify = doc.cfg.verify if verify is None else verify
    dest = os.path.abspath(dest)
    if overwrite and os.path.abspath(dest) != doc.path: _check_writable_target(dest, doc.cfg)
    if not overwrite and os.path.exists(long_path(dest)): raise Exists('%s exists' % dest)
    if overwrite and os.path.abspath(dest) == doc.path:
        return _save(doc, new_bytes, manifest, False, verify)
    if doc.journal: doc.journal.log('save_as_begin', dest=dest, size=len(new_bytes))
    dm = doc.adapter.source_damage(doc.buf) if hasattr(doc.adapter, 'source_damage') else []      # c4x-rvtgap: BEFORE the verify, so damage already in the source is known and not counted as new damage of the copy
    if dm and not doc.cfg.allow_damaged_edit and bytes(new_bytes) != bytes(doc.buf):
        raise VerifyFailed('the SOURCE file is damaged (%d problem(s), first: %s); an edited copy would carry the damage. Nothing was written. Save an unchanged rescue copy, or set allow_damaged_edit.' % (len(dm), dm[0]), dict(source_damage=dm[:20]))
    tmp, rep = _produce(doc, new_bytes, manifest, dest, verify)
    if hasattr(doc.adapter, 'source_damage'):
        if dm: rep.setdefault('warnings', []).append('the SOURCE file is damaged (%d problem(s), first: %s); the copy carries the same damage and is not confirmed to open in the application' % (len(dm), dm[0]))
    backup = None
    try:
        if os.path.exists(long_path(dest)):
            backup = make_backup(dest, doc.cfg.backup_keep, doc.cfg.backup_max_bytes)
            atomic.commit_temp(tmp, dest, copy_mode_from=dest, keep_readonly=doc.cfg.allow_readonly)      # c4x-rvtgap: keep the old destination's mode/owner/xattrs
        else:
            atomic.link_new(tmp, dest)
    except FileExistsError:
        try: os.remove(long_path(tmp))
        except OSError: pass
        raise Exists('%s exists' % dest)
    except BaseException:
        try: os.remove(long_path(tmp))
        except OSError: pass
        raise
    try: h = _finish_check(dest, new_bytes)
    except DiskError as e:      # c4x-rvtgap: same rule as save(): never leave a destination that does not hold the verified bytes
        if backup is None:
            try: os.remove(long_path(dest)); gone = 'the damaged new file was removed'
            except OSError as e2: gone = 'the damaged new file could NOT be removed (%s)' % e2
            raise DiskError('%s; %s' % (e, gone)) from e
        try:
            with open(long_path(backup), 'rb') as bf: prev = bf.read()
            from .backup import verify_backup
            if not verify_backup(backup): raise DiskError('backup %s fails its recorded hash' % backup)
            tmp2 = atomic.write_temp(dest, prev); atomic.commit_temp(tmp2, dest, copy_mode_from=dest, keep_readonly=doc.cfg.allow_readonly)
            ok = sha256_file(dest) == hashlib.sha256(prev).hexdigest()
        except Exception as e2:
            raise DiskError('%s; automatic restore of the old destination from %s FAILED (%s)' % (e, backup, e2)) from e
        raise DiskError('%s; the old destination was %s from %s' % (e, 'restored' if ok else 'NOT restored correctly', backup)) from e
    if doc.journal: doc.journal.log('save_as_done', dest=dest, sha256=h)
    return SaveResult(True, dest, backup, len(new_bytes), h, rep, time.time() - t0, doc.version)


def save(doc, new_bytes, manifest=None, force=False, verify=None):
    if not isinstance(new_bytes, bytes): new_bytes = bytes(new_bytes)      # c4x-rvtgap: snapshot a caller-owned bytearray/memoryview; verified bytes == written bytes == reported hash even if the caller reuses its buffer
    if not __debug__ and not os.environ.get('SAVEGATE_ALLOW_OPTIMIZED'):      # c4x-rvtgap: asserts are the guards of several writer modules; python -O strips them
        raise GateClosed('savegate refuses to write under python -O / PYTHONOPTIMIZE: assert-based guards in the writers are disabled. Run without -O (or set SAVEGATE_ALLOW_OPTIMIZED=1 at your own risk).')
    try:
        return _save(doc, new_bytes, manifest, force, verify)
    except OSError as e:
        raise DiskError('save failed, original untouched: %s' % e) from e


def _preflight_space(doc, new_bytes):
    """c5x-rvtgap: refuse BEFORE doing any work when a volume cannot hold what the save writes: the new file next to the original (temp copy), the backup of the
    original, and about twice the new size of scratch in the temp dir for the gate's checks. (A full disk was seen to make the checks fail with ENOSPC midway; safe, but late
    and cryptic.) Only checks what can be measured; unknown volumes are skipped."""
    import shutil, tempfile
    need_new = len(new_bytes); need_old = len(doc.buf)
    checks = [(os.path.dirname(os.path.abspath(doc.path)), need_new + (1 << 20), 'the folder of the file'), (tempfile.gettempdir(), 2 * need_new + (1 << 20), 'the temp folder')]
    try:
        from .backup import backup_dirs
        checks.append((backup_dirs(doc.path)[0], need_old + (1 << 20), 'the backup folder'))
    except Exception: pass
    for d, need, what in checks:
        while d and not os.path.isdir(d): d = os.path.dirname(d)
        try: free = shutil.disk_usage(d).free
        except OSError: continue
        if free < need: raise DiskError('not enough free space in %s (%s): %d MB free, %d MB needed; nothing was written, the original is untouched' % (what, d, free >> 20, need >> 20))


def _available_memory():
    """bytes of RAM this process can still use: MemAvailable, lowered by a cgroup limit when one applies; None when unknown"""
    avail = None
    try:
        for l in open('/proc/meminfo'):
            if l.startswith('MemAvailable:'): avail = int(l.split()[1]) * 1024; break
    except (OSError, ValueError): pass
    try:
        cg = open('/proc/self/cgroup').read().strip().split('\n')[-1].split('::')[-1] if os.path.exists('/proc/self/cgroup') else ''
        base = '/sys/fs/cgroup' + cg
        mx = open(base + '/memory.max').read().strip()
        if mx != 'max':
            left = int(mx) - int(open(base + '/memory.current').read().strip())
            avail = left if avail is None else min(avail, left)
    except (OSError, ValueError): pass
    return avail


def _preflight_memory(doc, new_bytes):
    """c5x-rvtread2 item 187: the gate decodes source and output of an RVT (measured peak about 56x the file size: 22 MB -> 1.24 GB; a 51 MB project was OOM-killed at 2 GB).
    Refuse up front, with a clear message, when the free RAM is clearly below 60x the file size, instead of dying midway (the original stays intact either way, but leaves a temp copy
    and no explanation). SAVEGATE_MEM_FACTOR=0 disables the check; unknown free memory skips it. RVT only (OLE header)."""
    try: f = float(os.environ.get('SAVEGATE_MEM_FACTOR', '60'))
    except ValueError: f = 60.0
    if f <= 0 or bytes(doc.buf[:4]) != b'\xd0\xcf\x11\xe0': return
    need = int(f * max(len(new_bytes), len(doc.buf))); avail = _available_memory()
    if avail is not None and avail < need:
        raise LowMemory('not enough free memory to verify this save safely: about %d MB available, about %d MB needed for a %d MB file (set SAVEGATE_MEM_FACTOR=0 to skip this check); nothing was written, the original is untouched' % (avail >> 20, need >> 20, len(doc.buf) >> 20))


def _save(doc, new_bytes, manifest, force, verify):
    """overwrite doc.path. Original is backed up first; verify failure/conflict/IO error leaves it untouched."""
    t0 = time.time(); cfg = doc.cfg; verify = cfg.verify if verify is None else verify
    if not cfg.allow_overwrite: raise OverwriteDisabled('overwrite is disabled in the config (use SAVEAS)')
    fmt = doc.adapter.name
    if cfg.require_gate and not gate_open(fmt, doc.version, cfg):
        raise GateClosed('overwrite of %s %s is not enabled: the oracle test matrix is not green' % (fmt, doc.version))
    _check_writable_target(doc.path, cfg)
    _preflight_space(doc, new_bytes)
    _preflight_memory(doc, new_bytes)
    if hasattr(doc.adapter, 'source_damage'):
        dm = doc.adapter.source_damage(doc.buf)
        if dm: raise VerifyFailed('the file is damaged (%d problem(s), first: %s); overwrite refused, the file was not touched. Use SAVE AS to write a copy.' % (len(dm), dm[0]), dict(source_damage=dm[:20]))
    if hasattr(doc.adapter, 'overwrite_risks'):
        rk = doc.adapter.overwrite_risks(doc.buf)
        if rk: raise VerifyFailed('%s; the file was not touched.' % rk[0], dict(overwrite_risks=rk))
    with Lock(doc.path):
        atomic.sweep_own_temps(doc.path)       # orphans of a killed earlier save of this file
        if not force: check_unchanged(doc.path, doc.fingerprint)
        if doc.journal: doc.journal.log('save_begin', size=len(new_bytes))
        tmp, rep = _produce(doc, new_bytes, manifest, doc.path, verify)
        try:
            if not force: check_unchanged(doc.path, doc.fingerprint, rehash=True)   # last check right before rename
            tb = time.time(); backup = make_backup(doc.path, cfg.backup_keep, cfg.backup_max_bytes, None if force else doc.fingerprint.sha256); rep.setdefault('timing', {})['backup'] = time.time() - tb
            if doc.journal: doc.journal.log('commit', backup=backup)
            old = None
            if os.name != 'nt' and not force:
                try: old = open(long_path(doc.path), 'rb')          # keeps the replaced version readable after the rename (POSIX)
                except OSError: old = None
            tb = time.time(); atomic.commit_temp(tmp, doc.path, copy_mode_from=doc.path, keep_readonly=cfg.allow_readonly); rep['timing']['commit'] = time.time() - tb
            if old is not None:
                with old:
                    prev = old.read()
                if hashlib.sha256(prev).hexdigest() != doc.fingerprint.sha256 and doc.fingerprint.sha256:     # changed in the last milliseconds before the rename
                    from .backup import backup_bytes
                    rep.setdefault('warnings', []).append('another program changed %s in the last moment before it was replaced; that version is kept as backup %s (RESTORE brings it back)' % (doc.path, backup_bytes(doc.path, prev)))
        except BaseException:
            try: os.remove(long_path(tmp))
            except OSError: pass
            raise
        try: h = _finish_check(doc.path, new_bytes)
        except DiskError as e:      # c4x-rvtgap: the renamed file does not hold the verified bytes: put the pre-save file back instead of leaving a damaged original
            if not backup: raise DiskError('%s; NO backup was taken, the file may be damaged' % e) from e
            try:
                with open(long_path(backup), 'rb') as bf: prev_bytes = bf.read()
                want = doc.fingerprint.sha256 or hashlib.sha256(prev_bytes).hexdigest()      # the hash of the file as opened (c1x-review 382): a damaged backup must never be written back as 'restored'
                if hashlib.sha256(prev_bytes).hexdigest() != want: raise DiskError('backup %s does not match the pre-save hash' % backup)
                tmp2 = atomic.write_temp(doc.path, prev_bytes); atomic.commit_temp(tmp2, doc.path, copy_mode_from=doc.path, keep_readonly=cfg.allow_readonly)
                ok = sha256_file(doc.path) == want
            except Exception as e2:
                raise DiskError('%s; automatic restore from %s FAILED (%s): run RESTORE' % (e, backup, e2)) from e
            raise DiskError('%s; the pre-save version was %s from %s' % (e, 'restored' if ok else 'NOT restored correctly (run RESTORE)', backup)) from e
        from .guard import Fingerprint
        st = os.stat(long_path(doc.path))
        doc.buf = new_bytes; doc.fingerprint = Fingerprint(len(new_bytes), st.st_mtime_ns, h)
        if doc.journal: doc.journal.log('save_done', sha256=h)
    return SaveResult(True, doc.path, backup, len(new_bytes), h, rep, time.time() - t0, doc.version)


def restore(path, which=None, allow_readonly=False):
    with Lock(path):      # c5x-rvtread2: restore overwrites the file like a save does; it ran without the lock and could replace a file another process was saving
        return _restore(path, which, allow_readonly)
