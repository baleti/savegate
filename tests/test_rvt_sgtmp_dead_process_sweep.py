"""c4x-rvtgap 197: scratch copies live in savegate-<pid>-* dirs; dirs of dead pids are swept, live ones are not."""
import os, subprocess, sys, tempfile
PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def test_dead_pid_dir_is_swept_and_live_dir_kept(tmp_path):
    env = dict(os.environ); env['TMPDIR'] = str(tmp_path)
    p = subprocess.Popen([sys.executable, '-c', 'import os; print(os.getpid())'], stdout=subprocess.PIPE, text=True); dead = int(p.communicate()[0]); p.wait()
    d_dead = tmp_path / ('savegate-%d-abc' % dead); d_dead.mkdir(); (d_dead / 'x.rvt').write_bytes(b'x')
    live = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); d_live = tmp_path / ('savegate-%d-abc' % live.pid); d_live.mkdir()
    try:
        code = "import sys; sys.path.insert(0, %r)\nfrom savegate import sgtmp\nd = sgtmp.tmpdir(); print(d)\n" % PKG
        out = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True, timeout=60).stdout.strip()
        assert out.startswith(str(tmp_path)) and 'savegate-' in out
        assert not d_dead.exists() and d_live.exists()
        assert not os.path.exists(out)        # own dir removed at exit
    finally: live.kill()
