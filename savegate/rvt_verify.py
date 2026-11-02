"""c4x-rvtgap (queue 78): the gate cannot know the intended new value of a declared element (bit flips inside the declared record pass it).
verify_declared() decodes that element from the source and from the output and demands that exactly the intended fields changed, to exactly the intended values."""
import os, sys


def _fields(path, eid, lib):
    for p in (lib, os.path.dirname(lib)):
        if p not in sys.path: sys.path.insert(0, p)
    import wlrec
    m = wlrec.Model(path)
    recs = list(m.find(eid))
    if not recs: raise ValueError('element %s has no decodable record in %s' % (eid, path))      # the editor edits the first one (which=0), so does this
    return [(x[0], x[1], x[4]) for x in recs[0][3]]


def field_diff(src_path, out_path, eid, lib=None):
    lib = lib or os.environ.get('SAVEGATE_RVT_LIB') or os.path.expanduser('~/rvt-research/write-lab')
    a = _fields(src_path, eid, lib); b = _fields(out_path, eid, lib)
    if len(a) != len(b): return None, a, b      # structure changed
    return [(x[1], x[2], y[2]) for x, y in zip(a, b) if x != y], a, b


def verify_declared(src_path, out_path, eid, expected, lib=None):
    """expected: {field name: new value (as the decoder logs it, usually str)}. Raises ValueError unless the changed fields are exactly these, with these values."""
    d, a, b = field_diff(src_path, out_path, eid, lib)
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
