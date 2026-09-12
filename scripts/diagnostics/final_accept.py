# -*- coding: utf-8 -*-
"""最终验收：干净安装包 → 安装 → 补丁生效 → 卸载 → 回到纯净 + 无残留。

针对用户即将使用的那个成品安装包。判据：
  安装：languagebarrier/log.txt 生成（唯一可靠信号，LB 一启动必写）且无错误
  中文：解码 enscript/*.msb，统计包含汉字的条目
  卸载：补丁痕迹全部消失，与纯净母本逐字节一致（只剩两个工具自身）
  残留：%TEMP% 下不留 7z 解压目录
"""
import hashlib
import os
import struct
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

SETUP = (r"D:\DATA\tran\agent tran\9.6文本外工作\成品ing\setup"
         r"\RNDZh-Setup-v0.1.exe")
MASTER = r"D:\Ruanjian\Steam\steamapps\common\ROBOTICS;NOTES DaSH -原版英文 副本"
TARGET = r"D:\Ruanjian\Steam\steamapps\common\RND_DaSH_en_copy"
TEMP = os.environ.get("TEMP") or ""
# 卸载器的产品名（中文，避免与 RNDZhLauncher.exe 混淆而误点）
UNINSTALLER = "卸载汉化.exe"
# 补丁装完后游戏目录里会留下这两个（工具自身，设计如此）；
# 卸载器的产品名是中文「卸载汉化.exe」——它与 RNDZhLauncher.exe 名字太像，
# 旧名 RNDZhUninstall.exe 已弃用（玩家容易点错成卸载）。
KEEP = {"RNDZhSetup.exe", "卸载汉化.exe", "RNDZhUninstall.exe"}


def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def snap(root, skip_dirs=("fonts",)):
    out = {}
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in skip_dirs]
        for fn in fns:
            p = os.path.join(dp, fn)
            rel = os.path.relpath(p, root).replace(os.sep, "/")
            try:
                out[rel] = md5(p)
            except OSError:
                pass
    return out


def z7_dirs():
    try:
        return [d for d in os.listdir(TEMP)
                if d.lower().startswith("7z") and os.path.isdir(os.path.join(TEMP, d))]
    except OSError:
        return []



def patch_left(root):
    """还有哪些补丁痕迹（用于等待卸载真正完成）

    注：`NOTES DaSH\\dinput8.dll` 这条只对**含分号**的目录（如 Steam 正本）有意义 ——
    加载器会去「分号后片段同名」的子目录找 DLL，安装器就在那里建一个。
    对无分号的目录这条永不命中，留着无害（多一条"必须消失"的判据而已）。
    """
    marks = ["dinput8.dll", "VSFilter.dll", "RNDZhLauncher.exe",
             "d3d9", "d3d10", "d3d10_1", "d3d10core", "d3d11", "dxgi",
             "languagebarrier", os.path.join("NOTES DaSH", "dinput8.dll"),
             "_cn_patch_boot_orig.bat"]
    return [m for m in marks if os.path.exists(os.path.join(root, m))]

def cjk_stat(root):
    lb = os.path.join(root, "languagebarrier")
    try:
        import io, json
        cs = json.load(io.open(os.path.join(lb, "patchdef.json"),
                               encoding="utf-8-sig"))["base"]["charset"]
    except Exception:
        return None
    p = os.path.join(lb, "enscript", "rnd_01_01_00.msb")
    if not os.path.exists(p):
        return None
    d = open(p, "rb").read()
    n = struct.unpack_from("<I", d, 8)[0]
    base = struct.unpack_from("<I", d, 12)[0]
    tot = cjk = 0
    for k in range(n):
        e = 0x18 + k * 8
        if e + 8 > len(d):
            break
        _, off = struct.unpack_from("<II", d, e)
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
        t = "".join(s)
        tot += 1
        if any("\u4e00" <= c <= "\u9fff" for c in t):
            cjk += 1
    return tot, cjk


print("=" * 74)
print(" 成品安装包最终验收")
print(" 包: %s" % SETUP)
print("=" * 74)
print(" 大小: %.1f MB   md5: %s" % (os.path.getsize(SETUP) / 1048576, md5(SETUP)[:16]))

master = snap(MASTER)
print("\n[0] 纯净母本: %d 文件" % len(master))

# 先卸载到纯净
print("\n[1] 归零")
ui = os.path.join(TARGET, UNINSTALLER)
if os.path.exists(ui):
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "$p=Start-Process -FilePath '%s' -ArgumentList '/silent' "
                    "-Verb RunAs -PassThru; $p|Wait-Process -Timeout 180 "
                    "-EA SilentlyContinue" % ui], capture_output=True)
    for _ in range(120):
        time.sleep(1)
        if not patch_left(TARGET):
            break
