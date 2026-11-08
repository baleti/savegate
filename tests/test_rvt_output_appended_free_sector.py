"""c4x-rvtgap: c1x-review i375/i376 found an output with 4096 zero bytes (whole free sector) appended at EOF was ACCEPTED. Now refused; the honest output is accepted."""
import os, sys, shutil, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
@pytest.mark.parametrize('yr', ['2024', '2026'])
def test_appended_sectors(tmp_path, yr):
    import savegate as sg, wledit
    src = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-%s.rfa' % yr)
    if not os.path.exists(src): pytest.skip('no sample')
    ed = wledit.Editor(src); ed.set_strings([(7, 'FillPattern.m_name', 'Tail probe')]); o = str(tmp_path / 'o.rfa'); ed.save(o); good = open(o, 'rb').read()
    man = {'modified': ['stream:Partitions/67', 'el:7']}
    for extra, ok in ((b'', True), (b'\0' * 4096, False), (b'\0' * 512, False)):
        cur = str(tmp_path / ('c%d.rfa' % len(extra))); shutil.copy(src, cur); before = open(cur, 'rb').read()
        doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
        if ok: sg.save(doc, good + extra, man)
        else:
            with pytest.raises(sg.SaveError): sg.save(doc, good + extra, man)
            assert open(cur, 'rb').read() == before
