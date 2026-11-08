"""c4x-rvtgap 191: gate reads of temp copies must not leave reader cache entries behind (never reused, 80 MB per scan of a 28 MB project, ~/.cache/rvt-core reached 70-86 GB)."""
import os, sys, glob, subprocess, pytest
PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAM = glob.glob(os.path.expanduser('~/rvt-research/**/racbasicsamplefamily-2024.rfa'), recursive=True)
pytestmark = pytest.mark.skipif(not FAM, reason='no Autodesk sample family')
CODE = """
import sys, os
sys.path.insert(0, %r)
from savegate import rvt_elements as R, adapters as A
b = open(%r, 'rb').read()
R._elements(b)
a = A.RvtAdapter(); a._src_buf = b; a._delete_reference_checks({'deleted': ['el:11']})
"""
def test_no_cache_files_remain(tmp_path):
    c = tmp_path / 'core'; c.mkdir()
    env = dict(os.environ); env['RVT_CORE_CACHE'] = str(c)
    r = subprocess.run([sys.executable, '-c', CODE % (PKG, FAM[0])], env=env, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr[-500:]
    left = [os.path.basename(x) for x in glob.glob(str(c / '*'))]
    assert left == [], left
