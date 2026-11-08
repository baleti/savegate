"""c7x-rvtread2 item 388: rotate_instance must turn FamilyInstance.m_zAxis with the matrix (10 of 1432 instances in the Snowdon Structural 2024 sample have a horizontal local z). SGPKG = tree with c7x-rvtread2-finite-and-delete-once.diff."""
import os, sys, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research')); sys.path.insert(0, os.environ.get('SGPKG', os.path.expanduser('~/src/savegate')))
S = os.path.expanduser('~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt')
pytestmark = pytest.mark.skipif(not os.path.exists(S), reason='public Autodesk sample missing')

def _fields(path, eid):
    import rvt_xcache
    f = rvt_xcache.get_x_ro(path)['recs'][(eid, 'FamilyInstance')]['fields']
    def find(v, key, d=0):
        if d > 9: return
        if isinstance(v, dict):
            for k, q in v.items():
                if k == key: yield q
                else: yield from find(q, key, d + 1)
        elif isinstance(v, (list, tuple)):
            for q in v: yield from find(q, key, d + 1)
    return [float(x) for x in next(find(f, 'm_zAxis'))], [[float(x) for x in r] for r in next(find(f, 'm_3x3'))]

def test_zaxis_matches_matrix_third_column(tmp_path):
    from savegate import rvt_writer_ops as WO
    o = str(tmp_path / 'o.rvt'); WO.run(S, [{'op': 'rotate_instance', 'id': 642543, 'deg': 90.0}], o)
    z, m = _fields(o, 642543)
    col3 = [m[0][2], m[1][2], m[2][2]]
    assert all(abs(a - b) < 1e-9 for a, b in zip(z, col3)), (z, col3)
