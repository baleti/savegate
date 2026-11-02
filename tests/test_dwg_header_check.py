"""c4x-dwgreadfuzz item 75: R2004+ file header check (magic + CRC32 of the decrypted 0x6C block + two preamble invariants). Synthetic header, no client data."""
import os, sys, struct, zlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from savegate.adapters import _header_problems


def make(ver=b'AC1032'):
    h = bytearray(0x6C); h[:11] = b'AcFssFcAJMB'; h[0x20:0x24] = b'\x11\x22\x33\x44'
    h[0x68:0x6C] = struct.pack('<I', zlib.crc32(bytes(h)) & 0xFFFFFFFF)
    seed = 1; e = bytearray(h)
    for i in range(len(e)):
        seed = (seed * 0x343FD + 0x269EC3) & 0xFFFFFFFF; e[i] ^= (seed >> 16) & 0xFF
    b = bytearray(0x200); b[:6] = ver; b[0x28:0x2C] = b'\x80\0\0\0'; b[0x80:0x80 + 0x6C] = e
    return b


def test_good_header_has_no_problems():
    assert _header_problems(bytes(make())) == []
    assert _header_problems(b'AC1015' + bytes(500)) == []        # R2000: not checked here


def test_block_bit_flip_is_reported():
    for off in (0x80, 0x90, 0xB0, 0xE0, 0xEB):
        b = make(); b[off] ^= 1
        assert _header_problems(bytes(b)), off


def test_preamble_invariants_and_truncation():
    b = make(); b[8] = 1; assert _header_problems(bytes(b))
    b = make(); b[0x29] = 1; assert _header_problems(bytes(b))
    assert _header_problems(bytes(make())[:0x90])


def test_preamble_snapshot_changes_with_any_preamble_byte():
    from savegate.adapters import _preamble_snap
    a = bytes(make()); assert _preamble_snap(a) == _preamble_snap(bytes(a))
    for off in (0x0B, 0x13, 0x20, 0x30, 0x7F):
        b = bytearray(a); b[off] ^= 1
        assert _preamble_snap(bytes(b)) != _preamble_snap(a), off
    b = bytearray(a); b[0x80] ^= 1; assert _preamble_snap(bytes(b)) == _preamble_snap(a)   # encrypted block is covered by _header_problems, not this
    assert _preamble_snap(b'AC1015' + bytes(300)) is None


def _with_system_pages():
    from savegate.adapters import _system_page_problems
    def page(typ, data):
        hz = struct.pack('<5I', typ, 100, len(data), 2, 0)
        ck = zlib.adler32(data, zlib.adler32(hz, 0) & 0xFFFFFFFF) & 0xFFFFFFFF
        return struct.pack('<5I', typ, 100, len(data), 2, ck) + data
    h = bytearray(0x6C); h[:11] = b'AcFssFcAJMB'
    struct.pack_into('<q', h, 0x54, 0x300 - 0x100); struct.pack_into('<I', h, 0x5C, 7)
    h[0x68:0x6C] = struct.pack('<I', zlib.crc32(bytes(h)) & 0xFFFFFFFF)
    seed = 1; e = bytearray(h)
    for i in range(len(e)):
        seed = (seed * 0x343FD + 0x269EC3) & 0xFFFFFFFF; e[i] ^= (seed >> 16) & 0xFF
    b = bytearray(0x600); b[:6] = b'AC1032'; b[0x28:0x2C] = b'\x80\0\0\0'; b[0x80:0x80 + 0x6C] = e
    pm = page(0x41630E3B, bytes(range(50))); sm = page(0x4163003B, bytes(range(80)))
    b[0x300:0x300 + len(pm)] = pm; b[0x400:0x400 + len(sm)] = sm
    info = {'pages': {7: (0x400, 0x100)}}
    return b, info, _system_page_problems, len(pm), len(sm)


