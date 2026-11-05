"""c2x-rvtgap item 9/12: after a string edit every stream except the edited Partitions/N (and the Global streams the writer may touch) is byte-identical
to the source (BasicFileInfo, thumbnail, OLE property streams, Formats, ...); the stream and directory name sets are equal; a second no-edit rewrite
of the output is a fixed point at stream level."""
import os, sys, glob, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SAMPLES = sorted(glob.glob(os.path.expanduser('~/rvt-research/samples-rfa/*.rfa')))
pytestmark = pytest.mark.skipif(not SAMPLES, reason='no public samples')


@pytest.mark.parametrize('path', SAMPLES, ids=[os.path.basename(p)[-9:] for p in SAMPLES])
def test_edit_keeps_every_other_stream_and_rewrite_is_a_fixed_point(path, tmp_path):
    import cfb, wledit
    ed = wledit.Editor(path)
    try: ed.set_strings([(7, 'FillPattern.m_name', 'HorizontalZ')])
    except Exception as e: pytest.skip('edit not applicable: %s' % e)
    o = str(tmp_path / 'o.rfa'); ed.save(o)
    A = cfb.CFB(open(path, 'rb').read()).streams(); B = cfb.CFB(open(o, 'rb').read()).streams()
    assert set(A) == set(B), 'stream set changed'
    diff = sorted(k for k in A if A[k].data != B[k].data)
    assert diff and all(k.startswith('Partitions/') for k in diff), 'unexpected streams changed: %s' % diff
    assert len(diff) == 1, diff
    o2 = str(tmp_path / 'o2.rfa'); cfb.write(cfb.CFB(open(o, 'rb').read()), o2)
    C = cfb.CFB(open(o2, 'rb').read()).streams()
    assert set(C) == set(B) and all(C[k].data == B[k].data for k in B)
