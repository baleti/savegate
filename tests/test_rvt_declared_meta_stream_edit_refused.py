"""c4x-rvtgap: an HONEST, structurally valid change to BasicFileInfo / RevitPreview4.0 / TransmissionData declared in the manifest is refused by design (Revit writes these; our writer must not), with a message that names the stream; original untouched."""
import os, sys, shutil, pytest
import savegate as sg
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
@pytest.mark.parametrize('yr', ['2024', '2026'])
@pytest.mark.parametrize('stream', ['BasicFileInfo', 'RevitPreview4.0', 'TransmissionData'])
def test_declared_meta_edit_refused(tmp_path, yr, stream):
    import cfb
    src = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-%s.rfa' % yr)
    if not os.path.exists(src): pytest.skip('no sample')
    raw = open(src, 'rb').read(); c = cfb.CFB(raw); e = c.streams()[stream]
    d = bytearray(e.data)
    if stream == 'BasicFileInfo':
        i = d.find('Build'.encode('utf-16le')); d[i + 12] ^= 0x01          # a character inside the build text: still valid, still ends in CRLF
    elif stream == 'RevitPreview4.0':
        i = d.find(b'IDAT'); d[i + 8] ^= 1
    else: d[-1] ^= 1
    e.data = bytes(d); o = str(tmp_path / 'o.rfa'); cfb.write(c, o); out = open(o, 'rb').read()
    cur = str(tmp_path / 'c.rfa'); shutil.copy(src, cur)
    doc = sg.open_doc(cur, None, sg.Config(allow_overwrite=True, require_gate=False))
    with pytest.raises(sg.SaveError) as ei: sg.save(doc, out, {'modified': ['stream:' + stream]})
    assert stream in str(ei.value) or 'metadata' in str(ei.value).lower() or 'differ' in str(ei.value).lower(), str(ei.value)
    assert open(cur, 'rb').read() == raw
