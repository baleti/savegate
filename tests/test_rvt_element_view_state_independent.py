"""c4x-rvtgap: the element view of a file must not depend on what the process did before (import order, an earlier save) or on the worker count. Autodesk 2024/2026 sample families."""
import os, sys, subprocess, glob, pytest
PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAM = [f for y in (2024, 2026) for f in glob.glob(os.path.expanduser('~/rvt-research/**/racbasicsamplefamily-%d.rfa' % y), recursive=True)[:1]]
CODE = """
import sys, os, hashlib, tempfile
sys.path.insert(0, %r)
from savegate import adapters, core, rvt_elements as R
b0 = open(%r, 'rb').read()
if %r == 'after':
    d = tempfile.mkdtemp(); p = d + '/in.rfa'; open(p, 'wb').write(b0)
    core.save_as(core.open_doc(p, adapters.RvtAdapter(), journal=False), b0, d + '/out.rfa'); R._elements(open(d + '/out.rfa', 'rb').read())
e = R._elements(b0); print(hashlib.sha1(repr(sorted((str(k), repr(v)) for k, v in e.items())).encode()).hexdigest(), len(e))
"""
def _run(f, mode, **env):
    e = dict(os.environ); e.update(env)
    return subprocess.run([sys.executable, '-c', CODE % (PKG, f, mode)], env=e, capture_output=True, text=True, timeout=600).stdout.strip().splitlines()[-1]

@pytest.mark.skipif(not FAM, reason='no Autodesk sample families')
@pytest.mark.parametrize('f', FAM)
def test_view_is_identical_fresh_after_a_save_and_with_one_worker(f):
    a = _run(f, 'fresh'); assert a.endswith(' 1975') or int(a.split()[1]) > 100
    assert _run(f, 'after') == a
    assert _run(f, 'fresh', SAVEGATE_RVT_WORKERS='1') == a
