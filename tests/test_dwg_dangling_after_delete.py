"""_dangling_after_delete (c4x-dwgreadfuzz 225): a surviving object that still names a handle deleted from the output is reported; pre-existing dangling pointers and
declared relinks are not. Synthetic models + a stub dwgmodel.resolve_handles (reads the 'refs' attribute of each fake object)."""
import os, sys, types, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Dangling(unittest.TestCase):
    def setUp(self):
        self._saved = sys.modules.get('dwgmodel')
        stub = types.ModuleType('dwgmodel'); stub.resolve_handles = lambda o: [(5, v) for v in o.refs]
        sys.modules['dwgmodel'] = stub
        from savegate.adapters import _dangling_after_delete
        self.f = _dangling_after_delete

    def tearDown(self):
        if self._saved is None: sys.modules.pop('dwgmodel', None)
        else: sys.modules['dwgmodel'] = self._saved

    @staticmethod
    def model(**objs): return types.SimpleNamespace(objs={h: types.SimpleNamespace(refs=r) for h, r in objs.items()})

    def test_surviving_reference_to_deleted_handle(self):
        ms = types.SimpleNamespace(objs={1: types.SimpleNamespace(refs=[2]), 2: types.SimpleNamespace(refs=[]), 3: types.SimpleNamespace(refs=[])})
        mo = types.SimpleNamespace(objs={1: types.SimpleNamespace(refs=[2]), 3: types.SimpleNamespace(refs=[])})   # 2 deleted, 1 still names it
        self.assertEqual(self.f(ms, mo), [(1, 2)])

    def test_relinked_neighbour_is_fine(self):
        ms = types.SimpleNamespace(objs={1: types.SimpleNamespace(refs=[2]), 2: types.SimpleNamespace(refs=[])})
        mo = types.SimpleNamespace(objs={1: types.SimpleNamespace(refs=[])})
        self.assertEqual(self.f(ms, mo), [])

    def test_preexisting_dangling_pointer_is_not_new(self):
        ms = types.SimpleNamespace(objs={1: types.SimpleNamespace(refs=[99]), 2: types.SimpleNamespace(refs=[])})      # 99 never existed
        mo = types.SimpleNamespace(objs={1: types.SimpleNamespace(refs=[99])})
        self.assertEqual(self.f(ms, mo), [])

    def test_nothing_deleted(self):
        ms = types.SimpleNamespace(objs={1: types.SimpleNamespace(refs=[2]), 2: types.SimpleNamespace(refs=[])})
        self.assertEqual(self.f(ms, ms), [])


if __name__ == '__main__':
    unittest.main()
