"""c2x-rvtgap item 20: unusual strings written into a UTF-16 name field: either refused cleanly or round-trip exactly, always a valid container."""
import os, sys, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no public sample')
CASES = {'polish': 'Zażółć gęślą jaźń', 'cjk': '漢字かな', 'emoji_pair': 'a\U0001F600b', 'lone_surrogate': 'a\ud800b', 'nul': 'a\x00b', 'empty': '', 'bom': '﻿x', 'rtl': 'ab‮ba', 'crlf': 'a\r\nb', 'maxish': 'é' * 255}


@pytest.mark.parametrize('name', list(CASES))
def test_unicode_name_roundtrip_or_clean_refusal(name, tmp_path):
    import wledit, cfb
    from savegate.adapters import RvtAdapter
    val = CASES[name]
    ed = wledit.Editor(SRC)
    try: ed.set_strings([(7, 'FillPattern.m_name', val)])
    except (ValueError, UnicodeError): return                 # clean refusal
    o = str(tmp_path / 'o.rfa'); ed.save(o); b = open(o, 'rb').read(); a = RvtAdapter()
    assert not a.source_damage(b); a.validate(b)
    got = wledit.Editor(o).trace(7)[2]['fields']['m_pFillPattern']['obj']['m_name']
    assert got == val, (name, got)
