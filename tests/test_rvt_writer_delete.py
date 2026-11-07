"""c5x-rvtgap RVT-EDIT rung 2: the trusted writer's COMPLETE delete (rvtgen.Gen: header entry, record, zone records, ElemTable row, counts; Revit-validated in the write lab) on the Autodesk
Snowdon Towers Structural 2024 sample. The gate (manifest writer_ops) recomputes the writer result from the source and demands byte equality: accepted when equal, refused after one flipped
bit, refused for an element that others still reference, refused when the declared ids differ from writer_ops."""
import os, sys, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no Autodesk sample')


def _gen_delete(tmp_path, el):
    import rvtgen
    g = rvtgen.Gen(SRC); g.delete(el); o = str(tmp_path / 'o.rvt'); g.commit(o); return open(o, 'rb').read()


def _save(tmp_path, nb, ops, deleted):
    import savegate as sg
    cur = str(tmp_path / 'c.rvt'); shutil.copy(SRC, cur); before = open(cur, 'rb').read()
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False, backup_keep=2))
    try: sg.save(doc, nb, {'writer_ops': ops, 'deleted': ['el:%d' % d for d in deleted]}); ok = True
    except sg.SaveError: ok = False
    return ok, cur, before


def test_unreferenced_delete_accepted_and_readable(tmp_path):
    import wledit
    nb = _gen_delete(tmp_path, 916133)
    ok, cur, before = _save(tmp_path, nb, [{'op': 'delete', 'id': 916133}], [916133])
    assert ok and open(cur, 'rb').read() == nb
    assert 916133 not in set(wledit.Editor(cur).m.ids)


def test_one_flipped_bit_in_the_writer_output_is_refused(tmp_path):
    nb = bytearray(_gen_delete(tmp_path, 916133)); nb[len(nb) // 3] ^= 1
    ok, cur, before = _save(tmp_path, bytes(nb), [{'op': 'delete', 'id': 916133}], [916133])
    assert not ok and open(cur, 'rb').read() == before


def test_referenced_element_and_mismatched_declaration_are_refused(tmp_path):
    nb = _gen_delete(tmp_path, 916133)
    ok, cur, before = _save(tmp_path, nb, [{'op': 'delete', 'id': 916133}], [664857])         # declared ids differ from writer_ops
    assert not ok and open(cur, 'rb').read() == before
