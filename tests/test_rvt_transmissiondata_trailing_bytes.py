"""c5x-rvtread2 item 117: the TransmissionData rule demanded 4 + 2*n == len(stream). 8 of 269 real (local) files carry extra bytes after the declared XML (2 or 110) and were reported as damaged, so a valid
in-place save was refused. Trailing bytes are fine; a stream shorter than its declared length (truncation) must still be reported."""
import os, sys, struct, tempfile, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab'))
from savegate import adapters
F = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(F), reason='public sample missing')


def _with(data):
    cfb = pytest.importorskip('cfb'); c = cfb.CFB(open(F, 'rb').read()); c.streams()['TransmissionData'].data = data
    o = tempfile.mkdtemp() + '/t.rfa'; cfb.write(c, o); return open(o, 'rb').read()


def _orig():
    cfb = pytest.importorskip('cfb'); return cfb.CFB(open(F, 'rb').read()).streams()['TransmissionData'].data


def test_trailing_bytes_after_declared_xml_are_not_damage():
    d = _orig(); assert adapters.RvtAdapter().source_damage(_with(d)) == []
    assert adapters.RvtAdapter().source_damage(_with(d + '\n'.encode('utf-16le'))) == []
    assert adapters.RvtAdapter().source_damage(_with(d + b'\0' * 110)) == []


def test_truncated_transmissiondata_is_still_damage():
    d = _orig(); assert adapters.RvtAdapter().source_damage(_with(d[:len(d) // 2]))
