"""c5x-rvtgap item 20: a move in each of two different partitions of Autodesk Snowdon Electrical 2026 (4 partitions) is gate-accepted, only the edited partition differs; a save spanning two partitions is refused by the writer. Slow (3-4 min per save)."""
import os, sys, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/corpus/2026/56_Snowdon_Towers_Sample_Electrical.rvt')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no Autodesk sample')
CASES = [('Partitions/38', 1721627), ('Partitions/39', 1566354)]


@pytest.mark.parametrize('part,eid', CASES)
def test_move_in_partition_accepted_only_that_partition_differs(tmp_path, part, eid):
    import savegate as sg, wledit
    from savegate import rvt_writer_ops as WO
    ops = [{'op': 'move_element', 'id': eid, 'dx': 1.0}]
    o = str(tmp_path / 'o.rvt'); WO.run(SRC, ops, o); nb = open(o, 'rb').read()
    cur = str(tmp_path / 'c.rvt'); shutil.copy(SRC, cur)
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False, backup_keep=2))
    sg.save(doc, nb, {'writer_ops': ops}); assert open(cur, 'rb').read() == nb
    a = wledit.Editor(SRC); b = wledit.Editor(cur)
    assert [p for p in a.m.parts if bytes(a.m.parts[p]['joined']) != bytes(b.m.parts[p]['joined'])] == [part]


def test_edit_spanning_two_partitions_refused(tmp_path):
    from savegate import rvt_writer_ops as WO
    with pytest.raises(Exception):
        WO.run(SRC, [{'op': 'move_element', 'id': e, 'dx': 1.0} for _, e in CASES], str(tmp_path / 'x.rvt'))
