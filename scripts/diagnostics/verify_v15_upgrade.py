# -*- coding: utf-8 -*-
"""升级路径验证：v1.4 状态 → 跑 v1.5 安装器 → 旧孤儿副本必须被清掉。

为什么单独做这一条：`final_accept.py` 只验「纯净母本 → 装 → 卸」，
**覆盖不到升级**。而 v1.5 去掉了 c0data 里两个文件，安装器的复制步骤
只覆盖/新增、**不会**清理「包内已不存在的条目」—— 旧文件会留在玩家机器上。
所以 v1.5 的安装器里加了显式清理，这条测试就是验它真的生效。

做法：拿纯净母本复制一份到 %TEMP%，手工造出 v1.4 的文件布局
（补上两个孤儿副本 + 用 v1.4 的 cls/patchdef），再静默跑 v1.5 安装器，
断言：① 两个孤儿文件消失 ② cls 是 77 行 ③ 重定向指向同一份 ④ 卸载后回纯净。
"""
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = r'D:\DATA\tran\agent tran\9.6文本外工作'
SETUP = os.path.join(ROOT, '成品ing', 'RNDZh-Setup-v1.5.exe')
PRISTINE = r'D:\Ruanjian\Steam\steamapps\common\RND_DaSH_en_copy'
V14_PKG = os.path.join(ROOT, '成品ing', 'RNDZh-Setup-v1.4.exe')
# 曾经用过、现在已被合并掉的名字（安装器要删的）
OLD_NAMES = ('RND_PC_controller_jp.png', 'RND_PC_keyboard_jp.png')
# 现在正式使用的名字（与源图同名）
NEW_NAMES = ('control_pc.png', 'keyboard_pc.png')
SDK7Z = os.path.join(ROOT, '成品ing', 'setup', 'build', 'sdk', '7zr.exe')


def count_files(d):
    return sum(len(f) for _, _, f in os.walk(d))


def run_elevated(exe, args, timeout=600):
    """安装器/卸载器清单里是 requireAdministrator，直接 CreateProcess 会
    WinError 740。走 PowerShell 的 -Verb RunAs（与 final_accept.py 同一做法）。

    ⚠ 参数必须**逐个带引号**：`-ArgumentList` 是把数组拼成命令行字符串，
    含空格的路径不加引号会被拆成两个参数，安装器按 argv[1] 取目标目录就会
    拿到半截路径 —— 它检测到目录不存在会直接返回 2（不会误装到别处），
    但测试会看到"什么都没发生"。实测踩过：%TEMP% 路径含空格。
    """
    arglist = ",".join("'\"%s\"'" % a for a in args)
    ps = ("$p=Start-Process -FilePath '%s' -ArgumentList %s -Verb RunAs -PassThru; "
          "$p|Wait-Process -Timeout %d -EA SilentlyContinue; $p.Id"
          % (exe, arglist, timeout))
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout + 60)
    return r


