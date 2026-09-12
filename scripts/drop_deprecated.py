# -*- coding: utf-8 -*-
"""把用户已废弃的图集从补丁包里撤下来，并归档到 `成品ing/补丁包/废弃图片/`。

用户把不要的图放在 `临时/cn/汉化好的/bg/废弃/`。其中一部分**已经上线**在补丁包里
（曾被 `fileRedirection` 重定向）。既然废弃，就**撤掉重定向** —— 游戏会显示原版图，
而不是继续发我们已经不要的汉化图。

★ 撤条目必须连 c0data.cls 一起重排：fileRedirection 存的是**数组下标**，
  删一行数组会让它后面所有下标整体前移一位，不重排就会指错文件
  （本项目出过事故：标题 UI 整个空白，索引指到了角色模型）。
  本脚本一次性重建 cls 与全部下标，并有自检。

保留：`临时/cn/汉化好的/` 顶层有的（那才是"汉化好的"成品），
      例如 `rnd_ibg058a` 虽然 `废弃/` 里也有一份，但顶层有同内容的 `重做` 版 → 保留。

    python scripts/drop_deprecated.py --dry-run
    python scripts/drop_deprecated.py
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
PKG = os.path.join(ROOT, "成品ing", "补丁包")
LB = os.path.join(PKG, "languagebarrier")
C0 = os.path.join(LB, "c0data")
ARCHIVE = os.path.join(PKG, "废弃图片")
SRC = os.path.join(ROOT, "临时", "cn", "汉化好的")
DEP = os.path.join(SRC, "bg", "废弃")


def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def top_level_hashes():
    out = set()
    for cat in ("bg", "system", "manual"):
        d = os.path.join(SRC, cat)
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            p = os.path.join(d, f)
            if os.path.isfile(p) and f.lower().endswith(".png"):
                out.add(md5(p))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cls = [l.strip() for l in io.open(os.path.join(LB, "c0data.cls"),
                                      encoding="utf-8-sig").read().splitlines() if l.strip()]
    patch = json.load(io.open(os.path.join(LB, "patchdef.json"), encoding="utf-8-sig"))
    fr = patch["base"]["fileRedirection"]
    live = {n: os.path.join(C0, n) for n in os.listdir(C0) if n.lower().endswith(".png")}
    top = top_level_hashes()

    # 归档全部废弃项；同时找出"已上线"的那些（内容 == c0data 某条目）
    dep_files = sorted(f for f in os.listdir(DEP) if f.lower().endswith(".png"))
    to_drop = {}          # c0data 名 -> 废弃源文件
    for f in dep_files:
        h = md5(os.path.join(DEP, f))
        stem = os.path.splitext(f)[0]
        base = stem[:-3] if stem.endswith("_zh") else stem
        for cand in (base + ".png", base + "_last.png"):
            if cand in live and md5(live[cand]) == h:
                # 顶层若有同内容成品，说明这个是想要的那份 → 不撤
                if h in top:
                    print("  保留（顶层有同内容成品）: %s" % cand)
                else:
                    to_drop[cand] = f
                break

    print("\n将从补丁包撤下的条目（%d）：" % len(to_drop))
    for n, f in sorted(to_drop.items()):
        which = [a for a, m in fr.items()
                 for k, v in m.items() if isinstance(v, int) and v < len(cls) and cls[v] == n]
        print("  %-26s <- 废弃/%s  （%s）" % (n, f, "/".join(which) or "未重定向"))

    # 新 cls（保序，去掉撤下的名字）
    new_cls = [n for n in cls if n not in to_drop]
    if len(new_cls) == len(cls):
        print("\n没有需要撤下的条目，改动为空")
    new_idx = {n: i for i, n in enumerate(new_cls)}

    # 重排 fileRedirection
    new_fr = {}
    dropped_entries = []
    for a, m in fr.items():
        nm = {}
        for k, v in m.items():
            if isinstance(v, int) and 0 <= v < len(cls) and cls[v] in to_drop:
                dropped_entries.append((a, k, cls[v]))
                continue
            nm[k] = new_idx[cls[v]] if isinstance(v, int) and 0 <= v < len(cls) else v
        if nm:
            new_fr[a] = nm
    # 保序
    patch["base"]["fileRedirection"] = {a: new_fr[a] for a in fr if a in new_fr}

    print("\ncls: %d -> %d 行；删掉的重定向 %d 条" % (len(cls), len(new_cls), len(dropped_entries)))
    for a, k, n in dropped_entries:
        print("    - %s/%s -> %s" % (a, k, n))

    # 自检：重排后每条下标都指向同一个名字
    bad = []
    for a, m in patch["base"]["fileRedirection"].items():
        for k, v in m.items():
            oldname = None
            # 原下标在旧表里的名字，应当与新表指向的名字一致
            oldv = fr[a][k]
            oldname = cls[oldv] if isinstance(oldv, int) and oldv < len(cls) else None
            if oldname and new_cls[v] != oldname:
                bad.append((a, k, oldname, new_cls[v]))
    if bad:
        sys.exit("★ 重排自检失败：%s" % bad[:5])
    print("重排自检：每条下标仍指向原名 ✓")

    if args.dry_run:
        print("\n[dry-run] 未写入")
        return

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = os.path.join(ROOT, "成品ing", "_backup", "drop_deprecated_%s" % stamp)
    os.makedirs(bak, exist_ok=True)
    for n in (os.path.join(LB, "c0data.cls"), os.path.join(LB, "patchdef.json")):
        shutil.copy2(n, os.path.join(bak, os.path.basename(n)))

    # 归档：全部废弃项（含未上线的），已在归档里的跳过
    os.makedirs(ARCHIVE, exist_ok=True)
    n_arch = 0
    for f in dep_files:
        dst = os.path.join(ARCHIVE, f)
        if not os.path.exists(dst):
            shutil.copy2(os.path.join(DEP, f), dst)
            n_arch += 1
    print("\n归档 %d 个废弃图 -> %s（共 %d 个）"
          % (n_arch, os.path.relpath(ARCHIVE, ROOT), len(os.listdir(ARCHIVE))))

    # 撤下的 c0data 文件移到归档（同名）。内容已在归档里的就不再放一份 ——
    # 曾经因此产生 10 个「同内容、不同名」的重复（movie_dar005b_zh.png 与
    # movie_dar005b_last.png），把归档撑成两倍。
    archived_hashes = {}
    for f in os.listdir(ARCHIVE):
        p = os.path.join(ARCHIVE, f)
        if os.path.isfile(p) and f.lower().endswith(".png"):
            archived_hashes.setdefault(md5(p), []).append(f)
    dup = 0
    for n in to_drop:
        h = md5(live[n])
        if h in archived_hashes:
            os.remove(live[n])
            dup += 1
            continue
        shutil.move(live[n], os.path.join(ARCHIVE, n))
    print("撤下 c0data 文件 %d 个（其中 %d 个内容已归档，未重复存放）"
          % (len(to_drop), dup))

    # 同步撤掉"镜像"里的对应图（图片汉化/）
    mirror_removed = []
    for f in os.listdir(os.path.join(ROOT, "成品ing", "图片汉化", "bg")):
        stem = os.path.splitext(f)[0]
        base = stem[:-3] if stem.endswith("_zh") else stem
        for cand in (base + ".png", base + "_last.png"):
            if cand in to_drop:
                os.remove(os.path.join(ROOT, "成品ing", "图片汉化", "bg", f))
                mirror_removed.append(f)
                break
    if mirror_removed:
        print("镜像里同步撤下:", mirror_removed)

    # 落盘
    io.open(os.path.join(LB, "c0data.cls"), "w", encoding="utf-8", newline="").write(
        "\r\n".join(new_cls) + "\r\n")
    io.open(os.path.join(LB, "patchdef.json"), "w", encoding="utf-8", newline="").write(
        json.dumps(patch, ensure_ascii=False, indent=2).replace("\n", "\r\n") + "\r\n")
    print("\n已落盘 c0data.cls + patchdef.json；备份 %s" % os.path.relpath(bak, ROOT))


if __name__ == "__main__":
    main()
