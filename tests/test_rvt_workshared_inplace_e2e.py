"""c4x-rvtgap: end to end: honest edit of a workshared (Central/Local) model: in-place sg.save refused with the reason and the original byte-identical; save_as to a new path still allowed."""
import os, sys, shutil, pytest
import savegate as sg
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
@pytest.mark.parametrize('v', ['Central', 'Local'])
def test_inplace_refused_saveas_allowed(tmp_path, v):
    import cfb, wledit
    c = cfb.CFB(open(F, 'rb').read()); e = c.streams()['BasicFileInfo']; OLD = 'Not enabled'
    e.data = e.data.replace(('Worksharing: ' + OLD).encode('utf-16le'), ('Worksharing: ' + v.ljust(len(OLD))).encode('utf-16le'), 1)
    ws = str(tmp_path / 'ws.rfa'); cfb.write(c, ws); before = open(ws, 'rb').read()
    ed = wledit.Editor(ws); ed.set_strings([(7, 'FillPattern.m_name', 'Edited')]); o = str(tmp_path / 'o.rfa'); ed.save(o); out = open(o, 'rb').read()
    man = {'modified': ['stream:Partitions/67', 'el:7']}
    doc = sg.open_doc(ws, None, sg.Config(allow_overwrite=True, require_gate=False))
    with pytest.raises(sg.SaveError) as ei: sg.save(doc, out, man)
    assert 'workshared' in str(ei.value).lower() or 'worksharing' in str(ei.value).lower(), str(ei.value)
    assert open(ws, 'rb').read() == before
    dst = str(tmp_path / 'copy.rfa'); r = sg.save_as(doc, out, dst, man); assert os.path.exists(dst) and open(dst, 'rb').read() == out
    assert open(ws, 'rb').read() == before
