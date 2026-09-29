# -*- coding: utf-8 -*-
"""去掉补丁包 c0data 里的重复图：control_pc.png / keyboard_pc.png。

背景
----
日文原版 `system.cpk` 与 `manual.cpk` 里，同一张操作说明图各存了一份
（`control_pc.png` / `RND_PC_controller_jp.png` 逐字节相同，键盘同理）。
CoZ 上游让两个归档**指向同一个 c0data 槽位**（`system/33` 与 `manual/0` 都指
`control_pc_en.png`），也就是「一张图、两条路径」。

我们这边 `rebuild_c0data.py` 的去重是按「归档里的**原始文件名**」做的，而两个
归档里同一张图**名字不同**（system 叫 `control_pc.png`，manual 叫
`RND_PC_controller_jp.png`），所以没认出来、留成了两份。

★ 为什么必须去掉：`sync_images.py` 的同步源是 `临时/cn/汉化好的/manual/`，
它的别名表只把源图映射到 `RND_PC_*`，**从不写 `control_pc.png`** ——
那份是**孤儿副本**。现在两份内容恰好相同所以看不出问题，一旦改图，
`system/33` 这条路径就会静默停在旧图上（同 2026-09-25 extra_chip 那次漏同步）。

★ 为什么不能「直接删两行」：`fileRedirection` 存的是**数组下标**，不是文件名。
删掉 cls 里两行，后面所有下标整体前移 2 位，不重编号就会指错文件
（本项目出过「标题 UI 全白」事故：索引指到了角色模型）。所以本脚本
**重建 cls + 重写全部受影响下标**，并且每处替换都要求「旧串在全文里唯一命中」。

用法
----
    python scripts/dedup_guide_images.py --dry-run    # 只看计划
    python scripts/dedup_guide_images.py              # 执行（先备份）
"""
import argparse
import datetime
import hashlib
import io
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PKG = os.path.join(ROOT, "成品ing", "补丁包", "languagebarrier")
CLS = os.path.join(PKG, "c0data.cls")
PATCH = os.path.join(PKG, "patchdef.json")
C0 = os.path.join(PKG, "c0data")

# 要删的 c0data 条目（孤儿副本）；保留 RND_PC_* 那份，因为它是同步管线的目标
DROP = ["control_pc.png", "keyboard_pc.png"]

# 被删条目 -> 改指到哪一份（去重后两个归档共享同一份）
#   system/33 原指 control_pc.png，改指 manual/0 用的 RND_PC_controller_jp.png
RETARGET = {"control_pc.png": "RND_PC_controller_jp.png",
            "keyboard_pc.png": "RND_PC_keyboard_jp.png"}

