"""c4x-rvtgap 183: SAVEGATE_RVT_ALLOW_DANGLING_DELETE exists for the delete-mechanics tests only; a host environment that carries it must not switch the dangling-delete refusal off in production (PYTEST_CURRENT_TEST absent)."""
import os, subprocess, sys
PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def test_flag_is_ignored_without_pytest():
    code = "import sys; sys.path.insert(0, %r)\nfrom savegate import adapters as A\na = A.RvtAdapter(); a._src_buf = b'not an rvt'\nprint(a._delete_reference_checks({'deleted': ['el:5']}))\n" % PKG
    env = {k: v for k, v in os.environ.items() if k != 'PYTEST_CURRENT_TEST'}; env['SAVEGATE_RVT_ALLOW_DANGLING_DELETE'] = '1'
    out = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True, timeout=120).stdout
    assert 'delete_references_unchecked' in out, out       # unreadable source: refused, not waved through by the flag
def test_flag_still_works_under_pytest(monkeypatch):
    from savegate import adapters as A
    monkeypatch.setenv('SAVEGATE_RVT_ALLOW_DANGLING_DELETE', '1')
    a = A.RvtAdapter(); a._src_buf = b'not an rvt'
    assert a._delete_reference_checks({'deleted': ['el:5']}) == []
