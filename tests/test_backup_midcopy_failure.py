"""c5x-rvtgap: the backup copy fails part-way (RLIMIT_FSIZE as stand-in for ENOSPC): make_backup raises, no .part and no backup is left, the source is untouched."""
import os, sys, subprocess, textwrap


def test_midcopy_failure_leaves_no_part(tmp_path):
    f = tmp_path / 'm.rvt'; data = os.urandom(300000); f.write_bytes(data)
    code = textwrap.dedent('''
        import sys, resource, os
        sys.path.insert(0, %r)
        from savegate.backup import make_backup
        resource.setrlimit(resource.RLIMIT_FSIZE, (100000, 100000))
        import signal; signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
        try: make_backup(sys.argv[1], 20, 0, None); print("NOERR")
        except Exception as e: print("ERR", type(e).__name__)
    ''' % os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    r = subprocess.run([sys.executable, '-c', code, str(f)], capture_output=True, text=True, env=dict(os.environ, HOME=str(tmp_path), XDG_CACHE_HOME=str(tmp_path / 'cache')))
    assert r.stdout.strip().startswith('ERR'), r.stdout + r.stderr
    left = [os.path.join(d, n) for root in (str(tmp_path),) for d, _, ns in os.walk(root) for n in ns if n.endswith('.part') or '.savegate' in d]
    assert left == [], left
    assert f.read_bytes() == data
