"""c2x-rvtgap item 10 (+9): after a string edit the 10-byte gzip header (magic, method, flags, mtime, xfl, OS) of every member of the edited partition equals the
source's, member count is unchanged, and BasicFileInfo / RevitPreview4.0 / other non-partition streams are byte-identical."""
import os, sys, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
D = os.path.expanduser('~/rvt-research/samples-rfa/')
FILES = [D + n for n in ('rac_basic_sample_family-2018.rfa', 'racbasicsamplefamily-2022.rfa', 'racbasicsamplefamily-2024.rfa', 'racbasicsamplefamily-2026.rfa') if os.path.exists(D + n)]
pytestmark = pytest.mark.skipif(not FILES, reason='no public samples')


@pytest.mark.parametrize('src', FILES, ids=[os.path.basename(f)[-9:] for f in FILES])
@pytest.mark.parametrize('new', ['Edited', 'E' * 3000])
def test_gzip_headers_and_side_streams_kept(tmp_path, src, new):
    import wledit, wlrec, cfb
    ed = wledit.Editor(src); pn = ed.trace(7)[0]
    ed.set_strings([(7, 'FillPattern.m_name', new)]); o = str(tmp_path / 'o.rfa'); ed.save(o)
    A = wlrec.Model(src); B = wlrec.Model(o)
    ma, mb = A.parts[pn]['mem'], B.parts[pn]['mem']
    assert len(ma) == len(mb)
    pa, pb = A.parts[pn]['stream'].payload, B.parts[pn]['stream'].payload
    for (sa, _, _), (sb, _, _) in zip(ma, mb):
        assert pa[sa:sa + 10] == pb[sb:sb + 10], 'gzip header changed'
    SA = cfb.CFB(open(src, 'rb').read()).streams(); SB = cfb.CFB(open(o, 'rb').read()).streams()
    assert [k for k in SA if SA[k].data != SB[k].data] == [pn]
