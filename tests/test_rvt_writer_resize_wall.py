"""c5x-rvtgap RVT-EDIT rung 1 RESIZE: wall 585072 of the Autodesk Snowdon Towers Structural 2024 project, height 76.75 -> 60.0 ft and length +2 ft, through the writer op resize_wall (height parameter
-1001105, face envelopes, header bounding box; end parameter, envelopes u1, bounding box along the wall). The gate recomputes the writer result (byte equality); a flipped bit is refused.
Joins, hosted openings and other dependents of the wall are NOT handled (Revit-VM question)."""
import os, sys, struct, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt'); EL = 585072
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no Autodesk sample')
H = [{'op': 'resize_wall', 'id': EL, 'height': 60.0}]; LN = [{'op': 'resize_wall', 'id': EL, 'length_delta': 2.0}]


def _read(path):
    import wledit, rvtgen
    a = wledit.Editor(path); t = a.trace(EL); b = a.m.parts[t[0]]['joined']
    env = [struct.unpack('<4d', b[x[2]:x[3]]) for x in t[3] if x[1] == 'Envelope.m_corners']; ep = [struct.unpack('<2d', b[x[2]:x[3]]) for x in t[3] if x[1] == 'GCurve.m_endParams'][0]
    g = rvtgen.Gen(path); T = g.template(EL); hl = {n: (o, e) for n, o, e, _ in T['hlog']}
    last = None; hp = None
    for x in t[3]:
        if x[1] == 'ParamValueDouble.m_paramId': last = struct.unpack('<q', b[x[2]:x[3]])[0]
        elif x[1] == 'ParamValueDouble.m_value' and last == -1001105: hp = struct.unpack('<d', b[x[2]:x[3]])[0]
    return dict(env=env, ep=ep, hp=hp, mm=struct.unpack_from('<6d', T['hdr'], hl['Outline.m_minmax'][0]))


def _go(tmp_path, ops):
    import savegate as sg
    from savegate import rvt_writer_ops as WO
    o = str(tmp_path / 'o.rvt'); WO.run(SRC, ops, o); nb = open(o, 'rb').read()
    cur = str(tmp_path / 'c.rvt'); shutil.copy(SRC, cur)
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False, backup_keep=2))
    sg.save(doc, nb, {'writer_ops': ops}); assert open(cur, 'rb').read() == nb
    return _read(SRC), _read(cur), nb


def test_height_change(tmp_path):
    old, new, _ = _go(tmp_path, H)
    assert new['hp'] == pytest.approx(60.0) and old['hp'] == pytest.approx(76.75)
    assert all(e[3] == pytest.approx(60.0) and e[2] == pytest.approx(old['env'][0][2]) for e in new['env'])
    assert new['mm'][5] == pytest.approx(old['mm'][2] + 60.0) and new['mm'][:5] == pytest.approx(old['mm'][:5])


def test_length_change(tmp_path):
    old, new, _ = _go(tmp_path, LN)
    assert new['ep'][1] == pytest.approx(old['ep'][1] + 2.0) and new['hp'] == pytest.approx(old['hp'])
    assert all(e[2] == pytest.approx(o[2] + 2.0) for e, o in zip(new['env'], old['env']))
    assert new['mm'][3] == pytest.approx(old['mm'][3] + 2.0)          # wall runs along +x


def test_flipped_bit_is_refused(tmp_path):
    import savegate as sg
    from savegate import rvt_writer_ops as WO
    o = str(tmp_path / 'o.rvt'); WO.run(SRC, H, o); b = bytearray(open(o, 'rb').read()); b[len(b) // 2] ^= 1
    cur = str(tmp_path / 'c.rvt'); shutil.copy(SRC, cur); before = open(cur, 'rb').read()
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False, backup_keep=2))
    with pytest.raises(sg.SaveError): sg.save(doc, bytes(b), {'writer_ops': H})
    assert open(cur, 'rb').read() == before
