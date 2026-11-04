"""c7x-rvtread2 64: an all-zero Global/ElemTable (valid zero ECC pages, no gzip member) passed source_damage in 11/11 public samples 2016-2026."""
import os, sys, tempfile, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab'))
from savegate import adapters
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')

@pytest.mark.skipif(not os.path.exists(F), reason='public sample missing')
@pytest.mark.parametrize('name', ['Global/ElemTable', 'Global/History', 'Global/Latest'])
def test_zeroed_global_stream_reported(name):
    cfb = pytest.importorskip('cfb'); b = open(F, 'rb').read(); A = adapters.RvtAdapter(); assert A.source_damage(b) == []
    c = cfb.CFB(b); e = c.streams()[name]; e.data = bytes(len(e.data)); o = tempfile.mkdtemp() + '/z.rfa'; cfb.write(c, o)
    assert A.source_damage(open(o, 'rb').read())


@pytest.mark.skipif(not os.path.exists(F), reason='public sample missing')
@pytest.mark.parametrize('how', ['empty', 'zero'])
def test_empty_or_zeroed_formats_latest_reported(how):
    """c7x-rvtread2 65: Formats/Latest (the class/schema table) emptied or zeroed was accepted in 3/3 samples."""
    cfb = pytest.importorskip('cfb'); b = open(F, 'rb').read(); A = adapters.RvtAdapter()
    c = cfb.CFB(b); e = c.streams()['Formats/Latest']; e.data = b'' if how == 'empty' else bytes(len(e.data)); o = tempfile.mkdtemp() + '/z.rfa'; cfb.write(c, o)
    assert A.source_damage(open(o, 'rb').read())


@pytest.mark.skipif(not os.path.exists(F), reason='public sample missing')
def test_truncated_png_preview_reported():
    cfb = pytest.importorskip('cfb'); b = open(F, 'rb').read(); A = adapters.RvtAdapter()
    c = cfb.CFB(b); e = c.streams()['RevitPreview4.0']; e.data = e.data[:len(e.data) // 2]; o = tempfile.mkdtemp() + '/z.rfa'; cfb.write(c, o)
    assert A.source_damage(open(o, 'rb').read())
