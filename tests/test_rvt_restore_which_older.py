"""c2x-rvtgap 147: after 3 chained gate saves (v0 -> v3) restore(path, which=2) returns the ORIGINAL v0 bytes; an out-of-range which raises SaveError and leaves the file alone."""
import os, sys, shutil, pytest
import savegate as sg
from savegate.errors import SaveError
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
def test_which_older(tmp_path):
    sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
    import wledit
    t = str(tmp_path / 'x.rfa'); shutil.copy(F, t); vers = [open(t, 'rb').read()]
    man = {'modified': ['stream:Partitions/67', 'el:7']}
    for i in range(3):
        ed = wledit.Editor(t); ed.set_strings([(7, 'FillPattern.m_name', 'V%d' % i)]); o = str(tmp_path / 'o.tmp'); ed.save(o)
        new = open(o, 'rb').read(); os.remove(o)
        doc = sg.open_doc(t, None, sg.Config(allow_overwrite=True, require_gate=False, backup_keep=5))
        assert sg.save(doc, new, man).ok; vers.append(new)
    sg.restore(t, which=2); assert open(t, 'rb').read() == vers[0]
    with pytest.raises(SaveError): sg.restore(t, which=99)
    assert open(t, 'rb').read() == vers[0]
