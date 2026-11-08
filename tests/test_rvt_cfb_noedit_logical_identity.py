"""Container no-edit round trip (queue 156): cfb.write(CFB(x)) re-lays out every stream
(start sectors move) but must keep every stream's bytes, every directory entry field
(name, type, tree links, clsid, state, size) and the total file size, on every public sample."""
import glob, os, sys
import pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab'))
import cfb

SAMPLES = sorted(glob.glob(os.path.expanduser('~/rvt-research/samples-rfa/*.rfa')))


@pytest.mark.skipif(not SAMPLES, reason='no samples')
@pytest.mark.parametrize('path', SAMPLES, ids=os.path.basename)
def test_noedit_logical_identity(path, tmp_path):
    a = open(path, 'rb').read()
    o = str(tmp_path / 'o.rfa')
    cfb.write(cfb.CFB(a), o)
    b = open(o, 'rb').read()
    assert len(a) == len(b)
    assert a[:48] == b[:48]
    ca, cb = cfb.CFB(a), cfb.CFB(b)
    assert len(ca.entries) == len(cb.entries)
    for x, y in zip(ca.entries, cb.entries):
        assert (x.name, x.type, x.left, x.right, x.child, x.clsid, x.state, x.size) == \
               (y.name, y.type, y.left, y.right, y.child, y.clsid, y.state, y.size)
        if x.type == 2:
            assert x.data == y.data
