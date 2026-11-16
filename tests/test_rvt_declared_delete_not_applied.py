"""c4x-rvtgap 555: a no-op output with a manifest that declares a deletion was ACCEPTED (the declared element still resolved). Now refused (delete_not_applied); a real delete is still accepted."""
import os, shutil, sys, pytest
sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
import savegate as sg
from savegate import rvt_writer_ops as WO
SRC = os.path.expanduser('~/rvt-research/vg-scenes/2026_vg_link_target.rvt')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='lab scene missing')


def _doc(p): return sg.open_doc(str(p), None, sg.Config(allow_overwrite=True, require_gate=False))


def test_declared_delete_without_change_refused_real_delete_accepted(tmp_path):
    p = tmp_path / 'a.rvt'; shutil.copy(SRC, p); orig = p.read_bytes()
    with pytest.raises(sg.SaveError) as ei: sg.save(_doc(p), orig, {'deleted': ['el:303726']})
    assert 'delete_not_applied' in str(ei.value) and p.read_bytes() == orig
    ops = [{'op': 'delete', 'id': 303726}]; o = str(tmp_path / 'o.rvt'); WO.run(SRC, ops, o)
    sg.save(_doc(p), open(o, 'rb').read(), {'writer_ops': ops, 'deleted': ['el:303726']})
    assert p.read_bytes() != orig
