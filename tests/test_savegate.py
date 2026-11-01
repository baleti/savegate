import os, stat, sys, time, hashlib, subprocess, signal, shutil, errno, pytest
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
    if sys.platform == 'win32' or os.geteuid() == 0: pytest.skip('root / chmod semantics differ on Windows')
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
    if sys.platform == 'win32' and len(str(tmp_path / long)) > 255: pytest.skip('test helper has no \\\\?\\ prefix')
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
    if s == step: os.kill(os.getpid(), signal.SIGKILL) if hasattr(signal, 'SIGKILL') else os._exit(137)
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
    assert r.returncode in (-getattr(signal, 'SIGKILL', 9), 137)
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
    cfb = pytest.importorskip('cfb')
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


@pytest.mark.skipif(not os.path.exists(RTE), reason='write-lab scene absent (local only)')
def test_rvt_element_level_identity(tmp_path):
    pytest.importorskip('numpy'); pytest.importorskip('olefile')
    sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab'))
    cfb = pytest.importorskip('cfb')
    from savegate.rvt_elements import elements
    buf = open(RTE, 'rb').read(); p = tmp_path / 'x.rte'; p.write_bytes(buf)
    ad = RvtAdapter(elements_fn=elements)
    doc = sg.open_doc(str(p), ad, cfg())
    cfb.write(cfb.CFB(buf), str(tmp_path / 's.bin'))
    r = sg.save(doc, open(tmp_path / 's.bin', 'rb').read(), {})
    assert r.report['objects_src'] > 1000          # element ids were compared, not just streams


@pytest.mark.skipif(not HAVE_DWG, reason='dwg-write templates absent')
def test_dwg_copy_of_polyline_children_belong_to_declared_entity(tmp_path):
    sys.path.insert(0, DWGLIB)
    import dwgdoc, dwgxform as X
    d = dwgdoc.Doc(open(DWGLIB + '/templates/blank_2018.dwg', 'rb').read()); pl = d.add_polyline2d([(0, 0), (5, 5), (9, 0)]); buf = d.save()
    p = tmp_path / 'x.dwg'; p.write_bytes(buf); doc = sg.open_doc(str(p), None, cfg())
    d = dwgdoc.Doc(buf); new = d.copy_entity(pl, X.Transform.translate(5, 5))
    assert sg.save(doc, d.save(), {'added': [new]}).ok
    d = dwgdoc.Doc(doc.buf); d.erase(pl)
    assert sg.save(doc, d.save(), {'deleted': [pl]}).ok


@pytest.mark.skipif(not os.path.exists(RTE), reason='write-lab scene absent (local only)')
def test_rvt_declared_element_edit_tolerates_holding_streams(tmp_path):
    """stub element view: element 7 is 'stored' in a Partitions stream; editing that stream is accepted only with element 7 declared"""
    sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab'))
    cfb = pytest.importorskip('cfb')
    buf = open(RTE, 'rb').read(); p = tmp_path / 'x.rte'; p.write_bytes(buf)
    c = cfb.CFB(buf)
    pk = next((k for k in c.streams() if k.startswith('Partitions/')), None)
    if pk is None: pytest.skip('no Partitions stream in the sample')
    def view(b):
        s = cfb.CFB(b).streams()[pk].data
        return {7: hashlib.sha1(s).hexdigest(), 8: 'const'}
    doc = sg.open_doc(str(p), RvtAdapter(elements_fn=view), cfg())
    e = c.streams()[pk]; e.data = e.data[:-1] + bytes([e.data[-1] ^ 1])
    cfb.write(c, str(tmp_path / 'm.bin')); mod = open(tmp_path / 'm.bin', 'rb').read()
    with pytest.raises(sg.VerifyFailed): sg.save(doc, mod, {})                             # nothing declared
    with pytest.raises(sg.VerifyFailed): sg.save(doc, mod, {'modified': ['el:8']})         # wrong element declared
    assert sg.save(doc, mod, {'modified': ['el:7']}).ok


def test_gate_open_requires_complete_ledger(tmp_path, monkeypatch):
    from savegate import evidence
    led = tmp_path / 'ledger.tsv'
    rows = ['sha\tAC1032\t%s\tAUDIT_OK\t2026' % r for r in evidence.DWG_ROWS[:-1]]
    led.write_text('\n'.join(rows) + '\n')
    assert evidence.missing(str(led), 'dwg', 'AC1032') == [evidence.DWG_ROWS[-1]]
    monkeypatch.setenv('SAVEGATE_GATE', str(tmp_path / 'gate.json'))
    from savegate.__main__ import main
    assert main(['gate', 'open', 'dwg', 'AC1032', '--evidence', str(led)]) == 3        # one row missing: refused
    led.write_text('\n'.join(rows + ['sha\tAC1032\t%s\tFAIL x\t2026' % evidence.DWG_ROWS[-1]]) + '\n')
    assert evidence.missing(str(led), 'dwg', 'AC1032')                                 # a FAIL row does not count
    led.write_text('\n'.join(rows + ['sha\tAC1032\t%s\tAUDIT_OK\t2026' % evidence.DWG_ROWS[-1]]) + '\n')
    assert main(['gate', 'open', 'dwg', 'AC1032', '--evidence', str(led)]) == 0


def test_readonly_target_refused_fast(tmp_path):
    p = mk(tmp_path)
    data = open(p, 'rb').read()
    os.chmod(p, 0o444)
    before = sorted(os.listdir(tmp_path))
    t0 = time.time()
    with sg.open_doc(p, RawAdapter(), cfg()) as doc:
        with pytest.raises(sg.ReadOnlyTarget):
            sg.save(doc, b'NEW' * 10, {'modified': ['file']})
        with pytest.raises(sg.ReadOnlyTarget):             # Save As over another read-only file as well
            q = mk(tmp_path, name='b.bin'); os.chmod(q, 0o444)
            sg.save_as(doc, b'NEW', q, {'modified': ['file']}, overwrite=True)
    assert time.time() - t0 < 2.0, 'must not spend the sharing-violation backoff on a read-only flag'
    assert open(p, 'rb').read() == data
    assert stat.S_IMODE(os.stat(p).st_mode) & 0o222 == 0
    assert [x for x in sorted(os.listdir(tmp_path)) if x not in ('b.bin', 'journal')] == before, 'temp, lock or journal files left behind'


def test_readonly_target_allowed_keeps_mode(tmp_path):
    p = mk(tmp_path); os.chmod(p, 0o444)
    with sg.open_doc(p, RawAdapter(), cfg(allow_readonly=True)) as doc:
        assert sg.save(doc, b'NEW', {'modified': ['file']}).ok
    assert open(p, 'rb').read() == b'NEW'
    assert stat.S_IMODE(os.stat(p).st_mode) & 0o222 == 0        # the protection flag survives


