"""Format adapters: sniff version, snapshot (key -> comparable) for the verify diff, structural validate.
A snapshot key present in the source and output must be equal unless the manifest lists it as modified."""
import hashlib, os, sys, re, struct
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
        b = bytearray(buf[:0x80]) + bytearray(buf[0xEC:0x100]); a = int.from_bytes(b[0x0D:0x11], 'little'); b[0x0D:0x11] = bytes(4)   # + the 20 unreferenced bytes behind the encrypted header block (item 131: 43/43 outputs equal the source)
        ok = a == 0 or bytes(buf[a:a + 16]) == _PREVIEW_SENTINEL
        return _h(bytes(b)) + (':preview-ok' if ok else ':preview-broken')
    return None


def _r2000_section_problems(buf):
    """AC1015 header-variable and class sections: CRC16 and complement end sentinel (c4x-dwgreadfuzz 191: 24/24 flips inside the class section were invisible to source_damage;
    the writer copies the section unchanged, so the damage would be saved as if it were good)."""
    if bytes(buf[:6]) != b'AC1015': return []
    import dwgfmt as F
    out = []
    try:
        loc = F.read_r13_r2000(buf)['locators']
        for i, name in ((0, 'header variables'), (1, 'classes')):
            _, crc_ok, sent_ok = F.section_r13_r2000(buf, loc[i])
            if not crc_ok: out.append('AC1015 %s section: CRC mismatch' % name)
            if not sent_ok: out.append('AC1015 %s section: end sentinel mismatch' % name)
    except Exception as e:
        out.append('AC1015 sections unreadable: %s' % str(e)[:80])
    return out


def _dangling_after_delete(ms, mo, limit=20):
    """c4x-dwgreadfuzz 225: handles that existed in the source object map, are gone from the output, and are still NAMED by a surviving object. A surviving object that names
    them is byte-identical to the source (undeclared-object rule) so no other check sees the dangling pointer. Pre-existing dangling pointers never count (only handles
    that disappeared). [(referrer handle, deleted handle)]"""
    gone = set(ms.objs) - set(mo.objs)
    if not gone: return []
    import dwgmodel
    out = []
    for h, o in mo.objs.items():
        try: hs = dwgmodel.resolve_handles(o)
        except Exception: continue
        for c, v in hs:
            if v in gone:
                out.append((h, v)); break
        if len(out) >= limit: break
    return out


def _r2000_preview_problems(buf):
    """AC1015 preview image block (c4x-dwgreadfuzz 233): the only large region with no CRC. Structure only: start sentinel, RL size == 1 + 9*count + sum(sizes), contiguous entry
    offsets, end sentinel at its place, BMP entries (code 2) with a BITMAPINFOHEADER (biSize 40, planes 1). Pixel flips are not detectable. [] = fine or no preview."""
    import struct
    if bytes(buf[:6]) != b'AC1015' or len(buf) < 0x11: return []
    img = struct.unpack_from('<I', buf, 0x0D)[0]
    if img == 0: return []
    SENT = bytes.fromhex('1f256d07d43628289d57ca3f9d44102b')
    out = []
    try:
        if bytes(buf[img:img + 16]) != SENT: return ['preview: start sentinel']
        n = struct.unpack_from('<I', buf, img + 16)[0]; cnt = buf[img + 20]
        ents = [struct.unpack_from('<BII', buf, img + 21 + 9 * i) for i in range(cnt)]
        if n != 1 + 9 * cnt + sum(e[2] for e in ents): out.append('preview: size field %d != entries %d' % (n, 1 + 9 * cnt + sum(e[2] for e in ents)))
        pos = img + 21 + 9 * cnt
        for code, start, size in ents:
            if start != pos: out.append('preview: entry code %d starts at %d, expected %d' % (code, start, pos))
            if code == 2 and size >= 40:
                bsz, _w, _h, planes = struct.unpack_from('<IiiH', buf, start)
                if bsz != 40 or planes != 1: out.append('preview: BMP header (biSize %d, planes %d)' % (bsz, planes))
            pos = start + size
        if img + 20 + n + 16 > len(buf): out.append('preview: end sentinel beyond the file')
        elif bytes(buf[img + 20 + n:img + 20 + n + 16]) != bytes(x ^ 0xFF for x in SENT) and bytes(buf[img + 20 + n:img + 20 + n + 16]) != PREVIEW_END_SENT:
            out.append('preview: end sentinel')
    except (struct.error, IndexError):
        out.append('preview: unreadable')
    return out


PREVIEW_END_SENT = bytes.fromhex('e0da92f8 2bc9d7d7 62a835c0 62bbefd4'.replace(' ', ''))


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


def _header_section_crc_ok(m):
    """AcDb:Header section CRC16 of an R2004-family model (position 20 + size + 4; 20 + size for AC1018). None when not applicable.
    c4x-dwgreadfuzz item 108: a writer using 'length - 18' put the new CRC in the wrong place for 41/239 real files."""
    try:
        import dwgfmt as F
        if m.version not in ('AC1018', 'AC1024', 'AC1027', 'AC1032'): return None
        h = F.r2004_section_data(m._buf, m._info, 'AcDb:Header')
        sz = int.from_bytes(h[16:20], 'little'); p = 20 + sz + (0 if m.version == 'AC1018' else 4)
        return F.crc16(bytes(h[16:p]), 0xC0C1) == int.from_bytes(h[p:p + 2], 'little')
    except Exception:
        return None


