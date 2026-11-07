"""c5x-rvtgap RVT-EDIT rung 1 (complete form): MOVE a Wall (585072, +1 ft Y), a Grid (578141, +1 ft X) and a Level (32567, +1 ft Z) of the Autodesk Snowdon Towers Structural 2024 project through the
trusted writer op move_element: every origin triple of the record, the header bounding box when present and the zone pair move together. The gate recomputes the writer result (byte equality)."""
import os, sys, struct, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no Autodesk sample')
CASES = {'wall': (585072, (0.0, 1.0, 0.0)), 'grid': (578141, (1.0, 0.0, 0.0)), 'level': (32567, (0.0, 0.0, 1.0))}


def _origins(path, el):
    import wledit
    from savegate import rvt_writer_ops as WO
    a = wledit.Editor(path); t = a.trace(el); b = a.m.parts[t[0]]['joined']
    return [struct.unpack('<3d', b[x[2]:x[3]]) for x in t[3] if x[1] in WO.MOVE_FIELDS and x[3] - x[2] == 24]


@pytest.mark.parametrize('kind', ['wall', 'grid', 'level'])
def test_move_accepted_and_every_origin_moved(tmp_path, kind):
    import savegate as sg
    from savegate import rvt_writer_ops as WO
    el, d = CASES[kind]; ops = [{'op': 'move_element', 'id': el, 'dx': d[0], 'dy': d[1], 'dz': d[2]}]
    o = str(tmp_path / 'o.rvt'); WO.run(SRC, ops, o); nb = open(o, 'rb').read()
    cur = str(tmp_path / 'c.rvt'); shutil.copy(SRC, cur)
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False, backup_keep=2))
    sg.save(doc, nb, {'writer_ops': ops}); assert open(cur, 'rb').read() == nb
    old = _origins(SRC, el); new = _origins(cur, el); assert len(old) == len(new) >= 2
    for p, q in zip(old, new): assert q == pytest.approx((p[0] + d[0], p[1] + d[1], p[2] + d[2]))