def test_system_page_checksums():
    b, info, f, lp, ls = _with_system_pages()
    assert f(bytes(b), info) == []
    for off in (0x300, 0x310, 0x300 + 25, 0x300 + lp - 1):                 # header, checksum field, data
        m = bytearray(b); m[off] ^= 1; assert f(bytes(m), info), hex(off)
    for off in (0x400 + 3, 0x400 + 22, 0x400 + ls - 1):
        m = bytearray(b); m[off] ^= 1; assert f(bytes(m), info), hex(off)
    m = bytearray(b); m[0x300 + lp + 5] ^= 1; assert f(bytes(m), info) == []   # padding behind the page is not covered (harmless)
    assert f(b'AC1015' + bytes(0x600), info) == []


def test_embedded_object_handle_must_match_object_map():
    from savegate.adapters import DwgAdapter
    DwgAdapter()                                    # puts the dwg lib (dwgbits) on sys.path
    class O: pass
    o = O(); o.raw = bytes([0x01, 0x5C, 0x00]); o.data_bit = 0          # H(): code 0, 1 counter byte, value 0x5C
    assert DwgAdapter._handle_damage_one(0x5C, o) is False
    assert DwgAdapter._handle_damage_one(0x5D, o) is True               # CRC-fixed flip in the value
    o.raw = bytes([0x11, 0x5C, 0x00]); assert DwgAdapter._handle_damage_one(0x5C, o) is True    # code nibble must be 0
    o.raw = bytes([0x09, 0x5C, 0x00]); assert DwgAdapter._handle_damage_one(0x5C, o) is True    # counter changed: reads garbage/short
    class M: pass
    m = M(); o.raw = bytes([0x01, 0x5C, 0x00]); m.objs = {0x5C: o, 0x5E: o}
    assert DwgAdapter._handle_damage(m) == ['obj:5e: embedded handle 5c differs from the object map']


def test_undeclared_object_with_changed_bytes_is_refused_even_if_it_decodes_the_same():
    """item 87: entity compared by decoded fields only; a flipped discarded bit changes raw but not the decoded entity."""
    from savegate.adapters import DwgAdapter
    class O:
        def __init__(s, raw): s.raw = raw; s.type = 19; s.data_bit = 0
    class M:
        def __init__(s, raws): s.objs = {h: O(r) for h, r in raws.items()}; s.blocks = {}
    a = DwgAdapter(); a.owners = {}; a.bheaders = {}; a.dimobjs = {}
    a._pair = (M({0x40: b'\x01\x40\x00\x00\x00'}), M({0x40: b'\x01\x40\x00\x00\x01'}))
    r = a.extra_checks({'modified': []})
    assert ('undeclared_object_bytes', 'obj:40') in r
    assert ('undeclared_object_bytes', 'obj:40') not in a.extra_checks({'modified': [0x40]})


def test_undeclared_bytes_rule_is_off_for_r2000_entity_chains():
    from savegate.adapters import DwgAdapter
    class O:
        def __init__(s, raw): s.raw = raw; s.type = 19; s.data_bit = 0
    class M:
        def __init__(s, raws, v): s.version = v; s.objs = {h: O(r) for h, r in raws.items()}; s.blocks = {}
    a = DwgAdapter(); a.owners = {}; a.bheaders = {}; a.dimobjs = {}
    a._pair = (M({0x40: b'\x01\x40\x00\x00\x00'}, 'AC1015'), M({0x40: b'\x01\x40\x00\x00\x01'}, 'AC1015'))
    assert not [x for x in a.extra_checks({'added': [0x99]}) if x[0].startswith('undeclared')]


