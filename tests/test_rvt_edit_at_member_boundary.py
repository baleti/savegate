"""c2x-rvtgap item 7: string edits of the record (partition frame fields, next-record link, member size) on public samples.
Output must keep the element id set, change exactly one stream, pass RvtAdapter.validate and have no source_damage."""
import os, sys, glob, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SAMPLES = sorted(glob.glob(os.path.expanduser('~/rvt-research/samples-rfa/*.rfa')))
pytestmark = pytest.mark.skipif(not SAMPLES, reason='no public samples')


def _boundary_candidates(path, want=2):
    import wledit
    ed = wledit.Editor(path); got = {'before': [], 'after': [], 'straddle': []}
    offs = {}
    for e in sorted(ed.m.ids):
        if all(len(v) >= want for v in got.values()): break
        try: pn, i, r, log, q = ed.trace(e)
        except Exception: continue
        cand = next(((l[1], l[4]) for l in log if isinstance(l[4], str) and 0 < len(l[4]) < 200 and l[3] - l[2] == 4 + 2 * len(l[4]) and l[4] != 'None'), None)
        if not cand: continue
        if pn not in offs: offs[pn] = ed.part(pn).offs()[1:-1]
        for bd in offs[pn]:
            kind = 'straddle' if i < bd < q else 'before' if 0 <= bd - q < 3000 else 'after' if 0 <= i - bd < 3000 else None
            if kind and len(got[kind]) < want: got[kind].append((e,) + cand); break
    return got


@pytest.mark.parametrize('path', SAMPLES, ids=[os.path.basename(p)[-9:] for p in SAMPLES])
def test_edit_next_to_and_across_a_member_boundary(path, tmp_path):
    import wledit, cfb
    from savegate.adapters import RvtAdapter
    got = _boundary_candidates(path)
    n = 0
    for which, lst in got.items():
        for e, fld, txt in lst:
            ed = wledit.Editor(path)
            try: ed.set_string(e, fld, txt + 'XY', match=txt)
            except ValueError: continue      # clean refusal (straddles members / overlapping) is acceptable
            o = str(tmp_path / ('%s%d.rfa' % (which, e))); ed.save(o); b = open(o, 'rb').read()
            A = cfb.CFB(open(path, 'rb').read()).streams(); B = cfb.CFB(b).streams()
            ch = [k for k in A if A[k].data != B[k].data]
            a = RvtAdapter()
            assert len(ch) == 1 and ch[0].startswith('Partitions/'), (which, e, ch)
            assert not a.source_damage(b), (which, e, a.source_damage(b))
            a.validate(b)
            assert sorted(wledit.Editor(o).m.ids) == sorted(wledit.Editor(path).m.ids), (which, e)
            n += 1
    if not n: pytest.skip('no boundary string record found in this sample')


@pytest.mark.parametrize('path', SAMPLES, ids=[os.path.basename(p)[-9:] for p in SAMPLES])
def test_pristine_public_sample_passes_validate_member_limit(path):
    """2016-2018 Autodesk samples have members of 140-146 KB; the 131088 member limit must not refuse the unmodified file (fails without the per-stream source max)"""
    from savegate.adapters import RvtAdapter
    b = open(path, 'rb').read(); a = RvtAdapter(); a.source_damage(b); a.validate(b)


def test_member_limit_allowance_from_the_source_is_capped(tmp_path):
    """an output whose member is far above the limit must be refused even if source_damage was (wrongly) called on that output: the allowance is capped at 147456"""
    import wledit
    from savegate.adapters import RvtAdapter
    p = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
    ed = wledit.Editor(p); ed.set_strings([(7, 'FillPattern.m_name', 'H' + 'X' * 90000)])
    o = str(tmp_path / 'o.rfa'); ed.save(o); b = open(o, 'rb').read(); a = RvtAdapter(); a.source_damage(b)
    with pytest.raises(Exception, match='131088'):
        a.validate(b)
