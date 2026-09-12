# 废弃图片（不再随补丁发布）

这里是从补丁包里**撤下来**的汉化图，以及作者标记为「废弃」的图。
图片不随补丁发布，也不被 `fileRedirection` 引用，仅作留存备查。

来源：`临时/cn/汉化好的/bg/废弃/`（用户标记不要的），
其中一部分**曾经上线过**，已连 `fileRedirection` 一起撤掉（游戏显示原版图）。

## 撤回记录（2026-09-12）

以下条目当时是**生效中**的重定向，按用户要求「废弃的就不要了」撤下。
撤下时 `c0data.cls` 一并重排（`fileRedirection` 存的是数组下标，
删行不重排会让后面所有下标错位）。

| 归档文件名（原名） | 曾用的 c0data 名 | 曾对应的归档/fileId |
|---|---|---|
| `rnd_ibg058b_zh.png` | `rnd_ibg058b.png` | bg / 252 |
| `rnd_ibg083a_zh.png` | `rnd_ibg083a.png` | bg / 285 |
| `movie_dar005b_zh.png` | `movie_dar005b_last.png` | bg / 420 |
| `movie_dar005c_zh.png` | `movie_dar005c_last.png` | bg / 421 |
| `movie_dar005d_zh.png` | `movie_dar005d_last.png` | bg / 422 |
| `movie_dar005e_zh.png` | `movie_dar005e_last.png` | bg / 423 |
| `movie_dar005f_zh.png` | `movie_dar005f_last.png` | bg / 424 |
| `movie_dar005g_zh.png` | `movie_dar005g_last.png` | bg / 425 |
| `movie_dar005h_zh.png` | `movie_dar005h_last.png` | bg / 426 |
| `movie_dar013_zh.png` | `movie_dar013_last.png` | bg / 427 |

> `rnd_ibg058a` 虽在 `废弃/` 里也有一份，但顶层有同内容的 `重做` 版，**保留未撤**。

其余文件（`rnd_ibg02*a` / `02*b` / `04*a` / `054a` / `064*` / `135*` /
`也许不需要（纯gpt跑的）rnd_ibg070a`）从未上线，只是留档。

## 相关脚本

- `scripts/drop_deprecated.py` —— 撤下 + 归档（幂等，内容重复不重复存放）
- `scripts/sync_images.py` —— 成品图同步（源 → 镜像 → c0data）

本目录被 `build_installer.py` 与 `gen_pkg_manifest.py` 排除，**不会进玩家拿到的安装包**。
