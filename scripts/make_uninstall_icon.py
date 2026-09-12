# -*- coding: utf-8 -*-
"""生成「卸载汉化」专用图标（与启动器的游戏封面图标明确区分，避免误点）。

为什么要单独一个图标：
    启动器 RNDZhLauncher.exe 用的是游戏封面图（色彩丰富），而卸载器原本跟它共用
    同一个 game.ico，两个 exe 摆在同一目录里图标一模一样 —— 玩家很容易点错，
    而点错的代价是「把汉化卸了」。所以卸载器必须一眼看出是"删东西"的那个。

设计（刻意扁平、无文字）：
    红底圆角方块 + 白色垃圾桶。红色=破坏性操作，垃圾桶=删除，语义直白；
    不做文字是因为 16×16 下汉字糊成一团，反而看不清。

输出：成品ing/setup/src/uninstall.ico（含 16/24/32/48/64/128/256 七档）
"""
import io
import os
import sys

from PIL import Image, ImageDraw

sys.stdout.reconfigure(encoding="utf-8")

OUT = r"D:\DATA\tran\agent tran\9.6文本外工作\成品ing\setup\src\uninstall.ico"
SIZES = [16, 24, 32, 48, 64, 128, 256]

# 红底（与安装器 C_ERR=(207,34,46) 同一族，但更饱和一点，小尺寸下更醒目）
TOP = (226, 62, 62)
BOT = (170, 28, 38)
WHITE = (255, 255, 255, 255)


def rounded(draw, box, rad, fill):
    draw.rounded_rectangle(box, radius=rad, fill=fill)


def make(size):
    # 4 倍超采样后缩下来，边缘才干净（小尺寸图标尤其明显）
    ss = 4
    n = size * ss
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 底：竖向渐变 + 圆角
    grad = Image.new("RGBA", (n, n))
    gd = ImageDraw.Draw(grad)
    for y in range(n):
        t = y / max(1, n - 1)
        gd.line([(0, y), (n, y)],
                fill=(int(TOP[0] + (BOT[0] - TOP[0]) * t),
                      int(TOP[1] + (BOT[1] - TOP[1]) * t),
                      int(TOP[2] + (BOT[2] - TOP[2]) * t), 255))
    mask = Image.new("L", (n, n), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, n - 1, n - 1],
                                          radius=int(n * 0.22), fill=255)
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)

    # 垃圾桶：盖（含提手） + 桶身（上宽下窄） + 两道竖缝
    # 比例都以 n 为基准，保证各尺寸一致
    lid_y = int(n * 0.30)
    lid_h = int(n * 0.075)
    lid_x0, lid_x1 = int(n * 0.26), int(n * 0.74)
    # 提手
    hw = int(n * 0.10)
    d.rounded_rectangle([int(n * 0.5) - hw, int(n * 0.205), int(n * 0.5) + hw,
                         lid_y + lid_h], radius=max(1, int(n * 0.022)), fill=WHITE)
    # 盖
    d.rounded_rectangle([lid_x0, lid_y, lid_x1, lid_y + lid_h],
                        radius=max(1, int(n * 0.018)), fill=WHITE)
    # 桶身（梯形：用多边形）
    body_y0 = lid_y + lid_h + int(n * 0.035)
    body_y1 = int(n * 0.82)
    bx = int(n * 0.315)
    taper = int(n * 0.035)
    d.polygon([(bx, body_y0), (n - bx, body_y0),
               (n - bx - taper, body_y1), (bx + taper, body_y1)], fill=WHITE)
    # 桶口连接块（让盖与桶身之间不留缝）
    d.rectangle([bx, body_y0 - int(n * 0.035), n - bx, body_y0], fill=WHITE)

    # 两道竖缝（挖空，露出红底）—— 太小的尺寸下不画，否则变成噪点
    if size >= 32:
        slit_w = max(2, int(n * 0.028))
        for cx in (0.43, 0.57):
            x = int(n * cx) - slit_w // 2
            d.rectangle([x, body_y0 + int(n * 0.075),
                         x + slit_w, body_y1 - int(n * 0.06)], fill=(0, 0, 0, 0))

    return img.resize((size, size), Image.LANCZOS)


images = [make(s) for s in SIZES]
os.makedirs(os.path.dirname(OUT), exist_ok=True)
images[-1].save(OUT, format="ICO",
                sizes=[(s, s) for s in SIZES], append_images=images[:-1])
print("已生成 %s" % OUT)
print("  尺寸: %s" % SIZES)
print("  大小: %.1f KB" % (os.path.getsize(OUT) / 1024))

# 顺手导一张预览图，方便肉眼确认
prev = os.path.join(os.path.dirname(OUT), "uninstall_preview.png")
sheet = Image.new("RGBA", (sum(SIZES) + 8 * len(SIZES), 256), (245, 246, 248, 255))
x = 8
for im in images:
    sheet.paste(im, (x, 256 - im.height - 8), im)
    x += im.width + 8
sheet.save(prev)
print("  预览: %s" % prev)
