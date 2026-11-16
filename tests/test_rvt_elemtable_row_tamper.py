"""c4x-rvtgap 563: a +1 in a field of an ElemTable row of an element nobody declared was ACCEPTED (19 of 28 variants). Now refused (elemtable_row_changed); real delete / add_instance / delete+add / move are still accepted."""
import os, shutil, sys, pytest
sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
import cfb, rvtw
import savegate as sg
from savegate import rvt_writer_ops as WO
SRC = os.path.expanduser('~/rvt-research/vg-scenes/2026_vg_link_target.rvt')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='lab scene missing')


def _doc(p): return sg.open_doc(str(p), None, sg.Config(allow_overwrite=True, require_gate=False))


def _tamper(data, row, off, tmp):
    c = cfb.CFB(data); e = c.streams()['Global/ElemTable']; st = rvtw.Stream(e.data); P = st.payload
    pos = P.find(rvtw.GZ); raw, end = rvtw.read_member(P, pos); raw = bytearray(raw); raw[6 + row * 40 + off] = (raw[6 + row * 40 + off] + 1) & 255
    m = rvtw.gz_member(bytes(raw), P[pos:pos + 10], target_deflate_len=end - pos - 10 - 8); assert len(m) == end - pos
    e.data = st.build(P[:pos] + m + P[end:]); o = str(tmp / 't.rvt'); cfb.write(c, o); return open(o, 'rb').read()


@pytest.mark.parametrize('row,off', [(0, 12), (2500, 16), (5750, 24)])
def test_row_field_tamper_refused(tmp_path, row, off):
    p = tmp_path / 'a.rvt'; shutil.copy(SRC, p); orig = p.read_bytes()
    bad = _tamper(orig, row, off, tmp_path)
    with pytest.raises(sg.SaveError) as ei: sg.save(_doc(p), bad, {'modified': ['stream:Global/ElemTable']})
    assert 'elemtable_row_changed' in str(ei.value) and p.read_bytes() == orig


@pytest.mark.parametrize('ops,man', [
    ([{'op': 'delete', 'id': 303726}], {'deleted': ['el:303726']}),
    ([{'op': 'add_instance', 'template': 303694, 'dx': 1.0, 'dy': 0.5}], {'added': ['el:303728']}),
    ([{'op': 'delete', 'id': 303726}, {'op': 'add_instance', 'template': 303694, 'dx': 1.0, 'dy': 0.5}], {'deleted': ['el:303726'], 'added': ['el:303728']}),
    ([{'op': 'move_textnote', 'id': 303726, 'dx': 1.0, 'dy': 0.5}], {'modified': ['el:303726']}),
])
def test_real_edits_still_accepted(tmp_path, ops, man):
    p = tmp_path / 'a.rvt'; shutil.copy(SRC, p); orig = p.read_bytes(); o = str(tmp_path / 'o.rvt'); WO.run(SRC, ops, o)
    sg.save(_doc(p), open(o, 'rb').read(), dict(man, writer_ops=ops)); assert p.read_bytes() != orig
