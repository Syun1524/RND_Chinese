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

# 角色名线索：来自 motion 文件名（`c003_070_frau@rnd_dance_5.lka`），不是猜的。
# 只用于在工具里标一下"这是谁"，方便对剧情找角色。
NAME_HINT = {
    "c002": "akiho",
    "c003": "frau",
    "c004": "junna",
    "c013": "kou",
    "c018": "daru",
}


def main():
    mapping = json.load(io.open(os.path.join(ROOT, "成品ing", "服装映射表.json"),
                                encoding="utf-8"))
    # 中文角色名（用户实测核对）优先，缺的用 motion 文件名里的罗马字兜底
    roles_p = os.path.join(ROOT, "成品ing", "服装核对", "角色名表.json")
    roles = json.load(io.open(roles_p, encoding="utf-8")) if os.path.exists(roles_p) else {}
    chs = sorted(mapping)
    for ch in chs:
        if len(mapping[ch]) > MAXV:
            sys.exit("%s 有 %d 个变体，超过 MAXV=%d" % (ch, len(mapping[ch]), MAXV))

    L = []
    L.append("// 自动生成，勿手改 —— 由 scripts/gen_outfit_table.py 从")
    L.append("// 成品ing/服装映射表.json 生成。改映射请改 json 后重跑该脚本。")
    L.append("//")
    L.append("// 用途：换装核对工具（RNDZhOutfitTool）的角色×服装表。")
    L.append("// 每行对应 patchdef.json -> settings.zz_<角色>_<变体>（bool），")
    L.append("// 工具按选择把对应的键写成 true 进 config.json。")
    L.append("#pragma once")
    L.append("")
    L.append("struct OutfitChar { const wchar_t* id; const wchar_t* hint; int count;")
    L.append("                    const wchar_t* variant[%d]; int fileId[%d]; };" % (MAXV, MAXV))
    L.append("")
    L.append("static const OutfitChar OUTFIT_CHARS[] = {")
    for ch in chs:
        es = sorted(mapping[ch], key=lambda e: e["variant"])
        vs = ", ".join('L"%s"' % e["variant"] for e in es)
        fs = ", ".join(str(e["fileId"]) for e in es)
        hint = roles.get(ch) or NAME_HINT.get(ch, "")
        L.append("  { L\"%s\", L\"%s\", %2d, { %s }, { %s } },"
                 % (ch, hint, len(es), vs, fs))
    L.append("};")
    L.append("static const int OUTFIT_CHAR_COUNT = %d;" % len(chs))
    L.append("")
    multi = sum(len(mapping[c]) for c in chs if len(mapping[c]) > 1)
    L.append("// 多变体角色数（= 核对面板里显示的行数）")
    L.append("static const int OUTFIT_MULTI_COUNT = %d;"
             % sum(1 for c in chs if len(mapping[c]) > 1))
    L.append("// 需核对的项数合计（多变体角色全部变体之和）")
    L.append("static const int OUTFIT_VERIFY_COUNT = %d;" % multi)
    L.append("// 最多变体数（决定「全体对齐第 k 套」的 k 上限）")
    L.append("static const int OUTFIT_MAX_VARIANTS = %d;"
             % max(len(mapping[c]) for c in chs))

    out = os.path.join(ROOT, "launcher", "outfit_table.h")
    io.open(out, "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
    print("已写入 %s" % out)
    print("  %d 个角色 / %d 个需核对变体" % (len(chs), multi))


if __name__ == "__main__":
    main()
