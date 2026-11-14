"""c5x-rvtgap 162: bytes of an OLDER version presented as a new save. v0 -> v1 (el:7 edit) -> v2 (el:0 edit). Presenting v0 (reverts both) declared as el:7 only must be refused; presenting v1 declared el:0 (reverts el:0 only) is a legitimate edit and is accepted."""
import os, sys, shutil, pytest
import savegate as sg
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
def test_stale(tmp_path):
    sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
    import wledit
    t = tmp_path / 'x.rfa'; shutil.copy(F, t); v0 = t.read_bytes()
    cfg = lambda: sg.Config(allow_overwrite=True, require_gate=False, backup_keep=5, journal_dir=str(tmp_path / 'j'))
    def edit(eid, field, val, man):
        ed = wledit.Editor(str(t)); ed.set_strings([(eid, field, val)]); o = str(tmp_path / 'o.bin'); ed.save(o); nb = open(o, 'rb').read(); os.remove(o)
        assert sg.save(sg.open_doc(str(t), None, cfg()), nb, man).ok; return nb
    v1 = edit(7, 'FillPattern.m_name', 'E1', {'modified': ['el:7']})
    v2 = edit(0, 'SymbolInfo.m_name', 'E2', {'modified': ['el:0']})
    assert t.read_bytes() == v2
    doc = sg.open_doc(str(t), None, cfg())
    with pytest.raises(sg.SaveError): sg.save(doc, v0, {'modified': ['el:7']})
    assert t.read_bytes() == v2
    r = sg.save(sg.open_doc(str(t), None, cfg()), v1, {'modified': ['el:0']})
    assert r.ok and t.read_bytes() == v1
