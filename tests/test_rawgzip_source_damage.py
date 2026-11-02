"""c7x-rvtread2: Formats/Latest is a raw-gzip stream whose 8-byte tail is NOT a valid crc32/isize (2018/2024/2026 public samples),
so a crc rule gives false positives on clean files and cannot detect flips. Requirements that are checkable:
 1. source_damage == [] on clean Autodesk samples (a crc rule would flag them and refuse every save);
 2. an unedited save_as keeps Formats/Latest byte-identical to the source (writable years)."""
import os, sys, shutil, pytest
import savegate as sg
from savegate import adapters, core
S = os.path.expanduser('~/rvt-research/samples-rfa/')
FILES = ['rac_basic_sample_family-2018.rfa', 'racbasicsamplefamily-2024.rfa', 'racbasicsamplefamily-2026.rfa']

@pytest.mark.parametrize('f', FILES)
def test_clean_sample_has_no_damage(f):
    if not os.path.exists(S + f): pytest.skip('public sample missing')
    assert adapters.RvtAdapter().source_damage(open(S + f, 'rb').read()) == []

@pytest.mark.parametrize('f', FILES[1:])
def test_identity_save_keeps_formats_latest(f, tmp_path):
    if not os.path.exists(S + f): pytest.skip('public sample missing')
    A = adapters.RvtAdapter(); sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); import cfb
    b = open(S + f, 'rb').read(); p = str(tmp_path / 'in.rfa'); d = str(tmp_path / 'out.rfa'); open(p, 'wb').write(b)
    core.save_as(core.open_doc(p, A, journal=False), b, d)
    assert cfb.CFB(open(d, 'rb').read()).streams()['Formats/Latest'].data == cfb.CFB(b).streams()['Formats/Latest'].data


def test_fat_chain_cut_makes_streams_short_and_is_reported(tmp_path):
    """c4x-rvtgap: a FAT entry forced to ENDOFCHAIN left a stream shorter than its directory size; the old gate saved such a source back unchanged (accepted)."""
    import struct
    f = S + 'racbasicsamplefamily-2024.rfa'
    if not os.path.exists(f): pytest.skip('public sample missing')
    src = open(f, 'rb').read(); A = adapters.RvtAdapter()
    assert A.source_damage(src) == []
    off = (struct.unpack_from('<I', src, 76)[0] + 1) * (1 << struct.unpack_from('<H', src, 30)[0])
    for i in (4, 23, 35):
        b = bytearray(src); struct.pack_into('<I', b, off + 4 * i, 0xFFFFFFFE)
        assert any('declared' in e for e in A.source_damage(bytes(b))), i


@pytest.mark.parametrize('y', ['2024', '2026'])
def test_writer_copies_every_stream_but_the_edited_partition(y, tmp_path):
    """c4x-rvtgap inventory: a no-edit container write leaves all streams byte-identical; a one-string edit changes exactly one Partitions/* stream."""
    sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab'))
    cfb = pytest.importorskip('cfb'); wledit = pytest.importorskip('wledit')
    src = S + 'racbasicsamplefamily-%s.rfa' % y
    if not os.path.exists(src): pytest.skip('public sample missing')
    St = cfb.CFB(open(src, 'rb').read()).streams()
    o = str(tmp_path / 'n.rfa'); cfb.write(cfb.CFB(open(src, 'rb').read()), o)
    N = cfb.CFB(open(o, 'rb').read()).streams()
    assert set(N) == set(St) and [n for n in St if N[n].data != St[n].data] == []
    ed = wledit.Editor(src); l = next(l for l in ed.trace(0)[3] if l[1] == 'SymbolInfo.m_name')
    ed.set_string(0, l[1], l[4] + 'XY', match=l[4]); o2 = str(tmp_path / 'e.rfa'); ed.save(o2)
    E = cfb.CFB(open(o2, 'rb').read()).streams()
    d = [n for n in St if E[n].data != St[n].data]
    assert set(E) == set(St) and len(d) == 1 and d[0].startswith('Partitions/')


def test_set_string_refuses_a_non_string_field_with_matching_span(tmp_path):
    """c4x-rvtgap: Identifier.m_id64 (text '17', 8-byte span == 4+2*2) used to be overwritten by a string edit and saved as a valid-looking file."""
    sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab'))
    wledit = pytest.importorskip('wledit')
    src = S + 'racbasicsamplefamily-2024.rfa'
    if not os.path.exists(src): pytest.skip('public sample missing')
    ed = wledit.Editor(src)
    if not hasattr(ed, '_check_wstr'): pytest.skip('wledit without the type check')
    with pytest.raises(ValueError, match='not a length-prefixed wide string'):
        ed.set_string(0, 'Identifier.m_id64', 'ab', match='17')
    l = next(l for l in ed.trace(0)[3] if l[1] == 'SymbolInfo.m_name')
    ed.set_string(0, l[1], l[4] + 'XY', match=l[4]); ed.save(str(tmp_path / 'o.rfa'))


