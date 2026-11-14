"""c5x-rvtread2 item 283 (sev 2, OPEN): a genuine Revit 2023 family whose BasicFileInfo year text is rewritten to 2024 (build stamp 2023 stays inside
[year-2, year]) passes the year gate; the editor then builds a consistent 4-byte-id (IDW 4) edit and the gate ACCEPTS the in-place save of a file that is
not 2024 content. Expected: refuse (check the id width / format stamp against the year). Fixed in RvtAdapter.sniff (id width from the schema must be 8 for a writable year)."""
import os, sys, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2023.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no public sample')


def test_mislabelled_2023_as_2024_is_refused(tmp_path):
    import savegate as sg, wledit, cfb
    u = lambda s: s.encode('utf-16-le')
    c = cfb.CFB(open(SRC, 'rb').read()); st = c.streams(); st['BasicFileInfo'].data = st['BasicFileInfo'].data.replace(u('2023'), u('2024'), 1)
    p = str(tmp_path / 'f.rfa'); cfb.write(c, p); before = open(p, 'rb').read()
    # the editor itself is fine with the file; the gate is what must refuse (open_doc already raises UnsupportedVersion)
    with pytest.raises(sg.SaveError):
        sg.open_doc(p, None, sg.Config(allow_overwrite=True, require_gate=False))
    return
    ed = wledit.Editor(p); ed.set_strings([(7, 'FillPattern.m_name', 'Edit 283')]); o = str(tmp_path / 'o.rfa'); ed.save(o)
    doc = sg.open_doc(p, None, sg.Config(allow_overwrite=True, require_gate=False))
    with pytest.raises(sg.SaveError):
        sg.save(doc, open(o, 'rb').read(), {'modified': ['el:7']})
    assert open(p, 'rb').read() == before
