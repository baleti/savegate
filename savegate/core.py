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
    gate_file: str = None             # default: <cache>/gate.json or $SAVEGATE_GATE
    journal_dir: str = None
    verify: bool = True


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
    with open(long_path(path), 'rb') as f: buf = f.read()
    st = os.stat(long_path(path))
    from .guard import Fingerprint
    fp = Fingerprint(len(buf), st.st_mtime_ns, hashlib.sha256(buf).hexdigest())
    ad, ver = pick_adapter(buf, adapter)
    atomic.sweep_stale_temps(os.path.dirname(os.path.abspath(path)))
    j = Journal(path, cfg.journal_dir) if journal else None
    return Doc(path, buf, ad, ver, fp, cfg, j)


def _verify(doc, new_bytes, manifest):
    ad = doc.adapter
    a = ad.snapshot(doc.buf); b = ad.snapshot(new_bytes)
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
    missing = [('not_modified', k) for k in allowed_mod if k in a and k in b and a[k] == b[k]]  # informational
    rep = dict(objects_src=len(a), objects_out=len(b), unexpected=bad[:50], n_unexpected=len(bad), declared_noop=missing[:50])
    if bad:
        raise VerifyFailed('verify failed: %d differences outside the declared edit (first: %s)' % (len(bad), bad[0]), rep)
    ver = ad.validate(new_bytes)    # structure checks (raises on failure)
    rep['validate'] = ver or 'ok'
    return rep


def _produce(doc, new_bytes, manifest, dest, verify):
    """write temp, verify the bytes AS READ BACK FROM DISK; returns (tmp, report)"""
    manifest = manifest or {}
    try:
        tmp = atomic.write_temp(dest, new_bytes)
    except OSError as e:
        raise DiskError('cannot write temp file next to %s: %s' % (dest, e)) from e
    try:
        with open(long_path(tmp), 'rb') as f: back = f.read()
        if back != new_bytes: raise DiskError('read-back of temp file differs (short write?)')
        rep = _verify(doc, back, manifest) if verify else {'verify': 'skipped'}
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
    try:
        return _save_as(doc, new_bytes, dest, manifest, overwrite, verify)
    except OSError as e:
        raise DiskError('save failed, nothing was written: %s' % e) from e


def _save_as(doc, new_bytes, dest, manifest, overwrite, verify):
    t0 = time.time(); verify = doc.cfg.verify if verify is None else verify
    dest = os.path.abspath(dest)
    if not overwrite and os.path.exists(long_path(dest)): raise Exists('%s exists' % dest)
    if overwrite and os.path.abspath(dest) == doc.path:
        return _save(doc, new_bytes, manifest, False, verify)
    if doc.journal: doc.journal.log('save_as_begin', dest=dest, size=len(new_bytes))
    tmp, rep = _produce(doc, new_bytes, manifest, dest, verify)
    backup = None
    try:
        if os.path.exists(long_path(dest)):
            backup = make_backup(dest, doc.cfg.backup_keep)
            atomic.commit_temp(tmp, dest)
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
    h = _finish_check(dest, new_bytes)
    if doc.journal: doc.journal.log('save_as_done', dest=dest, sha256=h)
    return SaveResult(True, dest, backup, len(new_bytes), h, rep, time.time() - t0, doc.version)


def save(doc, new_bytes, manifest=None, force=False, verify=None):
    try:
        return _save(doc, new_bytes, manifest, force, verify)
    except OSError as e:
        raise DiskError('save failed, original untouched: %s' % e) from e


def _save(doc, new_bytes, manifest, force, verify):
    """overwrite doc.path. Original is backed up first; verify failure/conflict/IO error leaves it untouched."""
    t0 = time.time(); cfg = doc.cfg; verify = cfg.verify if verify is None else verify
    if not cfg.allow_overwrite: raise OverwriteDisabled('overwrite is disabled in the config (use SAVEAS)')
    fmt = doc.adapter.name
    if cfg.require_gate and not gate_open(fmt, doc.version, cfg):
        raise GateClosed('overwrite of %s %s is not enabled: the oracle test matrix is not green' % (fmt, doc.version))
    with Lock(doc.path):
        if not force: check_unchanged(doc.path, doc.fingerprint)
        if doc.journal: doc.journal.log('save_begin', size=len(new_bytes))
        tmp, rep = _produce(doc, new_bytes, manifest, doc.path, verify)
        try:
            if not force: check_unchanged(doc.path, doc.fingerprint, rehash=True)   # last check right before rename
            backup = make_backup(doc.path, cfg.backup_keep)
            if doc.journal: doc.journal.log('commit', backup=backup)
            atomic.commit_temp(tmp, doc.path, copy_mode_from=doc.path)
        except BaseException:
            try: os.remove(long_path(tmp))
            except OSError: pass
            raise
        h = _finish_check(doc.path, new_bytes)
        from .guard import Fingerprint
        st = os.stat(long_path(doc.path))
        doc.buf = new_bytes; doc.fingerprint = Fingerprint(len(new_bytes), st.st_mtime_ns, h)
        if doc.journal: doc.journal.log('save_done', sha256=h)
    return SaveResult(True, doc.path, backup, len(new_bytes), h, rep, time.time() - t0, doc.version)


def restore(path, which=None):
    return _restore(path, which)
