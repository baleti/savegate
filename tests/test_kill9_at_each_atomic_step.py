"""c7x-rvtread2 201: SIGKILL at each atomic step leaves the target either fully OLD or fully NEW (never partial); a following save sweeps the orphan temp/lock files."""
import os, sys, signal, subprocess, pytest
pytestmark = pytest.mark.skipif(sys.platform == 'win32', reason='POSIX SIGKILL')
CHILD = '''
import os, sys, signal
import savegate as sg
from savegate import atomic
from savegate.adapters import RawAdapter
step, p = sys.argv[1], sys.argv[2]
atomic._hook = lambda n: os.kill(os.getpid(), signal.SIGKILL) if n == step else None
doc = sg.open_doc(p, RawAdapter(), sg.Config(allow_overwrite=True, require_gate=False))
sg.save(doc, b"N" * 80000, {"modified": ["file"]})
'''

@pytest.mark.parametrize('step,expect', [('tmp_written', 'old'), ('before_replace', 'old'), ('after_replace', 'new')])
def test_kill9(tmp_path, step, expect):
    import savegate as sg
    from savegate.adapters import RawAdapter
    p = str(tmp_path / 'f.bin'); orig = os.urandom(60000); open(p, 'wb').write(orig)
    root = os.path.dirname(os.path.dirname(sg.__file__))
    r = subprocess.run([sys.executable, '-c', CHILD, step, p], env=dict(os.environ, PYTHONPATH=root))
    assert r.returncode == -9
    assert open(p, 'rb').read() == (orig if expect == 'old' else b'N' * 80000)
    doc = sg.open_doc(p, RawAdapter(), sg.Config(allow_overwrite=True, require_gate=False))
    sg.save(doc, b'M' * 70000, {'modified': ['file']})
    assert open(p, 'rb').read() == b'M' * 70000
    assert sorted(os.listdir(str(tmp_path))) == ['.savegate', 'f.bin']
