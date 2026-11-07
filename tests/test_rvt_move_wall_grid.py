"""c5x-rvtgap RVT-EDIT rung 1 (Autodesk Snowdon Towers Structural 2024): MOVE a Grid (578141, plane origin x +1 ft) and a Wall (SWall 585072, location line + 4 face plane origins, y +1 ft).
The gate accepts both with manifest derived_ok; the readback equals the expectation; a stray flip elsewhere in the same output is still refused. Local checks only (Revit-VM step separate)."""
import os, sys, struct, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no Autodesk sample')
CASES = {'grid': (578141, ('Plane.m_origin',), (1.0, 0.0, 0.0)), 'wall': (585072, ('Plane.m_origin', 'GLine.m_origin'), (0.0, 1.0, 0.0))}


def _moved(kind):
    import wledit
    el, names, d = CASES[kind]; ed = wledit.Editor(SRC); t = ed.trace(el); pn = t[0]; b = ed.m.parts[pn]['joined']
    fl = sorted([x for x in t[3] if x[1] in names], key=lambda x: -x[2])
    old = [struct.unpack('<3d', b[x[2]:x[2] + 24]) for x in fl]; new = [tuple(a + c for a, c in zip(o, d)) for o in old]
    ed.modify(el, [(x[2], 24, struct.pack('<3d', *n)) for x, n in zip(fl, new)])
    return el, pn, ed, new


def _save(tmp_path, ed, pn, el, extra=None, mutate=None):
    import savegate as sg
    o = str(tmp_path / 'o.rvt'); ed.save(o)
    if mutate: mutate(o)
    new = open(o, 'rb').read(); cur = str(tmp_path / 'c.rvt'); shutil.copy(SRC, cur); before = open(cur, 'rb').read()
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False, backup_keep=2))
    try: sg.save(doc, new, {'modified': ['stream:' + pn, 'el:%d' % el], 'derived_ok': True}); ok = True
    except sg.SaveError: ok = False
    return ok, cur, before, new


@pytest.mark.parametrize('kind', ['grid', 'wall'])
def test_move_accepted_and_reads_back(tmp_path, kind):
    import wledit
    el, pn, ed, new = _moved(kind)
    ok, cur, before, nb = _save(tmp_path, ed, pn, el)
    assert ok and open(cur, 'rb').read() == nb
    a = wledit.Editor(cur); t = a.trace(el); b = a.m.parts[pn]['joined']; names = CASES[kind][1]
    got = [struct.unpack('<3d', b[x[2]:x[2] + 24]) for x in sorted([x for x in t[3] if x[1] in names], key=lambda x: -x[2])]
    assert [v for g in got for v in g] == pytest.approx([v for n in new for v in n])


def test_wall_move_with_a_stray_flip_is_refused(tmp_path):
    import cfb, rvtw, wlpart
    el, pn, ed, new = _moved('wall')
    def mutate(o):
        c = cfb.CFB(open(o, 'rb').read()); st = rvtw.Stream(c.streams()[pn].data); pt = wlpart.Partition(st)
        m = pt.mem[-1]; m['raw'][len(m['raw']) // 2] ^= 1; m['dirty'] = True
        c.streams()[pn].data = st.build(pt.rebuild(), keep_spare=False); cfb.write(c, o)
    ok, cur, before, nb = _save(tmp_path, ed, pn, el, mutate=mutate)
    assert not ok and open(cur, 'rb').read() == before
