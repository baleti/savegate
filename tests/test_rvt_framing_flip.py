"""c4x-rvtgap 317/318: a bit flip in the partition FRAMING (44-byte header, 32-byte frames between gzip members, tail after the last member), ECC recomputed, must be refused;
the legitimate size-changing string edit must still be accepted. Autodesk sample family only."""
import os, sys, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-%s.rfa')
@pytest.mark.parametrize('year', ['2024', '2026'])
def test_framing_flip_refused_legit_edit_accepted(tmp_path, year):
    import savegate as sg, wledit, cfb, rvtw, wlpart
    from test_rvt_last_record_string_edit import _last_string_records
    src = SRC % year
    if not os.path.exists(src): pytest.skip('no public sample')
    cfg = sg.Config(allow_overwrite=True, require_gate=False)
    q, eid, fn, old, pn = _last_string_records(wledit.Editor(src), 1)[0]
    ed = wledit.Editor(src); ed.set_strings([(eid, fn, str(old) + 'Z' * 40)]); o = str(tmp_path / 'o.rfa'); ed.save(o); good = open(o, 'rb').read()
    decl = {'modified': ['stream:' + pn, 'el:%d' % eid]}
    cur = str(tmp_path / 'ok.rfa'); shutil.copy(src, cur)
    assert sg.save(sg.open_doc(cur, None, cfg), good, decl).ok
    c0 = cfb.CFB(good); st0 = rvtw.Stream(bytes(c0.streams()[pn].data)); p0 = bytes(st0.payload); P = wlpart.Partition(st0)
    offs = [P.mem[0]['pos'] + 4, P.mem[2]['pos'] + 8, P.mem[5]['pos'] + 9, 0, 12, 30, P.mem[0]['end'], P.mem[0]['end'] + 8, P.mem[0]['end'] + 12, P.mem[3]['end'] + 24, P.mem[3]['end'] + 31, P.mem[P.n - 1]['end'], P.mem[P.n - 1]['end'] + 12]
    for po in offs:
        c = cfb.CFB(good)
        for x in c.entries:
            if x.type == 2: x.data = bytes(x.data)
        x = [x for x in c.entries if x.type == 2 and x.name == pn.split('/')[-1]][0]
        pp = bytearray(p0); pp[po] ^= 0x40; x.data = bytes(rvtw.Stream(x.data).build(bytes(pp)))
        m = str(tmp_path / 'm.rfa'); cfb.write(c, m); cur = str(tmp_path / 'c.rfa'); shutil.copy(src, cur)
        with pytest.raises(Exception):
            sg.save(sg.open_doc(cur, None, cfg), open(m, 'rb').read(), decl)
        assert open(cur, 'rb').read() == open(src, 'rb').read(), 'original damaged at offset %d' % po
@pytest.mark.parametrize('year', ['2024', '2026'])
def test_equivalent_deflate_bitflip_refused(tmp_path, year):
    """a flip inside a gzip member's deflate data that inflates to the SAME bytes (found by random flips, c4x-rvtgap 315/316) must be refused too: unchanged members are copied byte-exactly"""
    import savegate as sg, wledit, cfb, rvtw, wlpart, zlib
    from test_rvt_last_record_string_edit import _last_string_records
    src = SRC % year
    if not os.path.exists(src): pytest.skip('no public sample')
    cfg = sg.Config(allow_overwrite=True, require_gate=False)
    q, eid, fn, old, pn = _last_string_records(wledit.Editor(src), 1)[0]
    ed = wledit.Editor(src); ed.set_strings([(eid, fn, 'Q')]); o = str(tmp_path / 'o.rfa'); ed.save(o); good = open(o, 'rb').read()
    decl = {'modified': ['stream:' + pn, 'el:%d' % eid]}
    st0 = rvtw.Stream(bytes(cfb.CFB(good).streams()[pn].data)); p0 = bytes(st0.payload); P = wlpart.Partition(st0)
    found = None
    for k in range(P.n):
        a, b = P.mem[k]['pos'], P.mem[k]['end']
        for po in range(b - 8 - 1, a + 10, -1):          # scan back from the deflate end for a bit whose flip keeps the inflate output identical
            pp = bytearray(p0); pp[po] ^= 1
            do = zlib.decompressobj(-15)
            try:
                out = do.decompress(bytes(pp[a + 10:b])); same = do.eof and out == bytes(P.mem[k]['raw'])
            except zlib.error: same = False
            if same: found = po; break
        if found: break
    if not found: pytest.skip('no equivalent-inflate flip located in this sample')
    c = cfb.CFB(good)
    for x in c.entries:
        if x.type == 2: x.data = bytes(x.data)
    x = [x for x in c.entries if x.type == 2 and x.name == pn.split('/')[-1]][0]
    pp = bytearray(p0); pp[found] ^= 1; x.data = bytes(rvtw.Stream(x.data).build(bytes(pp)))
    m = str(tmp_path / 'm.rfa'); cfb.write(c, m); cur = str(tmp_path / 'c.rfa'); shutil.copy(src, cur)
    with pytest.raises(Exception):
        sg.save(sg.open_doc(cur, None, cfg), open(m, 'rb').read(), decl)
    assert open(cur, 'rb').read() == open(src, 'rb').read()
@pytest.mark.parametrize('year', ['2024', '2026'])
def test_directory_timestamp_flip_refused(tmp_path, year):
    """c4x-rvtgap 325: creation/modified FILETIME bytes of a CFB directory entry (offsets 100..115) were accepted; the writer preserves them, so a change is refused"""
    import savegate as sg, wledit, struct
    from test_rvt_last_record_string_edit import _last_string_records
    src = SRC % year
    if not os.path.exists(src): pytest.skip('no public sample')
    cfg = sg.Config(allow_overwrite=True, require_gate=False)
    q, eid, fn, old, pn = _last_string_records(wledit.Editor(src), 1)[0]
    ed = wledit.Editor(src); ed.set_strings([(eid, fn, 'Q')]); o = str(tmp_path / 'o.rfa'); ed.save(o); good = bytearray(open(o, 'rb').read())
    ss = 1 << struct.unpack_from('<H', good, 30)[0]; base = ss * (struct.unpack_from('<I', good, 48)[0] + 1)
    for po in (base + 100, base + 108, base + 115, base + 128 * 2 + 104):
        b = bytearray(good); b[po] ^= 1
        cur = str(tmp_path / 'c.rfa'); shutil.copy(src, cur)
        with pytest.raises(Exception):
            sg.save(sg.open_doc(cur, None, cfg), bytes(b), {'modified': ['stream:' + pn, 'el:%d' % eid]})
        assert open(cur, 'rb').read() == open(src, 'rb').read()
