"""c2x-rvtgap: the pristine original (the first backup ever made) must survive pruning: 25 saves with backup_keep=20 used to leave no copy of it."""
import savegate as sg
from savegate.adapters import RawAdapter


def test_first_original_survives_more_saves_than_backup_keep(tmp_path):
    p = str(tmp_path / 'f.bin'); open(p, 'wb').write(b'ORIGINAL')
    for i in range(25):
        with sg.open_doc(p, RawAdapter(), sg.Config(allow_overwrite=True, require_gate=False)) as doc:
            sg.save(doc, ('v%d' % i).encode(), {'modified': ['file']})
    bl = sg.list_backups(p)
    assert len(bl) == 20
    assert open(bl[-1][1], 'rb').read() == b'ORIGINAL'          # oldest = pristine original
    assert open(bl[0][1], 'rb').read() == b'v23'                # newest = the version replaced by the last save
    sg.restore(p, len(bl) - 1)
    assert open(p, 'rb').read() == b'ORIGINAL'
