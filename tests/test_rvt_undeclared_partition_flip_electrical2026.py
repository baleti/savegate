"""c4x-rvtgap item 457 SEV1: valid same-length string edit of el:669049 (Partitions/38) plus ONE bit flip in a different, undeclared partition (Partitions/41 at 133718 and 6303772, id/table
bytes the element view does not decode): the default gate ACCEPTED it before the fix; it must refuse and leave the original byte-identical. Slow (minutes), ~1.5 GB."""
import os, sys, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/corpus/2026/56_Snowdon_Towers_Sample_Electrical.rvt')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no Autodesk sample')
E = 669049


@pytest.mark.parametrize('flip', [None, ('Partitions/41', 133718), ('Partitions/41', 6303772)])
def test_flip_in_undeclared_partition_refused(tmp_path, flip):
    import savegate as sg, wledit
    A = wledit.Editor(SRC); pn, i, r, log, q = A.trace(E)
    f = [x for x in log if isinstance(x[4], str) and len(x[4]) >= 3 and x[3] - x[2] == 4 + 2 * len(x[4]) and '\x00' not in x[4]][0]; del A
    ed = wledit.Editor(SRC); new = f[4][:-1] + ('Y' if f[4][-1] != 'Y' else 'Z'); ed.set_strings([(E, f[1], new, f[4])])
    if flip:
        p, off = flip; b = ed.m.parts[p]['joined']; ed.part(p).replace(off, 1, bytes([b[off] ^ 1]))
    o = str(tmp_path / 'o.rvt'); ed.save(o); del ed; nb = open(o, 'rb').read()
    cur = str(tmp_path / 'c.rvt'); shutil.copy(SRC, cur); orig = open(cur, 'rb').read()
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False, journal_dir=str(tmp_path / 'j')))
    if flip is None:
        sg.save(doc, nb, {'modified': ['el:%d' % E]}); return
    with pytest.raises(sg.SaveError): sg.save(doc, nb, {'modified': ['el:%d' % E]})
    assert open(cur, 'rb').read() == orig
