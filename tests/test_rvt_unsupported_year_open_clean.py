"""c2x-rvtgap 143: opening an Autodesk sample rfa of a non-writable year (2016-2023, 2025) is refused with UnsupportedVersion; file byte-identical and the folder holds only the file (no backup, lock or .savegate)."""
import os, shutil, glob, pytest
import savegate as sg
from savegate.errors import UnsupportedVersion
D = os.path.expanduser('~/rvt-research/samples-rfa/')
FILES = [f for f in sorted(glob.glob(D + '*.rfa')) if not f.endswith(('-2024.rfa', '-2026.rfa'))]
@pytest.mark.skipif(not FILES, reason='no samples')
@pytest.mark.parametrize('f', FILES, ids=os.path.basename)
def test_open_refused_clean(tmp_path, f):
    t = str(tmp_path / 'y.rfa'); shutil.copy(f, t); orig = open(t, 'rb').read()
    with pytest.raises(UnsupportedVersion): sg.open_doc(t, None, sg.Config(allow_overwrite=True, require_gate=False))
    assert open(t, 'rb').read() == orig and os.listdir(tmp_path) == ['y.rfa']
