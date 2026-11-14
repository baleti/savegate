"""c7x-rvtread2 601: a payload changes element 7 (declared) AND element 8 (not declared). The gate must refuse and leave the original untouched; declaring both is accepted.
Autodesk sample families 2024/2026 (FillPattern names of elements 7 and 8)."""
import os, sys, shutil, pytest
import savegate as sg
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
R = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-%s.rfa')
YEARS = [y for y in ('2024', '2026') if os.path.exists(R % y)]
pytestmark = pytest.mark.skipif(not YEARS, reason='no public sample')

@pytest.mark.parametrize('year', YEARS)
def test_smuggled(tmp_path, year):
    import wledit
    src = R % year; cur = str(tmp_path / 'c.rfa'); shutil.copy(src, cur); before = open(cur, 'rb').read()
    ed = wledit.Editor(cur); pn = ed.trace(7)[0]
    ed.set_strings([(7, 'FillPattern.m_name', 'Edited seven'), (8, 'FillPattern.m_name', 'Smuggled eight')])
    o = str(tmp_path / 'o.rfa'); ed.save(o); new = open(o, 'rb').read(); os.remove(o)
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    with pytest.raises(sg.SaveError) as ei: sg.save(doc, new, {'modified': ['stream:' + pn, 'el:7']})
    assert type(ei.value).__name__ not in ('GateClosed', 'LowMemory'), type(ei.value).__name__
    print('REFUSED', type(ei.value).__name__, str(ei.value)[:200])
    assert open(cur, 'rb').read() == before
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    sg.save(doc, new, {'modified': ['stream:' + pn, 'el:7', 'el:8']})
    assert open(cur, 'rb').read() == new
