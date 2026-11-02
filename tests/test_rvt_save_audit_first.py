"""rvt_save.save_string_edits audits the container BEFORE the writer lab opens the file (c4x-dwgreadfuzz 207). Synthetic CFB with a FAT cycle; needs rvt_integrity.py (next to the write-lab); no numpy needed because the audit raises first."""
import os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LAB = os.path.expanduser('~/rvt-research')
sys.path.insert(0, LAB)
HAVE = os.path.exists(os.path.join(LAB, 'rvt_integrity.py')) and os.path.exists(os.path.join(LAB, 'test_rvt_ole_hostile.py'))


@unittest.skipUnless(HAVE, 'rvt-research lab not present')
class AuditFirst(unittest.TestCase):
    def test_fat_cycle_source_is_refused_before_editor(self):
        import savegate as sg
        from savegate import rvt_save
        src = open(os.path.join(LAB, 'test_rvt_ole_hostile.py')).read().split("assert run('intact'")[0]
        ns = {}; exec(src, ns)
        d = tempfile.mkdtemp(); p = os.path.join(d, 'x.rvt'); data = ns['build'](fat_edit=lambda f: f.__setitem__(3, 3)); open(p, 'wb').write(data)
        with self.assertRaises(sg.VerifyFailed) as cm:
            rvt_save.save_string_edits(p, [(1, 'Name', 'x')])
        self.assertIn('container problem', str(cm.exception))
        self.assertEqual(open(p, 'rb').read(), data)         # untouched


if __name__ == '__main__':
    unittest.main()
