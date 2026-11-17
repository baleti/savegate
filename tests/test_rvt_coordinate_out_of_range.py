"""c4x-rvtgap 570: a TextNote origin of 1e30 ft written behind the writer was ACCEPTED (gate cutoff was 1e100); now refused (coordinate_out_of_range). A normal value is still accepted."""
import os, shutil, struct, sys, pytest
sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
import savegate as sg
SRC = os.path.expanduser('~/rvt-research/vg-scenes/2026_vg_link_target.rvt')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='lab scene missing')


def _out(val, tmp):
    import wledit
    E = wledit.Editor(SRC); log = E.trace(303726)[3]; o = [l[2] for l in log if l[1] == 'TextElement.m_orig'][0]
    E.modify(303726, [(o, 8, struct.pack('<d', val))]); out = str(tmp / 'o.rvt'); E.save(out); return open(out, 'rb').read()


@pytest.mark.parametrize('val,ok', [(12.5, True), (1e30, False), (-1e7, False)])
def test_origin_bound(tmp_path, val, ok):
    p = tmp_path / 'a.rvt'; shutil.copy(SRC, p); orig = p.read_bytes(); new = _out(val, tmp_path)
    doc = sg.open_doc(str(p), None, sg.Config(allow_overwrite=True, require_gate=False))
    if ok: sg.save(doc, new, {'modified': ['el:303726']}); assert p.read_bytes() != orig
    else:
        with pytest.raises(sg.SaveError) as ei: sg.save(doc, new, {'modified': ['el:303726']})
        assert 'coordinate_out_of_range' in str(ei.value) and p.read_bytes() == orig


@pytest.mark.parametrize('eid,fld,val,ok', [(303695, 'FamilyInstance.m_instOrigin', 1e30, False), (303689, 'GLine.m_origin', 1e30, False), (303689, 'GCurve.m_endParams', 1e30, False), (303689, 'VWall.m_locLineOffset', 1e30, False), (303689, 'GLine.m_origin', 12.5, True)])
def test_instance_and_wall_location_bound(tmp_path, eid, fld, val, ok):
    import wledit
    E = wledit.Editor(SRC); o = [l[2] for l in E.trace(eid)[3] if l[1] == fld][0]
    E.modify(eid, [(o, 8, struct.pack('<d', val))]); out = str(tmp_path / 'o.rvt'); E.save(out); new = open(out, 'rb').read()
    p = tmp_path / 'a.rvt'; shutil.copy(SRC, p); orig = p.read_bytes()
    doc = sg.open_doc(str(p), None, sg.Config(allow_overwrite=True, require_gate=False)); man = {'modified': ['el:%d' % eid]}
    if ok: sg.save(doc, new, man); assert p.read_bytes() != orig
    else:
        with pytest.raises(sg.SaveError) as ei: sg.save(doc, new, man)
        assert 'coordinate_out_of_range' in str(ei.value) and p.read_bytes() == orig
