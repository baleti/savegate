"""c2x-rvtgap 145: save_as(overwrite=True) onto an existing destination (an older-year rfa, and a non-Revit file) keeps the previous bytes as a backup; restore(dest) returns exactly those bytes."""
import os, sys, shutil, pytest
import savegate as sg
D = os.path.expanduser('~/rvt-research/samples-rfa/')
F = D + 'racbasicsamplefamily-2024.rfa'
@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
@pytest.mark.parametrize('kind', ['rfa2022', 'garbage'])
def test_overwrite_then_restore(tmp_path, kind):
    sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
    import wledit
    a = str(tmp_path / 'a.rfa'); shutil.copy(F, a)
    ed = wledit.Editor(a); ed.set_strings([(7, 'FillPattern.m_name', 'SA')]); o = str(tmp_path / 'o.tmp'); ed.save(o)
    new = open(o, 'rb').read(); os.remove(o)
    dest = str(tmp_path / 'b.rfa')
    if kind == 'garbage': open(dest, 'wb').write(b'not a revit file' * 100)
    else: shutil.copy(D + 'racbasicsamplefamily-2022.rfa', dest)
    prev = open(dest, 'rb').read()
    doc = sg.open_doc(a, None, sg.Config(allow_overwrite=True, require_gate=False))
    assert sg.save_as(doc, new, dest, {'modified': ['stream:Partitions/67', 'el:7']}, overwrite=True).ok
    assert open(dest, 'rb').read() == new
    sg.restore(dest)
    assert open(dest, 'rb').read() == prev
