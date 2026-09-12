# -*- coding: utf-8 -*-
r"""检查启动器所有玩家可见文案的宽度，超宽就报错。

为什么需要：`DrawTxt()` 用 `RectF(x, y, 0, 0)` —— 宽度给 0 表示"不约束"，
GDI+ 会把整句画成**一行**，太长就直接顶出窗口右边、被裁掉（界面上看起来
文字凭空断掉）。这个坑真的踩过：「用 LanguageBarrier 重定向模型归档…」那段。

两道防线：
  1) 本脚本量像素宽度，超宽即报错（不靠肉眼估）
  2) 长文案改用 `DrawTxtW(..., wrapW)`，超长会自动折行

宽度用界面同款字体（F(12) 走 g_ff，通常是 Microsoft YaHei UI）实算。

用法:
    python scripts/diagnostics/audit_label_width.py          # 检查
    python scripts/diagnostics/audit_label_width.py --list   # 顺带列出全部宽度
"""
import io
import os
import re
import sys

from PIL import ImageFont

sys.stdout.reconfigure(encoding="utf-8")

SRC = r"D:\DATA\tran\agent tran\9.6文本外工作\launcher\RNDZhLauncher.cpp"

# ── 与源码一致的布局（逻辑像素）──
WIN_H = 620
RIGHT_W = 460
PAD_R = 32.0
LEFT_W = int(WIN_H * 540.0 / 720.0 + 0.5)   # 主题图 540x720
WIN_W = LEFT_W + RIGHT_W
RXL = LEFT_W + 36.0
RW = WIN_W - PAD_R
AVAIL = RW - RXL
# 标签行左边留出勾选框宽度（DrawTxt 从 r.X + 34 起画）
LABEL_INDENT = 34.0
LABEL_AVAIL = AVAIL - LABEL_INDENT

FONTS = ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc",
         "C:/Windows/Fonts/simhei.ttf"]


def font(px):
    for p in FONTS:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, px)
            except Exception:
                pass
    return ImageFont.load_default()


def main():
    show_all = "--list" in sys.argv
    src = io.open(SRC, encoding="utf-8").read()

    # 抓源码里的中文字符串字面量（跳过注释行）。
    # 先按"用在哪儿"分类，因为字号和可用宽度不同：
    #   *_HINT / OPT_HINT   → 说明行，12px，**已用 DrawTxtW 折行**（宽度不是硬约束）
    #   *_LABEL / 分区标题   → 单行文本，17px，必须放得下（不折行）
    hint_lines = set()
    for m in re.finditer(r'^\s*(?:static\s+)?(?:const\s+wchar_t\*|const char\*)\s+'
                         r'(\w*HINT\w*)\s*=', src, re.M):
        pass
    # 逐行扫，记录"这一行属于哪个变量"（含多行拼接的字符串）
    cur_var = None
    kinds = {}          # 行号 → "hint" / "label"
    for i, line in enumerate(src.split("\n"), 1):
        st = line.strip()
        if st.startswith("//") or st.startswith("*"):
            kinds[i] = "comment"
            continue
        m = re.match(r'^(?:static\s+)?(?:const\s+wchar_t\*\s+)?(\w+)\s*(\[\d+\])?\s*=', st)
        if m and st.endswith(("=", "{")) or (m and "=" in st):
            cur_var = m.group(1)
        # 声明区里 OPT_LABEL / OPT_HINT 都在数组里；用变量名判断
        if cur_var:
            if "HINT" in cur_var:
                kinds[i] = "hint"
            else:
                kinds[i] = "label"
        else:
            kinds[i] = "label"
        if st.endswith(";"):
            cur_var = None

    items = []
    for i, line in enumerate(src.split("\n"), 1):
        if kinds.get(i) == "comment":
            continue
        # MessageBox 的文案不受右栏宽度约束（对话框会自己撑开），跳过
        if "MessageBoxW" in line or "MessageBox(" in line:
            continue
        for m in re.finditer(r'L"((?:[^"\\]|\\.)*)"', line):
            s = m.group(1)
            if any(u'\u4e00' <= c <= u'\u9fff' for c in s) and len(s) > 6:
                items.append((i, s, kinds.get(i, "label")))

    f12 = font(12)
    f17 = font(17)
    print("右栏可用 %.0f px（单行标签再扣勾选框 → %.0f px）" % (AVAIL, LABEL_AVAIL))
    print("说明行 12px + 自动折行用 DrawTxtW；单行标签 17px 必须放得下")
    print()
    print("%-5s %-5s %-6s %-6s  %s" % ("行", "类型", "宽度", "可用", "文案"))
    print("-" * 104)

    bad = []
    for ln, s, kind in items:
        if kind == "hint":
            w, avail = f12.getlength(s), AVAIL   # 折行：只报宽度，不算违规
        else:
            w, avail = f17.getlength(s), LABEL_AVAIL
        over = (w > avail)
        if over or show_all:
            print("%-5d %-5s %-6.0f %-6.0f  %s%s"
                  % (ln, "说明" if kind == "hint" else "标签", w, avail, s,
                     "   ← 超宽!" if over else ""))
        if over:
            bad.append((ln, s, kind, w, avail))

    print()
    if bad:
        print("★ 有 %d 条超宽（会被窗口裁掉）：" % len(bad))
        for ln, s, kind, w, a in bad:
            print("   行 %d（%s）：超出 %.0f px —— %s"
                  % (ln, "说明" if kind == "hint" else "标签", w - a, s))
        print()
        print("  处理办法：① 精简文案；② 该处改用 DrawTxtW(..., RW-RXL) 自动折行。")
        sys.exit(1)
    print("✓ 单行标签都在宽度内；说明行已用 DrawTxtW 自动折行")


if __name__ == "__main__":
    main()
