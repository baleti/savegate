"""c7x-rvtread2 111: an emptied element partition made rvt2text exit 0 with half the text and no hint."""
import os, sys, subprocess, tempfile, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab'))
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
T = os.path.expanduser('~/rvt-research/rvt2text.py')

@pytest.mark.skipif(not os.path.exists(F), reason='public sample missing')
def test_empty_partition_warned():
    cfb = pytest.importorskip('cfb'); c = cfb.CFB(open(F, 'rb').read())
    n = sorted(k for k in c.streams() if k.startswith('Partitions/'))[-1]
    c.streams()[n].data = b''; d = tempfile.mkdtemp(); o = d + '/z.rfa'; cfb.write(c, o)
    env = dict(os.environ, RVT_NOCACHE='1')
    r = subprocess.run([sys.executable, T, o], capture_output=True, env=env, timeout=120)
    assert b'INCOMPLETE' in r.stdout and b'INCOMPLETE' in r.stderr
    r0 = subprocess.run([sys.executable, T, F], capture_output=True, env=env, timeout=120)
    assert b'INCOMPLETE' not in r0.stdout


@pytest.mark.skipif(not os.path.exists(F), reason='public sample missing')
def test_member_boundary_truncation_warned():
    """c7x-rvtread2 112: partition cut after the last gzip member (trailer dropped) was read silently."""
    cfb = pytest.importorskip('cfb'); rvtw = pytest.importorskip('rvtw'); sys.path.insert(0, os.path.dirname(T)); import rvt2text as R
    c = cfb.CFB(open(F, 'rb').read()); n = sorted(k for k in c.streams() if k.startswith('Partitions/'))[-1]
    st = rvtw.Stream(c.streams()[n].data); end = R._member_spans(st.payload)[-1][1]
    c.streams()[n].data = st.build(st.payload[:end]); d = tempfile.mkdtemp(); o = d + '/z.rfa'; cfb.write(c, o)
    env = dict(os.environ, RVT_NOCACHE='1')
    r = subprocess.run([sys.executable, T, o], capture_output=True, env=env, timeout=120)
    assert b'TRUNCATED' in r.stdout and b'TRUNCATED' in r.stderr
    r0 = subprocess.run([sys.executable, T, F], capture_output=True, env=env, timeout=120)
    assert b'TRUNCATED' not in r0.stdout