_CHILD = r'''
import os, sys
sys.path.insert(0, %(root)r)
import savegate as sg
from savegate.adapters import RawAdapter
n = int(sys.argv[2]); count = [0]
def wrap(mod, name):
    f = getattr(mod, name)
    def g(*a, **k):
        count[0] += 1
        if n and count[0] == n: os._exit(137)
        return f(*a, **k)
    setattr(mod, name, g)
for nm in ('replace', 'rename', 'fsync', 'write', 'open', 'link', 'remove', 'unlink', 'chmod', 'close', 'mkdir', 'makedirs', 'utime'):
    if hasattr(os, nm): wrap(os, nm)
import shutil
for nm in ('copy2', 'copyfile', 'copy'): wrap(shutil, nm)
os.environ['SAVEGATE_JOURNAL'] = sys.argv[3]
cfg = sg.Config(allow_overwrite=True, require_gate=False, backup_keep=2)
doc = sg.open_doc(sys.argv[1], RawAdapter(), cfg)
count[0] = 0
sg.save(doc, b'NEWCONTENT' * 1000, {'modified': ['file']})
print('CALLS', count[0])
'''


def test_kill_at_every_os_call_during_save(tmp_path):
    """kill -9 equivalent (os._exit) before the Nth filesystem call of one save, for every N: the destination is always the old or the new
    bytes (never partial, never missing), and the next save always succeeds"""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    child = tmp_path / 'child.py'; child.write_text(_CHILD % {'root': root})
    old = b'ORIGINAL' * 500; new = b'NEWCONTENT' * 1000
    def run(n, d):
        p = d / 'a.bin'; p.write_bytes(old)
        return subprocess.run([sys.executable, str(child), str(p), str(n), str(d / 'j')], capture_output=True, text=True), p
    r, _ = run(0, tmp_path / 'probe') if (tmp_path / 'probe').mkdir() is None else None
    total = int(r.stdout.split('CALLS')[1]); assert total > 5, r.stderr
    seen = set()
    for n in range(1, total + 1):
        d = tmp_path / ('k%d' % n); d.mkdir()
        r, p = run(n, d)
        assert r.returncode == 137, (n, r.stderr)
        data = p.read_bytes()
        assert data in (old, new), 'partial or missing destination after kill at call %d' % n
        seen.add(data == new)
        with sg.open_doc(str(p), RawAdapter(), cfg(backup_keep=2)) as doc:       # the next save works (stale lock of a dead pid)
            assert sg.save(doc, b'AFTER', {'modified': ['file']}).ok
        assert p.read_bytes() == b'AFTER'
    assert seen == {True, False}        # both outcomes occur across the sweep (before and after the rename)


def test_full_fsync_darwin_uses_fullfsync(monkeypatch, tmp_path):
    calls = []
    import types
    fake = types.SimpleNamespace(F_FULLFSYNC=51, fcntl=lambda fd, op, *a: calls.append(op))
    monkeypatch.setattr(atomic.sys, 'platform', 'darwin'); monkeypatch.setitem(sys.modules, 'fcntl', fake)
    with open(tmp_path / 'f', 'wb') as f: atomic.full_fsync(f.fileno())
    assert calls == [51]
    fake.fcntl = lambda fd, op, *a: (_ for _ in ()).throw(OSError('unsupported'))      # drive without F_FULLFSYNC: falls back to fsync
    with open(tmp_path / 'g', 'wb') as f: atomic.full_fsync(f.fileno())


def test_journal_replay_equals_edit_list_50_sessions(tmp_path):
    """50 random sessions, each crashed at a random point (file closed without 'closed', last line torn at a random byte): the recovered
    entries equal the logged edits up to the torn one, in order; closed sessions leave nothing behind"""
    import random, json as _json
    from savegate.journal import Journal, unfinished
    rng = random.Random(7); jd = str(tmp_path / 'j'); expect = {}
    for s in range(50):
        j = Journal('/x/src%d.dwg' % s, jd)
        edits = [dict(op=rng.choice(['move', 'erase', 'copy', 'props']), handle=rng.randrange(1 << 20), args=[rng.random() for _ in range(rng.randrange(4))]) for _ in range(rng.randrange(0, 30))]
        for e in edits: j.log('edit', **e)
        if s % 5 == 0:
            j.close(done=True)               # clean close: no journal remains
            continue
        j.close(done=False)
        raw = open(j.path, 'rb').read()
        if s % 2:                            # tear the last line at a random byte (power loss during the append)
            last = raw.rstrip(b'\n').rfind(b'\n') + 1
            cut = rng.randrange(last + 1, len(raw) - 1) if len(raw) - 2 > last + 1 else len(raw)
            open(j.path, 'wb').write(raw[:cut]); torn = cut < len(raw)
        else: torn = False
        expect[j.path] = (edits, torn)
    got = {p: ents for p, ents in unfinished(jd)}
    assert set(got) == {p for p, (e, t) in expect.items()}
    for p, (edits, torn) in expect.items():
        rec = [{k: v for k, v in x.items() if k not in ('t', 'kind')} for x in got[p] if x['kind'] == 'edit']
        want = edits[:-1] if torn and edits else edits
        assert rec == want, p


def test_orphan_temp_files_of_crashed_saves_are_cleaned(tmp_path):
    p = mk(tmp_path)
    old = tmp_path / '.a.bin.deadbeef.sgtmp'; old.write_bytes(b'partial'); t = time.time() - 7200; os.utime(old, (t, t))
    fresh = tmp_path / '.a.bin.cafe.sgtmp'; fresh.write_bytes(b'inprogress')           # cannot belong to a live save: that would hold the lock
    with sg.open_doc(p, RawAdapter(), cfg()) as doc:
        assert sg.save(doc, b'NEW', {'modified': ['file']}).ok
    assert not old.exists() and not fresh.exists()      # the save holds the target's lock, so every temp of this target is a crash leftover (was: only >1 h old ones; changed by c3x-e2e)


@pytest.mark.parametrize('ver', ['AC1006', 'AC1009', 'AC1012', 'AC1014', 'AC1021', 'AC1035', 'AC1099'])
def test_unsupported_dwg_versions_named_clearly(ver):
    from savegate.adapters import pick_adapter
    with pytest.raises(sg.UnsupportedVersion) as ei:
        pick_adapter(ver.encode() + b'\0' * 100)
    assert 'AC1015' in str(ei.value) and 'AC1032' in str(ei.value) or 'unknown or unsupported' in str(ei.value)


def test_unsupported_message_names_alternatives():
    from savegate.adapters import pick_adapter
    with pytest.raises(sg.UnsupportedVersion) as ei:
        pick_adapter(b'AC1021' + b'\0' * 100)
    m = str(ei.value)
    assert 'AC1021 (2007)' in m and 'AC1015 (2000)' in m and 'AC1032 (2018+)' in m and 'DXF' in m and 'not touched' in m


