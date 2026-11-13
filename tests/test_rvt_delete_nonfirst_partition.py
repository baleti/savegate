"""c5x-rvtgap item 30: deleting an unreferenced element in a non-first partition of Autodesk Snowdon Electrical 2026 is gate-accepted and only that partition differs; a delete in /38 plus a clone template from /39 is refused by the writer; a referenced element is refused by the cascade planner (nothing written). Slow (about 3 min per save)."""
import os, sys, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/corpus/2026/56_Snowdon_Towers_Sample_Electrical.rvt')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no Autodesk sample')
CASES = [('Partitions/38', 1559995), ('Partitions/39', 1478813)]   # unreferenced TextNotes


@pytest.mark.parametrize('part,eid', CASES)
def test_delete_textnote_accepted_only_that_partition_differs(tmp_path, part, eid):
    import savegate as sg, wledit
    from savegate import rvt_writer_ops as WO
    ops = [{'op': 'delete_cascade', 'id': eid}]
    o = str(tmp_path / 'o.rvt'); WO.run(SRC, ops, o); nb = open(o, 'rb').read()
    cur = str(tmp_path / 'c.rvt'); shutil.copy(SRC, cur)
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False, backup_keep=2))
    sg.save(doc, nb, {'writer_ops': ops, 'deleted': ['el:%d' % eid]}); assert open(cur, 'rb').read() == nb
    a = wledit.Editor(SRC); b = wledit.Editor(cur)
    assert [p for p in a.m.parts if bytes(a.m.parts[p]['joined']) != bytes(b.m.parts[p]['joined'])] == [part]


def test_delete_in_38_with_clone_from_39_refused(tmp_path):
    from savegate import rvt_writer_ops as WO
    with pytest.raises(Exception):
        WO.run(SRC, [{'op': 'delete_cascade', 'id': 1559995}, {'op': 'add_element', 'template': 1566354, 'dy': 3.0}], str(tmp_path / 'x.rvt'))
    assert not os.path.exists(str(tmp_path / 'x.rvt'))


def test_referenced_element_cascade_refused():
    from savegate import rvt_writer_ops as WO
    with pytest.raises(ValueError):
        WO.cascade_plan(SRC, 1566354)   # referenced by an RbsConduitCurve
