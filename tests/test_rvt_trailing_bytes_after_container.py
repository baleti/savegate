"""c4x-rvtgap 365: bytes appended after the OLE container end (Autodesk 2024 rfa sample + 96 bytes) were DROPPED by the no-edit writer save and the gate accepted the shorter file.
Fixed: source_damage reports the tail, so the overwrite is refused and the original stays byte-identical."""
import os, sys, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))

def test_trailing_bytes_not_silently_dropped(tmp_path):
    SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
    if not os.path.exists(SRC): pytest.skip('no sample')
    import wledit, savegate as sg
    cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur); tail = b'TAILDATA' * 12
    open(cur, 'ab').write(tail); orig = open(cur, 'rb').read()
    o = str(tmp_path / 'o.rfa'); wledit.Editor(cur).save(o); new = open(o, 'rb').read()
    try: sg.save(sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False)), new, {'modified': []})
    except sg.SaveError: assert open(cur, 'rb').read() == orig; return
    assert open(cur, 'rb').read().endswith(tail)


def test_file_ending_mid_sector_is_not_a_tail(tmp_path):
    """real Revit files (88 of 6124 local) end inside the last sector of TransmissionData; that is not an appended tail (first version of the tail rule flagged 12 of them)."""
    SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
    if not os.path.exists(SRC): pytest.skip('no sample')
    from savegate.adapters import RvtAdapter
    b = open(SRC, 'rb').read()
    assert RvtAdapter._unreferenced_tail(b) == []
    assert RvtAdapter._unreferenced_tail(b[:-100]) == []
    assert RvtAdapter._unreferenced_tail(b + b'x' * 100) != []
