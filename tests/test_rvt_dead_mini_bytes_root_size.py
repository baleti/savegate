"""c4x-rvtgap 399: a source whose OLE Root Entry size (mini-stream size) exceeds the bytes referenced by its small streams (dead Revit leftovers, seen in 1 of 60 real
families) was REFUSED on a no-edit save ('1 differences outside the declared edit: meta:dirmeta') because the writer re-packs the mini stream compactly. The snapshot now
compares only 'root size covers every small stream' so the compact output is accepted; a root size SMALLER than the small streams still differs."""
import os, sys, struct, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))

def _patched(b, delta):
    name = 'Root Entry'.encode('utf-16le'); i = b.find(name)
    assert i >= 0
    b = bytearray(b); (sz,) = struct.unpack_from('<I', b, i + 120); struct.pack_into('<I', b, i + 120, sz + delta); return bytes(b)

def test_root_size_dead_bytes_not_a_difference():
    SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
    if not os.path.exists(SRC): pytest.skip('no sample')
    from savegate.adapters import RvtAdapter
    b = open(SRC, 'rb').read(); a = RvtAdapter()
    base = a.snapshot(b)['meta:dirmeta']
    assert a.snapshot(_patched(b, 192))['meta:dirmeta'] == base          # dead bytes: source larger than the compact output
    assert a.snapshot(_patched(b, -64))['meta:dirmeta'] != base      # root size smaller than the small streams need: still a difference
