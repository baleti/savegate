import os, savegate as sg
from savegate.journal import Journal

def test_journal_dir_is_a_file(tmp_path):
    f = tmp_path / 'afile'; f.write_text('x')
    j = Journal(str(tmp_path / 'src.rvt'), str(f))
    j.log('x'); j.close(done=True)
    assert f.read_text() == 'x'

def test_journal_dir_readonly(tmp_path):
    d = tmp_path / 'ro'; d.mkdir(); os.chmod(d, 0o500)
    try:
        j = Journal(str(tmp_path / 'src.rvt'), str(d)); j.log('x'); j.close(done=True)
        assert os.listdir(d) == []
    finally:
        os.chmod(d, 0o700)

def test_journal_dir_under_file(tmp_path):
    f = tmp_path / 'afile'; f.write_text('x')
    j = Journal(str(tmp_path / 'src.rvt'), str(f / 'sub')); j.log('x'); j.close(done=False)
    os.remove(j.path) if os.path.exists(j.path) and j.path != os.devnull else None