@pytest.mark.parametrize('year', ['2017', '2019', '2022', '2025'])
def test_rvt_other_years_refused_with_clear_message(year, tmp_path):
    seed = os.environ.get('SG_RVT_SEED', '/tmp/sgcl3/2024_a.rte')       # writer-made synthetic scene, local only
    if not os.path.exists(seed): pytest.skip('no synthetic RVT seed (SG_RVT_SEED)')
    cfb = pytest.importorskip('cfb', reason='write-lab module, local only')
    from savegate.adapters import pick_adapter
    buf = open(seed, 'rb').read(); c = cfb.CFB(buf); e = c.streams()['BasicFileInfo']
    txt = e.data.decode('utf-16le', 'ignore')
    assert '2024' in txt
    e.data = txt.replace('2024', year).encode('utf-16le')
    out = tmp_path / 'y.rvt'; cfb.write(c, str(out))
    with pytest.raises(sg.UnsupportedVersion) as ei:
        pick_adapter(out.read_bytes())
    m = str(ei.value)
    assert year in m and '2024' in m and '2026' in m and 'not touched' in m


def test_backup_size_cap_and_damaged_backup_not_restored(tmp_path, monkeypatch):
    from savegate import backup as B
    monkeypatch.setenv('SAVEGATE_CACHE', str(tmp_path / 'cache'))
    p = tmp_path / 'a.bin'
    for i in range(6):
        p.write_bytes(bytes([i]) * 1000); B.make_backup(str(p), keep=20, max_bytes=2500)
    bl = B.list_backups(str(p))
    assert 1 <= len(bl) <= 2 and sum(b[2] for b in bl) <= 2500          # cap: newest kept, oldest dropped
    assert open(bl[0][1], 'rb').read() == bytes([5]) * 1000
    assert B.verify_backup(bl[0][1])
    with open(bl[0][1], 'r+b') as f: f.seek(10); f.write(b'X')           # bit rot in the newest backup
    assert not B.verify_backup(bl[0][1])
    p.write_bytes(b'current')
    with pytest.raises(sg.SaveError, match='damaged'):
        B.restore(str(p))
    assert p.read_bytes() == b'current'                                  # target untouched
    assert B.restore(str(p), 1) if len(bl) > 1 else True


def test_declared_block_record_does_not_excuse_its_entities(tmp_path):
    """c8-perf escape class: a flip inside an entity record passed when the owning BLOCK_HEADER was declared modified."""
    import sys
    sys.path.insert(0, os.path.expanduser('~/dwg-write'))
    dwgdoc = pytest.importorskip('dwgdoc'); X = pytest.importorskip('dwgxform'); wtest = pytest.importorskip('wtest')
    d0 = dwgdoc.Doc(open(os.path.expanduser('~/dwg-write/templates/blank_2018.dwg'), 'rb').read()); wtest.basic(d0)
    p = tmp_path / 'f.dwg'; p.write_bytes(d0.save())
    d = dwgdoc.Doc(p.read_bytes()); hs = list(d.entities('*Model_Space')); ms = d.model_space()
    d.transform(hs[0], X.Transform.translate(1, 1)); d.transform(hs[1], X.Transform.translate(2, 2))       # hs[1] is NOT declared
    with sg.open_doc(str(p), None, cfg()) as doc:
        with pytest.raises(sg.VerifyFailed):
            sg.save_as(doc, d.save(), str(tmp_path / 'o.dwg'), {'modified': [hs[0], ms]}, overwrite=True)


def test_contract_fake_viewer_session(tmp_path, monkeypatch):
    """A fake viewer drives SAVEAS / SAVE / SAVE! / RESTORE / RECOVER exactly as savegate-contract.md says, checking the exit codes."""
    monkeypatch.setenv('SAVEGATE_JOURNAL', str(tmp_path / 'j')); monkeypatch.setenv('SAVEGATE_CACHE', str(tmp_path / 'c'))
    monkeypatch.setenv('SAVEGATE_GATE', str(tmp_path / 'gate.json'))
    src = tmp_path / 'm.bin'; src.write_bytes(b'v0')
    def run(fn):
        try: fn(); return 0
        except sg.SaveError as e: return sg.exit_code(e)
    c0 = sg.Config(allow_overwrite=False, require_gate=True)
    with sg.open_doc(str(src), RawAdapter(), c0) as doc:
        # SAVEAS new name: ok, source untouched
        assert run(lambda: sg.save_as(doc, b'v1', str(tmp_path / 'n.bin'), {'modified': ['file']})) == 0
        assert src.read_bytes() == b'v0'
        # SAVEAS onto an existing file without confirm: refused (3); with confirm: ok, old dest backed up
        assert run(lambda: sg.save_as(doc, b'v2', str(tmp_path / 'n.bin'), {'modified': ['file']})) == 3
        assert run(lambda: sg.save_as(doc, b'v2', str(tmp_path / 'n.bin'), {'modified': ['file']}, overwrite=True)) == 0
        assert (tmp_path / 'n.bin').read_bytes() == b'v2' and len(sg.list_backups(str(tmp_path / 'n.bin'))) == 1
        # SAVEAS with the source path and overwrite=True (what the viewer's save_over does) is SAVE!: gated too
        assert run(lambda: sg.save_as(doc, b'v3', str(src), {'modified': ['file']}, overwrite=True)) == 3 and src.read_bytes() == b'v0'
        # SAVE! with overwrite disabled: 3, source intact
        assert run(lambda: sg.save(doc, b'v3', {'modified': ['file']})) == 3 and src.read_bytes() == b'v0'
        # undeclared change on a verified format is the editor's bug: 5 (RawAdapter: manifest without 'file' while bytes differ)
        assert run(lambda: sg.save_as(doc, b'v4', str(tmp_path / 'o.bin'), {})) == 5 and not (tmp_path / 'o.bin').exists()
    # gate closed with overwrite enabled: 3
    c1 = sg.Config(allow_overwrite=True, require_gate=True)
    with sg.open_doc(str(src), RawAdapter(), c1) as doc:
        assert run(lambda: sg.save(doc, b'v5', {'modified': ['file']})) == 3 and src.read_bytes() == b'v0'
    # gate not required: SAVE! ok, backup made, RESTORE brings v0 back (and backs up the current file first)
    c2 = sg.Config(allow_overwrite=True, require_gate=False)
    with sg.open_doc(str(src), RawAdapter(), c2) as doc:
        assert run(lambda: sg.save(doc, b'v6', {'modified': ['file']})) == 0 and src.read_bytes() == b'v6'
    n = len(sg.list_backups(str(src))); assert n == 1
    sg.restore(str(src), 0); assert src.read_bytes() == b'v0' and len(sg.list_backups(str(src))) == 2
    # external modification after load: conflict 4
    with sg.open_doc(str(src), RawAdapter(), c2) as doc:
        src.write_bytes(b'someone else')
        assert run(lambda: sg.save(doc, b'v7', {'modified': ['file']})) == 4 and src.read_bytes() == b'someone else'
    # RECOVER lists a session that was never closed
    d = sg.open_doc(str(src), RawAdapter(), c2); d.journal.log('edit', op='move', handle=1)
    assert any(len(ents) >= 1 for p, ents in sg.recover())


