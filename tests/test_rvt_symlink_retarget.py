"""c5x-rvtgap 125: open_doc on a symlink resolves it; if the link is re-pointed to a different file before save, the save must touch neither file with a stale plan."""
import os, sys, shutil, pytest
import savegate as sg
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
G = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2026.rfa')
@pytest.mark.skipif(not (os.path.exists(F) and os.path.exists(G)), reason='no sample')
def test_retarget(tmp_path):
    sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
    import wledit
    a = tmp_path / 'a.rfa'; b = tmp_path / 'b.rfa'; shutil.copy(F, a); shutil.copy(G, b)
    link = tmp_path / 'link.rfa'; os.symlink(a, link)
    ed = wledit.Editor(str(a)); ed.set_strings([(7, 'FillPattern.m_name', 'Edited')]); o = str(tmp_path / 'o.tmp'); ed.save(o)
    new = open(o, 'rb').read(); os.remove(o)
    ha, hb = a.read_bytes(), b.read_bytes()
    doc = sg.open_doc(str(link), None, sg.Config(allow_overwrite=True, require_gate=False))
    os.remove(link); os.symlink(b, link)
    try: r = sg.save(doc, new, {'modified': ['stream:Partitions/67', 'el:7']}); ok = r.ok
    except sg.SaveError: ok = False
    assert a.read_bytes() in (ha, new)      # the file resolved at open time (a) is the only one that may change
    assert b.read_bytes() == hb
    assert os.path.islink(link) and os.path.realpath(link) == str(b)
