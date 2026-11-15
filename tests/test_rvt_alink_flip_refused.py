"""c4x-rvtgap 445: a flipped A link (first u32) of the declared record, or of the element after the el:0 record, must be refused (Autodesk 2024 racbasic family)."""
import os, sys, shutil, struct, pytest
for p in ('~/rvt-research', '~/rvt-research/write-lab'): sys.path.insert(0, os.path.expanduser(p))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no public sample')

@pytest.mark.parametrize('el,off', [(1, 0), (1, 4), (3, 0)])
def test_header_flip_refused(tmp_path, el, off):
    import wledit, savegate as sg
    ed = wledit.Editor(SRC); pn, i, r, log, q = ed.trace(el); b = ed.m.parts[pn]['joined']; n = 4 if off == 0 else ed.m.IDW
    ed.modify(el, [(i + off, n, bytes(x ^ 1 for x in b[i + off:i + off + n]))]); o = str(tmp_path / 'o.rfa'); ed.save(o); new = open(o, 'rb').read(); del ed
    cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur); orig = open(cur, 'rb').read()
    with pytest.raises(sg.VerifyFailed):
        sg.save(sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False)), new, {'modified': ['el:%d' % el]})
    assert open(cur, 'rb').read() == orig


def test_next_record_alink_flip_after_same_length_edit_refused(tmp_path):
    """c4x-rvtgap 447: el:0 edited same-length, the A link of the NEXT record (el:1) flipped: refused."""
    import wledit, savegate as sg
    A = wledit.Editor(SRC); W = A.m.IDW; pn, i, r, log, q = A.trace(0)
    f = [x for x in log if isinstance(x[4], str) and len(x[4]) >= 3 and x[3] - x[2] == 4 + 2 * len(x[4]) and '\x00' not in x[4]][0]
    ed = wledit.Editor(SRC); new = f[4][:-1] + ('Y' if f[4][-1] != 'Y' else 'Z'); ed.set_strings([(0, f[1], new, f[4])]); pt = ed.part(pn)
    ob = bytes(ed.m.parts[pn]['joined'][q:q + 4]); pt.replace(q, 4, bytes(x ^ 1 for x in ob)); o = str(tmp_path / 'o.rfa'); ed.save(o); nb = open(o, 'rb').read(); del ed
    cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur); orig = open(cur, 'rb').read()
    with pytest.raises(sg.VerifyFailed):
        sg.save(sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False)), nb, {'modified': ['el:0']})
    assert open(cur, 'rb').read() == orig


def test_grown_edit_with_wrong_next_alink_refused(tmp_path):
    """c4x-rvtgap 449: el:0 grown by 2 chars, the next record's A link then corrupted (not the refreshed value): refused."""
    import wledit, savegate as sg
    A = wledit.Editor(SRC); W = A.m.IDW; pn, i, r, log, q = A.trace(0)
    f = [x for x in log if isinstance(x[4], str) and len(x[4]) >= 3 and x[3] - x[2] == 4 + 2 * len(x[4]) and '\x00' not in x[4]][0]
    ed = wledit.Editor(SRC); ed.set_strings([(0, f[1], f[4] + 'GG', f[4])]); pt = ed.part(pn)
    pt.replace(q + 4, 4, b'\x01\x02\x03\x04'); o = str(tmp_path / 'o.rfa'); ed.save(o); nb = open(o, 'rb').read(); del ed
    cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur); orig = open(cur, 'rb').read()
    with pytest.raises(sg.VerifyFailed):
        sg.save(sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False)), nb, {'modified': ['el:0']})
    assert open(cur, 'rb').read() == orig
