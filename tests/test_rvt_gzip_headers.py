"""c2x-rvtgap item 10: after a string edit every gzip member of every partition keeps its 10-byte header (flags, mtime, xfl, OS) and has a valid CRC32/ISIZE trailer."""
import os, sys, glob, zlib, struct, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SAMPLES = sorted(glob.glob(os.path.expanduser('~/rvt-research/samples-rfa/*.rfa')))
pytestmark = pytest.mark.skipif(not SAMPLES, reason='no public samples')


def _members(path):
    import wlrec, wlpart
    m = wlrec.Model(path); out = {}
    for pn in m.parts:
        if pn.startswith('Partitions/'):
            st = m.parts[pn]['stream']; p = wlpart.Partition(st, hs=12 + m.IDW); P = st.payload
            out[pn] = [(x['gzhdr'], bytes(P[x['pos']:x['end']])) for x in p.mem]
    return out


@pytest.mark.parametrize('path', SAMPLES, ids=[os.path.basename(p)[-9:] for p in SAMPLES])
def test_gzip_member_headers_and_trailers_after_edit(path, tmp_path):
    import wledit
    ed = wledit.Editor(path)
    try: ed.set_strings([(7, 'FillPattern.m_name', 'HorizontalZ')])
    except Exception as e: pytest.skip('edit not applicable: %s' % e)
    o = str(tmp_path / 'o.rfa'); ed.save(o)
    a, b = _members(path), _members(o)
    for pn in a:
        assert len(a[pn]) == len(b[pn]), pn
        for k, ((h0, _), (h1, raw)) in enumerate(zip(a[pn], b[pn])):
            assert h0 == h1, '%s member %d: gzip header changed %r -> %r' % (pn, k, h0, h1)
            d = zlib.decompressobj(-15); data = d.decompress(raw[10:]); assert d.eof
            crc, isz = struct.unpack('<II', raw[-8:])
            assert crc == zlib.crc32(data) & 0xffffffff and isz == len(data) & 0xffffffff, '%s member %d: bad trailer' % (pn, k)
