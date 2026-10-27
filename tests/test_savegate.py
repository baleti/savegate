import os, sys, time, hashlib, subprocess, signal, shutil, errno, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import savegate as sg
from savegate import atomic
from savegate.adapters import RawAdapter, DwgAdapter, RvtAdapter

DWGLIB = os.path.expanduser('~/dwg-write')
HAVE_DWG = os.path.exists(DWGLIB + '/templates/blank_2018.dwg')


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv('SAVEGATE_CACHE', str(tmp_path / 'cache'))
    monkeypatch.setenv('SAVEGATE_JOURNAL', str(tmp_path / 'journal'))
    monkeypatch.setenv('SAVEGATE_GATE', str(tmp_path / 'gate.json'))
    atomic._hook = None
    yield
    atomic._hook = None


def cfg(**k):
    d = dict(allow_overwrite=True, require_gate=False); d.update(k); return sg.Config(**d)


def mk(tmp_path, data=b'original', name='a.bin'):
    p = tmp_path / name; p.write_bytes(data); return str(p)


def leftovers(d):
    return [x for x in os.listdir(d) if x.endswith('.sgtmp')]


def test_overwrite_backup_restore(tmp_path):
    p = mk(tmp_path)
    with sg.open_doc(p, RawAdapter(), cfg()) as doc:
        r = sg.save(doc, b'new content', {'modified': ['file']})
    assert open(p, 'rb').read() == b'new content' and r.backup
    assert open(r.backup, 'rb').read() == b'original'
    sg.restore(p)
    assert open(p, 'rb').read() == b'original'
    assert len(sg.list_backups(p)) == 2     # restore backs up the current file first
    assert not leftovers(tmp_path)


def test_overwrite_disabled_and_gate(tmp_path):
    p = mk(tmp_path)
    doc = sg.open_doc(p, RawAdapter(), sg.Config())
    with pytest.raises(sg.OverwriteDisabled): sg.save(doc, b'x', {'modified': ['file']})
    doc.cfg = sg.Config(allow_overwrite=True)
    with pytest.raises(sg.GateClosed): sg.save(doc, b'x', {'modified': ['file']})
    assert open(p, 'rb').read() == b'original'


def test_conflict_detected(tmp_path):
    p = mk(tmp_path)
    doc = sg.open_doc(p, RawAdapter(), cfg())
    open(p, 'wb').write(b'someone else')
    with pytest.raises(sg.Conflict): sg.save(doc, b'mine', {'modified': ['file']})
    assert open(p, 'rb').read() == b'someone else'
    sg.save(doc, b'mine', {'modified': ['file']}, force=True)


def test_conflict_same_size_same_mtime(tmp_path):
    p = mk(tmp_path, b'AAAA')
    doc = sg.open_doc(p, RawAdapter(), cfg())
    st = os.stat(p); open(p, 'wb').write(b'BBBB'); os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns))
    with pytest.raises(sg.Conflict): sg.save(doc, b'mine', {'modified': ['file']})


def test_verify_failure_keeps_original(tmp_path):
    p = mk(tmp_path)
    doc = sg.open_doc(p, RawAdapter(), cfg())
    with pytest.raises(sg.VerifyFailed): sg.save(doc, b'changed but not declared', {})
    assert open(p, 'rb').read() == b'original' and not leftovers(tmp_path) and not sg.list_backups(p)


def test_save_as_new_and_exists(tmp_path):
    p = mk(tmp_path); q = str(tmp_path / 'b.bin')
    doc = sg.open_doc(p, RawAdapter(), sg.Config())     # overwrite disabled, SAVEAS still works
    sg.save_as(doc, b'n', q, {'modified': ['file']})
    assert open(q, 'rb').read() == b'n' and open(p, 'rb').read() == b'original'
    with pytest.raises(sg.Exists): sg.save_as(doc, b'm', q, {'modified': ['file']})
    assert open(q, 'rb').read() == b'n'
    sg.save_as(doc, b'm', q, {'modified': ['file']}, overwrite=True)
    assert open(q, 'rb').read() == b'm' and sg.list_backups(q)


def test_lock(tmp_path):
    from savegate.guard import Lock
    p = mk(tmp_path)
    with Lock(p):
        with pytest.raises(sg.Locked): Lock(p).acquire()
    Lock(p).acquire().release()
    l = Lock(p); l.acquire()
    open(l.lp, 'w').write('{"pid": 999999, "host": "%s", "time": %f}' % (__import__('socket').gethostname(), time.time()))
    Lock(p).acquire().release()      # dead pid on this host = stale


