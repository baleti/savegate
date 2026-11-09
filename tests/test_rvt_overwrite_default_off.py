"""c4x-rvtgap: the shipped default Config() has allow_overwrite=False: in-place save() is refused with OverwriteDisabled for an RVT, nothing written, no backup, no debris."""
import os, sys, shutil, pytest
import savegate as sg
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
def test_default_config_refuses_inplace(tmp_path):
    import wledit
    f = str(tmp_path / 'a.rfa'); shutil.copy(F, f); raw = open(f, 'rb').read()
    ed = wledit.Editor(f); ed.set_strings([(7, 'FillPattern.m_name', 'Default off')]); o = str(tmp_path / 'o.tmp'); ed.save(o); new = open(o, 'rb').read(); os.remove(o)
    assert sg.Config().allow_overwrite is False
    doc = sg.open_doc(f, None, sg.Config())
    with pytest.raises(sg.OverwriteDisabled): sg.save(doc, new, {'modified': ['stream:Partitions/67', 'el:7']})
    assert open(f, 'rb').read() == raw and os.listdir(tmp_path) == ['a.rfa']
    # Save As to a NEW name is the supported path and works with the default config
    dst = str(tmp_path / 'copy.rfa'); sg.save_as(doc, new, dst, {'modified': ['stream:Partitions/67', 'el:7']}); assert open(dst, 'rb').read() == new
