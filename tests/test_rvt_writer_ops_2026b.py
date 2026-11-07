"""c5x-rvtgap RVT-EDIT on the 2026 year (second batch): set_instance_type and delete_cascade on the Snowdon Structural 2026 project. (First batch: test_rvt_writer_ops_2026.py) The same writer ops as for 2024, on the Autodesk Snowdon Towers Structural 2026 project (same model, same element ids): move wall/grid/level/instance,
rotate instance, resize wall height and length, move text note, delete an unreferenced text note, add a text note. Each is run through the writer, accepted by the gate (recomputation, byte equality) and a
flipped bit in one of them is refused. Gate-level evidence only; Revit-VM verdict is separate."""
import os, sys, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/corpus/2026/55_Snowdon_Towers_Sample_Structural.rvt')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no Autodesk 2026 sample')
OPS = {
    'set_type': [{'op': 'set_instance_type', 'id': 730441, 'symbol': 666720}],
    'delete_cascade': [{'op': 'delete_cascade', 'id': 870670}],
}


def _gate(tmp_path, ops, flip=False):
    import savegate as sg
    from savegate import rvt_writer_ops as WO
    o = str(tmp_path / 'o.rvt'); ids = WO.run(SRC, ops, o); nb = bytearray(open(o, 'rb').read())
    if flip: nb[len(nb) // 2] ^= 1
    cur = str(tmp_path / 'c.rvt'); shutil.copy(SRC, cur); before = open(cur, 'rb').read()
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False, backup_keep=2))
    man = {'writer_ops': ops, 'added': ['el:%d' % i for i in ids], 'deleted': ['el:%d' % i for i in ([870669, 870670] if ops[0]['op'] == 'delete_cascade' else [])]}
    try: sg.save(doc, bytes(nb), man); ok = True
    except sg.SaveError: ok = False
    return ok, cur, before, bytes(nb), ids


@pytest.mark.parametrize('name', sorted(OPS))
def test_op_accepted_on_2026(tmp_path, name):
    ok, cur, before, nb, ids = _gate(tmp_path, OPS[name])
    assert ok and open(cur, 'rb').read() == nb and nb != before
