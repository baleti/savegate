"""c2x-rvtgap item 19: a same-size numeric (double) field edit through Editor.modify: value reads back bit-exact for ordinary, signed-zero, denormal and huge values;
container valid, one stream differs. NaN/inf: recorded as accepted by the writer (the gate's value sanity rule, not the editor, is the barrier)."""
import os, sys, struct, math, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no public sample')
VALUES = [2.5, -0.0, 5e-324, 1e300, -1.0, 0.1]


def _edit(tmp_path, v):
    import wledit
    ed = wledit.Editor(SRC); l = next(x for x in ed.trace(7)[3] if x[1] == 'FillPattern.m_scale')
    ed.modify(7, [(l[2], 8, struct.pack('<d', v))])
    o = str(tmp_path / 'o.rfa'); ed.save(o); return o


@pytest.mark.parametrize('v', VALUES)
def test_double_field_roundtrip_bit_exact(tmp_path, v):
    import wledit, cfb
    from savegate.adapters import RvtAdapter
    o = _edit(tmp_path, v); b = open(o, 'rb').read(); a = RvtAdapter()
    assert not a.source_damage(b); a.validate(b)
    got = wledit.Editor(o).trace(7)[2]['fields']['m_pFillPattern']['obj']['m_scale']
    assert struct.pack('<d', got) == struct.pack('<d', v), (v, got)
    A = cfb.CFB(open(SRC, 'rb').read()).streams(); B = cfb.CFB(b).streams()
    assert [k for k in A if A[k].data != B[k].data] == ['Partitions/67']
    # the neighbouring fields of the same element are unchanged
    f0 = wledit.Editor(SRC).trace(7)[2]['fields']['m_pFillPattern']['obj']; f1 = wledit.Editor(o).trace(7)[2]['fields']['m_pFillPattern']['obj']
    assert f0['m_windowSize'] == f1['m_windowSize'] and f0['m_name'] == f1['m_name']


@pytest.mark.parametrize('v', [float('nan'), float('inf')])
def test_nonfinite_double_is_written_by_the_editor_gate_must_stop_it(tmp_path, v):
    """documents the gap: the RVT editor itself does not refuse NaN/inf (unlike the DWG Editor fix); only the gate's wild-value rule or the UI can"""
    import wledit
    o = _edit(tmp_path, v)
    got = wledit.Editor(o).trace(7)[2]['fields']['m_pFillPattern']['obj']['m_scale']
    assert math.isnan(got) or math.isinf(got)


@pytest.mark.parametrize('v', [float('nan'), float('inf'), -float('inf')])
def test_gate_refuses_nonfinite_number_in_a_declared_element(tmp_path, v):
    import savegate as sg, shutil
    o = _edit(tmp_path, v); new = open(o, 'rb').read(); cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur); before = open(cur, 'rb').read()
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    with pytest.raises(sg.SaveError):
        sg.save(doc, new, {'modified': ['stream:Partitions/67', 'el:7']})
    assert open(cur, 'rb').read() == before


def test_gate_still_accepts_a_finite_declared_numeric_edit(tmp_path):
    import savegate as sg, shutil
    o = _edit(tmp_path, 2.5); new = open(o, 'rb').read(); cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur)
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    sg.save(doc, new, {'modified': ['stream:Partitions/67', 'el:7']})
    assert open(cur, 'rb').read() == new
