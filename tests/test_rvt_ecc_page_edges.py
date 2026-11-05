"""c2x-rvtgap item 8: string growth that moves the partition payload to just below / on / just above an ECC page boundary (and shrinks back):
output must pass source_damage (ECC + gzip CRC), validate, keep the id set and change exactly one stream."""
import os, sys, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SAMPLES = [os.path.expanduser('~/rvt-research/samples-rfa/%s.rfa' % n) for n in ('rac_basic_sample_family-2018', 'racbasicsamplefamily-2022', 'racbasicsamplefamily-2024', 'racbasicsamplefamily-2026')]
SAMPLES = [s for s in SAMPLES if os.path.exists(s)]
pytestmark = pytest.mark.skipif(not SAMPLES, reason='no public samples')


@pytest.mark.parametrize('path', SAMPLES, ids=[os.path.basename(p)[-9:] for p in SAMPLES])
def test_growth_around_ecc_page_boundaries(path, tmp_path):
    import wledit, cfb, rvtw
    from savegate.adapters import RvtAdapter
    ed0 = wledit.Editor(path); pn = ed0.trace(7)[0]; L = len(ed0.m.parts[pn]['stream'].payload); PG = rvtw.PAGE_PAYLOAD
    base = ed0.trace(7)[2]['fields']['m_pFillPattern']['obj']['m_name']
    nxt = (L // PG + 1) * PG
    cs = sorted({max(1, (nxt - L) // 2 + d) for d in (-3, -2, -1, 0, 1, 2, 3)} | {1, 2, 31, 32, 33})
    A = cfb.CFB(open(path, 'rb').read()).streams(); ids = sorted(ed0.m.ids); n = 0
    for c in cs:
        ed = wledit.Editor(path)
        try: ed.set_strings([(7, 'FillPattern.m_name', base + 'x' * c)])
        except ValueError: continue          # clean refusal is acceptable
        o = str(tmp_path / ('g%d.rfa' % c)); ed.save(o); b = open(o, 'rb').read(); a = RvtAdapter()
        assert not a.source_damage(b), (c, a.source_damage(b))
        a.validate(b)
        B = cfb.CFB(b).streams(); ch = [k for k in A if A[k].data != B[k].data]
        assert ch == [pn], (c, ch)
        assert sorted(wledit.Editor(o).m.ids) == ids, c
        n += 1
    assert n >= 3, 'too few growth sizes were accepted (%d)' % n
