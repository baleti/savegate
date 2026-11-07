"""c5x-rvtgap RVT-EDIT rung 1: MOVE a Level (Autodesk Snowdon Towers Structural 2024, level 32567 at 8.0833 ft): both Plane.m_origin z values +1 ft. Dependents (family instances)
change in their derived parameters only; their stored records are byte-identical. Default stays strict (refused); with manifest['derived_ok'] the gate accepts it, still
refusing any stray flip elsewhere. Local readback only; the Revit-VM verdict is a separate step."""
import os, sys, struct, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt'); EL = 32567
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no Autodesk sample')


def _moved(tmp_path, dz=1.0):
    import wledit
    ed = wledit.Editor(SRC); t = ed.trace(EL); pn = t[0]
    pl = sorted([x for x in t[3] if x[1] == 'Plane.m_origin'], key=lambda x: -x[2])
    ed.modify(EL, [(x[2] + 16, 8, struct.pack('<d', eval(x[4])[2] + dz)) for x in pl])
    o = str(tmp_path / 'o.rvt'); ed.save(o); return pn, open(o, 'rb').read(), [eval(x[4])[2] + dz for x in pl]


def _try(tmp_path, new, man):
    import savegate as sg
    cur = str(tmp_path / 'c.rvt'); shutil.copy(SRC, cur); before = open(cur, 'rb').read()
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False, backup_keep=2))
    try: sg.save(doc, new, man); ok = True
    except sg.SaveError: ok = False
    return ok, cur, before


def test_level_move_is_strict_by_default(tmp_path):
    pn, new, _ = _moved(tmp_path)
    ok, cur, before = _try(tmp_path, new, {'modified': ['stream:' + pn, 'el:%d' % EL]})
    assert not ok and open(cur, 'rb').read() == before


def test_level_move_with_derived_ok_is_accepted_and_reads_back(tmp_path):
    import wledit
    pn, new, zs = _moved(tmp_path)
    ok, cur, before = _try(tmp_path, new, {'modified': ['stream:' + pn, 'el:%d' % EL], 'derived_ok': True})
    assert ok and open(cur, 'rb').read() == new
    t = wledit.Editor(cur).trace(EL)
    assert [eval(x[4])[2] for x in t[3] if x[1] == 'Plane.m_origin'] == pytest.approx(zs)


def test_derived_ok_still_refuses_a_stray_flip_elsewhere(tmp_path):
    import cfb, rvtw, wlpart
    pn, new, _ = _moved(tmp_path)
    c = cfb.CFB(new); st = rvtw.Stream(c.streams()[pn].data); pt = wlpart.Partition(st)
    m = pt.mem[-1]; m['raw'][len(m['raw']) // 2] ^= 1; m['dirty'] = True
    c.streams()[pn].data = st.build(pt.rebuild(), keep_spare=False); o = str(tmp_path / 'bad.rvt'); cfb.write(c, o)
    ok, cur, before = _try(tmp_path, open(o, 'rb').read(), {'modified': ['stream:' + pn, 'el:%d' % EL], 'derived_ok': True})
    assert not ok and open(cur, 'rb').read() == before
