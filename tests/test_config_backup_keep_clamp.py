"""c5x-rvtgap item 119: Config(backup_keep=0/1/-1) kept ONE backup, so the original was lost after the 2nd save; None/'3'/2.5 raised a raw TypeError inside save. Now: ints below 2 are raised to 2 (original pinned), non-int refused at construction."""
import os, pytest
import savegate as sg


@pytest.mark.parametrize('v', [0, 1, -1, -100])
def test_small_keep_is_raised_to_two(v):
    assert sg.Config(backup_keep=v).backup_keep == 2


@pytest.mark.parametrize('v', [None, '3', 2.5, True, [2]])
def test_non_int_keep_refused(v):
    with pytest.raises(ValueError): sg.Config(backup_keep=v)


def test_original_survives_three_saves_with_keep_one(tmp_path):
    import sys
    sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
    S = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
    if not os.path.exists(S): pytest.skip('no public sample')
    import wledit
    p = str(tmp_path / 'a.rfa'); orig = open(S, 'rb').read(); open(p, 'wb').write(orig)
    cfg = sg.Config(allow_overwrite=True, require_gate=False, backup_keep=1)
    for txt in ('A', 'BB', 'CCC'):
        ed = wledit.Editor(p); ed.set_strings([(7, 'FillPattern.m_name', txt)]); o = str(tmp_path / 'n.rfa'); ed.save(o)
        sg.save(sg.open_doc(p, None, cfg), open(o, 'rb').read(), {'modified': ['stream:Partitions/67', 'el:7']})
    assert any(open(b[1], 'rb').read() == orig for b in sg.list_backups(p))
