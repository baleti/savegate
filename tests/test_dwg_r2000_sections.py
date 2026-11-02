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

    def test_other_versions_ignored(self):
        self.assertEqual(prob(b'AC1032' + bytes(100)), [])


if __name__ == '__main__':
    unittest.main()