# 两个归档必须指向同一条目（去重后）
MUST_SHARE = [("system", "33", "manual", "0"), ("system", "35", "manual", "1")]


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    raw_cls = io.open(CLS, encoding="utf-8-sig").read()
    cls = [l.strip() for l in raw_cls.splitlines() if l.strip()]
    raw_patch = open(PATCH, "rb").read().decode("utf-8-sig")

    # ---------- 前置校验：要删的确实存在，且确实是重复内容 ----------
    print("=== 前置校验 ===")
    for name in DROP:
        if name not in cls:
            sys.exit("★ %s 不在 c0data.cls 里，脚本前提已变" % name)
        twin = {"control_pc.png": "RND_PC_controller_jp.png",
                "keyboard_pc.png": "RND_PC_keyboard_jp.png"}[name]
        if twin not in cls:
            sys.exit("★ 保留项 %s 不在 cls 里" % twin)
        a, b = os.path.join(C0, name), os.path.join(C0, twin)
        if not (os.path.exists(a) and os.path.exists(b)):
            sys.exit("★ 文件缺失：%s / %s" % (a, b))
        ha, hb = md5(a), md5(b)
        same = "内容相同 ✓" if ha == hb else "★ 内容不同！"
        print("  %-26s %s  vs  %-26s %s   %s" % (name, ha[:16], twin, hb[:16], same))
        if ha != hb:
            sys.exit("★ 两份内容不同，不能当作重复项删除")

    # ---------- 计算新 cls 与下标映射 ----------
    new_cls = [n for n in cls if n not in DROP]
    print("\n=== cls: %d -> %d 行（删 %s）===" % (len(cls), len(new_cls), ", ".join(DROP)))

    def new_index(name):
        return new_cls.index(name)

    # 旧下标 -> 新下标。被删条目的旧下标**不映射**（指向它的必须先改指，
    # 否则下面 remap[old] 会 KeyError —— 那是刻意的硬失败，不要吞掉）。
    remap = {}
    for i, n in enumerate(cls):
        if n in DROP:
            continue
        remap[i] = new_index(n)

    # 被删条目的旧下标 -> 目标条目的新下标（供改指用）
    retarget_idx = {}
    for i, n in enumerate(cls):
        if n in DROP:
            retarget_idx[i] = new_index(RETARGET[n])

    # ---------- 重写 patchdef：字符串级替换，保持原格式 ----------
    # 解析出 fileRedirection 段，逐条算出旧值/新值，再生成 (旧串, 新串) 对
    patch = json.loads(raw_patch)
    fr = patch["base"]["fileRedirection"]

    print("\n=== fileRedirection 改动计划 ===")
    edits = []          # (arch, fileId, lang, old_idx, new_idx, old_line, new_line)

    def resolve(arch, fid, old):
        """旧下标 -> 新下标；指向被删条目的改指到保留的那一份。

        ⚠ DROP 里存的是**文件名**，这里比的是**下标** —— 用 cls[old] 判。
        """
        if cls[old] in DROP:
            return retarget_idx[old]
        return remap[old]

    for arch, m in fr.items():
        for fid, val in m.items():
            if isinstance(val, dict):        # 语言条件形式 {"jp": n, "en": n}
                nv = {}
                changed = False
                for lang, old in val.items():
                    new = resolve(arch, fid, old)
                    nv[lang] = new
                    if new != old:
                        changed = True
                if changed:
                    old_line = '        "%s": { "jp": %d, "en": %d },' % (
                        fid, val["jp"], val["en"])
                    new_line = '        "%s": { "jp": %d, "en": %d },' % (
                        fid, nv["jp"], nv["en"])
                    edits.append((arch, fid, None, val["jp"], nv["jp"],
                                  old_line, new_line))
            else:
                old = val
                new = resolve(arch, fid, old)
                if new != old:
                    # 行尾逗号：段内最后一项没有逗号，靠“旧串是否唯一”兜底
                    for tail in (",", ""):
                        cand = '        "%s": %d%s' % (fid, old, tail)
                        if raw_patch.count(cand) == 1:
                            edits.append((arch, fid, None, old, new, cand,
                                          '        "%s": %d%s' % (fid, new, tail)))
                            break
                    else:
                        sys.exit("★ 无法唯一匹配 %s/%s 的行" % (arch, fid))

    # 唯一性断言：每处替换必须恰好命中一次，且改完不能有残留旧串
    bad = [(e[0], e[1]) for e in edits if raw_patch.count(e[5]) != 1]
    if bad:
        sys.exit("★ 以下替换串在 patchdef.json 里不唯一：%s" % bad)
    for e in edits:
        print("  %-8s %-4s %-4s %2d -> %2d   %s"
              % (e[0], e[1], e[2] or "", e[3], e[4], e[5].strip()))

    # ---------- 输出新内容 ----------
    new_patch = raw_patch
    for e in edits:
        new_patch = new_patch.replace(e[5], e[6])

    # 校验：解析得通、且没有任何值越界
    np = json.loads(new_patch)
    for arch, m in np["base"]["fileRedirection"].items():
        for fid, val in m.items():
            vals = list(val.values()) if isinstance(val, dict) else [val]
            for v in vals:
                if not (0 <= v < len(new_cls)):
                    sys.exit("★ 改后 %s/%s = %d 越界（cls 只有 %d 行）"
                             % (arch, fid, v, len(new_cls)))

    # ---------- 必须共享：两个归档指向同一条目 ----------
    print("\n=== 去重后「两个归档共享一条目」校验 ===")
    nfr = np["base"]["fileRedirection"]
    for a1, f1, a2, f2 in MUST_SHARE:
        v1, v2 = nfr[a1][f1], nfr[a2][f2]
        ok = (v1 == v2)
        print("  %s/%-3s -> [%d] %-26s | %s/%-3s -> [%d] %s  %s"
              % (a1, f1, v1, new_cls[v1], a2, f2, v2, new_cls[v2],
                 "✓ 同一份" if ok else "★ 不一致"))
        if not ok:
            sys.exit("★ 两个归档没有指向同一份，去重不成立")

    # ---------- 写入 ----------
    if args.dry_run:
        print("\n[dry-run] 未写入")
        return

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = os.path.join(ROOT, "成品ing", "_backup", "dedup_guides_%s" % stamp)
    os.makedirs(bak, exist_ok=True)
    shutil.copy2(CLS, bak)
    shutil.copy2(PATCH, bak)
    for name in DROP:
        shutil.copy2(os.path.join(C0, name), bak)
    print("\n备份 -> %s" % bak)

    # cls：保持 CRLF、无 BOM
    with open(CLS, "w", encoding="utf-8", newline="") as f:
        f.write("\r\n".join(new_cls) + "\r\n")
    # patchdef：保持 UTF-8 无 BOM + CRLF
    with open(PATCH, "w", encoding="utf-8", newline="") as f:
        f.write(new_patch)
    for name in DROP:
        os.remove(os.path.join(C0, name))
        print("  已删除 c0data/%s" % name)

    print("\n=== 写后复核 ===")
    after_cls = [l.strip() for l in io.open(CLS, encoding="utf-8-sig").read().splitlines() if l.strip()]
    after_patch = json.load(io.open(PATCH, encoding="utf-8-sig"))
    print("  cls 行数: %d" % len(after_cls))
    for name in DROP:
        print("  %-26s 在 cls: %-5s 在磁盘: %s"
              % (name, name in after_cls, os.path.exists(os.path.join(C0, name))))
    afr = after_patch["base"]["fileRedirection"]
    for a1, f1, a2, f2 in MUST_SHARE:
        print("  %s/%s=%d  %s/%s=%d  %s"
              % (a1, f1, afr[a1][f1], a2, f2, afr[a2][f2],
                 "✓" if afr[a1][f1] == afr[a2][f2] else "★"))
    print("\n完成。")


if __name__ == "__main__":
    main()