def test_preview_pointer_may_move_but_must_hit_the_preview_sentinel():
    from savegate.adapters import _preamble_snap, _PREVIEW_SENTINEL
    def mk(addr, total=0x400):
        b = bytearray(make()); b += bytes(total - len(b)); b[0x0D:0x11] = addr.to_bytes(4, 'little'); b[addr:addr + 16] = _PREVIEW_SENTINEL; return bytes(b)
    a, c = mk(0x200), mk(0x300)
    assert _preamble_snap(a) == _preamble_snap(c)                                   # moved, still valid
    d = bytearray(c); d[0x300] ^= 1; assert _preamble_snap(bytes(d)) != _preamble_snap(a)     # points at garbage
    e = bytearray(c); e[0x0D:0x11] = (0x350).to_bytes(4, 'little'); assert _preamble_snap(bytes(e)) != _preamble_snap(a)


def test_output_header_section_crc_must_be_valid_if_source_was(monkeypatch=None):
    import savegate.adapters as AD
    class O:
        def __init__(s, raw): s.raw = raw; s.type = 19; s.data_bit = 0
    class M:
        def __init__(s, tag): s.tag = tag; s.objs = {1: O(b'\x01\x01\x00\x00\x00')}; s.blocks = {}; s.version = 'AC1032'
    a = AD.DwgAdapter(); a.owners = {}; a.bheaders = {}; a.dimobjs = {}
    real = AD._header_section_crc_ok
    try:
        for src, out, flagged in ((True, False, True), (True, True, False), (False, False, False), (False, True, False)):
            AD._header_section_crc_ok = lambda m, src=src, out=out: src if m.tag == 's' else out
            a._pair = (M('s'), M('o'))
            assert (('header_section_crc', 'hdr') in a.extra_checks({})) == flagged, (src, out)
    finally:
        AD._header_section_crc_ok = real


