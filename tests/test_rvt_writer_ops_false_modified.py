"""c4x-rvtgap 498: a writer_ops save whose manifest declares a modification of an element no operation targets is refused (the file was right, the declaration false). Lab scene only (local)."""
import os, shutil, pytest
import savegate as sg
from savegate.adapters import RvtAdapter
SRC = os.path.expanduser('~/rvt-research/vg-scenes/2026_vg_link_target.rvt')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='lab scene missing')

def _save(tmp_path, decl):
    from savegate import rvt_writer_ops as WO
    ops = [{'op': 'delete', 'id': 303726}]; o = str(tmp_path / 'o.rvt'); WO.run(SRC, ops, o); out = open(o, 'rb').read()
    cur = str(tmp_path / 'c.rvt'); shutil.copy(SRC, cur); before = open(cur, 'rb').read()
    doc = sg.open_doc(cur, RvtAdapter(), sg.Config(allow_overwrite=True, require_gate=False))
    try: sg.save(doc, out, dict(decl, writer_ops=ops)); return True
    except sg.SaveError: assert open(cur, 'rb').read() == before; return False

def test_good_accepted(tmp_path): assert _save(tmp_path, {'deleted': ['el:303726']})
def test_false_modified_refused(tmp_path): assert not _save(tmp_path, {'deleted': ['el:303726'], 'modified': ['el:303694']})
