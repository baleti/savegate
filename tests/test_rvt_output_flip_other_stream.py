"""c2x-rvtgap: a valid declared edit of Partitions/67 + el:7, then ONE byte flipped (in the middle, and in the first/last byte) inside every OTHER stream of the OUTPUT
(schema/Formats, Global/*, BasicFileInfo, thumbnail, ...): the in-place gate must refuse and leave the target untouched. Streams where the flip is accepted are listed (ESCAPE)."""
import os, sys, shutil, hashlib, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no public sample')


def test_flip_in_other_streams_refused(tmp_path):
    import savegate as sg, wledit, cfb
    from savegate.adapters import RvtAdapter
    ed = wledit.Editor(SRC); ed.set_strings([(7, 'FillPattern.m_name', 'Flip')]); o = str(tmp_path / 'o.rfa'); ed.save(o)
    good = cfb.CFB(open(o, 'rb').read()); names = [k for k in good.streams() if k != 'Partitions/67' and len(good.streams()[k].data) > 0]
    escapes = []; n = 0
    for k in names:
        L = len(good.streams()[k].data)
        for pos in sorted({0, L // 2, L - 1}):
            c = cfb.CFB(open(o, 'rb').read()); d = bytearray(c.streams()[k].data); d[pos] ^= 0x10; c.streams()[k].data = bytes(d)
            p = str(tmp_path / 'f.bin'); cfb.write(c, p); bad = open(p, 'rb').read()
            cur = str(tmp_path / 'cur.rfa'); shutil.copy(SRC, cur); before = open(cur, 'rb').read(); n += 1
            doc = sg.open_doc(cur, RvtAdapter(), sg.Config(allow_overwrite=True, require_gate=False))
            try: sg.save(doc, bad, {'modified': ['stream:Partitions/67', 'el:7']}); escapes.append((k, pos, L))
            except sg.SaveError: assert open(cur, 'rb').read() == before
    print('flips tried %d, accepted %d: %s' % (n, len(escapes), escapes))
    assert not escapes, escapes
