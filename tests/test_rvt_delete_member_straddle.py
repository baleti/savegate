"""c2x-rvtgap items 45-49: deleting an element whose record straddles a gzip member end (Autodesk Snowdon Electrical 2026, id 44139) must never yield a damaged file: either the writer refuses and leaves no output (current behaviour: 'edit straddles members'), or the output must carry no source damage. Slow (about 1 min)."""
import os, sys, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/corpus/2026/56_Snowdon_Towers_Sample_Electrical.rvt')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no Autodesk sample')


def test_member_straddling_delete_refused_or_clean(tmp_path):
    from savegate import rvt_writer_ops as WO
    from savegate.adapters import RvtAdapter
    out = str(tmp_path / 'o.rvt')
    try:
        WO.run(SRC, [{'op': 'delete_cascade', 'id': 44139}], out)
    except ValueError:
        assert not os.path.exists(out)
        return
    assert RvtAdapter().source_damage(open(out, 'rb').read()) == []
