"""c5x-rvtgap: when no backup store can be written (full / read-only / missing), the in-place save must refuse BEFORE touching the original (no backup, no overwrite),
and leave no temp file in the destination folder."""
import os, sys, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC) or os.geteuid() == 0, reason='no public sample / root ignores modes')


def test_unwritable_backup_stores_leave_original_untouched(tmp_path, monkeypatch):
    import savegate as sg, wledit
    from savegate import backup
    ed = wledit.Editor(SRC); ed.set_strings([(7, 'FillPattern.m_name', 'Zed')]); o = str(tmp_path / 'o.rfa'); ed.save(o); new = open(o, 'rb').read()
    work = tmp_path / 'w'; work.mkdir(); cur = str(work / 'c.rfa'); shutil.copy(SRC, cur); before = open(cur, 'rb').read()
    ro = tmp_path / 'ro'; ro.mkdir(); ro.chmod(0o500)
    monkeypatch.setattr(backup, 'backup_dirs', lambda p: [str(ro / 'a'), str(ro / 'b')])
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    try:
        with pytest.raises(sg.SaveError):
            sg.save(doc, new, {'modified': ['stream:Partitions/67', 'el:7']})
    finally: ro.chmod(0o700)
    assert open(cur, 'rb').read() == before
    assert [f for f in os.listdir(work) if f != 'c.rfa' and not f.startswith('.savegate')] == [] or all(f.endswith('lock') for f in os.listdir(work) if f != 'c.rfa')
