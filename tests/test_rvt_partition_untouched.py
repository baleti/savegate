"""c2x-rvtgap item 5/6: after a string edit the writer must reproduce every OTHER partition member (unknown classes, records it cannot parse) byte for byte,
and the edited member may differ only in a window around the edit. Public Autodesk samples, all years where the edit is accepted."""
import os, sys, glob, tempfile, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SAMPLES = sorted(glob.glob(os.path.expanduser('~/rvt-research/samples-rfa/*.rfa')))
pytestmark = pytest.mark.skipif(not SAMPLES, reason='no public samples')


def _members(path):
    import wlrec, wlpart
    m = wlrec.Model(path); out = {}
    for pn in m.parts:
        if pn.startswith('Partitions/'):
            try: p = wlpart.Partition(m.parts[pn]['stream'], hs=12 + m.IDW)
            except Exception: continue
            out[pn] = [bytes(x['raw']) for x in p.mem]
    return out


@pytest.mark.parametrize('path', SAMPLES, ids=[os.path.basename(p)[-9:] for p in SAMPLES])
def test_edit_leaves_all_other_members_and_unknown_records_identical(path, tmp_path):
    import wledit
    ed = wledit.Editor(path)
    try: ed.set_strings([(7, 'FillPattern.m_name', 'HorizontalZ')])
    except Exception as e: pytest.skip('edit not applicable: %s' % e)
    o = str(tmp_path / 'o.rfa'); ed.save(o)
    a, b = _members(path), _members(o)
    assert a.keys() == b.keys()
    changed = 0
    for pn in a:
        x, y = b''.join(a[pn]), b''.join(b[pn])
        if x == y: continue
        changed += 1
        p = 0
        while p < min(len(x), len(y)) and x[p] == y[p]: p += 1
        s = 0
        while s < min(len(x), len(y)) - p and x[-1 - s] == y[-1 - s]: s += 1
        # the record payload of the whole partition (member boundaries aside: the writer may re-chunk members over the size limit) differs only around the edit
        assert len(x) - p - s <= 1024 and len(y) - p - s <= 1024, '%s: changed window %d/%d bytes' % (pn, len(x) - p - s, len(y) - p - s)
    assert changed == 1, 'exactly one partition must change, %d did' % changed
