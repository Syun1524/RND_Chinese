# -*- coding: utf-8 -*-
# movie.cpk TOC reader - MAGES Steam CPK variant (per GARbro ArcCPK.cs):
#   chunk = tag(4) + u32 zero(4) + u64 LE size(8) + data(size bytes)
#   data starts with '@UTF'; if not, decrypt: key=0x655F, out=b^(key&0xFF), key*=0x4115 (mod 2^32)
#   @UTF offsets are relative to chunk+8; schema entry = flags(1)[+3 skip if 0]+nameoff(4)
#   column flags: high nibble storage (0x10/0x30 skip), low nibble type
#   (0=u8,2=u16,4=u32,6=u64,8=f32,A=string,B=data), values big-endian
import struct

def lcg_decrypt(data):
    key = 0x655F
    out = bytearray(len(data))
    for i, b in enumerate(data):
        out[i] = b ^ (key & 0xFF)
        key = (key * 0x4115) & 0xFFFFFFFF
    return bytes(out)

def read_chunk(d, tag_off):
    size = struct.unpack('<Q', d[tag_off+8:tag_off+16])[0]
    data = d[tag_off+16:tag_off+16+size]
    if data[:4] != b'@UTF':
        data = lcg_decrypt(data)
    assert data[:4] == b'@UTF', data[:8]
    return data

def parse_utf(m):
    tsize, rows_off, str_off, data_off, name = struct.unpack('>IIII4s', m[4:24])
    ncols, rowlen = struct.unpack('>HH', m[24:28])
    nrows = struct.unpack('>I', m[28:32])[0]
    str_base = 8 + str_off
    data_base = 8 + data_off
    def getstr(o):
        e = m.index(b'\x00', str_base + o)
        return m[str_base + o:e].decode('utf-8', 'replace')
    cols = []
    p = 32
    for _ in range(ncols):
        flags = m[p]; p += 1
        if flags == 0:
            p += 3
            flags = m[p]; p += 1
        noff = struct.unpack('>I', m[p:p+4])[0]; p += 4
        cols.append((flags, getstr(noff)))
    rows = []
    rp = 8 + rows_off
    for _ in range(nrows):
        row = {}
        for flags, nm in cols:
            if flags & 0xF0 in (0x10, 0x30):
                continue  # zero/constant storage: no inline value
            t = flags & 0x0F
            if t == 0x0: row[nm] = m[rp]; rp += 1
            elif t == 0x2: row[nm] = struct.unpack('>H', m[rp:rp+2])[0]; rp += 2
            elif t == 0x3: row[nm] = struct.unpack('>h', m[rp:rp+2])[0]; rp += 2
            elif t in (0x4, 0x5): row[nm] = struct.unpack('>I', m[rp:rp+4])[0]; rp += 4
            elif t in (0x6, 0x7): row[nm] = struct.unpack('>Q', m[rp:rp+8])[0]; rp += 8
            elif t == 0x8: row[nm] = struct.unpack('>f', m[rp:rp+4])[0]; rp += 4
            elif t == 0xA:
                o = struct.unpack('>I', m[rp:rp+4])[0]; rp += 4
                row[nm] = getstr(o)
            elif t == 0xB:
                o, n = struct.unpack('>II', m[rp:rp+8]); rp += 8
                row[nm] = m[data_base + o:data_base + o + n]
            else: raise ValueError(hex(t) + ' ' + nm)
        rows.append(row)
    return rows

def read_cpk(path):
    d = open(path, 'rb').read()
    assert d[:4] == b'CPK '
    hdr = parse_utf(read_chunk(d, 0))[0]
    content_off = hdr['ContentOffset']
    toc_off = hdr['TocOffset']
    assert d[toc_off:toc_off+4] == b'TOC ', d[toc_off:toc_off+4]
    return d, parse_utf(read_chunk(d, toc_off)), content_off

if __name__ == '__main__':
    import sys
    d, rows, content_off = read_cpk(sys.argv[1])
    print('rows:', len(rows), '| cols:', list(rows[0].keys()))
    ids = [r['ID'] for r in rows]
    print('IDs sequential 0..n:', ids == list(range(len(ids))), '| max id:', max(ids))
    for r in rows:
        if 'dar020' in str(r.get('FileName', '')):
            print('DAR020 row:', r)
    print('first 3 rows:')
    for r in rows[:3]:
        print(' ', r)
