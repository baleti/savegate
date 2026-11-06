"""c5x-rvtgap: another program rewrites the file after the last pre-rename check but before the rename (the narrowest race). The save may go ahead, but the
foreign version must not be lost: it has to be kept as a backup (RESTORE brings it back) and reported in warnings."""
import os, sys, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no public sample')


def test_foreign_write_just_before_rename_is_kept_as_backup(tmp_path, monkeypatch):
    import savegate as sg, wledit
    from savegate import atomic
    ed = wledit.Editor(SRC); ed.set_strings([(7, 'FillPattern.m_name', 'Zed')]); o = str(tmp_path / 'o.rfa'); ed.save(o); new = open(o, 'rb').read()
    cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur)
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    foreign = open(SRC, 'rb').read() + b'\0' * 4096
    real = atomic.commit_temp
    def racing(tmp, dest, **kw):
        with open(dest, 'wb') as f: f.write(foreign)
        return real(tmp, dest, **kw)
    monkeypatch.setattr(atomic, 'commit_temp', racing)
    rep = sg.save(doc, new, {'modified': ['stream:Partitions/67', 'el:7']})
    monkeypatch.undo()
    assert open(cur, 'rb').read() == new
    kept = []
    for root, _, fs in os.walk(os.path.dirname(cur)):
        for f in fs:
            kept.append(open(os.path.join(root, f), 'rb').read())
    import savegate.backup as b
    found = any(bytes(x) == foreign for x in kept)
    if not found:
        found = any(open(p, 'rb').read() == foreign for _, p in b.list_backups(cur))
    assert found, 'foreign version lost'
