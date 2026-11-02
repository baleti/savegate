"""Format adapters: sniff version, snapshot (key -> comparable) for the verify diff, structural validate.
A snapshot key present in the source and output must be equal unless the manifest lists it as modified."""
import hashlib, os, sys, re
from .errors import UnsupportedVersion, VerifyFailed

DWG_WRITABLE = ('AC1015', 'AC1018', 'AC1024', 'AC1027', 'AC1032')
RVT_WRITABLE = ('2024', '2026')      # write-lab verified years; extend only with oracle evidence


GZ_CAP = 1 << 30      # same bound as rvtw.GZ_CAP: largest plausible decompressed Revit stream


def _h(b): return hashlib.sha1(b).hexdigest()


def _page_problems(buf, info):
    """R2004-family data pages whose stored checksums do not match (header checksum = adler over the decoded 32-byte header seeded with the data checksum; data checksum = adler over
    the stored bytes). The reader inflates a damaged page silently, AutoCAD refuses it. [] when info is None (R2000). Same rule as dwg-viewer dwgfmt.r2004_page_problems."""
    import struct, zlib
    out = []
    if not info: return out
    for name, sec in info['sections'].items():
        for num, psz, start in sec['pages']:
            if num not in info['pages']: continue
            addr, _ = info['pages'][num]
            if addr < 0 or addr + 32 > len(buf): out.append('%s page %d: header beyond end of file' % (name, num)); continue
            mask = 0x4164536B ^ addr
            f = [x ^ mask for x in struct.unpack_from('<8I', buf, addr)]
            if f[0] != 0x4163043B: out.append('%s page %d: bad page type' % (name, num)); continue
            if addr + 32 + f[2] > len(buf): out.append('%s page %d: data beyond end of file' % (name, num)); continue
            hdr = list(f); hdr[6] = 0
            if zlib.adler32(struct.pack('<8I', *hdr), f[7]) & 0xffffffff != f[6]: out.append('%s page %d: header checksum' % (name, num))
            elif zlib.adler32(bytes(buf[addr + 32:addr + 32 + f[2]]), 0) & 0xffffffff != f[7]: out.append('%s page %d: data checksum' % (name, num))
    return out


def _dec_header(buf):
    seed = 1; h = bytearray(buf[0x80:0x80 + 0x6C])
    for i in range(len(h)):
        seed = (seed * 0x343FD + 0x269EC3) & 0xFFFFFFFF
        h[i] ^= (seed >> 16) & 0xFF
    return h


def _system_page_problems(buf, info):
    """R2004-family SYSTEM pages (page map at the header address, section map): header 0x41630E3B, checksum = adler32(compressed data, seed = adler32(20-byte header with the checksum field zeroed))
    (verified on a real file: stored 0xF06626E5). The reader ignores it (36/40 random flips inside the page map were accepted by the gate before)."""
    import struct, zlib
    if not info or bytes(buf[:6]) not in (b'AC1018', b'AC1024', b'AC1027', b'AC1032') or len(buf) < 0x80 + 0x6C: return []
    h = _dec_header(buf); out = []
    addrs = {'page map': struct.unpack_from('<q', h, 0x54)[0] + 0x100}
    sm = struct.unpack_from('<I', h, 0x5C)[0]
    if sm in info['pages']: addrs['section map'] = info['pages'][sm][0]
    for nm, a in addrs.items():
        if a < 0 or a + 20 > len(buf): out.append('%s: header beyond end of file' % nm); continue
        t, ds, cs, ct, ck = struct.unpack_from('<5I', buf, a)
        if t not in (0x41630E3B, 0x4163003B): out.append('%s: bad system page type' % nm); continue
        if a + 20 + cs > len(buf): out.append('%s: data beyond end of file' % nm); continue
        hz = bytearray(buf[a:a + 20]); hz[16:20] = bytes(4)
        if zlib.adler32(bytes(buf[a + 20:a + 20 + cs]), zlib.adler32(bytes(hz), 0) & 0xFFFFFFFF) & 0xFFFFFFFF != ck: out.append('%s: checksum' % nm)
    return out


_PREVIEW_SENTINEL = bytes.fromhex('1f256d07d43628289d57ca3f9d44102b')


def _preamble_snap(buf):
    """R2004+ files: bytes 0x00..0x7F of the file (version, maintenance, preview/summary/VBA seekers, codepage, security flags) have NO checksum and the reader ignores them,
    but the writer copies them verbatim (measured: no-edit rewrite of a real AC1032 keeps all 128 bytes). A save that alters them is a writer bug (c4x-dwgreadfuzz item 75b)."""
    if bytes(buf[:6]) in (b'AC1018', b'AC1024', b'AC1027', b'AC1032'):
        # bytes 0x0D..0x10 = file address of the preview image: it moves with the file (measured on 2 real AC1032 no-edit rewrites: the writer repoints it and the new address holds
        # the preview sentinel). Compare the pointer by what it points at, not by its value.
        b = bytearray(buf[:0x80]); a = int.from_bytes(b[0x0D:0x11], 'little'); b[0x0D:0x11] = bytes(4)
        ok = a == 0 or bytes(buf[a:a + 16]) == _PREVIEW_SENTINEL
        return _h(bytes(b)) + (':preview-ok' if ok else ':preview-broken')
    return None


