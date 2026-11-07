"""c5x-rvtgap RVT-EDIT rung 4: CHANGE the type of FamilyInstance 730441 (Autodesk Snowdon Towers Structural 2024) from symbol 667822 to 666720 (same family 982926) through the writer op set_instance_type:
FamilyInstance.m_masterSymbolId and the symbol id in the header lists change together. The gate recomputes the writer result (byte equality); a symbol of another family is refused by the writer; a flipped bit
is refused by the gate. The symbols' own instance lists are not updated (Revit-VM question)."""
import os, sys, struct, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt'); EL = 730441
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no Autodesk sample')
OPS = [{'op': 'set_instance_type', 'id': EL, 'symbol': 666720}]


def _go(tmp_path, flip=False):
    import savegate as sg
    from savegate import rvt_writer_ops as WO
    o = str(tmp_path / 'o.rvt'); WO.run(SRC, OPS, o); nb = bytearray(open(o, 'rb').read())
    if flip: nb[len(nb) // 2] ^= 1
    cur = str(tmp_path / 'c.rvt'); shutil.copy(SRC, cur); before = open(cur, 'rb').read()
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False, backup_keep=2))
    try: sg.save(doc, bytes(nb), {'writer_ops': OPS}); ok = True
    except sg.SaveError: ok = False
    return ok, cur, before, bytes(nb)


def test_type_change_accepted_and_reads_back(tmp_path):
    import wledit
    ok, cur, before, nb = _go(tmp_path); assert ok and open(cur, 'rb').read() == nb
    a = wledit.Editor(cur); t = a.trace(EL); b = a.m.parts[t[0]]['joined']; o = [x for x in t[3] if x[1] == 'FamilyInstance.m_masterSymbolId'][0]
    assert struct.unpack('<Q', b[o[2]:o[3]])[0] == 666720


def test_flipped_bit_refused(tmp_path):
    ok, cur, before, nb = _go(tmp_path, flip=True); assert not ok and open(cur, 'rb').read() == before


def test_symbol_of_another_family_is_refused_by_the_writer():
    from savegate import rvt_writer_ops as WO
    with pytest.raises(ValueError): WO.run(SRC, [{'op': 'set_instance_type', 'id': EL, 'symbol': 32567}], '/dev/null')
