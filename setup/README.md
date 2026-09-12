# setup/ —— 安装器与卸载器

| 路径 | 说明 |
|---|---|
| `src/` | 源文件：`RNDZhSetup.cpp`（安装器）、`RNDZhUninstall.cpp`（卸载器）、图标、manifest、.rc |
| `build/` | 构建脚本（`.bat`）+ `sdk/`（安装器版 SFX 模块，来自 LZMA SDK） |
| `../成品ing/setup/` | 工作区里的实际构建目录，产物 `RNDZh-Setup-v0.1.exe` 也生成在那里 |

## 构建

```bat
cd build
build_setup.bat        :: src\RNDZhSetup.cpp    -> bin\RNDZhSetup.exe
build_uninstall.bat    :: src\RNDZhUninstall.cpp -> bin\RNDZhUninstall.exe
build_installer.bat    :: 打成单文件 RNDZh-Setup-v0.1.exe（需要补丁包已就位）
```

中间产物（`.obj` / `.res`）写在 `%TEMP%`，源码树不会落垃圾。

## 关键设计（踩过的坑）

1. **SFX 模块必须是 `7zSD.sfx`**（在 `build/sdk/`，取自 LZMA SDK）。
   7-Zip 25.01 主程序自带的 `7z.sfx` / `7zCon.sfx` 是**纯解压模块** ——
   没有 `;!@Install@!` 机制，config 会被整体忽略，双击弹「Extract to:」对话框，
   玩家得自己解压再手动找 setup 运行。
2. **SFX 配置必须写真正的 CR LF**，不能是字面的 `\r\n`；否则报 `Config failed`。
   `build_installer.py` 内有断言自检。
3. **两个程序都要 `requireAdministrator`** —— Steam 默认装在 `Program Files`，
   不提权写不进去。
4. **都支持 `/silent`**（无人值守、返回退出码），便于自动化验证。
5. **安装目标目录必须加引号传给安装器**：
   `RNDZhSetup.exe "<游戏目录>" /silent`。不加引号时，路径含空格会被
   `CommandLineToArgvW` 切断；安装器现在对此**明确失败返回 2**，
   而不是悄悄回退到自动探测目录（那会"装到别的目录却报成功"）。