def test_block_record_dropping_out_of_the_listing_is_refused():
    """c8-perf: a flipped bit in a BLOCK_HEADER made its entities unreachable; the fast path saw identical raw records and accepted.
    Unit level (a real flip needs a compressed-section offset): stub models whose output no longer lists block 0x70."""
    from savegate.adapters import DwgAdapter
    class O:
        def __init__(s, t, raw): s.type = t; s.raw = raw
    class M:
        def __init__(s, blocks): s.blocks = blocks; s.objs = {h: O(49, b'x') for h in blocks}
    a = DwgAdapter.__new__(DwgAdapter); a.owners = {}; a.bheaders = {}; a.dimobjs = {}; a.blockhs = set(); a.dims = set()
    src = M({0x1f: '*Model_Space', 0x70: 'DOOR'}); out = M({0x1f: '*Model_Space'}); out.objs[0x70] = O(49, b'x')
    a._pair = (src, out)
    assert ('block_unlisted', 'obj:70') in a.extra_checks({})
    assert ('block_unlisted', 'obj:70') not in a.extra_checks({'deleted': [0x70]})        # declared deletion of that record is fine
    a._pair = (src, M({0x1f: '*Model_Space', 0x70: 'DOOR'})); assert a.extra_checks({}) == []


def test_rust_port_vectors_are_current(tmp_path):
    """tests/vectors/*.json (consumed by the Rust port) must equal what the Python reference produces now."""
    import subprocess, sys
    here = os.path.dirname(os.path.abspath(__file__))
    subprocess.run([sys.executable, os.path.join(here, '..', 'tools', 'export_vectors.py'), str(tmp_path)], check=True, capture_output=True)
    for n in ('verify.json', 'errors.json', 'backup.json', 'sniff.json'):
        assert (tmp_path / n).read_bytes() == open(os.path.join(here, 'vectors', n), 'rb').read(), n


def test_change_between_last_check_and_backup_is_refused(tmp_path, monkeypatch):
    """c3x-e2e: the last fingerprint check runs BEFORE the backup copy; a same-size/same-mtime change landing in between used to be backed up and then overwritten (lost update)"""
    from savegate import core
    p = mk(tmp_path, b'original')
    real = core.make_backup
    def sneaky(path, *a, **k):
        st = os.stat(path); open(path, 'wb').write(b'0riginal'); os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))   # other program: same size, same mtime
        return real(path, *a, **k)
    monkeypatch.setattr(core, 'make_backup', sneaky)
    with sg.open_doc(p, RawAdapter(), cfg()) as doc:
        with pytest.raises(sg.Conflict) as ei: sg.save(doc, b'new content', {'modified': ['file']})
    assert open(p, 'rb').read() == b'0riginal', 'the other program\'s change was overwritten'
    assert 'not' in str(ei.value).lower() and not leftovers(tmp_path)
    assert any(open(b[1], 'rb').read() == b'0riginal' for b in sg.list_backups(p))      # its content is kept as a backup


def test_change_in_the_last_instant_before_rename_is_rescued(tmp_path):
    """c3x-e2e: a write landing after the last check/backup but before the rename cannot be refused any more; the replaced version is kept as a backup and reported"""
    p = mk(tmp_path, b'original')
    def hook(name):
        if name == 'before_replace':
            st = os.stat(p); open(p, 'wb').write(b'0riginal'); os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns))
    atomic._hook = hook
    with sg.open_doc(p, RawAdapter(), cfg()) as doc:
        r = sg.save(doc, b'new content', {'modified': ['file']})
    assert open(p, 'rb').read() == b'new content'
    assert r.report.get('warnings') and 'another program' in r.report['warnings'][0]
    assert any(open(b[1], 'rb').read() == b'0riginal' for b in sg.list_backups(p))
    sg.restore(p, 0); assert open(p, 'rb').read() == b'0riginal'


@pytest.mark.skipif(not os.path.exists(RTE), reason='write-lab scene absent (local only)')
def test_rvt_damaged_source_not_overwritten(tmp_path):
    """c3x-rvtgap: the reader tolerates a zeroed run / flipped bit in the source, the gate compares reader-vs-reader, so the damaged file used to be saved without a word"""
    import random, hashlib
    sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab'))
    pytest.importorskip('cfb')
    raw = open(RTE, 'rb').read(); rnd = random.Random(3); refused = 0
    good = tmp_path / 'g.rte'; good.write_bytes(raw)
    assert sg.save(sg.open_doc(str(good), None, cfg()), raw, {}).ok          # undamaged: identity save passes
    for i in range(12):
        b = bytearray(raw); o = rnd.randrange(8, len(b) - 64); b[o:o + 64] = bytes(64)
        p = tmp_path / ('d%d.rte' % i); p.write_bytes(bytes(b)); h = hashlib.sha256(bytes(b)).hexdigest()
        try: doc = sg.open_doc(str(p), None, cfg())
        except sg.SaveError: continue                                         # unreadable container: refused earlier
        try: sg.save(doc, bytes(b), {})
        except sg.VerifyFailed as e:
            assert 'damaged' in str(e) and 'not touched' in str(e); refused += 1
        assert hashlib.sha256(p.read_bytes()).hexdigest() == h               # source untouched in every case
    assert refused >= 8
    r = sg.save_as(sg.open_doc(str(p), None, cfg()), bytes(b), str(tmp_path / 'copy.rte'), {})
    assert r.ok and any('damaged' in w for w in r.report.get('warnings', []))


TRUNC_RTE = os.path.expanduser('~/rvt-research/rosetta/2024_all_types_base.rte')


@pytest.mark.skipif(not os.path.exists(TRUNC_RTE), reason='rosetta scene absent (local only)')
def test_rvt_truncated_source_is_never_accepted(tmp_path):
    """c5x-rvtgap: olefile-style readers parse a truncated .rvt silently with short streams; the gate must not treat it as healthy (any cut length)"""
    sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab'))
    pytest.importorskip('cfb')
    raw = open(TRUNC_RTE, 'rb').read()
    ad = sg.RvtAdapter() if hasattr(sg, 'RvtAdapter') else __import__('savegate.adapters', fromlist=['x']).RvtAdapter()
    assert ad._damage(raw) == []
    for fr in (0.999, 0.99, 0.9, 0.5, 0.1):
        assert ad._damage(raw[:int(len(raw) * fr)]), fr


VGS = os.path.expanduser('~/rvt-research/vg-scenes')


