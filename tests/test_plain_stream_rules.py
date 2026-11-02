"""c7x-rvtread2: structure rules for the plain RVT streams + Formats/Latest page ECC. Public Autodesk samples only."""
import os, glob, shutil, pytest
olefile = pytest.importorskip('olefile')
from savegate import adapters
S = os.path.expanduser('~/rvt-research/samples-rfa/')
SRC = S + 'racbasicsamplefamily-2024.rfa'
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='public sample missing')
PLAIN = ('PartAtom', 'RevitPreview4.0', 'BasicFileInfo', 'Contents', 'TransmissionData')

def test_clean_public_samples_unflagged():
    A = adapters.RvtAdapter(); bad = []
    for f in sorted(glob.glob(S + '*.rfa')):
        r = [e for e in A.source_damage(open(f, 'rb').read()) if e.split(':')[0] in PLAIN + ('Formats/Latest',)]
        if r: bad.append((os.path.basename(f), r))
    assert bad == []

@pytest.mark.parametrize('st', PLAIN)
def test_zeroed_plain_stream_reported(st, tmp_path):
    p = str(tmp_path / 'f.rfa'); shutil.copy(SRC, p)
    o = olefile.OleFileIO(p, write_mode=True); n = o.get_size(st)
    if n == 0: pytest.skip('stream empty')
    o.write_stream(st, bytes(n)); o.close()
    assert any(e.startswith(st) for e in adapters.RvtAdapter().source_damage(open(p, 'rb').read()))
