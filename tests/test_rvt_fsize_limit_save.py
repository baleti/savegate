"""c5x-rvtgap 127: a write that fails part way (RLIMIT_FSIZE in a child process stands in for a full disk): the save must refuse, the original stays byte-identical, no temp file is left."""
import os, sys, shutil, subprocess, pytest
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')

CHILD = r'''
import os, sys, resource, signal
signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research'), sys.argv[3]]
import wledit, savegate as sg
t, o = sys.argv[1], sys.argv[2]
new = open(o, 'rb').read()
doc = sg.open_doc(t, None, sg.Config(allow_overwrite=True, require_gate=False, journal_dir=os.path.dirname(t) + '_j'))
resource.setrlimit(resource.RLIMIT_FSIZE, (int(sys.argv[4]), int(sys.argv[4])))
try:
    r = sg.save(doc, new, {'modified': ['stream:Partitions/67', 'el:7']}); print('RESULT ok', r.ok)
except sg.SaveError as e: print('RESULT refused', str(e)[:100])
except Exception as e: print('RESULT RAW', type(e).__name__, str(e)[:100])
'''


@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
@pytest.mark.parametrize('limit', [1000, 100000, 300000])
def test_fsize(tmp_path, limit):
    sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
    import wledit
    d = tmp_path / 'd'; d.mkdir(); t = d / 'x.rfa'; shutil.copy(F, t)
    ed = wledit.Editor(str(t)); ed.set_strings([(7, 'FillPattern.m_name', 'Edited')]); o = str(tmp_path / 'o.bin'); ed.save(o)
    orig = t.read_bytes()
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    p = subprocess.run([sys.executable, '-c', CHILD, str(t), o, repo, str(limit)], capture_output=True, text=True, timeout=200)
    out = [l for l in p.stdout.splitlines() if l.startswith('RESULT')]
    assert out, p.stdout + p.stderr
    assert 'RAW' not in out[0], out[0]
    assert t.read_bytes() == orig and 'refused' in out[0], out[0]
    left = [n for n in os.listdir(d) if n not in ('x.rfa', '.savegate') and not n.endswith('savegate-lock')]
    assert left == [], left
