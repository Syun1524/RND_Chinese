# -*- coding: utf-8 -*-
"""把 .ico 替换进一个 PE 文件的图标资源（用 Win32 资源 API，最可靠）。

用途：7z.sfx 外壳自带 7-Zip 图标；安装包 exe 的外壳就是它，
需要换成我们自己的图标，玩家在资源管理器里看到的才是我们的图标。

做法：BeginUpdateResource / UpdateResource(RT_ICON + RT_GROUP_ICON) / EndUpdateResource。
"""
import ctypes
import os
import struct
import sys
from ctypes import wintypes

k32 = ctypes.WinDLL('kernel32', use_last_error=True)

RT_ICON = 3
RT_GROUP_ICON = 14

k32.BeginUpdateResourceW.argtypes = [wintypes.LPCWSTR, wintypes.BOOL]
k32.BeginUpdateResourceW.restype = wintypes.HANDLE
k32.UpdateResourceW.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.LPVOID,
                                wintypes.WORD, wintypes.LPVOID, wintypes.DWORD]
k32.UpdateResourceW.restype = wintypes.BOOL
k32.EndUpdateResourceW.argtypes = [wintypes.HANDLE, wintypes.BOOL]
k32.EndUpdateResourceW.restype = wintypes.BOOL


def read_ico(path):
    b = open(path, 'rb').read()
    resv, typ, cnt = struct.unpack('<HHH', b[:6])
    assert resv == 0 and typ == 1, 'not an ICO file'
    imgs = []
    for i in range(cnt):
        o = 6 + i * 16
        w, h, cc, r, pl, bpp, sz, off = struct.unpack('<BBBBHHII', b[o:o + 16])
        imgs.append({'w': w or 256, 'h': h or 256, 'cc': cc, 'planes': pl or 1,
                     'bpp': bpp or 32, 'data': b[off:off + sz]})
    return imgs


def build_group(imgs):
    """构造 RT_GROUP_ICON 数据：GRPICONDIR + 每项 GRPICONDIRENTRY"""
    out = bytearray(struct.pack('<HHH', 0, 1, len(imgs)))
    for i, im in enumerate(imgs):
        w = 0 if im['w'] >= 256 else im['w']
        h = 0 if im['h'] >= 256 else im['h']
        out += struct.pack('<BBBBHHIH', w, h, im['cc'], 0,
                           im['planes'], im['bpp'], len(im['data']), i + 1)
    return bytes(out)


def replace_icons(pe_path, ico_path, out_path=None):
    imgs = read_ico(ico_path)
    print('图标: %s  尺寸 %s' % (ico_path, ['%dx%d' % (i['w'], i['h']) for i in imgs]))

    tmp = pe_path + '.tmpicon'
    if os.path.exists(tmp):
        os.remove(tmp)
    # 复制一份再改（保留原 sfx 不动）
    with open(pe_path, 'rb') as s, open(tmp, 'wb') as d:
        d.write(s.read())

    h = k32.BeginUpdateResourceW(tmp, False)
    if not h:
        sys.exit('BeginUpdateResource 失败: %d' % ctypes.get_last_error())

    ok = True
    for i, im in enumerate(imgs):
        buf = im['data']
        arr = (ctypes.c_char * len(buf)).from_buffer_copy(buf)
        if not k32.UpdateResourceW(h, ctypes.c_wchar_p(RT_ICON),
                                   ctypes.c_wchar_p(i + 1), 0,
                                   ctypes.cast(arr, wintypes.LPVOID), len(buf)):
            print('  尺寸 %dx%d 写入失败' % (im['w'], im['h']))
            ok = False

    grp = build_group(imgs)
    arr = (ctypes.c_char * len(grp)).from_buffer_copy(grp)
    if not k32.UpdateResourceW(h, ctypes.c_wchar_p(RT_GROUP_ICON),
                               ctypes.c_wchar_p(1), 0,
                               ctypes.cast(arr, wintypes.LPVOID), len(grp)):
        print('  RT_GROUP_ICON 写入失败')
        ok = False

    if not k32.EndUpdateResourceW(h, not ok):
        sys.exit('EndUpdateResource 失败: %d' % ctypes.get_last_error())

    final = out_path or pe_path
    os.replace(tmp, final)
    print('已写入: %s  (%d 字节)' % (final, os.path.getsize(final)))


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit('用法: patch_pe_icon.py <目标.exe> <图标.ico> [输出.exe]')
    replace_icons(sys.argv[1], sys.argv[2],
                  sys.argv[3] if len(sys.argv) > 3 else None)
