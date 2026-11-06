"""c7x-rvtread2 212: an unwritable journal directory must not stop open_doc/save."""
import os, sys, pytest
pytestmark = pytest.mark.skipif(sys.platform == 'win32' or (hasattr(os, 'geteuid') and os.geteuid() == 0), reason='POSIX permissions, non-root')

def test_readonly_journal_dir(tmp_path, monkeypatch):
    import savegate as sg
    from savegate.adapters import RawAdapter
    j = tmp_path / 'j'; j.mkdir(); j.chmod(0o500); monkeypatch.setenv('SAVEGATE_JOURNAL', str(j))
    p = str(tmp_path / 'f.bin'); open(p, 'wb').write(os.urandom(30000))
    try:
        sg.save(sg.open_doc(p, RawAdapter(), sg.Config(allow_overwrite=True, require_gate=False)), b'N' * 40000, {'modified': ['file']})
    finally: j.chmod(0o700)
    assert open(p, 'rb').read() == b'N' * 40000
