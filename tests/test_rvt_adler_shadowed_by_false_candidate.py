"""c4x-rvtgap 447: el:8 of the Autodesk 2024 racbasic family has a second, false header candidate later in the stream whose Adler is invalid; it used to shadow the real record in
the checksum check, so a flipped own Adler of the edited record was ACCEPTED. It must be refused."""
import os, sys, shutil, pytest
for p in ('~/rvt-research', '~/rvt-research/write-lab'): sys.path.insert(0, os.path.expanduser(p))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no public sample')

def test_own_adler_flip_of_el8_refused(tmp_path):
    import wledit, savegate as sg
    e = 8; A = wledit.Editor(SRC); W = A.m.IDW; pn, i, r, log, q = A.trace(e)
    f = [x for x in log if isinstance(x[4], str) and len(x[4]) >= 3 and x[3] - x[2] == 4 + 2 * len(x[4]) and '\x00' not in x[4]][0]
    ed = wledit.Editor(SRC); new = f[4][:-1] + ('Y' if f[4][-1] != 'Y' else 'Z'); ed.set_strings([(e, f[1], new, f[4])]); pt = ed.part(pn)
    off = i + 4 + W; ob = bytes(ed.m.parts[pn]['joined'][off:off + 4]); pt.replace(off, 4, bytes(x ^ 1 for x in ob))
    o = str(tmp_path / 'o.rfa'); ed.save(o); nb = open(o, 'rb').read(); del ed
    cur = str(tmp_path / 'c.rfa'); shutil.copy(SRC, cur); orig = open(cur, 'rb').read()
    with pytest.raises(sg.VerifyFailed):
        sg.save(sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False)), nb, {'modified': ['el:%d' % e]})
    assert open(cur, 'rb').read() == orig
