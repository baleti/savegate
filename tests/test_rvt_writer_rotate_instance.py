"""c5x-rvtgap RVT-EDIT rung 1 ROTATE (complete form): rotate FamilyInstance 730441 of the Autodesk Snowdon Towers Structural 2024 project by +90 deg about Z through its own origin via the writer
op rotate_instance (Trf.m_3x3, FamilyInstance.m_RefDir, header bounding box of the rotated corners). Gate recomputes the writer result (byte equality); the origin does not move; a flipped bit is refused."""
import os, sys, struct, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt'); EL = 730441
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no Autodesk sample')
OPS = [{'op': 'rotate_instance', 'id': EL, 'deg': 90.0}]


def _f(path):
    import wledit, rvtgen
    a = wledit.Editor(path); t = a.trace(EL); b = a.m.parts[t[0]]['joined']; f = {x[1]: x for x in t[3]}
    g = rvtgen.Gen(path); T = g.template(EL); hl = {n: (o, e) for n, o, e, _ in T['hlog']}
    return dict(M=struct.unpack('<9d', b[f['Trf.m_3x3'][2]:f['Trf.m_3x3'][3]]), o=struct.unpack('<3d', b[f['Trf.m_or'][2]:f['Trf.m_or'][3]]),
                R=struct.unpack('<3d', b[f['FamilyInstance.m_RefDir'][2]:f['FamilyInstance.m_RefDir'][3]]), mm=struct.unpack_from('<6d', T['hdr'], hl['Outline.m_minmax'][0]))


def _make(tmp_path):
    from savegate import rvt_writer_ops as WO
    o = str(tmp_path / 'o.rvt'); WO.run(SRC, OPS, o); return o, open(o, 'rb').read()


def _save(tmp_path, nb):
    import savegate as sg
    cur = str(tmp_path / 'c.rvt'); shutil.copy(SRC, cur); before = open(cur, 'rb').read()
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False, backup_keep=2))
    try: sg.save(doc, nb, {'writer_ops': OPS}); ok = True
    except sg.SaveError: ok = False
    return ok, cur, before


def test_rotate_accepted_matrix_refdir_bbox_and_origin(tmp_path):
    o, nb = _make(tmp_path); ok, cur, before = _save(tmp_path, nb); assert ok and open(cur, 'rb').read() == nb
    old = _f(SRC); new = _f(cur)
    assert new['o'] == pytest.approx(old['o'])
    assert new['R'] == pytest.approx((-old['R'][1], old['R'][0], old['R'][2]), abs=1e-9)
    M = old['M']; exp = []
    cols = [(-M[3], M[0], M[6]), (-M[4], M[1], M[7]), (-M[5], M[2], M[8])]
    assert new['M'] == pytest.approx((cols[0][0], cols[1][0], cols[2][0], cols[0][1], cols[1][1], cols[2][1], cols[0][2], cols[1][2], cols[2][2]), abs=1e-9)
    ox, oy = old['o'][0], old['o'][1]; mm = old['mm']
    pts = [(-(y - oy), x - ox) for x in (mm[0], mm[3]) for y in (mm[1], mm[4])]
    assert new['mm'] == pytest.approx((ox + min(p[0] for p in pts), oy + min(p[1] for p in pts), mm[2], ox + max(p[0] for p in pts), oy + max(p[1] for p in pts), mm[5]), abs=1e-6)


def test_flipped_bit_is_refused(tmp_path):
    o, nb = _make(tmp_path); b = bytearray(nb); b[len(b) // 2] ^= 1
    ok, cur, before = _save(tmp_path, bytes(b)); assert not ok and open(cur, 'rb').read() == before
