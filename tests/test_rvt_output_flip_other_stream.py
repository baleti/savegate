"""c2x-rvtgap: a valid declared edit of Partitions/67 + el:7, then ONE byte flipped (in the middle, and in the first/last byte) inside every OTHER stream of the OUTPUT
(schema/Formats, Global/*, BasicFileInfo, thumbnail, ...): the in-place gate must refuse and leave the target untouched. Streams where the flip is accepted are listed (ESCAPE)."""
import os, sys, shutil, hashlib, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
R = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-%s.rfa')
YEARS = [y for y in ('2024', '2026') if os.path.exists(R % y)]
pytestmark = pytest.mark.skipif(not YEARS, reason='no public sample')


@pytest.mark.parametrize('mode', ['flip', 'zero16'])
@pytest.mark.parametrize('year', YEARS)
def test_flip_in_other_streams_refused(tmp_path, year, mode):
    SRC = R % year
    import savegate as sg, wledit, cfb
    from savegate.adapters import RvtAdapter
    ed = wledit.Editor(SRC); PN = ed.trace(7)[0]; ed.set_strings([(7, 'FillPattern.m_name', 'Flip')]); o = str(tmp_path / 'o.rfa'); ed.save(o)
    good = cfb.CFB(open(o, 'rb').read()); names = [k for k in good.streams() if k != PN and len(good.streams()[k].data) > 0]
    escapes = []; n = 0
    for k in names:
        L = len(good.streams()[k].data)
        for pos in sorted({0, L // 2, L - 1}):
            c = cfb.CFB(open(o, 'rb').read()); orig = bytes(c.streams()[k].data); d = bytearray(c.streams()[k].data); (d.__setitem__(pos, d[pos] ^ 0x10) if mode == 'flip' else d.__setitem__(slice(pos, min(pos + 16, L)), bytes(min(16, L - pos)))); c.streams()[k].data = bytes(d)
            if bytes(d) == orig: continue          # zeroing already-zero bytes changes nothing
            p = str(tmp_path / 'f.bin'); cfb.write(c, p); bad = open(p, 'rb').read()
            cur = str(tmp_path / 'cur.rfa'); shutil.copy(SRC, cur); before = open(cur, 'rb').read(); n += 1
            doc = sg.open_doc(cur, RvtAdapter(), sg.Config(allow_overwrite=True, require_gate=False))
            try: sg.save(doc, bad, {'modified': ['stream:' + PN, 'el:7']}); escapes.append((k, pos, L))
            except sg.SaveError: assert open(cur, 'rb').read() == before
    print('flips tried %d, accepted %d: %s' % (n, len(escapes), escapes))
    assert not escapes, escapes
