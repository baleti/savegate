"""c5x-rvtgap item 80: a no-edit save whose bytes differ from the source in ONE metadata stream (flip or truncation by one byte) must be refused and leave the original byte-identical (2024 and 2026 public sample)."""
import os, sys, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
STREAMS = ['RevitPreview4.0', 'BasicFileInfo', 'PartAtom', 'TransmissionData', 'Contents']


@pytest.mark.parametrize('how', ['flip', 'cut'])
@pytest.mark.parametrize('stream', STREAMS)
@pytest.mark.parametrize('year', ['2024', '2026'])
def test_undeclared_metadata_stream_change_refused(tmp_path, year, stream, how):
    import savegate as sg, cfb
    src = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-%s.rfa' % year)
    if not os.path.exists(src): pytest.skip('no public sample')
    good = open(src, 'rb').read(); c = cfb.CFB(good); t = None
    for x in c.entries:
        if x.type == 2: x.data = bytes(x.data)
        if x.name == stream: t = x
    if t is None or len(t.data) < 20: pytest.skip('stream absent')
    d = bytearray(t.data)
    if how == 'flip': d[len(d) // 2] ^= 1
    else: d = d[:-1]
    t.data = bytes(d); o = str(tmp_path / 'o.rfa'); cfb.write(c, o); new = open(o, 'rb').read()
    assert new != good
    cur = str(tmp_path / 'c.rfa'); open(cur, 'wb').write(good)
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    with pytest.raises(sg.SaveError) as ei:
        sg.save(doc, new, {})
    print(year, stream, how, str(ei.value)[:120])
    assert open(cur, 'rb').read() == good
