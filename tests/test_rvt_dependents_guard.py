"""c5x-rvtgap 76: move / resize / rotate of an element with dimensions, joined walls or hosted instances pointing at it is refused unless allow_dependents=true (public Autodesk Structural 2024 sample)."""
import os, sys, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research'))
from savegate import rvt_writer_ops as WO
SRC = os.path.expanduser('~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='sample missing')
WALL = 586803   # 26 FamilyInstance, 2 joined SWall, 2 LinearDimString referrers


@pytest.mark.parametrize('op', [{'op': 'move_element', 'dx': 1.0}, {'op': 'resize_wall', 'height': 14.0}, {'op': 'resize_wall', 'length_delta': 1.0}])
def test_wall_with_dependents_refused(op, tmp_path):
    with pytest.raises(ValueError, match='dependents the writer does not update'):
        WO.run(SRC, [dict(op, id=WALL)], str(tmp_path / 'o.rvt'))


def test_override_flag_passes_the_guard(tmp_path):
    out = str(tmp_path / 'o.rvt'); WO.run(SRC, [{'op': 'resize_wall', 'id': WALL, 'height': 14.0, 'allow_dependents': True}], out)
    assert os.path.getsize(out) == os.path.getsize(SRC)