@pytest.mark.skipif(not os.path.isdir(VGS), reason='vg scenes absent (local only)')
@pytest.mark.parametrize('name', ['2024_vg_worksets.rvt', '2026_vg_worksets.rvt', '2024_vg_link_target.rvt'])
def test_rvt_writer_noedit_is_stream_and_directory_identical(name, tmp_path):
    """c3x-rvtgap: load + save with NO edit through the write-lab editor: every stream byte-identical and every directory entry (name, type, colour, tree links, CLSID, state, times) equal; only the container layout (sector order, free tail, FAT, header pointers) may differ"""
    sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab'))
    cfb = pytest.importorskip('cfb'); wledit = pytest.importorskip('wledit')
    o = str(tmp_path / 'o.rvt'); wledit.Editor(os.path.join(VGS, name)).save(o)
    A, B = cfb.CFB(open(os.path.join(VGS, name), 'rb').read()), cfb.CFB(open(o, 'rb').read())
    sa, sb = A.streams(), B.streams()
    assert sa.keys() == sb.keys() and all(sa[k].data == sb[k].data for k in sa)
    meta = lambda c: [(e.name, e.type, e.color, e.left, e.right, e.child, bytes(e.clsid), e.state, bytes(e.ctime), bytes(e.mtime)) for e in c.entries if e.type]
    assert meta(A) == meta(B)


@pytest.mark.skipif(not os.path.isdir(VGS), reason='vg scenes absent (local only)')
@pytest.mark.parametrize('name', ['2024_vg_worksets.rvt', '2026_vg_worksets.rvt'])
@pytest.mark.parametrize('grow', [1, 30])
def test_rvt_string_edit_touches_only_the_holding_partition(name, grow, tmp_path):
    """c3x-rvtgap: a size-changing string edit rewrites exactly one Partitions/N stream, with the SAME stored length (page layout kept); every other stream, ElemTable included, stays byte-identical"""
    sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab'))
    cfb = pytest.importorskip('cfb'); wledit = pytest.importorskip('wledit')
    src = os.path.join(VGS, name); ed = wledit.Editor(src)
    eid, fn, old = 2, 'ProjectPhase.m_name', None
    old = [l[4] for l in ed.trace(eid)[3] if l[1] == fn][0]
    ed.set_string(eid, fn, 'Z' * (len(old) + grow), match=old); o = str(tmp_path / 'o.rvt'); ed.save(o)
    A, B = cfb.CFB(open(src, 'rb').read()).streams(), cfb.CFB(open(o, 'rb').read()).streams()
    ch = [k for k in A if A[k].data != B[k].data]
    assert len(ch) == 1 and ch[0].startswith('Partitions/') and len(A[ch[0]].data) == len(B[ch[0]].data)


@pytest.mark.skipif(not os.path.isdir(VGS), reason='vg scenes absent (local only)')
def test_rvt_oversized_partition_member_refused(tmp_path):
    """c3x-rvtgap: the writer accepts a 200k-character string and emits a 395 KB partition member; Revit's limit is 131088 and validate() said ok"""
    sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab'))
    pytest.importorskip('cfb'); wledit = pytest.importorskip('wledit')
    src = os.path.join(VGS, '2024_vg_worksets.rvt'); ed = wledit.Editor(src)
    old = [l[4] for l in ed.trace(2)[3] if l[1] == 'ProjectPhase.m_name'][0]
    ed.set_string(2, 'ProjectPhase.m_name', 'Z' * 200000, match=old); o = str(tmp_path / 'o.rvt'); ed.save(o)
    ad = RvtAdapter()
    assert ad.validate(open(src, 'rb').read())
    with pytest.raises(sg.VerifyFailed, match='131088'): ad.validate(open(o, 'rb').read())


def test_orphan_temp_of_a_killed_save_is_swept_by_the_next_save(tmp_path):
    """c3x-e2e: a SIGKILLed SAVE! left a hidden full-size .sgtmp that lived until a save more than 1 h later"""
    p = mk(tmp_path, b'original'); orphan = tmp_path / '.a.bin.abc123.sgtmp'; orphan.write_bytes(b'x' * 100); other = tmp_path / '.b.bin.abc123.sgtmp'; other.write_bytes(b'y')
    with sg.open_doc(p, RawAdapter(), cfg()) as doc: sg.save(doc, b'new content', {'modified': ['file']})
    assert not orphan.exists() and other.exists()       # only this target's orphans


@pytest.mark.skipif(not os.path.isdir(VGS), reason='vg scenes absent (local only)')
@pytest.mark.parametrize('name', ['2024_vg_worksets.rvt', '2026_vg_worksets.rvt'])
def test_rvt_edit_keeps_every_other_element_and_the_id_set(name, tmp_path):
    """c3x-rvtgap: after an edit of one string, the element id set is unchanged and every OTHER element decodes to the same field log (offsets excluded, later elements shift; neighbours in the same partition, unknown classes included, are not dropped or reinterpreted)"""
    sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab'))
    pytest.importorskip('cfb'); wledit = pytest.importorskip('wledit')
    src = os.path.join(VGS, name); ed = wledit.Editor(src)
    old = [l[4] for l in ed.trace(2)[3] if l[1] == 'ProjectPhase.m_name'][0]
    ids = sorted(ed.m.ids); before = {}
    for e in ids:
        try: before[e] = repr([(l[0], l[1], l[4]) for l in ed.trace(e)[3]])
        except Exception: before[e] = 'ERR'
    ed.set_string(2, 'ProjectPhase.m_name', old + 'XYZ', match=old); o = str(tmp_path / 'o.rvt'); ed.save(o)
    ed2 = wledit.Editor(o)
    assert sorted(ed2.m.ids) == ids
    diff = []
    for e in ids:
        try: a = repr([(l[0], l[1], l[4]) for l in ed2.trace(e)[3]])
        except Exception: a = 'ERR'
        if a != before[e]: diff.append(e)
    assert diff == [2]


ROS = os.path.expanduser('~/rvt-research/write-lab/../rosetta')


@pytest.mark.skipif(not os.path.isdir(ROS), reason='rosetta scenes absent (local only)')
@pytest.mark.parametrize('name', ['2024_roof_ceiling_base.rte', '2026_room_base.rte', '2026_railing_var.rte'])
def test_rvt_edit_on_rosetta_scenes_changes_one_partition_and_only_the_edited_element(name, tmp_path):
    """c3x-rvtgap: one string edit on writer scenes of both writable years: exactly one Partitions/N stream differs (same stored length), ECC/gzip CRC clean, validate ok, id set equal, every other element decodes to the same field log (offsets excluded: later elements shift)"""
    sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab'))
    cfb = pytest.importorskip('cfb'); wledit = pytest.importorskip('wledit')
    src = os.path.join(ROS, name); ed = wledit.Editor(src); ids = sorted(ed.m.ids)
    key = lambda e_, ed_: [(l[0], l[1], l[4]) for l in ed_.trace(e_)[3]]
    cand = None
    for e in ids[:600]:
        try: log = ed.trace(e)[3]
        except Exception: continue
        for l in log:
            if isinstance(l[4], str) and 0 < len(l[4]) < 200 and l[3] - l[2] == 4 + 2 * len(l[4]) and l[4] != 'None': cand = (e, l[1], l[4]); break
        if cand: break
    assert cand
    before = {}
    for e in ids[:300]:
        try: before[e] = key(e, ed)
        except Exception: before[e] = 'ERR'
    e0, fn, v = cand; ed.set_string(e0, fn, v + 'XY', match=v); o = str(tmp_path / 'o.rte'); ed.save(o)
    ob = open(o, 'rb').read(); A = cfb.CFB(open(src, 'rb').read()).streams(); B = cfb.CFB(ob).streams()
    ch = [k for k in A if A[k].data != B[k].data]
    assert len(ch) == 1 and ch[0].startswith('Partitions/') and len(A[ch[0]].data) == len(B[ch[0]].data)
    ad = RvtAdapter(); assert ad.source_damage(ob) == [] and ad.validate(ob)
    ed2 = wledit.Editor(o); assert sorted(ed2.m.ids) == ids
    def k2(e):
        try: return key(e, ed2)
        except Exception: return 'ERR'
    assert [e for e in before if k2(e) != before[e]] == [e0]


