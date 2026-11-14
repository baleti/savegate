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


def _edit(tmp_path, src, el, txt):
    import savegate as sg, wledit
    ed = wledit.Editor(src); ed.set_strings([(el, 'ForgeTypeId.m_typeId', txt)]); o = str(tmp_path / 'o.rfa'); ed.save(o); new = open(o, 'rb').read(); del ed
    cur = str(tmp_path / 'c.rfa'); shutil.copy(src, cur)
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
