"""c7x-rvtread2 649: SIGINT / SIGTERM delivered to a process in the middle of an in-place save (2024 Autodesk sample family, random time 0.3-2.5 s):
the target is always EXACTLY the old or the new bytes (never mixed) and the next save works. Neither signal leaves .sgtmp/.part debris.
SIGTERM/SIGHUP/SIGQUIT used to leave the .sgtmp (12 of 14); atomic.py now removes pending temp files (650), so no debris is asserted for both."""
import os, sys, shutil, subprocess, signal, time, random, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no sample')
CHILD = '''import sys,os
sys.path[:0]=[os.path.expanduser(p) for p in ('~/rvt-research/write-lab','~/rvt-research','~/src/savegate')]
import savegate as sg
t,n,pn=sys.argv[1:4]
sg.save(sg.open_doc(t,None,sg.Config(allow_overwrite=True,require_gate=False)),open(n,'rb').read(),{'modified':['stream:'+pn,'el:7']})
'''
@pytest.mark.parametrize('sig', [signal.SIGINT, signal.SIGTERM])
def test_signal(tmp_path, sig):
    import wledit, savegate as sg
    ed = wledit.Editor(SRC); pn = ed.trace(7)[0]; ed.set_strings([(7, 'FillPattern.m_name', 'Signal probe')]); nf = str(tmp_path / 'new.x'); ed.save(nf)
    new = open(nf, 'rb').read(); old = open(SRC, 'rb').read(); env = dict(os.environ, SAVEGATE_MEM_FACTOR='0'); rnd = random.Random(649)
    for r in range(6):
        d = tmp_path / ('r%d' % r); d.mkdir(); t = str(d / 'a.rfa'); shutil.copy(SRC, t)
        p = subprocess.Popen([sys.executable, '-c', CHILD, t, nf, pn], env=env, stderr=subprocess.DEVNULL); time.sleep(rnd.uniform(0.3, 2.5)); p.send_signal(sig); p.wait()
        b = open(t, 'rb').read(); assert b in (old, new), 'MIXED bytes after %s' % sig.name
        if True: assert not [x for x in os.listdir(d) if x.endswith(('.sgtmp', '.part'))]
        sg.save(sg.open_doc(t, None, sg.Config(allow_overwrite=True, require_gate=False)), new, {'modified': ['stream:' + pn, 'el:7']}) if b == old else None
        assert open(t, 'rb').read() == new
