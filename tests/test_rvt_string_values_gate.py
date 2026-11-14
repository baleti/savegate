"""c5x-rvtgap 136: unusual replacement strings through Editor + gate: any ACCEPTED output must read back the exact string; a refusal leaves the original intact; no raw exceptions."""
import os, sys, shutil, pytest
import savegate as sg
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
VALS = {'longer': 'Horizontal' * 3, 'shorter': 'H', 'empty': '', 'nul': 'a\x00b', 'newline': 'a\nb', 'nonbmp': 'x\U0001F600y', 'big10k': 'Z' * 10000,
        'cjk': '日本語', 'lonely_surrogate': 'a\ud800b', 'bom': '﻿name', 'ctrl': '\x01\x1f'}
@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
@pytest.mark.parametrize('k', list(VALS))
def test_val(tmp_path, k):
    sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
    import wledit
    t = tmp_path / 'x.rfa'; shutil.copy(F, t); orig = t.read_bytes()
    try:
        ed = wledit.Editor(str(t)); ed.set_strings([(7, 'FillPattern.m_name', VALS[k])]); o = str(tmp_path / 'o.bin'); ed.save(o)
    except (ValueError, UnicodeError) as e:
        print(k, 'editor refused', type(e).__name__); return
    new = open(o, 'rb').read()
    doc = sg.open_doc(str(t), None, sg.Config(allow_overwrite=True, require_gate=False, journal_dir=str(tmp_path / 'j')))
    try: ok = sg.save(doc, new, {'modified': ['el:7']}).ok; err = None
    except sg.SaveError as e: ok = False; err = e
    except Exception as e: ok = False; err = 'RAW %r' % e
    print(k, 'accepted' if ok else 'refused', str(err)[:90])
    assert not isinstance(err, str), err
    if not ok: assert t.read_bytes() == orig; return
    assert t.read_bytes() == new
    got = wledit.Editor(str(t)).trace(7)[2]['fields']['m_pFillPattern']['obj']['m_name']
    assert got == VALS[k], 'accepted but reads back %r' % (got,)
