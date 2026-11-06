"""c7x-rvtread2 item 242: in-place overwrite with verify=False and require_gate=False must not write a truncated RVT (today it does: expected failure until fixed)."""
import os, shutil, pytest
import savegate as sg
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='public Autodesk 2024 family sample not present')

def test_verify_off_still_refuses_truncated(tmp_path):
    t = str(tmp_path / 'x.rfa'); shutil.copy(SRC, t); old = open(t, 'rb').read()
    cfg = sg.Config(allow_overwrite=True, require_gate=False)
    try: sg.save(sg.open_doc(t, None, cfg), old[:len(old) // 2], {'modified': ['el:7']}, verify=False)
    except Exception: pass
    assert open(t, 'rb').read() == old, 'a truncated file replaced the original'
