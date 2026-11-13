"""c5x-rvtgap 83: delete_cascade refuses a target whose class is not user content (a GStyleElem has no inbound id references, so the planner alone accepted it)."""
import os, pytest
from savegate import rvt_writer_ops as WO
SRC = os.path.expanduser('~/rvt-research/corpus/2024/71_Construction-DefaultMetric.rte')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='sample missing')

def test_style_delete_refused():
    for eid in (277690, 75785):      # GStyleElem, unreferenced
        with pytest.raises(ValueError, match='not allowed'): WO.cascade_plan(SRC, eid)
