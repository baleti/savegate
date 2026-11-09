"""c4x-rvtgap: read-only files: save refused (untouched, no debris) unless allow_readonly, which keeps the RO bit; restore() of a read-only file is refused unless allowed."""
import os, sys, shutil, stat, pytest
import savegate as sg
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = [pytest.mark.skipif(not os.path.exists(F), reason='no sample'), pytest.mark.skipif(os.geteuid() == 0, reason='root ignores modes')]
def mode(p): return stat.S_IMODE(os.stat(p).st_mode)
def _edit(tmp_path, f):
    import wledit
    ed = wledit.Editor(f); ed.set_strings([(7, 'FillPattern.m_name', 'RO probe')]); o = str(tmp_path / 'o.tmp'); ed.save(o); b = open(o, 'rb').read(); os.remove(o); return b
MAN = {'modified': ['stream:Partitions/67', 'el:7']}
def test_save_refused_when_readonly(tmp_path):
    f = str(tmp_path / 'a.rfa'); shutil.copy(F, f); new = _edit(tmp_path, f); raw = open(f, 'rb').read(); os.chmod(f, 0o444)
    doc = sg.open_doc(f, None, sg.Config(allow_overwrite=True, require_gate=False))
    with pytest.raises(sg.ReadOnlyTarget): sg.save(doc, new, MAN)
    assert open(f, 'rb').read() == raw and mode(f) == 0o444 and os.listdir(tmp_path) == ['a.rfa']
def test_save_allowed_keeps_readonly_bit(tmp_path):
    f = str(tmp_path / 'a.rfa'); shutil.copy(F, f); new = _edit(tmp_path, f); os.chmod(f, 0o444)
    doc = sg.open_doc(f, None, sg.Config(allow_overwrite=True, require_gate=False, allow_readonly=True))
    sg.save(doc, new, MAN); assert open(f, 'rb').read() == new and mode(f) == 0o444
def test_restore_refused_when_readonly(tmp_path):
    f = str(tmp_path / 'a.rfa'); shutil.copy(F, f); new = _edit(tmp_path, f); raw = open(f, 'rb').read()
    doc = sg.open_doc(f, None, sg.Config(allow_overwrite=True, require_gate=False)); sg.save(doc, new, MAN); os.chmod(f, 0o444)
    with pytest.raises(sg.ReadOnlyTarget): sg.restore(f)
    assert open(f, 'rb').read() == new and mode(f) == 0o444
    sg.restore(f, allow_readonly=True); assert open(f, 'rb').read() == raw and mode(f) == 0o444