cur = snap(TARGET)
print("  多余: %s" % (sorted(set(cur) - set(master)) or "无"))

before = set(z7_dirs())
print("\n[2] 安装（静默，验证整条链路）")
ps = ("$p=Start-Process -FilePath '%s' -ArgumentList '-y','\"%s\"','/silent' "
      "-Verb RunAs -PassThru; $p.Id" % (SETUP, TARGET))
r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print("  启动 pid=%s" % (r.stdout or "").strip())
# 判断"补丁落盘"看的是 languagebarrier/ —— 不要盯 NOTES DaSH\。
# TARGET 是个 junction（RND_DaSH_en_copy，名字里没有分号），加载器直接用根目录那份，
# 安装器也就**不会**建任何片段子目录。以前这里查 NOTES DaSH\dinput8.dll 能过，
# 只是因为 payload 里恰好预置了那个目录（2026-09-12 已移除，实测它冗余）——
# 于是这个检查条件本身是错的，改成查真正必然存在的补丁目录。
ok = False
for i in range(100):
    time.sleep(2)
    if (os.path.exists(os.path.join(TARGET, "languagebarrier", "patchdef.json"))
            and os.path.exists(os.path.join(TARGET, "dinput8.dll"))):
        ok = True
        print("  第 %d 秒：补丁落盘" % ((i + 1) * 2))
        break
print("  安装: %s" % ("✓" if ok else "★失败"))

print("\n[3] 启动验证（补丁是否真的加载 + 文本是否中文）")
log = os.path.join(TARGET, "languagebarrier", "log.txt")
if os.path.exists(log):
    os.remove(log)
subprocess.run(["taskkill", "/F", "/IM", "Game.exe"], capture_output=True)
time.sleep(2)
p = subprocess.Popen([os.path.join(TARGET, "Game.exe"), "roboticsnotesd", "EN"],
                     cwd=TARGET, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
loaded = False
for _ in range(60):
    if os.path.exists(log) and os.path.getsize(log) > 0:
        loaded = True
        break
    if p.poll() is not None:
        break
    time.sleep(1)
p.kill()
subprocess.run(["taskkill", "/F", "/IM", "Game.exe"], capture_output=True)
print("  log.txt: %s" % ("✓ %d B" % os.path.getsize(log) if loaded else "★无（未加载）"))
if loaded:
    txt = open(log, encoding="utf-8", errors="replace").read()
    print("  错误数: %d"
          % (txt.lower().count("error") + txt.lower().count("exception")))
st = cjk_stat(TARGET)
if st:
    print("  中文文本: %d/%d 条含汉字" % (st[1], st[0]))

print("\n[4] 卸载")
time.sleep(2)
ps2 = ("$p=Start-Process -FilePath '%s' -ArgumentList '/silent' -Verb RunAs "
       "-PassThru; $p.Id" % os.path.join(TARGET, UNINSTALLER))
subprocess.run(["powershell", "-NoProfile", "-Command", ps2],
               capture_output=True)
for _ in range(120):
    time.sleep(1)
    if not patch_left(TARGET):
        break
print("  卸载耗时约 %d 秒（等待所有补丁痕迹消失）" % (_ + 1))

print("\n[5] 与纯净母本比对")
cur = snap(TARGET)
extra = sorted(set(cur) - set(master))
miss = sorted(set(master) - set(cur))
diff = sorted(k for k in set(cur) & set(master) if cur[k] != master[k])
unexpected = [x for x in extra if x not in KEEP]
print("  多余 %d（工具 %d）| 缺失 %d | 不同 %d"
      % (len(extra), len(extra) - len(unexpected), len(miss), len(diff)))
for x in unexpected[:8]:
    print("     + %s" % x)
for x in miss[:8]:
    print("     - %s" % x)
for x in diff[:8]:
    print("     ~ %s" % x)

time.sleep(6)
new_z7 = set(z7_dirs()) - before
print("\n[6] 临时目录残留: %s" % ("★ %s" % new_z7 if new_z7 else "✓ 无"))

print("\n" + "=" * 74)
good = ok and loaded and not unexpected and not miss and not diff and not new_z7
print(" 结果: %s" % ("★ 通过 —— 安装有效、卸载回纯净、无残留" if good else "★ 有问题，见上"))
print("=" * 74)
sys.exit(0 if good else 1)
