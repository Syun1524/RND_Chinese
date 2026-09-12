# 把两个诊断工具编译到 scripts/diagnostics/（源码在这些 .cpp 里）。
# 之前它们建在已删除的 tmp_128/ 下，这里一次编好，脚本就不再依赖旧目录。
import os
import subprocess
import sys

HERE = r"D:\DATA\tran\agent tran\9.6文本外工作\scripts\diagnostics"

BAT = """@echo off
call "C:\\VS2022BT\\VC\\Auxiliary\\Build\\vcvars32.bat" >nul
cd /d "%~dp0"
cl /nologo /EHsc /O2 modscan32.cpp /link /SUBSYSTEM:CONSOLE /OUT:modscan32.exe
cl /nologo /EHsc /O1 rndkill.cpp   /link /SUBSYSTEM:CONSOLE /OUT:rndkill.exe
"""
bp = os.path.join(HERE, "build_tools.bat")
open(bp, "w", newline="\r\n").write(BAT)
r = subprocess.run(["cmd", "/c", bp], capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
print(r.stdout[-600:])
for t in ("modscan32.exe", "rndkill.exe"):
    p = os.path.join(HERE, t)
    print("  %-16s %s" % (t, "%d B" % os.path.getsize(p) if os.path.exists(p) else "★缺失"))
