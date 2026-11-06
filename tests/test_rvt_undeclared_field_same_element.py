"""c2x-rvtgap item 53: two numeric fields of ONE element change (record restamped, Adler valid), only one is declared (expect): the gate must refuse (undeclared collateral field);
declaring both is accepted."""
import os, sys, struct, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
R = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-%s.rfa')
YEARS = [y for y in ('2024', '2026') if os.path.exists(R % y)]
SRC = [None]
pytestmark = pytest.mark.skipif(not YEARS, reason='no public sample')


def wledit_pn():
    import wledit
    return wledit.Editor(SRC[0]).trace(7)[0]


def _out(tmp_path):
    import wledit
    ed = wledit.Editor(SRC[0]); log = ed.trace(7)[3]
    a = next(x for x in log if x[1] == 'FillPattern.m_scale'); b = next(x for x in log if x[1] == 'FillPattern.m_windowSize')
    n = b[3] - b[2]; assert n == 8, n
    items = sorted([(a[2], 8, struct.pack('<d', 3.5)), (b[2], n, struct.pack('<d', 0.25))], reverse=True)
    ed.modify(7, items); o = str(tmp_path / 'o.rfa'); ed.save(o); return open(o, 'rb').read(), b[4]


def _save(tmp_path, new, expect):
    import savegate as sg
    cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC[0], cur); before = open(cur, 'rb').read()
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    try: sg.save(doc, new, {'modified': ['stream:' + wledit_pn(), 'el:7'], 'expect': {7: expect}}); return True, cur, before
    except sg.SaveError as e: print('REFUSED:', str(e)[:300]); return False, cur, before


@pytest.mark.parametrize('year', YEARS)
def test_undeclared_second_field_refused_declared_both_accepted(tmp_path, year):
    SRC[0] = R % year
    new, old = _out(tmp_path)
    ok, cur, before = _save(tmp_path, new, {'FillPattern.m_scale': 3.5})
    assert not ok and open(cur, 'rb').read() == before, 'undeclared windowSize change accepted'
    ok, cur, before = _save(tmp_path, new, {'FillPattern.m_scale': 3.5, 'FillPattern.m_windowSize': 0.25})
    assert ok and open(cur, 'rb').read() == new, 'declaring both changes must be accepted'
