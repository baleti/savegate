"""c2x-rvtgap item 45: SOURCE file truncated at a sector boundary / with trailing garbage: an in-place save must refuse (or at least never alter the file into something worse)."""
import os, sys, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no public sample')


@pytest.mark.parametrize('how', ['trunc_sector', 'trunc_mid', 'garbage_tail'])
def test_damaged_source_shape_not_overwritten(tmp_path, how):
    import savegate as sg, wledit
    good = open(SRC, 'rb').read()
    ed = wledit.Editor(SRC); ed.set_strings([(7, 'FillPattern.m_name', 'Edited')])
    o = str(tmp_path / 'o.rfa'); ed.save(o); new = open(o, 'rb').read()
    bad = {'trunc_sector': good[:len(good) - 512 * 4], 'trunc_mid': good[:len(good) - 777], 'garbage_tail': good + os.urandom(1000)}[how]
    cur = str(tmp_path / 'c.rfa'); open(cur, 'wb').write(bad)
    try: doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    except Exception: return                                   # refused at open: fine
    try: sg.save(doc, new, {'modified': ['stream:Partitions/67', 'el:7']})
    except sg.SaveError:
        assert open(cur, 'rb').read() == bad                    # refused, untouched
        return
    # accepted: only allowed when nothing real was lost, i.e. the damage was trailing slack: every source stream survives, only the edited one differs
    import cfb
    A = cfb.CFB(good).streams(); B = cfb.CFB(open(cur, 'rb').read()).streams()
    assert how != 'trunc_sector', 'a file missing whole sectors must not be accepted'
    assert [k for k in A if k not in B or A[k].data != B[k].data] == ['Partitions/67']
