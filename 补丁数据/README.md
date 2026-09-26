# 补丁数据（Patch Data）

本目录存放**补丁包里那些"不是本项目编译/生成出来"的原件** —— 它们是组装一个
可运行安装包所必需的，但既不在本仓库任何源码里，也无法从别的素材重新生成。

分成两类：

## `运行时配置/`

进补丁包 `languagebarrier/` 的配置文件。**这些是人写的，不是生成的**，
是本仓库的「源头数据」之一（与 `cnscript/` 的译文同级）。

| 文件 | 作用 |
|---|---|
| `patchdef.json` | **补丁主配置**：码表（4550 字符）、字体路径、字号、`fileRedirection`（bg/system/movie/manual 全部重定向）、换行参数、启动器劫持名…… |
| `gamedef.json` | **SigScan 特征码**：所有 hook 的游戏内地址来源。游戏本体更新会让特征码失效，改这里 |
| `c0data.cls` | 图集归档索引。**行号即 `fileRedirection` 的值**，与 `patchdef.json` 是「matched pair」，改动必须成对 |
| `enscript.cls` | 文本归档索引（322 个 `.msb` 的文件名与顺序） |
| `defaultconfig.json` | 默认用户配置 |
| `versioninfo.json` | 版本号与更新检查 URL |
| `stringReplacementTable.bin` | 字符串替换表（当前为空占位，功能未启用） |

⚠️ **改 `patchdef.json` 或任一 `.cls` 之后**，必须跑工作区的
`scripts/deploy_patch.py`（它会重新解析每条重定向、报告落到类型不符的文件上的条目）。
历史上漏同步 `.cls` 出过「标题 UI 全白」事故 —— 下标前移导致重定向指到了角色模型。

⚠️ **改 `patchdef.json` 的 `base.charset` 之后**，字体种子会失效，
必须重烘并跑 `scripts/check_seed_fonts.py`（见 `docs/字体种子.md`）。

## `代理DLL/`

补丁运行时注入所需的代理 DLL（DXVK 的 `d3d9`/`d3d10`/`d3d10_1`/`d3d10core`/
`d3d11`/`dxgi` + xy-VSFilter 的 `VSFilter.dll`）。来自 Committee of Zero 英文补丁包，
**非本项目产出**，本仓库没有任何构建它们的源码。详见该目录 README。

> `dinput8.dll`（我们自己的运行时）不在此目录 —— 它由
> `LanguageBarrier_chs/LanguageBarrier/` 编译，产物在
> `LanguageBarrier_chs/LanguageBarrier/dinput8-Release/`。

## 与工作区的关系

这些文件的**权威副本在工作区** `9.6文本外工作/成品ing/补丁包/languagebarrier/`，
打包脚本（`build_installer.py`）从那里取件。本目录是**归档镜像**，
用于「从本仓库重建安装包」和版本追溯。

改动流程：先改工作区 → 验证 → 再把这里的副本同步过来。
（`patchdef.json` 与 `c0data.cls` 必须**一起**同步。）
