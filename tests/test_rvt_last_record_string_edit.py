"""c4x-rvtgap: string edits in the LAST records of a partition stream (record end == payload end region), grown and shrunk, 2024 + 2026 families: gate accepts the honest save, refuses collateral."""
import os, sys, shutil, pytest
import savegate as sg
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
def _last_string_records(ed, n=3):
    out = []
    for eid in ed.m.ids:
        try: pn, i, r, log, q = ed.trace(eid)
        except Exception: continue
        for l in log:
            if l[4] in ('None', None): continue          # null pointer fields are not strings (see test_null_pointer_field_refused)
            try: ed._check_wstr(pn, l)
            except Exception: continue
            out.append((q, eid, l[1], l[4], pn)); break
    out.sort(reverse=True); return out[:n]
@pytest.mark.parametrize('yr', ['2024', '2026'])
@pytest.mark.parametrize('how', ['grow', 'shrink'])
def test_last_records(tmp_path, yr, how):
    import wledit
    src = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-%s.rfa' % yr)
    if not os.path.exists(src): pytest.skip('no sample')
    cands = _last_string_records(wledit.Editor(src)); assert cands
    for q, eid, fn, old, pn in cands:
        ed = wledit.Editor(src); new = (str(old) + 'Z' * 40) if how == 'grow' else 'Q'
        ed.set_strings([(eid, fn, new)]); o = str(tmp_path / ('o%d.rfa' % eid)); ed.save(o); good = open(o, 'rb').read()
        cur = str(tmp_path / ('c%d.rfa' % eid)); shutil.copy(src, cur); before = open(cur, 'rb').read()
        doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
        r = sg.save(doc, good, {'modified': ['stream:' + pn, 'el:%d' % eid]}); assert r.ok
        # readback: the edited string is what the file now says, nothing else moved
        e2 = wledit.Editor(cur); t = [l for l in e2.trace(eid)[3] if l[1] == fn][0]; assert t[4] == new
        # collateral: same save but one bit flipped inside the partition payload elsewhere is refused (original untouched)
        b = bytearray(good); b[len(b) // 3] ^= 1
        cur2 = str(tmp_path / ('d%d.rfa' % eid)); shutil.copy(src, cur2)
        doc2 = sg.open_doc(cur2, None, sg.Config(allow_overwrite=True, require_gate=False))
        with pytest.raises(sg.SaveError): sg.save(doc2, bytes(b), {'modified': ['stream:' + pn, 'el:%d' % eid]})
        assert open(cur2, 'rb').read() == before


def test_null_pointer_field_refused():
    """the writer used to accept 'Element.m_geomSteps' (4 zero bytes, logged None) as an empty string and write text into a pointer field"""
    import wledit
    src = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
    if not os.path.exists(src): pytest.skip('no sample')
    ed = wledit.Editor(src)
    with pytest.raises(ValueError): ed.set_strings([(6192, 'Element.m_geomSteps', 'junk')])
