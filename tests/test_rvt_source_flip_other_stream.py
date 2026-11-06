"""c2x-rvtgap item 43: one flipped byte in a NON-edited stream of the SOURCE. In-place save must refuse, or else keep every other stream exactly as the (damaged) source had it: never silently rewrite or 'repair' data it was not asked to touch."""
import os, sys, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no public sample')
STREAMS = ['Global/PartitionTable', 'Global/ElemTable', 'Global/Latest', 'Global/History', 'BasicFileInfo', 'Contents', 'PartAtom', 'RevitPreview4.0', 'Formats/Latest']


@pytest.mark.parametrize('stream', STREAMS)
def test_source_flip_in_untouched_stream(tmp_path, stream):
    import savegate as sg, wledit, cfb
    good = open(SRC, 'rb').read(); c = cfb.CFB(good); st = c.streams()
    if stream not in st: pytest.skip('stream absent')
    e = st[stream]; ss = c.ss; fat = list(c.fat)
    mid = e.size // 2; s = e.start
    if e.size < c.cutoff: pytest.skip('mini stream')
    for _ in range(mid // ss): s = fat[s]
    off = (s + 1) * ss + mid % ss
    bad = bytearray(good); bad[off] ^= 0x01; bad = bytes(bad)
    ed = wledit.Editor(SRC); ed.set_strings([(7, 'FillPattern.m_name', 'Edited')])
    o = str(tmp_path / 'o.rfa'); ed.save(o); new = open(o, 'rb').read()
    cur = str(tmp_path / 'c.rfa'); open(cur, 'wb').write(bad)
    try:
        doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
        sg.save(doc, new, {'modified': ['stream:Partitions/67', 'el:7']})
    except Exception:
        assert open(cur, 'rb').read() == bad; return
    A = cfb.CFB(bad).streams(); B = cfb.CFB(open(cur, 'rb').read()).streams()
    assert [k for k in A if k not in B or A[k].data != B[k].data] == ['Partitions/67'], 'save changed streams it was not asked to touch'
