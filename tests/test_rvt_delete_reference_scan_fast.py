"""c5x-rvtgap: the delete-reference scan reads the reader's record cache instead of tracing every element (1 hour on a 28 MB project, 13 s now). Parity with the full trace on the Autodesk
Snowdon Towers Structural 2024 sample (full scan: text note 916133 and instance 664857 have no referrer, level 32567 has 43, instance 730441 has 2)."""
import os, sys, time, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no Autodesk sample')


def _scan(el):
    import savegate.adapters as A
    a = A.RvtAdapter(); a._src_buf = open(SRC, 'rb').read(); t = time.time()
    r = a._delete_reference_checks({'deleted': ['el:%d' % el]}); return r, time.time() - t


@pytest.mark.parametrize('el', [916133, 664857])
def test_unreferenced_elements_pass(el):
    r, dt = _scan(el); assert r == [] and dt < 120


@pytest.mark.parametrize('el,n', [(32567, None), (730441, 2)])
def test_referenced_elements_are_refused_with_the_known_referrers(el, n):
    r, dt = _scan(el); assert len(r) == 1 and r[0][0] == 'dangling_after_delete' and dt < 120
    if n is not None: assert '[585174, 795061]' in r[0][1]
