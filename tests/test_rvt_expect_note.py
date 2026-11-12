"""c4x-rvtgap 346: an element edit declared without 'expect' is accepted but the report says field-level checking was off; with 'expect' there is no such note."""
import os, sys, struct, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no public sample')

def _save(tmp_path, expect):
    import wledit, savegate as sg
    ed = wledit.Editor(SRC); l = next(x for x in ed.trace(7)[3] if x[1] == 'FillPattern.m_scale'); pn = ed.trace(7)[0]
    ed.modify(7, [(l[2], 8, struct.pack('<d', 2.5))]); o = str(tmp_path / 'o.rfa'); ed.save(o)
    cur = str(tmp_path / 'cur.rfa'); shutil.copy(SRC, cur)
    man = {'modified': ['stream:' + pn, 'el:7']}
    if expect: man['expect'] = {7: {'FillPattern.m_scale': 2.5}}
    return sg.save(sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False)), open(o, 'rb').read(), man)

def _weak(r):
    return ' '.join(map(str, (r.report.get('weakened', []) if hasattr(r, 'report') and isinstance(r.report, dict) else getattr(r, 'weakened', []))))

def test_note_without_expect(tmp_path):
    r = _save(tmp_path, False); assert r.ok and 'without manifest[expect]' in _weak(r), (r, _weak(r))

def test_no_note_with_expect(tmp_path):
    r = _save(tmp_path, True); assert r.ok and 'without manifest[expect]' not in _weak(r)
