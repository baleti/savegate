"""c2x-rvtgap 151: with backup_keep=2 at its limit (2 backups held), a REFUSED save (oversized string edit, VerifyFailed) leaves the backup set byte-identical: same names, nothing pruned, nothing added."""
import os, sys, shutil, pytest
import savegate as sg
from savegate.errors import VerifyFailed
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2026.rfa')
@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
def test_refusal_keeps_backup_set(tmp_path):
    sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
    import wledit
    t = str(tmp_path / 'x.rfa'); shutil.copy(F, t); man = {'modified': ['stream:Partitions/69', 'el:7']}
    def build(txt):
        ed = wledit.Editor(t); ed.set_strings([(7, 'FillPattern.m_name', txt)]); o = str(tmp_path / 'o.tmp'); ed.save(o)
        b = open(o, 'rb').read(); os.remove(o); return b
    for i in range(4):
        doc = sg.open_doc(t, None, sg.Config(allow_overwrite=True, require_gate=False, backup_keep=2))
        assert sg.save(doc, build('K%d' % i), man).ok
    store = tmp_path / '.savegate'; before = sorted(os.listdir(store)); cur = open(t, 'rb').read()
    assert len(before) == 2
    doc = sg.open_doc(t, None, sg.Config(allow_overwrite=True, require_gate=False, backup_keep=2))
    with pytest.raises(VerifyFailed): sg.save(doc, build('G' * 9000), man)
    assert sorted(os.listdir(store)) == before and open(t, 'rb').read() == cur
