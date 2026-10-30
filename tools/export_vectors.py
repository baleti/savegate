"""Export language-neutral test vectors (JSON) from the Python reference for the Rust port (docs/rust-port.md):
 verify.json  : snapshot pairs + manifest -> expected differences (core._verify decision table, via a stub adapter)
 errors.json  : exception class -> contract exit code
 backup.json  : prune selection (keep, max_bytes) for a list of backup sizes, backup file name grammar, hash-tag check
 sniff.json   : DWG version tags -> writable / refusal message fragments
usage: export_vectors.py [OUTDIR]  (default tests/vectors); synthetic data only. Rust port: load these files and assert equal results."""
import os, sys, json, random, re
sys.path[:0] = [os.path.join(os.path.dirname(__file__), '..')]
import savegate as sg
from savegate import errors, core
from savegate.adapters import DwgAdapter, DWG_WRITABLE, RVT_WRITABLE, _DWG_NAMES, pick_adapter
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '..', 'tests', 'vectors'); os.makedirs(out, exist_ok=True)

class Stub:
    """adapter over dict snapshots: buffers are json bytes"""
    name = 'stub'
    def snapshot(self, buf): return json.loads(buf)
    def validate(self, buf): return 'ok'
    def expand(self, m): return set(m.get('modified', ())), set(m.get('added', ())), set(m.get('deleted', ()))
rng = random.Random(1); cases = []
for i in range(300):
    a = {'k%d' % j: 'v%d' % rng.randrange(5) for j in range(rng.randint(0, 8))}; b = dict(a); man = {'modified': [], 'added': [], 'deleted': []}
    for _ in range(rng.randint(0, 4)):
        op = rng.choice(['mod', 'add', 'del', 'silent_mod', 'silent_add', 'silent_del', 'noop_decl'])
        ks = sorted(a)
        if op in ('mod', 'silent_mod') and ks:
            k = rng.choice(ks)
            if k in b: b[k] = b[k] + 'x'; (man['modified'].append(k) if op == 'mod' else None)
        elif op in ('add', 'silent_add'):
            k = 'n%d' % rng.randrange(50); b[k] = 'new'; (man['added'].append(k) if op == 'add' else None)
        elif op in ('del', 'silent_del') and ks:
            k = rng.choice(ks)
            if k in b: del b[k]; (man['deleted'].append(k) if op == 'del' else None)
        elif op == 'noop_decl' and ks: man['modified'].append(rng.choice(ks))
    try: core._verify(type('D', (), {'adapter': Stub(), 'buf': json.dumps(a).encode()}), json.dumps(b).encode(), man); bad = []
    except errors.VerifyFailed as e: bad = sorted([list(x) for x in e.report['unexpected']])
    cases.append({'src': a, 'out': b, 'manifest': man, 'expected_bad': bad})
json.dump({'doc': 'bad = sorted [kind,key] pairs; kinds changed/lost/unexpected; empty list = accepted', 'cases': cases}, open(out + '/verify.json', 'w'), indent=0, sort_keys=True)
ex = {}
for n in ('OverwriteDisabled', 'GateClosed', 'Exists', 'UnsupportedVersion', 'ReadOnlyTarget', 'Conflict', 'Locked', 'VerifyFailed', 'DiskError', 'SaveError'):
    ex[n] = errors.exit_code(getattr(errors, n)('x'))
ex['none'] = errors.exit_code(None); json.dump(ex, open(out + '/errors.json', 'w'), indent=1, sort_keys=True)
bk = []
for i in range(200):
    n = rng.randint(1, 12); sizes = [rng.randint(1, 5000) for _ in range(n)]       # newest first
    keep = rng.randint(1, 8); cap = rng.choice([0, 0, 3000, 8000, 15000])
    drop = list(sizes[keep:]); kept = sizes[:keep]; tot = 0
    if cap:
        for j, sz in enumerate(kept):
            tot += sz
            if tot > cap and j > 0: drop += kept[j:]; kept = kept[:j]; break
    bk.append({'sizes_newest_first': sizes, 'keep': keep, 'max_bytes': cap, 'kept': len(kept)})
# cross-check the vector generator against the real _prune on files
import tempfile, shutil, time
from savegate import backup as B
for c in bk[:40]:
    d = tempfile.mkdtemp(prefix='sgv'); os.environ['SAVEGATE_CACHE'] = d + '/c'
    try:
        p = os.path.join(d, 'f.bin'); os.makedirs(d + '/.savegate')
        for i, sz in enumerate(reversed(c['sizes_newest_first'])):
            q = '%s/.savegate/f.bin.20200101-0000%02d-000-%08x' % (d, i, i); open(q, 'wb').write(b'x' * sz); os.utime(q, (1e9 + i, 1e9 + i))
        B._prune(p, c['keep'], c['max_bytes']); assert len(B.list_backups(p)) == c['kept'], (c, len(B.list_backups(p)))
    finally: shutil.rmtree(d, ignore_errors=True)
json.dump({'prune': bk, 'name_grammar': r'^NAME\.\d{8}-\d{6}-\d{3}-[0-9a-f]{8}$', 'tag': 'last 8 hex chars of the name = prefix of the file SHA-256'}, open(out + '/backup.json', 'w'), indent=0)
sn = []
for v in ['AC1006', 'AC1009', 'AC1012', 'AC1014', 'AC1015', 'AC1018', 'AC1021', 'AC1024', 'AC1027', 'AC1032', 'AC1035', 'AC1099', 'ZZ9999']:
    try: pick_adapter(v.encode() + b'\0' * 100); r = {'ok': True}
    except errors.UnsupportedVersion as e: r = {'ok': False, 'message_has': [x for x in (v, 'DXF', 'not touched') if x in str(e)]}
    sn.append(dict(tag=v, **r))
json.dump({'dwg_writable': list(DWG_WRITABLE), 'rvt_writable': list(RVT_WRITABLE), 'cases': sn}, open(out + '/sniff.json', 'w'), indent=1)
print('wrote', sorted(os.listdir(out)), 'verify cases', len(cases), 'accepted', sum(1 for c in cases if not c['expected_bad']))
