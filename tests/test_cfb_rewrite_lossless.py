"""c7x-rvtread2 134-139: write-lab cfb.write must be a lossless, idempotent container rewrite (public 2024 sample)."""
import os, sys, tempfile, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab'))
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(F), reason='public sample missing')

def _meta(c):
    return {c.path(e): (e.type, bytes(e.clsid), e.state, bytes(e.ctime), bytes(e.mtime)) for e in c.entries if e.idx in c._paths()}

def test_rewrite_lossless_and_idempotent():
    cfb = pytest.importorskip('cfb'); d = tempfile.mkdtemp()
    a = cfb.CFB(open(F, 'rb').read()); cfb.write(a, d + '/1'); b = cfb.CFB(open(d + '/1', 'rb').read())
    assert {k: e.data for k, e in a.streams().items()} == {k: e.data for k, e in b.streams().items()}
    assert _meta(a) == _meta(b)
    cfb.write(b, d + '/2'); assert open(d + '/1', 'rb').read() == open(d + '/2', 'rb').read()

@pytest.mark.parametrize('n', [0, 1, 63, 64, 511, 512, 4095, 4096, 4097, 8192, 70000])
def test_resized_stream_roundtrip(n):
    cfb = pytest.importorskip('cfb'); olefile = pytest.importorskip('olefile'); d = tempfile.mkdtemp()
    c = cfb.CFB(open(F, 'rb').read()); data = bytes((i * 7 + 1) & 255 for i in range(n)); c.streams()['BasicFileInfo'].data = data
    cfb.write(c, d + '/o'); o = olefile.OleFileIO(d + '/o')
    assert o.get_size('BasicFileInfo') == n and o.openstream('BasicFileInfo').read() == data
