"""c5x-rvtgap 87: same chain on REAL placed elements (Autodesk Structural 2024 project: FamilyInstance move, FamilyInstance clone, Grid move), so no type is moved or cloned. Original docstring follows. c2x-rvtgap item 60/73: chained in-place gate saves with WRITER ops on an Autodesk 2024 template (public sample): move, add clone, move; each output is the next source.
Every round must be accepted, equal the writer output byte for byte, keep source_damage clean, add exactly one element on the add round, and leave at most backup_keep backups.
Guard (no known bug behind it): a gate that starts refusing a valid chained writer save, or a writer whose output the adapter flags as damaged, fails here."""
import os, sys, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no Autodesk sample')
ROUNDS = [([{'op': 'move_element', 'id': 588559, 'dx': 1.0, 'dy': 0.5}], {}),
          ([{'op': 'add_element', 'template': 589763, 'dy': 3.0}], 'add'),
          ([{'op': 'move_element', 'id': 578141, 'dx': 1.0, 'dy': 0.5}], {})]


def test_chain_move_add_move_placed_elements(tmp_path):
    import savegate as sg, wledit
    from savegate import rvt_writer_ops as WO
    from savegate.adapters import RvtAdapter
    cur = str(tmp_path / 'c.rvt'); shutil.copy(SRC, cur); n0 = len(wledit.Editor(cur).m.ids)
    for ops, kind in ROUNDS:
        out = str(tmp_path / 'o.rvt'); new_ids = WO.run(cur, ops, out); new = open(out, 'rb').read()
        decl = {'writer_ops': ops}
        if kind == 'add': decl['added'] = ['el:%d' % a for a in new_ids]
        doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False, backup_keep=2))
        sg.save(doc, new, decl)
        assert open(cur, 'rb').read() == new
        assert RvtAdapter().source_damage(new) == []
        assert len(sg.list_backups(cur)) <= 2
    assert len(wledit.Editor(cur).m.ids) == n0 + 1
