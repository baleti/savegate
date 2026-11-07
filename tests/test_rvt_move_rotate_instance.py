"""c5x-rvtgap RVT-EDIT rung 1: MOVE (+1 ft X via Trf.m_or) and ROTATE (+90 deg about Z via Trf.m_3x3 and FamilyInstance.m_RefDir) of FamilyInstance 730441 in the Autodesk Snowdon Towers
Structural 2024 sample. The gate accepts both with manifest derived_ok, the readback equals the expectation. Local gate-level checks only; Revit-VM verdict is separate."""
import os, sys, struct, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt'); EL = 730441
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no Autodesk sample')


def _fields(ed):
    t = ed.trace(EL); b = ed.m.parts[t[0]]['joined']; f = {x[1]: x for x in t[3] if x[1] in ('Trf.m_or', 'Trf.m_3x3', 'FamilyInstance.m_RefDir')}
    return t[0], b, f


def _rz(v): return [-v[1], v[0], v[2]]


def _edit(kind):
    import wledit
    ed = wledit.Editor(SRC); pn, b, f = _fields(ed)
    if kind == 'move':
        o = struct.unpack('<3d', b[f['Trf.m_or'][2]:f['Trf.m_or'][3]]); new = {'Trf.m_or': [o[0] + 1.0, o[1], o[2]]}
        ed.modify(EL, [(f['Trf.m_or'][2], 24, struct.pack('<3d', *new['Trf.m_or']))])
    else:
        M = struct.unpack('<9d', b[f['Trf.m_3x3'][2]:f['Trf.m_3x3'][3]]); R = struct.unpack('<3d', b[f['FamilyInstance.m_RefDir'][2]:f['FamilyInstance.m_RefDir'][3]])
        cols = [_rz([M[0], M[3], M[6]]), _rz([M[1], M[4], M[7]]), _rz([M[2], M[5], M[8]])]
        nm = [cols[0][0], cols[1][0], cols[2][0], cols[0][1], cols[1][1], cols[2][1], cols[0][2], cols[1][2], cols[2][2]]
        new = {'Trf.m_3x3': nm, 'FamilyInstance.m_RefDir': _rz(R)}
        ed.modify(EL, sorted([(f['Trf.m_3x3'][2], 72, struct.pack('<9d', *nm)), (f['FamilyInstance.m_RefDir'][2], 24, struct.pack('<3d', *new['FamilyInstance.m_RefDir']))], key=lambda e: -e[0]))
    return pn, ed, new


@pytest.mark.parametrize('kind', ['move', 'rotate'])
def test_instance_move_rotate_accepted_and_reads_back(tmp_path, kind):
    import savegate as sg, wledit
    pn, ed, new = _edit(kind); o = str(tmp_path / 'o.rvt'); ed.save(o); nb = open(o, 'rb').read()
    cur = str(tmp_path / 'c.rvt'); shutil.copy(SRC, cur)
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False, backup_keep=2))
    sg.save(doc, nb, {'modified': ['stream:' + pn, 'el:%d' % EL], 'derived_ok': True})
    assert open(cur, 'rb').read() == nb
    a = wledit.Editor(cur); pn2, b, f = _fields(a)
    for name, vals in new.items():
        n = len(vals); assert list(struct.unpack('<%dd' % n, b[f[name][2]:f[name][3]])) == pytest.approx(vals)
