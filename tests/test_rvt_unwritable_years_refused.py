"""c2x-rvtgap: an in-place save of any Revit year outside RVT_WRITABLE (2024, 2026) must be refused and leave the original byte-identical,
for every public RAC basic family 2016-2025 (no-edit bytes declared as an el:7 edit, i.e. the most innocent-looking request)."""
import os, shutil, pytest
D = os.path.expanduser('~/rvt-research/samples-rfa/')
YEARS = ['2016', '2017', '2018', '2019', '2020', '2021', '2022', '2023', '2025']
def _p(y):
    for n in ('rac_basic_sample_family-%s.rfa', 'racbasicsamplefamily-%s.rfa'):
        if os.path.exists(D + n % y): return D + n % y

@pytest.mark.parametrize('y', YEARS)
def test_unwritable_year_refused(tmp_path, y):
    import savegate as sg
    s = _p(y)
    if not s: pytest.skip('no sample')
    t = str(tmp_path / 'x.rfa'); shutil.copy(s, t); old = open(t, 'rb').read()
    try: doc = sg.open_doc(t, None, sg.Config(allow_overwrite=True, require_gate=False))
    except sg.SaveError: assert open(t, 'rb').read() == old; return
    with pytest.raises(sg.SaveError): sg.save(doc, old, {'modified': ['el:7']})
    assert open(t, 'rb').read() == old
