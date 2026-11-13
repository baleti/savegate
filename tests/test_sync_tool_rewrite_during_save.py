"""c5x-rvtread2 143: a sync tool rewrites the target between the fingerprint check and the rename.
The foreign version must survive as a backup (or the save must refuse); it must never be lost silently."""
import os, hashlib, pytest
import savegate as sg
from savegate import atomic
from savegate.adapters import RawAdapter

def _all_backup_bytes(p):
    d = os.path.join(os.path.dirname(p), '.savegate')
    return [open(os.path.join(d, f), 'rb').read() for f in os.listdir(d) if not f.endswith('.part') and f.startswith(os.path.basename(p))] if os.path.isdir(d) else []

@pytest.mark.parametrize('step', ['tmp_written', 'before_replace'])
@pytest.mark.parametrize('kind', ['content', 'touch_only'])
def test_foreign_rewrite(tmp_path, step, kind):
    p = str(tmp_path / 'f.bin'); orig = os.urandom(60000); open(p, 'wb').write(orig)
    foreign = os.urandom(60000) if kind == 'content' else orig
    doc = sg.open_doc(p, RawAdapter(), sg.Config(allow_overwrite=True, require_gate=False))
    fired = []
    def hook(n):
        if n == step and not fired:
            fired.append(1); open(p, 'wb').write(foreign); os.utime(p, ns=(1, 1))   # sync tool rewrite, new mtime
    atomic._hook = hook
    try:
        try: res = sg.save(doc, b'N' * 70000, {'modified': ['file']}); refused = False
        except Exception: refused = True
    finally: atomic._hook = None
    cur = open(p, 'rb').read()
    if kind == 'content':
        # foreign data either still on disk (refused) or preserved in a backup
        assert refused and cur == foreign or foreign in _all_backup_bytes(p), 'foreign version lost'
    else:
        assert refused or cur == b'N' * 70000      # identical content: fine either way, never garbage
    assert cur in (foreign, b'N' * 70000)