def main():
    if not os.path.exists(SETUP):
        sys.exit('缺少 %s' % SETUP)
    if not os.path.exists(PRISTINE):
        sys.exit('缺少纯净母本 %s' % PRISTINE)

    tmp = tempfile.mkdtemp(prefix='upgrade_v15_')
    game = os.path.join(tmp, 'ROBOTICS;NOTES DaSH')
    shutil.copytree(PRISTINE, game, symlinks=True)
    print('隔离副本: %s' % game)
    print('  初始文件数: %d' % count_files(game))

    # ---- 1) 造出 v1.4 状态：从 v1.4 安装包解出 languagebarrier 覆盖进去 ----
    print('\n[1] 构造 v1.4 状态')
    ex = os.path.join(tmp, 'v14')
    os.makedirs(ex, exist_ok=True)
    r = subprocess.run([SDK7Z, 'x', V14_PKG, '-o' + ex, '-y'],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode != 0:
        sys.exit('解 v1.4 包失败: %s' % (r.stdout or '')[-400:])
    # v1.4 包里的 languagebarrier 直接覆盖
    src_lb = os.path.join(ex, 'languagebarrier')
    if not os.path.isdir(src_lb):
        sys.exit('v1.4 包里没有 languagebarrier')
    shutil.copytree(src_lb, os.path.join(game, 'languagebarrier'), dirs_exist_ok=True)
    for f in ('RNDZhLauncher.exe', '卸载汉化.exe', '安装说明.txt'):
        s = os.path.join(ex, f)
        if os.path.exists(s):
            shutil.copy2(s, os.path.join(game, f))
    c0 = os.path.join(game, 'languagebarrier', 'c0data')
    orphans = [f for f in OLD_NAMES if os.path.exists(os.path.join(c0, f))]
    print('  v1.4 孤儿副本: %s' % (orphans or '★ 没造出来，测试无效'))
    if len(orphans) != 2:
        sys.exit('★ 未能构造出 v1.4 的两个孤儿副本，测试前提不成立')
    cls14 = [l.strip() for l in io.open(os.path.join(game, 'languagebarrier', 'c0data.cls'),
                                       encoding='utf-8-sig').read().splitlines() if l.strip()]
    print('  v1.4 cls 行数: %d' % len(cls14))

    # ---- 2) 跑 v1.5 安装器 ----
    # SFX 的 config 是 `RunProgram="RNDZhSetup.exe"` —— **不带任何参数**，
    # 安装器自己从 GetCommandLineW() 里找 /silent 与目标目录。
    # 所以传给 SFX exe 的参数就是给内层 setup 的：第一个非 `/` 参数 = 目标目录。
    # ⚠ 别在前面塞 `-y` 之类：那会被当成 argv[1]（目标目录），
    #   IsDir 失败 → 安装器直接 return 2，测试看到"什么都没发生"。
    print('\n[2] 跑 v1.5 安装器（静默，需提权）')
    t0 = time.time()
    run_elevated(SETUP, [game, '/silent'])
    dt = time.time() - t0
    print('  耗时 %.1fs' % dt)
    # 等补丁落盘（cls 变成 77 行才算真的换过）
    lb = os.path.join(game, 'languagebarrier')
    cls_path = os.path.join(lb, 'c0data.cls')
    for _ in range(180):
        if os.path.exists(cls_path):
            lines = [l for l in io.open(cls_path, encoding='utf-8-sig').read().splitlines() if l.strip()]
            if len(lines) == 77:
                break
        time.sleep(1)

    # ---- 3) 断言 ----
    print('\n[3] 断言')
    ok = True
    lb = os.path.join(game, 'languagebarrier')
    c0 = os.path.join(lb, 'c0data')

    left = [f for f in OLD_NAMES if os.path.exists(os.path.join(c0, f))]
    print('  旧名已清: %s' % ('✓' if not left else '★ 残留 %s' % left))
    ok &= not left
    miss = [f for f in NEW_NAMES if not os.path.exists(os.path.join(c0, f))]
    print('  新名就位: %s' % ('✓' if not miss else '★ 缺 %s' % miss))
    ok &= not miss

    cls = [l.strip() for l in io.open(os.path.join(lb, 'c0data.cls'),
                                     encoding='utf-8-sig').read().splitlines() if l.strip()]
    print('  cls 行数 = %d %s' % (len(cls), '✓' if len(cls) == 77 else '★ 期望 77'))
    ok &= (len(cls) == 77)

    fr = json.load(io.open(os.path.join(lb, 'patchdef.json'), encoding='utf-8-sig'))['base']['fileRedirection']
    for a1, f1, a2, f2, what in [('system', '33', 'manual', '0', '手柄图'),
                                 ('system', '35', 'manual', '1', '键盘图')]:
        v1 = fr[a1][f1]; v1 = v1['jp'] if isinstance(v1, dict) else v1
        v2 = fr[a2][f2]; v2 = v2['jp'] if isinstance(v2, dict) else v2
        good = (v1 == v2)
        print('  %s 共享同一条目: %s/%s=[%d] %s  %s'
              % (what, a1, f1, v1, cls[v1], '✓' if good else '★'))
        ok &= good

    # 共享的那份文件必须真的在
    for nm in NEW_NAMES:
        e = os.path.exists(os.path.join(c0, nm))
        print('  %-28s 存在: %s' % (nm, '✓' if e else '★'))
        ok &= e

    # ---- 4) 卸载回纯净 ----
    print('\n[4] 卸载')
    un = os.path.join(game, '卸载汉化.exe')
    if os.path.exists(un):
        run_elevated(un, ['/silent'])
        for _ in range(120):
            if not os.path.exists(os.path.join(game, 'languagebarrier')):
                break
            time.sleep(1)
        time.sleep(2)
        # 卸载器可能把自己留在原地，比对时排除
        base = set()
        for dp, dn, fn in os.walk(PRISTINE):
            for f in fn:
                base.add(os.path.relpath(os.path.join(dp, f), PRISTINE))
        cur = set()
        for dp, dn, fn in os.walk(game):
            for f in fn:
                cur.add(os.path.relpath(os.path.join(dp, f), game))
        extra = sorted(cur - base)
        missing = sorted(base - cur)
        print('  多余 %d %s' % (len(extra), extra[:5] if extra else ''))
        print('  缺失 %d %s' % (len(missing), missing[:5] if missing else ''))
        ok &= not missing
        # 多余只允许卸载器自身
        bad_extra = [x for x in extra if x != '卸载汉化.exe']
        ok &= not bad_extra
    else:
        print('  ★ 没找到卸载器')
        ok = False

    print('\n' + '=' * 60)
    print('升级路径验证: %s' % ('★ 通过' if ok else '★ 失败'))
    print('=' * 60)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
