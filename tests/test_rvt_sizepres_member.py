"""c4x-rvtgap 412: WL_SIZEPRES=1 re-deflates an edited partition member to its ORIGINAL compressed length: only the page(s) holding the edit differ from the source
(standard writer: every page after the edit differs because the tighter deflate shifts all later members and the footer). Gate accepts both."""
import os, sys, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))

def _pages(a, b):
    import rvtw
    S = rvtw.PAGE_STORED; return [k for k in range(max(len(a), len(b)) // S + 1) if a[k*S:(k+1)*S] != b[k*S:(k+1)*S]]

@pytest.mark.parametrize('flag', ['', '1'])
def test_sizepres_pages(tmp_path, monkeypatch, flag):
    SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
    if not os.path.exists(SRC): pytest.skip('no sample')
    if flag: monkeypatch.setenv('WL_SIZEPRES', '1')
    else: monkeypatch.delenv('WL_SIZEPRES', raising=False)
    import wledit, cfb, savegate as sg
    ed = wledit.Editor(SRC); pn, i, r, log, q = ed.trace(7247); old = [l for l in log if l[1] == 'KeyBasedTreeEntryWrapper.m_key'][0][4]
    e = wledit.Editor(SRC); e.set_strings([(7247, 'KeyBasedTreeEntryWrapper.m_key', old + 'Z')]); o = str(tmp_path / 'o.rfa'); e.save(o); b = open(o, 'rb').read()
    A = cfb.CFB(open(SRC, 'rb').read()).streams(); B = cfb.CFB(b).streams()
    assert [k for k in A if bytes(A[k].data) != bytes(B[k].data)] == [pn]
    d = _pages(bytes(A[pn].data), bytes(B[pn].data))
    if flag: assert len(d) <= 2 and len(bytes(A[pn].data)) == len(bytes(B[pn].data)), d
    cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur)
    assert sg.save(sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False)), b, {'modified': ['stream:' + pn, 'el:7247']}).ok
    print(flag or 'standard', 'pages differing', len(d), 'of', len(bytes(A[pn].data)) // 65249 + 1)
