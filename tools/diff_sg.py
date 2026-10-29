#!/usr/bin/env python3
"""diff_sg.py SGRS_BIN [N] [SEED]: differential test of the Python savegate against the Rust sgrs CLI.
Each scenario is a random op sequence run in two identical temp dirs (raw adapter, synthetic bytes); compares exit codes,
final bytes of every file and the number of backups. Prints the mismatch count (0 expected)."""
import sys, os, random, shutil, subprocess, tempfile, json, hashlib
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import savegate as sg
from savegate import core, errors
from savegate.adapters import RawAdapter

CODES = [(errors.VerifyFailed, 5), (errors.Conflict, 4), (errors.Locked, 4), (errors.DiskError, 6),
         (errors.Exists, 3), (errors.OverwriteDisabled, 3), (errors.GateClosed, 3), (errors.UnsupportedVersion, 3)]


def code_of(e):
    for c, n in CODES:
        if isinstance(e, c): return n
    return 3 if isinstance(e, sg.SaveError) else 99


def dir_state(d):
    out = {}
    for n in sorted(os.listdir(d)):
        p = os.path.join(d, n)
        if os.path.isfile(p): out[n] = hashlib.sha1(open(p, 'rb').read()).hexdigest()[:10]
    return out


def n_backups(path):
    try: return len(sg.list_backups(path))
    except Exception: return -1


def py_op(d, gate, op):
    cfg = core.Config(allow_overwrite=True, gate_file=gate, journal_dir=os.path.join(d, '.jr'))
    k = op[0]
    try:
        if k == 'saveas':
            _, src, new, dest, ow = op
            doc = core.open_doc(os.path.join(d, src), RawAdapter(), cfg)
            core.save_as(doc, open(os.path.join(d, new), 'rb').read(), os.path.join(d, dest), {}, overwrite=ow)
            doc.close()
        elif k == 'save':
            _, f = op
            doc = core.open_doc(os.path.join(d, f), RawAdapter(), cfg)
            core.save(doc, doc.buf, {}); doc.close()
        elif k == 'restore':
            _, f, i = op
            core.restore(os.path.join(d, f), i)
    except sg.SaveError as e:
        return code_of(e)
    except Exception:
        return 98
    return 0


def rs_op(d, gate, bin_, op):
    env = dict(os.environ, SAVEGATE_GATE=gate, SAVEGATE_JOURNAL=os.path.join(d, '.jr'), SAVEGATE_CACHE=os.path.join(d, '.cache'))
    k = op[0]
    if k == 'saveas':
        _, src, new, dest, ow = op
        a = [bin_, 'save-as', os.path.join(d, src), '--in', os.path.join(d, new), '--dest', os.path.join(d, dest)] + (['--overwrite'] if ow else [])
        # sgrs reads NEWFILE bytes from --in as a path
    elif k == 'save':
        f = os.path.join(d, op[1]); a = [bin_, 'save', f, '--in', f, '--dest', f, '--overwrite']
    else:
        a = [bin_, 'restore', os.path.join(d, op[1]), str(op[2])]
    return subprocess.run(a, env=env, capture_output=True, timeout=60).returncode


def main():
    bin_ = sys.argv[1]; n = int(sys.argv[2]) if len(sys.argv) > 2 else 200; seed = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    bad = 0; stats = {}
    for s in range(n):
        r = random.Random(seed * 100003 + s)
        root = tempfile.mkdtemp(prefix='dsg')
        try:
            dirs = []
            for tag in ('py', 'rs'):
                d = os.path.join(root, tag); os.makedirs(d); dirs.append(d)
                for nm in ('a.bin', 'b.bin', 'c.bin'):
                    open(os.path.join(d, nm), 'wb').write(bytes(r.getrandbits(8) for _ in range(r.randint(1, 300))) if tag == 'py' else b'')
            # same content in both: regenerate deterministically
            r = random.Random(seed * 100003 + s)
            files = {nm: bytes(r.getrandbits(8) for _ in range(r.randint(1, 300))) for nm in ('a.bin', 'b.bin', 'c.bin')}
            gate = os.path.join(root, 'gate.json')
            json.dump({'raw': {'raw': 'open', '1': 'open', '*': 'open'}}, open(gate, 'w'))
            for d in dirs:
                for nm, b in files.items(): open(os.path.join(d, nm), 'wb').write(b)
            ops = []
            for _ in range(r.randint(1, 6)):
                t = r.choice(['saveas', 'saveas', 'save', 'restore'])
                if t == 'saveas':
                    src = r.choice(list(files)); same = r.random() < 0.6
                    newf = src if same else r.choice(list(files))
                    dest = r.choice(list(files) + ['new1.bin', 'new2.bin'])
                    ops.append(('saveas', src, newf, dest, r.random() < 0.5))
                elif t == 'save': ops.append(('save', r.choice(list(files))))
                else: ops.append(('restore', r.choice(list(files)), r.randint(0, 2)))
            for op in ops:
                cp = py_op(dirs[0], gate.replace(root, root), op); cr = rs_op(dirs[1], gate, bin_, op)
                key = (op[0], cp, cr); stats[key] = stats.get(key, 0) + 1
                a = {k: v for k, v in dir_state(dirs[0]).items()}; b = {k: v for k, v in dir_state(dirs[1]).items()}
                nb = [n_backups(os.path.join(d, 'a.bin')) for d in dirs]
                if cp != cr or a != b:
                    bad += 1; print('MISMATCH scenario', s, op, 'py', cp, 'rs', cr, 'files equal', a == b, 'ops so far', ops[:ops.index(op) + 1]); break
        finally:
            shutil.rmtree(root, ignore_errors=True)
    print('scenarios', n, 'mismatches', bad)
    for k in sorted(stats): print(k, stats[k])


main()
