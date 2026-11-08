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

SAVE_CODE = """
import sys, os, shutil, tempfile
sys.path.insert(0, %r); sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
import savegate as sg, wledit
SRC = %r
d = tempfile.mkdtemp(); ed = wledit.Editor(SRC); ed.set_strings([(7, 'FillPattern.m_name', 'Cache probe')]); o = d + '/o.rfa'; ed.save(o); new = open(o, 'rb').read()
for f in os.listdir(os.environ['RVT_CORE_CACHE']): os.remove(os.path.join(os.environ['RVT_CORE_CACHE'], f))      # drop what the editor itself wrote for the stable source path
cur = d + '/c.rfa'; shutil.copy(SRC, cur)
print(sg.save(sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False)), new, {'modified': ['stream:Partitions/67', 'el:7']}).ok)
"""
def test_full_gated_save_leaves_no_cache_files(tmp_path):
    src = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
    if not os.path.exists(src): pytest.skip('no sample')
    c = tmp_path / 'core'; c.mkdir(); env = dict(os.environ); env['RVT_CORE_CACHE'] = str(c)
    r = subprocess.run([sys.executable, '-c', SAVE_CODE % (PKG, src)], env=env, capture_output=True, text=True, timeout=600)
    assert r.stdout.strip().endswith('True'), r.stderr[-400:]
    assert os.listdir(str(c)) == [], os.listdir(str(c))

def test_python_fallback_pickles_are_removed_too(tmp_path):
    src = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa'); xd = os.path.expanduser('~/rvt-research/xcache')
    if not (os.path.exists(src) and os.path.isdir(xd)): pytest.skip('no sample')
    c = tmp_path / 'core'; c.mkdir(); env = dict(os.environ); env['RVT_CORE_CACHE'] = str(c); env['RVT_NOFAST'] = '1'
    code = SAVE_CODE.replace("for f in os.listdir(os.environ['RVT_CORE_CACHE'])", "xd = %r\nbefore = set(os.listdir(xd))\nfor f in os.listdir(os.environ['RVT_CORE_CACHE'])" % xd)
    code += "\nprint('LEAK', sorted(set(os.listdir(%r)) - before))\n" % xd
    r = subprocess.run([sys.executable, '-c', code % (PKG, src)], env=env, capture_output=True, text=True, timeout=900)
    assert 'LEAK []' in r.stdout, (r.stdout[-300:], r.stderr[-300:])
