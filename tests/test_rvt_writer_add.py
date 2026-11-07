"""c5x-rvtgap RVT-EDIT rung 3: ADD a TextNote (clone of an existing rich-text-only note, new id, position and text) to the Autodesk Snowdon Towers Structural 2024 project through the trusted writer
(rvt_writer_ops). The gate recomputes the writer result and demands byte equality; the new element is registered in the ElemTable, decodes with the requested position, and carries the text in its
rich-text stream. A flipped bit, a wrong declared id and a changed text are refused. Local gate-level checks; Revit-VM verdict is separate."""
import os, sys, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no Autodesk sample')
OPS = [{'op': 'add_textnote', 'template': 916133, 'x': -60.0, 'y': 20.0, 'text': 'ADDED BY SAVEGATE'}]


def _make(tmp_path, ops=OPS):
    from savegate import rvt_writer_ops as WO
    o = str(tmp_path / 'o.rvt'); ids = WO.run(SRC, ops, o); return ids, open(o, 'rb').read()


def _save(tmp_path, nb, ops, added):
    import savegate as sg
    cur = str(tmp_path / 'c.rvt'); shutil.copy(SRC, cur); before = open(cur, 'rb').read()
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False, backup_keep=2))
    try: sg.save(doc, nb, {'writer_ops': ops, 'added': ['el:%d' % a for a in added]}); ok = True
    except sg.SaveError: ok = False
    return ok, cur, before


def test_add_textnote_accepted_registered_and_readable(tmp_path):
    import wledit
    ids, nb = _make(tmp_path); assert len(ids) == 1
    ok, cur, before = _save(tmp_path, nb, OPS, ids)
    assert ok and open(cur, 'rb').read() == nb
    a = wledit.Editor(cur); assert ids[0] in set(a.m.ids)
    t = a.trace(ids[0]); b = a.m.parts[t[0]]['joined']
    import struct
    o = [x for x in t[3] if x[1] == 'TextElement.m_orig'][0]; assert struct.unpack('<3d', b[o[2]:o[3]]) == (-60.0, 20.0, 0.0)
    r = [x for x in t[3] if x[1] == 'RtfData.m_arrRtfStream'][0]; assert b'ADDED BY SAVEGATE' in b[r[2]:r[3]]


def test_flipped_bit_wrong_declaration_and_other_text_are_refused(tmp_path):
    ids, nb = _make(tmp_path); bad = bytearray(nb); bad[len(bad) // 2] ^= 1
    ok, cur, before = _save(tmp_path, bytes(bad), OPS, ids); assert not ok and open(cur, 'rb').read() == before
    ok, cur, before = _save(tmp_path, nb, OPS, [ids[0] + 5]); assert not ok and open(cur, 'rb').read() == before
    other = [dict(OPS[0], text='SOMETHING ELSE')]; ids2, nb2 = _make(tmp_path / 'x' if False else tmp_path, other)
    ok, cur, before = _save(tmp_path, nb2, OPS, ids); assert not ok and open(cur, 'rb').read() == before
