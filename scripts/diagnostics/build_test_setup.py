# 编译一个"测试版"安装器：去掉 requireAdministrator 清单，
# 这样非提权也能启动，自动化测试才能点它、给它打字。
# 用途仅限验证 UI 交互（输入框、焦点），发布版仍用带清单的那个。
import os
import subprocess
import sys

SRC = r"D:\DATA\tran\agent tran\9.6文本外工作\成品ing\setup\src"
BUILD = r"D:\DATA\tran\agent tran\9.6文本外工作\成品ing\setup\build"
TMP = os.environ.get("TEMP", r"D:\rnd_test")
os.makedirs(TMP, exist_ok=True)

# 复制源码与 rc（rc 里引用 manifest，所以换成一个只有图标的 rc）
import shutil
shutil.copy2(os.path.join(SRC, "RNDZhSetup.cpp"), os.path.join(TMP, "RNDZhSetup.cpp"))
shutil.copy2(os.path.join(SRC, "game.ico"), os.path.join(TMP, "game.ico"))
with open(os.path.join(TMP, "test.rc"), "w") as f:
    f.write('#include <windows.h>\n101 ICON "game.ico"\n')

BAT = """@echo off
call "C:\\VS2022BT\\VC\\Auxiliary\\Build\\vcvars32.bat" >nul
cd /d "{tmp}"
rc /nologo /fo test.res test.rc
cl /nologo /std:c++17 /EHsc /utf-8 /O2 /MT /DUNICODE /D_UNICODE ^
   RNDZhSetup.cpp ^
   /link /SUBSYSTEM:WINDOWS /ENTRY:wWinMainCRTStartup ^
   gdiplus.lib shell32.lib user32.lib gdi32.lib ole32.lib advapi32.lib ^
   test.res /OUT:RNDZhSetup_test.exe
""".format(tmp=TMP)
bp = os.path.join(TMP, "b.bat")
open(bp, "w", newline="\r\n").write(BAT)
r = subprocess.run(["cmd", "/c", bp], capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
exe = os.path.join(TMP, "RNDZhSetup_test.exe")
print("编译:", "OK" if os.path.exists(exe) else r.stdout[-500:])
if os.path.exists(exe):
    d = open(exe, "rb").read()
    print("  requireAdministrator:", "有（不对，应去掉）" if b"requireAdministrator" in d else "无 ✓ 可非提权运行")
    print("  路径:", exe)
