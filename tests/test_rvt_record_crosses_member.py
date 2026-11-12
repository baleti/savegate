"""c4x-rvtgap 360: a string edit inside a record that crosses a gzip member boundary (2026/2024 family, el 7247 KeyBasedTreeEntryWrapper.m_key, record span ~125 KB over members 3-4).
Before: Editor refused ('edit straddles members'). Now: the record is patched as minimal spans; one stream differs, readback equals, default gate accepts."""
import os, sys, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))

@pytest.mark.parametrize('y', ['2024', '2026'])
def test_cross_member_record_string_edit(tmp_path, y):
    SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-%s.rfa' % y)
    if not os.path.exists(SRC): pytest.skip('no sample')
    import wledit, cfb, savegate as sg
    ed = wledit.Editor(SRC); pn, i, r, log, q = ed.trace(7247); old = [l for l in log if l[1] == 'KeyBasedTreeEntryWrapper.m_key'][0][4]
    e = wledit.Editor(SRC); e.set_strings([(7247, 'KeyBasedTreeEntryWrapper.m_key', old + 'Z')]); o = str(tmp_path / 'o.rfa'); e.save(o); b = open(o, 'rb').read()
    A = cfb.CFB(open(SRC, 'rb').read()).streams(); B = cfb.CFB(b).streams()
    assert [k for k in A if bytes(A[k].data) != bytes(B[k].data)] == [pn]
    assert [l[4] for l in wledit.Editor(o).trace(7247)[3] if l[1] == 'KeyBasedTreeEntryWrapper.m_key'][0] == old + 'Z'
    cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur)
    assert sg.save(sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False)), b, {'modified': ['stream:' + pn, 'el:7247']}).ok
