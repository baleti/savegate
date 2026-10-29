"""Gate evidence: a (format, version) cell may be opened only when the oracle ledger (tsv: sha8, version, row, result, date) holds an OK row
for every required row (docs: savegate-matrix-plan.md). OK = AUDIT_OK (AutoCAD VM) or OPEN_OK (Revit VM)."""
DWG_ROWS = ['identity', 'edit_move', 'edit_props', 'edit_copy', 'edit_erase', 'edit_add', 'cycles100', 'unicode_path'] + ['fuzz%d' % i for i in range(5)]
RVT_ROWS = ['identity', 'unicode_long_path', 'cycles100', 'edit_wall_move', 'edit_param_mark', 'edit_col', 'edit_win', 'edit_door', 'edit_floor', 'edit_text', 'edit_dline']
OK = ('AUDIT_OK', 'OPEN_OK')


def ledger_key(fmt, version):
    return ('RVT' + version) if fmt.lower() == 'rvt' and not version.startswith('RVT') else version


def required(fmt):
    return DWG_ROWS if fmt.lower() == 'dwg' else RVT_ROWS


def missing(ledger_path, fmt, version):
    key = ledger_key(fmt, version); have = set()
    with open(ledger_path, encoding='utf-8') as f:
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) >= 4 and p[1] == key and p[3].split(' ')[0] in OK: have.add(p[2])
    return [r for r in required(fmt) if r not in have]
