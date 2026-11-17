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


@pytest.mark.parametrize('val,ok', [(1.5, True), (1e30, False), (-1e12, False)])
def test_any_double_sane_to_absurd_refused(tmp_path, val, ok):
    import wledit
    E = wledit.Editor(SRC); o = [l[2] for l in E.trace(355)[3] if l[1] == 'Level.m_roomComputationElevationOffset'][0]
    E.modify(355, [(o, 8, struct.pack('<d', val))]); out = str(tmp_path / 'o.rvt'); E.save(out); new = open(out, 'rb').read()
    p = tmp_path / 'a.rvt'; shutil.copy(SRC, p); orig = p.read_bytes()
    doc = sg.open_doc(str(p), None, sg.Config(allow_overwrite=True, require_gate=False)); man = {'modified': ['el:355'], 'derived_ok': True}
    if ok: sg.save(doc, new, man); assert p.read_bytes() != orig
    else:
        with pytest.raises(sg.SaveError) as ei: sg.save(doc, new, man)
        assert 'value_out_of_range' in str(ei.value) and p.read_bytes() == orig


@pytest.mark.parametrize('v,ok', [(0x7fffffff, False), (19, False), (17, False)])
def test_rich_text_length_matches_text(tmp_path, v, ok):
    import wledit
    E = wledit.Editor(SRC); o = [l[2] for l in E.trace(303726)[3] if l[1] == 'RichTextFragment.m_nLengthInRichEditCtrl'][0]
    E.modify(303726, [(o, 4, struct.pack('<I', v))]); out = str(tmp_path / 'o.rvt'); E.save(out); new = open(out, 'rb').read()
    p = tmp_path / 'a.rvt'; shutil.copy(SRC, p); orig = p.read_bytes()
    doc = sg.open_doc(str(p), None, sg.Config(allow_overwrite=True, require_gate=False)); man = {'modified': ['el:303726']}
    if ok: sg.save(doc, new, man)
    else:
        with pytest.raises(sg.SaveError) as ei: sg.save(doc, new, man)
        assert 'rich_text_length' in str(ei.value) and p.read_bytes() == orig


@pytest.mark.parametrize('fld,v,ok', [('TextElement.m_leaderLeftAttachment', 0x7fffffff, False), ('TextElement.m_leaderRightAttachment', 65536, False), ('LineAndTextAttr.m_background', 0x7fffffff, False), ('TextElement.m_leaderLeftAttachment', 1, True)])
def test_enum_fields_bounded(tmp_path, fld, v, ok):
    import wledit
    E = wledit.Editor(SRC); o = [l[2] for l in E.trace(303726)[3] if l[1] == fld][0]
    E.modify(303726, [(o, 4, struct.pack('<I', v))]); out = str(tmp_path / 'o.rvt'); E.save(out); new = open(out, 'rb').read()
    p = tmp_path / 'a.rvt'; shutil.copy(SRC, p); orig = p.read_bytes()
    doc = sg.open_doc(str(p), None, sg.Config(allow_overwrite=True, require_gate=False)); man = {'modified': ['el:303726']}
    if ok: sg.save(doc, new, man); assert p.read_bytes() != orig
    else:
        with pytest.raises(sg.SaveError) as ei: sg.save(doc, new, man)
        assert 'enum_out_of_range' in str(ei.value) and p.read_bytes() == orig


