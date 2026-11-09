"""c4x-rvtgap: SIGKILL of a REAL RVT gated save (RvtAdapter, element view on) at each atomic step and during verification: target fully OLD or fully NEW, never partial; the next save works and leaves only file + .savegate; dead-pid scratch dirs get swept."""
import os, sys, signal, subprocess, shutil, time, glob, pytest
pytestmark = pytest.mark.skipif(sys.platform == 'win32', reason='POSIX SIGKILL')
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
CHILD = '''
import os, sys, signal, time
sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
import savegate as sg
from savegate import atomic
step, p, newp = sys.argv[1], sys.argv[2], sys.argv[3]
if step != 'verify': atomic._hook = lambda n: os.kill(os.getpid(), signal.SIGKILL) if n == step else None
else:
    import savegate.core as C; real = C._verify
    def slow(doc, back, manifest): os.kill(os.getpid(), signal.SIGKILL)       # die inside verification, scratch dir alive
    C._verify = slow
doc = sg.open_doc(p, None, sg.Config(allow_overwrite=True, require_gate=False))
sg.save(doc, open(newp, "rb").read(), {"modified": ["stream:Partitions/67", "el:7"]})
'''
@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
@pytest.mark.parametrize('step,expect', [('verify', 'old'), ('tmp_written', 'old'), ('before_replace', 'old'), ('after_replace', 'new')])
def test_kill9_rvt(tmp_path, step, expect):
    import savegate as sg, wledit
    f = str(tmp_path / 'a.rfa'); shutil.copy(F, f); old = open(f, 'rb').read()
    ed = wledit.Editor(f); ed.set_strings([(7, 'FillPattern.m_name', 'Kill probe')]); n = str(tmp_path / 'n.tmp'); ed.save(n); new = open(n, 'rb').read()
    root = os.path.dirname(os.path.dirname(sg.__file__))
    r = subprocess.run([sys.executable, '-c', CHILD, step, f, n], env=dict(os.environ, PYTHONPATH=root + os.pathsep + os.environ.get('PYTHONPATH', '')), timeout=300)
    assert r.returncode == -9
    got = open(f, 'rb').read(); assert got == (old if expect == 'old' else new), 'partial or unexpected content'
    os.remove(n)
    doc = sg.open_doc(f, None, sg.Config(allow_overwrite=True, require_gate=False))
    ed2 = wledit.Editor(f); ed2.set_strings([(7, 'FillPattern.m_name', 'After kill')]); n2 = str(tmp_path / 'n2.tmp'); ed2.save(n2); new2 = open(n2, 'rb').read(); os.remove(n2)
    from savegate import sgtmp; sgtmp._LAST[0] = 0.0        # a long-lived host process: the sweep interval has elapsed
    sg.save(doc, new2, {'modified': ['stream:Partitions/67', 'el:7']})
    assert open(f, 'rb').read() == new2
    assert sorted(os.listdir(tmp_path)) == ['.savegate', 'a.rfa'], os.listdir(tmp_path)
    import tempfile
    for d in glob.glob(os.path.join(tempfile.gettempdir(), 'savegate-*')):
        try: pid = int(os.path.basename(d).split('-')[1])
        except (ValueError, IndexError): continue
        try: os.kill(pid, 0)
        except ProcessLookupError: raise AssertionError('scratch dir of a dead process survived the next save: ' + d)
        except PermissionError: pass
