"""c5x-rvtread2 item 187: a gated RVT save is refused up front, with a clear message, when the free RAM is far below the measured need (~56x file size); original untouched."""
import os, sys, shutil, pytest
import savegate as sg
from savegate import core
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(F), reason='no sample')

def _prep(tmp_path):
    import wledit
    f = str(tmp_path / 'a.rfa'); shutil.copy(F, f)
    ed = wledit.Editor(f); ed.set_strings([(7, 'FillPattern.m_name', 'Mem probe')]); o = f + '.o'; ed.save(o); new = open(o, 'rb').read(); os.remove(o)
    return f, new

def test_low_memory_refused_before_any_work(tmp_path, monkeypatch):
    f, new = _prep(tmp_path); src = open(f, 'rb').read()
    monkeypatch.setattr(core, '_available_memory', lambda: 10 << 20)       # 10 MB free
    with pytest.raises(sg.LowMemory) as ei: sg.save(sg.open_doc(f, None, sg.Config(allow_overwrite=True, require_gate=False)), new, {'modified': ['stream:Partitions/67', 'el:7']})
    assert 'not enough free memory' in str(ei.value) and sg.exit_code(ei.value) == 6
    assert open(f, 'rb').read() == src and os.listdir(tmp_path) == ['a.rfa']        # no temp copy, no backup, no lock

def test_enough_memory_saves(tmp_path, monkeypatch):
    f, new = _prep(tmp_path)
    monkeypatch.setattr(core, '_available_memory', lambda: 64 << 30)
    sg.save(sg.open_doc(f, None, sg.Config(allow_overwrite=True, require_gate=False)), new, {'modified': ['stream:Partitions/67', 'el:7']})
    assert open(f, 'rb').read() == new

def test_factor_zero_disables(tmp_path, monkeypatch):
    f, new = _prep(tmp_path)
    monkeypatch.setattr(core, '_available_memory', lambda: 1 << 20); monkeypatch.setenv('SAVEGATE_MEM_FACTOR', '0')
    sg.save(sg.open_doc(f, None, sg.Config(allow_overwrite=True, require_gate=False)), new, {'modified': ['stream:Partitions/67', 'el:7']})
    assert open(f, 'rb').read() == new

def test_available_memory_is_measured():
    a = core._available_memory(); assert a is None or a > 0
