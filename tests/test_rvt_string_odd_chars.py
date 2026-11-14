"""c5x-rvtgap 168: odd string contents (empty, NUL, lone surrogate, non-BMP, RTL, long combining) written into FillPattern.m_name of the Autodesk 2024 rfa through writer + gate. Verdict per case printed; a raw exception or a damaged original fails the test; an ACCEPTED file must read the string back exactly."""
import os, sys, shutil, pytest
import savegate as sg
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
CASES = {'empty': '', 'nul': 'a\x00b', 'surrogate': 'a\ud800b', 'nonbmp': 'G\U0001F600', 'rtl': 'אבx', 'combining': 'e' + '́' * 50, 'ctrl': 'a\r\n\tb', 'bom': '﻿abc'}
@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
@pytest.mark.parametrize('k', sorted(CASES))
def test_str(tmp_path, k):
    sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
    import wledit
    s = CASES[k]
    t = str(tmp_path / 'x.rfa'); shutil.copy(F, t); orig = open(t, 'rb').read()
    try:
        ed = wledit.Editor(t); ed.set_strings([(7, 'FillPattern.m_name', s)]); o = str(tmp_path / 'o.tmp'); ed.save(o)
    except Exception as e:
        print(k, 'writer refused', repr(e)[:80]); assert open(t, 'rb').read() == orig; return
    new = open(o, 'rb').read(); os.remove(o)
    doc = sg.open_doc(t, None, sg.Config(allow_overwrite=True, require_gate=False))
    try: ok = sg.save(doc, new, {'modified': ['el:7']}).ok; err = None
    except sg.SaveError as e: ok = False; err = e
    except Exception as e: ok = False; err = 'RAW %r' % e
    print(k, 'ACCEPTED' if ok else 'refused', str(err)[:100])
    assert not isinstance(err, str), err
    if ok:
        assert open(t, 'rb').read() == new
        got = wledit.Editor(t).trace(7)[2]['fields']['m_pFillPattern']['obj']['m_name']
        print(k, 'readback', repr(got)[:60], got == s)
    else: assert open(t, 'rb').read() == orig
