"""c5x-rvtgap 131: malformed manifests never crash with a raw exception and never get a changed file accepted."""
import os, sys, shutil, pytest
import savegate as sg
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
BAD = [None, {}, 5, 'x', [], {'modified': 'file'}, {'modified': None}, {'modified': [1, None]}, {'modified': ['stream:nope']},
       {'modified': ['el:7']}, {'modified': ['stream:Partitions/67']}, {'modified': ['el:' + str(i) for i in range(5000)]},
       {'modified': ['el:7'], 'x': object()}, {'modified': {'el:7': 1}}, {'modified': ['file']}]
@pytest.mark.skipif(not os.path.exists(F), reason='no sample')
@pytest.mark.parametrize('i', range(len(BAD)))
def test_manifest(tmp_path, i):
    sys.path[:0] = [os.path.expanduser('~/rvt-research/write-lab'), os.path.expanduser('~/rvt-research')]
    import wledit
    t = tmp_path / 'x.rfa'; shutil.copy(F, t)
    ed = wledit.Editor(str(t)); ed.set_strings([(7, 'FillPattern.m_name', 'Edited')]); o = str(tmp_path / 'o.bin'); ed.save(o)
    new = open(o, 'rb').read(); orig = t.read_bytes()
    doc = sg.open_doc(str(t), None, sg.Config(allow_overwrite=True, require_gate=False, journal_dir=str(tmp_path / 'j')))
    try: ok = sg.save(doc, new, BAD[i]).ok; err = None
    except sg.SaveError as e: ok = False; err = e
    except Exception as e: ok = False; err = 'RAW %r' % e
    assert not isinstance(err, str), (BAD[i] if i != 11 else 'big', err)
    if ok: assert t.read_bytes() == new      # accepted only as the complete new file
    else: assert t.read_bytes() == orig
    print(i, 'accepted' if ok else 'refused')
