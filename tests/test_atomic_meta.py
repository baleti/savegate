"""Replacing a file by rename must not lose its extended attributes or (when possible) its group (synthetic)."""
import os, sys, tempfile, shutil, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from savegate import atomic


@unittest.skipUnless(hasattr(os, 'setxattr'), 'no xattr support on this platform')
class Meta(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(dir=os.path.expanduser('~/.sgtmp') if os.path.isdir(os.path.expanduser('~/.sgtmp')) else None); self.addCleanup(shutil.rmtree, self.d, True)
        self.dest = os.path.join(self.d, 'a.dwg'); self.tmp = os.path.join(self.d, '.a.tmp')
        open(self.dest, 'wb').write(b'old'); open(self.tmp, 'wb').write(b'new')

    def test_xattr_kept(self):
        try: os.setxattr(self.dest, 'user.sgtest', b'label-7')
        except OSError: self.skipTest('file system without user xattrs')
        atomic.commit_temp(self.tmp, self.dest, copy_mode_from=self.dest)
        self.assertEqual(open(self.dest, 'rb').read(), b'new'); self.assertEqual(os.getxattr(self.dest, 'user.sgtest'), b'label-7')

    def test_group_kept(self):
        other = [g for g in os.getgroups() if g != os.stat(self.dest).st_gid]
        if not other: self.skipTest('no second group for this user')
        os.chown(self.dest, -1, other[0])
        atomic.commit_temp(self.tmp, self.dest, copy_mode_from=self.dest)
        self.assertEqual(os.stat(self.dest).st_gid, other[0])


if __name__ == '__main__': unittest.main()