RFA = os.path.expanduser('~/rvt-research/samples-rfa')


@pytest.mark.skipif(not os.path.isdir(RFA), reason='Autodesk sample rfa absent')
def test_rvt_writer_noedit_identity_on_autodesk_sample_family_every_year(tmp_path):
    """c5x-rvtgap: Autodesk Basic Sample Family 2016..2026: no-edit save through the editor keeps every stream and every directory entry (13 streams each)"""
    sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab'))
    cfb = pytest.importorskip('cfb'); wledit = pytest.importorskip('wledit')
    names = sorted(n for n in os.listdir(RFA) if n.endswith('.rfa')); assert len(names) == 11
    meta = lambda c: [(e.name, e.type, e.color, e.left, e.right, e.child, bytes(e.clsid), e.state, bytes(e.ctime), bytes(e.mtime)) for e in c.entries if e.type]
    for n in names:
        o = str(tmp_path / 'o.rfa'); wledit.Editor(os.path.join(RFA, n)).save(o)
        A, B = cfb.CFB(open(os.path.join(RFA, n), 'rb').read()), cfb.CFB(open(o, 'rb').read())
        sa, sb = A.streams(), B.streams()
        assert sa.keys() == sb.keys() and all(sa[k].data == sb[k].data for k in sa), n
        assert meta(A) == meta(B), n


@pytest.mark.skipif(not os.path.isdir(ROS), reason='rosetta scenes absent (local only)')
def test_rvt_gate_refuses_a_corrupt_modified_stream_in_the_output(tmp_path):
    """c5x-rvtgap (review R1): a stream declared modified is exempt from the hash diff; its page ECC / gzip CRC must still be checked on the WRITTEN bytes"""
    sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab'))
    cfb = pytest.importorskip('cfb'); import hashlib
    raw = open(os.path.join(ROS, '2026_room_base.rte'), 'rb').read(); c = cfb.CFB(raw); name = sorted(n for n in c.streams() if n.startswith('Partitions/'))[0]
    st = c.streams()[name]; d = bytearray(st.data); d[100] ^= 0x55; st.data = bytes(d)
    o = str(tmp_path / 'bad.rte'); cfb.write(c, o); bad = open(o, 'rb').read()
    p = tmp_path / 'a.rte'; p.write_bytes(raw); h = hashlib.sha256(raw).hexdigest()
    with pytest.raises(sg.VerifyFailed) as ei: sg.save(sg.open_doc(str(p), None, cfg()), bad, {'modified': ['stream:' + name]})
    assert ('integrity' in str(ei.value) or 'span_changed' in str(ei.value)) and hashlib.sha256(p.read_bytes()).hexdigest() == h


@pytest.mark.skipif(not os.path.isdir(RFA), reason='Autodesk sample rfa absent')
def test_rvt_container_rewrite_is_a_fixed_point_and_keeps_size(tmp_path):
    """c5x-rvtgap: cfb.write(CFB(cfb.write(x))) == cfb.write(x) and the file size is unchanged, on Autodesk sample families 2016..2026 (4096 sectors, 64-byte mini sectors)"""
    sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab'))
    cfb = pytest.importorskip('cfb')
    for n in sorted(x for x in os.listdir(RFA) if x.endswith('.rfa')):
        raw = open(os.path.join(RFA, n), 'rb').read(); a, b = str(tmp_path / 'a'), str(tmp_path / 'b')
        cfb.write(cfb.CFB(raw), a); b1 = open(a, 'rb').read(); cfb.write(cfb.CFB(b1), b)
        assert open(b, 'rb').read() == b1 and len(b1) == len(raw), n


@pytest.mark.skipif(not os.path.isdir(RFA), reason='Autodesk sample rfa absent')
def test_rvt_family_edit_2024_2026_valid_and_other_years_refused(tmp_path):
    """c5x-rvtgap: a string edit on the Autodesk sample family of 2024/2026 yields a clean (ECC/CRC) output with the same id set that the adapter validates; the 2020 family is refused by the gate (writable years only), file untouched"""
    sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab'))
    pytest.importorskip('cfb'); wledit = pytest.importorskip('wledit'); import hashlib
    for y in ('2024', '2026'):
        src = os.path.join(RFA, 'racbasicsamplefamily-%s.rfa' % y); ed = wledit.Editor(src); ids = sorted(ed.m.ids)
        log = ed.trace(0)[3]; l = next(l for l in log if isinstance(l[4], str) and 0 < len(l[4]) < 200 and l[3] - l[2] == 4 + 2 * len(l[4]) and l[4] != 'None')
        ed.set_string(0, l[1], l[4] + 'XY', match=l[4]); o = str(tmp_path / ('o%s.rfa' % y)); ed.save(o); b = open(o, 'rb').read()
        ad = RvtAdapter(); assert ad.sniff(b) == y and ad.source_damage(b) == [] and ad.validate(b)
        assert sorted(wledit.Editor(o).m.ids) == ids
    p = tmp_path / 'f2020.rfa'; p.write_bytes(open(os.path.join(RFA, 'racbasicsamplefamily-2020.rfa'), 'rb').read()); h = hashlib.sha256(p.read_bytes()).hexdigest()
    with pytest.raises(Exception) as ei: sg.open_doc(str(p), None, cfg())
    assert 'cannot be saved' in str(ei.value) and hashlib.sha256(p.read_bytes()).hexdigest() == h


