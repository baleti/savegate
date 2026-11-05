"""c2x-rvtgap item 17: deleting an element that OTHER elements reference (element 0 is m_ownerId of 1 and 3; 11 owns 12; 14 owns 15) leaves dangling references. Record what the gate does."""
import os, sys, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no public sample')


@pytest.mark.parametrize('eid', [0, 11, 14])
def test_declared_delete_of_a_referenced_element_is_refused(tmp_path, eid):
    import savegate as sg, wledit
    ed = wledit.Editor(SRC); pn = ed.trace(eid)[0]; ed.delete(eid)
    o = str(tmp_path / 'n.rfa'); ed.save(o); new = open(o, 'rb').read()
    cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur); before = open(cur, 'rb').read()
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    with pytest.raises(sg.SaveError):
        sg.save(doc, new, {'modified': ['stream:' + pn], 'deleted': ['el:%d' % eid]})
    assert open(cur, 'rb').read() == before