def test_journal_recovery(tmp_path):
    p = mk(tmp_path)
    doc = sg.open_doc(p, RawAdapter(), cfg())
    doc.journal.log('edit', op='move', handle=5)
    assert sg.recover() and sg.recover()[0][1][-1]['op'] == 'move'    # session not closed = crash
    doc.close(); assert not sg.recover()


def test_dir_not_writable(tmp_path):
    if os.geteuid() == 0: pytest.skip('root')
    d = tmp_path / 'ro'; d.mkdir(); p = mk(d)
    doc = sg.open_doc(p, RawAdapter(), cfg())
    os.chmod(d, 0o555)
    try:
        with pytest.raises(sg.DiskError): sg.save(doc, b'x', {'modified': ['file']})
        assert open(p, 'rb').read() == b'original'
    finally: os.chmod(d, 0o755)


def test_unicode_and_long_paths(tmp_path):
    d = tmp_path / ('Gebäude Süd 設計 ' + 'x' * 100); d.mkdir()
    p = mk(d, name='Grundriß 平面図 (v2) é.bin')
    with sg.open_doc(p, RawAdapter(), cfg()) as doc:
        sg.save(doc, b'ok', {'modified': ['file']})
    assert open(p, 'rb').read() == b'ok'
    long = 'n' * 200 + '.bin'
    q = mk(tmp_path, name=long)
    with sg.open_doc(q, RawAdapter(), cfg()) as doc:
        sg.save(doc, b'ok', {'modified': ['file']})


STEPS = ['tmp_written', 'before_replace', 'after_replace']


@pytest.mark.parametrize('step', STEPS)
def test_exception_at_every_step(tmp_path, step):
    p = mk(tmp_path)
    doc = sg.open_doc(p, RawAdapter(), cfg())
    def boom(s):
        if s == step: raise OSError(errno.EIO, 'injected')
    atomic._hook = boom
    try:
        try: sg.save(doc, b'NEWNEW', {'modified': ['file']})
        except Exception: pass
    finally: atomic._hook = None
    data = open(p, 'rb').read()
    assert data in (b'original', b'NEWNEW')            # never torn
    if step != 'after_replace': assert data == b'original'
    assert not leftovers(tmp_path) or step == 'after_replace'


KILL_SCRIPT = r'''
import sys, os, signal
sys.path.insert(0, {root!r})
import savegate as sg
from savegate import atomic
from savegate.adapters import RawAdapter
step = sys.argv[2]
def hook(s):
    if s == step: os.kill(os.getpid(), signal.SIGKILL)
atomic._hook = hook
doc = sg.open_doc(sys.argv[1], RawAdapter(), sg.Config(allow_overwrite=True, require_gate=False))
sg.save(doc, b'N' * 100000, {{'modified': ['file']}})
'''


@pytest.mark.parametrize('step', STEPS)
def test_kill9_at_every_step(tmp_path, step):
    p = mk(tmp_path, b'O' * 5000)
    script = tmp_path / 'k.py'
    script.write_text(KILL_SCRIPT.format(root=os.path.join(os.path.dirname(__file__), '..')))
    r = subprocess.run([sys.executable, str(script), p, step], env=dict(os.environ))
    assert r.returncode == -signal.SIGKILL
    data = open(p, 'rb').read()
    assert data in (b'O' * 5000, b'N' * 100000)
    assert data == b'O' * 5000 or step == 'after_replace'
    # next open sweeps stale temps (age 0 forced) and a later save works
    atomic.sweep_stale_temps(str(tmp_path), max_age=-1)
    assert not leftovers(tmp_path)
    with sg.open_doc(p, RawAdapter(), cfg()) as doc:
        sg.save(doc, b'again', {'modified': ['file']})
    assert open(p, 'rb').read() == b'again'


def test_enospc_tmpfs_or_simulated(tmp_path, monkeypatch):
    p = mk(tmp_path)
    doc = sg.open_doc(p, RawAdapter(), cfg())
    real = os.fsync
    def full(fd):
        raise OSError(errno.ENOSPC, 'No space left on device')
    monkeypatch.setattr(os, 'fsync', full)
    with pytest.raises(sg.DiskError): sg.save(doc, b'x' * 1000, {'modified': ['file']})
    monkeypatch.setattr(os, 'fsync', real)
    assert open(p, 'rb').read() == b'original' and not leftovers(tmp_path)


