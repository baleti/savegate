"""c2x-rvtgap 142: a save refused by the memory preflight (LowMemory, forced with a huge SAVEGATE_MEM_FACTOR) leaves the original byte-identical and only x.rfa in the folder (no backup, temp, lock); the same save with the default factor is accepted."""
import os, sys, shutil, pytest
import savegate as sg
from savegate.errors import LowMemory
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
def test_lowmemory_clean(tmp_path, monkeypatch):
    sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
    import wledit
    t = str(tmp_path / 'x.rfa'); shutil.copy(F, t); orig = open(t, 'rb').read()
    ed = wledit.Editor(t); ed.set_strings([(7, 'FillPattern.m_name', 'Mem')]); o = str(tmp_path / 'o.tmp'); ed.save(o)
    new = open(o, 'rb').read(); os.remove(o)
    man = {'modified': ['stream:Partitions/67', 'el:7']}
    doc = sg.open_doc(t, None, sg.Config(allow_overwrite=True, require_gate=False))
    monkeypatch.setenv('SAVEGATE_MEM_FACTOR', '1000000')
    with pytest.raises(LowMemory): sg.save(doc, new, man)
    assert open(t, 'rb').read() == orig and sorted(os.listdir(tmp_path)) == ['x.rfa']
    monkeypatch.delenv('SAVEGATE_MEM_FACTOR')
    assert sg.save(doc, new, man).ok and open(t, 'rb').read() == new
