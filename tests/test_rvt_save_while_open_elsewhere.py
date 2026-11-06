"""c2x-rvtgap item 23: the target is held open (read handle, and an flock) by another process/handle while an in-place gate save runs: the save finishes, the
path holds the new bytes, the holder's handle still reads the complete OLD bytes (no torn file), and a backup of the old state exists."""
import os, sys, shutil, hashlib, fcntl, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no public sample')


def test_save_with_target_open_and_locked(tmp_path):
    import savegate as sg, wledit
    from savegate.adapters import RvtAdapter
    cur = str(tmp_path / 'm.rfa'); shutil.copy(SRC, cur); old = open(SRC, 'rb').read()
    ed = wledit.Editor(cur); ed.set_strings([(7, 'FillPattern.m_name', 'Held')]); o = str(tmp_path / 'o.rfa'); ed.save(o); new = open(o, 'rb').read()
    fh = open(cur, 'rb'); fcntl.flock(fh, fcntl.LOCK_SH); fh.read(1000)
    try:
        doc = sg.open_doc(cur, RvtAdapter(), sg.Config(allow_overwrite=True, require_gate=False))
        sg.save(doc, new, {'modified': ['stream:Partitions/67', 'el:7']})
        assert open(cur, 'rb').read() == new
        fh.seek(0); assert fh.read() == old, 'holder saw a torn or modified old file'
    finally: fh.close()
    assert any(open(b[1], 'rb').read() == old for b in sg.list_backups(cur))
