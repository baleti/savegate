"""c4x-rvtgap item 464: public 2024 racbasic family: a same-length string edit of el:23 (a name) is refused by default ('changed el:22', derived view of a neighbour whose record bytes are identical;
9 of 28 string edits on this family behave so); with manifest derived_ok=True it is accepted, while one bit flip inside the neighbour el:22 record or in its header is still refused."""
import os, sys, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no public sample')
E, N = 23, 22


def _out(tmp_path, flip):
    import wledit
    A = wledit.Editor(SRC); pn, i, r, log, q = A.trace(E); tn = A.trace(N); assert tn[0] == pn; N0, N1 = tn[1], tn[4]; del A
    f = [x for x in log if isinstance(x[4], str) and len(x[4]) >= 3 and x[3] - x[2] == 4 + 2 * len(x[4]) and '\x00' not in x[4]][0]
    new = f[4][:-1] + ('Y' if f[4][-1] != 'Y' else 'Z')
    ed = wledit.Editor(SRC); ed.set_strings([(E, f[1], new, f[4])])
    off = {None: None, 'body': (N0 + N1) // 2, 'hdr': N0 + 4}[flip]
    if off is not None: b = ed.m.parts[pn]['joined']; ed.part(pn).replace(off, 1, bytes([b[off] ^ 1]))
    o = str(tmp_path / 'o.rfa'); ed.save(o); return open(o, 'rb').read()


def _save(tmp_path, nb, derived):
    import savegate as sg
    cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur)
    man = {'modified': ['el:%d' % E]}
    if derived: man['derived_ok'] = True
    sg.save(sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False, journal_dir=str(tmp_path / 'j'))), nb, man)


def test_default_refuses_derived_neighbour(tmp_path):
    import savegate as sg
    with pytest.raises(sg.SaveError): _save(tmp_path, _out(tmp_path, None), False)


def test_derived_ok_accepts_clean(tmp_path):
    _save(tmp_path, _out(tmp_path, None), True)


@pytest.mark.parametrize('flip', ['body', 'hdr'])
def test_derived_ok_still_refuses_neighbour_flip(tmp_path, flip):
    import savegate as sg
    with pytest.raises(sg.SaveError): _save(tmp_path, _out(tmp_path, flip), True)
