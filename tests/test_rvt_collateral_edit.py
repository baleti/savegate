"""c2x-rvtgap item 44: output changes TWO elements (same member), only one declared: the gate must refuse and leave the original untouched."""
import os, sys, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no public sample')


def test_undeclared_second_element_change_is_refused(tmp_path):
    import savegate as sg, wledit
    base = wledit.Editor(SRC); found = None
    for e in sorted(base.m.ids):
        if e == 7: continue
        r = base.trace(e)[2]
        # first string field of another element, as the earlier sweeps do
        import json
        for line in base.trace(e)[3]:
            if line[1].endswith('m_name'): found = (e, line[1]); break
        if found: break
    assert found, 'no second element with a name field'
    ed = wledit.Editor(SRC)
    try: ed.set_strings([(7, 'FillPattern.m_name', 'Collateral A'), (found[0], found[1], 'Collateral B')])
    except Exception as ex: pytest.skip('editor refused: %s' % ex)
    o = str(tmp_path / 'o.rfa'); ed.save(o); new = open(o, 'rb').read()
    cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur); before = open(cur, 'rb').read()
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    with pytest.raises(sg.SaveError):
        sg.save(doc, new, {'modified': ['stream:Partitions/67', 'el:7']})
    assert open(cur, 'rb').read() == before
