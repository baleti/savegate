"""c2x-rvtgap item 7 side finding: wledit._check_wstr accepts a string edit on a pointer field whose empty value logs as 'None' (Element.m_pParamValueSetDouble of el:15,
a record at a gzip member boundary). The EDITOR writes the wrong-typed bytes; the GATE must refuse and leave the original untouched."""
import os, sys, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no public sample')


def test_gate_refuses_string_written_into_pointer_field(tmp_path):
    import savegate as sg, wledit
    t = str(tmp_path / 'x.rfa'); shutil.copy(SRC, t); old = open(t, 'rb').read()
    ed = wledit.Editor(t)
    try: ed.set_strings([(15, 'Element.m_pParamValueSetDouble', 'Hello')])
    except ValueError: return            # editor tightened later: also fine
    o = str(tmp_path / 'o.rfa'); ed.save(o); new = open(o, 'rb').read()
    doc = sg.open_doc(t, None, sg.Config(allow_overwrite=True, require_gate=False))
    with pytest.raises(sg.SaveError): sg.save(doc, new, {'modified': ['stream:Partitions/67', 'el:15']})
    assert open(t, 'rb').read() == old
