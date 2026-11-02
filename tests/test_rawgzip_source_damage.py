"""c7x-rvtread2: Formats/Latest is a raw-gzip stream whose 8-byte tail is NOT a valid crc32/isize (2018/2024/2026 public samples),
so a crc rule gives false positives on clean files and cannot detect flips. Requirements that are checkable:
 1. source_damage == [] on clean Autodesk samples (a crc rule would flag them and refuse every save);
 2. an unedited save_as keeps Formats/Latest byte-identical to the source (writable years)."""
import os, sys, pytest
from savegate import adapters, core
S = os.path.expanduser('~/rvt-research/samples-rfa/')
FILES = ['rac_basic_sample_family-2018.rfa', 'racbasicsamplefamily-2024.rfa', 'racbasicsamplefamily-2026.rfa']

@pytest.mark.parametrize('f', FILES)
def test_clean_sample_has_no_damage(f):
    if not os.path.exists(S + f): pytest.skip('public sample missing')
    assert adapters.RvtAdapter().source_damage(open(S + f, 'rb').read()) == []

@pytest.mark.parametrize('f', FILES[1:])
def test_identity_save_keeps_formats_latest(f, tmp_path):
    if not os.path.exists(S + f): pytest.skip('public sample missing')
    A = adapters.RvtAdapter(); sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); import cfb
    b = open(S + f, 'rb').read(); p = str(tmp_path / 'in.rfa'); d = str(tmp_path / 'out.rfa'); open(p, 'wb').write(b)
    core.save_as(core.open_doc(p, A, journal=False), b, d)
    assert cfb.CFB(open(d, 'rb').read()).streams()['Formats/Latest'].data == cfb.CFB(b).streams()['Formats/Latest'].data
