"""c7x-rvtread2 602: a valid declared edit (el:7 renamed) whose payload ALSO changes one metadata stream (flip or cut by one byte) is refused, original byte-identical;
control: the edit alone is accepted (so the refusal is caused by the metadata change). 2024 and 2026 Autodesk sample families."""
import os, sys, shutil, pytest
import savegate as sg
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
R = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-%s.rfa')
STREAMS = ['RevitPreview4.0', 'BasicFileInfo', 'PartAtom', 'TransmissionData', 'Contents']
@pytest.mark.parametrize('how', ['flip', 'cut'])
@pytest.mark.parametrize('stream', STREAMS)
@pytest.mark.parametrize('year', ['2024', '2026'])
def test_edit_plus_metadata(tmp_path, year, stream, how):
    import wledit, cfb
    src = R % year
    if not os.path.exists(src): pytest.skip('no public sample')
    cur = str(tmp_path / 'c.rfa'); shutil.copy(src, cur); before = open(cur, 'rb').read()
    ed = wledit.Editor(cur); pn = ed.trace(7)[0]; ed.set_strings([(7, 'FillPattern.m_name', 'Edit plus meta')])
    o = str(tmp_path / 'o.rfa'); ed.save(o); good_new = open(o, 'rb').read()
    c = cfb.CFB(good_new); t = None
    for x in c.entries:
        if x.type == 2: x.data = bytes(x.data)
        if x.name == stream: t = x
    if t is None or len(t.data) < 20: pytest.skip('stream absent')
    d = bytearray(t.data)
    if how == 'flip': d[len(d) // 2] ^= 1
    else: d = d[:-1]
    t.data = bytes(d); cfb.write(c, o); bad = open(o, 'rb').read(); assert bad != good_new
    man = {'modified': ['stream:' + pn, 'el:7']}
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    with pytest.raises(sg.SaveError) as ei: sg.save(doc, bad, man)
    assert type(ei.value).__name__ not in ('GateClosed', 'LowMemory')
    print(year, stream, how, type(ei.value).__name__, str(ei.value)[:110])
    assert open(cur, 'rb').read() == before
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    sg.save(doc, good_new, man); assert open(cur, 'rb').read() == good_new