def _header_problems(buf):
    """R2004/R2010/R2013/R2018 (AC1018, AC1024, AC1027, AC1032) file header: the encrypted 0x6C-byte block at 0x80 carries the magic 'AcFssFcAJMB' and a CRC32 (plain zlib crc32 over the
    decrypted block with the CRC field zeroed). The reader ignores both, AutoCAD does not (c4x-dwgreadfuzz item 75: 24/25 single-bit header flips were accepted before this check)."""
    import struct, zlib
    if bytes(buf[:6]) not in (b'AC1018', b'AC1024', b'AC1027', b'AC1032'): return []
    if len(buf) < 0x80 + 0x6C: return ['file header: truncated']
    out0 = []
    if bytes(buf[6:0x0B]) != bytes(5): out0.append('file header: bytes 6..10 not zero')       # 400/400 local R2004+ files have these invariants
    if bytes(buf[0x28:0x2C]) != b'\x80\0\0\0': out0.append('file header: constant at 0x28')
    h = _dec_header(buf)
    out = out0
    if bytes(h[:11]) != b'AcFssFcAJMB': out.append('file header: magic')
    crc = struct.unpack_from('<I', h, 0x68)[0]; h[0x68:0x6C] = b'\0\0\0\0'
    if zlib.crc32(bytes(h)) & 0xFFFFFFFF != crc: out.append('file header: CRC32')
    return out


class RawAdapter:
    """no format knowledge: the whole file is one object (tests, unknown formats are refused by pick_adapter)"""
    name = 'raw'
    def sniff(self, buf): return 'raw'
    def snapshot(self, buf): return {'file': _h(buf)}
    def validate(self, buf):
        if not buf: raise VerifyFailed('empty output')
        return 'ok'


def _plain(v):
    """repr with the model's duplicate-name suffix '~<handle>' removed (two anonymous '*D' blocks are told apart by the model only while both exist)."""
    return re.sub(r"(\*[A-Za-z]+)~[0-9a-f]+", r"\1", repr(v) if not isinstance(v, str) else v)


_DWG_NAMES = {'AC1006': 'R10', 'AC1009': 'R11/R12', 'AC1012': 'R13', 'AC1014': 'R14', 'AC1015': '2000', 'AC1018': '2004', 'AC1021': '2007', 'AC1024': '2010', 'AC1027': '2013', 'AC1032': '2018+'}
_SUBENT = {2, 6, 10, 11, 12, 13, 14, 15}   # ATTRIB, SEQEND, VERTEX kinds


class _SkipRule(Exception): pass


