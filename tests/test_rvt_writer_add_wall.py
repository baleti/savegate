"""c5x-rvtgap RVT-EDIT rung 3: ADD a Wall (clone of SWall 585072 of the Autodesk Snowdon Towers Structural 2024 project, +3 ft Y) through the writer op add_element (same machinery as add_instance): new id, record/header/zone/ElemTable row and the
Global/Latest id lists of the template and of its type symbol. The gate recomputes the writer result (byte equality); a flipped bit and a wrong declared id are refused."""
import os, sys, struct, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no Autodesk sample')
OPS = [{'op': 'add_element', 'template': 585072, 'dy': 3.0}]


def _make(tmp_path):
    from savegate import rvt_writer_ops as WO
    o = str(tmp_path / 'o.rvt'); ids = WO.run(SRC, OPS, o); return ids, open(o, 'rb').read()


def _save(tmp_path, nb, added):
    import savegate as sg
    cur = str(tmp_path / 'c.rvt'); shutil.copy(SRC, cur); before = open(cur, 'rb').read()
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False, backup_keep=2))
    try: sg.save(doc, nb, {'writer_ops': OPS, 'added': ['el:%d' % a for a in added]}); ok = True
    except sg.SaveError: ok = False
    return ok, cur, before


def test_add_instance_accepted_registered_and_placed(tmp_path):
    import wledit
    ids, nb = _make(tmp_path); ok, cur, before = _save(tmp_path, nb, ids); assert ok and open(cur, 'rb').read() == nb
    a = wledit.Editor(cur); nid = ids[0]; assert nid in set(a.m.ids)
    t = a.trace(nid); b = a.m.parts[t[0]]['joined']; from savegate import rvt_writer_ops as WO
    pts = [struct.unpack('<3d', b[x[2]:x[3]]) for x in t[3] if x[1] in WO.MOVE_FIELDS and x[3] - x[2] == 24]
    assert pts[0] == pytest.approx((-99.79166666666667, 36.875, -5.916666666666667), abs=1e-6)
    pass


def test_flipped_bit_and_wrong_declared_id_are_refused(tmp_path):
    ids, nb = _make(tmp_path); bad = bytearray(nb); bad[len(bad) // 2] ^= 1
    ok, cur, before = _save(tmp_path, bytes(bad), ids); assert not ok and open(cur, 'rb').read() == before
    ok, cur, before = _save(tmp_path, nb, [ids[0] + 3]); assert not ok and open(cur, 'rb').read() == before
