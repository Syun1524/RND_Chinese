# _archive —— 归档原件（不注入游戏）

本目录存放**补丁包需要、但不是我们汉化产出的图片/影片**。它们原样进 `c0data/`，
用途是让 `c0data.cls` 的下标与 `patchdef.json → fileRedirection` 对齐。

⚠️ **这不是「汉化成品」目录**。汉化成品在上一级（`图片汉化/system/` 等），
命名带 `_zh` 后缀；本目录的文件**不带 `_zh`**，因为它们不是中文图。

## 文件

| 文件 | 尺寸 | 补丁包内名字 | 用途 |
|---|---|---|---|
| `RND_PC_controller_jp.png` | 1920×1080 | 同名 | 手柄操作说明图（**日文原版**，未汉化） |
| `RND_PC_keyboard_jp.png` | 1920×1080 | 同名 | 键盘操作说明图（**日文原版**，未汉化） |
| `guid_pc_jp.png` | 2048×2048 | 同名 | 指南图集（**日文原版**占位；汉化版 `guid_pc_zh.png` 与它大小相同） |
| `meswindow.png` | 2048×2048 | 同名 | 消息窗口底图（原版，无文字） |
| `_source_backup_extra_chip_EN_original.png` | — | 不注入 | **英文原版** `extra_chip` 图集备份，是 `qa_extra_chip_en.py` 门禁的比对母本（见 AGENTS「EXTRA 统计行」） |

## 为什么放这里

这四张图 + `movie_dar020.usm`（在 `视频汉化/`）原本只存在于工作区的
`成品ing/补丁包/languagebarrier/c0data/`，**仓库里没有**。
而它们在别处也没有副本 —— 一旦工作区丢失就无法重建。

`c0data.cls` 是**按行号索引**的归档清单，`fileRedirection` 里存的是数组下标。
删掉其中任何一项都必须重排 `.cls`，否则后面所有下标前移错位
（本项目出过「标题 UI 全白」事故）。所以这些占位文件不能省。

## 与补丁包的一致性

```
RND_PC_controller_jp.png     ffc1af1234d12988
RND_PC_keyboard_jp.png       720576955785e26f
guid_pc_jp.png               aa10e8bce3046541
meswindow.png                fdecd0c002011386
```

（md5 前 16 位；补丁包内路径为 `languagebarrier/c0data/<同名>`）

## 对应关系（`c0data.cls` 下标）

| 下标 | 文件 | 被谁指向 |
|---|---|---|
| 61 | `RND_PC_controller_jp.png` | `fileRedirection.manual` |
| 62 | `RND_PC_keyboard_jp.png` | `fileRedirection.manual` |
| 67 | `meswindow.png` | `fileRedirection.system` |
| 72 | `guid_pc_jp.png` | `fileRedirection.system` |
