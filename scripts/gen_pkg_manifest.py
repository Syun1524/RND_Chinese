# -*- coding: utf-8 -*-
"""从 `成品ing/补丁包/` 实际内容重建 manifest 与文件清单。

补丁包每次改动（换图、重建启动器、更新 subs）后跑一次，两份清单才不会漂。
此前两份都是手工维护，结果累积出 7 条已删除的 `.bak` 幽灵条目和 30 条过期 size。

    python scripts/gen_pkg_manifest.py            # 重建
    python scripts/gen_pkg_manifest.py --check    # 只比对，不改
"""
import argparse
import hashlib
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PKG = os.path.join(ROOT, "成品ing", "补丁包")
MANIFEST = os.path.join(ROOT, "成品ing", "补丁包_manifest.json")
LISTING = os.path.join(ROOT, "成品ing", "补丁包_文件清单.txt")

# 这两份哈希是安装/卸载闭环的判据，必须与包内实际文件一致
HASHED = {"RNDZhLauncher.exe": "launcher_md5", "dinput8.dll": "dinput8_md5"}


def walk_pkg():
    out = {}
    for root, _dirs, files in os.walk(PKG):
        for f in files:
            p = os.path.join(root, f)
            out[os.path.relpath(p, PKG).replace("\\", "/")] = os.path.getsize(p)
    return out


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_listing():
    if not os.path.exists(LISTING):
        return {}
    out = {}
    for line in io.open(LISTING, encoding="utf-8-sig").read().splitlines()[1:]:
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and parts[0].isdigit():
            out[parts[1]] = int(parts[0])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只比对，不写入")
    args = ap.parse_args()

    disk = walk_pkg()
    if not disk:
        sys.exit("补丁包目录为空：%s" % PKG)

    man = json.load(io.open(MANIFEST, encoding="utf-8-sig"))
    lst = read_listing()

    for name, old in (("manifest", {e["path"]: e["size"] for e in man["files"]}),
                      ("文件清单", lst)):
        gone = sorted(set(old) - set(disk))
        new = sorted(set(disk) - set(old))
        drift = sorted(k for k in set(old) & set(disk) if old[k] != disk[k])
        print("%s: 记录 %d / 实际 %d" % (name, len(old), len(disk)))
        if gone:
            print("   ★ 记录了但磁盘没有（幽灵条目 %d）: %s" % (len(gone), gone[:6]))
        if new:
            print("   ★ 磁盘有但没记录（%d）: %s" % (len(new), new[:6]))
        if drift:
            print("   ★ size 过期 %d 条" % len(drift))
            for k in drift[:6]:
                print("        %-52s %d -> %d" % (k, old[k], disk[k]))

    total = sum(disk.values())
    print("\n实际: %d 文件 / %.1f MB" % (len(disk), total / 1048576))

    if args.check:
        return

    paths = sorted(disk, key=lambda s: s.encode("utf-8"))
    man_out = {
        "file_count": len(paths),
        "total_bytes": total,
        "launcher_md5": md5(os.path.join(PKG, "RNDZhLauncher.exe")),
        "dinput8_md5": md5(os.path.join(PKG, "dinput8.dll")),
        "mes_redirect": man.get("mes_redirect", "MES00+MES01 -> enscript"),
        "files": [{"path": p, "size": disk[p]} for p in paths],
    }
    with io.open(MANIFEST, "w", encoding="utf-8", newline="") as f:
        f.write(json.dumps(man_out, ensure_ascii=False, indent=2).replace("\n", "\r\n"))
    print("已写 %s" % os.path.relpath(MANIFEST, ROOT))

    head = "# 补丁包文件清单 (文件数 %d, 总 %.1f MB)\r\n" % (len(paths), total / 1048576)
    body = "".join("%9d  %s\r\n" % (disk[p], p) for p in paths)
    with io.open(LISTING, "w", encoding="utf-8", newline="") as f:
        f.write(head + body)
    print("已写 %s" % os.path.relpath(LISTING, ROOT))


if __name__ == "__main__":
    main()
