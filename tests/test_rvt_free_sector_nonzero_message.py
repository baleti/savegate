"""c7x-rvtread2 666: a payload with a NONZERO free sector appended is refused with the real reason (slack / free sector), not the masked 'could not be read back ... UnboundLocalError: struct' (validate() had a later local 'import struct' that made the except clause crash). 2024/2026 Autodesk sample families."""
import os, sys, shutil, pytest
import savegate as sg
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
R = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-%s.rfa')
@pytest.mark.parametrize('year', ['2024', '2026'])
def test_msg(tmp_path, year):
    import wledit
    if not os.path.exists(R % year): pytest.skip('no sample')
    t = str(tmp_path / 'a.rfa'); shutil.copy(R % year, t); raw = open(t, 'rb').read()
    ed = wledit.Editor(t); pn = ed.trace(7)[0]; ed.set_strings([(7, 'FillPattern.m_name', 'Free sector junk')]); o = str(tmp_path / 'o'); ed.save(o)
    bad = open(o, 'rb').read() + b'\xA5' * 4096
    with pytest.raises(sg.SaveError) as ei: sg.save(sg.open_doc(t, None, sg.Config(allow_overwrite=True, require_gate=False)), bad, {'modified': ['stream:' + pn, 'el:7']})
    msg = str(ei.value); assert 'UnboundLocalError' not in msg, msg[:200]
    assert open(t, 'rb').read() == raw
