# -*- coding: utf-8 -*-
"""Clean a working copy back to its pristine master EXACTLY, then verify.

The reason a plain "uninstall" is not enough for testing: the uninstaller restores from
its own backup, and if that backup was taken while the folder was already dirty (e.g. an
earlier aborted test), the restored state inherits the dirt. For a trustworthy lifecycle
test we therefore start from a byte-exact copy of the untouched master.

Copy source: the master folder (no patch traces). Only safe to run when the game is not
running and no installer is holding handles.
"""
import hashlib
import os
import shutil
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

MASTER = r"D:/Ruanjian/Steam/steamapps/common/ROBOTICS;NOTES DaSH -原版英文 副本"
TARGET = r"D:/Ruanjian/Steam/steamapps/common/RND_DaSH_en_copy"
KILLER = r"D:/DATA/tran/agent tran/9.6文本外工作/tmp_128/rndkill.exe"
OUT = r"D:/DATA/tran/agent tran/9.6文本外工作/tmp_128/rndkill_out.txt"

SKIP_DIRS = {"fonts"}


def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def files(root):
    out = {}
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in fns:
            p = os.path.join(dp, fn)
            try:
                out[os.path.relpath(p, root).replace("\\", "/")] = (
                    os.path.getsize(p), md5(p))
            except OSError:
                pass
    return out


def kill_elevated():
    if os.path.exists(OUT):
        os.remove(OUT)
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "$p=Start-Process -FilePath '%s' -Verb RunAs -PassThru "
                    "-WindowStyle Hidden;"
                    "$p|Wait-Process -Timeout 60 -EA SilentlyContinue"
                    % KILLER.replace("/", "\\")], capture_output=True)
    time.sleep(2)
    subprocess.run(["taskkill", "/F", "/IM", "Game.exe"], capture_output=True)


print("=== 1) 杀掉所有会锁文件的进程 ===")
kill_elevated()
if os.path.exists(OUT):
    print(open(OUT, encoding="utf-8-sig").read().strip())

print("\n=== 2) 用母本重建目标目录（先删后拷）===")
# 删除（可能需要提权：先把能删的删掉，剩下的报告出来）
def rmtree_force(p):
    try:
        shutil.rmtree(p)
        return True
    except Exception:
        pass
    # 提权删除：借 rndkill 的同款机制不方便，改用 attrib + 逐个删除
    for dp, dns, fns in os.walk(p, topdown=False):
        for fn in fns:
            try:
                os.chmod(os.path.join(dp, fn), 0o777)
                os.remove(os.path.join(dp, fn))
            except OSError:
                pass
        try:
            os.rmdir(dp)
        except OSError:
            pass
    return not os.path.exists(p)


if os.path.isdir(TARGET):
    ok = rmtree_force(TARGET)
    print("   删除旧目录: %s" % ("成功" if ok else "★仍有残留"))
    if not ok:
        print("   (残留文件需提权，请手动清理后重跑)")
        sys.exit(1)

shutil.copytree(MASTER, TARGET)
print("   已从母本复制")

print("\n=== 3) 校验与母本一致 ===")
a, b = files(MASTER), files(TARGET)
extra = sorted(set(b) - set(a))
miss = sorted(set(a) - set(b))
diff = sorted(k for k in set(a) & set(b) if a[k] != b[k])
print("   母本 %d / 目标 %d" % (len(a), len(b)))
print("   多余 %d | 缺失 %d | 不同 %d" % (len(extra), len(miss), len(diff)))
for x in extra[:5]:
    print("      + %s" % x)
for x in miss[:5]:
    print("      - %s" % x)
for x in diff[:5]:
    print("      ~ %s" % x)
if extra or miss or diff:
    sys.exit("★ 复制后与母本不一致")
print("\n★ 目标目录已是纯净状态（与母本逐字节一致）")
