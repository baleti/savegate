"""python -m savegate info FILE | backups FILE | restore FILE [N] | recover | gate open|close FMT VERSION [--evidence F]"""
import sys, os, json
import savegate as sg
from savegate.core import gate_open


def main(a):
    if not a: print(__doc__); return 2
    c = a[0]
    if c == 'info':
        d = sg.open_doc(a[1], journal=False); print(json.dumps(dict(format=d.adapter.name, version=d.version, size=d.fingerprint.size, sha256=d.fingerprint.sha256))); return 0
    if c == 'backups':
        for i, (n, p, s) in enumerate(sg.list_backups(a[1])): print(i, s, p)
        return 0
    if c == 'restore':
        print(sg.restore(a[1], int(a[2]) if len(a) > 2 else None)); return 0
    if c == 'recover':
        for p, ents in sg.recover(): print(p, len(ents), 'entries; source', ents[0].get('source'))
        return 0
    if c == 'gate':
        p = os.environ.get('SAVEGATE_GATE') or os.path.expanduser('~/.config/savegate/gate.json')
        try: g = json.load(open(p))
        except (OSError, ValueError): g = {}
        if a[1] == 'open':
            if '--evidence' not in a or not os.path.exists(a[a.index('--evidence') + 1]):
                print('refused: --evidence FILE (oracle matrix result) required'); return 3
            ev = a[a.index('--evidence') + 1]
            g.setdefault(a[2], {})[a[3]] = 'open'; g.setdefault('_evidence', {})['%s/%s' % (a[2], a[3])] = ev
        elif a[1] == 'close': g.setdefault(a[2], {})[a[3]] = 'closed'
        else: print(__doc__); return 2
        os.makedirs(os.path.dirname(p), exist_ok=True)
        from savegate.atomic import write_temp, commit_temp
        t = write_temp(p, json.dumps(g, indent=1).encode()); commit_temp(t, p); print('ok'); return 0
    print(__doc__); return 2

sys.exit(main(sys.argv[1:]))
