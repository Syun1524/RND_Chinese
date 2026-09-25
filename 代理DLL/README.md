# 代理 DLL（Proxy DLLs）

本目录存放补丁运行时注入游戏所必需的**代理 DLL**，安装时会被复制到游戏根目录
（含分号路径的目录还会在「分号后片段同名子目录」里再放一份）。

## 文件

| 文件 | 大小 | 来源 | 说明 |
|---|---|---|---|
| `dinput8.dll` | — | 本项目编译 | **不在此目录**：见 `LanguageBarrier_rndchs/LanguageBarrier/dinput8-Release/` |
| `d3d9` | 3.2 MB | CoZ 补丁包（DXVK） | DXVK 的 d3d9 代理 |
| `d3d10` | 1.2 MB | CoZ 补丁包（DXVK） | DXVK 的 d3d10 代理 |
| `d3d10_1` | 1.2 MB | CoZ 补丁包（DXVK） | DXVK 的 d3d10_1 代理 |
| `d3d10core` | 1.1 MB | CoZ 补丁包（DXVK） | DXVK 的 d3d10core 代理 |
| `d3d11` | 3.4 MB | CoZ 补丁包（DXVK） | DXVK 的 d3d11 代理 |
| `dxgi` | 2.2 MB | CoZ 补丁包（DXVK） | DXVK 的 dxgi 代理 |
| `VSFilter.dll` | 1.6 MB | CoZ 补丁包（xy-VSFilter） | 影片字幕渲染（karaoke / 翻译字幕） |

## 为什么放这里

补丁包需要这些 DLL，但它们**不是我们的产出**，也不是从本仓库任何源码编译出来的：
它们是 Committee of Zero 英文补丁包里的现成二进制（DXVK / xy-VSFilter 的构建产物）。

以前它们只存在于工作区的 `成品ing/补丁包/`，**仓库里没有**。后果是：
从本仓库 clone 后无法重建一个完整可用的安装包 —— 编译链、文本、图片都能重建，
唯独这几个代理 DLL 没有来源。

所以归档在这里，作为「重建安装包所需的原件」。

## 与补丁包的一致性

补丁包里这几份与本目录**逐字节相同**（md5 见下表），可直接 `cp` 过去：

```
d3d9        d1b890a158aae2c0
d3d10       8fa05ddecdb1e8ec
d3d10_1     2bb411254ebd018c
d3d10core   2e4432169f38688a
d3d11       9a6c857cd032551f
dxgi        a093050c1cc30304
VSFilter.dll 9f1e0cd80184f554
```

> 注：`dinput8.dll` 是我们自己编译的（LanguageBarrier），不在本目录；
> 它随源码一起进版本控制，见 `LanguageBarrier_rndchs/LanguageBarrier/dinput8-Release/`。

## 许可

DXVK 与 xy-VSFilter 均为宽松许可（zlib / LGPL，允许再分发），
许可全文随补丁包发布：`languagebarrier/THIRDPARTY.patch.txt`、`THIRDPARTY.LB.txt`。
