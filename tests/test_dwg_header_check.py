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
    for off in (0x0B, 0x0D, 0x13, 0x20, 0x30, 0x7F):
        b = bytearray(a); b[off] ^= 1
        assert _preamble_snap(bytes(b)) != _preamble_snap(a), off
    b = bytearray(a); b[0x80] ^= 1; assert _preamble_snap(bytes(b)) == _preamble_snap(a)   # encrypted block is covered by _header_problems, not this
    assert _preamble_snap(b'AC1015' + bytes(300)) is None
