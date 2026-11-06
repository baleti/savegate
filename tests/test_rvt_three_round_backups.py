"""c2x-rvtgap item 25/29: three chained in-place gate saves of one rvt file (edit, save, reopen, edit, save ...): every round is read back, every backup is a restorable
earlier state (restore gives the exact bytes the file had before that round)."""
import os, sys, shutil, hashlib, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no public sample')
H = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()


def test_three_rounds_and_restore(tmp_path):
    import savegate as sg, wledit
    from savegate.adapters import RvtAdapter
    cur = str(tmp_path / 'm.rfa'); shutil.copy(SRC, cur)
    states = [H(cur)]; names = ['Aa', 'Bbb', 'Cccc']
    for n in names:
        ed = wledit.Editor(cur); ed.set_strings([(7, 'FillPattern.m_name', n)]); o = str(tmp_path / 'o.rfa'); ed.save(o)
        new = open(o, 'rb').read()
        doc = sg.open_doc(cur, RvtAdapter(), sg.Config(allow_overwrite=True, require_gate=False))
        sg.save(doc, new, {'modified': ['stream:Partitions/67', 'el:7']})
        assert H(cur) == hashlib.sha256(new).hexdigest()
        RvtAdapter().validate(open(cur, 'rb').read())
        states.append(H(cur))
    assert len(set(states)) == 4
    bk = {H(b[1]) for b in sg.list_backups(cur)}
    assert set(states[:3]) <= bk, 'every earlier state must be among the backups'
    for want in (states[2], states[1], states[0]):
        b = [i for i, x in enumerate(sg.list_backups(cur)) if H(x[1]) == want][0]
        sg.restore(cur, b); assert H(cur) == want
