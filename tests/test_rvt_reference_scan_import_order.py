"""c4x-rvtgap SEV1: rvt_decode.Dec.STOP (skip GeomStepList/GeomTable) is fixed when rvt_decode is first imported. If anything imported it before RVT_GEOM=1 was set (a writer module, a host app),
the delete-reference scan decoded fewer fields and returned [] for an element that two others reference: a dangling delete was ACCEPTED. Autodesk Snowdon sample, el 730441 (referrers 585174, 795061)."""
import os, subprocess, sys, pytest
SRC = os.path.expanduser('~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no Autodesk sample')
CODE = """
import sys, os
sys.path.insert(0, %r); sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
%s
import savegate.adapters as A
a = A.RvtAdapter(); a._src_buf = open(%r, 'rb').read()
print(repr(a._delete_reference_checks({'deleted': ['el:730441']})))
"""
PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _run(pre):
    env = {k: v for k, v in os.environ.items() if k != 'RVT_GEOM'}
    return subprocess.run([sys.executable, '-c', CODE % (PKG, pre, SRC)], env=env, capture_output=True, text=True, timeout=600).stdout

def test_reader_imported_before_savegate_never_yields_an_empty_scan():
    out = _run('import rvt_decode')            # truncated decoder state, as after a writer import
    assert out.strip() != '[]' and ('dangling_after_delete' in out or 'delete_references_unchecked' in out), out

def test_savegate_import_enables_geometry_decoding():
    out = _run('')
    assert 'dangling_after_delete' in out and '585174' in out, out

def test_element_view_refuses_a_truncated_reader():
    code = ("import sys, os\nsys.path.insert(0, %r); sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))\n"
            "import rvt_decode\nfrom savegate import rvt_elements as R\n"
            "try:\n    R._elements(open(%r,'rb').read()); print('ACCEPTED')\nexcept Exception as e: print('REFUSED', e)\n") % (PKG, SRC)
    env = {k: v for k, v in os.environ.items() if k != 'RVT_GEOM'}
    out = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True, timeout=900).stdout
    assert 'REFUSED' in out and 'ACCEPTED' not in out, out

@pytest.mark.parametrize('flag', ['RVT_NOHOST', 'RVT_NOUNIV', 'RVT_OLDCAND'])
def test_element_view_refuses_reader_debug_switches(flag, monkeypatch):
    from savegate import rvt_elements as R
    monkeypatch.setenv(flag, '1')
    with pytest.raises(RuntimeError): R._elements(b'x')
