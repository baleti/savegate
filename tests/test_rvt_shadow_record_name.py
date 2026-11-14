"""c5x-rvtgap 210: on the Autodesk 2026 rfa a symbol name 'A/B' on el:0 makes the reader's header scan find a SPURIOUS 39-field record for el:1 (CategoryElem) 2 bytes before el:0, while 'AxB' does not
(the reader locates records by scanning for header candidates, wlrec.Model.find). The gate must not accept that save: declared el:0 only, and declared el:0+el:1, must both be refused and leave the original byte-identical."""
import os, sys, shutil, pytest
import savegate as sg
sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2026.rfa')


@pytest.mark.skipif(not os.path.exists(F), reason='no public sample')
@pytest.mark.parametrize('declared', [['el:0'], ['el:0', 'el:1']])
def test_shadow_record_refused(tmp_path, declared):
    import wledit
    t = str(tmp_path / 'c.rfa'); shutil.copy(F, t); orig = open(t, 'rb').read()
    ed = wledit.Editor(t); ed.set_string(0, 'SymbolInfo.m_name', 'A/B', match='Linear'); o = str(tmp_path / 'o.bin'); ed.save(o); new = open(o, 'rb').read()
    doc = sg.open_doc(t, None, sg.Config(allow_overwrite=True, require_gate=False, journal_dir=str(tmp_path / 'j')))
    with pytest.raises(sg.SaveError):
        sg.save(doc, new, {'modified': declared})
    assert open(t, 'rb').read() == orig
