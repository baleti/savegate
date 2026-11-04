"""c7x-rvtread2 102: header words that every Revit file has must be enforced by audit/gate (they passed olefile and source_damage)."""
import os, sys, struct, tempfile, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research')); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
CASES = {'major': (26, '<H', 3), 'minor': (24, '<H', 0), 'byteorder': (28, '<H', 0xFFFF), 'cutoff': (56, '<I', 8192), 'ndirsec': (40, '<I', 2)}

@pytest.mark.skipif(not os.path.exists(F), reason='public sample missing')
@pytest.mark.parametrize('k', sorted(CASES))
def test_header_word_mutation_flagged(k):
    R = pytest.importorskip('rvt_integrity'); from savegate import adapters
    b = bytearray(open(F, 'rb').read()); assert R.difat_problems(bytes(b)) == []
    o, f, v = CASES[k]; struct.pack_into(f, b, o, v)
    assert R.difat_problems(bytes(b)); assert adapters.RvtAdapter().source_damage(bytes(b))


def test_multi_sector_directory_not_false_positive():
    """c7x-rvtread2 142: files whose directory spans 2 sectors (header word 2) were flagged although intact (85/132 big local files, 2 public 2015 samples)."""
    import glob; R = pytest.importorskip('rvt_integrity')
    fs = glob.glob(os.path.expanduser('~/rvt-research/samples*/2015_1_*.rvt'))
    if not fs: pytest.skip('public 2015 sample missing')
    b = bytearray(open(fs[0], 'rb').read()); assert struct.unpack_from('<I', b, 40)[0] == 2
    assert R.difat_problems(bytes(b)) == []
    struct.pack_into('<I', b, 40, 3); assert R.difat_problems(bytes(b))     # wrong count is still damage
    struct.pack_into('<I', b, 40, 1); assert R.difat_problems(bytes(b))
