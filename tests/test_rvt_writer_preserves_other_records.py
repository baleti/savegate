"""c2x-rvtgap item 5/18: a string edit of one element must leave EVERY other byte of the edited partition (including records of classes the reader
does not know) identical: out == src with the one record replaced, plus the next record's length link (A, 4 bytes) re-stamped. All other partitions and
all other CFB streams must be byte-identical."""
import os, sys, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
D = os.path.expanduser('~/rvt-research/samples-rfa/')
FILES = [D + 'racbasicsamplefamily-2024.rfa', D + 'racbasicsamplefamily-2026.rfa']


@pytest.mark.parametrize('src', FILES)
def test_edit_changes_only_declared_record(tmp_path, src):
    if not os.path.exists(src): pytest.skip('no public sample')
    import wledit, wlrec, cfb
    ed = wledit.Editor(src); pn, i, r, log, q = ed.trace(7)
    ed.set_strings([(7, 'FillPattern.m_name', 'Edited by test')])
    o = str(tmp_path / 'o.rfa'); ed.save(o)
    A = wlrec.Model(src); B = wlrec.Model(o)
    a = bytes(A.parts[pn]['joined']); b = bytes(B.parts[pn]['joined'])
    assert a != b
    # the bytes before the record and after the next-record link are untouched
    assert a[:i] == b[:i] or a[:i - 0] == b[:i], 'prefix changed'
    tail_a = a[q + 4:]; tail_b = b[len(b) - len(tail_a):]
    assert tail_a == tail_b, 'records after the edited one changed (unknown classes dropped or reinterpreted?)'
    SA = cfb.CFB(open(src, 'rb').read()).streams(); SB = cfb.CFB(open(o, 'rb').read()).streams()
    assert set(SA) == set(SB)
    diff = [k for k in SA if SA[k].data != SB[k].data]
    assert diff == [pn], diff
