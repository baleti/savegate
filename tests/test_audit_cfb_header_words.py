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
