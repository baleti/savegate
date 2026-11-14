"""c2x-rvtgap 152: at the keep limit (backup_keep=2) every accepted save leaves backups that pass verify_backup (name hash tag == content) and the pristine original is among them; a flipped byte in one makes verify_backup False."""
import os, sys, shutil, pytest
import savegate as sg
from savegate import backup
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
def test_backups_verify(tmp_path):
    sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
    import wledit
    t = str(tmp_path / 'x.rfa'); shutil.copy(F, t); orig = open(t, 'rb').read(); man = {'modified': ['stream:Partitions/67', 'el:7']}
    for i in range(4):
        ed = wledit.Editor(t); ed.set_strings([(7, 'FillPattern.m_name', 'B%d' % i)]); o = str(tmp_path / 'o.tmp'); ed.save(o)
        new = open(o, 'rb').read(); os.remove(o)
        doc = sg.open_doc(t, None, sg.Config(allow_overwrite=True, require_gate=False, backup_keep=2))
        assert sg.save(doc, new, man).ok
        bl = backup.list_backups(t); assert len(bl) == min(i + 1, 2)
        assert all(backup.verify_backup(p) for _, p, _ in bl)
        assert any(open(p, 'rb').read() == orig for _, p, _ in bl)
    p = bl[0][1]; d = bytearray(open(p, 'rb').read()); d[1000] ^= 1; open(p, 'wb').write(bytes(d))
    assert not backup.verify_backup(p)
