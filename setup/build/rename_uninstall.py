# -*- coding: utf-8 -*-
"""把编译出来的 RNDZhUninstall.exe 改名成中文产品名「卸载汉化.exe」。

为什么不在 build_uninstall.bat 里直接输出中文名：
    .bat 里的中文很脆 —— cmd 按 OEM 代码页逐行读文件、chcp 只对还没读到的行生效，
    编辑器把 CRLF 写成 LF 也会直接失效（两种都踩过）。
    Python 处理 Unicode 路径没有这些问题（build_installer.py 用 Python 也是同样理由）。

为什么要改成中文名：
    RNDZhLauncher.exe 与 RNDZhUninstall.exe 名字太像，两个 exe 又并排躺在游戏目录里，
    玩家容易点错 —— 而点错的代价是「把汉化卸了」。中文名一眼可辨，图标也换成
    红底垃圾桶（make_uninstall_icon.py）。

同时清理旧名残留：玩家从旧版升级上来时，游戏目录里可能还留着 RNDZhUninstall.exe。
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(os.path.dirname(HERE), "bin")

OLD = "RNDZhUninstall.exe"
NEW = "卸载汉化.exe"
# 历史名（更早的版本用过别的写法，一并清掉）
STALE = ["RNDZhUninstall.exe", "RNDZh-Uninstall.exe", "卸载程序.exe", "uninstall.exe"]

src = os.path.join(BIN, OLD)
dst = os.path.join(BIN, NEW)

if not os.path.exists(src):
    # 已经是新名（重复构建）也算成功
    if os.path.exists(dst):
        print("已是新名: %s" % NEW)
        sys.exit(0)
    sys.exit("找不到编译产物: %s" % src)

# 覆盖旧产物
if os.path.exists(dst):
    os.remove(dst)
os.replace(src, dst)
print("已改名: %s -> %s" % (OLD, NEW))

# 清掉 bin 里其余历史名，免得打包时把旧名一起带进去
for n in STALE:
    p = os.path.join(BIN, n)
    if os.path.exists(p) and os.path.normcase(p) != os.path.normcase(dst):
        os.remove(p)
        print("已清理历史名: %s" % n)

print("bin/ 现有 exe: %s" % sorted(f for f in os.listdir(BIN)
                                   if f.lower().endswith(".exe")))
