"""c5x-rvtgap item 95: set_instance_type rewrote EVERY 8-byte match of the old symbol id in the header entry (accidental third match would be changed); real instances hold exactly 2 (60 of 60 Structural 2024). Now refused unless exactly 2. Synthetic, no sample needed."""
import os, sys, struct, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))


class _G:
    def __init__(self, hdr): self.hdr = hdr; self.replaced = None
    def template(self, tid): return {'rec': bytes(struct.pack('<Q', 111) + bytes(8)), 'log': [('FamilyInstance.m_masterSymbolId', 0, 8, None)], 'hdr': self.hdr}
    def replace_existing(self, tid, hdr, rec): self.replaced = (hdr, rec)


@pytest.mark.parametrize('copies,ok', [(0, False), (1, False), (2, True), (3, False)])
def test_header_must_hold_exactly_two_copies(monkeypatch, copies, ok):
    from savegate import rvt_writer_ops as WO
    monkeypatch.setattr(WO, '_family_of', lambda src, sym: ('FamilySymbol', 7))
    g = _G(b'\x01\x02' + b''.join(struct.pack('<Q', 111) + b'\xAA' for _ in range(copies)) + b'\x03')
    if ok:
        try: WO._set_instance_type(g, 'x', 5, 222)
        except ValueError as e: assert 'found' not in str(e)      # may fail later on Global/Latest access (no real file), never on the count
        except Exception: pass
    else:
        with pytest.raises(ValueError, match='expected exactly 2|not found'):
            WO._set_instance_type(g, 'x', 5, 222)
