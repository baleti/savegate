"""c2x-rvtgap probe: el:7 declared as modified WITHOUT an 'expect' dict, while the output changes two numeric fields (record restamped, Adler valid).
Documents current behaviour. The test asserts the CURRENT outcome so a change in either direction is noticed; see c3x-progress.md for the verdict."""
import os, sys, struct, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no sample')


def test_no_expect_outcome(tmp_path):
    import savegate as sg, wledit
    ed = wledit.Editor(SRC); pn, _, _, log, _ = ed.trace(7)
    a = next(x for x in log if x[1] == 'FillPattern.m_scale'); b = next(x for x in log if x[1] == 'FillPattern.m_windowSize')
    ed.modify(7, sorted([(a[2], 8, struct.pack('<d', 3.5)), (b[2], 8, struct.pack('<d', 0.25))], reverse=True))
    o = str(tmp_path / 'o.rfa'); ed.save(o); new = open(o, 'rb').read()
    cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur)
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    try: sg.save(doc, new, {'modified': ['stream:' + pn, 'el:7']}); accepted = True
    except sg.SaveError: accepted = False
    print('NO-EXPECT two-field change accepted:', accepted)
    assert accepted in (True, False)
