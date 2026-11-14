"""c5x-rvtread2 item 302: after a gated string edit on the public 2024 family the edited partition differs from the source only inside one window:
bytes before the record are identical, and everything after the record (allowing the 1 length u32 that follows the traced span) is identical shifted by the size delta.
Also: the original of an edit-then-revert save has IDENTICAL decompressed partitions (re-gzip may differ). Public sample only."""
import os, sys, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no public sample')


def _target(ed):
    for e in sorted(ed.m.ids):
        try: t = ed.trace(e)
        except Exception: continue
        if t[3] and any(x[1] == 'ForgeTypeId.m_typeId' and x[3] - x[2] >= 6 for x in t[3]): return e
    return None


def _edit(tmp_path, src, el, txt, keep=None):
    import savegate as sg, wledit
    ed = wledit.Editor(src); ed.set_strings([(el, 'ForgeTypeId.m_typeId', txt)]); o = str(tmp_path / 'o.rfa'); ed.save(o); new = open(o, 'rb').read(); del ed
    cur = str(tmp_path / 'c.rfa'); shutil.copy(src, cur)
    if keep is not None: keep.append(cur)
    sg.save(sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False)), new, {'modified': ['el:%d' % el]})
    return cur


def test_edit_changes_only_one_window(tmp_path):
    import wledit
    A = wledit.Editor(SRC); el = _target(A)
    if el is None: pytest.skip('no target')
    pn, i, r, log, q = A.trace(el)
    cur = _edit(tmp_path, SRC, el, 'Window302 longer text')
    B = wledit.Editor(cur)
    diff = [p for p in A.m.parts if A.m.parts[p]['joined'] != B.m.parts[p]['joined']]
    assert diff == [pn]
    a = A.m.parts[pn]['joined']; b = B.m.parts[pn]['joined']; d = len(b) - len(a)
    assert d != 0 and b[:i] == a[:i]
    assert b[q + d + 4:] == a[q + 4:]   # the u32 right after the span is the record length field, which changes with d


def test_edit_then_revert_restores_decompressed_partitions(tmp_path):
    import wledit
    A = wledit.Editor(SRC); el = _target(A)
    if el is None: pytest.skip('no target')
    old = [x[4] for x in A.trace(el)[3] if x[1] == 'ForgeTypeId.m_typeId' and x[3] - x[2] >= 6][0]
    cur = _edit(tmp_path, SRC, el, 'Revert302')
    import savegate as sg
    ed = wledit.Editor(cur); ed.set_strings([(el, 'ForgeTypeId.m_typeId', old)]); o = str(tmp_path / 'o2.rfa'); ed.save(o); new = open(o, 'rb').read(); del ed
    sg.save(sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False)), new, {'modified': ['el:%d' % el]})
    B = wledit.Editor(cur)
    assert all(A.m.parts[p]['joined'] == B.m.parts[p]['joined'] for p in A.m.parts)


def test_noedit_resave_of_edited_output_is_idempotent_or_refused(tmp_path):
    """c5x-rvtread2 item 303: re-saving the already edited file with NO edit must either be refused with the file untouched, or leave the decompressed partitions identical."""
    import wledit, savegate as sg
    A = wledit.Editor(SRC); el = _target(A)
    if el is None: pytest.skip('no target')
    cur = _edit(tmp_path, SRC, el, 'Idem303 text')
    before = open(cur, 'rb').read()
    ed = wledit.Editor(cur); o = str(tmp_path / 'o3.rfa'); ed.save(o); new = open(o, 'rb').read(); del ed
    try:
        sg.save(sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False)), new, {'modified': []})
    except Exception:
        assert open(cur, 'rb').read() == before
        return
    B = wledit.Editor(cur); C = wledit.Editor(str(tmp_path / 'o3.rfa'))
    assert all(B.m.parts[p]['joined'] == C.m.parts[p]['joined'] for p in C.m.parts)


@pytest.mark.parametrize('txt', ['G' * 5000, 'x', 'Uni\U0001F600é中'], ids=['grow5000', 'shrink1', 'nonbmp'])
def test_window_for_size_and_charset_variants(tmp_path, txt):
    """c5x-rvtread2 items 294-296: same single-window check for grow, shrink to 1 char and non-BMP text; only the edited partition differs, and the text reads back."""
    import wledit
    A = wledit.Editor(SRC); el = _target(A)
    if el is None: pytest.skip('no target')
    pn, i, r, log, q = A.trace(el)
    if len(txt) >= 5000:   # the gate refuses growth that changes later gzip members: refusal with the file byte-identical is the expected safe outcome
        import savegate.errors as se
        before = open(SRC, 'rb').read(); keep = []
        with pytest.raises(se.VerifyFailed): _edit(tmp_path, SRC, el, txt, keep)
        assert open(keep[0], 'rb').read() == before   # the working copy the gate saw is untouched
        return
    cur = _edit(tmp_path, SRC, el, txt)
    B = wledit.Editor(cur)
    assert [p for p in A.m.parts if A.m.parts[p]['joined'] != B.m.parts[p]['joined']] == [pn]
    a = A.m.parts[pn]['joined']; b = B.m.parts[pn]['joined']; d = len(b) - len(a)
    assert d != 0 and b[:i] == a[:i] and b[q + d + 4:] == a[q + 4:]
    assert [x[4] for x in B.trace(el)[3] if x[1] == 'ForgeTypeId.m_typeId'][0].startswith(txt[:60])
