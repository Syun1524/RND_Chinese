# -*- coding: utf-8 -*-
"""列出三个窗口程序里**玩家可见**的中文文案（HUD 巡检）。

目的：确认界面上没有实现细节外泄 —— 比如「路径含分号，已自动兼容」这类
玩家看不懂、也不需要知道的内部机制。注释里的技术说明不算（那是给维护者的）。

法：只扫非注释行里形如 L"中文…" 的字符串字面量。
"""
import io
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

CJK = re.compile(u'[\u4e00-\u9fff]')
STR = re.compile(r'L"((?:[^"\\]|\\.)*)"')

FILES = [
    r"成品ing\setup\src\RNDZhSetup.cpp",
    r"成品ing\setup\src\RNDZhUninstall.cpp",
    r"launcher\RNDZhLauncher.cpp",
]

# 明显是实现术语，出现在玩家可见文案里就该被质疑
JARGON = ["分号", "片段", "加载器", "DLL", "hook", "重定向", "fileRedirection",
          "registry", "兼容目录", "字节", "0x"]

for rel in FILES:
    print("=" * 78)
    print(rel)
    print("=" * 78)
    hits = 0
    for i, line in enumerate(io.open(rel, encoding="utf-8"), 1):
        st = line.strip()
        if st.startswith("//") or st.startswith("*") or st.startswith("/*"):
            continue
        for m in STR.finditer(line):
            s = m.group(1)
            if not CJK.search(s):
                continue
            hits += 1
            flag = ""
            for j in JARGON:
                if j in s:
                    flag = "   ← 含实现术语?"
                    break
            print("  %4d: %s%s" % (i, s, flag))
    if not hits:
        print("  （无）")
    print()
