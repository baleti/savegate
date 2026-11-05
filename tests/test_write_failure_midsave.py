"""c2x-rvtgap: a write that fails part-way (RLIMIT_FSIZE -> EFBIG, the nearest portable stand-in for ENOSPC) must leave the original byte-identical and no temp files."""
import os, sys, signal, pytest
pytestmark = pytest.mark.skipif(sys.platform == 'win32', reason='POSIX rlimit')


@pytest.mark.parametrize('limit', [10000, 49000, 60000, 100000])
def test_write_failure_leaves_original_intact_and_no_leftovers(tmp_path, limit):
    import resource, savegate as sg
    from savegate.adapters import RawAdapter
    p = str(tmp_path / 'f.bin'); orig = os.urandom(50000); open(p, 'wb').write(orig)
    doc = sg.open_doc(p, RawAdapter(), sg.Config(allow_overwrite=True, require_gate=False))
    old = signal.signal(signal.SIGXFSZ, signal.SIG_IGN); soft, hard = resource.getrlimit(resource.RLIMIT_FSIZE)
    resource.setrlimit(resource.RLIMIT_FSIZE, (limit, hard))
    try:
        with pytest.raises(sg.SaveError):
            sg.save(doc, os.urandom(120000), {'modified': ['file']})
    finally:
        resource.setrlimit(resource.RLIMIT_FSIZE, (soft, hard)); signal.signal(signal.SIGXFSZ, old)
    assert open(p, 'rb').read() == orig
    assert os.listdir(str(tmp_path)) == ['f.bin']
