# -*- coding: utf-8 -*-
"""Install translated `manual` / `system` atlases into a LanguageBarrier patch.

Same mechanism as apply_bg_redirect.py: every file in `languagebarrier/c0data/`
is one archive entry addressed by its 0-based line index in `c0data.cls`, and
`patchdef.json -> base.fileRedirection[<archive>][<fileId>] = <c0data index>`
redirects the engine's open to that entry.

The fileId -> file name tables come from the CPK unpack logs; their
"Extracting <name> ..." order is the CPK fileId order (checked against the
file ids the CoZ patch already maps).

`manual` and `system` share the same control_pc / keyboard_pc images (the
originals are byte-identical), and the CoZ patch therefore points both
archives at the same c0data slots. Reusing the existing slot keeps that
relationship intact: one content overwrite serves both archives. The c0data
entry keeps the plain name (`control_pc.png`, matching the source image), and
system/33, system/35 are redirected onto it -- see scripts/rename_guide_atlases.py.

Idempotent and formatting-preserving (UTF-8 no BOM, CRLF, indent=2).
"""
import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime

# (archive, staged file relative to --staged, original archive file name)
SPEC = [
    ("manual", "control_pc_zh.png",   "control_pc.png"),
    ("manual", "keyboard_pc_zh.png",  "keyboard_pc.png"),
    ("system", "ar_chip_zh.png",      "ar_chip.png"),
    ("system", "ar_chip3_zh.png",     "ar_chip3.png"),
    ("system", "button_zh.png",       "button.png"),
    ("system", "data01_zh.png",       "data01.png"),
    ("system", "extra_chip_zh.png",   "extra_chip.png"),
    ("system", "guid_pc_zh.png",      "guid_pc_jp.png"),
    ("system", "option_pc_zh.png",    "option_pc.png"),
    ("system", "sysmenu_pc_zh.png",   "sysmenu_pc.png"),
]


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True)
    ap.add_argument("--staged", required=True, help=".../临时/cn/汉化好的")
    ap.add_argument("--unpacked", required=True, help=".../解包/解包cpk的产物(日语)")
    ap.add_argument("--dry-run", action="store_true")
    return ap.parse_args()


def load_ids(log_path):
    ids = {}
    with open(log_path, encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            m = re.match(r"Extracting (.+?) \.\.\.", line.strip())
            if m:
                ids[m.group(1)] = len(ids)
    return ids


def read_bytes(p):
    with open(p, "rb") as f:
        return f.read()


def main():
    args = parse_args()
    lb = os.path.join(args.game, "languagebarrier")
    c0 = os.path.join(lb, "c0data")
    cls_path = os.path.join(lb, "c0data.cls")
    patch_path = os.path.join(lb, "patchdef.json")
    for p in (c0, cls_path, patch_path):
        if not os.path.exists(p):
            sys.exit("missing: %s" % p)

    id_tables = {
        "manual": load_ids(os.path.join(args.unpacked, "manual", "解包日志.txt")),
        "system": load_ids(os.path.join(args.unpacked, "system", "解包日志.txt")),
    }

    cls_raw = read_bytes(cls_path).decode("utf-8-sig")
    cls = [ln.strip() for ln in cls_raw.splitlines() if ln.strip()]
    patch = json.loads(read_bytes(patch_path).decode("utf-8-sig"))
    fr = patch["base"].setdefault("fileRedirection", {})

    # c0data index -> which (archive, fileId) claims it, to catch collisions
    claimed = {}
    for arch, m in fr.items():
        for fid, idx in m.items():
            if isinstance(idx, int):
                claimed.setdefault(idx, []).append("%s/%s" % (arch, fid))

    plan, copies, skipped = [], [], []
    for arch, staged_name, orig_name in SPEC:
        src = os.path.join(args.staged, arch, staged_name)
        if not os.path.exists(src):
            skipped.append((staged_name, "staged file not found"))
            continue
        fid = id_tables[arch].get(orig_name)
        if fid is None:
            skipped.append((staged_name, "no %s fileId for %r" % (arch, orig_name)))
            continue

        amap = fr.setdefault(arch, {})
        key = str(fid)
        if key in amap and isinstance(amap[key], int):
            idx = amap[key]
            target = cls[idx]
            action = "reuse"
        else:
            # avoid inventing a duplicate c0data name that another mapping owns
            if orig_name in cls:
                idx = cls.index(orig_name)
                holders = claimed.get(idx, [])
                if holders and all(not h.startswith(arch + "/") for h in holders):
                    skipped.append((staged_name,
                                    "c0data[%d]=%s already owned by %s"
                                    % (idx, orig_name, holders)))
                    continue
            else:
                idx = len(cls)
                cls.append(orig_name)
            amap[key] = idx
            claimed.setdefault(idx, []).append("%s/%s" % (arch, key))
            target = orig_name
            action = "new"
        plan.append((arch, staged_name, orig_name, fid, idx, target, action))

    print("c0data.cls: %d -> %d lines" % (len(cls_raw.splitlines()), len(cls)))
    print("\n%-8s %-22s %-24s %6s %5s %-6s %s"
          % ("archive", "staged", "original", "fileId", "idx", "action", "c0data file"))
    for arch, sf, of, fid, idx, tn, act in plan:
        print("%-8s %-22s %-24s %6d %5d %-6s %s" % (arch, sf, of, fid, idx, act, tn))
    if skipped:
        print("\nskipped:")
        for n, why in skipped:
            print("  %-30s %s" % (n, why))

    if args.dry_run:
        print("\n[dry-run] nothing written")
        return

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for p in (cls_path, patch_path):
        shutil.copy2(p, "%s.bak_uiredir_%s" % (p, stamp))
    print("\nbacked up c0data.cls / patchdef.json with suffix .bak_uiredir_%s" % stamp)

    changed = 0
    for arch, sf, of, fid, idx, tn, act in plan:
        src = os.path.join(args.staged, arch, sf)
        dst = os.path.join(c0, tn)
        old = read_bytes(dst) if os.path.exists(dst) else None
        if old != read_bytes(src):
            shutil.copy2(src, dst)
            changed += 1
    print("c0data files written: %d changed / %d total" % (changed, len(plan)))

    out = json.dumps(patch, ensure_ascii=False, indent=2).replace("\n", "\r\n")
    with open(patch_path, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    with open(cls_path, "w", encoding="utf-8", newline="") as f:
        f.write("\r\n".join(cls) + "\r\n")
    print("updated patchdef.json and c0data.cls")


if __name__ == "__main__":
    main()
