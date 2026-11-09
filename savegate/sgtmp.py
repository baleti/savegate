"""c4x-rvtgap 197: per-process temp directory for the gate's scratch copies. A killed process (SIGKILL, OOM) used to leave tmp*.rvt files in /tmp (a RAM-backed tmpfs on remote-host; 123 files / 300 MB found). Now: <tmp>/savegate-<pid>-<random>/; at first use, directories of dead pids are removed."""
import os, re, shutil, tempfile
_DIR = {}
_LAST = [0.0]      # time of the last sweep of dead-pid dirs
SWEEP_EVERY = 60.0
def _alive(pid):
    try: os.kill(pid, 0); return True
    except ProcessLookupError: return False
    except PermissionError: return True
    except OSError: return False
def _sweep(base):
    try:
        for n in os.listdir(base):
            m = re.match(r'^savegate-(\d+)-', n)
            if m and int(m.group(1)) != os.getpid() and not _alive(int(m.group(1))) and os.path.isdir(os.path.join(base, n)):
                shutil.rmtree(os.path.join(base, n), ignore_errors=True)
    except OSError: pass
def tmpdir():
    import time
    d = _DIR.get(os.getpid()); base = tempfile.gettempdir()
    if time.time() - _LAST[0] > SWEEP_EVERY: _LAST[0] = time.time(); _sweep(base)      # c4x-rvtgap: a long-lived host re-sweeps dirs of workers killed since (was: once per process)
    if d and os.path.isdir(d): return d
    d = tempfile.mkdtemp(prefix='savegate-%d-' % os.getpid(), dir=base); _DIR[os.getpid()] = d
    import atexit; me = os.getpid(); atexit.register(lambda: shutil.rmtree(d, True) if os.getpid() == me else None)      # a forked child exiting normally must not delete the parent's dir
    return d
