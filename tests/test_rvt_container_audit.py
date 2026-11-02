"""RvtAdapter._damage reports container-level damage via rvt_integrity.audit (c4x-dwgreadfuzz 190).
Needs numpy + the writer lab (remote-host) and one real or sample .rvt in $SAVEGATE_RVT_SAMPLE; skipped elsewhere. A FAT cycle is injected by pointing a stream sector at itself."""
import os, struct, sys, unittest
SAMPLE = os.environ.get('SAVEGATE_RVT_SAMPLE')
try:
    import numpy  # noqa
    HAVE = bool(SAMPLE) and os.path.isfile(SAMPLE)
except ImportError:
    HAVE = False


@unittest.skipUnless(HAVE, 'needs numpy and SAVEGATE_RVT_SAMPLE')
class ContainerAudit(unittest.TestCase):
    def test_fat_loop_is_reported(self):
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from savegate.adapters import RvtAdapter
        import olefile
        a = RvtAdapter(); b = open(SAMPLE, 'rb').read()
        self.assertEqual([x for x in a._damage(b) if x.startswith('container ')], [])
        o = olefile.OleFileIO(SAMPLE); ss = o.sectorsize
        fats = [x for x in struct.unpack_from('<109I', b, 0x4C) if x != 0xFFFFFFFF]
        # first chain link of the first long regular stream: make its FAT entry point to itself
        s = next(o.direntries[i].isectStart for i in range(len(o.direntries)) if o.direntries[i] and o.direntries[i].entry_type == 2 and o.direntries[i].size >= o.minisectorcutoff)
        fat_sec = fats[s // (ss // 4)]; pos = (fat_sec + 1) * ss + 4 * (s % (ss // 4))
        m = bytearray(b); struct.pack_into('<I', m, pos, s)
        errs = a._damage(bytes(m))
        self.assertTrue([x for x in errs if x.startswith('container chains')], errs)


if __name__ == '__main__':
    unittest.main()
