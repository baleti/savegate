"""c7x-rvtread2: Formats/Latest is a page-ECC stream (despite starting with a gzip header). A 1-bit flip in a stored page changes the
parsed class table yet inflates and parses, and the writer re-encodes with fresh ECC (damage laundered). source_damage must report it.
Autodesk public sample only. Sweep of 8 offsets; clean sample must give []."""
import os, shutil, pytest
olefile = pytest.importorskip('olefile')
from savegate import adapters
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
OFFS = (3928, 7849, 31377, 54905, 66669, 86276, 109804, 149018)

@pytest.mark.skipif(not os.path.exists(SRC), reason='public sample missing')
def test_formats_latest_bit_flip_reported(tmp_path):
    A = adapters.RvtAdapter()
    assert A.source_damage(open(SRC, 'rb').read()) == []
    miss = []
    for off in OFFS:
        p = str(tmp_path / 'f.rfa'); shutil.copy(SRC, p)
        o = olefile.OleFileIO(p, write_mode=True)
        d = bytearray(o.openstream('Formats/Latest').read()); d[off] ^= 1
        o.write_stream('Formats/Latest', bytes(d)); o.close()
        if not any('Formats/Latest' in e for e in A.source_damage(open(p, 'rb').read())): miss.append(off)
    assert miss == []
