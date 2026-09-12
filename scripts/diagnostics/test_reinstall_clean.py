# -*- coding: utf-8 -*-
r"""重装场景验证：装在【已装过补丁】的目录上，卸载后必须回纯净（不能留下补丁文件）。

发现的 bug（测试 Steam 正本时暴露）：
    对已经装过补丁的目录再装一次时，安装器把「那里的 dinput8.dll / d3d9 / dxgi /
    VSFilter.dll …」也备份了。卸载器看到"备份里有这个文件"就按
    "安装前就存在的文件 → 恢复"处理，于是把我们自己的补丁文件原样留下 ——
    卸载后游戏目录里还躺着 8 个代理 DLL，而纯净母本没有它们。

修法：安装前比对内容 —— 与 payload 里同名文件一致的，说明是上次装的补丁，不备份
（卸载时按"没有备份 → 删除"处理）。内容不同才是玩家的原版/别家文件，必须备份。

本脚本要覆盖两个方向：
  A) 断点续装：装 → 再装 → 卸载 → 必须回纯净
  B) 保护外来文件：放一个"内容不同的 dinput8.dll"（模拟别家补丁）→ 装 → 卸载 →
     那个文件必须被**还原**回来（而不是删掉）

B 方向容易被 A 的修法误伤（改宽了就变成"什么都删"），所以必须一起测。
"""
import hashlib
import os
import shutil
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

WS = r"D:\DATA\tran\agent tran\9.6文本外工作"
SETUP_SRC = os.path.join(WS, "成品ing", "setup", "src")
PAYLOAD_SRC = os.path.join(WS, "成品ing", "补丁包")

TARGET = r"D:\Ruanjian\Steam\steamapps\common\ROBOTICS;NOTES DaSH -原版英文 副本 - 副本"
FRAG = "NOTES DaSH -原版英文 副本 - 副本"

TMP = os.environ.get("TEMP", r"C:\Windows\Temp")
BUILD = os.path.join(TMP, "rnd_reinstall_build")
STAGE = os.path.join(TMP, "rnd_reinstall_payload")

INST = "ui_probe.exe"     # 名字避开 setup/install（否则被启发式要求提权）
UNINST = "ui_rm.exe"


def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def snap(root):
    out = {}
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if not d.startswith("_cn_patch_backup")]
        for n in fns:
            p = os.path.join(dp, n)
            rel = os.path.relpath(p, root)
            try:
                out[rel] = (os.path.getsize(p), md5(p))
            except OSError:
                out[rel] = (-1, "?")
    return out


def killall():
    for e in ("Game.exe", "launcher.exe", INST, UNINST):
        subprocess.run(["taskkill", "/F", "/IM", e], capture_output=True)


def build():
    for d in (BUILD, STAGE):
        os.makedirs(d, exist_ok=True)
    shutil.copy2(os.path.join(SETUP_SRC, "game.ico"), os.path.join(BUILD, "game.ico"))
    with open(os.path.join(BUILD, "test.rc"), "w") as f:
        f.write('#include <windows.h>\n101 ICON "game.ico"\n')
    for src_name, out_name in [("RNDZhSetup.cpp", INST),
                               ("RNDZhUninstall.cpp", UNINST)]:
        shutil.copy2(os.path.join(SETUP_SRC, src_name),
                     os.path.join(BUILD, src_name))
        bat = os.path.join(BUILD, "b_%s.bat" % out_name)
        with open(bat, "w", newline="\r\n") as f:
            f.write('@echo off\n'
                    'call "C:\\VS2022BT\\VC\\Auxiliary\\Build\\vcvars32.bat" >nul\n'
                    'cd /d "%s"\n'
                    'rc /nologo /fo test.res test.rc\n'
                    'cl /nologo /std:c++17 /EHsc /utf-8 /O2 /MT /DUNICODE /D_UNICODE '
                    '%s /link /SUBSYSTEM:WINDOWS /ENTRY:wWinMainCRTStartup '
                    'gdiplus.lib shell32.lib user32.lib gdi32.lib ole32.lib advapi32.lib '
                    'test.res /OUT:%s\n' % (BUILD, src_name, out_name))
        r = subprocess.run(["cmd", "/c", bat], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if not os.path.exists(os.path.join(BUILD, out_name)):
            print("!! 编译失败 %s\n%s" % (src_name, (r.stdout or "")[-700:]))
            return False
    # payload
    for n in os.listdir(PAYLOAD_SRC):
        if n in ("RNDZhSetup.exe", "RNDZhUninstall.exe"):
            continue
        s, d = os.path.join(PAYLOAD_SRC, n), os.path.join(STAGE, n)
        if os.path.isdir(s):
            shutil.copytree(s, d, dirs_exist_ok=True)
        else:
            shutil.copy2(s, d)
    shutil.copy2(os.path.join(BUILD, INST), os.path.join(STAGE, INST))
    return True


def run(exe, args, cwd=None, timeout=300):
    return subprocess.run([exe] + args, capture_output=True, cwd=cwd,
                          timeout=timeout)


def pristine():
    """把游戏目录清回干净（用无清单卸载器 + 手清残留）

    boot.bat 特殊：它是**游戏自己的文件**（安装器只改写内容、卸载时还原）。
    这里从纯净母本拷一份回来，保证基线快照包含它 —— 否则卸载后
    "多出 boot.bat" 会变成假警报（其实是我们自己刚才删掉的）。
    """
    killall()
    time.sleep(1)
    if os.path.isdir(os.path.join(TARGET, "languagebarrier")):
        shutil.copy2(os.path.join(BUILD, UNINST), os.path.join(TARGET, UNINST))
        run(os.path.join(TARGET, UNINST), ["/silent"], cwd=TARGET)
        for _ in range(90):
            time.sleep(1)
            if not os.path.isdir(os.path.join(TARGET, "languagebarrier")):
                break
        time.sleep(2)
    # 兜底手清（补丁文件 + 兼容子目录 + 工具）；boot.bat 不动
    payload_names = set(os.listdir(PAYLOAD_SRC)) - {"boot.bat"}
    for n in list(payload_names) + [UNINST, INST, FRAG, "RNDZhLauncher.exe",
                                    "RNDZhUninstall.exe", "_cn_patch_boot_orig.bat"]:
        p = os.path.join(TARGET, n)
        if os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)
        elif os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass
    if os.path.isdir(os.path.join(TARGET, FRAG)):
        shutil.rmtree(os.path.join(TARGET, FRAG), ignore_errors=True)
    # boot.bat 从母本还原（母本 = 去掉尾部「 - 副本」的同名目录）
    mother = r"D:\Ruanjian\Steam\steamapps\common\ROBOTICS;NOTES DaSH -原版英文 副本"
    src_bb = os.path.join(mother, "boot.bat")
    if os.path.exists(src_bb):
        shutil.copy2(src_bb, os.path.join(TARGET, "boot.bat"))
    time.sleep(1)


