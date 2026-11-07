"""c5x-rvtgap RVT-EDIT rung 1: MOVE a TextNote (916133 of the Autodesk Snowdon Towers Structural 2024 project, +1.0 / +0.5 ft in view coordinates) through the writer op move_textnote: TextElement.m_orig and all
leader points move together. And a text note ADDED at a new position carries its leader points with it (the add used to leave them at the template position). Gate recomputes the writer result."""
import os, sys, struct, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt'); EL = 916133
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no Autodesk sample')
MOVE = [{'op': 'move_textnote', 'id': EL, 'dx': 1.0, 'dy': 0.5}]
ADD = [{'op': 'add_textnote', 'template': EL, 'x': -60.0, 'y': 20.0, 'text': 'ADDED BY SAVEGATE'}]


def _pts(path, el):
    import wledit
    a = wledit.Editor(path); t = a.trace(el); b = a.m.parts[t[0]]['joined']
    return {n: [struct.unpack('<3d', b[x[2]:x[3]]) for x in t[3] if x[1] == n and x[3] - x[2] == 24] for n in ('TextElement.m_orig', 'Leader.m_end', 'Leader.m_elbow', 'Leader.m_anchor')}


def _gate(tmp_path, ops, added=()):
    import savegate as sg
    from savegate import rvt_writer_ops as WO
    o = str(tmp_path / 'o.rvt'); ids = WO.run(SRC, ops, o); nb = open(o, 'rb').read()
    cur = str(tmp_path / 'c.rvt'); shutil.copy(SRC, cur)
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False, backup_keep=2))
    sg.save(doc, nb, {'writer_ops': ops, 'added': ['el:%d' % i for i in ids]}); assert open(cur, 'rb').read() == nb
    return cur, ids


def test_move_shifts_origin_and_leaders(tmp_path):
    cur, ids = _gate(tmp_path, MOVE); old = _pts(SRC, EL); new = _pts(cur, EL)
    for k in old:
        assert old[k] and len(old[k]) == len(new[k])
        for p, q in zip(old[k], new[k]): assert q == pytest.approx((p[0] + 1.0, p[1] + 0.5, p[2]))


def test_added_note_carries_its_leaders(tmp_path):
    cur, ids = _gate(tmp_path, ADD); old = _pts(SRC, EL); new = _pts(cur, ids[0])
    dx, dy = -60.0 - old['TextElement.m_orig'][0][0], 20.0 - old['TextElement.m_orig'][0][1]
    assert new['TextElement.m_orig'][0] == pytest.approx((-60.0, 20.0, 0.0))
    for k in ('Leader.m_end', 'Leader.m_elbow', 'Leader.m_anchor'):
        for p, q in zip(old[k], new[k]): assert q == pytest.approx((p[0] + dx, p[1] + dy, p[2]))
