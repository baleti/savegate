"""c5x-rvtgap item 28 (SEV1 candidate): a declared edit that rewrites an ElementId reference to a NONEXISTENT id was accepted (193 of 198 tries on the 2024 public family).
The gate must refuse it; pointing the reference at another EXISTING element stays allowed."""
import os, sys, struct, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no public sample')


def _target():
    import wledit
    base = wledit.Editor(SRC); ids = set(base.m.ids)
    for e in sorted(ids):
        try: t = base.trace(e)[3]
        except Exception: continue
        l = [x for x in t if x[0] == 5 and x[1] == 'Identifier.m_id64' and x[3] - x[2] == 8 and x[4].isdigit() and int(x[4]) in ids and int(x[4]) != e]
        if l: return e, l[0], ids
    raise RuntimeError('no reference found')


def _save(tmp_path, newid):
    import savegate as sg, wledit
    e, l, ids = _target()
    ed = wledit.Editor(SRC); ed.modify(e, [(l[2], 8, struct.pack('<Q', newid))]); o = str(tmp_path / 'o.rfa'); ed.save(o); new = open(o, 'rb').read()
    cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur); before = open(cur, 'rb').read()
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    try: sg.save(doc, new, {'modified': ['stream:Partitions/67', 'el:%d' % e]}); ok = True
    except sg.SaveError: ok = False
    return ok, cur, before, new


def test_reference_to_nonexistent_id_is_refused(tmp_path):
    ok, cur, before, new = _save(tmp_path, 0x7ffffff0)
    assert not ok and open(cur, 'rb').read() == before


def test_reference_to_other_existing_id_is_accepted(tmp_path):
    e, l, ids = _target()
    other = next(i for i in sorted(ids) if i not in (e, int(l[4])))
    ok, cur, before, new = _save(tmp_path, other)
    assert ok and open(cur, 'rb').read() == new
