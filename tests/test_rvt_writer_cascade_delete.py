"""c5x-rvtgap RVT-EDIT rung 2 (dependents): delete a FamilyInstance together with the annotation that hosts on it (Autodesk Snowdon Towers Structural 2024: instance 870670 and its BeamSystemTag 870669)
through the writer op delete_cascade. The planner (rvt_writer_ops.cascade_plan) follows only annotation referrers; the gate recomputes the same plan and the writer result (byte equality) and requires that
nothing outside the deleted set references the deleted ids. A plain delete of the instance alone is refused (its tag would dangle); an instance a joist system references cannot be planned."""
import os, sys, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no Autodesk sample')
CAS = [{'op': 'delete_cascade', 'id': 870670}]


def _save(tmp_path, ops, deleted, nb):
    import savegate as sg
    cur = str(tmp_path / 'c.rvt'); shutil.copy(SRC, cur); before = open(cur, 'rb').read()
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False, backup_keep=2))
    try: sg.save(doc, nb, {'writer_ops': ops, 'deleted': ['el:%d' % d for d in deleted]}); ok = True
    except sg.SaveError: ok = False
    return ok, cur, before


def test_cascade_plan_and_refusals():
    from savegate import rvt_writer_ops as WO
    assert WO.cascade_plan(SRC, 870670) == [870669, 870670]
    for el in (610663, 608386):
        with pytest.raises(ValueError): WO.cascade_plan(SRC, el)


def test_cascade_delete_accepted_and_both_gone(tmp_path):
    import wledit
    from savegate import rvt_writer_ops as WO
    o = str(tmp_path / 'o.rvt'); WO.run(SRC, CAS, o); nb = open(o, 'rb').read()
    ok, cur, before = _save(tmp_path, CAS, [870669, 870670], nb); assert ok and open(cur, 'rb').read() == nb
    ids = set(wledit.Editor(cur).m.ids); assert 870669 not in ids and 870670 not in ids


def test_plain_delete_of_a_referenced_instance_is_refused(tmp_path):
    from savegate import rvt_writer_ops as WO
    ops = [{'op': 'delete', 'id': 870670}]; o = str(tmp_path / 'o.rvt'); WO.run(SRC, ops, o); nb = open(o, 'rb').read()
    ok, cur, before = _save(tmp_path, ops, [870670], nb); assert not ok and open(cur, 'rb').read() == before