def test_100_cycles(tmp_path):
    p = mk(tmp_path)
    with sg.open_doc(p, RawAdapter(), cfg(backup_keep=5)) as doc:
        for i in range(100):
            sg.save(doc, ('v%d' % i).encode() * 10, {'modified': ['file']})
    assert open(p, 'rb').read() == b'v99' * 10
    assert len(sg.list_backups(p)) == 5 and not leftovers(tmp_path)


def test_huge_file(tmp_path):
    big = os.urandom(1 << 20) * 64        # 64 MB
    p = mk(tmp_path, big)
    with sg.open_doc(p, RawAdapter(), cfg(verify=False)) as doc:
        r = sg.save(doc, big[:-1] + b'Z', {})
    assert r.size == len(big) and open(p, 'rb').read()[-1:] == b'Z'


def test_unsupported_format():
    with pytest.raises(sg.UnsupportedVersion):
        from savegate.adapters import pick_adapter
        pick_adapter(b'AC1021' + b'\0' * 100)
    with pytest.raises(sg.UnsupportedVersion):
        pick_adapter(b'AC1009' + b'\0' * 100)
    with pytest.raises(sg.UnsupportedVersion):
        pick_adapter(b'hello')


@pytest.mark.skipif(not HAVE_DWG, reason='dwg-write templates absent')
@pytest.mark.parametrize('year', ['2000', '2004', '2010', '2013', '2018'])
def test_dwg_edit_verify(tmp_path, year):
    sys.path.insert(0, DWGLIB)
    import dwgdoc
    buf = open('%s/templates/blank_%s.dwg' % (DWGLIB, year), 'rb').read()
    p = tmp_path / 'x.dwg'; p.write_bytes(buf)
    with sg.open_doc(str(p), None, cfg()) as doc:
        assert doc.adapter.name == 'dwg'
        d = dwgdoc.Doc(buf); h = d.add_line((0, 0), (10, 0)); d.add_circle((5, 5), 2)
        out = d.save()
        r = sg.save(doc, out, {'added': [h, h + 1]})
        assert r.ok
        # identity save passes with an empty manifest
        d2 = dwgdoc.Doc(out); sg.save(doc, d2.save(), {})
        # an undeclared extra entity is rejected and the file stays
        d3 = dwgdoc.Doc(out); d3.add_point((1, 1)); before = open(str(p), 'rb').read()
        with pytest.raises(sg.VerifyFailed): sg.save(doc, d3.save(), {})
        assert open(str(p), 'rb').read() == before
        # corrupt output (valid-looking header, garbage body) is rejected
        with pytest.raises(Exception): sg.save(doc, out[:len(out) // 2], {})
        assert open(str(p), 'rb').read() == before


@pytest.mark.skipif(not HAVE_DWG, reason='dwg-write templates absent')
def test_dwg_modify_undeclared_rejected(tmp_path):
    sys.path.insert(0, DWGLIB)
    import dwgdoc
    buf = open(DWGLIB + '/templates/blank_2018.dwg', 'rb').read()
    d = dwgdoc.Doc(buf); a = d.add_line((0, 0), (10, 0)); b2 = d.add_line((0, 5), (10, 5)); buf = d.save()
    p = tmp_path / 'x.dwg'; p.write_bytes(buf)
    doc = sg.open_doc(str(p), None, cfg())
    d = dwgdoc.Doc(buf); d.transform(a, __import__('dwgxform').Transform.rotate((0, 0), 0.5))
    out = d.save()
    with pytest.raises(sg.VerifyFailed): sg.save(doc, out, {})            # undeclared edit
    r = sg.save(doc, out, {'modified': [a]}); assert r.ok                 # declared edit passes


ENOSPC_SCRIPT = r'''
import sys, os
sys.path.insert(0, {root!r})
import savegate as sg
from savegate.adapters import RawAdapter
m = sys.argv[1]
p = os.path.join(m, 'f.bin'); open(p, 'wb').write(b'O' * 100000)
doc = sg.open_doc(p, RawAdapter(), sg.Config(allow_overwrite=True, require_gate=False, journal_dir=m + '/../jr'))
try:
    sg.save(doc, b'N' * 3000000, {{'modified': ['file']}}); print('NOERROR')
except sg.DiskError as e:
    print('DISKERROR')
assert open(p, 'rb').read() == b'O' * 100000
assert not [x for x in os.listdir(m) if x.endswith('.sgtmp') or x.endswith('.part')], os.listdir(m)
print('INTACT')
'''


def test_real_enospc_rootless_tmpfs(tmp_path):
    if not shutil.which('unshare'): pytest.skip('no unshare')
    m = tmp_path / 'm'; m.mkdir()
    s = tmp_path / 'e.py'; s.write_text(ENOSPC_SCRIPT.format(root=os.path.join(os.path.dirname(__file__), '..')))
    r = subprocess.run(['unshare', '-rm', 'sh', '-c', 'mount -t tmpfs -o size=1m tmpfs %s && %s %s %s' % (m, sys.executable, s, m)],
                       capture_output=True, text=True, env=dict(os.environ))
    if 'mount' in r.stderr and 'DISKERROR' not in r.stdout: pytest.skip('cannot mount tmpfs rootless: ' + r.stderr[:100])
    assert 'DISKERROR' in r.stdout and 'INTACT' in r.stdout, r.stdout + r.stderr


RTE = os.path.expanduser('~/rvt-research/write-lab/scenes/classtests/2024_writer_cols2.rte')


@pytest.mark.skipif(not os.path.exists(RTE), reason='write-lab scene absent (local only)')
def test_rvt_container_verify(tmp_path):
    sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab'))
    import cfb
    buf = open(RTE, 'rb').read()
    p = tmp_path / 'x.rte'; p.write_bytes(buf)
    doc = sg.open_doc(str(p), None, cfg())
    assert doc.adapter.name == 'rvt' and doc.version == '2024'
    c = cfb.CFB(buf); cfb.write(c, str(tmp_path / 'same.bin'))
    same = open(tmp_path / 'same.bin', 'rb').read()
    assert sg.save(doc, same, {}).ok                                   # identity re-layout passes
    c = cfb.CFB(same); e = c.streams()['Global/Latest']; e.data = e.data[:-1] + bytes([e.data[-1] ^ 1])
    cfb.write(c, str(tmp_path / 'mod.bin')); mod = open(tmp_path / 'mod.bin', 'rb').read()
    with pytest.raises(sg.VerifyFailed): sg.save(doc, mod, {})        # undeclared stream change
    assert sg.save(doc, mod, {'modified': ['stream:Global/Latest']}).ok
    with pytest.raises(Exception): sg.save(doc, b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1' + b'\0' * 600, {})


@pytest.mark.skipif(not HAVE_DWG, reason='dwg-write templates absent')
@pytest.mark.parametrize('year', ['2000', '2004', '2010', '2013', '2018'])
def test_dwg_fuzz_chain_with_tracked_manifest(tmp_path, year):
    """random edit chains; the test tracks the exact handles it touched, savegate must accept every step
    (no false alarms) and a lie in the manifest must be caught"""
    import random
    sys.path.insert(0, DWGLIB)
    import dwgdoc, dwgxform as X
    rng = random.Random(int(year))
    buf = open('%s/templates/blank_%s.dwg' % (DWGLIB, year), 'rb').read()
    d = dwgdoc.Doc(buf)
    for i in range(20): d.add_line((i, 0), (i, 10))
    buf = d.save()
    p = tmp_path / 'f.dwg'; p.write_bytes(buf)
    caught = 0
    with sg.open_doc(str(p), None, cfg(backup_keep=3)) as doc:
        for step in range(12):
            d = dwgdoc.Doc(doc.buf); ls = list(d.entities('*Model_Space')); man = {'modified': [], 'added': [], 'deleted': []}
            for _ in range(rng.randint(1, 4)):
                op = rng.choice(['move', 'props', 'copy', 'erase', 'line', 'circle'])
                if op == 'line': man['added'].append(d.add_line((0, 0), (rng.random() * 9, 3)))
                elif op == 'circle': man['added'].append(d.add_circle((1, 1), 1 + rng.random()))
                elif len(ls) < 3: continue
                else:
                    h = rng.choice(ls)
                    if h in man['deleted'] or h in man['added']: continue
                    if op == 'move': d.transform(h, X.Transform.translate(rng.random(), 1)); man['modified'].append(h)
                    elif op == 'props': d.set_props(h, color=rng.randint(1, 200)); man['modified'].append(h)
                    elif op == 'copy': man['added'].append(d.copy_entity(h, X.Transform.translate(5, 5)))
                    elif op == 'erase': d.erase(h); ls.remove(h); man['deleted'].append(h)
            out = d.save()
            if man['modified'] and rng.random() < .3:
                bad = dict(man, modified=man['modified'][1:])       # forget one declared edit
                if len(set(man['modified'])) == len(man['modified']):
                    with pytest.raises(sg.VerifyFailed): sg.save(doc, out, bad)
                    caught += 1
            assert sg.save(doc, out, man).ok
    assert not leftovers(tmp_path)
