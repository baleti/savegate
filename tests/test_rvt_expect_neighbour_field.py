"""c7x-rvtread2 672/673: a raw 16-byte modify of FillPattern.m_scale in el 4 that ALSO moves the next field (m_windowSize +1.0) is REFUSED when the manifest carries expect={4:{m_scale: new}}
(declared_element_mismatch). Without 'expect' the same payload is accepted (element-level check only): pinned as a documented limitation so a change of behaviour is noticed. 2024/2026 Autodesk sample families."""
import os, sys, shutil, struct, pytest
import savegate as sg
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
R = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-%s.rfa')
@pytest.mark.parametrize('year', ['2024', '2026'])
def test_neighbour(tmp_path, year):
    import wledit
    if not os.path.exists(R % year): pytest.skip('no sample')
    t = str(tmp_path / 'a.rfa'); shutil.copy(R % year, t); raw = open(t, 'rb').read()
    ed = wledit.Editor(t); lg = ed.trace(4); pn = lg[0]
    L = [l for l in lg[3] if l[1] == 'FillPattern.m_scale' and l[3] - l[2] == 8][0]
    b = ed.m.parts[pn]['joined']; old16 = bytes(b[L[2]:L[2] + 16]); newv = float(L[4]) + 3.0
    ed.modify(4, [(L[2], 16, struct.pack('<d', newv) + struct.pack('<d', struct.unpack('<d', old16[8:16])[0] + 1.0))]); o = str(tmp_path / 'o'); ed.save(o); new = open(o, 'rb').read()
    man = {'modified': ['stream:' + pn, 'el:4'], 'expect': {4: {'FillPattern.m_scale': newv}}}
    with pytest.raises(sg.SaveError) as ei: sg.save(sg.open_doc(t, None, sg.Config(allow_overwrite=True, require_gate=False)), new, man)
    assert 'declared_element_mismatch' in str(ei.value) and type(ei.value).__name__ not in ('GateClosed', 'LowMemory')
    assert open(t, 'rb').read() == raw
    sg.save(sg.open_doc(t, None, sg.Config(allow_overwrite=True, require_gate=False)), new, {'modified': ['stream:' + pn, 'el:4']})      # documented limitation: element-level only
    assert open(t, 'rb').read() == new
