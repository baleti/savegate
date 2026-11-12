"""c2x-rvtgap: a backup damaged on disk (flipped byte, truncated, emptied) must NOT be restored over a good current file silently:
restore either refuses (file untouched) or, if it restores, the result is byte-identical to what the backup held AND that is reported. Silent acceptance of a damaged backup is the escape."""
import os, sys, shutil, pytest
import savegate as sg
from savegate.backup import list_backups
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(F), reason='no sample')


@pytest.mark.parametrize('dmg', ['flip', 'truncate', 'empty'])
def test_damaged_backup(tmp_path, dmg):
    import wledit
    f = str(tmp_path / 'a.rfa'); shutil.copy(F, f)
    ed = wledit.Editor(f); ed.set_strings([(7, 'FillPattern.m_name', 'Good edit')]); o = str(tmp_path / 'o.tmp'); ed.save(o); new = open(o, 'rb').read(); os.remove(o)
    doc = sg.open_doc(f, None, sg.Config(allow_overwrite=True, require_gate=False))
    assert sg.save(doc, new, {'modified': ['stream:Partitions/67', 'el:7']}).ok
    (_, bp, _), = list_backups(f)[:1]
    b = bytearray(open(bp, 'rb').read())
    if dmg == 'flip': b[len(b) // 2] ^= 1
    elif dmg == 'truncate': b = b[:len(b) // 2]
    else: b = bytearray()
    open(bp, 'wb').write(bytes(b))
    try: sg.restore(f)
    except Exception: assert open(f, 'rb').read() == new, 'refused restore must leave the current file untouched'; return
    pytest.fail('damaged backup (%s) was restored over the good file without any error' % dmg)
