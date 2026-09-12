# -*- coding: utf-8 -*-
# Rebuild movie_dar020.usm: original CRI container + re-encoded MPEG-2 video.
#
# Verified original structure (258 frames @30000/1001, ADX 48k stereo):
#   chunk = magic(4) + u32be size + payload(size); payload = 24B pre-header + body
#   pre-header: u16 hdrsize=24 | u16 misc | u16 0 | u16 kind(0=data,1=@UTF,2=#marker,3=@UTF)
#               | u16 0 | u16 ts(=frame_idx*100-1, 0 for frame 0) | u32 2997 | u32 0 | u32 0
#   sequence: CRID, @SFV@UTF(fmt), @SFA@UTF(fmt), #HEADER x2, @SFV@UTF(VIDEO_SEEKINFO),
#             #METADATA, [interleaved data: 258 SFV (1 frame each) + 261 SFA], #CONTENTS(SFV),
#             last SFA chunks, #CONTENTS(SFA)
#   VIDEO_SEEKINFO: 20 rows x 12B = [u32 0][u32 ofs_byte=file offset of chunk magic][u32 frmid],
#               every 13 frames; strings '<NULL>/VIDEO_SEEKINFO/ofs_byte/ofs_frmid/num_skip...'
#   CRID @UTF rows: filesize(stmid=0) = total file; '@SFV' row filesize = video bytes;
#               '@SFA' row filesize = audio bytes; avbps = bytes*8/duration (advisory)
import struct, sys, pathlib

def walk(d):
    pos, out = 0, []
    while pos + 8 <= len(d):
        magic = d[pos:pos+4]
        size = struct.unpack('>I', d[pos+4:pos+8])[0]
        out.append((pos, magic, size))
        pos += 8 + size
    assert pos == len(d), f'walk ended at {pos:#x} of {len(d):#x}'
    return out

def split_frames(es):
    """Split MPEG-2 ES into per-picture units; header runs (seq/gop/ext) stay
    with the picture that follows them."""
    sc = []
    i = 0
    while True:
        i = es.find(b'\x00\x00\x01', i)
        if i < 0 or i + 3 >= len(es):
            break
        sc.append((i, es[i+3]))
        i += 3
    pics = [p for p, t in sc if t == 0x00]
    assert len(pics) == 258, f'expected 258 pictures, got {len(pics)}'
    # for each picture, walk back over non-picture atoms (contiguous header run)
    starts = []
    for pi, p in enumerate(pics):
        h = p
        # previous start code before p
        j = sc.index((p, 0x00)) - 1 if pi > 0 or sc[0] != (p, 0x00) else -1
        k = sc.index((p, 0x00))
        while k > 0 and sc[k-1][1] != 0x00:
            k -= 1
        starts.append(sc[k][0])
    frames = []
    for n in range(258):
        a = starts[n]
        b = starts[n+1] if n + 1 < 258 else len(es)
        frames.append(es[a:b])
    # coding type of every picture: picture header after start code =
    # temporal_reference(10) | type(3) | vbv_delay(16); u16 at +4 = tref<<6|type<<3|vbv>>13
    types = []
    for p in pics:
        v = struct.unpack('>H', es[p+4:p+6])[0]
        types.append((v >> 3) & 7)
    return frames, types

