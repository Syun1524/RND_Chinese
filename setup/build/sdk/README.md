# sdk/ —— 安装器版 SFX 模块（来自 LZMA SDK）

## 为什么需要这个目录

7-Zip 25.01 主程序自带的 `7z.sfx` / `7zCon.sfx` 是**纯解压模块**：
里面完全没有 `;!@Install@!` 那套机制，`config.txt` 会被整体忽略。
用它打包，双击后弹的是「Extract to:」对话框，玩家得自己解压、再手动找到
`RNDZhSetup.exe` 运行 —— 这就是之前"安装流程诡异"的原因。

**安装器版** SFX 是 `7zSD.sfx`（D = installer）。7-Zip 官方早已把它从主程序
移到 **LZMA SDK** 里分发，所以要从那里取。

## 文件来源

| 文件 | 来源 | 说明 |
|---|---|---|
| `7zSD.sfx` | lzma2501.7z → `bin/7zSD.sfx` | 官方安装器版 SFX 模块（128000 B） |
| `7zSD_custom.sfx` | `7zSD.sfx` + `game.ico` | 换成本项目图标（用 `../patch_pe_icon.py` 生成） |
| `7zr.exe` | lzma2501.7z → `bin/7zr.exe` | 官方示例用的压缩器，支持 `-mf=BCJ2` |
| `README-installer-sfx.txt` | lzma2501.7z → `DOC/installer.txt` | 官方文档原文（配置项说明） |

下载地址：`https://www.7-zip.org/a/lzma2501.7z`（LZMA SDK）

## 拼装方式（与官方 `bin/installer/cr.bat` 一致）

```
7zSD_custom.sfx  +  config.txt  +  payload.7z   →   RNDZh-Setup-v0.1.exe
```

由 `../build_installer.py` 自动完成。

## 两个必须保持的坑点

1. **模块必须是 `7zSD.sfx`**，不能用 `7z.sfx`（见上）。
2. **config 必须写真正的 CR LF**，不能是字面的反斜杠 r n。
   否则模块报 `Config failed` 并拒绝安装。
   `build_installer.py` 里有断言自检。

## 模块自带的好处

官方文档（`README-installer-sfx.txt`）：

> Such module extracts archive to temp folder and then runs specified program and
> **removes temp files after program finishing**.

即：**解压残留由模块自己清理**，装完不留 `%TEMP%\7zXXXXXXXX\`。
