import os, errno
def test_journal_enospc_save_still_exact(tmp_path, monkeypatch):
    import savegate as sg, savegate.journal as jr
    from savegate.adapters import RawAdapter
    monkeypatch.setenv('SAVEGATE_JOURNAL', str(tmp_path / 'j'))
    def boom(fd): raise OSError(errno.ENOSPC, 'No space left on device')
    monkeypatch.setattr(jr, 'full_fsync', boom)
    p = str(tmp_path / 'f.bin'); open(p, 'wb').write(os.urandom(30000))
    d = sg.open_doc(p, RawAdapter(), sg.Config(allow_overwrite=True, require_gate=False))
    sg.save(d, b'N' * 40000, {'modified': ['file']})
    assert open(p, 'rb').read() == b'N' * 40000
