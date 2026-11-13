"""c5x-rvtgap SEV1: a single bit flipped in the Adler32 field of a record header (the 22 bytes between element records) went unnoticed by every other rule
(1 of 40 random header-gap flips accepted on the 2024 public family). The gate must refuse it; the clean edit must still pass."""
import os, sys, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no public sample')
TARGET = 5138               # a record whose Adler32 is valid in the source (1962 of 1975 are; elements 0,1,3,8,... are not)


def _adler_offset():
    """payload offset of the Adler32 field of record TARGET"""
    import numpy as np, cfb, rvtw, wlpart, rvt_scan as S, rvt_inventory as I
    o, cls, ids = S.load(SRC); W = S.id_size(cls); hs = 12 + W
    c = cfb.CFB(open(SRC, 'rb').read()); st = rvtw.Stream(c.streams()['Partitions/67'].data); pt = wlpart.Partition(st, hs=hs)
    bj = b''.join(bytes(m['raw']) for m in pt.mem); arr = np.array(sorted(ids), dtype=np.uint32 if W == 4 else np.uint64)
    for i in S.header_candidates_tagged(bj, arr, W, I.element_tags(cls)):
        i = int(i)
        if int.from_bytes(bj[i + 4:i + 4 + W], 'little') == TARGET: return i + 4 + W
    raise RuntimeError('record not found')


CHK_OFFSET = None


def _out(tmp_path, flip, fixed=None):
    import wledit, cfb, rvtw, wlpart
    ed = wledit.Editor(SRC); ed.set_strings([(7, 'FillPattern.m_name', 'Zed')]); o = str(tmp_path / 'o.rfa'); ed.save(o)
    if flip:
        CHK = fixed if fixed is not None else _adler_offset()
        c = cfb.CFB(open(o, 'rb').read()); n = 'Partitions/67'; st = rvtw.Stream(c.streams()[n].data); pt = wlpart.Partition(st); base = 0
        for m in pt.mem:
            if base <= CHK < base + len(m['raw']): m['raw'][CHK - base] ^= 1; m['dirty'] = True; break
            base += len(m['raw'])
        c.streams()[n].data = st.build(pt.rebuild(), keep_spare=False); cfb.write(c, o)
    return open(o, 'rb').read()


def _save(tmp_path, new):
    import savegate as sg
    cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur); before = open(cur, 'rb').read()
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    try: sg.save(doc, new, {'modified': ['stream:Partitions/67', 'el:7']}); ok = True
    except sg.SaveError: ok = False
    return ok, cur, before


def test_flipped_record_checksum_is_refused(tmp_path):
    ok, cur, before = _save(tmp_path, _out(tmp_path, True))
    assert not ok and open(cur, 'rb').read() == before


def test_clean_edit_still_accepted(tmp_path):
    new = _out(tmp_path, False); ok, cur, before = _save(tmp_path, new)
    assert ok and open(cur, 'rb').read() == new


def test_flip_in_header_of_a_record_without_valid_adler_is_refused(tmp_path):
    """the case that really escaped: byte 13 of the 22-byte header of element 1 (one of ~13 records whose checksum is not an Adler32 of the assumed span), 1 KB before the edit"""
    ok, cur, before = _save(tmp_path, _out(tmp_path, True, fixed=440497))
    assert not ok and open(cur, 'rb').read() == before


@pytest.mark.parametrize('off', [686424, 734675, 744775, 903941, 958725])
def test_flip_in_checksum_of_a_record_whose_element_id_has_several_header_candidates_is_refused(tmp_path, off):
    """c5x item 205: for these element ids the header scan finds several candidates (phantoms or a stale copy); the Adler rule keeps only the last per id, so the
    first (real) record is not covered by that rule alone. The gate as a whole must still refuse (byte-window rule)."""
    ok, cur, before = _save(tmp_path, _out(tmp_path, True, fixed=off))
    assert not ok and open(cur, 'rb').read() == before
