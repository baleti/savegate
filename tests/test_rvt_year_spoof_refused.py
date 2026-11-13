"""c7x-rvtread2 564/566: a 2020 file whose BasicFileInfo year text was rewritten to 2024 must not pass the writable-year gate (build stamp disagrees)."""
import os, sys, glob, re, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
S = sorted(glob.glob(os.path.expanduser('~/rvt-research/corpus/2020/*.rvt')))
G = sorted(glob.glob(os.path.expanduser('~/rvt-research/corpus/2024/*.rvt')))
pytestmark = pytest.mark.skipif(not S or not G, reason='no Autodesk samples')

def _spoof(src, tmp_path):
    import cfb
    c = cfb.CFB(open(src, 'rb').read()); st = c.streams()['BasicFileInfo']
    st.data = re.sub('2020'.encode('utf-16le'), '2024'.encode('utf-16le'), st.data, count=1)
    p = str(tmp_path / 's.rvt'); cfb.write(c, p); return open(p, 'rb').read()

def test_spoofed_year_refused(tmp_path):
    from savegate.adapters import RvtAdapter
    from savegate.errors import UnsupportedVersion
    with pytest.raises(UnsupportedVersion): RvtAdapter().sniff(_spoof(S[0], tmp_path))

def test_genuine_writable_years_still_accepted():
    from savegate.adapters import RvtAdapter
    fs = sorted(glob.glob(os.path.expanduser('~/rvt-research/corpus/2024/*.rvt')) + glob.glob(os.path.expanduser('~/rvt-research/corpus/2026/*.rvt')))
    assert fs
    for f in fs: RvtAdapter().sniff(open(f, 'rb').read())      # must not raise
