"""c7x-rvtread2 item 499: add_element/add_instance with an all-zero offset would stack an exact duplicate on the template; the writer must refuse it
(fails without the zero-offset check in rvt_writer_ops.run), a non-zero offset must still be accepted. Autodesk 2024 template (public sample)."""
import os, sys, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/corpus/2024/71_Construction-DefaultMetric.rte')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no Autodesk sample')


@pytest.mark.parametrize('kw', [{}, {'dx': 0, 'dy': 0.0, 'dz': 0}])
def test_zero_offset_refused(tmp_path, kw):
    from savegate import rvt_writer_ops as WO
    out = str(tmp_path / 'o.rte')
    with pytest.raises(ValueError, match='all-zero offset'):
        WO.run(SRC, [dict(op='add_element', template=29795, **kw)], out)
    assert not os.path.exists(out)


def test_nonzero_offset_accepted(tmp_path):
    from savegate import rvt_writer_ops as WO
    out = str(tmp_path / 'o.rte')
    assert len(WO.run(SRC, [dict(op='add_element', template=29795, dy=3.0)], out)) == 1
