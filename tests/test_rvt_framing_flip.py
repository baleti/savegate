"""c4x-rvtgap 317/318: a bit flip in the partition FRAMING (44-byte header, 32-byte frames between gzip members, tail after the last member), ECC recomputed, must be refused;
the legitimate size-changing string edit must still be accepted. Autodesk sample family only."""
import os, sys, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-%s.rfa')
@pytest.mark.parametrize('year', ['2024', '2026'])
def test_framing_flip_refused_legit_edit_accepted(tmp_path, year):
    import savegate as sg, wledit, cfb, rvtw, wlpart
    from test_rvt_last_record_string_edit import _last_string_records
    src = SRC % year
    if not os.path.exists(src): pytest.skip('no public sample')
    cfg = sg.Config(allow_overwrite=True, require_gate=False)
    q, eid, fn, old, pn = _last_string_records(wledit.Editor(src), 1)[0]
    ed = wledit.Editor(src); ed.set_strings([(eid, fn, str(old) + 'Z' * 40)]); o = str(tmp_path / 'o.rfa'); ed.save(o); good = open(o, 'rb').read()
    decl = {'modified': ['stream:' + pn, 'el:%d' % eid]}
    cur = str(tmp_path / 'ok.rfa'); shutil.copy(src, cur)
    assert sg.save(sg.open_doc(cur, None, cfg), good, decl).ok
    c0 = cfb.CFB(good); st0 = rvtw.Stream(bytes(c0.streams()[pn].data)); p0 = bytes(st0.payload); P = wlpart.Partition(st0)
    offs = [P.mem[0]['pos'] + 4, P.mem[2]['pos'] + 8, P.mem[5]['pos'] + 9, 0, 12, 30, P.mem[0]['end'], P.mem[0]['end'] + 8, P.mem[0]['end'] + 12, P.mem[3]['end'] + 24, P.mem[3]['end'] + 31, P.mem[P.n - 1]['end'], P.mem[P.n - 1]['end'] + 12]
    for po in offs:
        c = cfb.CFB(good)
        for x in c.entries:
            if x.type == 2: x.data = bytes(x.data)
        x = [x for x in c.entries if x.type == 2 and x.name == pn.split('/')[-1]][0]
        pp = bytearray(p0); pp[po] ^= 0x40; x.data = bytes(rvtw.Stream(x.data).build(bytes(pp)))
        m = str(tmp_path / 'm.rfa'); cfb.write(c, m); cur = str(tmp_path / 'c.rfa'); shutil.copy(src, cur)
        with pytest.raises(Exception):
            sg.save(sg.open_doc(cur, None, cfg), open(m, 'rb').read(), decl)
        assert open(cur, 'rb').read() == open(src, 'rb').read(), 'original damaged at offset %d' % po
