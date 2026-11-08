"""c7x-rvtread2 item 383: text note text must be RTF-escaped (braces) and control chars refused. SGPKG = tree with c7x-rvtread2-finite-and-delete-once.diff."""
import os, sys, pytest
sys.path.insert(0, os.environ.get('SGPKG', os.path.expanduser('~/src/savegate')))
from savegate import rvt_writer_ops as WO

def test_braces_backslash_escaped():
    assert WO._rtf_escape('a{b}c\\d') == b'a\\{b\\}c\\\\d'

def test_non_cp1252_is_unicode_escape_not_question_mark():
    assert b'?' not in WO._rtf_escape('中').replace(b'\\u20013?', b'')

@pytest.mark.parametrize('t', ['a\x00b', 'x\ud800y', 'a\nb', 'a\rb'])
def test_bad_chars_refused(t):
    with pytest.raises(ValueError):
        WO._rtf_escape(t)