def main(orig_path, m2v_path, out_path):
    d = open(orig_path, 'rb').read()
    es = open(m2v_path, 'rb').read()
    chunks = walk(d)
    frames, types = split_frames(es)
    # sanity: seek-target frames must be I-pictures
    for k in range(0, 258, 13):
        assert types[k] == 1, f'frame {k} type={types[k]}, need I'
    print(f'new ES: {len(frames)} frames, {len(es)} bytes, max frame {max(len(f) for f in frames)} B')

    # classify original chunks
    items = []  # ('crid'|'sfvfmt'|'sfaseek'|'marker'|'sfvdata'|'sfadata', orig chunk tuple)
    for (p, m, s) in chunks:
        pre = struct.unpack('>6H3I', d[p+8:p+8+24])
        if m == b'CRID':
            items.append(('crid', (p, m, s)))
        elif m == b'@SFV' and pre[3] == 1:
            items.append(('sfvfmt', (p, m, s)))
        elif m == b'@SFA' and pre[3] == 1:
            items.append(('sfafmt', (p, m, s)))
        elif pre[3] in (2, 3):
            body = d[p+8+24:p+8+34]
            kind = 'sfaseek' if (m == b'@SFA' and pre[3] == 3) else \
                   ('seek' if (m == b'@SFV' and pre[3] == 3) else 'marker')
            items.append((kind, (p, m, s)))
        elif m == b'@SFV':
            items.append(('sfvdata', (p, m, s)))
        elif m == b'@SFA':
            items.append(('sfadata', (p, m, s)))
        else:
            raise ValueError(m)

    video_bytes = sum(len(f) for f in frames)
    audio_bytes = sum(s - 24 for (p, m, s) in chunks
                      if m == b'@SFA' and struct.unpack('>6H3I', d[p+8:p+8+24])[3] == 0)
    dur = 258 * 1001 / 30000

    # pass 1: emit with original seek table (unchanged size), record chunk offsets
    out = bytearray()
    chunk_pos = {}
    vk = 0
    for kind, (p, m, s) in items:
        if kind == 'sfvdata':
            chunk_pos[vk] = len(out)
            out += m + struct.pack('>I', 24 + len(frames[vk])) + d[p+8:p+8+24] + frames[vk]
            vk += 1
        else:
            out += d[p:p+8+s]
    assert vk == 258
    total = len(out)

    # locate the VIDEO_SEEKINFO chunk (kind-3 @SFV) in the emitted stream:
    # sizes of data chunks changed, so walk the new layout in lockstep
    pos_acc = 0
    seek_chunk_abs = None
    vk = 0
    for kind, (p, m, s) in items:
        if kind == 'seek':
            seek_chunk_abs = pos_acc
            break
        if kind == 'sfvdata':
            pos_acc += 8 + 24 + len(frames[vk])
            vk += 1
        else:
            pos_acc += 8 + s
    assert seek_chunk_abs is not None

    # pass 2: patch VIDEO_SEEKINFO ofs_byte values in the emitted stream
    # seekinfo chunk = magic@seek_chunk_abs, table rows at +8(chunk hdr) +24(pre) +0x38
    base = seek_chunk_abs + 8 + 24 + 0x38
    for i in range(20):
        frm = i * 13
        assert frm in chunk_pos, frm
        struct.pack_into('>I', out, base + i * 12 + 4, chunk_pos[frm])
    # sanity: seek rows must point at '@SFV' magics
    for i in range(20):
        assert out[chunk_pos[i*13]:chunk_pos[i*13]+4] == b'@SFV'

    # patch CRID integers (search within CRID chunk only)
    crid_pos = 0  # first chunk
    crid_len = 8 + items[0][1][2]
    crid = bytearray(out[:crid_len])
    dur_q = int(round(dur))
    patches = {
        8554784: total,                                   # row0 filesize -> new total
        8057617: video_bytes,                             # '@SFV' row filesize
        int(7920252): int(total * 8 / dur),               # row0 avbps
        int(7487969): int(video_bytes * 8 / dur),         # '@SFV' row avbps
    }
    for old, new in patches.items():
        pat = struct.pack('>I', old)
        idx = crid.find(pat)
        assert idx >= 0, f'CRID value {old} not found'
        assert crid.find(pat, idx + 1) < 0, f'CRID value {old} ambiguous'
        struct.pack_into('>I', crid, idx, new)
    out[:crid_len] = crid

    pathlib.Path(out_path).write_bytes(out)
    print(f'built {out_path}: {len(out)} bytes (orig {len(d)}), video {video_bytes} B, '
          f'audio {audio_bytes} B, seek entries patched: 20')

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3])
