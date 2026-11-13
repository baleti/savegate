"""c5x-rvtgap RVT-EDIT rung 1 (complete form): MOVE FamilyInstance 730441 of the Autodesk Snowdon Towers Structural 2024 project by +1 ft X through the trusted writer (rvt_writer_ops
'move_instance'): Trf.m_or, header Outline.m_minmax and the (x, y) pair of the zone record all move together (a record-only edit leaves the bounding box and zone copy stale). The gate recomputes
the writer result (byte equality); a flipped bit is refused. Local gate-level checks; Revit-VM verdict is separate."""
import os, sys, struct, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt'); EL = 730441
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no Autodesk sample')
OPS = [{'op': 'move_instance', 'allow_dependents': True, 'id': EL, 'dx': 1.0}]


def _make(tmp_path):
    from savegate import rvt_writer_ops as WO
    o = str(tmp_path / 'o.rvt'); WO.run(SRC, OPS, o); return open(o, 'rb').read()


def _save(tmp_path, nb):
    import savegate as sg
    cur = str(tmp_path / 'c.rvt'); shutil.copy(SRC, cur); before = open(cur, 'rb').read()
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False, backup_keep=2))
    try: sg.save(doc, nb, {'writer_ops': OPS}); ok = True
    except sg.SaveError: ok = False
    return ok, cur, before


def test_full_instance_move_accepted_and_all_position_copies_moved(tmp_path):
    import wledit, rvtgen
    nb = _make(tmp_path); ok, cur, before = _save(tmp_path, nb); assert ok and open(cur, 'rb').read() == nb
    a = wledit.Editor(cur); t = a.trace(EL); b = a.m.parts[t[0]]['joined']; o = [x for x in t[3] if x[1] == 'Trf.m_or'][0]
    assert struct.unpack('<3d', b[o[2]:o[3]]) == pytest.approx((-89.79166666666667, 25.625, 16.75))
    g = rvtgen.Gen(cur); T = g.template(EL); hl = {n: (oo, e) for n, oo, e, _ in T['hlog']}
    assert struct.unpack_from('<6d', T['hdr'], hl['Outline.m_minmax'][0]) == pytest.approx((-90.375, 25.208333333333, 16.75, -89.375, 26.041666666667, 18.333333333333), rel=1e-6)
    assert struct.unpack_from('<2d', T['item'], 276) == pytest.approx((-89.79166666666667, 25.625))


def test_flipped_bit_is_refused(tmp_path):
    nb = bytearray(_make(tmp_path)); nb[len(nb) // 2] ^= 1
    ok, cur, before = _save(tmp_path, bytes(nb)); assert not ok and open(cur, 'rb').read() == before