def test_junk_in_the_zero_padding_of_a_padded_partition_is_refused_without_the_element_view(tmp_path, monkeypatch):
    """c4x-rvtgap: second-generation edits pad the partition with a 64 KB zero page; a byte of junk there (valid ECC) was accepted when the element view is off."""
    sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab'))
    cfb = pytest.importorskip('cfb'); rvtw = pytest.importorskip('rvtw'); wledit = pytest.importorskip('wledit')
    src = S + 'racbasicsamplefamily-2024.rfa'
    if not os.path.exists(src): pytest.skip('public sample missing')
    cur = str(tmp_path / 'f.rfa'); shutil.copy(src, cur)
    for txt in ('XY', 'Z' * 300):      # gen2 overflows the last ECC page of gen1 -> full zero page
        ed = wledit.Editor(cur); l = next(l for l in ed.trace(0)[3] if l[1] == 'SymbolInfo.m_name')
        ed.set_string(0, l[1], l[4] + txt, match=l[4]); o = str(tmp_path / 'o.rfa'); ed.save(o); del ed
        if txt != 'XY': break
        shutil.copy(o, cur)
    good = open(o, 'rb').read(); pn = 'Partitions/67'
    A = adapters.RvtAdapter(); assert A.validate(good)
    c = cfb.CFB(good); st = rvtw.Stream(c.streams()[pn].data); P = bytearray(st.payload); assert P[-1000:] == bytes(1000)
    P[len(P) - 30000] = 0x5a; c.streams()[pn].data = st.build(bytes(P), keep_spare=False); b2 = str(tmp_path / 'j.rfa'); cfb.write(c, b2)
    with pytest.raises(sg.VerifyFailed, match='partition tail'): A.validate(open(b2, 'rb').read())


def test_junk_in_container_reserved_and_free_areas_is_refused(tmp_path):
    """c4x-rvtgap: header reserved bytes / transaction signature / name bytes in a free directory entry / non-free FAT entries past the end were all ACCEPTED (gate on and off)."""
    import struct
    sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab'))
    cfb = pytest.importorskip('cfb')
    src = S + 'racbasicsamplefamily-2024.rfa'
    if not os.path.exists(src): pytest.skip('public sample missing')
    good = open(src, 'rb').read(); c = cfb.CFB(good); out = str(tmp_path / 'w.rfa'); cfb.write(c, out); good = open(out, 'rb').read()
    A = adapters.RvtAdapter(); assert A.validate(good)
    ss = 1 << struct.unpack_from('<H', good, 30)[0]; off = (struct.unpack_from('<I', good, 48)[0] + 1) * ss
    free = next(i for i in range(ss // 128) if good[off + i * 128 + 66] == 0 and not any(good[off + i * 128:off + i * 128 + 64]))
    fo = (struct.unpack_from('<I', good, 76)[0] + 1) * ss
    cases = {'hdr_reserved': lambda b: b.__setitem__(slice(34, 40), b'\x99' * 6), 'transsig': lambda b: b.__setitem__(slice(52, 56), b'\1\2\3\4'),
             'free_dir_name': lambda b: b.__setitem__(slice(off + free * 128, off + free * 128 + 4), b'J\0K\0'), 'fat_tail': lambda b: struct.pack_into('<I', b, fo + ss - 4, 7)}
    for k, f in cases.items():
        b = bytearray(good); f(b)
        with pytest.raises(sg.VerifyFailed, match='reserved/free area'): A.validate(bytes(b))


def test_junk_after_the_gzip_member_of_a_declared_global_stream_is_refused(tmp_path):
    """c4x-rvtgap: a flipped byte in the 134-byte post-member tail of Global/Latest (valid ECC), stream declared modified, was ACCEPTED."""
    sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab'))
    cfb = pytest.importorskip('cfb'); rvtw = pytest.importorskip('rvtw')
    src = S + 'racbasicsamplefamily-2024.rfa'
    if not os.path.exists(src): pytest.skip('public sample missing')
    raw = open(src, 'rb').read(); n = 'Global/Latest'
    c = cfb.CFB(raw); st = rvtw.Stream(c.streams()[n].data); P = bytearray(st.payload); e = rvtw.read_member(bytes(P), P.find(rvtw.GZ))[1]
    P[e + 1] ^= 0x41; c.streams()[n].data = st.build(bytes(P), keep_spare=False); o = str(tmp_path / 'j.rfa'); cfb.write(c, o)
    A = adapters.RvtAdapter(); A.source_damage(raw)
    with pytest.raises(sg.VerifyFailed, match='after the gzip member'): A.validate(open(o, 'rb').read())
    ok = str(tmp_path / 'ok.rfa'); cfb.write(cfb.CFB(raw), ok); assert A.validate(open(ok, 'rb').read())


@pytest.mark.parametrize('st', ['BasicFileInfo', 'RevitPreview4.0', 'Contents', 'TransmissionData', 'Formats/Latest'])
def test_declared_metadata_stream_change_is_refused(st, tmp_path):
    """c4x-rvtgap: a flipped byte in a plain metadata stream, declared modified, was ACCEPTED (no ECC/CRC to catch it)."""
    sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab'))
    cfb = pytest.importorskip('cfb')
    src = S + 'racbasicsamplefamily-2024.rfa'
    if not os.path.exists(src): pytest.skip('public sample missing')
    raw = open(src, 'rb').read(); c = cfb.CFB(raw); e = c.streams()[st]; d = bytearray(e.data); d[len(d) // 2] ^= 0x41; e.data = bytes(d)
    o = str(tmp_path / 'm.rfa'); cfb.write(c, o); cur = str(tmp_path / 'cur.rfa'); shutil.copy(src, cur)
    before = open(cur, 'rb').read()
    with pytest.raises(sg.VerifyFailed, match='metadata'):
        sg.save(sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False)), open(o, 'rb').read(), {'modified': ['stream:' + st]})
    assert open(cur, 'rb').read() == before