@pytest.mark.parametrize('eid,fld,nth,derived,ok', [(303689, 'GeomTabEntry.m_geomGeneratorId', 0, False, False), (303689, 'EdgeHistEntry.m_id', 0, False, False), (303689, 'GeomStep.m_pElem', 0, False, False), (303689, 'VWall.m_locLineOffset', 0, False, True)])
def test_geometry_untouched_without_derived_ok(tmp_path, eid, fld, nth, derived, ok):
    import wledit
    E = wledit.Editor(SRC); ent = [l for l in E.trace(eid)[3] if l[1] == fld][nth]
    E.modify(eid, [(ent[2], ent[3] - ent[2], struct.pack('<I', 0x7fffffff) if ent[3] - ent[2] == 4 else struct.pack('<d', 0.5))]); out = str(tmp_path / 'o.rvt'); E.save(out); new = open(out, 'rb').read()
    p = tmp_path / 'a.rvt'; shutil.copy(SRC, p); orig = p.read_bytes()
    doc = sg.open_doc(str(p), None, sg.Config(allow_overwrite=True, require_gate=False)); man = {'modified': ['el:%d' % eid]}
    if ok: sg.save(doc, new, man); assert p.read_bytes() != orig
    else:
        with pytest.raises(sg.SaveError) as ei: sg.save(doc, new, man)
        assert 'geometry_changed' in str(ei.value) and p.read_bytes() == orig


def test_geometry_untouched_also_with_derived_ok(tmp_path):
    import wledit
    E = wledit.Editor(SRC); ent = [l for l in E.trace(303689)[3] if l[1] == 'GeomTabEntry.m_geomGeneratorId'][0]
    E.modify(303689, [(ent[2], 4, struct.pack('<I', 0x7fffffff))]); out = str(tmp_path / 'o.rvt'); E.save(out); new = open(out, 'rb').read()
    p = tmp_path / 'a.rvt'; shutil.copy(SRC, p); orig = p.read_bytes()
    doc = sg.open_doc(str(p), None, sg.Config(allow_overwrite=True, require_gate=False))
    with pytest.raises(sg.SaveError) as ei: sg.save(doc, new, {'modified': ['el:303689'], 'derived_ok': True})
    assert 'geometry_changed' in str(ei.value) and p.read_bytes() == orig


def test_family_sketch_curve_info_change_refused(tmp_path):
    """c4x-rvtgap 581: VarSketch.m_absorbedCurves[].m_GInfo.m_controlCommand = 0x7fffffff on the 2026 sample family was ACCEPTED; sketch curves count as geometry now."""
    import wledit
    FAM = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2026.rfa')
    if not os.path.exists(FAM): pytest.skip('no sample family')
    E = wledit.Editor(FAM); ent = [l for l in E.trace(613)[3] if l[1] == 'GInfo.m_controlCommand'][0]
    E.modify(613, [(ent[2], 4, struct.pack('<I', 0x7fffffff))]); out = str(tmp_path / 'o.rfa'); E.save(out); new = open(out, 'rb').read()
    p = tmp_path / 'a.rfa'; shutil.copy(FAM, p); orig = p.read_bytes()
    doc = sg.open_doc(str(p), None, sg.Config(allow_overwrite=True, require_gate=False))
    with pytest.raises(sg.SaveError) as ei: sg.save(doc, new, {'modified': ['el:613']})
    assert 'geometry_changed' in str(ei.value) and p.read_bytes() == orig


@pytest.mark.parametrize('eid,fld', [(80, 'ControlledDocAccess.m_pDoc'), (80, 'Element.m_docAccess')])
def test_small_int_to_huge_refused_in_family(tmp_path, eid, fld):
    """c4x-rvtgap 582: enums/masks/handles/indices jumping from a small value to 0x7fffffff were accepted (28 of 90 sampled family writes)."""
    import wledit, glob
    FAM = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2026.rfa')
    if not os.path.exists(FAM): pytest.skip('no sample family')
    E = wledit.Editor(FAM); ents = [l for l in E.trace(eid)[3] if l[1] == fld]
    if not ents: pytest.skip('field not in record')
    E.modify(eid, [(ents[0][2], 4, struct.pack('<I', 0x7fffffff))]); out = str(tmp_path / 'o.rfa'); E.save(out); new = open(out, 'rb').read()
    p = tmp_path / 'a.rfa'; shutil.copy(FAM, p); orig = p.read_bytes()
    doc = sg.open_doc(str(p), None, sg.Config(allow_overwrite=True, require_gate=False))
    with pytest.raises(sg.SaveError) as ei: sg.save(doc, new, {'modified': ['el:%d' % eid]})
    assert 'int_out_of_range' in str(ei.value) and p.read_bytes() == orig
