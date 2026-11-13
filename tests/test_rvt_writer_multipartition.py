"""c5x-rvtgap: multi-partition projects. The write lab's rvtgen.Gen used to bind to the FIRST partition only, so every writer op on an element living in another partition of the Autodesk
Snowdon Towers Site 2024 project (Partitions/94 + /96; wall 1139388, instance 359507, level 30 are in /96) failed with 'no element header'. Gen._bind(tid) now binds to the element's partition.
Checks: the op works, the gate accepts it by recomputation, the OTHER partition is byte-identical, a flipped bit is refused, a two-partition edit is refused cleanly."""
import os, sys, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/corpus/2024/47_Snowdon_Towers_Sample_Site.rvt')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no Autodesk sample')
OPS = [{'op': 'move_element', 'allow_dependents': True, 'id': 1139388, 'dx': 1.0}]


def _make(tmp_path, ops=OPS):
    from savegate import rvt_writer_ops as WO
    o = str(tmp_path / 'o.rvt'); WO.run(SRC, ops, o); return o


def _save(tmp_path, nb, ops=OPS):
    import savegate as sg
    cur = str(tmp_path / 'c.rvt'); shutil.copy(SRC, cur); before = open(cur, 'rb').read()
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False, backup_keep=2))
    try: sg.save(doc, nb, {'writer_ops': ops}); ok = True
    except sg.SaveError: ok = False
    return ok, cur, before


def test_move_in_second_partition_accepted_other_partition_identical(tmp_path):
    import wledit
    o = _make(tmp_path); nb = open(o, 'rb').read(); ok, cur, before = _save(tmp_path, nb); assert ok and open(cur, 'rb').read() == nb
    a = wledit.Editor(SRC); b = wledit.Editor(cur)
    assert list(a.m.parts) == ['Partitions/94', 'Partitions/96']
    assert bytes(a.m.parts['Partitions/94']['joined']) == bytes(b.m.parts['Partitions/94']['joined'])
    assert bytes(a.m.parts['Partitions/96']['joined']) != bytes(b.m.parts['Partitions/96']['joined'])


def test_flipped_bit_is_refused(tmp_path):
    nb = bytearray(open(_make(tmp_path), 'rb').read()); nb[len(nb) // 2] ^= 1
    ok, cur, before = _save(tmp_path, bytes(nb)); assert not ok and open(cur, 'rb').read() == before


def test_edit_spanning_two_partitions_is_refused_by_the_writer(tmp_path):
    ops = OPS + [{'op': 'move_element', 'allow_dependents': True, 'id': 1139388 + 0, 'dx': 0}]
    from savegate import rvt_writer_ops as WO
    import wledit
    e = wledit.Editor(SRC); other = [i for i in list(e.m.ids)[:20000] if e.trace(i)[0] == 'Partitions/94'][:1]
    if not other: pytest.skip('no element found in partition 94')
    with pytest.raises(Exception):
        WO.run(SRC, [{'op': 'move_element', 'allow_dependents': True, 'id': 1139388, 'dx': 1.0}, {'op': 'move_element', 'allow_dependents': True, 'id': other[0], 'dx': 1.0}], str(tmp_path / 'x.rvt'))
