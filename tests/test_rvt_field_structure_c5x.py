"""c5x-rvtread2 item 173: a raw write into a string-length / container-count prefix of a DECLARED element changes the element's field structure but is accepted by the gate. Documented as xfail until the gate re-traces declared elements (NEEDS-FROM-SAVEGATE 2026-11-13)."""
import os, sys, shutil, random, pytest
import savegate as sg
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(F), reason='no sample')


def test_length_prefix_garbage_in_declared_element_is_refused(tmp_path):
    import wledit
    f = str(tmp_path / 'a.rfa'); shutil.copy(F, f); src = open(f, 'rb').read()
    t = wledit.Editor(F).trace(35)
    off = 485412                       # inside GRenderSettings.m_oExposureAssets (a count prefix region)
    ed = wledit.Editor(f); random.seed(1); ed.modify(35, [(off, 4, bytes([0x07, 0x00, 0x00, 0x00]))])
    o = str(tmp_path / 'o.tmp'); ed.save(o); new = open(o, 'rb').read(); os.remove(o)
    names = lambda tr: [x[1] for x in tr[3]]
    doc = sg.open_doc(f, None, sg.Config(allow_overwrite=True, require_gate=False))
    try: sg.save(doc, new, {'modified': ['el:35']}); accepted = True
    except sg.SaveError: accepted = False
    if accepted:
        again = wledit.Editor(f).trace(35)
        assert names(again) == names(t), 'gate accepted an output whose element has a different field structure'
    else:
        assert open(f, 'rb').read() == src
