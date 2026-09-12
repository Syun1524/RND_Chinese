# -*- coding: utf-8 -*-
"""构建单文件安装包 RNDZh-Setup-v<版本>.exe（官方 SFX 安装器模式）

拼装方式（与 LZMA SDK 的 DOC/installer.txt + bin/installer/cr.bat 一致）：

    7zSD.sfx  +  config.txt  +  archive.7z   →   RNDZh-Setup-v0.1.exe

7zSD.sfx 是**安装器版** SFX 模块（LZMA SDK 提供）。它自解压到临时目录、运行
RunProgram 指定的程序、并在程序退出后**自动删除临时目录** —— 解压残留由模块
自己解决，不需要额外清理代码。

★ 两个踩过的坑，务必保持：

  1) 模块必须是 7zSD.sfx，不能用 7z.sfx。
     7-Zip 25.01 自带的 7z.sfx / 7zCon.sfx 是**纯解压模块**，里面完全没有
     ;!@Install@! 那套机制 —— 用它打包时 config 会被整体忽略，双击后弹的是
     「Extract to:」对话框，玩家得自己解压再手动找 setup 运行。
     （这正是之前"安装流程诡异"的原因。）

  2) config 必须写**真正的 CR LF**，不能是字面的反斜杠 r n。
     一旦是字面量，模块会报 "Config failed" 并拒绝安装。

为什么用 Python 而不是 .bat：包路径和 SFX 配置都含中文，
cmd 的代码页处理这些会错乱，Python 处理 UTF-8 没有这个问题。
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SDK = os.path.join(HERE, 'sdk')
SEVENZR = os.path.join(SDK, '7zr.exe')            # SDK 自带，支持 -mf=BCJ2
SFX = os.path.join(SDK, '7zSD_custom.sfx')        # 安装器版 SFX（已换我方图标）
# setup/ 位于 成品ing/ 内，补丁包是它的兄弟目录
PKG = os.path.abspath(os.path.join(HERE, '..', '补丁包'))
SETUP = os.path.join(HERE, 'RNDZhSetup.exe')

VERSION = '0.1'
TITLE = 'ROBOTICS;NOTES DaSH 简体中文补丁'
# 一行说清「装什么 + 前提」。不做无意义的二次确认 ——
# 真正需要用户确认的是安装器界面里的「开始安装」。
PROMPT = '简体中文补丁，约需 1-2 分钟。\n\n安装前请先完全关闭游戏。'


def log(*a):
    print(*a, flush=True)


def main():
    for p, what in ((SEVENZR, '7zr.exe'), (SFX, '7zSD_custom.sfx'),
                    (PKG, '补丁包目录'), (SETUP, 'RNDZhSetup.exe')):
        if not os.path.exists(p):
            sys.exit('缺少 %s：%s' % (what, p))

    out_name = 'RNDZh-Setup-v%s.exe' % VERSION
    out_path = os.path.join(HERE, out_name)
    stage = os.path.join(HERE, '_stage')
    payload = os.path.join(HERE, 'payload.7z')
    cfg_path = os.path.join(HERE, 'sfx_config.txt')

    # 1) 准备 stage：补丁包全部内容 + 安装器
    log('[1/4] 准备临时目录…')
    if os.path.isdir(stage):
        shutil.rmtree(stage)
    shutil.copytree(PKG, stage)
    shutil.copy2(SETUP, os.path.join(stage, 'RNDZhSetup.exe'))
    total = sum(len(f) for _, _, f in os.walk(stage))
    log('      共 %d 个文件' % total)

    # 2) 用 7zr 压缩（官方安装器示例即 7zr + BCJ2）
    log('[2/4] 压缩中…（约需 20-60 秒）')
    if os.path.exists(payload):
        os.remove(payload)
    r = subprocess.run([SEVENZR, 'a', '-t7z', '-mx=5', '-ms=on', '-mf=BCJ2',
                        payload, os.path.join(stage, '*')],
                       capture_output=True)
    if r.returncode != 0:
        sys.exit('压缩失败：' + r.stderr.decode('utf-8', 'replace'))

    # 3) 写 SFX 配置（真 CRLF + UTF-8）
    log('[3/4] 写 SFX 配置…')
    # 不设 BeginPrompt：确认点留给安装器窗口的「开始安装」，少一次点击。
    # 解压要一两分钟，期间用 Progress 显示进度条，避免用户以为卡住。
    cfg = (';!@Install@!UTF-8!\r\n'
           'Title="%s"\r\n'
           'Progress="yes"\r\n'
           'RunProgram="RNDZhSetup.exe"\r\n'
           ';!@InstallEnd@!\r\n' % TITLE)
    with open(cfg_path, 'w', newline='', encoding='utf-8') as f:
        f.write(cfg)
    raw = open(cfg_path, 'rb').read()
    # 自检：必须是真 CRLF，不能是字面 \r\n（否则 7zSD 报 Config failed）
    assert b'\r\n' in raw, 'config 缺少 CRLF'
    assert b'\\r\\n' not in raw, 'config 里是字面 \\r\\n，未写成真换行'

    # 4) 拼装：SFX + 配置 + payload
    log('[4/4] 拼装…')
    if os.path.exists(out_path):
        os.remove(out_path)
    with open(out_path, 'wb') as dst:
        for part in (SFX, cfg_path, payload):
            with open(part, 'rb') as src:
                shutil.copyfileobj(src, dst)

    # 清理中间产物
    os.remove(payload)
    os.remove(cfg_path)
    shutil.rmtree(stage, ignore_errors=True)

    log('')
    log('=== 完成 ===')
    log('  输出：%s' % out_path)
    log('  大小：%.1f MB' % (os.path.getsize(out_path) / 1048576))
    log('  模块：%s（安装器版 SFX）' % os.path.basename(SFX))


if __name__ == '__main__':
    main()
