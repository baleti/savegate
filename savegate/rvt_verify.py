"""c4x-rvtgap (queue 78): the gate cannot know the intended new value of a declared element (bit flips inside the declared record pass it).
verify_declared() decodes that element from the source and from the output and demands that exactly the intended fields changed, to exactly the intended values."""
import os, sys


class _LightModel:
    """wlrec.Model that inflates only the named Partitions/* streams (a big project holds many; the declared element lives in a declared one)"""
    def __new__(cls, path, only=None):
        import wlrec
        if not only: return wlrec.Model(path)
        import cfb, rvtw
        full = wlrec.Model.__new__(wlrec.Model)
        S, D, I, ES = wlrec.S, wlrec.D, wlrec.I, wlrec.ES
        full.path = path; full.o, full.cls, full.ids = S.load(path); full.IDW = S.id_size(full.cls); full.IDF = '<I' if full.IDW == 4 else '<Q'
        full.sch = D.Schema(full.cls); full.dec = D.Dec(full.sch, idsize=full.IDW); full.etags = I.element_tags(full.cls)
        try: full.dec.es_schemas = ES.load(path)[0]
        except Exception: full.dec.es_schemas = {}
        full.c = cfb.CFB(open(path, 'rb').read()); full.parts = {}
        for sn, e in full.c.streams().items():
            if sn.startswith('Partitions/') and sn in only:
                st = rvtw.Stream(e.data); P = st.payload; st0 = P.find(rvtw.GZ); mem = rvtw.members(P, st0)
                raws = [rvtw.read_member(P, pos)[0] for pos, end, _ in mem]
                full.parts[sn] = dict(stream=st, mem=mem, raws=raws, joined=b''.join(raws), offs=wlrec.np.cumsum([0] + [len(r) for r in raws]))
        full.idarr = wlrec.np.array(sorted(full.ids), dtype=wlrec.np.uint32 if full.IDW == 4 else wlrec.np.uint64)
        return full


def _fields(path, eid, lib, only=None):
    for p in (lib, os.path.dirname(lib)):
        if p not in sys.path: sys.path.insert(0, p)
    import rvt_decode
    old = getattr(rvt_decode, 'LOGW', 60); rvt_decode.LOGW = 1 << 30      # long strings are compared in full, not on the 60-char log prefix
    try: return _fields2(path, eid, lib, only)
    finally: rvt_decode.LOGW = old


def _fields2(path, eid, lib, only):
    m = _LightModel(path, only)
    recs = list(m.find(eid))
    if not recs: raise ValueError('element %s has no decodable record in %s' % (eid, path))      # the editor edits the first one (which=0), so does this
    return [(x[0], x[1], x[4]) for x in recs[0][3]]


def field_diff(src_path, out_path, eid, lib=None, only=None):
    lib = lib or os.environ.get('SAVEGATE_RVT_LIB') or os.path.expanduser('~/rvt-research/write-lab')
    a = _fields(src_path, eid, lib, only); b = _fields(out_path, eid, lib, only)
    if len(a) != len(b): return None, a, b      # structure changed
    return [(x[1], x[2], y[2]) for x, y in zip(a, b) if x != y], a, b


def verify_declared(src_path, out_path, eid, expected, lib=None, only=None):
    """expected: {field name: new value (as the decoder logs it, usually str)}. Raises ValueError unless the changed fields are exactly these, with these values."""
    d, a, b = field_diff(src_path, out_path, eid, lib, only)
    if d is None: raise ValueError('el:%s: field structure differs (%d fields in the source, %d in the output)' % (eid, len(a), len(b)))
    got = {}
    for n, old, new in d:
        if n in got and got[n] != str(new): raise ValueError('el:%s: field %s changed more than once, to different values' % (eid, n))
        got[n] = str(new)
    exp = {k: str(v) for k, v in expected.items()}
    extra = sorted(set(got) - set(exp)); miss = sorted(set(exp) - set(got)); wrong = sorted(k for k in exp if k in got and got[k] != exp[k])
    if extra or miss or wrong:
        raise ValueError('el:%s: declared element differs from the intent (unexpected %s, not changed %s, wrong value %s)' % (eid, extra[:5], miss[:5], wrong[:5]))
    return True


def verify_new(src_path, out_path, new_id, clone_of=None, expected=None, lib=None):
    """added element: new_id must NOT decode in the source, must decode in the output; with clone_of, every field of the new record (ids excluded)
    must equal the same field of that source element except the ones named in `expected`, which must hold exactly those values."""
    lib = lib or os.environ.get('SAVEGATE_RVT_LIB') or os.path.expanduser('~/rvt-research/write-lab')
    try: _fields(src_path, new_id, lib); raise ValueError('el:%s already exists in the source: it is not an added element' % new_id)
    except ValueError as e:
        if 'already exists' in str(e): raise
    n = _fields(out_path, new_id, lib)
    exp = {k: str(v) for k, v in (expected or {}).items()}
    if clone_of is not None:
        o = _fields(src_path, clone_of, lib)
        if len(o) != len(n): raise ValueError('el:%s: field structure differs from its clone source el:%s (%d vs %d fields)' % (new_id, clone_of, len(n), len(o)))
        bad = [x[1] for x, y in zip(o, n) if x != y and 'm_id' not in x[1] and not (x[1] in exp and str(y[2]) == exp[x[1]])]
        if bad: raise ValueError('el:%s differs from its clone source el:%s in unexpected fields %s' % (new_id, clone_of, sorted(set(bad))[:5]))
    got = {name: str(v) for _, name, v in n}
    wrong = sorted(k for k in exp if got.get(k) != exp[k])
    if wrong: raise ValueError('el:%s: fields %s do not hold the intended values' % (new_id, wrong[:5]))
    return True
