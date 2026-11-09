"""c4x-rvtgap 245: two chained string edits (el 23 empty->'C2', then el 1083 ->'C4') on the Autodesk 2024/2026 sample families make the edited partition
grow by a whole ECC page (~63 KB of zero tail) although the gzip members got smaller. Valid per the gate, but unexplained bloat (oracle request 244). xfail until the writer owner explains/fixes."""
import os, sys, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
@pytest.mark.xfail(strict=False, reason='c4x-rvtgap 245: page-rounding bloat in chained edits, writer owner')
@pytest.mark.parametrize('yr', ['2024', '2026'])
def test_two_chained_edits_do_not_add_a_page(tmp_path, yr):
    import wledit
    from test_rvt_last_record_string_edit import _last_string_records
    import random
    src = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-%s.rfa' % yr)
    if not os.path.exists(src): pytest.skip('no sample')
    allr = _last_string_records(wledit.Editor(src), 10**6); random.seed(5); picks = random.sample(allr, 5)
    cur = str(tmp_path / 'c.rfa'); shutil.copy(src, cur); size0 = os.path.getsize(cur)
    for k in (2, 4):
        q, eid, fn, old, pn = picks[k]; e = wledit.Editor(cur); e.set_strings([(eid, fn, 'C%d' % k)]); o = str(tmp_path / 'o.rfa'); e.save(o); shutil.copy(o, cur)
    assert os.path.getsize(cur) - size0 < 4096 * 4
