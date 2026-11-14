"""c7x-rvtread2 594: target on tmpfs (/dev/shm), its .savegate folder blocked so the backup falls back to the cache dir on another file system.
The backup must be a real copy of the old bytes (no EXDEV rename failure), the save must succeed or refuse with the original intact."""
import os, sys, shutil, tempfile, pytest
import savegate as sg
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
@pytest.mark.skipif(not (os.path.exists(F) and os.path.isdir('/dev/shm')), reason='no sample')
def test_xdev(tmp_path, monkeypatch):
    sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
    import wledit
    monkeypatch.setenv('XDG_CACHE_HOME', str(tmp_path / 'cache'))
    d = tempfile.mkdtemp(dir='/dev/shm')
    try:
        if os.stat(d).st_dev == os.stat(tmp_path).st_dev: pytest.skip('same fs')
        a = os.path.join(d, 'a.rfa'); shutil.copy(F, a); open(os.path.join(d, '.savegate'), 'w').write('block')   # a file where the folder should be
        old = open(a, 'rb').read()
        ed = wledit.Editor(a); ed.set_strings([(7, 'FillPattern.m_name', 'Edited')]); o = os.path.join(d, 'o.tmp'); ed.save(o)
        new = open(o, 'rb').read(); os.remove(o)
        doc = sg.open_doc(a, None, sg.Config(allow_overwrite=True, require_gate=False))
        try: sg.save(doc, new, {'modified': ['stream:Partitions/67', 'el:7']}); ok = True
        except sg.SaveError as e: ok = False; print('REFUSED', str(e)[:120])
        now = open(a, 'rb').read()
        assert now == (new if ok else old)
        if ok:
            from savegate.backup import list_backups
            bs = list_backups(a)
            assert any(open(b[1], 'rb').read() == old for b in bs), 'no byte-identical backup of the old file'
            assert not any(f.endswith('.part') for _, _, fs in os.walk(str(tmp_path / 'cache')) for f in fs)
        print('ok', ok)
    finally: shutil.rmtree(d, ignore_errors=True)
