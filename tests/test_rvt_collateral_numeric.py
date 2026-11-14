"""c5x-rvtread2 items 264/266: a declared string edit plus an UNDECLARED numeric change in another element (double +1.0, int32 +1) with valid framing and
checksums must be refused by the gate and leave the original untouched (public 2024 family only). Passed on HEAD when written (no escape found)."""
import os, sys, shutil, struct, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no public sample')


def _find(ed, width, ok, skip):
    for e in sorted(ed.m.ids):
        if e == skip: continue
        try: t = ed.trace(e)
        except Exception: continue
        for x in t[3]:
            if x[3] - x[2] == width and isinstance(x[4], str) and ok(x[4]): return e, x[2], x[4]
    return None


@pytest.mark.parametrize('kind', ['double', 'int32'])
def test_undeclared_numeric_change_is_refused(tmp_path, kind):
    import savegate as sg, wledit
    base = wledit.Editor(SRC)
    tgt = next((e for e in sorted(base.m.ids) if e < 3 and any(x[1] == 'ForgeTypeId.m_typeId' and isinstance(x[4], str) and x[3] - x[2] >= 6 for x in (base.trace(e)[3] if e in base.m.ids else []))), None)
    if kind == 'double': hit = _find(base, 8, lambda v: '.' in v and v.replace('.', '', 1).replace('-', '', 1).isdigit(), tgt)
    else: hit = _find(base, 4, lambda v: v.lstrip('-').isdigit(), tgt)
    if tgt is None or hit is None: pytest.skip('no suitable fields')
    de, off, val = hit; ed = wledit.Editor(SRC)
    ed.modify(de, [(off, 8 if kind == 'double' else 4, struct.pack('<d', float(val) + 1.0) if kind == 'double' else struct.pack('<i', int(val) + 1))])
    ed.set_strings([(tgt, 'ForgeTypeId.m_typeId', 'Template probe')])
    o = str(tmp_path / 'o.rfa'); ed.save(o); new = open(o, 'rb').read()
    cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur); before = open(cur, 'rb').read()
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    with pytest.raises(sg.SaveError):
        sg.save(doc, new, {'modified': ['el:%d' % tgt]})
    assert open(cur, 'rb').read() == before
