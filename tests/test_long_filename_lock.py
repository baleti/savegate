"""c7x-rvtread2 199: a 240-char file name must be savable (lock file name derived from the name used to exceed the 255-byte limit)."""
import os, savegate as sg
from savegate.adapters import RawAdapter

def test_long_name_saves(tmp_path):
    p = str(tmp_path / ('x' * 240 + '.rvt')); orig = os.urandom(30000); open(p, 'wb').write(orig)
    doc = sg.open_doc(p, RawAdapter(), sg.Config(allow_overwrite=True, require_gate=False))
    sg.save(doc, b'N' * 40000, {'modified': ['file']})
    assert open(p, 'rb').read() == b'N' * 40000
    sg.restore(p); assert open(p, 'rb').read() == orig
