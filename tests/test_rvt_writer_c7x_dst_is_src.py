"""c7x-rvtread2 item 471: WO.run(src, ops, dst) with dst the same file (or a hard/symlink to it) wrote the original non-atomically; it must refuse and leave the bytes untouched."""
import os, sys, shutil, hashlib, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
from savegate import rvt_writer_ops as WO
S = os.path.expanduser('~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt')
@pytest.mark.parametrize('link', [False, True])
def test_dst_is_src_refused(link, tmp_path):
    p = str(tmp_path / 'a.rvt'); shutil.copy(S, p); h = hashlib.sha1(open(p, 'rb').read()).hexdigest()
    d = p
    if link: d = str(tmp_path / 'b.rvt'); os.symlink(p, d)
    with pytest.raises(ValueError): WO.run(p, [{'op': 'move_textnote', 'id': 916133, 'dx': 1.0}], d)
    assert hashlib.sha1(open(p, 'rb').read()).hexdigest() == h
