"""c4x-rvtgap: a host app that reuses the bytearray it passed to save() and mutates it while the call runs must not change what is written or reported: the committed file equals the bytes verified, the call succeeds."""
import os, sys, shutil, pytest
import savegate as sg
from savegate import core
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
@pytest.mark.parametrize('how', ['save', 'save_as'])
def test_mutation_during_call(tmp_path, monkeypatch, how):
    import wledit
    f = str(tmp_path / 'a.rfa'); shutil.copy(F, f)
    ed = wledit.Editor(f); ed.set_strings([(7, 'FillPattern.m_name', 'Buffer probe')]); o = str(tmp_path / 'o.tmp'); ed.save(o); new = open(o, 'rb').read(); os.remove(o)
    buf = bytearray(new); real = core._verify
    def evil(doc, back, manifest):
        r = real(doc, back, manifest); buf[len(buf) // 2] ^= 0xFF; return r      # caller reuses its buffer right after verification
    monkeypatch.setattr(core, '_verify', evil)
    doc = sg.open_doc(f, None, sg.Config(allow_overwrite=True, require_gate=False)); man = {'modified': ['stream:Partitions/67', 'el:7']}
    if how == 'save': r = sg.save(doc, buf, man); target = f
    else: target = str(tmp_path / 'copy.rfa'); r = sg.save_as(doc, buf, target, man)
    assert open(target, 'rb').read() == new, 'file does not equal the verified bytes'
