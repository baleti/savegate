"""Element-level snapshot for RvtAdapter(elements_fn=...): decodes the output with the pure-Python reader and
returns {element_id: comparable} (class + geometry bbox/confidence + solids hash). Heavy for big files: run the
save verification for RVT on a worker host; for the small writer scenes it takes seconds."""
import os, sys, tempfile, hashlib, json


def _geom_one(a):
    p, eid = a
    import rvt_geometry as G
    try:
        r = G.element_geometry(p, eid)
        return eid, '|' + json.dumps([r.get('class'), r.get('confidence'), r.get('bbox'), r.get('transform')], default=repr, sort_keys=True) + '|' + hashlib.sha1(json.dumps(r.get('solids'), default=repr, sort_keys=True).encode()).hexdigest()
    except Exception as e:
        return eid, '|ERR ' + type(e).__name__


def _cache_path(buf, flags):
    base = os.environ.get('SAVEGATE_CACHE') or os.path.join(os.environ.get('XDG_CACHE_HOME', os.path.expanduser('~/.cache')), 'savegate')
    return os.path.join(base, 'elsnap', hashlib.sha256(buf).hexdigest()[:32] + flags + '.json')


def elements(buf, reader_dir=None, with_geometry=True, with_params=True, with_records=True):
    """Snapshot of every element; results are cached on disk by the SHA-256 of the file (a second Save of the same source, or the
    source of a chain of saves, costs nothing), geometry runs in SAVEGATE_RVT_WORKERS fork workers (default min(4, cpus))."""
    cp = _cache_path(buf, '%d%d%d' % (with_geometry, with_params, with_records))
    try: return {int(k): v for k, v in json.load(open(cp)).items()}
    except (OSError, ValueError): pass
    out = _elements(buf, reader_dir, with_geometry, with_params, with_records)
    try:
        os.makedirs(os.path.dirname(cp), exist_ok=True); t = cp + '.%d.tmp' % os.getpid()
        json.dump(out, open(t, 'w')); os.replace(t, cp)
        old = sorted((os.path.join(os.path.dirname(cp), f) for f in os.listdir(os.path.dirname(cp)) if f.endswith('.json')), key=os.path.getmtime)
        for f in old[:-8]: os.remove(f)        # keep the 8 newest snapshots
    except OSError: pass
    return out


def _elements(buf, reader_dir=None, with_geometry=True, with_params=True, with_records=True):
    reader_dir = reader_dir or os.environ.get('SAVEGATE_RVT_READER') or os.path.expanduser('~/rvt-research')
    if reader_dir not in sys.path: sys.path.insert(0, reader_dir)
    import rvt_geometry as G
    fd, p = tempfile.mkstemp(suffix='.rvt'); os.close(fd)
    try:
        with open(p, 'wb') as f: f.write(buf)
        idx = G.file_geometry_index(p)
        out = {}
        geo = {}
        if with_geometry:
            n = int(os.environ.get('SAVEGATE_RVT_WORKERS', min(4, os.cpu_count() or 1)))
            if n > 1 and len(idx) > 200 and hasattr(os, 'fork'):
                import multiprocessing as mp
                with mp.get_context('fork').Pool(n) as pool:
                    geo = dict(pool.imap_unordered(_geom_one, [(p, e) for e in idx], chunksize=64))
            else:
                geo = dict(_geom_one((p, e)) for e in idx)
        for eid, cls in idx.items():
            out[eid] = str(cls) + geo.get(eid, '')
        if with_records:    # every decoded record field per element (text notes, tags and other classes without geometry or parameters)
            import rvt_xcache
            x = rvt_xcache.get_x_ro(p); acc = {}
            for (eid, c), r in x['recs'].items():
                acc.setdefault(eid, []).append((c, hashlib.sha1(repr(r.get('fields')).encode()).hexdigest()))
            for eid, lst in acc.items():
                if eid in out: out[eid] += '|R' + hashlib.sha1(repr(sorted(lst)).encode()).hexdigest()
        if with_params:     # parameter values (stored + derived) per element: a parameter-only edit must show up too
            import rvt_params
            pr = rvt_params.params(p)
            for eid, d in pr.items():
                if eid in out: out[eid] += '|P' + hashlib.sha1(json.dumps(d, default=repr, sort_keys=True).encode()).hexdigest()
        return out
    finally:
        os.remove(p)


def id_state(buf, reader_dir=None, lib=None):
    """c4x-rvtgap: fast structural check (no decoding): every ElemTable id must have a record header whose length field is confirmed by the next record's
    A link. Returns the sorted ids that have none. On 266 rosetta scenes: 0 unresolved, 0.03 s on a 5k-element scene; the old double-edit writer bug leaves exactly the next element unresolved."""
    reader_dir = reader_dir or os.environ.get('SAVEGATE_RVT_READER') or os.path.expanduser('~/rvt-research')
    lib = lib or os.environ.get('SAVEGATE_RVT_LIB') or os.path.join(reader_dir, 'write-lab')
    for d in (reader_dir, lib):
        if d not in sys.path: sys.path.insert(0, d)
    import struct, wlrec, rvt_scan as S
    fd, p = tempfile.mkstemp(suffix='.rvt'); os.close(fd)
    try:
        with open(p, 'wb') as f: f.write(buf)
        m = wlrec.Model(p); W = m.IDW; found = set()
        for pn, part in m.parts.items():
            b = part['joined']; n = len(b)
            for i in S.header_candidates_tagged(b, m.idarr, W, m.etags).tolist():
                if i + 16 + W > n: continue
                L = struct.unpack_from('<I', b, i + 8 + W)[0]; q = i + 12 + W + L
                if q + 4 <= n and struct.unpack_from('<I', b, q)[0] == L: found.add(struct.unpack_from(m.IDF, b, i + 4)[0])
        return sorted(int(x) for x in m.ids), sorted(int(x) for x in m.ids if int(x) not in found)
    finally:
        os.remove(p)


def unresolved_ids(buf, reader_dir=None, lib=None):
    return id_state(buf, reader_dir, lib)[1]
