"""c4x-rvtgap item 457b: valid delete of an unreferenced TextNote (Partitions/38) declared with writer_ops (the only manifest the gate accepts for a delete: a manifest-only delete is refused even without a flip, ElemTable etc. change; verify_writer_ops recomputes the output byte for byte) plus ONE bit flip in the undeclared Partitions/41 (id/table bytes):
must be refused with the original byte-identical. Slow (minutes), ~1.5 GB; run with SAVEGATE_MEM_FACTOR=0 under a memory cap."""
import os, sys, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/corpus/2026/56_Snowdon_Towers_Sample_Electrical.rvt')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no Autodesk sample')
E = 1559995


@pytest.mark.parametrize('flip', [False, True])
def test_delete_plus_flip_in_other_partition(tmp_path, flip):
    import savegate as sg, wledit
    from savegate import rvt_writer_ops as WO
    ops = [{'op': 'delete_cascade', 'id': E}]; o = str(tmp_path / 'o.rvt'); WO.run(SRC, ops, o); man = {'writer_ops': ops, 'deleted': ['el:%d' % E]}
    if flip:
        ed = wledit.Editor(o); p = 'Partitions/41'; b = ed.m.parts[p]['joined']; ed.part(p).replace(133718, 1, bytes([b[133718] ^ 1])); o2 = str(tmp_path / 'o2.rvt'); ed.save(o2); del ed; o = o2
    nb = open(o, 'rb').read()
    cur = str(tmp_path / 'c.rvt'); shutil.copy(SRC, cur); orig = open(cur, 'rb').read()
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False, journal_dir=str(tmp_path / 'j')))
    if not flip:
        sg.save(doc, nb, man); return
    with pytest.raises(sg.SaveError): sg.save(doc, nb, man)
    assert open(cur, 'rb').read() == orig