class DwgAdapter:
    name = 'dwg'
    def __init__(self, lib=None):
        lib = lib or os.environ.get('SAVEGATE_DWG_LIB') or os.path.expanduser('~/dwg-write')
        self.owners = {}; self.bheaders = {}; self.dimobjs = {}; self.blockhs = set()
        if lib not in sys.path: sys.path.insert(0, lib)

    def sniff(self, buf):
        v = buf[:6].decode('ascii', 'replace')
        if not re.fullmatch(r'AC10\d\d', v): return None
        if v not in DWG_WRITABLE:
            raise UnsupportedVersion('DWG %s (%s) cannot be saved: writable versions are %s. The file was not touched; export a copy as DXF or '
                                     'Save As one of the writable versions instead.' % (v, _DWG_NAMES.get(v, 'unknown'), ', '.join('%s (%s)' % (w, _DWG_NAMES[w]) for w in DWG_WRITABLE)))
        return v

    def _snap(self, m, same):
        out = {}
        ent_handles = set()
        for blk, e in m.entities():
            out['ent:%x' % e['handle']] = hashlib.blake2b((repr(sorted((k, _plain(v)) for k, v in e.items())) + '|' + _plain(blk)).encode(), digest_size=12).digest()
            ent_handles.add(e['handle']); self.owners[e['handle']] = e.get('owner')
            if str(e.get('kind', '')).startswith(('INSERT', 'MINSERT')) and isinstance(e.get('block_handle'), int): self.bheaders[e['handle']] = e['block_handle']
        self.blockhs |= set(getattr(m, 'blocks', {}))   # block records own entities but are not entities: declaring one must not excuse all its entities
        dimblk = {e['block_ref']: e['handle'] for blk, e in m.entities() if e.get('block_ref', '').startswith('*D')} if hasattr(m, 'entities') else {}
        self.dims = getattr(self, 'dims', set()) | set(dimblk.values())
        bhmap = {e['handle']: e.get('block_handle') for blk, e in m.entities() if e.get('block_ref', '').startswith('*D')} if dimblk else {}
        for bn, dh in dimblk.items():   # the anonymous block's own objects: BLOCK_HEADER, BLOCK, ENDBLK (adjacent handles)
            bh = bhmap.get(dh)
            if isinstance(bh, int):
                self.dimobjs[dh] = {'obj:%x' % x for x in range(bh, bh + 4) if x in m.objs and (x == bh or m.objs[x].type in (4, 5))}
        if dimblk:   # geometry of a dimension's anonymous block belongs to the dimension
            for blk, e in m.entities():
                if blk in dimblk and e['handle'] != dimblk[blk]: self.owners[e['handle']] = dimblk[blk]
        for h, o in m.objs.items():
            if h not in ent_handles:
                out['obj:%x' % h] = _h(o.raw)
                if o.type in _SUBENT and h not in self.owners:   # vertex / SEQEND / ATTRIB not emitted as entities (fast path skips): still owned by their parent
                    try:
                        par = [v for c, v in __import__('dwgmodel').owner_and_layer(o) if c == 4]
                        if par: self.owners[h] = par[0]
                    except Exception: pass
        for k, v in m.header().items():
            out['hdr:%s' % k] = repr(v)
        out['meta:version'] = m.version
        return out

    def snapshot_pair(self, src, out):
        """Fast path for verify: objects whose raw bytes are identical in source and output cannot differ when decoded
        (any cross-object change shows in the raw bytes of the object that changed), so only the others are decoded."""
        import dwgmodel as M
        ms, mo = M.Model(src), M.Model(out); self._pair = (ms, mo)
        same = {h for h, o in ms.objs.items() if h in mo.objs and mo.objs[h].raw == o.raw and mo.objs[h].type == o.type}
        saved = (dict(M.ENT_DECODERS), dict(M.CLASS_DECODERS), M._proxy_entity)
        def guard(f):
            def g(o, *a, **k):
                if o.handle in same: raise _Skip()
                return f(o, *a, **k)
            return g
        class _Skip(Exception): pass
        try:
            for d in (M.ENT_DECODERS, M.CLASS_DECODERS):
                for k in list(d): d[k] = guard(d[k])
            M._proxy_entity = guard(saved[2])
            snaps = [self._snap(m, same) for m in (ms, mo)]
            for sn, bb in zip(snaps, (src, out)):
                pa = _preamble_snap(bb)
                if pa is not None: sn['file_preamble'] = pa
        finally:
            M.ENT_DECODERS.clear(); M.ENT_DECODERS.update(saved[0]); M.CLASS_DECODERS.clear(); M.CLASS_DECODERS.update(saved[1]); M._proxy_entity = saved[2]
        return snaps

    def snapshot(self, buf):
        import dwgmodel
        return self._snap(dwgmodel.Model(buf), set())

    def expand(self, manifest):
        """handles (ints) in the manifest mean entity + object keys; structural side effects of add/delete
        (header HANDSEED, owner block table/object lists) are tolerated: the entity keys remain strict."""
        mod = set(); 
        for k in manifest.get('modified', ()):
            mod |= {k} if isinstance(k, str) else {'ent:%x' % k, 'obj:%x' % k}
        add = set(); dele = set()
        for k in manifest.get('added', ()):
            add |= {k} if isinstance(k, str) else {'ent:%x' % k, 'obj:%x' % k}
        for k in manifest.get('deleted', ()):
            dele |= {k} if isinstance(k, str) else {'ent:%x' % k, 'obj:%x' % k}
        return mod, add, dele


    @staticmethod
    def _crc_damage(m):
        """Objects of model m whose per-object CRC16 is wrong (bytes damaged although the container parsed)."""
        try:
            import dwgfmt as _F
        except ImportError:
            return []
        return ['obj:%x: object CRC mismatch' % h for h, o in m.objs.items()
                if len(o.raw) < 4 or _F.crc16(o.raw[:-2], 0xC0C1) != (o.raw[-2] | (o.raw[-1] << 8))]

    @staticmethod
    def _handle_damage_one(h, o):
        """True if the object's own embedded handle is unreadable or differs from h (see _handle_damage)."""
        try:
            import dwgbits as _B
            r = _B.Bits(o.raw, o.data_bit); _code, v = r.H()
            return v != h or _code != 0
        except ImportError:
            return False
        except Exception:
            return True

    @staticmethod
    def _handle_damage(m):
        """Objects whose OWN handle (first field of the object data, read by every decoder and thrown away) differs from the handle the object map gives them. The reader never looks at it,
        the object CRC is easy to recompute: c4x-dwgreadfuzz item 84, 151/151 CRC-fixed flips in that field were accepted by the gate and 108/151 were invisible to the snapshot diff."""
        try:
            import dwgbits as _B
        except ImportError:
            return []
        out = []
        for h, o in m.objs.items():
            try:
                r = _B.Bits(o.raw, o.data_bit); _code, v = r.H()
                if v != h or _code != 0: out.append('obj:%x: embedded handle %x differs from the object map' % (h, v))
            except Exception:
                out.append('obj:%x: embedded handle unreadable' % h)
        return out

    def source_damage(self, buf):
        """c4x-dwgreadfuzz: damage in the SOURCE that the writer would carry over byte for byte (overwrite is refused; SAVE AS stays possible)."""
        try:
            import dwgmodel
            m = dwgmodel.Model(buf)
            return (['object map: CRC mismatch'] if getattr(m, 'omap_ok', None) is False else []) + _header_problems(buf) + _system_page_problems(buf, getattr(m, '_info', None)) + _page_problems(buf, getattr(m, '_info', None))[:50] + self._crc_damage(m)[:200] + self._handle_damage(m)[:200]
        except Exception as e:
            return ['source not readable: %s' % str(e)[:100]]

    def extra_checks(self, manifest):
        """Structural objects tolerated as side effects (block records, BLOCK/ENDBLK, tables) must keep their identity: a changed
        BLOCK/ENDBLK object is never a legitimate side effect (they are only added/removed with a dimension), and a changed BLOCK_HEADER
        must keep its decoded name (bit flip in a block name renames the block under its INSERTs; found by c8-perf gatepower 2026-10-30)."""
        pair = getattr(self, '_pair', None)
        if not pair: return
        ms, mo = pair; bad = []
        for h, o in ms.objs.items():
            p = mo.objs.get(h)
            if p is None or p.raw == o.raw: continue
            if o.type in (4, 5): bad.append(('struct_changed', 'obj:%x' % h))
            elif o.type == 49 and _plain(ms.blocks.get(h)) != _plain(mo.blocks.get(h)): bad.append(('block_renamed', 'obj:%x' % h))
        for h, n in ms.blocks.items():
            if h in mo.blocks and _plain(mo.blocks[h]) != _plain(n) and ('block_renamed', 'obj:%x' % h) not in bad: bad.append(('block_renamed', 'obj:%x' % h))
        # c4x-dwgreadfuzz: every object whose bytes differ from the source must carry a valid per-object CRC16 (a writer bug or a flipped byte in a declared
        # object was not seen by the element diff). Objects byte-identical to the source are exempt, so pre-existing damage never blocks a save.
        try:
            import dwgfmt as _F
            for h, o in mo.objs.items():
                r = o.raw; s0 = ms.objs.get(h)
                if s0 is not None and s0.raw == r: continue
                if len(r) < 4 or _F.crc16(r[:-2], 0xC0C1) != (r[-2] | (r[-1] << 8)): bad.append(('object_crc', 'obj:%x' % h))
                if self._handle_damage_one(h, o): bad.append(('embedded_handle', 'obj:%x' % h))
        except ImportError:
            pass
        # c4x-dwgreadfuzz item 87: the element view compares ENTITIES by decoded fields only, so a CRC-consistent bit flip in a bit the decoder discards (e.g. the
        # three visual-style flag bits of common_entity) is invisible to it (5/295 CRC-fixed LINE flips accepted by every check). An object that is not declared
        # (modified/added/side effect) must therefore be byte-identical to the source.
        try:
            if getattr(mo, 'version', 'AC1018') <= 'AC1015': raise _SkipRule()   # R2000 links entities in a chain: adding one rewrites its neighbours' bytes (2/5 AC1015 add-line saves refused in the false-positive sweep)
            mod_, add_, dele_ = self.expand(manifest); decl_ = mod_ | add_ | dele_ | self.side_effects(manifest)
            for h, o in ms.objs.items():
                p = mo.objs.get(h)
                if p is None or p.raw == o.raw: continue
                if 'obj:%x' % h in decl_ or 'ent:%x' % h in decl_: continue
                bad.append(('undeclared_object_bytes', 'obj:%x' % h))
        except _SkipRule:
            pass
        except Exception as e:
            bad.append(('undeclared_check_failed', str(e)[:60]))
        # a block record that stops being listed turns every entity it owns into an orphan that no reader walks (entities silently vanish; c8-perf 2026-10-30):
        # allowed only for a declared deletion (a dimension's anonymous block) or when it was never a block of the source
        mod, add, dele = self.expand(manifest); ok = dele | self.side_effects(manifest)
        for h in ms.blocks:
            if h not in mo.blocks and 'obj:%x' % h not in ok: bad.append(('block_unlisted', 'obj:%x' % h))
        return bad

    # structural objects/header vars that legitimately change with add/delete/edit
    def side_effects(self, manifest):
        se = set()
        # owned sub-entities (POLYLINE vertices, SEQEND, INSERT attributes) belong to the declared entity
        decl = {k for kind in ('modified', 'added', 'deleted') for k in manifest.get(kind, ()) if isinstance(k, int)}
        for h, o in self.owners.items():
            if o in decl and o not in self.blockhs: se |= {'ent:%x' % h, 'obj:%x' % h}
        for k in list(manifest.get('added', ())) + list(manifest.get('deleted', ())):
            if isinstance(k, int):
                se.add('hdr:HANDSEED')
                if k in self.bheaders: se.add('obj:%x' % self.bheaders[k])   # INSERT: the block record keeps the list of its inserts
                if k in getattr(self, 'dims', ()): se |= {'obj:1'} | self.dimobjs.get(k, set())   # adding/removing a dimension adds/removes its anonymous block: BLOCK_CONTROL object list
                if self.owners.get(k) is not None: se.add('obj:%x' % self.owners[k])
        return se

    def validate(self, buf):
        import dwgmodel
        m = dwgmodel.Model(buf)
        if m.version not in DWG_WRITABLE: raise VerifyFailed('output version %s' % m.version)
        if getattr(m, 'omap_ok', None) is False:      # c4x-dwgreadfuzz: the writer rebuilds the object map, so a wrong map CRC in the OUTPUT is a writer bug (AutoCAD would call it a corrupt file)
            raise VerifyFailed('object map CRC mismatch in the output')
        hp = _header_problems(buf) + _system_page_problems(buf, getattr(m, '_info', None))
        if hp: raise VerifyFailed('file header damaged in the output (%s)' % hp[0])
        pp = _page_problems(buf, getattr(m, '_info', None))
        if pp: raise VerifyFailed('page checksum mismatch in the output (%d, first: %s)' % (len(pp), pp[0]))
        hs = m.header().get('HANDSEED')
        if isinstance(hs, int) and m.objs and hs <= max(m.objs):
            raise VerifyFailed('HANDSEED %x not above the highest handle %x' % (hs, max(m.objs)))
        # rule learned from the AutoCAD oracle (AUDIT 'color != owner's'): polyline vertices carry the owner's colour
        ents = {e['handle']: e for _, e in m.entities()}
        for h, e in ents.items():
            if str(e.get('kind', '')).startswith('VERTEX'):
                o = ents.get(e.get('owner'))
                if o is not None and o.get('color') != e.get('color'):
                    raise VerifyFailed('vertex %x colour %r differs from its polyline %x colour %r (AutoCAD AUDIT would repair)' % (h, e.get('color'), e['owner'], o.get('color')))
        return 'ok %s %d objects' % (m.version, len(m.objs))


