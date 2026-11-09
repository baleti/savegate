"""c4x-rvtgap: 5 successive accepted saves of one file (each edit built from the file as the previous save left it): folder = file + .savegate only, backups bounded by keep (newest keep-1 + the pristine original), every backup is a byte-exact earlier version, restore returns it."""
import os, sys, shutil, hashlib, pytest
import savegate as sg
from savegate.backup import list_backups
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
def test_chain(tmp_path):
    import wledit
    f = str(tmp_path / 'a.rfa'); shutil.copy(F, f); versions = [open(f, 'rb').read()]
    doc = sg.open_doc(f, None, sg.Config(allow_overwrite=True, require_gate=False, backup_keep=3))
    for n in range(5):
        ed = wledit.Editor(f); ed.set_strings([(7, 'FillPattern.m_name', 'Step %d %s' % (n, 'x' * n))]); o = str(tmp_path / 'o.tmp.rfa'); ed.save(o)
        new = open(o, 'rb').read(); os.remove(o)
        r = sg.save(doc, new, {'modified': ['stream:Partitions/67', 'el:7']}); assert r.ok
        assert open(f, 'rb').read() == new; versions.append(new)
        assert open(r.backup, 'rb').read() == versions[-2]                      # the backup of THIS save is the version it replaced
    assert sorted(os.listdir(tmp_path)) == ['.savegate', 'a.rfa']
    bl = list_backups(f); assert len(bl) <= 3, len(bl)
    held = [open(p, 'rb').read() for _, p, _ in bl]
    assert versions[0] in held                                                 # pristine original survives the pruning
    assert all(h in versions[:-1] for h in held)                               # only earlier versions, no foreign bytes
    sg.restore(f); assert open(f, 'rb').read() == versions[-2]                 # newest backup = the version before the last save

@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
def test_restore_older_backups(tmp_path):
    import wledit
    f = str(tmp_path / 'a.rfa'); shutil.copy(F, f); versions = [open(f, 'rb').read()]
    doc = sg.open_doc(f, None, sg.Config(allow_overwrite=True, require_gate=False, backup_keep=4))
    for n in range(3):
        ed = wledit.Editor(f); ed.set_strings([(7, 'FillPattern.m_name', 'Old %d %s' % (n, 'y' * n))]); o = str(tmp_path / 'o.tmp.rfa'); ed.save(o)
        new = open(o, 'rb').read(); os.remove(o); sg.save(doc, new, {'modified': ['stream:Partitions/67', 'el:7']}); versions.append(new)
    bl = list_backups(f); order = [open(p, 'rb').read() for _, p, _ in bl]      # newest first
    assert order == [versions[2], versions[1], versions[0]], [versions.index(x) if x in versions else None for x in order]
    for expect in (versions[0], versions[1], versions[2]):
        # restore() backs up the current file first, so indices shift after every restore: locate the wanted version by content
        cur = [open(p, 'rb').read() for _, p, _ in list_backups(f)]; which = cur.index(expect)
        sg.restore(f, which); assert open(f, 'rb').read() == expect, which
        assert versions[0] in [open(p, 'rb').read() for _, p, _ in list_backups(f)], 'pristine pruned after restore'
