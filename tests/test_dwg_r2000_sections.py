"""_r2000_section_problems: AC1015 header-variable/class section CRC and end sentinel (c4x-dwgreadfuzz 191). Synthetic buffer, needs the DWG lib (dwgfmt) on the path."""
import os, struct, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LIB = os.environ.get('SAVEGATE_DWG_LIB') or os.path.expanduser('~/dwg-write')
if os.path.isdir(LIB): sys.path.insert(0, LIB)
try:
    import dwgfmt as F
    from savegate.adapters import _r2000_section_problems as prob
except ImportError:
    F = None
SENT = bytes([0x8D, 0xA1, 0xC4, 0xB8, 0xC4, 0xA9, 0xF8, 0xC5, 0xC0, 0xDC, 0xF4, 0x5F, 0xE7, 0xCF, 0xB6, 0x8A])


def sec(data):
    s = SENT + struct.pack('<I', len(data)) + data
    return s + struct.pack('<H', F.crc16(s[16:], 0xC0C1)) + bytes(x ^ 0xFF for x in SENT)


def build(hv=bytes(range(30)), cl=bytes(range(50))):
    s0, s1 = sec(hv), sec(cl); a0 = 0x60; a1 = a0 + len(s0)
    h = bytearray(b'AC1015' + bytes(0x60 - 6)); struct.pack_into('<I', h, 0x15, 2)
    struct.pack_into('<BII', h, 0x19, 0, a0, len(s0)); struct.pack_into('<BII', h, 0x19 + 9, 1, a1, len(s1))
    return bytes(h) + s0 + s1, a0, a1


@unittest.skipIf(F is None, 'dwg lib not found')
class R2000Sections(unittest.TestCase):
    def test_clean(self):
        self.assertEqual(prob(build()[0]), [])

    def test_every_byte_flip_is_reported(self):
        buf, a0, a1 = build(); n = 0
        for base, size in ((a0, 30), (a1, 50)):
            for off in range(16, 22 + size + 16):
                if 16 <= off < 20: continue   # size field: section bounds, not CRC
                m = bytearray(buf); m[base + off] ^= 0x10
                self.assertTrue(prob(bytes(m)), (base, off)); n += 1
        self.assertGreater(n, 100)

    def test_lib_without_reader_functions_fails_closed(self):
        import types
        real = sys.modules['dwgfmt']
        sys.modules['dwgfmt'] = types.ModuleType('dwgfmt')
        try: r = prob(build()[0])
        finally: sys.modules['dwgfmt'] = real
        self.assertTrue(r and 'unreadable' in r[0], r)

    def test_other_versions_ignored(self):
        self.assertEqual(prob(b'AC1032' + bytes(100)), [])


@unittest.skipIf(F is None, 'dwg lib not found')
class R2000Preview(unittest.TestCase):
    @staticmethod
    def build(sizes=(80, 200)):
        from savegate.adapters import _r2000_preview_problems as pp
        SENT = bytes.fromhex('1f256d07d43628289d57ca3f9d44102b')
        cnt = len(sizes); body = []
        pos = 0x60 + 21 + 9 * cnt; ents = b''
        for i, sz in enumerate(sizes):
            code = 1 if i == 0 else 2
            ents += struct.pack('<BII', code, pos, sz); body.append(struct.pack('<IiiH', 40, 4, 4, 1).ljust(sz, b'\0') if code == 2 else bytes(sz)); pos += sz
        n = 1 + 9 * cnt + sum(sizes)
        blk = SENT + struct.pack('<I', n) + bytes([cnt]) + ents + b''.join(body) + bytes(x ^ 0xFF for x in SENT)
        hdr = bytearray(b'AC1015' + bytes(0x60 - 6)); struct.pack_into('<I', hdr, 0x0D, 0x60)
        return bytes(hdr) + blk, pp

    def test_clean_and_no_preview(self):
        b, pp = self.build(); self.assertEqual(pp(b), [])
        h = bytearray(b); struct.pack_into('<I', h, 0x0D, 0); self.assertEqual(pp(bytes(h)), [])

    def test_structural_damage_reported(self):
        b, pp = self.build()
        for off, what in ((0x60, 'start sentinel'), (0x60 + 16, 'size field'), (0x60 + 21 + 1, 'entry start'), (len(b) - 1, 'end sentinel'), (0x60 + 21 + 18 + 80, 'BMP biSize')):
            m = bytearray(b); m[off] ^= 0x01; self.assertTrue(pp(bytes(m)), what)

    def test_pixel_flip_is_not_detectable(self):
        b, pp = self.build(); m = bytearray(b); m[0x60 + 21 + 18 + 80 + 30] ^= 0xFF; self.assertEqual(pp(bytes(m)), [])


if __name__ == '__main__':
    unittest.main()
