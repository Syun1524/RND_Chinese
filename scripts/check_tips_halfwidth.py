# -*- coding: utf-8 -*-
"""门禁：`_tips_00.msb` 必须保持「半角标点」版（用户 2026-10-09 拍板）。

背景：
  TIPS 词条表 `_tips_00.msb` 是**唯一**被整体半角化的文件（322 个部署文件里
  只有它半角为主，其余 321 个全角为主）。它在 v1.5→v1.6 之间被换成半角版，
  此后 v1.6/1.7/1.8/1.9/2.0.1 **六版一致**（`4def0caa55f8ea91`），属稳定既成事实。

  ⚠ 而**校对源是全角的**（`文本复校/rnd文本汉化校对v*/_tips_00.msb.json`
  里 `，`498 / `（`123 / `）`124）。所以**拿源重编会把它翻回全角** ——
  2026-10-09 那轮 183 个文件整批编译时它就跟着变了（`995434dd`），
  当时靠人工比对才发现、只部署了真正要改的 `_mail_00`。

  用户裁定（2026-10-09）：「保留她半角吧 不管了」——即**以部署版为准**，
  不追平全角、也不改源。

本门禁检查两件事：
  A. 补丁包里的 `_tips_00.msb` 仍是半角版（标点计数符合预期、且不等于全角版）；
  B. 若补丁包旁边存在「从源编出来的全角版」痕迹（临时文件），给出提示 ——
     真正的用途是：任何人重编后跑本门禁，会立刻看到自己把 tips 翻回全角了。

用法：
    python scripts/check_tips_halfwidth.py
    python scripts/check_tips_halfwidth.py --file <某个 .msb>   # 检查任意一份
"""
import argparse
import io
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def _resolve(rel_candidates):
    """本脚本在工作区与仓库各有一份，两处相对层级不同，逐个候选试。"""
    for rel in rel_candidates:
        p = os.path.normpath(os.path.join(HERE, rel))
        if os.path.exists(p):
            return p
    return os.path.normpath(os.path.join(HERE, rel_candidates[0]))


PKG_TIPS = _resolve(["../成品ing/补丁包/languagebarrier/enscript/_tips_00.msb",
                     "../../9.6文本外工作/成品ing/补丁包/languagebarrier/enscript/_tips_00.msb",
                     "../../../9.6文本外工作/成品ing/补丁包/languagebarrier/enscript/_tips_00.msb"])
CHARSET = _resolve(["../GitHub/RND_Chinese/sc3tools_chs/resources/rndzh/charset.utf8",
                    "../../GitHub/RND_Chinese/sc3tools_chs/resources/rndzh/charset.utf8",
                    "../sc3tools_chs/resources/rndzh/charset.utf8"])

# 已发布的半角版指纹（v1.6 起六版一致）
KNOWN_HALFWIDTH_MD5 = "4def0caa55f8ea91"
# 从源编出来的全角版指纹（2026-10-09 实测）
KNOWN_FULLWIDTH_MD5 = "5d9081c49dc5abc0"


def walk_to_end(d, start):
    """按 token 走到 0x03 收尾（0xFF 是合法字形低字节，不能当终止符扫）。"""
    i = start
    L = len(d)
    while i < L:
        b = d[i]
        if b == 0xFF:
            return d[start:i]
        if b >= 0x80:
            if i + 1 >= L:
                return d[start:i]
            i += 2
        elif b == 4:
            j = i + 1
            while j < L and d[j] != 0:
                j += 1
            i = j + 1
        else:
            i += 1
            if b == 0x03:
                return d[start:i - 1]
    return d[start:L]


def decode_all(path):
    cs = io.open(CHARSET, encoding="utf-8").read()
    d = open(path, "rb").read()
    n = struct.unpack_from("<I", d, 8)[0]
    base = struct.unpack_from("<I", d, 12)[0]
    out = []
    for k in range(n):
        sid, off = struct.unpack_from("<II", d, 0x18 + k * 8)
        raw = walk_to_end(d, base + off)
        s = []
        i = 0
        L = len(raw)
        while i < L:
            b = raw[i]
            if b >= 0x80:
                if i + 1 >= L:
                    break
                g = ((b & 0x7F) << 8) | raw[i + 1]
                s.append(cs[g] if g < len(cs) else "?")
                i += 2
            elif b == 4:
                i += 1
                while i < L and raw[i] != 0:
                    i += 1
                i += 1
            else:
                i += 1
        out.append((sid, "".join(s)))
    return out


def md5f(p):
    import hashlib
    return hashlib.md5(open(p, "rb").read()).hexdigest()


def check(path):
    errs, notes = [], []
    if not os.path.exists(path):
        return ["文件不存在: %s" % path], []
    h = md5f(path)
    # 常量是 16 位前缀，比较必须截断（直接比 32 位永远不等 —— 这里踩过一次）
    h16 = h[:16]
    text = "".join(t for _, t in decode_all(path))
    fw_c, hw_c = text.count("，"), text.count(",")
    fw_p = text.count("（") + text.count("）")
    hw_p = text.count("(") + text.count(")")

    if h16 == KNOWN_FULLWIDTH_MD5:
        errs.append("这是**从源编出来的全角版**（%s）—— 会把 TIPS 标点翻回全角，"
                    "不要部署。用户已裁定保持半角。" % h16)
    elif hw_c == 0 and fw_c > 0:
        errs.append("标点是全角为主（全角 ，=%d / 半角 ,=%d）—— 应为半角版。"
                    "若你刚重编过，请勿部署这个文件。" % (fw_c, hw_c))
    elif hw_c < fw_c:
        errs.append("半角标点少于全角（全角 ，=%d / 半角 ,=%d）—— 疑似被翻回全角。"
                    % (fw_c, hw_c))
    else:
        notes.append("半角版正常（全角 ，=%d / 半角 ,=%d / 全角（）=%d / 半角()=%d）"
                     % (fw_c, hw_c, fw_p, hw_p))

    if not errs:
        if h16 == KNOWN_HALFWIDTH_MD5:
            notes.append("md5 与已发布的半角版一致（%s）" % h[:16])
        else:
            notes.append("md5=%s（与已知发布版 %s 不同，但标点形态正确 —— "
                         "可能是有意的文本修订，请自行确认）"
                         % (h16, KNOWN_HALFWIDTH_MD5))
    return errs, notes

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", action="append", default=None,
                    help="检查指定文件（可多次）；默认检查补丁包里的 _tips_00.msb")
    args = ap.parse_args()

    targets = args.file or [PKG_TIPS]
    all_errs = []
    print("=== _tips_00 半角标点门禁 ===")
    for t in targets:
        errs, notes = check(t)
        print("  %s" % os.path.relpath(t, ROOT))
        for n in notes:
            print("     · %s" % n)
        for e in errs:
            print("     ★ %s" % e)
        all_errs += errs

    if all_errs:
        print("\nRESULT: FAIL（%d 项）" % len(all_errs))
        return 1
    print("\nRESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
