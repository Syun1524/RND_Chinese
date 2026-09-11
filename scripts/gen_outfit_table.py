# -*- coding: utf-8 -*-
"""Emit launcher/outfit_table.h from 成品ing/服装映射表.json.

The launcher needs the character -> variant -> fileId table to drive its 换装核对
dropdowns. Embedding it as a generated header keeps the shipped launcher a single
self-contained exe (no extra json to lose), and regenerating is a one-liner.

    python scripts/gen_outfit_table.py
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MAXV = 12   # c002/c004 top out at 10 variants; keep headroom


def main():
    mapping = json.load(io.open(os.path.join(ROOT, "成品ing", "服装映射表.json"),
                                encoding="utf-8"))
    chs = sorted(mapping)
    for ch in chs:
        if len(mapping[ch]) > MAXV:
            sys.exit("%s 有 %d 个变体，超过 MAXV=%d" % (ch, len(mapping[ch]), MAXV))

    L = []
    L.append("// 自动生成，勿手改 —— 由 scripts/gen_outfit_table.py 从")
    L.append("// 成品ing/服装映射表.json 生成。改映射请改 json 后重跑该脚本。")
    L.append("//")
    L.append("// 用途：启动器「换装核对」下拉框。choice id = \"c002_100\" 形式，对应")
    L.append("// patchdef.json -> settings.zzOutfitOverride.choices[<id>]。")
    L.append("#pragma once")
    L.append("")
    L.append("struct OutfitChar { const wchar_t* id; int count;")
    L.append("                    const wchar_t* variant[%d]; int fileId[%d]; };" % (MAXV, MAXV))
    L.append("")
    L.append("static const OutfitChar OUTFIT_CHARS[] = {")
    for ch in chs:
        es = sorted(mapping[ch], key=lambda e: e["variant"])
        vs = ", ".join('L"%s"' % e["variant"] for e in es)
        fs = ", ".join(str(e["fileId"]) for e in es)
        L.append("  { L\"%s\", %2d, { %s }, { %s } }," % (ch, len(es), vs, fs))
    L.append("};")
    L.append("static const int OUTFIT_CHAR_COUNT = %d;" % len(chs))
    L.append("")
    multi = sum(len(mapping[c]) for c in chs if len(mapping[c]) > 1)
    L.append("// 需要核对的项数 = %d（%d 个角色）。单变体角色无其它服装可切，不列入。"
             % (multi, sum(1 for c in chs if len(mapping[c]) > 1)))
    L.append("static const int OUTFIT_VERIFY_COUNT = %d;" % multi)

    out = os.path.join(ROOT, "launcher", "outfit_table.h")
    io.open(out, "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
    print("已写入 %s" % out)
    print("  %d 个角色 / %d 个需核对变体" % (len(chs), multi))


if __name__ == "__main__":
    main()