def test_header_section_may_only_change_in_the_seed_field_and_crc():
    import savegate.adapters as AD
    DwgA = AD.DwgAdapter; DwgA()
    import dwgfmt, dwghdr
    a = bytearray(range(256)) * 2; a[16:20] = (400).to_bytes(4, 'little')
    class M:
        def __init__(s, data): s.version = 'AC1032'; s._buf = b''; s._info = {}; s.d = bytes(data)
    saved = (dwgfmt.r2004_section_data, dwghdr.header_vars)
    try:
        dwgfmt.r2004_section_data = lambda buf, info, name: info_data[0]
        dwghdr.header_vars = lambda buf, info, ver: {'_seedpos': 800}
        info_data = [None]
        def diff(x, y):
            seq = iter([bytes(x), bytes(y)]); dwgfmt.r2004_section_data = lambda buf, info, name: next(seq)
            return AD._header_section_diff(M(x), M(y))
        b = bytearray(a); assert diff(a, b) == []
        b[50] ^= 1; assert diff(a, b) == [50]
        b = bytearray(a); b[800 // 8 + 2] ^= 1; assert diff(a, b) == []          # inside the seed field
        crc = 20 + 400 + 4; b = bytearray(a); b[crc] ^= 1; assert diff(a, b) == []
        b = bytearray(a); b[300] ^= 1; assert diff(a, b) == [300]                 # undecoded tail bit
    finally:
        dwgfmt.r2004_section_data, dwghdr.header_vars = saved


def test_sections_other_than_header_objects_handles_preview_must_be_carried_verbatim():
    import savegate.adapters as AD
    AD.DwgAdapter()
    import dwgfmt
    class M:
        def __init__(s, names, tag): s.version = 'AC1032'; s._buf = tag; s._info = {'sections': {n: 1 for n in names}}
    names = ['AcDb:Header', 'AcDb:AcDbObjects', 'AcDb:Handles', 'AcDb:Preview', 'AcDb:Classes', 'AcDb:AppInfo']
    saved = dwgfmt.r2004_section_data
    try:
        data = {('s', 'AcDb:Classes'): b'abc', ('o', 'AcDb:Classes'): b'abc', ('s', 'AcDb:AppInfo'): b'x', ('o', 'AcDb:AppInfo'): b'x'}
        dwgfmt.r2004_section_data = lambda buf, info, nm: data.get((buf, nm), b'-')
        assert AD._other_sections_changed(M(names, 's'), M(names, 'o')) == []
        data[('o', 'AcDb:Classes')] = b'abd'
        assert AD._other_sections_changed(M(names, 's'), M(names, 'o')) == ['AcDb:Classes']
        assert AD._other_sections_changed(M(names, 's'), M(names[:-1], 'o')) == ['AcDb:AppInfo', 'AcDb:Classes']
    finally:
        dwgfmt.r2004_section_data = saved


def test_preview_section_may_only_change_its_image_start_addresses():
    import savegate.adapters as AD
    AD.DwgAdapter()
    import dwgfmt
    class M:
        def __init__(s, tag): s.version = 'AC1032'; s._buf = tag; s._info = {'sections': {'AcDb:Preview': 1}}
    a = bytearray(60); a[20] = 2                      # two entries: code@21 start@22..25 size@26..29, code@30 start@31..34
    saved = dwgfmt.r2004_section_data
    try:
        cur = {'s': bytes(a), 'o': bytes(a)}
        dwgfmt.r2004_section_data = lambda buf, info, nm: cur[buf]
        assert AD._preview_changed(M('s'), M('o')) == []
        b = bytearray(a); b[22] = 9; b[33] = 9; cur['o'] = bytes(b); assert AD._preview_changed(M('s'), M('o')) == []
        b = bytearray(a); b[26] = 9; cur['o'] = bytes(b); assert AD._preview_changed(M('s'), M('o')) == [26]     # size field
        b = bytearray(a); b[40] = 1; cur['o'] = bytes(b); assert AD._preview_changed(M('s'), M('o')) == [40]     # image data
    finally:
        dwgfmt.r2004_section_data = saved


def test_dimension_add_tolerates_the_real_block_control_handle():
    import savegate.adapters as AD
    class O:
        def __init__(s, t): s.type = t; s.raw = b''
    class M:
        def __init__(s): s.objs = {0x4a1: O(48), 0x10: O(19)}
    a = AD.DwgAdapter(); a.owners = {}; a.bheaders = {}; a.dimobjs = {}; a.dims = {0x99}
    a._pair = (M(), M())
    se = a.side_effects({'added': [0x99]})
    assert 'obj:4a1' in se and 'obj:10' not in se


def test_r2000_neighbour_may_gain_explicit_links_but_not_lose_them():
    import savegate.adapters as AD
    class O:
        def __init__(s): s.type = 19; s.raw = b'\x01'; s.data_bit = 0
    class M:
        def __init__(s, flags): s.version = 'AC1015'; s.objs = {h: O() for h in flags}; s.blocks = {}; s.f = flags
        def entities(s): return [('*Model_Space', {'handle': h, 'xdicmissing': v}) for h, v in s.f.items()]
    a = AD.DwgAdapter(); a.owners = {}; a.bheaders = {}; a.dimobjs = {}
    def run(f0, f1, man): a._pair = (M(f0), M(f1)); return [x for x in a.extra_checks(man) if x[0].startswith('xdic')]
    assert run({1: 1, 2: 1}, {1: 0, 2: 1}, {'deleted': [3]}) == []                                  # neighbour gained links
    assert run({1: 1, 2: 1}, {1: 0, 2: 1}, {'modified': [2]}) != []                                 # nothing added/deleted: not a side effect
    assert run({1: 0, 2: 1}, {1: 1, 2: 1}, {'deleted': [3]}) != []                                  # links lost (0 -> 1): refused
    assert run({i: 1 for i in range(10)}, {i: 0 for i in range(10)}, {'deleted': [99]}) != []       # far more neighbours than one edit can touch


def test_output_page_padding_behind_the_payload_must_be_zero():
    import struct, savegate.adapters as AD
    def page(a, comp, size, pad):
        mask = 0x4164536B ^ a
        hdr = struct.pack('<8I', *[x ^ mask for x in (0x4163043B, 100, comp, 0, 0, 0, 0, 0)])
        return hdr + bytes(range(1, comp + 1)) + pad
    a = 64; pg = page(a, 10, 80, bytes(80 - 32 - 10))
    class M: pass
    m = M(); m.version = 'AC1032'; m._buf = bytes(a) + pg; m._info = {'pages': {1: (a, 80)}}
    assert AD._page_padding_nonzero(m) == []
    bad = bytearray(m._buf); bad[a + 32 + 10 + 3] = 1; m._buf = bytes(bad)
    assert AD._page_padding_nonzero(m) == [1]
    m._buf = bytes(m._buf[:a + 32 + 10 + 3]) + b'\0' * 100; m.version = 'AC1015'; assert AD._page_padding_nonzero(m) is None


def test_unreferenced_bytes_behind_the_encrypted_header_block_are_part_of_the_preamble_snapshot():
    from savegate.adapters import _preamble_snap
    a = bytes(make())
    for off in (0xEC, 0xF5, 0xFF):
        b = bytearray(a); b[off] ^= 4; assert _preamble_snap(bytes(b)) != _preamble_snap(a), hex(off)
    b = bytearray(a); b[0x100] ^= 4; assert _preamble_snap(bytes(b)) == _preamble_snap(a)


def test_r2000_regions_outside_the_objects_must_not_change():
    import struct, savegate.adapters as AD
    AD.DwgAdapter()
    import dwgfmt, dwghdr
    class M:
        def __init__(s, buf): s.version = 'AC1015'; s._buf = buf
    def build(pre=b'P' * 40, cls=b'C' * 30, hvars=None):
        hv = hvars or (bytes(16) + struct.pack('<I', 30) + bytes(range(30)) + b'\0\0')
        hv = bytearray(hv); c = dwgfmt.crc16(bytes(hv[16:20 + 30]), 0xC0C1); hv[50:52] = struct.pack('<H', c)
        locs = 0x19 + 9 * 2 + 2
        b = bytearray(locs) + pre
        o0 = len(b); b += hv; o1 = len(b); b += cls
        b[:6] = b'AC1015'; struct.pack_into('<I', b, 0x15, 2)
        struct.pack_into('<BII', b, 0x19, 0, o0, len(hv)); struct.pack_into('<BII', b, 0x19 + 9, 1, o1, len(cls))
        return bytes(b)
    a = build()
    saved = dwghdr.decode_header
    dwghdr.decode_header = lambda h, v, s=0: {'_seedpos': (20 + 10) * 8}      # HANDSEED at section byte 30 -> data index 10
    try:
        assert AD._r2000_regions_changed(M(a), M(a)) == []
        b = bytearray(a); b[0x19 + 9 * 2 + 2 + 5] ^= 1; assert 'pre-header area' in AD._r2000_regions_changed(M(a), M(bytes(b)))
        b = bytearray(a); b[-3] ^= 1; assert 'classes section' in AD._r2000_regions_changed(M(a), M(bytes(b)))
        b = bytearray(a); b[0x0B] ^= 1; assert 'file header' in AD._r2000_regions_changed(M(a), M(bytes(b)))
        b = bytearray(a); b[0x0D] ^= 1; assert 'file header' in AD._r2000_regions_changed(M(a), M(bytes(b)))           # image seeker cannot move: the area behind it is carried unchanged
    finally:
        dwghdr.decode_header = saved


def test_r2000_second_header_only_its_pointer_fields_and_crc_may_change():
    import struct, savegate.adapters as AD
    AD.DwgAdapter()
    import dwgfmt, dwghdr
    class M:
        def __init__(s, buf): s.version = 'AC1015'; s._buf = buf
    sent = bytes.fromhex('d47b21ce28939fbf53244009123caa01')
    def build(gap):
        hv = bytearray(16) + struct.pack('<I', 30) + bytes(30) + b'\0\0'
        c = dwgfmt.crc16(bytes(hv[16:50]), 0xC0C1); hv[50:52] = struct.pack('<H', c)
        locs = 0x19 + 9 * 5 + 2
        b = bytearray(locs) + b'P' * 8
        o0 = len(b); b += hv; o1 = len(b); b += b'C' * 20; o2 = len(b); b += b'M' * 30; g0 = len(b)
        gap = bytearray(gap)
        def put32(pbit, v):
            for k in range(32):
                bit = (v >> (8 * (k // 8) + 7 - (k % 8))) & 1; pos = pbit + k
                if bit: gap[pos >> 3] |= 0x80 >> (pos & 7)
                else: gap[pos >> 3] &= ~(0x80 >> (pos & 7)) & 0xFF
        for pb, v in ((162, g0), (352, o0), (386, len(hv)), (428, o1), (462, 20), (504, o2), (538, 30)): put32(pb, v)
        b += gap; o4 = len(b); b += b'\0' * 4
        b[:6] = b'AC1015'; struct.pack_into('<I', b, 0x15, 5)
        for i, (n, s_, z) in enumerate([(0, o0, len(hv)), (1, o1, 20), (2, o2, 30), (3, 0, 0), (4, o4, 4)]): struct.pack_into('<BII', b, 0x19 + 9 * i, n, s_, z)
        return bytes(b)
    gap = sent + struct.pack('<I', 129) + bytes(129)
    a = build(gap); saved = dwghdr.decode_header
    dwghdr.decode_header = lambda h, v, s=0: {'_seedpos': 30 * 8}
    try:
        base = len(a) - 4 - len(gap)
        assert AD._r2000_regions_changed(M(a), M(a)) == []
        b = bytearray(a); b[base + 162 // 8 + 1] ^= 1; assert 'second header pointers' in AD._r2000_regions_changed(M(a), M(bytes(b)))      # a pointer field that no longer matches the locator table
        b = bytearray(a); b[base + 100] ^= 1; assert 'second header' in AD._r2000_regions_changed(M(a), M(bytes(b)))   # anything else
    finally:
        dwghdr.decode_header = saved


def test_named_dimension_block_geometry_belongs_to_the_dimension():
    import savegate.adapters as AD
    assert AD._is_dim_block_ref({'block_ref': '*D5', 'kind': 'DIM_LINEAR'})
    assert AD._is_dim_block_ref({'block_ref': 'DIMBLOCK60-CCW07', 'kind': 'DIM_LINEAR'})
    assert not AD._is_dim_block_ref({'block_ref': 'DOOR', 'kind': 'INSERT'})          # an ordinary insert's block is not owned by the insert
    assert not AD._is_dim_block_ref({'kind': 'DIM_LINEAR'})
    assert not AD._is_dim_block_ref({'block_ref': '', 'kind': 'LINE'})


def test_r2000_undeclared_changes_are_limited_to_the_chain_neighbours_of_declared_add_delete():
    from savegate.adapters import DwgAdapter
    class O:
        def __init__(s, raw): s.raw = raw; s.type = 19; s.data_bit = 0
    class M:
        def __init__(s, raws): s.version = 'AC1015'; s.objs = {h: O(r) for h, r in raws.items()}; s.blocks = {}
        def entities(s): return []
    a = DwgAdapter(); a.owners = {}; a.bheaders = {}; a.dimobjs = {}
    src = {h: b'\x01\x01\x00\x00\x00' for h in (0x40, 0x41, 0x42, 0x43)}
    def run(changed, man):
        out = dict(src)
        for h in changed: out[h] = b'\x01\x01\x00\x00\x09'
        a._pair = (M(src), M(out)); return [x for x in a.extra_checks(man) if x[0] == 'undeclared_object_bytes']
    assert run([0x40], {'modified': []}) != []                    # nothing added/deleted: no neighbour excuse
    assert run([0x40, 0x41], {'deleted': [0x99]}) == []           # two neighbours of one delete
    assert run([0x40, 0x41, 0x42], {'deleted': [0x99]}) != []     # a third one is not a neighbour
