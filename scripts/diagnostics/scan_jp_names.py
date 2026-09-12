# -*- coding: utf-8 -*-
"""统计补丁里残留的日文说话人名 —— 给「名字待译清单.md」复查用。

背景：游戏的名字框（`[name]` 字段）里有一部分仍是日文，玩家会直接看到
（如 `あき穂`、`ミスター・プレアデス`）。译名要用户拍板，但**有多少处、在哪些文件**
必须可复查 —— 否则清单里的数字没法验证，改完也不知道有没有漏。

做法：解码 enscript/*.msb，逐条搜名字。
    enscript 是 LanguageBarrier 的文本归档：头部 <uint32 n> 条数、
    <uint32 base> 大字区起始偏移；每条 8 字节（sid, offset）。
    文本从 base+offset 开始，两字节一个大字：((b0 & 0x7F) << 8) | b1，
    查 patchdef.json 的 charset 得到字符，0xFF 结束。
    （半角 ASCII 直接跳过 —— 本项目的 enscript 只存大字。）

用法:
    python scripts/diagnostics/scan_jp_names.py            # 扫清单里的名字
    python scripts/diagnostics/scan_jp_names.py あき穂 フラウ   # 扫指定名字
"""
import io
import json
import os
import struct
import sys

sys.stdout.reconfigure(encoding="utf-8")

WS = r"D:\DATA\tran\agent tran\9.6文本外工作"
LB = os.path.join(WS, "成品ing", "补丁包", "languagebarrier")
LIST = os.path.join(WS, "名字待译清单.md")

# 清单里点名的那批（与 名字待译清单.md 同步）
DEFAULT = [
    "あき穂", "フラウ", "女の子", "みさ希", "アイリィ", "祭り客たち",
    "ミスター・プレアデス", "島の老婆", "スバル", "メイド喫茶店长", "アナウンサー",
    "ミス・ヒアデス", "キャスターＡ", "ロボ部員たち", "ゲンキ", "ガキンチョ",
    "祭り游客Ａ", "カメラマン", "会場アナウンス", "ジュウベェ", "ベニィ",
    "タネガシマン", "ふよう", "子ども", "ロゼッタ", "弟たち", "ガキンチョたち",
    "プリースト４", "祭り游客Ｂ", "メイド喫茶游客Ａ", "メイド喫茶游客Ｂ", "ロボ部員達",
    "秋穗&ミスター・プレアデス", "至&あき穂", "海翔&あき穂",
]


def load_charset():
    p = os.path.join(LB, "patchdef.json")
    with io.open(p, encoding="utf-8-sig") as f:
        return json.load(f)["base"]["charset"]


def decode(path, cs):
    """返回 [(sid, text)]"""
    d = open(path, "rb").read()
    if len(d) < 0x18:
        return []
    n = struct.unpack_from("<I", d, 8)[0]
    base = struct.unpack_from("<I", d, 12)[0]
    out = []
    for k in range(n):
        e = 0x18 + k * 8
        if e + 8 > len(d):
            break
        sid, off = struct.unpack_from("<II", d, e)
        i, s = base + off, []
        while i < len(d) and d[i] != 0xFF:
            if d[i] < 0x80:
                i += 1
                continue
            if i + 1 >= len(d):
                break
            g = ((d[i] & 0x7F) << 8) | d[i + 1]
            s.append(cs[g] if g < len(cs) else "")
            i += 2
        out.append((sid, "".join(s)))
    return out


def main():
    names = sys.argv[1:] or DEFAULT
    d = os.path.join(LB, "enscript")
    if not os.path.isdir(d):
        sys.exit("找不到 enscript 目录: %s" % d)
    cs = load_charset()
    files = [f for f in sorted(os.listdir(d)) if f.endswith(".msb")]

    hits = {}
    for f in files:
        try:
            for sid, t in decode(os.path.join(d, f), cs):
                for q in names:
                    if q in t:
                        hits.setdefault(q, []).append((f, sid, t))
        except Exception:
            pass

    print("扫描 %d 个 enscript 文件，查找 %d 个名字" % (len(files), len(names)))
    print()
    print("%-24s %-6s %s" % ("日文名", "处数", "示例（文件 / sid / 上下文）"))
    print("-" * 100)
    total = 0
    for q in names:
        h = hits.get(q, [])
        total += len(h)
        if not h:
            continue
        f, sid, t = h[0]
        # 截取命中位置附近，便于确认不是误报
        i = t.find(q)
        ctx = t[max(0, i - 8): i + len(q) + 12].replace("\n", " ")
        print("%-24s %-6d %s / sid=%d / …%s…" % (q, len(h), f, sid, ctx))
    print()
    missing = [q for q in names if not hits.get(q)]
    print("合计 %d 处；命中 %d / %d 个名字"
          % (total, len(names) - len(missing), len(names)))
    if missing:
        print("清单里有、实际未命中（可能已译或写法不同）：%s" % "、".join(missing))


if __name__ == "__main__":
    main()
