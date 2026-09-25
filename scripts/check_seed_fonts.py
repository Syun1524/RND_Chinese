# -*- coding: utf-8 -*-
"""门禁：预置字体种子必须与当前 charset 同代。

背景：补丁包 languagebarrier/fonts/ 里预置了 12 档烘焙好的中文字形图集
（font_NN.dds / outline_NN.dds）+ 索引 fontData.bin，让玩家首次进各界面
不必等待烘焙。种子的有效性由 fontData.bin 里每档存的 charsetHash 决定：

    charsetHash = FNV-1a(patchdef.base.charset)
                  再折叠 narrowQuotes / quoteWidth32 / quoteInset32
                  （TextRendering.cpp Init() 里的算法，与 loadCache() 的校验同源）

★ 为什么必须上门禁：charset 一改（加字/删字），hash 就变，运行时会判定
  「Font cache was baked from a different charset」并把整份种子丢弃重烘 ——
  玩家又回到卡顿，而**游戏不会报错、验收也不会变红**（final_accept 的 snap()
  把 fonts/ 排除在比对之外）。属于典型静默失效。

用法:
    python scripts/check_seed_fonts.py          # 校验
    python scripts/check_seed_fonts.py -v       # 附每档详情
退出码 0=通过，1=种子过期或缺失。
"""
import hashlib
import io
import json
import os
import struct
import sys

sys.stdout.reconfigure(encoding="utf-8")

WS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LB = os.path.join(WS, "成品ing", "补丁包", "languagebarrier")
FONTS = os.path.join(LB, "fonts")
PATCHDEF = os.path.join(LB, "patchdef.json")


def compute_charset_hash(charset, narrow_quotes, quote_width32, quote_inset32):
    """复刻 TextRendering.cpp Init() 的指纹算法。

    先对 charset 做 FNV-1a（逐 UTF-16 码元，含高/低位两轮），再把三个
    字形度量参数按同样方式折叠进去 —— 它们会改变烘焙出的 advance，
    却不改变 charset，所以必须进同一个指纹。
    """
    h = 2166136261
    for c in charset:
        h ^= ord(c) & 0xFFFF
        h = (h * 16777619) & 0xFFFFFFFF
        h ^= (ord(c) >> 16) & 0xFFFF
        h = (h * 16777619) & 0xFFFFFFFF
    for v in (int(narrow_quotes), quote_width32, quote_inset32):
        h ^= v & 0xFFFFFFFF
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def parse_fontdata(path):
    """解析 fontData.bin（cereal 二进制），返回 [(字号, lang, charsetHash, 字形数)]。"""
    b = open(path, "rb").read()
    off = 0
    n = struct.unpack_from("<Q", b, off)[0]
    off += 8
    out = []
    for _ in range(n):
        size = struct.unpack_from("<H", b, off)[0]; off += 2
        lang = b[off]; off += 1
        h = struct.unpack_from("<I", b, off)[0]; off += 4
        counts = []
        for _ in range(2):                      # glyphMap, outlineMap
            c = struct.unpack_from("<Q", b, off)[0]; off += 8
            off += c * 24                       # 键 uint16 + FontGlyph(22)
            counts.append(c)
        out.append((size, lang, h, counts[0], counts[1]))
    return out, (off == len(b))


def main():
    verbose = "-v" in sys.argv
    if not os.path.isdir(FONTS):
        print("★ 补丁包 fonts/ 不存在: %s" % FONTS)
        return 1
    if not os.path.exists(PATCHDEF):
        print("★ patchdef.json 不存在: %s" % PATCHDEF)
        return 1

    raw = open(PATCHDEF, "rb").read()
    base = json.loads(raw.decode("utf-8-sig"))["base"]
    charset = base["charset"]
    # 这三个键 patchdef 里没配时，用 TextRendering.h 的默认值
    nq = base.get("narrowQuotes", True)
    qw = base.get("quoteWidthPixels", 16)
    qi = base.get("quoteInsetPixels", 3)
    expect = compute_charset_hash(charset, nq, qw, qi)

    print("patchdef.json  md5 %s" % hashlib.md5(raw).hexdigest()[:16])
    print("charset        %d 字符（唯一码点 %d）" % (len(charset), len(set(charset))))
    print("度量参数       narrowQuotes=%s quoteWidth32=%d quoteInset32=%d"
          % (nq, qw, qi))
    print("期望 charsetHash = 0x%08x" % expect)

    fd = os.path.join(FONTS, "fontData.bin")
    if not os.path.exists(fd):
        print("\n★ 种子缺失：fonts/fontData.bin 不存在")
        print("  说明：补丁包未预置字体缓存，玩家会当场烘焙（功能正常，只是会卡）。")
        print("  若这是有意为之（例如刚改过 charset 待重烘），可忽略；")
        print("  否则请按 docs 的步骤重烘种子。")
        return 1

    rows, complete = parse_fontdata(fd)
    if not complete:
        print("\n★ fontData.bin 解析长度不符 —— 文件可能损坏或被截断")
        return 1

    print("\n种子：%d 档" % len(rows))
    bad_hash, bad_atlas, missing = [], [], []
    for size, lang, h, ng, no in sorted(rows):
        ok_h = (h == expect)
        if not ok_h:
            bad_hash.append(size)
        for pre in ("font_", "outline_"):
            p = os.path.join(FONTS, "%s%02d.dds" % (pre, size))
            if not os.path.exists(p):
                missing.append("%s%02d.dds" % (pre, size))
            else:
                head = open(p, "rb").read(24)
                if head[:4] != b"DDS ":
                    bad_atlas.append("%s%02d.dds 非 DDS" % (pre, size))
                else:
                    w = struct.unpack_from("<I", head, 16)[0]
                    cell = int(size * 1.33)
                    if w % cell:
                        bad_atlas.append("%s%02d.dds 宽 %d 不是 cell(%d) 整数倍"
                                         % (pre, size, w, cell))
        if verbose:
            print("   %2d  lang=%d  hash=0x%08x %s  glyph=%d/%d"
                  % (size, lang, h, "✓" if ok_h else "★", ng, no))

    print()
    if bad_hash:
        print("★ 种子已过期：%d 档的 charsetHash 与当前 charset 不符" % len(bad_hash))
        print("   档位: %s" % bad_hash)
        print("   → 运行时会判定「baked from a different charset」并整份丢弃重烘，")
        print("     玩家首次进各界面仍会卡顿。请重烘种子后重新出包。")
    if missing:
        print("★ 缺图集 %d 个: %s" % (len(missing), missing[:8]))
    if bad_atlas:
        print("★ 图集异常: %s" % bad_atlas[:8])

    ok = not (bad_hash or missing or bad_atlas)
    print("结果: %s" % ("✓ 种子与当前 charset 同代，可用"
                       if ok else "★ 未通过，见上"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
