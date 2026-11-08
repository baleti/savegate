"""c4x-rvtgap: in-place save on awkward file names (unicode, spaces, leading dash, newline, name near the 255-byte limit): save + backup + restore must work or refuse cleanly with the original intact."""
import os, shutil, pytest
import savegate as sg
NAMES = ['plan v2 (final).rfa', 'Grundriß Ünï 設計.rfa', '-dash.rfa', 'new\nline.rfa', 'a' * 247 + '.rfa', 'b' * 200 + '.rfa', '.hidden.rfa', 'x.RFA']
@pytest.mark.parametrize('name', NAMES, ids=lambda n: n[:12].encode('unicode_escape').decode())
def test_save_backup_restore(tmp_path, name):
    src = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
    if not os.path.exists(src): pytest.skip('no sample')
    f = str(tmp_path / name); shutil.copy(src, f); orig = open(f, 'rb').read()
    doc = sg.open_doc(f, None, sg.Config(allow_overwrite=True, require_gate=False))
    try: r = sg.save(doc, orig, {})
    except sg.SaveError:
        assert open(f, 'rb').read() == orig; raise
    assert r.backup and os.path.exists(r.backup) and open(r.backup, 'rb').read() == orig
    sg.restore(f); assert open(f, 'rb').read() == orig
    assert sorted(os.listdir(tmp_path)) == sorted([name] + [n for n in os.listdir(tmp_path) if n != name]) and not [n for n in os.listdir(tmp_path) if n.endswith(('.tmp', '.part', '.lock'))]
