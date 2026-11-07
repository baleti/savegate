"""c5x-rvtread2 item 106: wledit._check_wstr compared the stored text with the trace-log value, which is truncated to 60 chars, so a string longer than 60 chars could never be edited again
(a grown name, repeated edits). The prefix clause was inside a comment and never ran. Public 2024 family; fails on the old wledit, passes with the clause live."""
import os, sys, struct, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no public sample')


def _raw(path, eid, field):
    import wledit
    e = wledit.Editor(path); t = e.trace(eid); l = [l for l in t[3] if l[1] == field][0]; b = e.m.parts[t[0]]['joined']; n = struct.unpack_from('<I', b, l[2])[0]
    return bytes(b[l[2] + 4:l[2] + 4 + 2 * n]).decode('utf-16le')


def test_long_string_can_be_edited_again(tmp_path):
    import wledit
    a = str(tmp_path / 'a.rfa'); b = str(tmp_path / 'b.rfa')
    ed = wledit.Editor(SRC); ed.set_strings([(7, 'FillPattern.m_name', 'Q' * 200)]); ed.save(a)
    assert _raw(a, 7, 'FillPattern.m_name') == 'Q' * 200
    ed = wledit.Editor(a); ed.set_strings([(7, 'FillPattern.m_name', 'R' * 70)]); ed.save(b)       # was: ValueError 'not a length-prefixed wide string'
    assert _raw(b, 7, 'FillPattern.m_name') == 'R' * 70


def test_non_string_field_still_refused():
    import wledit
    ed = wledit.Editor(SRC)
    with pytest.raises(ValueError):
        ed.set_strings([(7, 'Identifier.m_id64', 'x' * 60)])