rvtw_META = {'Formats/Latest', 'BasicFileInfo', 'RevitPreview4.0', 'Contents', 'TransmissionData', 'ProjectInformation', 'PartAtom'}


class RvtAdapter:
    name = 'rvt'
    def __init__(self, lib=None, elements_fn=None):
        lib = lib or os.environ.get('SAVEGATE_RVT_LIB') or os.path.expanduser('~/rvt-research/write-lab')
        if lib not in sys.path: sys.path.insert(0, lib)
        self.elements_fn = elements_fn      # optional: buf -> {key: comparable} (reader element/parameter dump)

    def sniff(self, buf):
        if buf[:8] != bytes.fromhex('d0cf11e0a1b11ae1'): return None
        import cfb
        try: c = cfb.CFB(buf); s = c.streams()
        except Exception: return None
        if 'BasicFileInfo' not in s or 'Global/ElemTable' not in s and 'Global/Latest' not in s: return None
        t = s['BasicFileInfo'].data.decode('utf-16le', 'ignore')
        m = re.search(r'(20[12]\d)', t)
        v = m.group(1) if m else '?'
        if v not in RVT_WRITABLE:
            raise UnsupportedVersion('Revit %s file cannot be saved: writable years are %s. The file was not touched; open it in Revit and Save As a '
                                     'writable year, or save the edit as a new file with the writer.' % (v, ', '.join(RVT_WRITABLE)))
        return v

    def source_damage(self, buf):
        d = self._damage(buf); self._src_dmg = set(d); self._src_gtails = self._global_tails(buf); return d

    @staticmethod
    def _global_tails(buf):
        """c4x-rvtgap: {Global/<stream>: bytes after the first gzip member}; nobody decodes them, so junk there is invisible to every other check"""
        out = {}
        try:
            import cfb, rvtw
            for n, e in cfb.CFB(bytes(buf)).streams().items():
                if not n.startswith('Global/') or e.data[:5] == b'<?xml': continue
                P = rvtw.Stream(e.data).payload; i = P.find(rvtw.GZ)
                if i < 0: continue
                out[n] = bytes(P[rvtw.read_member(P, i)[1]:])
        except Exception: return {}
        return out

    def overwrite_risks(self, buf):
        """c5x-rvtgap: reasons NOT to replace this file in place although the bytes are fine. A workshared model (Worksharing: Central/Local in BasicFileInfo) is tied to its
        central/local pair, workset ownership and sync history that live outside this file; rewriting it behind Revit's back can break the sync. SAVE AS stays allowed."""
        import cfb
        try: d = cfb.CFB(bytes(buf)).streams()['BasicFileInfo'].data
        except Exception: return []
        k = d.find('Worksharing:'.encode('utf-16le'))
        if k < 0: return []
        m = d[k + 24:k + 80].decode('utf-16le', 'ignore').strip().split('\r')[0].split('\n')[0].strip()
        if m and not m.lower().startswith('not enabled'): return ['workshared model (Worksharing: %s): in-place overwrite refused, use SAVE AS or save from Revit' % m]
        return []

    def _damage(self, buf):
        """problems in the SOURCE bytes the reader tolerates but the writer would carry over unchanged: bad page ECC, gzip CRC/size mismatch, bad inflate, unreadable container.
        Plain XML / raw gzip streams carry no page ECC. [] = nothing found. (c3x-rvtgap: a zeroed 64-byte run used to be saved back without any warning.)"""
        import struct, zlib, cfb, rvtw, ecc, wlpart
        errs = []
        try: S = cfb.CFB(bytes(buf)).streams()
        except Exception as ex: return ['container unreadable: %s' % ex]
        for n, e in S.items():
            if len(e.data) != e.size: errs.append('%s: %d bytes readable of %d declared (FAT chain damaged/truncated)' % (n, len(e.data), e.size)); continue   # c4x-rvtgap
            if n in rvtw.PLAIN or n.startswith('\x05'): continue      # OLE property-set streams are plain
            d = e.data
            if d[:5] == b'<?xml' or d[:2] == b'\x1f\x8b': continue
            full = len(d) // rvtw.PAGE_STORED
            bad = [i for i in range(full) if not ecc.check(d[i * rvtw.PAGE_STORED:(i + 1) * rvtw.PAGE_STORED])]
            last = d[full * rvtw.PAGE_STORED:]
            if last and (ecc.params(len(last)) is None or not ecc.check(last)): bad.append(full)
            if bad: errs.append('%s: ECC bad on %d page(s), first %d' % (n, len(bad), bad[0]))
            try:
                P = rvtw.Stream(d).payload
                if n.startswith('Partitions/'):
                    if len(P) < 40: continue        # tiny partition: the parser needs a 36-byte frame
                    for k, m in enumerate(wlpart.Partition(rvtw.Stream(d)).mem):
                        raw = bytes(m['raw']); crc, isz = struct.unpack('<II', P[m['pos']:m['end']][-8:])
                        if crc != zlib.crc32(raw) & 0xffffffff or isz != len(raw): errs.append('%s member %d: crc/size mismatch' % (n, k))
                else:
                    i = P.find(rvtw.GZ)
                    if i < 0: continue
                    do = zlib.decompressobj(-15); raw = do.decompress(P[i + 10:], GZ_CAP + 1)     # c4x-dwgreadfuzz: bounded (a gzip bomb must not exhaust the gate's memory)
                    if len(raw) > GZ_CAP: errs.append('%s: inflates to more than %d bytes (gzip bomb or damage)' % (n, GZ_CAP)); continue
                    crc, isz = struct.unpack('<II', do.unused_data[:8])
                    if crc != zlib.crc32(raw) & 0xffffffff or isz != len(raw) & 0xffffffff: errs.append('%s: crc/size mismatch' % n)
            except Exception as ex: errs.append('%s: %s %s' % (n, type(ex).__name__, ex))
        return errs

    def snapshot(self, buf):
        import cfb
        c = cfb.CFB(buf)
        out = {'stream:' + k: _h(e.data) for k, e in c.streams().items()}
        out['meta:streams'] = repr(sorted(c.streams()))
        out['meta:sector'] = '%d' % c.major
        if self.elements_fn:
            try: els = self.elements_fn(buf)
            except Exception as ex: raise VerifyFailed('element view of the file could not be built (%s: %s)' % (type(ex).__name__, str(ex)[:120]))      # c4x-rvtgap: a file the reader cannot decode is not verifiable: refuse as VerifyFailed (not a DiskError)
            out.update({'el:' + str(k): v for k, v in els.items()})
        if os.environ.get('SAVEGATE_RVT_IDCHECK', '1') != '0':
            try:
                from . import rvt_elements
                ids, ur = rvt_elements.id_state(buf); out['meta:unresolved_ids'] = repr(ur); out['meta:n_ids'] = str(len(ids))
                self._ctr_hist = (getattr(self, '_ctr_hist', [])[-1:]) + [rvt_elements.counter_state(buf)]
                self._unres_hist = (getattr(self, '_unres_hist', [])[-1:]) + [ur]; self._ids_hist = (getattr(self, '_ids_hist', [])[-1:]) + [set(ids)]      # c4x-rvtgap: an ElemTable id without a framed record (neighbour eaten by a bad edit) changes this key -> refused unless declared
            except ImportError: pass
            except Exception as ex: raise VerifyFailed('id-resolution check failed (%s: %s)' % (type(ex).__name__, str(ex)[:120]))
        self._buf_hist = (getattr(self, '_buf_hist', [])[-1:]) + [buf]      # c4x-rvtgap: source+output bytes for manifest['expect'] (verify_declared)
        self._keys = set(out)
        self._mem_hist = (getattr(self, '_mem_hist', [])[-1:]) + [self._member_hashes(c)]     # [source, output] of the current verify
        self._blk_hist = (getattr(self, '_blk_hist', [])[-1:]) + [self._block_hashes(c)]
        return out

    @staticmethod
    def _member_hashes(c):
        """{partition stream: [sha1 of each inflated gzip member]} or {} when the stream does not parse"""
        try:
            import rvtw, wlpart
            r = {}
            for n, e in c.streams().items():
                if not n.startswith('Partitions/'): continue
                st = rvtw.Stream(e.data)
                if len(st.payload) < 40: continue
                r[n] = [hashlib.sha1(bytes(m['raw'])).hexdigest() for m in wlpart.Partition(st).mem]
            return r
        except Exception: return {}

    BLK = 1024

    @classmethod
    def _block_hashes(cls, c):
        """{partition stream: (hashes of 1 KB blocks of the inflated members from the start, same from the end, total length)}"""
        try:
            import rvtw, wlpart
            r = {}
            for n, e in c.streams().items():
                if not n.startswith('Partitions/'): continue
                st = rvtw.Stream(e.data)
                if len(st.payload) < 40: continue
                b = b''.join(bytes(m['raw']) for m in wlpart.Partition(st).mem); B = cls.BLK
                r[n] = ([hash(b[i:i + B]) for i in range(0, len(b), B)], [hash(b[max(0, i - B):i]) for i in range(len(b), 0, -B)], len(b))
            return r
        except Exception: return {}

    SPAN_MAX = 8192        # per declared element (<= 8): the changed window of a partition (prefix/suffix diff) was <= 1066 bytes on 60 real scenes

    def span_checks(self, manifest):
        h = getattr(self, '_blk_hist', [])
        nd = sum(len(manifest.get(k, ())) for k in ('modified', 'added', 'deleted'))
        if not 1 <= nd <= 8 or len(h) < 2 or not h[0] or not h[1]: return []
        bad = []
        for n, (fa, ba, la) in h[0].items():
            if n not in h[1]: continue
            fb, bb, lb = h[1][n]
            if (fa, la) == (fb, lb): continue
            p = 0
            while p < min(len(fa), len(fb)) and fa[p] == fb[p]: p += 1
            q = 0
            while q < min(len(ba), len(bb)) and ba[q] == bb[q]: q += 1
            span = max(la, lb) - (p + q) * self.BLK
            if span > self.SPAN_MAX * nd: bad.append(('span_changed', '%s: changed window ~%d bytes for %d declared elements' % (n, span, nd)))
        return bad

    def _expect_checks(self, manifest):
        """c4x-rvtgap: manifest['expect'] = {element id: {field name: new value}}: the declared element must differ from the source in exactly these fields (a flip inside the declared record is invisible to every other rule)"""
        ex = manifest.get('expect'); bh = getattr(self, '_buf_hist', [])
        if not ex: return []
        if len(bh) < 2: return [('expect_unverifiable', 'expected field values were given but source and output bytes are not both available')]
        import tempfile
        from . import rvt_verify
        bad = []
        with tempfile.TemporaryDirectory() as d:
            a = os.path.join(d, 'a.rvt'); b = os.path.join(d, 'b.rvt')
            open(a, 'wb').write(bh[0]); open(b, 'wb').write(bh[1])
            added = {str(x).split(':')[-1] for x in manifest.get('added', ())}
            only = {str(k)[7:] for k in manifest.get('modified', ()) if str(k).startswith('stream:Partitions/')} or None      # c4x-rvtgap: inflate only the declared partitions
            for eid, fields in ex.items():
                try:
                    i = int(str(eid).split(':')[-1])
                    if str(i) in added:      # fields may carry {'__clone_of__': <id>}
                        f = dict(fields); co = f.pop('__clone_of__', None); rvt_verify.verify_new(a, b, i, co, f)
                    else: rvt_verify.verify_declared(a, b, i, fields, only=only)
                except Exception as e: bad.append(('declared_element_mismatch', '%s: %s' % (type(e).__name__, str(e)[:200])))
        return bad

    def extra_checks(self, manifest):
        """c5x-rvtgap: the element view and the record checks do not see a bit flip in a record region they do not decode (23 of 25 random single-bit flips with valid ECC/CRC
        went unnoticed), so a declared edit may change only a few neighbouring gzip members of a partition (real edits: 1-3 adjacent members); anything wider is refused"""
        meta = [k for k in manifest.get('modified', ()) if str(k).split(':', 1)[-1] in rvtw_META and not os.environ.get('SAVEGATE_RVT_ALLOW_META')]
        if meta: return [('metadata_stream_declared', '%s: file metadata streams (version/build/worksharing, thumbnail, transmission data) carry no integrity data and no edit needs them; a flip there passed the gate when declared' % ', '.join(map(str, meta)))]
        exp = self._expect_checks(manifest)
        if exp: return exp
        h = getattr(self, '_mem_hist', [])
        if len(h) < 2 or not h[0]: return []      # c4x-rvtgap: an EMPTY output map is no reason to skip (all partitions vanished)
        bad = self.span_checks(manifest)
        uh = getattr(self, '_unres_hist', [])
        if len(uh) >= 2:
            decl = set()
            for k in manifest.get('deleted', ()):
                try: decl.add(int(str(k).split(':')[-1]))
                except ValueError: pass
            new = set(uh[1]) - set(uh[0]) - decl
            ch = getattr(self, '_ctr_hist', [])
            if len(ch) >= 2 and ch[0] and ch[1] and ch[0][0] >= ch[0][1] and ch[1][0] < ch[1][1]:
                bad.append(('id_counter', 'ElemTable id counter %d is below the highest element id %d in the output (source: %d >= %d): Revit would hand out an id that already exists' % (ch[1][0], ch[1][1], ch[0][0], ch[0][1])))
            ih = getattr(self, '_ids_hist', [])
            if len(ih) >= 2:      # added elements: each declared el:<id> must be in the output ElemTable and resolve; no other id may appear or vanish
                add = set()
                for k in manifest.get('added', ()):
                    try: add.add(int(str(k).split(':')[-1]))
                    except ValueError: pass
                gone = ih[0] - ih[1] - decl; extra = ih[1] - ih[0] - add; missing = add - ih[1]; dang = add & set(uh[1])
                if gone or extra or missing or dang: bad.append(('id_set', 'ElemTable id set vs declaration: vanished %s, undeclared new %s, declared added but absent %s, added without record %s' % (sorted(gone)[:5], sorted(extra)[:5], sorted(missing)[:5], sorted(dang)[:5])))
            if new: bad.append(('unresolved_ids', 'ElemTable ids without a framed record in the output that were not declared deleted: %s' % sorted(new)[:8]))
        nd = sum(len(manifest.get(k, ())) for k in ('modified', 'added', 'deleted')); budget = 4 * max(1, nd)
        for n, a in h[0].items():
            b = h[1].get(n)
            if b is None or abs(len(a) - len(b)) > budget:      # c4x-rvtgap ESCAPE: a declared Partitions stream emptied (valid container, nothing to check) was accepted; a partition that vanishes or whose member count changes wildly is refused
                bad.append(('members_changed', '%s: %d members in the source, %s in the output' % (n, len(a), 'none (stream empty or unparsable)' if b is None else len(b)))); continue
            if len(a) != len(b): continue
            ch = [k for k in range(len(a)) if a[k] != b[k]]
            if len(ch) > budget or (ch and ch[-1] - ch[0] + 1 > budget + 2): bad.append(('members_changed', '%s: %d members changed (%d..%d), declared %d' % (n, len(ch), ch[0], ch[-1], nd)))
        return bad

    def expand(self, manifest):
        mod = set(manifest.get('modified', ()))
        if manifest.get('added'): mod.add('meta:n_ids')
        if manifest.get('deleted'): mod.add('meta:unresolved_ids')      # c4x-rvtgap: a deleted record leaves its ElemTable id unresolved; extra_checks demands that exactly the declared ids did
        return mod, set(manifest.get('added', ())), set(manifest.get('deleted', ()))

    def side_effects(self, manifest):
        """With an element-level view, an element edit rewrites the partition / global streams that hold it; those stream keys
        are tolerated only when something is declared and the element keys (strict) cover the content. Identity stays byte-strict."""
        if not self.elements_fn or not any(manifest.get(k) for k in ('modified', 'added', 'deleted')): return set()
        return {k for k in getattr(self, '_keys', ()) if k.startswith('stream:Partitions/')}      # c5x-rvtgap: Global/* is NOT excused (the writer leaves every Global stream byte-identical on an element edit; a tampered one with valid ECC/CRC was accepted)

    @staticmethod
    def _container_slack(buf, c):
        import struct
        errs = []; ss = c.ss
        if any(buf[34:40]): errs.append('header reserved bytes are not zero')
        if struct.unpack_from('<I', buf, 52)[0]: errs.append('header transaction signature is not zero')
        d = c._chain(struct.unpack_from('<I', buf, 48)[0])
        for i in range(len(d) // 128):
            e = d[i * 128:(i + 1) * 128]
            if e[66] == 0 and any(e[:64]): errs.append('free directory entry %d carries a name' % i); break
        nfat = struct.unpack_from('<I', buf, 44)[0]; fat = []
        for x in [x for x in struct.unpack_from('<109I', buf, 76) if x < 0xFFFFFFFA][:nfat]:
            fat += struct.unpack_from('<%dI' % (ss // 4), buf, (x + 1) * ss)
        ns = len(buf) // ss - 1
        if any(x != 0xFFFFFFFF for x in fat[ns:]): errs.append('FAT entries beyond the end of the file are not free')
        return errs

    def validate(self, buf):
        import cfb
        c = cfb.CFB(buf)
        s = c.streams()
        for need in ('BasicFileInfo',):
            if need not in s: raise VerifyFailed('stream %s missing in output' % need)
        if len(buf) != (c.nsectors + 1) * c.ss + (512 - c.ss if c.major == 3 else 0) and len(buf) % c.ss:
            raise VerifyFailed('container length is not sector aligned')
        sl = self._container_slack(buf, c)      # c4x-rvtgap: bytes the container format reserves as zero/free must stay so (0 violations in 277 real files)
        if sl: raise VerifyFailed('container reserved/free area is not clean: %s' % '; '.join(sl[:3]))
        sg_ = getattr(self, '_src_gtails', None)
        if sg_:       # the tail after a Global stream's gzip member must be the source's own or pure zero padding (a rewrite that drops it is fine)
            for n, t in self._global_tails(buf).items():
                if n in sg_ and t != sg_[n] and t.rstrip(b'\0'): raise VerifyFailed('%s: bytes after the gzip member differ from the source and are not zero padding' % n)
        dmg = [d for d in self._damage(buf) if d not in getattr(self, '_src_dmg', ())]       # c5x-rvtgap: the written bytes get the same page ECC / gzip CRC+size check as the source (a modified stream is exempt from the hash diff); damage already present in the source (SAVE AS rescue copy) is not new
        if dmg: raise VerifyFailed('output fails the integrity check: %s' % '; '.join(dmg[:3]))
        try:
            import rvtw, wlpart
            for n, e in s.items():
                if not n.startswith('Partitions/'): continue
                st = rvtw.Stream(e.data)
                if len(st.payload) < 40: continue
                pt = wlpart.Partition(st)
                import struct
                for k, m in enumerate(pt.mem):
                    L = m['end'] - m['pos']
                    if k < len(pt.gaps) and len(pt.gaps[k]) >= 32:       # c5x-rvtgap: frame after member k holds its own stored size + 8 and the next member's (0 across a section boundary); 0 violations in 35873 frames of 91 real partitions
                        own = struct.unpack_from('<I', pt.gaps[k], 2)[0]; nxt = struct.unpack_from('<I', pt.gaps[k], 16)[0]
                        Ln = pt.mem[k + 1]['end'] - pt.mem[k + 1]['pos'] if k + 1 < len(pt.mem) else None
                        if own != L + 8 or (Ln is not None and nxt not in (0, Ln + 8)): raise VerifyFailed('%s member %d: frame size fields do not match the stored member length' % (n, k))
                if len(bytes(pt.tail).rstrip(b'\0')) > 2048:       # c4x-rvtgap: after the footer (nonzero span 176-685 B in 277 real partitions) only zero padding may follow (the writer pads to a full ECC page)
                    raise VerifyFailed('%s: non-zero bytes %d bytes into the partition tail (only zero padding may follow the footer)' % (n, len(bytes(pt.tail).rstrip(b'\0'))))
                for k, m in enumerate(pt.mem):
                    if len(m['raw']) > 131088:       # every real 2024/2026 file tops out at exactly 131088 (12 files); Revit rejects larger members (vcheck rule)
                        raise VerifyFailed('%s member %d holds %d bytes, above the 131088 Revit limit' % (n, k, len(m['raw'])))
        except VerifyFailed: raise
        except Exception as ex: raise VerifyFailed('partition framing of the output could not be checked: %s %s' % (type(ex).__name__, ex))
        return 'ok %d streams' % len(s)


def _default_rvt_elements():
    rd = os.environ.get('SAVEGATE_RVT_READER') or os.path.expanduser('~/rvt-research')
    if not os.path.isdir(rd): return None
    def fn(buf):
        from . import rvt_elements
        return rvt_elements.elements(buf, with_geometry=False)
    return fn


def pick_adapter(buf, adapter=None):
    if adapter is not None:
        return adapter, adapter.sniff(buf) or '?'
    for cls in (DwgAdapter, RvtAdapter):
        a = cls(); v = a.sniff(buf)
        if v:
            if cls is RvtAdapter and a.elements_fn is None and os.environ.get('SAVEGATE_RVT_ELEMENTS', '1') != '0':
                a.elements_fn = _default_rvt_elements()      # c4x-rvtgap: without an element view a corrupted neighbour record (valid ECC/CRC) passes the gate; default ON, set SAVEGATE_RVT_ELEMENTS=0 to disable
            return a, v
    raise UnsupportedVersion('unknown or unsupported file format (not a writable DWG/RVT)')
