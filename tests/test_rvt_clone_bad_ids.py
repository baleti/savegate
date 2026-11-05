"""c2x-rvtgap: a clone whose new id already exists, or has no ElemTable row, must be refused by the gate even when declared as added (2024 sample family)."""
import os, sys, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no public sample')


@pytest.mark.parametrize('new_id', [17, 999999])
def test_declared_clone_with_duplicate_or_unregistered_id_is_refused(tmp_path, new_id):
    import savegate as sg, wledit
    ed = wledit.Editor(SRC); pn = ed.trace(7)[0]; ed.clone(7, new_id)
    o = str(tmp_path / 'o.rfa'); ed.save(o); new = open(o, 'rb').read()
    cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur); before = open(cur, 'rb').read()
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    with pytest.raises(sg.SaveError):
        sg.save(doc, new, {'added': ['el:%d' % new_id], 'modified': ['stream:' + pn]})
    assert open(cur, 'rb').read() == before
