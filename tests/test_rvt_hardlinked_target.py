"""c7x-rvtread2 593: target has a second hardlink (e.g. a sync tool or a user copy-as-link). Save must either leave BOTH names consistent
(same bytes, both valid) or update the target and leave the other name as the intact old file. Never a mix, never a truncated/damaged file."""
import os, sys, shutil, pytest
import savegate as sg
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
def test_hardlink(tmp_path):
    sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
    import wledit
    a = tmp_path / 'a.rfa'; shutil.copy(F, a); h = tmp_path / 'h.rfa'; os.link(a, h)
    ed = wledit.Editor(str(a)); ed.set_strings([(7, 'FillPattern.m_name', 'Edited')]); o = str(tmp_path / 'o.tmp'); ed.save(o)
    new = open(o, 'rb').read(); os.remove(o); old = a.read_bytes()
    doc = sg.open_doc(str(a), None, sg.Config(allow_overwrite=True, require_gate=False))
    refused = False
    try: sg.save(doc, new, {'modified': ['stream:Partitions/67', 'el:7']})
    except sg.SaveError as e: refused = True
    A, H = a.read_bytes(), h.read_bytes()
    assert A in (old, new) and H in (old, new)
    print('same inode after save:', os.stat(a).st_ino == os.stat(h).st_ino, 'a new:', A == new, 'h new:', H == new)
    assert refused and A == old and H == old
