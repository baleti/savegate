"""c7x-rvtread2 regression: a 64-byte flip inside a raw-gzip stream (Formats/Latest) must be reported by RvtAdapter.source_damage.
Autodesk public sample only. Fails until adapters.RvtAdapter._damage stops skipping raw-gzip streams (patch: demo-state/suggested_savegate_c7x_rawgzip.patch)."""
import os, shutil, pytest
olefile = pytest.importorskip('olefile')
from savegate import adapters
SRC = os.path.expanduser('~/rvt-research/samples-rfa/rac_basic_sample_family-2018.rfa')

@pytest.mark.skipif(not os.path.exists(SRC), reason='public sample missing')
def test_formats_latest_flip_detected(tmp_path):
    A = adapters.RvtAdapter()
    assert A.source_damage(open(SRC, 'rb').read()) == []
    p = str(tmp_path / 'f.rfa'); shutil.copy(SRC, p)
    o = olefile.OleFileIO(p, write_mode=True)
    d = bytearray(o.openstream('Formats/Latest').read()); m = len(d) // 2
    for k in range(64): d[m + k] ^= 0xff
    o.write_stream('Formats/Latest', bytes(d)); o.close()
    assert A.source_damage(open(p, 'rb').read()) != []
