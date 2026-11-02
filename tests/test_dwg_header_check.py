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
