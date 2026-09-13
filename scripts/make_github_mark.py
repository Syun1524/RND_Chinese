# -*- coding: utf-8 -*-
r"""把官方 GitHub 标志的 SVG path 转成 GDI+ GraphicsPath 的 C++ 代码。

用法:
    python scripts/make_github_mark.py > tmp_github_mark.inc

为什么不用 PNG / ICO：这个标志是「实心圆 + 中间镂空的猫形」，靠**单条闭合轮廓
的非零环绕填充**（nonzero winding）形成镂空 —— 位图要么得带透明通道做遮罩，
要么自己写扫描线填充。GDI+ 的 GraphicsPath 设 FillModeWinding 直接就画对了，
而且任意缩放都不糊（启动器按钮尺寸随 DPI 变）。

输出的函数坐标是参数化的（ox / oy / s），调用方按目标矩形给值即可。
path 数据取自 GitHub 官方 octicon `mark-github`（16x16 视图框）。

★ 生成结果已内联进 launcher/RNDZhLauncher.cpp，**不要手改那段代码**；
  要调整就改这里的 PATH 再重新生成。
"""
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

# GitHub 官方 octicon mark-github（16x16）
PATH = "M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z"

TOK = re.compile(r"([MmLlHhVvCcSsQqTtAaZz])"
                 r"|(-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)")


def tokenize(d):
    out = []
    for m in TOK.finditer(d):
        if m.group(1):
            out.append(("c", m.group(1)))
        else:
            out.append(("n", float(m.group(2))))
    return out


def arc_to_center(x1, y1, rx, ry, phi_deg, laf, sf, x2, y2):
    """SVG 端点式圆弧 → 圆心式。返回 (cx, cy, rx, ry, start_deg, sweep_deg)。"""
    import math
    if rx == 0 or ry == 0:
        return None
    rx, ry = abs(rx), abs(ry)
    phi = math.radians(phi_deg)
    dx2, dy2 = (x1 - x2) / 2.0, (y1 - y2) / 2.0
    x1p = math.cos(phi) * dx2 + math.sin(phi) * dy2
    y1p = -math.sin(phi) * dx2 + math.cos(phi) * dy2
    lam = x1p * x1p / (rx * rx) + y1p * y1p / (ry * ry)
    if lam > 1:
        s = math.sqrt(lam)
        rx *= s
        ry *= s
    num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
    den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    co = math.sqrt(max(0.0, num / den)) if den else 0.0
    if laf == sf:
        co = -co
    cxp = co * rx * y1p / ry
    cyp = -co * ry * x1p / rx
    cx = math.cos(phi) * cxp - math.sin(phi) * cyp + (x1 + x2) / 2.0
    cy = math.sin(phi) * cxp + math.cos(phi) * cyp + (y1 + y2) / 2.0

    def ang(ux, uy, vx, vy):
        d = (ux * vx + uy * vy) / (math.hypot(ux, uy) * math.hypot(vx, vy))
        d = max(-1.0, min(1.0, d))
        a = math.acos(d)
        if ux * vy - uy * vx < 0:
            a = -a
        return a

    ux, uy = (x1p - cxp) / rx, (y1p - cyp) / ry
    vx, vy = (-x1p - cxp) / rx, (-y1p - cyp) / ry
    t1 = ang(1, 0, ux, uy)
    dt = ang(ux, uy, vx, vy)
    if not sf and dt > 0:
        dt -= 2 * math.pi
    elif sf and dt < 0:
        dt += 2 * math.pi
    return cx, cy, rx, ry, math.degrees(t1), math.degrees(dt)


def parse(d):
    toks = tokenize(d)
    i = 0
    cx = cy = sx = sy = 0.0
    pc2 = None
    pcmd = None
    segs = []

    def num():
        nonlocal i
        v = toks[i][1]
        i += 1
        return v

    while i < len(toks):
        k, v = toks[i]
        if k == "c":
            cmd = v
            i += 1
            if cmd in "Zz":
                segs.append(("close",))
                cx, cy = sx, sy
                pc2 = None
                pcmd = cmd
                continue
        else:
            # 隐式重复上一个命令；M 之后的隐式命令是 L（SVG 规定）
            if pcmd == "M":
                cmd = "L"
            elif pcmd == "m":
                cmd = "l"
            else:
                cmd = pcmd

        rel = cmd.islower()
        u = cmd.upper()
        if u == "M":
            x, y = num(), num()
            if rel:
                x += cx
                y += cy
            cx, cy = x, y
            sx, sy = x, y
            segs.append(("move", x, y))
        elif u == "L":
            x, y = num(), num()
            if rel:
                x += cx
                y += cy
            segs.append(("line", x, y))
            cx, cy = x, y
        elif u == "H":
            x = num()
            if rel:
                x += cx
            segs.append(("line", x, cy))
            cx = x
        elif u == "V":
            y = num()
            if rel:
                y += cy
            segs.append(("line", cx, y))
            cy = y
        elif u == "C":
            x1, y1, x2, y2, x, y = (num() for _ in range(6))
            if rel:
                x1 += cx; y1 += cy; x2 += cx; y2 += cy; x += cx; y += cy
            segs.append(("bez", x1, y1, x2, y2, x, y))
            pc2 = (x2, y2)
            cx, cy = x, y
        elif u == "S":
            x2, y2, x, y = (num() for _ in range(4))
            if rel:
                x2 += cx; y2 += cy; x += cx; y += cy
            if pcmd and pcmd.upper() in "CS" and pc2:
                x1, y1 = 2 * cx - pc2[0], 2 * cy - pc2[1]
            else:
                x1, y1 = cx, cy
            segs.append(("bez", x1, y1, x2, y2, x, y))
            pc2 = (x2, y2)
            cx, cy = x, y
        elif u == "A":
            rx, ry, rot, laf, sf, x, y = (num() for _ in range(7))
            if rel:
                x += cx
                y += cy
            a = arc_to_center(cx, cy, rx, ry, rot, int(laf), int(sf), x, y)
            if a is None:
                segs.append(("line", x, y))
            else:
                segs.append(("arc",) + a)
            cx, cy = x, y
            pc2 = None
        else:
            raise SystemExit("不支持的 SVG 命令: %s" % cmd)
        pcmd = cmd
    return segs


