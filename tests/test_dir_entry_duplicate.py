"""c7x-rvtread2 58: a directory entry overwritten by a copy of another (stream lost/duplicated) used to pass source_damage (128 of 992 pairs per sample)."""
import os, struct, pytest
from savegate import adapters
F = os.path.expanduser('~/rvt-research/samples-rfa/rac_basic_sample_family-2018.rfa')

@pytest.mark.skipif(not os.path.exists(F), reason='public sample missing')
@pytest.mark.parametrize('i,j', [(8, 13), (13, 6), (17, 6), (8, 15)])
def test_duplicated_dir_entry_reported(i, j):
    src = open(F, 'rb').read(); A = adapters.RvtAdapter(); assert A.source_damage(src) == []
    ss = 1 << struct.unpack_from('<H', src, 30)[0]; base = (struct.unpack_from('<I', src, 48)[0] + 1) * ss
    b = bytearray(src); b[base + j * 128:base + j * 128 + 128] = src[base + i * 128:base + i * 128 + 128]
    assert A.source_damage(bytes(b))
