"""c2x-rvtgap 140: guard the size edge of a string edit through the gate (Autodesk 2026 rfa): 8193 chars accepted, 8400 refused with span_changed + growth_too_large, original intact. A change of the caps shows up here."""
import os, sys, shutil, pytest
import savegate as sg
from savegate.errors import VerifyFailed
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2026.rfa')
@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
@pytest.mark.parametrize('n,ok', [(8193, True), (8400, False)])
def test_edge(tmp_path, n, ok):
    sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
    import wledit
    t = str(tmp_path / 'x.rfa'); shutil.copy(F, t); orig = open(t, 'rb').read()
    ed = wledit.Editor(t); ed.set_strings([(7, 'FillPattern.m_name', 'G' * n)]); o = str(tmp_path / 'o.tmp'); ed.save(o)
    new = open(o, 'rb').read(); os.remove(o)
    doc = sg.open_doc(t, None, sg.Config(allow_overwrite=True, require_gate=False))
    man = {'modified': ['stream:Partitions/69', 'el:7']}
    if ok:
        assert sg.save(doc, new, man).ok and open(t, 'rb').read() == new
    else:
        with pytest.raises(VerifyFailed) as ei: sg.save(doc, new, man)
        codes = {u[0] for u in ei.value.report['unexpected']}
        assert {'span_changed', 'growth_too_large'} <= codes and open(t, 'rb').read() == orig
