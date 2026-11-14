"""c7x-rvtread2 627: 20 chained same-length declared string edits saved in place on an Autodesk sample family must not make the Partitions stream grow
by whole pages (wledit _shrinkpad/FULLPAD ratchet, see ~/demo-state/c7x-wledit-pagegrowth-finding.md). xfail(strict) until the writer fix lands: it then XPASSes and strict mode forces removing the marker."""
import os, sys, shutil, pytest
import savegate as sg
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
R = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-%s.rfa')
@pytest.mark.xfail(strict=True, reason='wledit page-growth ratchet (c7x-rvtread2 625/626)')
@pytest.mark.parametrize('year', ['2024', '2026'])
def test_size_stable(tmp_path, year):
    import wledit
    if not os.path.exists(R % year): pytest.skip('no sample')
    t = str(tmp_path / 'a.rfa'); shutil.copy(R % year, t); sizes = []
    for g in range(1, 21):
        ed = wledit.Editor(t); pn = ed.trace(7)[0]; ed.set_strings([(7, 'FillPattern.m_name', 'Same length %02d' % g)]); o = str(tmp_path / 'o'); ed.save(o)
        sg.save(sg.open_doc(t, None, sg.Config(allow_overwrite=True, require_gate=False, backup_keep=0)), open(o, 'rb').read(), {'modified': ['stream:' + pn, 'el:7']})
        sizes.append(os.path.getsize(t))
    assert max(sizes) - min(sizes) < 4096 * 4, sizes
