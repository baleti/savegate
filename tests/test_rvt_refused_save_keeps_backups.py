"""c2x-rvtgap 98: after one accepted save, a REFUSED save (output carries a change that is not declared) must leave the file byte-identical, create no new backup, leave the existing backups unchanged and leave no stray files."""
import os, sys, shutil, pytest
import savegate as sg
from savegate.backup import list_backups
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
def test_refused_save_keeps_backups(tmp_path):
    import wledit
    f = str(tmp_path / 'a.rfa'); shutil.copy(F, f)
    doc = sg.open_doc(f, None, sg.Config(allow_overwrite=True, require_gate=False, backup_keep=3))
    def build(txt):
        ed = wledit.Editor(f); ed.set_strings([(7, 'FillPattern.m_name', txt)]); o = str(tmp_path / 'o.tmp.rfa'); ed.save(o)
        b = open(o, 'rb').read(); os.remove(o); return b
    r = sg.save(doc, build('First'), {'modified': ['stream:Partitions/67', 'el:7']}); assert r.ok
    cur = open(f, 'rb').read(); before = [(p, open(p, 'rb').read()) for _, p, _ in list_backups(f)]
    bad = build('Second')
    with pytest.raises(sg.errors.VerifyFailed):                              # edit is in Partitions/67 but only BasicFileInfo declared
        sg.save(doc, bad, {'modified': ['stream:BasicFileInfo']})
    assert open(f, 'rb').read() == cur
    after = [(p, open(p, 'rb').read()) for _, p, _ in list_backups(f)]
    assert after == before
    assert sorted(os.listdir(tmp_path)) == ['.savegate', 'a.rfa']
