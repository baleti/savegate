"""c2x-rvtgap 150: with backup_max_bytes=1000 (smaller than ONE backup) and 5 chained gate saves exactly 2 backups remain: the newest pre-save state (v4) and the pristine ORIGINAL (v0, pinned by _prune); which=0/1 restore them exactly, which=2 is refused (pruned) and the file is unchanged."""
import os, sys, shutil, pytest
import savegate as sg
from savegate.errors import SaveError
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
def test_max_bytes_smaller_than_one(tmp_path):
    sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
    import wledit
    t = str(tmp_path / 'x.rfa'); shutil.copy(F, t); vers = [open(t, 'rb').read()]
    man = {'modified': ['stream:Partitions/67', 'el:7']}
    for i in range(5):
        ed = wledit.Editor(t); ed.set_strings([(7, 'FillPattern.m_name', 'P%d' % i)]); o = str(tmp_path / 'o.tmp'); ed.save(o)
        new = open(o, 'rb').read(); os.remove(o)
        doc = sg.open_doc(t, None, sg.Config(allow_overwrite=True, require_gate=False, backup_keep=10, backup_max_bytes=1000))
        assert sg.save(doc, new, man).ok; vers.append(new)
    assert len(os.listdir(tmp_path / '.savegate')) == 2
    held = [[i for i, v in enumerate(vers) if v == open(bp, 'rb').read()] for _, bp, _ in sg.backup.list_backups(t)]
    assert held == [[4], [0]], held
    final = open(t, 'rb').read(); assert final == vers[5]
    with pytest.raises(SaveError): sg.restore(t, which=2)
    assert open(t, 'rb').read() == final
    sg.restore(t, which=1); assert open(t, 'rb').read() == vers[0]
