"""c4x-rvtgap 206: single-bit flips found by a gated-output fuzz that the gate ACCEPTED: header padding (offset 830, both years) and a miniFAT entry past the end of the mini-stream (offset 408128, 2026 family)."""
import os, sys, glob, shutil, struct, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
@pytest.mark.parametrize('yr', ['2024', '2026'])
@pytest.mark.parametrize('what', ['hdrpad', 'minifat_tail'])
def test_flip_is_refused(tmp_path, yr, what):
    import savegate as sg, wledit, cfb
    src = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-%s.rfa' % yr)
    if not os.path.exists(src): pytest.skip('no sample')
    ed = wledit.Editor(src); ed.set_strings([(7, 'FillPattern.m_name, ', 'x')][:0] or [(7, 'FillPattern.m_name', 'Pad probe')]); o = str(tmp_path / 'o.rfa'); ed.save(o); good = open(o, 'rb').read()
    b = bytearray(good)
    if what == 'hdrpad': b[830] ^= 1
    else:
        c = cfb.CFB(good); root = c.entries[0]; first_free = (root.size + 63) // 64
        ms = struct.unpack_from('<I', good, 60)[0]; pos = (ms + 1) * c.ss + first_free * 4
        assert struct.unpack_from('<I', good, pos)[0] in (0, 0xFFFFFFFF)      # writer zero-fills the unused part of the miniFAT sector
        b[pos] ^= 1
    cur = str(tmp_path / 'c.rfa'); shutil.copy(src, cur); before = open(cur, 'rb').read()
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    with pytest.raises(sg.SaveError): sg.save(doc, bytes(b), {'modified': ['stream:Partitions/67', 'el:7']})
    assert open(cur, 'rb').read() == before
