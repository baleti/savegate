"""c7x-rvtread2 193: a target held under an exclusive flock by another handle is refused (Locked), untouched; a shared lock does not block."""
import os, sys, pytest
pytestmark = pytest.mark.skipif(sys.platform == 'win32', reason='POSIX flock')

def _doc(p):
    import savegate as sg
    from savegate.adapters import RawAdapter
    return sg.open_doc(p, RawAdapter(), sg.Config(allow_overwrite=True, require_gate=False))

def test_exclusive_flock_refused(tmp_path):
    import fcntl, savegate as sg
    p = str(tmp_path / 'f.bin'); orig = os.urandom(30000); open(p, 'wb').write(orig)
    h = open(p, 'r+b'); fcntl.flock(h, fcntl.LOCK_EX)
    try:
        with pytest.raises(sg.Locked): sg.save(_doc(p), b'N' * 40000, {'modified': ['file']})
    finally: h.close()
    assert open(p, 'rb').read() == orig

def test_shared_flock_allowed(tmp_path):
    import fcntl, savegate as sg
    p = str(tmp_path / 'f.bin'); open(p, 'wb').write(os.urandom(30000))
    h = open(p, 'rb'); fcntl.flock(h, fcntl.LOCK_SH)
    try: sg.save(_doc(p), b'N' * 40000, {'modified': ['file']})
    finally: h.close()
    assert open(p, 'rb').read() == b'N' * 40000
