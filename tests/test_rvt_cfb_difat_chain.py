"""c4x-rvtgap 166: a container needing a DIFAT chain (>109 FAT sectors, 4096-byte sectors => stream > ~457 MB) round-trips through cfb.write/CFB with all stream bytes equal, and the DIFAT audit reports no problem. Heavy (~1.5 GB RAM): run with RVT_HEAVY=1."""
import os, sys, struct, hashlib, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = [pytest.mark.skipif(not os.path.exists(SRC), reason='no sample'), pytest.mark.skipif(not os.environ.get('RVT_HEAVY'), reason='heavy (set RVT_HEAVY=1)')]

def test_difat_chain_roundtrip(tmp_path):
    import cfb
    c = cfb.CFB(open(SRC, 'rb').read()); name = max(c.streams(), key=lambda k: len(c.streams()[k].data))
    big = (b'\x5a\xa5' * 2048) * (115 * 1024)      # 115 FAT sectors worth of 4096-byte sectors
    c.streams()[name].data = big
    o = str(tmp_path / 'big.rfa'); cfb.write(c, o)
    b = open(o, 'rb').read()
    assert struct.unpack_from('<I', b, 72)[0] >= 1, 'no DIFAT sector used'      # ndif
    c2 = cfb.CFB(b)
    assert hashlib.sha256(c2.streams()[name].data).digest() == hashlib.sha256(big).digest()
    others = [k for k in c.streams() if k != name]
    assert all(c2.streams()[k].data == cfb.CFB(open(SRC, 'rb').read()).streams()[k].data for k in others)
    R = pytest.importorskip('rvt_integrity')
    assert R.difat_problems(b) == []