@pytest.mark.skipif(not os.path.isdir(ROS), reason='rosetta scenes absent (local only)')
def test_rvt_gate_refuses_a_valid_but_undeclared_stream_change(tmp_path):
    """c5x-rvtgap: a stream rewritten with correct ECC and gzip CRC (so it is 'clean') but NOT declared modified is a hash-diff violation: refused, original untouched"""
    sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab'))
    cfb = pytest.importorskip('cfb'); rvtw = pytest.importorskip('rvtw'); import hashlib, zlib
    raw = open(os.path.join(ROS, '2026_room_base.rte'), 'rb').read(); c = cfb.CFB(raw)
    n = [k for k in c.streams() if k.startswith('Global/') and k not in ('Global/ContentDocuments',)][0]
    st = rvtw.Stream(c.streams()[n].data); P = bytearray(st.payload); i = P.find(rvtw.GZ); assert i >= 0
    r, end = rvtw.read_member(bytes(P), i); r2 = bytearray(r); r2[len(r2) // 2] ^= 1
    P2 = bytes(P[:i]) + rvtw.gz_member(bytes(r2), bytes(P[i:i + 10]), None) + bytes(P[end:])
    c.streams()[n].data = st.build(P2, keep_spare=False); o = str(tmp_path / 'o.rte'); cfb.write(c, o); new = open(o, 'rb').read()
    ad = RvtAdapter(); assert ad.source_damage(new) == []
    p = tmp_path / 'a.rte'; p.write_bytes(raw); h = hashlib.sha256(raw).hexdigest()
    with pytest.raises(sg.VerifyFailed): sg.save(sg.open_doc(str(p), None, cfg()), new, {'modified': ['stream:Partitions/none']})
    assert hashlib.sha256(p.read_bytes()).hexdigest() == h


@pytest.mark.skipif(not os.path.isdir(ROS), reason='rosetta scenes absent (local only)')
def test_rvt_validate_refuses_stale_partition_frame_size(tmp_path):
    """c5x-rvtgap: an output partition whose member was re-deflated without updating the 32-byte frame size fields (ECC and CRC all valid) is refused; the real edit output passes"""
    sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab'))
    cfb = pytest.importorskip('cfb'); rvtw = pytest.importorskip('rvtw'); wlpart = pytest.importorskip('wlpart')
    raw = open(os.path.join(ROS, '2026_room_base.rte'), 'rb').read(); assert RvtAdapter().validate(raw)
    c = cfb.CFB(raw); n = sorted(k for k in c.streams() if k.startswith('Partitions/') and len(rvtw.Stream(c.streams()[k].data).payload) > 40)[0]
    st = rvtw.Stream(c.streams()[n].data); pt = wlpart.Partition(st); pt.mem[0]['dirty'] = True; pt.mem[0]['raw'] += b'\0'      # bytes appended, frame fields not updated (cascade/rebuild would fix them)
    P0 = st.payload; m = pt.mem[0]
    P2 = P0[:m['pos']] + rvtw.gz_member(bytes(m['raw']), m['gzhdr'], None) + P0[m['end']:]
    c.streams()[n].data = st.build(P2, keep_spare=False); o = str(tmp_path / 'o.rte'); cfb.write(c, o)
    with pytest.raises(sg.VerifyFailed): RvtAdapter().validate(open(o, 'rb').read())


@pytest.mark.skipif(not os.path.isdir(ROS), reason='rosetta scenes absent (local only)')
def test_rvt_element_view_does_not_excuse_a_tampered_global_stream(tmp_path, monkeypatch):
    """c5x-rvtgap ESCAPE: with elements_fn and a declared element edit, side_effects used to excuse EVERY Global/* stream, so a Global stream rewritten with valid ECC+CRC went through. Legit edit passes, tampered Global stream refused."""
    pytest.importorskip('numpy'); pytest.importorskip('olefile')
    sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab'))
    cfb = pytest.importorskip('cfb'); rvtw = pytest.importorskip('rvtw'); wledit = pytest.importorskip('wledit')
    from savegate.rvt_elements import elements
    monkeypatch.setenv('SAVEGATE_CACHE', str(tmp_path / 'cache'))
    view = lambda b: elements(b, with_geometry=False)
    src = os.path.join(ROS, '2024_roof_ceiling_base.rte'); raw = open(src, 'rb').read(); ed = wledit.Editor(src)
    e, l = next((e, l) for e in sorted(ed.m.ids) for l in (ed.trace(e)[3] if e < 30000 else []) if l[1] == 'FamilyBase.m_name' and l[3] - l[2] == 4 + 2 * len(l[4]))
    ed.set_string(e, l[1], l[4] + 'XY', match=l[4]); o = str(tmp_path / 'ok.rte'); ed.save(o); ok = open(o, 'rb').read()
    a0, b0 = view(raw), view(ok); decl = ['el:%d' % k for k in a0 if a0[k] != b0.get(k)]; assert decl and len(b0) == len(a0)
    c = cfb.CFB(ok); n = 'Global/ContentDocuments'; st = rvtw.Stream(c.streams()[n].data); P = st.payload; i = P.find(rvtw.GZ)
    r, end = rvtw.read_member(bytes(P), i); r2 = bytearray(r); r2[len(r2) // 2] ^= 1
    c.streams()[n].data = st.build(bytes(P[:i]) + rvtw.gz_member(bytes(r2), bytes(P[i:i + 10]), None) + bytes(P[end:]), keep_spare=False)
    t = str(tmp_path / 't.rte'); cfb.write(c, t); bad = open(t, 'rb').read(); assert RvtAdapter().source_damage(bad) == []
    p = tmp_path / 'a.rte'; p.write_bytes(raw)
    assert sg.save(sg.open_doc(str(p), RvtAdapter(elements_fn=view), cfg()), ok, {'modified': decl}).ok
    p.write_bytes(raw)
    with pytest.raises(sg.VerifyFailed): sg.save(sg.open_doc(str(p), RvtAdapter(elements_fn=view), cfg()), bad, {'modified': decl})


@pytest.mark.skipif(not os.path.isdir(ROS), reason='rosetta scenes absent (local only)')
def test_rvt_declared_edit_plus_far_bit_flip_in_the_same_partition_is_refused(tmp_path, monkeypatch):
    """c5x-rvtgap: a single-bit flip (valid gzip CRC and page ECC) in a member far from the declared edit is invisible to the element view (23/25 flips undetected); the member-spread check refuses it, the clean edit passes"""
    pytest.importorskip('numpy'); pytest.importorskip('olefile')
    sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab'))
    cfb = pytest.importorskip('cfb'); rvtw = pytest.importorskip('rvtw'); wledit = pytest.importorskip('wledit'); wlpart = pytest.importorskip('wlpart')
    from savegate.rvt_elements import elements
    monkeypatch.setenv('SAVEGATE_CACHE', str(tmp_path / 'cache'))
    view = lambda b: elements(b, with_geometry=False)
    src = os.path.join(ROS, '2024_roof_ceiling_base.rte'); raw = open(src, 'rb').read(); ed = wledit.Editor(src)
    e, l = next((e, l) for e in sorted(ed.m.ids) for l in (ed.trace(e)[3] if e < 30000 else []) if l[1] == 'FamilyBase.m_name' and l[3] - l[2] == 4 + 2 * len(l[4]))
    ed.set_string(e, l[1], l[4] + 'XY', match=l[4]); o = str(tmp_path / 'ok.rte'); ed.save(o); ok = open(o, 'rb').read()
    a0, b0 = view(raw), view(ok); decl = ['el:%d' % k for k in a0 if a0[k] != b0.get(k)]
    c = cfb.CFB(ok); n = [k for k in c.streams() if k.startswith('Partitions/')][0]; st = rvtw.Stream(c.streams()[n].data); pt = wlpart.Partition(st)
    m = pt.mem[130]; m['raw'][97227] ^= 1; m['dirty'] = True; c.streams()[n].data = st.build(pt.rebuild(), keep_spare=False)
    t = str(tmp_path / 't.rte'); cfb.write(c, t); bad = open(t, 'rb').read(); assert RvtAdapter().source_damage(bad) == []
    p = tmp_path / 'a.rte'; p.write_bytes(raw)
    assert sg.save(sg.open_doc(str(p), RvtAdapter(elements_fn=view), cfg()), ok, {'modified': decl}).ok
    p.write_bytes(raw)
    with pytest.raises(sg.VerifyFailed) as ei: sg.save(sg.open_doc(str(p), RvtAdapter(elements_fn=view), cfg()), bad, {'modified': decl})
    assert 'members_changed' in str(ei.value) or 'span_changed' in str(ei.value)


@pytest.mark.skipif(not os.path.isdir(ROS), reason='rosetta scenes absent (local only)')
def test_rvt_declared_edit_plus_bit_flip_in_the_edited_member_is_refused(tmp_path, monkeypatch):
    """c5x-rvtgap: a flip inside the SAME gzip member as the declared edit but 60 KB away passes the member-spread check; the changed-window check (a declared string edit changes <= ~1 KB of a partition on real scenes) flags it"""
    pytest.importorskip('numpy'); pytest.importorskip('olefile')
    sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab'))
    cfb = pytest.importorskip('cfb'); rvtw = pytest.importorskip('rvtw'); wledit = pytest.importorskip('wledit'); wlpart = pytest.importorskip('wlpart')
    from savegate.rvt_elements import elements
    monkeypatch.setenv('SAVEGATE_CACHE', str(tmp_path / 'cache'))
    view = lambda b: elements(b, with_geometry=False)
    src = os.path.join(ROS, '2024_roof_ceiling_base.rte'); raw = open(src, 'rb').read(); ed = wledit.Editor(src)
    e, l = next((e, l) for e in sorted(ed.m.ids) for l in (ed.trace(e)[3] if e < 30000 else []) if l[1] == 'FamilyBase.m_name' and l[3] - l[2] == 4 + 2 * len(l[4]))
    ed.set_string(e, l[1], l[4] + 'XY', match=l[4]); o = str(tmp_path / 'ok.rte'); ed.save(o); ok = open(o, 'rb').read()
    a0, b0 = view(raw), view(ok); decl = ['el:%d' % k for k in a0 if a0[k] != b0.get(k)]
    c = cfb.CFB(ok); n = [k for k in c.streams() if k.startswith('Partitions/')][0]; st = rvtw.Stream(c.streams()[n].data); pt = wlpart.Partition(st)
    A = [bytes(m['raw']) for m in wlpart.Partition(rvtw.Stream(cfb.CFB(raw).streams()[n].data)).mem]
    k = next(i for i, m in enumerate(pt.mem) if bytes(m['raw']) != A[i]); m = pt.mem[k]
    d = next(i for i in range(len(m['raw'])) if m['raw'][i] != A[k][i]); far = d + 60000 if d + 60000 < len(m['raw']) else d - 60000
    m['raw'][far] ^= 1; m['dirty'] = True; c.streams()[n].data = st.build(pt.rebuild(), keep_spare=False)
    t = str(tmp_path / 't.rte'); cfb.write(c, t); bad = open(t, 'rb').read(); assert RvtAdapter().source_damage(bad) == []
    def spans(out):      # the changed-window rule alone (the element view already catches most flips in this dense member)
        a = RvtAdapter(); a._blk_hist = [a._block_hashes(cfb.CFB(raw)), a._block_hashes(cfb.CFB(out))]
        return a.span_checks({'modified': decl})
    assert spans(ok) == [], 'a real string edit must stay inside the window budget'
    r = spans(bad); assert r and r[0][0] == 'span_changed', r


@pytest.mark.skipif(not os.path.exists(os.path.join(VGS, '2026_vg_worksets.rvt')), reason='vg scenes absent (local only)')
def test_rvt_workshared_model_is_not_overwritten_in_place(tmp_path):
    """c5x-rvtgap: Worksharing: Central/Local files are tied to central/local sync state outside the file; in-place overwrite refused (file untouched), SAVE AS still works; a non-workshared scene overwrites normally"""
    import hashlib
    sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab'))
    pytest.importorskip('cfb')
    raw = open(os.path.join(VGS, '2026_vg_worksets.rvt'), 'rb').read(); p = tmp_path / 'w.rvt'; p.write_bytes(raw); h = hashlib.sha256(raw).hexdigest()
    with pytest.raises(sg.VerifyFailed) as ei: sg.save(sg.open_doc(str(p), None, cfg()), raw, {})
    assert 'workshared' in str(ei.value) and hashlib.sha256(p.read_bytes()).hexdigest() == h
    assert sg.save_as(sg.open_doc(str(p), None, cfg()), raw, str(tmp_path / 'copy.rvt'), {}).ok
    if os.path.isdir(ROS):
        q = tmp_path / 'n.rte'; r2 = open(os.path.join(ROS, '2026_room_base.rte'), 'rb').read(); q.write_bytes(r2)
        assert sg.save(sg.open_doc(str(q), None, cfg()), r2, {}).ok


@pytest.mark.skipif(not os.path.isdir(ROS), reason='rosetta scenes absent (local only)')
def test_rvt_declared_partition_stream_emptied_is_refused(tmp_path):
    """c4x-rvtgap SEV1 ESCAPE: the declared-modified Partitions stream replaced by an EMPTY stream (valid container, no ECC page, no member) used to be accepted; the clean edit still passes"""
    sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab'))
    cfb = pytest.importorskip('cfb'); wledit = pytest.importorskip('wledit'); pytest.importorskip('numpy'); pytest.importorskip('olefile')
    src = os.path.join(ROS, '2024_roof_ceiling_base.rte'); raw = open(src, 'rb').read(); ed = wledit.Editor(src)
    e, l = next((e, l) for e in sorted(ed.m.ids) for l in (ed.trace(e)[3] if e < 30000 else []) if l[1] == 'FamilyBase.m_name' and l[3] - l[2] == 4 + 2 * len(l[4]))
    ed.set_string(e, l[1], l[4] + 'XY', match=l[4]); o = str(tmp_path / 'ok.rte'); ed.save(o); ok = open(o, 'rb').read()
    c = cfb.CFB(ok); n = [k for k in c.streams() if k.startswith('Partitions/')][0]; c.streams()[n].data = b''
    t = str(tmp_path / 't.rte'); cfb.write(c, t); bad = open(t, 'rb').read()
    p = tmp_path / 'a.rte'; p.write_bytes(raw)
    assert sg.save(sg.open_doc(str(p), RvtAdapter(), cfg()), ok, {'modified': ['stream:' + n]}).ok
    p.write_bytes(raw)
    with pytest.raises(sg.VerifyFailed): sg.save(sg.open_doc(str(p), RvtAdapter(), cfg()), bad, {'modified': ['stream:' + n]})
    assert p.read_bytes() == raw
