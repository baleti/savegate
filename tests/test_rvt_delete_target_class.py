"""c5x-rvtgap 83: delete_cascade refuses a target whose class is not user content (a GStyleElem has no inbound id references, so the planner alone accepted it)."""
import os, pytest
from savegate import rvt_writer_ops as WO
SRC = os.path.expanduser('~/rvt-research/corpus/2024/71_Construction-DefaultMetric.rte')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='sample missing')

def test_style_delete_refused():
    for eid in (277690, 75785):      # GStyleElem, unreferenced
        with pytest.raises(ValueError, match='not allowed'): WO.cascade_plan(SRC, eid)

def test_plain_delete_style_refused():
    tmp = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'tdc_plain.rte')
    for eid in (277690, 75785):
        with pytest.raises(ValueError, match='not allowed'): WO.run(SRC, [{'op': 'delete', 'id': eid}], tmp)

def _first(cls_name):
    import sys; sys.path.insert(0, os.path.expanduser('~/rvt-research')); import rvt_xcache
    return next(k[0] for k in rvt_xcache.get_x_ro(SRC)['recs'] if k[1] == cls_name)

@pytest.mark.parametrize('cls_name', ['SketchPlane', 'GStyleElem'])
def test_move_and_clone_of_types_and_sketch_planes_refused(cls_name, tmp_path):
    e = _first(cls_name)
    with pytest.raises(ValueError, match='not an element placed'): WO.run(SRC, [{'op': 'move_element', 'id': e, 'dx': 1.0}], str(tmp_path / 'm.rte'))
    if cls_name == 'SketchPlane':
        with pytest.raises(ValueError, match='not an element placed'): WO.run(SRC, [{'op': 'add_element', 'template': e, 'dy': 3.0}], str(tmp_path / 'a.rte'))

@pytest.mark.parametrize('cls_name', ['LeaderStyle', 'Viewport', 'DBDrawing', 'SunAndShadowSettings', 'PropertySetElement'])
def test_move_of_non_placed_classes_refused(cls_name, tmp_path):
    e = _first(cls_name)
    with pytest.raises(ValueError, match='not an element placed'): WO.run(SRC, [{'op': 'move_element', 'id': e, 'dx': 1.0}], str(tmp_path / 'm.rte'))
