# RND_Chinese
Chinese localization of Robotics;Notes DaSH. Based on the patch by Committee of Zero. Muchas gracias. Contact me if there is anything inappropriate.

## 仓库内容

| 目录 | 内容 |
|---|---|
| `cnscript/` | 中文译稿（`.msb.txt`）与中文码表 |
| `jpscript/` | 日文原版脚本（提取用基线） |
| `subs/` | 影片字幕 `.ass` 与歌词字体 |
| `LanguageBarrier_rndchs/` | LanguageBarrier 运行时源码 + 编译产物 |
| `sc3tools_jp/`、`sc3tools_rndchs/` | 日文提取 / 中文回写工具链 |
| `tools/`、`setup/` | 启动器、安装器、卸载器源码与构建脚本 |
| `图片汉化/` | **成品中文图集**（`bg/` `system/` `manual/`，与补丁包 `c0data/` 逐字节一致） |
| `scripts/` | 构建与部署脚本（`deploy_patch.py`、`gen_pkg_manifest.py` 等） |
| `docs/` | 交接文档、打包清单、设计说明 |

> `图片汉化/` 里的文件名带 `_zh` 后缀（便于与解包原图区分）；进补丁包时按
> `c0data.cls` 的原始资源名（去掉 `_zh`）落位，`scripts/rebuild_c0data.py` 负责这件事。

## sc3tools 版本说明 (IMPORTANT)

仓库里有两套 sc3tools,源码完全相同,唯一区别是编译时内嵌的 `resources/rnd/charset.utf8` 码表。**码表是 rust-embed 编译期打进 exe 的,改码表必须重新 `cargo build --release`,改完直接跑旧 exe 无效。**

- `sc3tools_rndchs/` — **中文版**。码表为汉化简体字码表 (13K, 4499 字, md5 `e62f5ca3...`),用于配合 `cnscript/` 译稿做中文回写 (replace-text)。
- `sc3tools_jp/` — **日文版**。码表为日文原版码表 (8.7K, 3020 字, md5 `6040d18f...`,即 `charset-.utf8` / `charset-备份.utf8`),用于提取日文原版脚本 (extract-text)。

**配对关系:日文包用日文版提取,中文回写用中文版。用错码表会得到大面积错码 (例如 `種子島` → `丽仁亿`,`海翔` → `ΥΦ`)。**

现成的 exe:
- `sc3tools_rndchs/target/release/sc3tools.exe` (934K, md5 `96cf7bb0...`) — 中文版
- `sc3tools_jp/target/release/sc3tools.exe` (921K, md5 `295b1c24...`) — 日文版

用法示例 (提取日文):
```
sc3tools_jp/target/release/sc3tools.exe extract-text "mes00.cpk/*.msb" rnd
```
输出会放在输入文件同级的 `txt/` 子目录。