def _header_section_diff(ms, mo):
    """Byte offsets of AcDb:Header section data that differ between source and output model, outside the HANDSEED field (<= 10 bytes) and the section CRC.
    The decoded header variables stop after DIMATFIT for R2007+ (control-object handles, dictionary handles, FLAGS, INSUNITS, string and handle streams are NOT decoded),
    so a flipped bit there is invisible to the snapshot. c4x-dwgreadfuzz item 111. None when not applicable."""
    try:
        import dwgfmt as F, dwghdr
        if ms.version not in ('AC1018', 'AC1024', 'AC1027', 'AC1032') or mo.version != ms.version: return None
        a = F.r2004_section_data(ms._buf, ms._info, 'AcDb:Header'); b = F.r2004_section_data(mo._buf, mo._info, 'AcDb:Header')
        if len(a) != len(b): return [-1]
        sp = dwghdr.header_vars(ms._buf, ms._info, ms.version).get('_seedpos')
        if sp is None: return None
        sz = int.from_bytes(a[16:20], 'little'); crc = 20 + sz + (0 if ms.version == 'AC1018' else 4)
        return [i for i in range(len(a)) if a[i] != b[i] and not (sp // 8 <= i <= sp // 8 + 10) and not (crc <= i < crc + 2)]
    except Exception:
        return None


def _other_sections_changed(ms, mo):
    """Names of R2004-family sections other than Header, Objects, Handles, Preview whose decoded data differ between source and output (Classes, AppInfo, SummaryInfo,
    FileDepList, Template, RevHistory, AppInfoHistory...). The writer carries them verbatim (c4x-dwgreadfuzz item 110: 66/66 files); no snapshot key covered them. None if n/a."""
    try:
        import dwgfmt as F
        if ms.version not in ('AC1018', 'AC1024', 'AC1027', 'AC1032') or mo.version != ms.version: return None
        skip = {'AcDb:Header', 'AcDb:AcDbObjects', 'AcDb:Handles', 'AcDb:Preview'}
        out = []
        for nm in sorted(set(ms._info['sections']) | set(mo._info['sections'])):
            if nm in skip: continue
            a = F.r2004_section_data(ms._buf, ms._info, nm) if nm in ms._info['sections'] else None
            b = F.r2004_section_data(mo._buf, mo._info, nm) if nm in mo._info['sections'] else None
            if a != b: out.append(nm)
        return out
    except Exception:
        return None


def _preview_changed(ms, mo):
    """AcDb:Preview may differ between source and output ONLY in the 4-byte 'start address' of each image entry (entries: code RC, start RL, size RL after the 16-byte
    sentinel, 4-byte size and 1-byte count); the writer rebases them (c4x-dwgreadfuzz item 110: offsets 22-24 and 31-33). Returns differing offsets outside those, [] if fine, None if n/a."""
    try:
        import dwgfmt as F
        if ms.version not in ('AC1018', 'AC1024', 'AC1027', 'AC1032') or mo.version != ms.version: return None
        if 'AcDb:Preview' not in ms._info['sections'] and 'AcDb:Preview' not in mo._info['sections']: return None
        a = F.r2004_section_data(ms._buf, ms._info, 'AcDb:Preview') if 'AcDb:Preview' in ms._info['sections'] else None
        b = F.r2004_section_data(mo._buf, mo._info, 'AcDb:Preview') if 'AcDb:Preview' in mo._info['sections'] else None
        if a is None or b is None: return [-1]
        if len(a) != len(b): return [-2]
        n = a[20] if len(a) > 20 else 0; ok = set()
        for i in range(n):
            st = 21 + 9 * i + 1
            ok |= set(range(st, st + 4))
        return [i for i in range(len(a)) if a[i] != b[i] and i not in ok]
    except Exception:
        return None


def _page_padding_nonzero(m):
    """Numbers of data pages of an R2004-family model whose bytes behind the compressed payload (inside the page) are not all zero. Our writer zero-fills them
    (c4x-dwgreadfuzz item 129: 0 of 2020 output pages non-zero, while 1783 of 2025 SOURCE pages carry non-zero padding from the producing application), so in an OUTPUT
    non-zero padding means a flipped or foreign byte that no decoder looks at (items 122/124: the only bit flips the gate accepted, 5 of 900). None if n/a."""
    try:
        import struct
        if m.version not in ('AC1018', 'AC1024', 'AC1027', 'AC1032'): return None
        b = m._buf; out = []
        for n, (a, sz) in m._info['pages'].items():
            if a + 32 > len(b): continue
            mask = 0x4164536B ^ a; f = [x ^ mask for x in struct.unpack_from('<8I', b, a)]
            if f[0] != 0x4163043B: continue
            end = a + 32 + f[2]
            if end <= a + sz and any(b[end:a + sz]): out.append(n)
        return out
    except Exception:
        return None


def _r2000_regions_changed(ms, mo):
    """AC1015 (R2000) has no section pages: the gate checked nothing outside the objects there (c4x-dwgreadfuzz item 136: 42 of 300 random bit flips in a real AC1015 writer
    output were ACCEPTED: 34 in the pre-header area (preview image etc.), 4 in the classes section, 3 in the header-variables section, 1 in the locator area).
    Output must equal the source in: the 25-byte file header (except the image seeker at 0x0D), everything between the locator table and the header-variables section,
    the classes section, and the header-variables section except the HANDSEED field (<= 10 bytes) and its CRC. Returns names of changed regions, None if n/a."""
    try:
        import struct, dwgfmt as F, dwghdr
        if ms.version != 'AC1015' or mo.version != 'AC1015': return None
        a, b = ms._buf, mo._buf
        ha, hb = F.read_r13_r2000(a), F.read_r13_r2000(b)
        la = {n: (s_, z) for n, s_, z in ha['locators']}; lb = {n: (s_, z) for n, s_, z in hb['locators']}
        out = []
        if bytes(a[:0x19]) != bytes(b[:0x19]): out.append('file header')      # incl. the image seeker: the pre-header area is carried unchanged, so it cannot move (item 138: seeker flip accepted)
        ta = 0x19 + 9 * len(ha['locators']) + 2; tb = 0x19 + 9 * len(hb['locators']) + 2
        if ta != tb or bytes(a[ta:la[0][0]]) != bytes(b[tb:lb[0][0]]): out.append('pre-header area')
        if 1 not in la or 1 not in lb or la[1][1] != lb[1][1] or bytes(a[la[1][0]:la[1][0] + la[1][1]]) != bytes(b[lb[1][0]:lb[1][0] + lb[1][1]]): out.append('classes section')
        # second header (copy of the header variables behind the object map, 149 bytes, sentinel d47b21ce...): only the 7 patched 32-bit pointer fields and the section CRC may differ
        try:
            if 2 in la and 4 in la and 2 in lb and 4 in lb:
                ga = bytes(a[la[2][0] + la[2][1]:la[4][0]]); gb = bytes(b[lb[2][0] + lb[2][1]:lb[4][0]])
                if len(ga) != len(gb): out.append('second header size')
                elif ga[:16] == bytes.fromhex('d47b21ce28939fbf53244009123caa01'):
                    ok = set()
                    for pbit in (162, 352, 386, 428, 462, 504, 538):
                        ok |= set(range(pbit // 8, (pbit + 32 + 7) // 8 + 1))
                    sz_ = int.from_bytes(ga[16:20], 'little'); ok |= {6 + sz_, 7 + sz_}
                    if any(ga[i] != gb[i] and i not in ok for i in range(len(ga))): out.append('second header')
                    else:   # the seven pointer fields must carry the values of the OUTPUT's own locator table (item 101: writer does; a flipped bit inside a pointer is otherwise invisible)
                        def f32(buf, pbit):
                            v = 0
                            for k in range(32): v |= ((buf[(pbit + k) >> 3] >> (7 - ((pbit + k) & 7))) & 1) << (8 * (k // 8) + 7 - (k % 8))
                            return v
                        exp = [(162, lb[2][0] + lb[2][1]), (352, lb[0][0]), (386, lb[0][1]), (428, lb[1][0]), (462, lb[1][1]), (504, lb[2][0]), (538, lb[2][1])]
                        if any(f32(gb, pb) != v for pb, v in exp): out.append('second header pointers')
                elif ga != gb: out.append('second header (zero gap family)')
        except Exception:
            pass
        da, ok_a, _ = F.section_r13_r2000(a, (0,) + la[0]); db, ok_b, _ = F.section_r13_r2000(b, (0,) + lb[0])
        if ok_a and not ok_b: out.append('header variables CRC')
        if len(da) != len(db): out.append('header variables size')
        else:
            sp = dwghdr.decode_header(bytes(a[la[0][0]:la[0][0] + la[0][1]]), 'AC1015', 160).get('_seedpos')
            if sp is None:   # HANDSEED not decodable (7 of 112 local AC1015 files, item 142): the writer refuses to change such a header, so ANY change (but the section CRC) is damage
                szh = int.from_bytes(bytes(a[la[0][0] + 16:la[0][0] + 20]), 'little')
                if any(da[i] != db[i] for i in range(len(da)) if not (szh <= i < szh + 2)): out.append('header variables (seed not decodable)')
                return out
            # da starts after the 20-byte sentinel+size prefix in this reader; _seedpos is relative to the section incl. prefix (start=160 bits = 20 bytes)
            bad = [i for i in range(len(da)) if da[i] != db[i] and not (sp // 8 - 20 <= i <= sp // 8 - 20 + 10)]
            if bad: out.append('header variables')
        return out
    except Exception:
        return None


def _is_dim_block_ref(e):
    """A dimension's geometry block: anonymous '*D<n>' OR a named block (c4x-dwgreadfuzz item 145: a real AC1032 dimension owns 'DIMBLOCK60-CCW07'; moving/copying it was refused with 20 'changes' in the block's entities)."""
    br = e.get('block_ref') or ''
    return br.startswith('*D') or (br != '' and str(e.get('kind', '')).startswith('DIM'))


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
            out['ent:%x' % e['handle']] = hashlib.blake2b((repr(sorted((k, _plain(v)) for k, v in e.items() if not (k == 'xdicmissing' and m.version == 'AC1015'))) + '|' + _plain(blk)).encode(), digest_size=12).digest()   # AC1015: the flag is judged in extra_checks (item 119)
            ent_handles.add(e['handle']); self.owners[e['handle']] = e.get('owner')
            if str(e.get('kind', '')).startswith(('INSERT', 'MINSERT')) and isinstance(e.get('block_handle'), int): self.bheaders[e['handle']] = e['block_handle']
        self.blockhs |= set(getattr(m, 'blocks', {}))   # block records own entities but are not entities: declaring one must not excuse all its entities
        dimblk = {e['block_ref']: e['handle'] for blk, e in m.entities() if _is_dim_block_ref(e)} if hasattr(m, 'entities') else {}
        self.dims = getattr(self, 'dims', set()) | set(dimblk.values())
        bhmap = {e['handle']: e.get('block_handle') for blk, e in m.entities() if _is_dim_block_ref(e)} if dimblk else {}
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
            return (['object map: CRC mismatch'] if getattr(m, 'omap_ok', None) is False else []) + _header_problems(buf) + _r2000_section_problems(buf) + _r2000_preview_problems(buf) + _system_page_problems(buf, getattr(m, '_info', None)) + _page_problems(buf, getattr(m, '_info', None))[:50] + self._crc_damage(m)[:200] + self._handle_damage(m)[:200]
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
        for nm_ in (_other_sections_changed(ms, mo) or [])[:5]: bad.append(('section_changed', nm_))
        for nm_ in (_r2000_regions_changed(ms, mo) or [])[:5]: bad.append(('r2000_region_changed', nm_))
        for n_ in (_page_padding_nonzero(mo) or [])[:5]: bad.append(('page_padding', 'page:%d' % n_))
        pv_ = _preview_changed(ms, mo)
        if pv_: bad.append(('preview_changed', 'pv:%d' % pv_[0]))
        hd_ = _header_section_diff(ms, mo)
        if hd_: bad.append(('header_section_bytes', 'hdr:%d' % hd_[0]))
        okm = _header_section_crc_ok(mo)
        if okm is False and _header_section_crc_ok(ms) is not False: bad.append(('header_section_crc', 'hdr'))
        # c4x-dwgreadfuzz item 119: R2000 'no links' flag. Erasing/adding an entity makes the writer give its chain neighbours explicit prev/next links (flag 1 -> 0, same
        # drawing). Allowed only in that direction (never 0 -> 1), only for AC1015 and only when the manifest adds or deletes something.
        if getattr(ms, 'version', None) == 'AC1015' and getattr(mo, 'version', None) == 'AC1015':
            try:
                f0 = {e['handle']: e.get('xdicmissing') for _, e in ms.entities()}; f1 = {e['handle']: e.get('xdicmissing') for _, e in mo.entities()}
                moved = [h for h in f0 if h in f1 and f0[h] != f1[h]]
                declared_ = bool(manifest.get('added') or manifest.get('deleted'))
                nb = [h for h in moved if not (f0[h] == 1 and f1[h] == 0)]
                if nb or (moved and not declared_) or len(moved) > 2 * (len(manifest.get('added', ())) + len(manifest.get('deleted', ()))) + 2:
                    bad.append(('xdic_flag_changed', 'ent:%x' % (nb or moved)[0]))
            except Exception as e:
                bad.append(('xdic_check_failed', str(e)[:60]))
        # c4x-dwgreadfuzz item 87: the element view compares ENTITIES by decoded fields only, so a CRC-consistent bit flip in a bit the decoder discards (e.g. the
        # three visual-style flag bits of common_entity) is invisible to it (5/295 CRC-fixed LINE flips accepted by every check). An object that is not declared
        # (modified/added/side effect) must therefore be byte-identical to the source.
        try:
            r2000 = getattr(mo, 'version', 'AC1018') <= 'AC1015'
            mod_, add_, dele_ = self.expand(manifest); decl_ = mod_ | add_ | dele_ | self.side_effects(manifest)
            und = []
            for h, o in ms.objs.items():
                p = mo.objs.get(h)
                if p is None or p.raw == o.raw: continue
                if 'obj:%x' % h in decl_ or 'ent:%x' % h in decl_: continue
                und.append(h)
            # R2000 links entities in a chain: adding/deleting one rewrites the bytes of its (at most two) neighbours, whose decoded fields do not change. Allow that many
            # undeclared changed objects per declared add/delete there, nothing else (item 151); other versions: none.
            for rh_, dh_ in _dangling_after_delete(ms, mo): bad.append(('dangling_after_delete', 'obj:%x names deleted obj:%x' % (rh_, dh_)))
            quota = 2 * (len(manifest.get('added', ())) + len(manifest.get('deleted', ()))) if r2000 else 0
            if len(und) > quota:
                for h in und[:5]: bad.append(('undeclared_object_bytes', 'obj:%x' % h))
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

    def _block_controls(self):
        """obj keys of the BLOCK_CONTROL object(s) (type 48) of the source. The old code assumed handle 1; real files use other handles (c4x-dwgreadfuzz item 118: a dimension copy in an AC1024 file was refused because BLOCK_CONTROL is 0x4a1 there)."""
        pair = getattr(self, '_pair', None)
        if not pair: return set()
        return {'obj:%x' % h for h, o in pair[0].objs.items() if o.type == 48}

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
                if k in getattr(self, 'dims', ()): se |= {'obj:1'} | self._block_controls() | self.dimobjs.get(k, set())   # adding/removing a dimension adds/removes its anonymous block: BLOCK_CONTROL object list
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


def _plain_damage(n, d):
    """structure rules for the plain (non-ECC) streams; [] = looks fine"""
    import struct
    try:
        if n == 'PartAtom':
            from xml.dom import minidom; minidom.parseString(d)
        elif n == 'RevitPreview4.0':
            if d.find(b'\x89PNG') < 0 and d[:2] != b'BM': return ['%s: no PNG/BMP signature' % n]
        elif n == 'BasicFileInfo':
            if 'Build'.encode('utf-16le') not in d: return ['%s: no Build key' % n]
        elif n == 'Contents':
            if d[:4] != b'\x62\x19\x22\x05': return ['%s: bad magic' % n]
        elif n == 'TransmissionData':
            if len(d) < 4 or 4 + 2 * struct.unpack('<I', d[:4])[0] != len(d): return ['%s: length field does not match' % n]
            from xml.dom import minidom; minidom.parseString(d[4:].decode('utf-16le').rstrip('\0').encode())
    except Exception as ex: return ['%s: %s' % (n, type(ex).__name__)]
    return []


class RvtAdapter:
    name = 'rvt'
    def __init__(self, lib=None, elements_fn=None):
        lib = lib or os.environ.get('SAVEGATE_RVT_LIB') or os.path.expanduser('~/rvt-research/write-lab')
        if lib not in sys.path: sys.path.insert(0, lib)
        if os.path.dirname(lib) not in sys.path: sys.path.append(os.path.dirname(lib))   # rvt_integrity.py lives next to write-lab
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

    @staticmethod
    def _unreferenced_tail(buf):
        """c2x-rvtgap 45/364: whole sectors after the last FAT-referenced sector would be dropped by a rewrite (the writer emits a compact container); refuse so appended data is never lost silently"""
        try:
            import cfb
            c = cfb.CFB(bytes(buf)); last = max(i for i, v in enumerate(c.fat) if v != 0xFFFFFFFF and i < c.nsectors)
            n = c.nsectors - (last + 1)
            return ['%d whole sector(s) after the last used sector would be dropped by a save' % n] if n > 0 else []
        except Exception:
            return []

    def source_damage(self, buf):
        d = self._damage(buf); d = list(d) + self._unreferenced_tail(buf); self._src_dmg = set(d); self._src_gtails = self._global_tails(buf)
        try: self._src_slack = self._slack_map(buf)
        except Exception: self._src_slack = None
        self._src_member_max = self._member_max(buf); self._src_buf = buf
        return d

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
        try:
            import rvt_integrity       # c4x-dwgreadfuzz 190: FAT/miniFAT loops, DIFAT, directory tree: olefile-style readers accept these silently
            errs.extend('container %s: %s' % x for x in rvt_integrity.audit(bytes(buf)))
        except ImportError: errs.append('container audit unavailable (rvt_integrity.py not found next to the writer lab)')
        for n, e in S.items():
            if len(e.data) != e.size: errs.append('%s: %d bytes readable of %d declared (FAT chain damaged/truncated)' % (n, len(e.data), e.size)); continue   # c4x-rvtgap
            if n in ('PartAtom', 'RevitPreview4.0', 'BasicFileInfo', 'Contents', 'TransmissionData'):   # c7x-rvtread2: plain streams, structure rules (0 false positives on 22 public samples)
                errs.extend(_plain_damage(n, e.data)); continue
            if n in rvtw.PLAIN or n.startswith('\x05'): continue      # OLE property-set streams are plain
            d = e.data
            if d[:5] == b'<?xml': continue      # c7x-rvtread2: raw-gzip-looking Formats/Latest IS page-ECC protected, do not skip it
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
        import struct
        c = cfb.CFB(buf)
        out = {'stream:' + k: _h(e.data) for k, e in c.streams().items()}
        out['meta:streams'] = repr(sorted(c.streams()))
        out['meta:sector'] = '%d' % c.major
        out['meta:hdr'] = _h(bytes(buf[8:24]) + bytes(buf[24:44]) + bytes(buf[56:60]) + bytes(buf[64:72]))      # c4x-rvtgap: version, byte order, shifts, reserved, directory-sector count, mini cutoff: not part of any edit (the writer reproduces them)
        out['meta:dirmeta'] = _h(repr([(e.name, e.type, bytes(e.clsid), e.state, e.color, bytes(e.raw)[struct.unpack_from('<H', e.raw, 64)[0]:64], bytes(e.raw)[68:80], bytes(e.raw)[116:128] if e.type == 1 else b'') for e in c.entries]).encode())      # c4x-rvtgap: directory-entry clsid/state/colour changes are not part of any edit (times are free)
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
        # c5x-rvtgap: the byte-exact rule (_byte_window_checks) is strictly tighter whenever it applies; the 8 KB-per-element block allowance wrongly refuses elements whose own record is
        # larger (a wall record is ~20 KB of B-rep topology). When it applied and passed, the block rule has nothing to add.
        if not self._byte_window_checks(manifest) and getattr(self, '_bw_applied', False): return []
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

    def filter_changed(self, bad, a, b, manifest):
        """c5x-rvtgap RVT-EDIT rung 1: moving a Level (or any element others depend on) changes the DERIVED view (geometry, derived parameters) of its dependents
        although their stored records are byte-identical. With manifest['derived_ok'] = True an undeclared element may differ in the derived view only: its raw
        record-field hash (class + decoded fields, the '|R' part) must be equal, and the byte-exact window rule (_byte_window_checks) must pass, i.e. every differing byte lies inside a
        declared element's own record. Without the flag nothing changes."""
        if not manifest.get('derived_ok') or not any(k == 'changed' for k, _ in bad): return bad
        if self._byte_window_checks(manifest): return bad
        def part(v, tag):
            i = v.find('|' + tag)
            if i < 0: return ''
            j = v.find('|', i + 2)
            return v[i:j if j > 0 else len(v)]
        keep = []
        for kind, k in bad:
            if kind == 'changed' and k in a and k in b and part(a[k], 'R') == part(b[k], 'R') and part(a[k], 'R'): continue
            keep.append((kind, k))
        return keep

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
        bad += self._delete_reference_checks(manifest)
        bad += self._nonfinite_checks(manifest)
        bad += self._dangling_ref_checks(manifest)
        bad += self._adler_checks(manifest)
        bad += self._byte_window_checks(manifest)
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

    MAX_IDS_FOR_REF_SCAN = 30000

    def _nonfinite_checks(self, manifest):
        """c2x-rvtgap 19: the RVT editor writes NaN/inf into a double field and the gate accepted it (declared edit of el:7 with no 'expect'); refuse non-finite floats in any
        declared modified/added element of the OUTPUT."""
        ids = set()
        for kind in ('modified', 'added'):
            for k in manifest.get(kind, ()):
                if str(k).startswith('el:'):
                    try: ids.add(int(str(k)[3:]))
                    except ValueError: pass
        h = getattr(self, '_buf_hist', [])
        if not ids or len(h) < 2: return []
        import math, tempfile, wledit
        fd, p = tempfile.mkstemp(suffix='.rvt'); os.write(fd, bytes(h[1])); os.close(fd)
        bad = []; p2 = None
        try:
            ed = wledit.Editor(p)
            def badleaves(v, d=0):
                """bad leaf values (as repr strings) in a field tree"""
                if d > 12: return []
                if isinstance(v, float):
                    return [repr(v)] if (math.isnan(v) or math.isinf(v) or abs(v) > 1e100) else []       # c2x-rvtgap: 1e300 is finite but no real model value
                if isinstance(v, str):
                    return [repr(v)] if any(ord(c) < 32 and c not in '\t' or c in '\u202e\u2066\u2067\u2068\u2069\u200b\ufeff\ufffe\uffff' or 0xD800 <= ord(c) <= 0xDFFF for c in v) else []
                if isinstance(v, dict): return [x for y in v.values() for x in badleaves(y, d + 1)]
                if isinstance(v, (list, tuple)): return [x for y in v for x in badleaves(y, d + 1)]
                return []
            # c5x-rvtgap: only values that are NEW versus the source element count (a source string with a legitimate CRLF stays editable elsewhere)
            sed = None; p2 = None
            sb = getattr(self, '_src_buf', None)
            if sb is not None:
                fd2, p2 = tempfile.mkstemp(suffix='.rvt'); os.write(fd2, bytes(sb)); os.close(fd2)
                try: sed = wledit.Editor(p2)
                except Exception: sed = None
            for e in sorted(ids):
                try: r = ed.trace(e)[2]
                except Exception: continue
                new_bad = badleaves(r.get('fields'))
                if new_bad and sed is not None:
                    try: old = badleaves(sed.trace(e)[2].get('fields'))
                    except Exception: old = []
                    for o in old:
                        if o in new_bad: new_bad.remove(o)
                if new_bad: bad.append(('nonfinite_value', 'el:%d holds a NaN, infinite, huge or control-character value in the output' % e))
        except Exception as ex: bad.append(('nonfinite_unchecked', 'could not scan the declared elements for NaN/inf: %s' % ex))
        finally:
            os.unlink(p)
            if p2: os.unlink(p2)
        return bad

    def _byte_window_checks(self, manifest):
        """c5x-rvtgap SEV1: 1 of 40 random single-bit flips in the 22-byte record headers between element records (next to a valid declared edit) was ACCEPTED: the element view
        decodes fields only, the 1 KB block rule allows ~8 KB per element. Byte-exact rule: in the inflated partition of the declared element(s), the differing window
        (everything between the common prefix and the common suffix of source and output) must lie inside the declared elements' own records (field span plus 40 bytes of
        record header in front, 8 behind). Applies to pure in-place edits (no add/delete) of elements that live in one partition stream."""
        self._bw_applied = False
        if manifest.get('added') or manifest.get('deleted'): return []
        ids = []
        for k in manifest.get('modified', ()):
            if str(k).startswith('el:'):
                try: ids.append(int(str(k)[3:]))
                except ValueError: pass
        h = getattr(self, '_buf_hist', [])
        if not ids or len(h) < 2 or not h[0] or not h[1]: return []
        import tempfile
        paths = []
        try:
            import wledit, cfb, rvtw, wlpart
            def mk(b):
                fd, p = tempfile.mkstemp(suffix='.rvt'); os.write(fd, bytes(b)); os.close(fd); paths.append(p); return wledit.Editor(p)
            ed = mk(h[0]); pn = None; lo, hi = None, None
            for e in ids:
                t = ed.trace(e)
                if pn not in (None, t[0]): return []                   # several partitions: other rules cover it
                pn = t[0]; l = min(x[2] for x in t[3]); u = max(x[3] for x in t[3])
                lo = l if lo is None else min(lo, l); hi = u if hi is None else max(hi, u)
            def payload(buf):
                st = rvtw.Stream(cfb.CFB(bytes(buf)).streams()[pn].data); pt = wlpart.Partition(st)
                return b''.join(bytes(m['raw']) for m in pt.mem)
            A = payload(h[0]); B = payload(h[1])
        except Exception as ex: return [('byte_window_unchecked', 'could not compare the declared partition byte for byte: %s' % str(ex)[:150])]
        finally:
            for p in paths:
                try: os.unlink(p)
                except OSError: pass
        self._bw_applied = True
        if A == B: return [('declared_edit_not_applied', '%s: el:%s declared as modified but the partition is byte-identical to the source (the edit did not land)' % (pn, ids))]
        n = min(len(A), len(B)); p = 0
        while p < n and A[p] == B[p]: p += 1
        q = 0
        while q < n - p and A[len(A) - 1 - q] == B[len(B) - 1 - q]: q += 1
        a_end = len(A) - q
        if abs(len(B) - len(A)) > 16384 * len(ids):      # the cap the old 8 KB block rule imposed in effect (a 16384-char name = 32 KB growth stays refused, 7000 chars = 14 KB passes)
            return [('growth_too_large', '%s: the partition changed size by %d bytes for %d declared element(s)' % (pn, len(B) - len(A), len(ids)))]
        if p < lo - 40 or a_end > hi + 8:
            return [('changed_outside_declared_record', '%s: bytes %d..%d differ, the declared element(s) occupy %d..%d' % (pn, p, a_end, lo, hi))]
        return []

    def _adler_checks(self, manifest):
        """c5x-rvtgap SEV1: a single-bit flip in the 4-byte Adler32 field of a record header (between element records, invisible to the element view) was ACCEPTED
        (1 of 40 random header-gap flips on the 2024 public family; 99% of its records carry a valid Adler32 over the record body). Every record whose Adler32 is valid in the
        SOURCE must still be valid in the OUTPUT (the editor recomputes it for the records it edits); a record that disappears counts as lost."""
        h = getattr(self, '_buf_hist', [])
        if len(h) < 2 or not h[0] or not h[1]: return []
        import tempfile, struct, zlib
        paths = []
        try:
            import numpy as np, cfb, rvtw, wlpart, rvt_scan as S, rvt_inventory as I
            def amap(buf):
                fd, p = tempfile.mkstemp(suffix='.rvt'); os.write(fd, bytes(buf)); os.close(fd); paths.append(p)
                o, cls, ids = S.load(p); W = S.id_size(cls); hs = 12 + W; etags = I.element_tags(cls)
                c = cfb.CFB(bytes(buf)); out = {}
                arr = np.array(sorted(ids), dtype=np.uint32 if W == 4 else np.uint64)
                for n, e in c.streams().items():
                    if not n.startswith('Partitions/'): continue
                    pt = wlpart.Partition(rvtw.Stream(e.data), hs=hs); bj = b''.join(bytes(m['raw']) for m in pt.mem)
                    for i in S.header_candidates_tagged(bj, arr, W, etags):
                        i = int(i); L = struct.unpack_from('<I', bj, i + hs - 4)[0]
                        if L > len(bj) - i - hs or L < 2: continue
                        eid = int.from_bytes(bj[i + 4:i + 4 + W], 'little'); st = struct.unpack_from('<I', bj, i + 4 + W)[0]
                        out[(n, eid)] = (zlib.adler32(bj[i + 4 + W + 8:i + hs + L]) & 0xffffffff == st)
                return out
            a = amap(h[0]); b = amap(h[1])
        except Exception as ex: return [('adler_unchecked', 'could not verify the record checksums of source and output: %s' % str(ex)[:150])]
        finally:
            for p in paths:
                try: os.unlink(p)
                except OSError: pass
        gone = set()
        for k in manifest.get('deleted', ()):
            try: gone.add(int(str(k).split(':')[-1]))
            except ValueError: pass
        lost = sorted(k[1] for k, v in a.items() if v and not b.get(k, False) and k[1] not in gone)
        return [('record_checksum_broken', '%d record(s) with a valid Adler32 in the source are invalid or missing in the output (element ids %s)' % (len(lost), lost[:6]))] if lost else []

    def _dangling_ref_checks(self, manifest):
        """c5x-rvtgap 28: an edit that points an ElementId field of a declared element at an id that does not exist (the gate accepted 193 of 198 such edits on the
        2024 public family) leaves a dangling reference. Refuse NEW dangling ElementId values (sentinels >= 2**62 such as -1/-4 are fine) in declared modified/added
        elements; dangling values the SOURCE element already held are tolerated."""
        ids = set()
        for kind in ('modified', 'added'):
            for k in manifest.get(kind, ()):
                if str(k).startswith('el:'):
                    try: ids.add(int(str(k)[3:]))
                    except ValueError: pass
        h = getattr(self, '_buf_hist', [])
        if not ids or len(h) < 2: return []
        import tempfile, wledit
        paths = []
        def mk(b):
            fd, p = tempfile.mkstemp(suffix='.rvt'); os.write(fd, bytes(b)); os.close(fd); paths.append(p); return wledit.Editor(p)
        def nonelem(v):
            """negative ids (built-in categories, 'none' markers): 64-bit -N is >= 2**62; the 2016-2023 32-bit encoding of the same is 0xFF000000..0xFFFFFFFF"""
            return v >= 2 ** 62 or 0xFF000000 <= v <= 0xFFFFFFFF
        def refs(r, d=0):
            out = []
            if d > 12: return out
            if isinstance(r, dict):
                for x in r.values(): out += refs(x, d + 1)
            elif isinstance(r, (list, tuple)):
                for x in r: out += refs(x, d + 1)
            elif type(r).__name__ == 'EID': out.append(int(r))
            return out
        bad = []
        try:
            ed = mk(h[1]); oids = set(ed.m.ids)
            sb = getattr(self, '_src_buf', None)
            sed = mk(sb) if sb is not None else None
            soids = set(sed.m.ids) if sed is not None else set()
            for e in sorted(ids):
                try: r = ed.trace(e)[2]
                except Exception: continue
                dang = [v for v in refs(r.get('fields')) if not nonelem(v) and v not in oids]
                if not dang: continue
                old = []
                if sed is not None:
                    try: old = [v for v in refs(sed.trace(e)[2].get('fields')) if not nonelem(v) and v not in soids]
                    except Exception: old = []
                for v in old:
                    if v in dang: dang.remove(v)
                if dang: bad.append(('dangling_reference', 'el:%d refers to element id(s) %s that do not exist in the output' % (e, sorted(set(dang))[:4])))
        except Exception as ex: bad.append(('dangling_unchecked', 'could not scan the declared elements for dangling references: %s' % ex))
        finally:
            for p in paths: os.unlink(p)
        return bad

    def _delete_reference_checks(self, manifest):
        """c2x-rvtgap 17: a declared delete of an element that another SOURCE element still references (owner, family, level, ... any ElementId field) leaves a dangling
        id that no other check sees (the gate accepted deleting elements 0, 11, 14 of the 2024 sample family, each referenced by others). Refuse unless no other element
        names it; if the references cannot be scanned (no source buffer, too many elements) refuse as well."""
        dels = set()
        for k in manifest.get('deleted', ()):
            try: dels.add(int(str(k).split(':')[-1]))
            except ValueError: pass
        if not dels or os.environ.get('SAVEGATE_RVT_ALLOW_DANGLING_DELETE'): return []      # env only for tests of the delete mechanics
        buf = getattr(self, '_src_buf', None)
        try:
            if buf is None: raise ValueError('no source buffer')
            import tempfile, wledit, struct
            fd, p = tempfile.mkstemp(suffix='.rvt'); os.write(fd, bytes(buf)); os.close(fd)
            try:
                ed = wledit.Editor(p); found = {}
                if os.environ.get('SAVEGATE_RVT_SLOW_REFS'):
                    ids = sorted(ed.m.ids)
                    if len(ids) > self.MAX_IDS_FOR_REF_SCAN: raise ValueError('%d elements, reference scan limit %d' % (len(ids), self.MAX_IDS_FOR_REF_SCAN))
                    def walk(v, me, depth=0):
                        if depth > 12: return
                        if isinstance(v, dict):
                            for x in v.values(): walk(x, me, depth + 1)
                        elif isinstance(v, (list, tuple)):
                            for x in v: walk(x, me, depth + 1)
                        elif type(v).__name__ == 'EID' and int(v) in dels and int(v) != me: found.setdefault(int(v), []).append(me)
                    for e in ids:
                        try: r = ed.trace(e)[2]
                        except Exception: continue
                        walk(r.get('fields'), e)
                else:
                    # c5x-rvtgap: tracing every element took ~1 hour on a 28 MB project. The reader's record cache (decoded fields of every record, built once for the element
                    # view anyway) gives the same inbound references in ~3 s (checked against the full trace on the 2024 Snowdon Structural sample: identical answers for 5 elements).
                    # Elements the cache did not decode (a handful) are traced one by one so that no possible referrer is skipped.
                    import rvt_xcache
                    x = rvt_xcache.get_x_ro(p); seen = set()
                    def walk(v, me, depth=0):
                        if depth > 12: return
                        if isinstance(v, dict):
                            for y in v.values(): walk(y, me, depth + 1)
                        elif isinstance(v, (list, tuple)):
                            for y in v: walk(y, me, depth + 1)
                        elif type(v).__name__ == 'EID' and int(v) in dels and int(v) != me: found.setdefault(int(v), []).append(me)
                    for (eid, c), r in x['recs'].items():
                        seen.add(eid); walk(r.get('fields'), eid)
                    for e in sorted(set(ed.m.ids) - seen):
                        try: tr = ed.trace(e)
                        except IndexError: continue      # an ElemTable row without a framed record (the source itself has such unresolved ids): it holds no references
                        except Exception as ex2: raise ValueError('element %s could not be decoded: %s' % (e, ex2))
                        walk(tr[2].get('fields'), e)
            finally: os.unlink(p)
        except Exception as ex:
            return [('delete_references_unchecked', 'cannot prove that no element references the deleted id(s): %s' % ex)]
        return [('dangling_after_delete', 'el:%d is still referenced by elements %s' % (d, sorted(set(r))[:6])) for d, r in sorted(found.items())]

    @staticmethod
    def _member_max(buf):
        """c2x-rvtgap: largest decoded gzip member per Partitions stream of the source. 2016-2018 Autodesk files carry members of 140-146 KB, so the 131088 limit
        (true for 2019+) must not refuse a pristine older file; an output member may be as large as max(131088, the source's own largest in that stream)"""
        try:
            import cfb, rvtw, wlpart
            out = {}
            for n, e in cfb.CFB(buf).streams().items():
                if not n.startswith('Partitions/'): continue
                st = rvtw.Stream(e.data)
                if len(st.payload) < 40: continue
                out[n] = max(len(m['raw']) for m in wlpart.Partition(st).mem)
            return out
        except Exception: return {}

    @staticmethod
    def _slack_map(buf):
        """c4x-rvtgap 150: nonzero bytes after the end of a large stream in its last sector, and in free sectors (mini-stream tails excluded), keyed by stream name / sector index"""
        import cfb, struct
        c = cfb.CFB(buf); ss = c.ss; out = {}
        fat = []
        fat = list(c.fat)
        ns = len(buf) // ss - 1
        for name, e in c.streams().items():
            if e.size >= c.cutoff and e.size % ss:
                s = e.start; k = 0
                while fat[s] < 0xFFFFFFFA and k <= len(fat): s = fat[s]; k += 1
                t = bytes(buf[(s + 1) * ss + e.size % ss:(s + 2) * ss])
                if any(t): out[name] = t
        for i, x in enumerate(fat[:ns]):
            if x == 0xFFFFFFFF:
                t = bytes(buf[(i + 1) * ss:(i + 2) * ss])
                if any(t): out['free:%d' % i] = t
        return out

    def validate(self, buf):
        import cfb
        c = cfb.CFB(buf)
        s = c.streams()
        for need in ('BasicFileInfo',):
            if need not in s: raise VerifyFailed('stream %s missing in output' % need)
        if len(buf) != (c.nsectors + 1) * c.ss + (512 - c.ss if c.major == 3 else 0) and len(buf) % c.ss:
            raise VerifyFailed('container length is not sector aligned')
        src_sl = getattr(self, '_src_slack', None)
        if src_sl is not None:    # only against a known source: real Revit files carry nonzero slack, the writer pads with zeros; new nonzero slack that is not the source's own is refused
            try:
                for k, t in self._slack_map(buf).items():
                    if src_sl.get(k) != t: raise VerifyFailed('%s: slack after the stream end / free sector is nonzero and not the source\'s own' % k)
            except (IndexError, struct.error, ValueError): raise VerifyFailed('FAT chain unreadable while checking slack')
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
                    if len(m['raw']) > max(131088, min(147456, (getattr(self, '_src_member_max', None) or {}).get(n, 0))):       # c2x-rvtgap: allowance from the source capped (largest real member seen 146492, Revit 2018) so a mis-sequenced source_damage(output) cannot lift the limit; every real 2024/2026 file tops out at exactly 131088 (12 files); Revit rejects larger members (vcheck rule)
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
