"""c2x-rvtgap item 7: numeric edit (GStyle.m_color 0 -> 5) of records whose successor's length link straddles a gzip member boundary (2024 public family,
els 4141, 5728, 6502). Gate accepts, readback is 5, neighbours still decode, only the partition stream changes."""
import os, sys, shutil, struct, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
D = os.path.expanduser('~/rvt-research/samples-rfa/')
CASES = [('racbasicsamplefamily-2024.rfa', 4141), ('racbasicsamplefamily-2024.rfa', 5728), ('racbasicsamplefamily-2024.rfa', 6502), ('racbasicsamplefamily-2026.rfa', 4137), ('racbasicsamplefamily-2026.rfa', 5724), ('racbasicsamplefamily-2026.rfa', 6502)]
SRC = D + CASES[0][0]
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no public sample')

@pytest.mark.parametrize('name,eid', CASES)
def test_boundary_record_numeric_edit(tmp_path, name, eid):
    SRC = D + name
    if not os.path.exists(SRC): pytest.skip('no sample')
    import savegate as sg, wledit, wlrec, cfb
    ed = wledit.Editor(SRC); pn, i, r, log, q = ed.trace(eid)
    o, e = [(l[2], l[3]) for l in log if l[1] == 'GStyle.m_color'][0]; assert e - o == 4
    ed.modify(eid, [(o, 4, struct.pack('<I', 5))]); out = str(tmp_path / 'o.rfa'); ed.save(out); new = open(out, 'rb').read()
    t = str(tmp_path / 'x.rfa'); shutil.copy(SRC, t)
    doc = sg.open_doc(t, None, sg.Config(allow_overwrite=True, require_gate=False))
    sg.save(doc, new, {'modified': ['stream:' + pn, 'el:%d' % eid]})
    B = wlrec.Model(t)
    assert [[l[4] for l in x[3] if l[1] == 'GStyle.m_color'] for x in B.find(eid)][0] == ['5']
    assert all(len(list(B.find(n))) == 1 for n in (eid - 1, eid + 1))
    SA = cfb.CFB(open(SRC, 'rb').read()).streams(); SB = cfb.CFB(open(t, 'rb').read()).streams()
    assert [k for k in SA if SA[k].data != SB[k].data] == [pn]
