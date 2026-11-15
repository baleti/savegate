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
