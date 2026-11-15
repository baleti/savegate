"""c4x-rvtgap 365: bytes appended after the OLE container end (Autodesk 2024 rfa sample + 100 bytes) are DROPPED by the no-edit writer save and the gate
ACCEPTS the shorter file (data loss, original replaced). Expected safe behaviour: the tail is preserved or the save is refused. Currently fails (xfail strict)."""
import os, sys, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))

@pytest.mark.xfail(strict=True, reason='c4x-rvtgap 365: trailing bytes after the container are dropped and the gate accepts')
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