INST_EXE = os.path.join(STAGE, INST)

print("=== 编译 ===")
if not build():
    sys.exit(1)
print("  OK  payload=%s" % STAGE)
print()

# ───────────── A) 重装 ─────────────
print("=" * 90)
print("A) 装两次再卸载 —— 检查是否留下补丁文件")
print("=" * 90)
pristine()
base = snap(TARGET)
print("  基线 %d 个文件" % len(base))

r = run(INST_EXE, [TARGET, "/silent"], cwd=STAGE)
print("  第 1 次安装 rc=%s" % r.returncode)
r = run(INST_EXE, [TARGET, "/silent"], cwd=STAGE)
print("  第 2 次安装 rc=%s（重装）" % r.returncode)

shutil.copy2(os.path.join(BUILD, UNINST), os.path.join(TARGET, UNINST))
r = run(os.path.join(TARGET, UNINST), ["/silent"], cwd=TARGET)
print("  卸载 rc=%s" % r.returncode)
for _ in range(90):
    time.sleep(1)
    if not os.path.isdir(os.path.join(TARGET, "languagebarrier")):
        break
time.sleep(2)

after = snap(TARGET)
allow = {INST, UNINST}
extra = sorted(set(after) - set(base) - allow)
missing = sorted(set(base) - set(after))
changed = sorted(k for k in (set(base) & set(after)) if base[k] != after[k])
print("  多余 %d | 缺失 %d | 不同 %d" % (len(extra), len(missing), len(changed)))
for k in extra[:15]:
    print("    多余: %s" % k)
for k in missing[:15]:
    print("    缺失: %s" % k)
for k in changed[:15]:
    print("    不同: %s" % k)
a_ok = not extra and not missing and not changed
print("  A 结论: %s" % ("✓ 重装后卸载干净" if a_ok else "✗ 仍有残留"))
print()

# ───────────── B) 外来文件必须被还原 ─────────────
print("=" * 90)
print("B) 目录里先放一个「别家的 dinput8.dll」——装完卸载必须还原它，不能删")
print("=" * 90)
pristine()
fake = os.path.join(TARGET, "dinput8.dll")
with open(fake, "wb") as f:
    f.write(b"FAKE_FOREIGN_PATCH_DLL" * 1000)      # 内容与 payload 不同
fake_md5 = md5(fake)
print("  放了假的 dinput8.dll（%d 字节, md5 %s）" % (os.path.getsize(fake),
                                                    fake_md5[:12]))

r = run(INST_EXE, [TARGET, "/silent"], cwd=STAGE)
print("  安装 rc=%s" % r.returncode)
now = md5(os.path.join(TARGET, "dinput8.dll"))
print("  安装后 dinput8.dll 被覆盖成补丁的: %s" % ("是" if now != fake_md5 else "否"))

shutil.copy2(os.path.join(BUILD, UNINST), os.path.join(TARGET, UNINST))
r = run(os.path.join(TARGET, UNINST), ["/silent"], cwd=TARGET)
print("  卸载 rc=%s" % r.returncode)
for _ in range(90):
    time.sleep(1)
    if not os.path.isdir(os.path.join(TARGET, "languagebarrier")):
        break
time.sleep(2)

if os.path.exists(fake):
    restored = md5(fake)
    b_ok = (restored == fake_md5)
    print("  卸载后 dinput8.dll: %s"
          % ("✓ 还原成外来文件" if b_ok else "✗ 内容不对（md5 %s）" % restored[:12]))
else:
    b_ok = False
    print("  ✗ 外来文件被删掉了（应该还原）")

# 清掉测试放的外来文件
if os.path.exists(fake) and md5(fake) == fake_md5:
    os.remove(fake)

print()
print("=" * 90)
print("A 重装清理 : %s" % ("通过 ✓" if a_ok else "失败 ✗"))
print("B 外来还原 : %s" % ("通过 ✓" if b_ok else "失败 ✗"))
killall()
# 清掉测试工具（会被安装器当 payload 拷进游戏目录）与暂存目录
for n in (INST, UNINST):
    p = os.path.join(TARGET, n)
    if os.path.exists(p):
        try:
            os.remove(p)
        except OSError:
            pass
for d in (BUILD, STAGE):
    shutil.rmtree(d, ignore_errors=True)
print("已清理测试工具与暂存目录")
