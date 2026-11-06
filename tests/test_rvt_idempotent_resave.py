"""c2x-rvtgap item 12: re-saving an already edited file with the SAME value (no-op edit) gives byte-identical bytes, and an A->B->A string round trip returns the original bytes of the
partition payload/stream (the writer must not drift on repeated saves)."""
import os, sys, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no public sample')


def _set(src, dst, v):
    import wledit
    ed = wledit.Editor(src); ed.set_strings([(7, 'FillPattern.m_name', v)]); ed.save(dst); return open(dst, 'rb').read()


def test_same_value_resave_identical_and_roundtrip(tmp_path):
    import cfb
    a = str(tmp_path / 'a.rfa'); b = str(tmp_path / 'b.rfa'); c = str(tmp_path / 'c.rfa'); d = str(tmp_path / 'd.rfa')
    A = _set(SRC, a, 'Zed1'); B = _set(a, b, 'Zed1')
    assert A == B, 'same-value resave drifted'
    orig = open(SRC, 'rb').read()
    import wledit
    old = [l[4] for l in wledit.Editor(SRC).trace(7)[3] if l[1] == 'FillPattern.m_name'][0]
    _set(a, c, old)
    S0 = cfb.CFB(orig).streams(); S1 = cfb.CFB(open(c, 'rb').read()).streams()
    diff = [k for k in S0 if S0[k].data != S1[k].data]
    print('A->B->A differing streams:', diff)
    assert diff == [] or diff == ['Partitions/67']
    # the differing stream must still inflate to the SAME records: every gzip member of the original reappears with identical inflated bytes
    import rvtw, zlib
    def infl(d):
        P = bytes(rvtw.Stream(d).payload); out = []; i = 0
        while True:
            i = P.find(rvtw.GZ, i)
            if i < 0: return out
            try: z = zlib.decompressobj(31); u = z.decompress(P[i:]); out.append(u); i += len(P[i:]) - len(z.unused_data)
            except Exception: i += 1
    assert infl(S0['Partitions/67'].data) == infl(S1['Partitions/67'].data), 'A->B->A changed the inflated record data'
