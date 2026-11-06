"""c5x-rvtgap: an element whose SOURCE already holds a legitimate CRLF string (street/city text in 2 of 255714 local elements) must stay editable elsewhere;
only NEW control chars are refused. Fails without the narrowing of RvtAdapter._nonfinite_checks."""
import os, sys, struct, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no public sample')


def _src_with_crlf(tmp_path):
    import wledit
    ed = wledit.Editor(SRC); ed.set_strings([(7, 'FillPattern.m_name', 'a\r\nb')])
    o = str(tmp_path / 'src.rfa'); ed.save(o); return o


def _edit(path, out, scale=None, name=None):
    import wledit
    ed = wledit.Editor(path)
    if scale is not None:
        l = next(x for x in ed.trace(7)[3] if x[1] == 'FillPattern.m_scale'); ed.modify(7, [(l[2], 8, struct.pack('<d', scale))])
    if name is not None: ed.set_strings([(7, 'FillPattern.m_name', name)])
    ed.save(out); return open(out, 'rb').read()


def test_numeric_edit_next_to_existing_crlf_is_accepted(tmp_path):
    import savegate as sg
    src = _src_with_crlf(tmp_path); cur = str(tmp_path / 'c.rfa'); shutil.copy(src, cur)
    new = _edit(src, str(tmp_path / 'o.rfa'), scale=2.5)
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    sg.save(doc, new, {'modified': ['stream:Partitions/67', 'el:7']})
    assert open(cur, 'rb').read() == new


def test_new_control_char_next_to_existing_crlf_is_still_refused(tmp_path):
    import savegate as sg
    src = _src_with_crlf(tmp_path); cur = str(tmp_path / 'c.rfa'); shutil.copy(src, cur); before = open(cur, 'rb').read()
    new = _edit(src, str(tmp_path / 'o.rfa'), name='a\r\nb\x00')
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    with pytest.raises(sg.SaveError):
        sg.save(doc, new, {'modified': ['stream:Partitions/67', 'el:7']})
    assert open(cur, 'rb').read() == before
