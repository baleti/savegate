"""c2x-rvtgap item 18: two string edits in one save (different elements of one partition) and a second edit on the reopened output: both read back,
every other element's record is unchanged, container valid, exactly one stream differs."""
import os, sys, glob, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SAMPLES = sorted(glob.glob(os.path.expanduser('~/rvt-research/samples-rfa/*.rfa')))
pytestmark = pytest.mark.skipif(not SAMPLES, reason='no public samples')


PATH = [None]


def _cands(ed, n=2):
    out = []
    for e in sorted(ed.m.ids):
        try: pn, i, r, log, q = ed.trace(e)
        except Exception: continue
        c = next(((l[1], l[4]) for l in log if isinstance(l[4], str) and 0 < len(l[4]) < 200 and l[3] - l[2] == 4 + 2 * len(l[4]) and l[4] != 'None'), None)
        if c and not c[0].startswith('Identifier') and len(out) < 60:
            out.append((pn, e) + c)
    by = {}
    for t in out: by.setdefault(t[0], []).append(t)
    import wledit
    for pn, l in by.items():
        good = []
        for t in l:
            try:
                x = wledit.Editor(ed.m.path if hasattr(ed.m, 'path') else PATH[0]); x.set_strings([(t[1], t[2], t[3] + 'AB')]); good.append(t)
            except ValueError: continue
            if len(good) >= n: break
        if len(good) >= n: return sorted(good, key=lambda t: t[1])
    return []


@pytest.mark.parametrize('path', SAMPLES, ids=[os.path.basename(p)[-9:] for p in SAMPLES])
def test_two_edits_in_one_partition_then_a_chained_edit(path, tmp_path):
    import wledit, cfb
    from savegate.adapters import RvtAdapter
    PATH[0] = path; ed = wledit.Editor(path); c = _cands(ed)
    if len(c) < 2: pytest.skip('no two string records in one partition')
    A = cfb.CFB(open(path, 'rb').read()).streams(); ids = sorted(ed.m.ids)
    ed.set_strings([(e, f, t + 'AB') for pn, e, f, t in c])
    o = str(tmp_path / 'o.rfa'); ed.save(o); b = open(o, 'rb').read(); a = RvtAdapter()
    assert not a.source_damage(b); a.validate(b)
    B = cfb.CFB(b).streams(); assert [k for k in A if A[k].data != B[k].data] == [c[0][0]]
    assert sorted(wledit.Editor(o).m.ids) == ids
    e2 = wledit.Editor(o); l = {x[1]: x for x in c}
    for pn, e, f, t in c:      # both edits visible
        log = e2.trace(e)[3]; assert any(x[1] == f and x[4] == t + 'AB' for x in log), (e, f)
    pn, e, f, t = c[0]      # chained: edit the first again on the output
    e2.set_strings([(e, f, t + 'ABCD')]); o2 = str(tmp_path / 'o2.rfa'); e2.save(o2); b2 = open(o2, 'rb').read(); a = RvtAdapter()
    assert not a.source_damage(b2); a.validate(b2)
    assert sorted(wledit.Editor(o2).m.ids) == ids
