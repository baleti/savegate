"""c2x-rvtgap item 54: valid el:7 edit, but one byte flipped in a NON-declared stream of the OUTPUT (ElemTable, PartitionTable, ...). The gate must refuse and leave the original byte-identical."""
import os, sys, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no public sample')
STREAMS = ['Global/PartitionTable', 'Global/ElemTable', 'Global/Latest', 'Global/History', 'BasicFileInfo', 'Contents', 'PartAtom', 'RevitPreview4.0', 'Formats/Latest']


@pytest.mark.parametrize('stream', STREAMS)
def test_output_flip_in_undeclared_stream(tmp_path, stream):
    import savegate as sg, wledit, cfb
    good = open(SRC, 'rb').read(); c = cfb.CFB(good); st = c.streams()
    if stream not in st: pytest.skip('stream absent')
    e = st[stream]; ss = c.ss; fat = list(c.fat)
    mid = e.size // 2; s = e.start
    if e.size < c.cutoff:                       # mini stream: walk the miniFAT, then the root entry's sector chain
        for _ in range(mid // c.mss): s = c.minifat[s]
        mo = s * c.mss + mid % c.mss; r = c.entries[0].start
        for _ in range(mo // ss): r = fat[r]
        off = (r + 1) * ss + mo % ss
    else:
        for _ in range(mid // ss): s = fat[s]
        off = (s + 1) * ss + mid % ss
    ed = wledit.Editor(SRC); ed.set_strings([(7, 'FillPattern.m_name', 'Edited')])
    o = str(tmp_path / 'o.rfa'); ed.save(o); new = open(o, 'rb').read()
    cn = cfb.CFB(new); e = cn.streams()[stream]; ss = cn.ss; fat = list(cn.fat); mid = e.size // 2; s = e.start
    if e.size < cn.cutoff:
        for _ in range(mid // cn.mss): s = cn.minifat[s]
        mo = s * cn.mss + mid % cn.mss; r = cn.entries[0].start
        for _ in range(mo // ss): r = fat[r]
        off = (r + 1) * ss + mo % ss
    else:
        for _ in range(mid // ss): s = fat[s]
        off = (s + 1) * ss + mid % ss
    bad = bytearray(new); bad[off] ^= 0x01; bad = bytes(bad)
    assert [k for k, v in cfb.CFB(bad).streams().items() if v.data != cn.streams()[k].data] == [stream]
    cur = str(tmp_path / 'c.rfa'); open(cur, 'wb').write(good); 
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    with pytest.raises(sg.SaveError):
        sg.save(doc, bad, {'modified': ['stream:Partitions/67', 'el:7']})
    assert open(cur, 'rb').read() == good
