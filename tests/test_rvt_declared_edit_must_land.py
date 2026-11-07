"""c5x-rvtread2 item 87 (sev3, silent lost edit): the caller declares an edit of element 7 but hands the gate a file whose edited stream is the ORIGINAL source stream (edit not applied).
The gate currently accepts it and the 'saved' file equals the source. A declared edit that did not land should be refused (or at least reported); this test fails until the gate checks it."""
import os, sys, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no public sample')


def test_declared_edit_that_did_not_land_is_refused(tmp_path):
    import savegate as sg, wledit, cfb
    src = open(SRC, 'rb').read()
    ed = wledit.Editor(SRC); ed.set_strings([(7, 'FillPattern.m_name', 'Edited')]); o = str(tmp_path / 'o.rfa'); ed.save(o)
    c = cfb.CFB(open(o, 'rb').read()); S = c.streams(); orig = cfb.CFB(src).streams()
    S['Partitions/67'].data = orig['Partitions/67'].data           # edit silently dropped
    p = str(tmp_path / 'm.rfa'); cfb.write(c, p); b = open(p, 'rb').read()
    cur = str(tmp_path / 'c.rfa'); open(cur, 'wb').write(src)
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    with pytest.raises(sg.SaveError):
        sg.save(doc, b, {'modified': ['stream:Partitions/67', 'el:7']})
    assert open(cur, 'rb').read() == src