def fmt(v):
    s = "%.3f" % v
    s = s.rstrip("0").rstrip(".")
    if s in ("", "-0", "-"):
        s = "0"
    return s


# ★ 浮点字面量必须写成 `4.f` 而不是 `4f` —— `4f` 不是合法 C++ 字面量
#   （会报 C3688 文本后缀无效）。整数值得补一个小数点。
def fl(v):
    s = fmt(v)
    if "." not in s and "e" not in s and "E" not in s:
        s += "."
    return s


# ★ 必须带 f 后缀：不带的话字面量是 double，GraphicsPath 的
#   AddLine/AddBezier/AddArc 都有 REAL(float) 与 INT 两套重载，
#   混着 float 变量传会报 C2668 重载不明确。
def X(v):
    if abs(v) < 1e-9:
        return "ox"
    return "ox + s*%sf" % fl(v) if v > 0 else "ox - s*%sf" % fl(-v)


def Y(v):
    if abs(v) < 1e-9:
        return "oy"
    return "oy + s*%sf" % fl(v) if v > 0 else "oy - s*%sf" % fl(-v)


def SC(v):
    if abs(v) < 1e-9:
        return "0.f"
    return "s*%sf" % fl(v) if v > 0 else "-s*%sf" % fl(-v)


def N(v):
    return fl(v) + "f"


def main():
    segs = parse(PATH)
    print("// ── GitHub 标志（octicon mark-github，16x16 视图框）──")
    print("// ★ 本函数由 scripts/make_github_mark.py 从官方 SVG path 生成，**不要手改**；")
    print("//   要调整请改脚本里的 PATH 再重新生成。")
    print("// 单条闭合轮廓 + 非零环绕填充（FillModeWinding）形成中间镂空的猫形 ——")
    print("// 位图做不到这点（要么带透明遮罩，要么自己写扫描线填充），")
    print("// GraphicsPath 直接就能画对，而且任意缩放都清晰。")
    print("static void GithubMarkPath(GraphicsPath& p, float ox, float oy, float s) {")
    print("  p.SetFillMode(FillModeWinding);")
    # ★ GDI+ 的 AddBezier 要**显式给全部 4 个点**（起点 + 两个控制点 + 终点），
    #   它不会从"当前点"续画（这点和 AddLine 的两参重载不同）。
    #   所以这里自己跟一个 cur 记录当前点，把起点补上。
    cur = (0.0, 0.0)
    start = (0.0, 0.0)
    for sg in segs:
        if sg[0] == "move":
            print("  p.StartFigure();")
            cur = start = (sg[1], sg[2])
        elif sg[0] == "line":
            print("  p.AddLine(%s, %s);" % (X(sg[1]), Y(sg[2])))
            cur = (sg[1], sg[2])
        elif sg[0] == "bez":
            print("  p.AddBezier(%s, %s, %s, %s, %s, %s, %s, %s);"
                  % (X(cur[0]), Y(cur[1]), X(sg[1]), Y(sg[2]),
                     X(sg[3]), Y(sg[4]), X(sg[5]), Y(sg[6])))
            cur = (sg[5], sg[6])
        elif sg[0] == "arc":
            _, acx, acy, arx, ary, a0, asw = sg
            print("  p.AddArc(%s, %s, %s, %s, %s, %s);"
                  % (X(acx - arx), Y(acy - ary), SC(2 * arx), SC(2 * ary),
                     N(a0), N(asw)))
            import math
            a1 = math.radians(a0 + asw)
            cur = (acx + arx * math.cos(a1), acy + ary * math.sin(a1))
        elif sg[0] == "close":
            print("  p.CloseFigure();")
            cur = start
    print("}")
    print()
    print("// 段数自检：SVG 命令 %d 段" % len(segs))


if __name__ == "__main__":
    main()
