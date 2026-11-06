"""c7x-rvtread2 218: U+FFFE (byte-swapped BOM) and U+FFFF in an edited RVT string must be refused by the gate like NUL/BOM/control characters."""
import os, sys, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no public sample')

@pytest.mark.parametrize('val,ok', [('ab￾c', False), ('a￿b', False), ('￾abc', False), ('Zed', True), ('Kühe', True)])
def test_noncharacters(tmp_path, val, ok):
    import savegate as sg, wledit
    ed = wledit.Editor(SRC); ed.set_strings([(7, 'FillPattern.m_name', val)]); o = str(tmp_path / 'o.rfa'); ed.save(o); new = open(o, 'rb').read()
    t = str(tmp_path / 't.rfa'); shutil.copy(SRC, t); orig = open(t, 'rb').read()
    doc = sg.open_doc(t, None, sg.Config(allow_overwrite=True, require_gate=False))
    if ok: sg.save(doc, new, {'modified': ['el:7']}); assert open(t, 'rb').read() == new
    else:
        with pytest.raises(sg.VerifyFailed): sg.save(doc, new, {'modified': ['el:7']})
        assert open(t, 'rb').read() == orig
