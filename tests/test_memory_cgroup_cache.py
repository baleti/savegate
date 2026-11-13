"""c5x item 251: page cache counted in cgroup memory.current is reclaimable and must not make the memory preflight refuse a save"""
from savegate.core import _parse_reclaimable


def test_parse_reclaimable_sums_file_cache():
    t = 'anon 100\nfile 900\ninactive_file 300\nactive_file 200\nshmem 50\n'
    assert _parse_reclaimable(t) == 500


def test_parse_reclaimable_missing_or_garbage():
    assert _parse_reclaimable('') == 0
    assert _parse_reclaimable('inactive_file x\nactive_file\n') == 0


def test_trim_heap_never_raises():
    from savegate.core import _trim_heap
    _trim_heap()
