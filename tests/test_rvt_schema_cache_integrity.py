"""c4x-rvtgap: ES/format schema cache entries carry an HMAC; a corrupt, swapped or legacy raw pickle is a miss (rebuilt), never trusted."""
import os, sys, pickle, pytest
import savegate  # noqa: first, sets RVT_GEOM before any reader import
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
def test_roundtrip_and_tamper(tmp_path, monkeypatch):
    import fmt_parser as fp
    monkeypatch.setattr(fp, '_CD', str(tmp_path))
    f = str(tmp_path / 'es-x.pkl'); fp.cache_dump({'a': 1}, f); assert fp.cache_load(f) == {'a': 1}
    b = bytearray(open(f, 'rb').read()); b[-3] ^= 1; open(f, 'wb').write(bytes(b))
    with pytest.raises(ValueError): fp.cache_load(f)                       # flipped payload
    open(f, 'wb').write(pickle.dumps({'evil': 1}))
    with pytest.raises(Exception): fp.cache_load(f)                        # legacy raw pickle
    fp.cache_dump({'a': 1}, f); good = open(f, 'rb').read(); fp.cache_dump({'b': 2}, f); other = open(f, 'rb').read()
    open(f, 'wb').write(good[:32] + other[32:])
    with pytest.raises(ValueError): fp.cache_load(f)                       # digest of another payload
def test_real_load_rebuilds_corrupt_entry(tmp_path, monkeypatch):
    import rvt_es, fmt_parser as fp
    monkeypatch.setattr(fp, '_CD', str(tmp_path)); monkeypatch.setattr(os.path, 'expanduser', (lambda o: (lambda p: str(tmp_path) if p == '~/.cache/rvt-schema' else o(p)))(os.path.expanduser))
    src = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2024.rfa')
    if not os.path.exists(src): pytest.skip('no sample')
    r1, _ = rvt_es.load(src); ents = [x for x in os.listdir(tmp_path) if x.startswith('es-')]; assert ents
    for x in ents: open(tmp_path / x, 'wb').write(b'\0' * 100 + pickle.dumps('poison'))
    r2, _ = rvt_es.load(src); assert r2 == r1 and r2 != 'poison'
