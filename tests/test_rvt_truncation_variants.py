"""c7x-rvtread2 item 526: a truncated copy of an RVT must never be accepted as a clean SOURCE (it would be re-saved looking healthy).
Public Autodesk 2024 template. Cuts that remove data (99/75/50/25 percent, the last data byte, header only, empty) must be flagged by RvtAdapter.source_damage; cutting only
the zero padding after the last data byte is harmless and may stay clean (guard against a rule so strict that it flags the padding). Guard test, no known bug behind it."""
import os, pytest
SRC = os.path.expanduser('~/rvt-research/corpus/2024/71_Construction-DefaultMetric.rte')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no Autodesk sample')


@pytest.fixture(scope='module')
def data():
    return open(SRC, 'rb').read()


@pytest.mark.parametrize('frac', [0.99, 0.75, 0.5, 0.25])
def test_fraction_cut_flagged(data, frac):
    from savegate.adapters import RvtAdapter
    assert RvtAdapter().source_damage(data[:int(len(data) * frac)])


@pytest.mark.parametrize('cut', ['header', 'empty'])
def test_tiny_flagged(data, cut):
    from savegate.adapters import RvtAdapter
    assert RvtAdapter().source_damage(data[:512] if cut == 'header' else b'')


def test_last_data_byte_cut_flagged_but_zero_padding_ok(data):
    from savegate.adapters import RvtAdapter
    p = max(i for i in range(len(data)) if data[i])
    assert RvtAdapter().source_damage(data[:p]), 'a cut that removes the last non-zero byte must be flagged'
    assert RvtAdapter().source_damage(data) == []
    assert RvtAdapter().source_damage(data[:p + 1]) == [], 'cutting only the zero padding after the last data byte is harmless'
