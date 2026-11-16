"""c4x-rvtgap 502: the raw writer refuses a plain delete of an element other elements reference (it used to write a file with a dangling reference; only the gate caught it). Lab scene (local)."""
import os, pytest
SRC = os.path.expanduser('~/rvt-research/vg-scenes/2026_vg_link_target.rvt')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='lab scene missing')

@pytest.mark.parametrize('eid', [303694, 303699])
def test_referenced_refused(tmp_path, eid):
    from savegate import rvt_writer_ops as WO
    o = str(tmp_path / 'o.rvt')
    with pytest.raises(ValueError, match='dangling'): WO.run(SRC, [{'op': 'delete', 'id': eid}], o)
    assert not os.path.exists(o)

def test_unreferenced_textnote_still_deleted(tmp_path):
    from savegate import rvt_writer_ops as WO
    o = str(tmp_path / 'o.rvt'); WO.run(SRC, [{'op': 'delete', 'id': 303726}], o); assert os.path.exists(o)
