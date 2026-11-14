"""c5x-rvtgap 203: the u16 class tag at record offset 20 (the only bytes the reader does not decode) overwritten with another valid tag of the file, on a declared el:7 edit
(Autodesk 2024 and 2026 rfa). The gate must refuse (field_structure_changed or id check), leave the original byte-identical, and raise nothing raw."""
import os, sys, shutil, struct, pytest
import savegate as sg
sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]


@pytest.mark.parametrize('year', ['2024', '2026'])
def test_class_tag_swap_refused(tmp_path, year):
    import wledit
    F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-%s.rfa' % year)
    if not os.path.exists(F): pytest.skip('no public sample')
    ed0 = wledit.Editor(F); tags = {}
    for e in sorted(ed0.m.ids):
        r = ed0.trace(e)[2]; tags.setdefault(r['tag'], r['class'])
    pn, i, r, log, q = ed0.trace(7); own = r['tag']
    tried = 0
    for tag in list(tags)[:8]:
        if tag == own: continue
        d = tmp_path / ('t%d' % tag); d.mkdir(); t = str(d / 'c.rfa'); shutil.copy(F, t); orig = open(t, 'rb').read()
        ed = wledit.Editor(t); ed.modify(7, [(i + 20, 2, struct.pack('<H', tag))]); o = str(d / 'o.bin'); ed.save(o); new = open(o, 'rb').read()
        doc = sg.open_doc(t, None, sg.Config(allow_overwrite=True, require_gate=False, journal_dir=str(d / 'j')))
        with pytest.raises(sg.SaveError):
            sg.save(doc, new, {'modified': ['el:7']})
        assert open(t, 'rb').read() == orig
        tried += 1
    assert tried >= 5
