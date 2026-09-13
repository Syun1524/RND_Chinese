// RNDZhLauncher — ROBOTICS;NOTES DaSH 简体中文补丁 启动器
// 原生 Win32 + GDI+，不依赖 Qt。布局：左品牌 / 右选项。
//
// 职责：
//   1. 读写 %LOCALAPPDATA%\Committee of Zero\RNDSteam\config.json 的开关
//   2. 「换装」= 全员切换到 和服/泳装/体操服/猫耳 四套主题之一（写 zzOutfitSet）
//   3. 「启用 DXVK」= 对游戏根目录下的 d3d9/d3d10/... 做改名（带/不带 .dll）
//   4. 「开始游戏」= 以 "Game.exe roboticsnotesd EN" 拉起游戏
//
// 编译：见 build_launcher.bat
//
// 换装写 zzOutfitSet（四套并列：和服/泳装/体操服/猫耳），不再用 CoZ 的 swimsuitPatch
// —— 那只表达"泳装"一种，且覆盖范围已被本机制完全包住（见 scripts/add_outfit_sets.py，
// 该脚本会把 swimsuitPatch 从 patchdef 里删掉）。
//
// 另外：换装核对（把某角色单独指向某套）是开发者工具，见 RNDZhOutfitTool.cpp。
// 它写的 zz_<角色>_<变体> 键排序在 zzOutfitSet 之后，所以能压过主题单独固定某个角色。

#define WIN32_LEAN_AND_MEAN
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <windowsx.h>
#include <objidl.h>
#include <gdiplus.h>
#include <shlobj.h>
#include <tlhelp32.h>
#include <string>
#include <vector>
#include <map>
#include <fstream>
#include <sstream>
#include <cwchar>

#pragma comment(lib, "gdiplus.lib")
#pragma comment(lib, "shell32.lib")

// 图标：编译时把 game.ico 嵌入 exe 资源（ID 101），窗口/任务栏都用它。
// 资源文件 launcher.rc 引用，见 build_launcher.bat。

// 注意：启动器【不】导入 DINPUT8.dll。
// 补丁的 dinput8.dll 是代理 DLL，由 Game.exe 自身（它静态导入 DINPUT8.dll）加载，
// 生效位置是「分号后片段同名」的子目录（路径含 `;` 时加载器按分号切开、把片段
// 当相对目录搜）；无分号的目录则直接用根目录那份。详见 AGENTS.md「重大发现」。
// 无论如何都与启动器无关。

using namespace Gdiplus;

// ───────────────────────── 配置（颜色/布局常量） ─────────────────────────
// 配色与安装器/卸载器保持一致（纯白极简）：白底、浅灰边框、深灰字、蓝色主按钮。
// 三个窗口是一套东西，色调必须统一 —— 启动器以前是深色霓虹风，跟安装器对不上。
//
// 布局：左栏是主题图（主视觉），右栏是选项。
// **左栏宽度按主题图的实际比例算**（见 ApplyThemeGeometry）：图有多宽，栏就多宽，
// 图按栏高等比缩放、正好铺满，不变形也不留黑边。换一张不同比例的图也不用改代码。
static int WIN_H  = 500;      // 窗口高（逻辑像素）——固定值，由它反推左栏宽
static int LEFT_W = 375;      // 左栏宽（初值是 540x720 算出来的，运行时按实际图覆盖）
static int WIN_W  = 800;      // 窗口宽 = 左栏 + 右栏(425)
static const int RIGHT_W = 425;   // 右栏固定宽度（放选项）

// 产品版本。⚠ 改版本要同步三处：这里、成品ing/setup/src/RNDZhSetup.cpp 的 VER、
// 成品ing/setup/build/build_installer.py 的 VERSION（决定包文件名）。
static const wchar_t* VER = L"1.0";
// 产品标题（用户要求结尾带版本号）。窗口标题与游戏窗口标题劫持共用这一份。
static const std::wstring APP_TITLE =
    std::wstring(L"ROBOTICS;NOTES DaSH 简体中文 AI人工精校版 v") + VER;

static const Color
  C_BG      (255, 255, 255, 255),   // 窗口底
  C_PANEL   (255, 245, 246, 248),   // 悬停底
  C_FIELD   (255, 255, 255, 255),   // 输入/下拉底色
  C_BORDER  (255, 216, 220, 227),   // 边框
  C_TEXT    (255,  31,  35,  40),   // 正文
  C_DIM     (255, 107, 114, 128),   // 次要文字
  C_MUTED   (255, 156, 163, 175),   // 更淡（禁用/提示）
  C_ACCENT  (255,  11, 107, 203),   // 主按钮 / 勾选态
  C_ACCENTH (255,  10,  95, 176),   // 主按钮悬停
  C_HILITE  (255, 236, 240, 245),   // 下拉项悬停底
  C_SEL     (255, 226, 238, 252),   // 下拉项"当前选中"底
  C_HOVER   (255, 233, 237, 242),   // 悬停底（下拉项/主按钮）——要比 C_HILITE 明显，
                                    // 否则玩家感觉"没有反馈"（2026-09-13 用户反馈）
  C_WHITE   (255, 255, 255, 255);

// ── DPI 缩放 ──
// 三个 exe 以前都没声明 DPI 感知，系统 125% 缩放时 Windows 会把整个界面
// 位图拉伸 1.25 倍 —— 文字发虚、边缘发糊（实测客户区 1125x775 而逻辑只有 900x620）。
// 现在声明「系统 DPI 感知」，并把绘制坐标统一乘 S：界面物理尺寸不变，但变清晰。
// 实现上用 GDI+ 的 ScaleTransform 一次性缩放坐标系，不用逐个坐标乘 ——
// 布局常量保持逻辑值，看源码仍能直接算。
static float S = 1.0f;                 // 缩放系数 = 窗口DPI / 96
static inline float unscale(int v) { return (float)v / S; }   // 鼠标坐标 → 逻辑坐标

// 设置项（「cosplay 模式」是下拉，不在这组复选里）
//
// ★ 标签措辞原则：功能就是功能，直说做什么；不写"（而不是键盘）""也可……"
//   这类绕弯解释，也不写实现术语。文案都对着 LB 源码的真实行为核过：
//
//   scrollDownToAdvanceText  → CustomInputRND.cpp:1808
//       `ScrollDownToAdvanceText && (mouseButtons & MouseScrollWheelDown) → PAD1A`
//       即**滚轮向下**推进文本。以前标签写"滚轮向上推进文本"是错的 ——
//       既与配置键名（scroll**Down**ToAdvanceText）相反，也与自己下面的灰字矛盾。
//   disableScrollDownToCloseBacklog → CustomInputRND.cpp:1211
//       `ScrollDownToCloseBacklog && 已翻到底 && ...(MouseScrollWheelDown) → PAD1B`
//       （PAD1B=返回）即**滚轮向下**在历史记录翻到底部时退出记录。
//   两个滚轮项的标签本身就是那句话，不再配灰字（2026-09-13 用户拍板：
//   「也可点左键或 Auto」这类补充是好笨的写法）。
enum Opt { OPT_MOUSE=0, OPT_SCROLL_ADV, OPT_SCROLL_CLOSE, OPT_DXVK, OPT_COUNT };
static const wchar_t* OPT_LABEL[OPT_COUNT] = {
  L"鼠标控制", L"滚轮向下推进文本", L"滚轮向下可退出历史记录", L"启用 DXVK"
};
static const wchar_t* OPT_KEY[OPT_COUNT] = {
  L"mouseControls", L"scrollDownToAdvanceText", L"disableScrollDownToCloseBacklog",
  L"enableDxvk"
};
static const wchar_t* OPT_HINT[OPT_COUNT] = {
  L"开启原版不支持的鼠标操作功能",
  L"",
  L"",
  L"用 Vulkan 转译渲染，缓解新显卡上的兼容问题"
};
// 注意：disableScrollDownToCloseBacklog 在配置里是"禁用"语义。
// 界面写正向「滚轮向下可退出历史记录」，勾选=启用该功能=写 false。
static bool OPT_INVERT[OPT_COUNT] = { false, false, true, false };
static bool OPT_DEF[OPT_COUNT]    = { true,  true,  true, false };

// ── cosplay 模式（界面名）──
// 玩家看到的叫「cosplay 模式」；实现上是全员换一套衣服。
// 值必须与 patchdef.json -> settings.zzOutfitSet.choices 的键一致。
// none = 保持原样（各角色穿默认服）。
static const wchar_t* OUTFIT_LABEL[5] = { L"原版", L"和服", L"泳装", L"体操服", L"猫耳" };
static const wchar_t* OUTFIT_VALUE[5] = { L"none", L"kimono", L"swimsuit", L"gym", L"nekomimi" };
static const int OUTFIT_N = 5;

// 下拉框下方那行灰字。**这是刻意写技术说明的地方**：
// 玩家问"为什么换个装就能改立绘"时，这行给出准确答案，
// 而不是"全员换成这套服装（各角色只换自己有的那套）"那种把玩家当傻子的废话。
//
// 实现细节（对着源码核过，别凭印象写）：
//   LB 的 mgsFileOpenHook 拦下模型归档的打开请求，按 fileIdRemap 把
//   「默认服装的 model fileId」重指向「目标服装的 fileId」；
//   命中即 return，不落到 fileRedirection。所以这是运行时重定向，不改任何游戏文件。
static const wchar_t* OUTFIT_HINT =
    L"LanguageBarrier 重定向模型归档，运行时切换该套立绘";

static const wchar_t* SUBS_LABEL[3] = { L"卡拉OK + 翻译", L"仅卡拉OK", L"仅翻译" };
static const wchar_t* SUBS_VALUE[3] = { L"all", L"karaonly", L"tlonly" };
static const wchar_t* SUBS_HINT = L"mv播放时叠加的字幕轨";

static const wchar_t* SET_KEY = L"zzOutfitSet";

struct State {
  bool on[OPT_COUNT];
  int  subs;            // 0/1/2
  int  outfit;          // 0..4
  int  comboOpen = -1;  // -1 无 / 0 subs / 1 outfit
  int  hot = -1;        // 悬停项，用与 press 同一套 id
  int  press = -1;
} st;

static HWND g_hwnd;
// 从 exe 资源加载 256x256 图标（RT_ICON 里最大的一个），供左侧品牌区绘制。
static Gdiplus::Bitmap* g_iconBmp = nullptr;
static void LoadAppIconFromResource() {
  if (g_iconBmp) return;
  int bestW = 0;
  for (int id = 1; id <= 8; id++) {
    HRSRC hr = FindResourceW(nullptr, MAKEINTRESOURCEW(id), MAKEINTRESOURCEW(3));
    if (!hr) continue;
    DWORD sz = SizeofResource(nullptr, hr);
    HGLOBAL hg = LoadResource(nullptr, hr);
    void* p = LockResource(hg);
    if (!p) continue;
    HICON ico = CreateIconFromResourceEx((PBYTE)p, sz, TRUE, 0x00030000, 0, 0, LR_DEFAULTCOLOR);
    if (!ico) continue;
    ICONINFO ii = { 0 };
    GetIconInfo(ico, &ii);
    BITMAP bm = { 0 };
    GetObject(ii.hbmColor, sizeof(bm), &bm);
    int W = bm.bmWidth, H = bm.bmHeight;
    if (W > bestW) {
      Gdiplus::Bitmap* b = new Gdiplus::Bitmap(W, H, PixelFormat32bppARGB);
      Graphics gg(b);
      HDC hdc = gg.GetHDC();
      DrawIconEx(hdc, 0, 0, ico, W, H, 0, nullptr, DI_NORMAL);
      gg.ReleaseHDC(hdc);
      if (b->GetLastStatus() == Ok) {
        if (g_iconBmp) delete g_iconBmp;
        g_iconBmp = b; bestW = W;
      } else delete b;
    }
    if (ii.hbmColor) DeleteObject(ii.hbmColor);
    if (ii.hbmMask) DeleteObject(ii.hbmMask);
    DestroyIcon(ico);
  }
}
// 左侧主题图（资源 ID 102，RCDATA 里是一份 JPEG）。
// 直接从内存流解码，不需要外部文件 —— 启动器被拷来拷去也不会丢图。
static Gdiplus::Bitmap* g_themeBmp = nullptr;

// 按主题图的**实际比例**反推左栏宽度与窗口尺寸。
// 换一张不同比例的图（比如 16:9 的宽幅主视觉）不用改任何常量 —— 这里会自己算。
// 必须在建窗口之前调用（窗口尺寸取决于它）。
static void ApplyThemeGeometry() {
  if (g_themeBmp) {
    int iw = (int)g_themeBmp->GetWidth();
    int ih = (int)g_themeBmp->GetHeight();
    if (iw > 0 && ih > 0) {
      // 图按「窗口高」等比缩放到左栏宽；四舍五入免得差一像素露白边
      LEFT_W = (int)((double)WIN_H * iw / ih + 0.5);
    }
  }
  WIN_W = LEFT_W + RIGHT_W;
}

static FontFamily* g_ff = nullptr;   // 从系统字体取（中文正文）
// 主按钮英文用的字体：Bahnschrift（DIN 1451 的后继，Win10+ 自带），
// 工业感/机械感贴 ROBOTICS;NOTES 的气质。找不到依次退 Segoe UI / Arial，
// 最后退中文字体 —— 任何机器上都不会画不出来。
static FontFamily* g_ffTech = nullptr;
static std::wstring g_dir;           // 启动器所在目录

static void LoadThemeImage() {
  HRSRC hr = FindResourceW(nullptr, MAKEINTRESOURCEW(102), RT_RCDATA);
  if (!hr) return;
  DWORD sz = SizeofResource(nullptr, hr);
  HGLOBAL hg = LoadResource(nullptr, hr);
  if (!hg || !sz) return;
  void* p = LockResource(hg);
  if (!p) return;
  // GDI+ 需要一个 IStream：把资源字节包成内存流交给 Bitmap
  HGLOBAL hMem = GlobalAlloc(GMEM_MOVEABLE, sz);
  if (!hMem) return;
  void* dst = GlobalLock(hMem);
  memcpy(dst, p, sz);
  GlobalUnlock(hMem);
  IStream* is = nullptr;
  if (SUCCEEDED(CreateStreamOnHGlobal(hMem, TRUE, &is)) && is) {
    Gdiplus::Bitmap* b = new Gdiplus::Bitmap(is);
    if (b->GetLastStatus() == Ok) g_themeBmp = b;
    else delete b;
    is->Release();
  } else {
    GlobalFree(hMem);
  }
}

// ───────────────────────── 小工具 ─────────────────────────
static std::wstring ExeDir() {
  wchar_t buf[MAX_PATH]; GetModuleFileNameW(nullptr, buf, MAX_PATH);
  std::wstring s(buf); size_t p = s.find_last_of(L'\\');
  return p == std::wstring::npos ? L"." : s.substr(0, p);
}

static bool FileExists(const std::wstring& p) {
  return GetFileAttributesW(p.c_str()) != INVALID_FILE_ATTRIBUTES;
}

static std::wstring Utf8ToWide(const std::string& s) {
  if (s.empty()) return L"";
  int n = MultiByteToWideChar(CP_UTF8, 0, s.c_str(), (int)s.size(), nullptr, 0);
  std::wstring w(n, 0);
  MultiByteToWideChar(CP_UTF8, 0, s.c_str(), (int)s.size(), &w[0], n);
  return w;
}

static std::string WideToUtf8(const std::wstring& w) {
  if (w.empty()) return "";
  int n = WideCharToMultiByte(CP_UTF8, 0, w.c_str(), (int)w.size(), nullptr, 0, nullptr, nullptr);
  std::string s(n, 0);
  WideCharToMultiByte(CP_UTF8, 0, w.c_str(), (int)w.size(), &s[0], n, nullptr, nullptr);
  return s;
}

// 读文件为 UTF-8 → wstring 简易解析（只取顶层平铺键值）
static std::map<std::wstring, std::wstring> LoadFlatJson(const std::wstring& path) {
  std::map<std::wstring, std::wstring> m;
  std::ifstream f(path, std::ios::binary);
  if (!f) return m;
  std::stringstream ss; ss << f.rdbuf();
  std::string s = ss.str();
  size_t i = 0;
  while (i < s.size()) {
    size_t q1 = s.find('"', i);
    if (q1 == std::string::npos) break;
    size_t q2 = s.find('"', q1 + 1);
    if (q2 == std::string::npos) break;
    size_t colon = s.find(':', q2 + 1);
    if (colon == std::string::npos) break;
    std::string key = s.substr(q1 + 1, q2 - q1 - 1);
    size_t j = colon + 1;
    while (j < s.size() && isspace((unsigned char)s[j])) j++;
    size_t vstart = j; bool instr = false;
    if (j < s.size() && s[j] == '"') { instr = true; j++; }
    while (j < s.size()) {
      if (instr) { if (s[j] == '\\') { j += 2; continue; } if (s[j] == '"') { j++; break; } }
      else { if (s[j] == ',' || s[j] == '}' || s[j] == '\n') break; }
      j++;
    }
    m[Utf8ToWide(key)] = Utf8ToWide(s.substr(vstart, j - vstart));
    size_t nxt = s.find(',', j);
    i = (nxt == std::string::npos) ? s.size() : nxt + 1;
    if (s.find('}', j) != std::string::npos && s.find('}', j) < nxt) break;
  }
  return m;
}

static std::wstring ConfigPath() {
  wchar_t* appdata = nullptr;
  SHGetKnownFolderPath(FOLDERID_LocalAppData, 0, nullptr, &appdata);
  std::wstring p = appdata ? appdata : L"";
  if (appdata) CoTaskMemFree(appdata);
  p += L"\\Committee of Zero\\RNDSteam";
  return p;
}

static void EnsureDir(const std::wstring& dir) {
  SHCreateDirectoryExW(nullptr, dir.c_str(), nullptr);
}

// 写配置：整份重写，未知键原样带上。
// 换装核对工具写的 zz_<角色>_<变体> 属于未知键 → 会被保留，
// 玩家在这里改开关不会把开发工具的当前核对项清掉。
static void SaveConfig() {
  std::wstring dir = ConfigPath();
  EnsureDir(dir);
  std::wstring path = dir + L"\\config.json";

  auto old = LoadFlatJson(path);

  std::wstringstream out;
  out << L"{\n";
  auto b = [](bool v) { return v ? L"true" : L"false"; };
  bool first = true;
  auto emit = [&](const std::wstring& k, const std::wstring& v) {
    if (!first) out << L",\n";
    first = false;
    out << L"    \"" << k << L"\": " << v;
  };
  emit(L"__schema_version", L"5");
  for (int i = 0; i < OPT_COUNT; i++) {
    bool v = st.on[i];
    if (OPT_INVERT[i]) v = !v;            // 界面正向 → 配置语义
    emit(OPT_KEY[i], b(v));
  }
  emit(SET_KEY, std::wstring(L"\"") + OUTFIT_VALUE[st.outfit] + L"\"");
  emit(L"karaokeSubs", std::wstring(L"\"") + SUBS_VALUE[st.subs] + L"\"");
  emit(L"showAllSettings", L"true");
  emit(L"rneMouseControls", L"true");
  static const wchar_t* MINE[] = { L"__schema_version", L"mouseControls",
    L"scrollDownToAdvanceText", L"disableScrollDownToCloseBacklog",
    SET_KEY, L"enableDxvk", L"karaokeSubs", L"showAllSettings", L"rneMouseControls" };
  for (auto& kv : old) {
    bool mine = false;
    for (auto m : MINE) if (kv.first == m) { mine = true; break; }
    if (mine || kv.first.empty()) continue;
    // 丢掉除 zzOutfitSet 外的所有 zz* 键：
    //  - zz_<角色>_<变体>：核对工具的固定项。它排序在 zzOutfitSet 之后，会把对应
    //    角色压过主题（选了「和服」但那几个角色不换），玩家的"一键切换"就废了。
    //  - swimsuitPatch：CoZ 的老键，patchdef 里已删除（四套并列，泳装不再特殊）。
    //  - zzOutfitOverride：更早的单选机制残留。
    // 这三者都是开发/历史状态，不该跟着成品走。
    if (kv.first.rfind(L"zz", 0) == 0 && kv.first != SET_KEY) continue;
    if (kv.first == L"swimsuitPatch") continue;
    emit(kv.first, kv.second);
  }
  out << L"\n}";

  std::string u8 = WideToUtf8(out.str());
  std::ofstream f(path, std::ios::binary | std::ios::trunc);
  f.write(u8.data(), u8.size());
}

static void LoadConfig() {
  std::wstring path = ConfigPath() + L"\\config.json";
  auto m = LoadFlatJson(path);
  auto getb = [&](const wchar_t* k, bool dflt) {
    auto it = m.find(k); if (it == m.end()) return dflt;
    return it->second.find(L"true") != std::wstring::npos;
  };
  for (int i = 0; i < OPT_COUNT; i++) {
    bool v = getb(OPT_KEY[i], OPT_DEF[i]);
    if (OPT_INVERT[i]) v = !v;
    st.on[i] = v;
  }
  st.subs = 0;
  auto it = m.find(L"karaokeSubs");
  if (it != m.end())
    for (int i = 0; i < 3; i++)
      if (it->second.find(SUBS_VALUE[i]) != std::wstring::npos) st.subs = i;

  st.outfit = 0;                          // 默认「原版」，不换装
  auto sit = m.find(SET_KEY);
  if (sit != m.end())
    for (int i = 0; i < OUTFIT_N; i++)
      if (sit->second.find(OUTFIT_VALUE[i]) != std::wstring::npos) { st.outfit = i; break; }
}

// DXVK：d3d9/d3d10/d3d10_1/d3d10core/d3d11/dxgi 带/不带 .dll
// 必须与 Game.exe 同目录（游戏根目录）才会被 Windows 加载。
static const wchar_t* DXVK_NAMES[6] = { L"d3d9", L"d3d10", L"d3d10_1", L"d3d10core", L"d3d11", L"dxgi" };

static void ApplyDxvk(bool enable) {
  std::wstring dir = g_dir;
  for (int i = 0; i < 6; i++) {
    std::wstring base = dir + L"\\" + DXVK_NAMES[i];
    std::wstring withdll = base + L".dll", nodll = base;
    if (enable) { if (FileExists(nodll) && !FileExists(withdll)) MoveFileW(nodll.c_str(), withdll.c_str()); }
    else        { if (FileExists(withdll) && !FileExists(nodll)) MoveFileW(withdll.c_str(), nodll.c_str()); }
  }
}

// ───────────────────────── 绘制 ─────────────────────────
static Font* F(float sz, bool bold = false) {
  static std::map<std::pair<int,bool>, Font*> cache;
  auto key = std::make_pair((int)(sz * 10), bold);
  auto it = cache.find(key);
  if (it != cache.end()) return it->second;
  Font* f = new Font(g_ff, sz, bold ? FontStyleBold : FontStyleRegular, UnitPixel);
  cache[key] = f; return f;
}

// 主按钮英文字（g_ffTech），同样缓存
static Font* FTech(float sz, bool bold = true) {
  static std::map<std::pair<int,bool>, Font*> cache;
  auto key = std::make_pair((int)(sz * 10), bold);
  auto it = cache.find(key);
  if (it != cache.end()) return it->second;
  Font* f = new Font(g_ffTech, sz, bold ? FontStyleBold : FontStyleRegular, UnitPixel);
  cache[key] = f; return f;
}

// 逐字排 + 固定字距，在 r 内水平垂直居中。
// GDI+ 没有字距（tracking）概念，整串 DrawString 排出来太挤，
// 「START!」这种按钮字逐字摆才有科技感。
static void DrawTrackedCentered(Graphics& g, const wchar_t* s, Font* f,
                                const Color& c, const RectF& r, float track) {
  int n = (int)wcslen(s);
  if (n <= 0 || n > 32) return;
  float ws[32], total = 0;
  StringFormat sf; sf.SetFormatFlags(StringFormatFlagsNoWrap);
  for (int i = 0; i < n; i++) {
    RectF m; g.MeasureString(s + i, 1, f, PointF(0, 0), &sf, &m);
    ws[i] = m.Width; total += m.Width;
  }
  total += track * (n - 1);
  float x = r.X + (r.Width - total) / 2.f;
  SolidBrush b(c);
  sf.SetLineAlignment(StringAlignmentCenter);
  for (int i = 0; i < n; i++) {
    RectF lay(x, r.Y, ws[i] + 2, r.Height);
    g.DrawString(s + i, 1, f, lay, &sf, &b);
    x += ws[i] + track;
  }
}

static void FillRR(Graphics& g, const RectF& r, float rad, const Color& c) {
  GraphicsPath p;
  // ★ rad=0 不能走 AddArc：GDI+ 对零尺寸圆弧返回 InvalidParameter，
  //   整条路径作废 → FillPath 静默画不出任何东西。下拉第 1 项起的悬停高亮
  //   （圆角 0）就是这么"消失"的（2026-09-13 查实）。直角一律 AddRectangle。
  if (rad > 0.5f) {
    float d = rad * 2;
    p.AddArc(r.X, r.Y, d, d, 180, 90);
    p.AddArc(r.GetRight() - d, r.Y, d, d, 270, 90);
    p.AddArc(r.GetRight() - d, r.GetBottom() - d, d, d, 0, 90);
    p.AddArc(r.X, r.GetBottom() - d, d, d, 90, 90);
    p.CloseFigure();
  } else {
    p.AddRectangle(r);
  }
  SolidBrush b(c); g.FillPath(&b, &p);
}

static void StrokeRR(Graphics& g, const RectF& r, float rad, const Color& c, float w) {
  GraphicsPath p;
  if (rad > 0.5f) {
    float d = rad * 2;
    p.AddArc(r.X, r.Y, d, d, 180, 90);
    p.AddArc(r.GetRight() - d, r.Y, d, d, 270, 90);
    p.AddArc(r.GetRight() - d, r.GetBottom() - d, d, d, 0, 90);
    p.AddArc(r.X, r.GetBottom() - d, d, d, 90, 90);
    p.CloseFigure();
  } else {
    p.AddRectangle(r);
  }
  Pen pen(c, w); g.DrawPath(&pen, &p);
}

// 画一行文字。
//
// ★ wrapW > 0 时自动换行 —— 这是防"文案太长被窗口裁掉"的兜底。
//   以前固定传 RectF(x, y, 0, 0)，宽度 0 = 不约束，GDI+ 把整句画成一行，
//   超出部分被窗口边缘直接裁掉，看起来像文字凭空断掉（踩过：
//   「用 LanguageBarrier 重定向模型归档…」那句就出界了）。
//   需要的地方传可用宽度即可折行，不会再"看不到后半句"。
static void DrawTxtW(Graphics& g, const wchar_t* s, Font* f, const Color& c,
                     float x, float y, float wrapW, int align = 0) {
  SolidBrush b(c);
  StringFormat sf; sf.SetAlignment((StringAlignment)align);
  sf.SetLineAlignment(StringAlignmentNear);
  if (wrapW > 0) {
    // 中文没有空格，要显式允许"不按词断行"，否则 GDI+ 找不到断点就整句不折
    sf.SetFormatFlags(StringFormatFlagsLineLimit);
    g.DrawString(s, -1, f, RectF(x, y, wrapW, 0), &sf, &b);
  } else {
    g.DrawString(s, -1, f, RectF(x, y, 0, 0), &sf, &b);
  }
}
static void DrawTxt(Graphics& g, const wchar_t* s, Font* f, const Color& c, float x, float y, int align = 0) {
  DrawTxtW(g, s, f, c, x, y, 0, align);
}

// 勾选框（含对勾 / 空框）
static void DrawCheck(Graphics& g, const RectF& box, bool on, bool hot) {
  if (on) {
    FillRR(g, box, 5, C_ACCENT);
    Pen p(C_WHITE, 2.4f); p.SetStartCap(LineCapRound); p.SetEndCap(LineCapRound);
    g.DrawLine(&p, box.X + 5, box.Y + 11.5f, box.X + 9.5f, box.Y + 16);
    g.DrawLine(&p, box.X + 9.5f, box.Y + 16, box.X + 17.5f, box.Y + 5.5f);
  } else {
    FillRR(g, box, 5, C_FIELD);
    StrokeRR(g, box, 5, hot ? C_DIM : C_BORDER, 1.4f);
  }
}

// 下拉框外框 + 当前值 + 箭头
static void DrawComboFrame(Graphics& g, const RectF& cr, const wchar_t* value, bool hot) {
  FillRR(g, cr, 7, C_FIELD);
  StrokeRR(g, cr, 7, hot ? C_ACCENT : C_BORDER, hot ? 1.4f : 1.f);
  DrawTxt(g, value, F(14), C_TEXT, cr.X + 14, cr.Y + 8);
  float cx = cr.GetRight() - 18, cy = cr.Y + 18;
  SolidBrush db(C_DIM); PointF tri[3] = { {cx-5,cy-2},{cx+5,cy-2},{cx,cy+3} };
  g.FillPolygon(&db, tri, 3);
}

// 下拉展开的选项列表（单独一个函数，便于最后绘制 —— 见 Paint 里的 z 序说明）。
// 注意：ItemRect 定义在下面（几何区），所以本函数声明在前、实现放在几何之后。
static void DrawComboItems(Graphics& g, const RectF& base, int n,
                           const wchar_t* const* labels, int sel, int idBase, int hot);

// ── 几何 ──
// 左栏宽度由**主题图的比例**决定（见顶部 LEFT_W 的推导），窗口高度固定 620。
// 右栏所有控件从右边界反推 —— 以前这里是一堆手写死坐标，
// StartRect() 的右边界曾超出窗口 10px（「开始游戏」被切），现在不会再有这种问题。
static const float PAD_R = 24.f;                   // 右栏右边距
static const float RXL   = (float)LEFT_W + 28.f;   // 右栏内容左边界
static const float RW    = (float)WIN_W - PAD_R;   // 右栏内容右边界

// 4 个复选框：行高 42（标题 15px + 灰色说明 11px）
static RectF OptRect(int i)   { return RectF(RXL, 56.f + i * 42.f, RW - RXL, 26.f); }
// 两个下拉：标签在左，控件在右
static const float COMBO_X = 110.f;
static RectF OutfitRect()     { return RectF(RXL + COMBO_X, 252.f, RW - (RXL + COMBO_X), 34.f); }
static RectF ComboRect()      { return RectF(RXL + COMBO_X, 324.f, RW - (RXL + COMBO_X), 34.f); }
// 主按钮：右下角对齐，宽 200 高 46，离底 24
static RectF StartRect()      { return RectF(RW - 200.f, (float)WIN_H - 24.f - 46.f, 200.f, 46.f); }
// 下拉一律【向下】展开。换装 5 项、字幕 3 项，展开时下面要留得下 ——
// 窗口高度按「字幕框底 + 3 项 + 主按钮」反推（见 WIN_H）。
static RectF ItemRect(const RectF& base, int k) {
  return RectF(base.X, base.GetBottom() + 2 + k * 34.f, base.Width, 34.f);
}

// 下拉列表的绘制（实现在这里，因为要用 ItemRect）
static void DrawComboItems(Graphics& g, const RectF& base, int n,
                           const wchar_t* const* labels, int sel, int idBase, int hot) {
  // 先铺一层白底，避免选项和背景的分隔线/按钮混在一起
  RectF box(base.X, base.GetBottom() + 2, base.Width, n * 34.f + 4);
  FillRR(g, box, 6, C_FIELD);
  for (int k = 0; k < n; k++) {
    RectF ir = ItemRect(base, k);
    bool isHot = (hot == idBase + k);
    Color bg = isHot ? C_HOVER : (k == sel ? C_SEL : C_FIELD);
    float rad = k == 0 ? 5.f : 0.f;
    RectF rr(ir.X + 1, ir.Y, ir.Width - 2, ir.Height);
    FillRR(g, rr, rad, bg);
    // 悬停反馈要一眼能看出来（2026-09-13 用户反馈"没有鼓起来的感觉"）：
    // 只变一点底色太淡，再加一圈主题色描边。
    if (isHot) StrokeRR(g, rr, rad, C_ACCENT, 1.2f);
    DrawTxt(g, labels[k], F(14), k == sel ? C_ACCENT : C_TEXT, ir.X + 12, ir.Y + 7);
  }
  StrokeRR(g, box, 6, C_BORDER, 1.f);
}

// 命中 id：0..OPT_COUNT-1 选项 / 100+k subs / 200 开始 / 300 subs框
//         400+k outfit / 500 outfit框
enum { ID_START = 200, ID_COMBO_SUBS = 300, ID_COMBO_OUTFIT = 500 };

static void Paint(HDC hdc) {
  RECT rc; GetClientRect(g_hwnd, &rc);
  // 物理客户区尺寸。声明 DPI 感知后 rc 就是物理像素；绘制时用 ScaleTransform
  // 把坐标系缩放到逻辑尺寸，但 BitBlt 必须用物理尺寸往回拷。
  const int pw = rc.right, ph = rc.bottom;
  HDC mem = CreateCompatibleDC(hdc);
  HBITMAP bmp = CreateCompatibleBitmap(hdc, pw, ph);
  HBITMAP old = (HBITMAP)SelectObject(mem, bmp);
  {
    Graphics gr(mem);
    gr.SetSmoothingMode(SmoothingModeAntiAlias);
    gr.SetTextRenderingHint(TextRenderingHintAntiAliasGridFit);
    float sx = (float)pw / WIN_W, sy = (float)ph / WIN_H;
    S = sx;
    gr.ScaleTransform(sx, sy);

    SolidBrush bg(C_BG); gr.FillRectangle(&bg, 0, 0, WIN_W, WIN_H);

    // ── 左：主题图（铺满左栏）──
    // 图是 3:4 竖版，左栏宽度就是按这个比例算的，所以直接铺满即可，
    // 不会变形也不留黑边。找不到资源时退化成一个纯色块 + 文字提示。
    if (g_themeBmp) {
      // 目标矩形 = 整个左栏；源矩形 = 整张图。图的比例与左栏一致（见 LEFT_W
      // 的推导），所以等比缩放后正好铺满，不会变形。
      RectF dst(0, 0, (float)LEFT_W, (float)WIN_H);
      RectF src(0, 0, (float)g_themeBmp->GetWidth(), (float)g_themeBmp->GetHeight());
      gr.DrawImage(g_themeBmp, dst, src.X, src.Y, src.Width, src.Height, UnitPixel);
    } else {
      SolidBrush ph(C_PANEL); gr.FillRectangle(&ph, 0, 0, LEFT_W, WIN_H);
      DrawTxt(gr, L"主题图", F(14), C_MUTED, LEFT_W / 2.f, WIN_H / 2.f, 1);
    }
    Pen edge(C_BORDER, 1.f); gr.DrawLine(&edge, LEFT_W, 0, LEFT_W, WIN_H);
    // 版本号压在图上：左下角，图上多半是深色，用白字加一层淡阴影保证可读
    {
      RectF vb(12, (float)WIN_H - 30, 80, 20);
      SolidBrush sh(Color(90, 0, 0, 0));
      gr.FillRectangle(&sh, RectF(vb.X + 1, vb.Y + 1, 58, 18));
      DrawTxt(gr, (std::wstring(L"v") + VER).c_str(), F(12), C_WHITE, vb.X, vb.Y);
    }

    // ── 右上角小字：实现方式 + 署名（右对齐，一眼能看到出处）──
    // 两人工作量五五开，「x」刻意不分先后；「汉化:」与名字之间要留空格
    // （2026-09-13 用户指定格式「汉化: aaa x bbb」）。
    DrawTxt(gr, L"基于CoZ LanguageBarrier·Gemini3.0Flash·人工精校",
            F(10), C_MUTED, RW, 14, 2);
    DrawTxt(gr, L"汉化: 仓式同学◆ x Eight_tide",
            F(10), C_MUTED, RW, 29, 2);

    // ── 右：选项 ──
    DrawTxt(gr, L"选项", F(12), C_MUTED, RXL, 30);
    for (int i = 0; i < OPT_COUNT; i++) {
      RectF r = OptRect(i);
      bool on = st.on[i];
      DrawCheck(gr, RectF(r.X, r.Y + 2, 22, 22), on, st.hot == i);
      DrawTxt(gr, OPT_LABEL[i], F(15), on ? C_TEXT : C_DIM, r.X + 32, r.Y + 1);
      // 说明行统一走折行版：宽度给 0 时 GDI+ 不折行，太长会被窗口裁掉
      DrawTxtW(gr, OPT_HINT[i], F(11), C_MUTED, r.X + 32, r.Y + 19, RW - (r.X + 32));
    }

    // ── cosplay 模式 ──
    Pen sep0(C_BORDER, 1.f); gr.DrawLine(&sep0, RXL, 232.f, RW, 232.f);
    DrawTxt(gr, L"cosplay 模式", F(15), C_TEXT, RXL, 261);
    DrawComboFrame(gr, OutfitRect(), OUTFIT_LABEL[st.outfit], st.hot == ID_COMBO_OUTFIT);
    DrawTxtW(gr, OUTFIT_HINT, F(11), C_MUTED, RXL, 292, RW - RXL);

    Pen sep(C_BORDER, 1.f); gr.DrawLine(&sep, RXL, 312.f, RW, 312.f);
    DrawTxt(gr, L"影片字幕", F(15), C_TEXT, RXL, 333);
    DrawComboFrame(gr, ComboRect(), SUBS_LABEL[st.subs], st.hot == ID_COMBO_SUBS);
    DrawTxtW(gr, SUBS_HINT, F(11), C_MUTED, RXL, 364, RW - RXL);

    // ── 主按钮 ──
    // 浅色极简 + **直角**（2026-09-13 用户指定：棱角分明，不再圆角）。
    // 字用「START!」+ Bahnschrift（DIN 风格）逐字排字距，机械感；
    // 悬停底色加深 + 边框加深。沿用现有色板，不引入新颜色。
    { RectF sr = StartRect();
      bool hot = (st.hot == ID_START);
      SolidBrush fillb(hot ? C_HOVER : C_PANEL);
      gr.FillRectangle(&fillb, sr);
      Pen bp(hot ? C_DIM : C_BORDER, 1.f);
      gr.DrawRectangle(&bp, sr);
      DrawTrackedCentered(gr, L"START!", FTech(20, false), C_TEXT, sr, 1.2f); }


    // ── 下拉列表最后画 ──
    // 必须放在所有控件之后：展开的选项会盖住下面的分隔线与主按钮，
    // 若按源码顺序（换装就在换装标题之后）绘制，会被后面画的「影片字幕」
    // 和「开始游戏」覆盖，看起来像下拉框被切了一块。
    if (st.comboOpen == 1)
      DrawComboItems(gr, OutfitRect(), OUTFIT_N, OUTFIT_LABEL, st.outfit,
                     400, st.hot);
    else if (st.comboOpen == 0)
      DrawComboItems(gr, ComboRect(), 3, SUBS_LABEL, st.subs, 100, st.hot);
  }
  BitBlt(hdc, 0, 0, pw, ph, mem, 0, 0, SRCCOPY);
  SelectObject(mem, old); DeleteObject(bmp); DeleteDC(mem);
}

// ───────────────────────── 启动游戏 ─────────────────────────
static bool HasSaveDir(const wchar_t* lang) {
  wchar_t* docs = nullptr;
  SHGetKnownFolderPath(FOLDERID_Documents, 0, nullptr, &docs);
  std::wstring p = docs ? docs : L"";
  if (docs) CoTaskMemFree(docs);
  p += L"\\My Games\\mages_steam\\Robotics Notes DASH\\";
  p += lang;
  return FileExists(p);
}

// 从 boot.bat 读语言（游戏权威来源）：内容形如 "start launcher.exe JP"
// 补丁会覆盖 boot.bat，故优先读我们备份的原版；都没有则看存档目录。
static const wchar_t* DetectLang() {
  static wchar_t buf[8] = { 0 };
  const wchar_t* cands[] = {
    L"\\_cn_patch_boot_orig.bat",   // 安装器保留的游戏原版
    L"\\boot.bat"
  };
  for (auto c : cands) {
    std::wstring p = g_dir + c;
    std::ifstream f(p, std::ios::binary);
    if (!f) continue;
    std::stringstream ss; ss << f.rdbuf();
    std::string s = ss.str();
    for (auto& ch : s) ch = (char)toupper((unsigned char)ch);
    size_t e = s.find("EN"), j = s.find("JP");
    if (e != std::string::npos && (j == std::string::npos || e < j)) { wcscpy_s(buf, L"EN"); return buf; }
    if (j != std::string::npos) { wcscpy_s(buf, L"JP"); return buf; }
  }
  // 退化：按存档目录判断
  wcscpy_s(buf, (!HasSaveDir(L"eng") && HasSaveDir(L"jpn")) ? L"JP" : L"EN");
  return buf;
}

// Steam 客户端在运行吗（查进程表里有没有 steam.exe）
static bool SteamRunning() {
  HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
  if (snap == INVALID_HANDLE_VALUE) return true;    // 查不到就别拦，让它试
  PROCESSENTRY32W pe; pe.dwSize = sizeof(pe);
  bool found = false;
  if (Process32FirstW(snap, &pe)) {
    do {
      if (_wcsicmp(pe.szExeFile, L"steam.exe") == 0) { found = true; break; }
    } while (Process32NextW(snap, &pe));
  }
  CloseHandle(snap);
  return found;
}

// 是 Steam 库安装吗：路径里有 steamapps 即是（盗版免 DVD 版不在，直接启动即可）
static bool IsSteamInstall() {
  std::wstring d = g_dir;
  for (auto& c : d) c = (wchar_t)towlower(c);
  return d.find(L"steamapps") != std::wstring::npos;
}

// /settitle <pid>：把该进程主窗口的标题换成补丁名。
// 由「开始游戏」以分离方式再拉起一份自己（无窗口），随游戏退出自动结束。
// 每 5 秒看一眼：游戏中途重建窗口（如全屏切换）也能补上；标题一致就不动。
static DWORD g_settitlePid = 0;
static HWND  g_gameHwnd = nullptr;

static BOOL CALLBACK FindGameWnd(HWND hwnd, LPARAM) {
  DWORD wpid = 0;
  GetWindowThreadProcessId(hwnd, &wpid);
  if (wpid == g_settitlePid && IsWindowVisible(hwnd)) {
    wchar_t t[128] = {0};
    GetWindowTextW(hwnd, t, 128);
    if (t[0]) { g_gameHwnd = hwnd; return FALSE; }
  }
  return TRUE;
}

static int RunSetTitle(DWORD pid) {
  const wchar_t* title = APP_TITLE.c_str();
  g_settitlePid = pid;
  for (int i = 0; i < 3600; i++) {             // 最多约 1 小时，随游戏退出结束
    // 前期窗口出现得快（几秒内），盯紧些；之后放宽，别空转
    Sleep(i < 60 ? 500 : 5000);
    // 游戏退出了就结束（不留下一个常驻进程）
    DWORD code = 0;
    HANDLE gp = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, pid);
    if (!gp) return 0;
    BOOL ok = GetExitCodeProcess(gp, &code);
    CloseHandle(gp);
    if (!ok || code != STILL_ACTIVE) return 0;
    g_gameHwnd = nullptr;
    EnumWindows(FindGameWnd, 0);
    if (!g_gameHwnd) continue;
    wchar_t cur[128] = {0};
    GetWindowTextW(g_gameHwnd, cur, 128);
    if (wcscmp(cur, title) != 0)
      SendMessageW(g_gameHwnd, WM_SETTEXT, 0, (LPARAM)title);
  }
  return 0;
}

static void LaunchGame() {
  SaveConfig();
  ApplyDxvk(st.on[OPT_DXVK]);
  const wchar_t* lang = DetectLang();   // 跟随玩家原本的版本（存档目录随之）

  // Steam 版必须先开 Steam 客户端，否则游戏会弹英文模态框
  // （"You need to execute Steam system..."）且主窗口根本不出来。
  // 检测不到进程时不拦 —— 免得误伤（比如改名版 Steam）。
  if (IsSteamInstall() && !SteamRunning()) {
    MessageBoxW(g_hwnd,
        L"请先启动 Steam，再点「START!」。\n\n也可以直接从 Steam 库里启动游戏。",
        L"Steam 未运行", MB_ICONINFORMATION | MB_OK);
    return;
  }

  std::wstring cmd = L"Game.exe roboticsnotesd " + std::wstring(lang);
  STARTUPINFOW si{}; si.cb = sizeof(si);
  PROCESS_INFORMATION pi{};
  if (CreateProcessW(L"Game.exe", &cmd[0], nullptr, nullptr, FALSE, 0, nullptr, g_dir.c_str(), &si, &pi)) {
    CloseHandle(pi.hThread);
    // 把游戏窗口标题换成补丁标题：分离一份自己（无窗口）去做，随游戏退出结束。
    {
      wchar_t self[MAX_PATH]; GetModuleFileNameW(nullptr, self, MAX_PATH);
      std::wstring c2 = std::wstring(L"\"") + self + L"\" /settitle "
                        + std::to_wstring(pi.dwProcessId);
      STARTUPINFOW si2{}; si2.cb = sizeof(si2);
      si2.dwFlags = STARTF_USESHOWWINDOW; si2.wShowWindow = SW_HIDE;
      PROCESS_INFORMATION pi2{};
      if (CreateProcessW(nullptr, &c2[0], nullptr, nullptr, FALSE,
                         CREATE_NO_WINDOW, nullptr, nullptr, &si2, &pi2)) {
        CloseHandle(pi2.hThread); CloseHandle(pi2.hProcess);
      }
    }
    CloseHandle(pi.hProcess);
    PostMessageW(g_hwnd, WM_CLOSE, 0, 0);
  } else {
    MessageBoxW(g_hwnd, L"未找到 Game.exe，请把本启动器放在游戏根目录。",
                L"启动失败", MB_ICONERROR | MB_OK);
  }
}

// ───────────────────────── 交互 ─────────────────────────
// 注意：鼠标消息给的是**物理像素**，而布局是逻辑坐标，所以先 unscale 再比。
static int HitTest(int px, int py) {
  int x = (int)unscale(px), y = (int)unscale(py);
  auto in = [&](const RectF& r) {
    return x >= r.X && x <= r.GetRight() && y >= r.Y && y <= r.GetBottom();
  };
  // 下拉优先：展开时它盖在下面的控件上，命中判定也必须先于它们
  if (st.comboOpen == 1) for (int k = 0; k < OUTFIT_N; k++) if (in(ItemRect(OutfitRect(), k))) return 400 + k;
  if (st.comboOpen == 0) for (int k = 0; k < 3; k++) if (in(ItemRect(ComboRect(), k))) return 100 + k;
  if (in(StartRect())) return ID_START;
  if (in(OutfitRect())) return ID_COMBO_OUTFIT;
  if (in(ComboRect())) return ID_COMBO_SUBS;
  for (int i = 0; i < OPT_COUNT; i++) {
    RectF r = OptRect(i);
    if (x >= r.X - 4 && x <= r.X + r.Width && y >= r.Y - 2 && y <= r.Y + 40) return i;
  }
  return -1;
}

static LRESULT CALLBACK WndProc(HWND h, UINT m, WPARAM w, LPARAM l) {
  switch (m) {
  case WM_MOUSEMOVE: {
    int id = HitTest(GET_X_LPARAM(l), GET_Y_LPARAM(l));
    if (id != st.hot) { st.hot = id; InvalidateRect(h, nullptr, FALSE); }
#ifndef RND_DBG_NOLEAVE   // 调试版可关掉：光标不在客户区时 TrackMouseEvent 会立刻
    TRACKMOUSEEVENT t{ sizeof(t) }; t.dwFlags = TME_LEAVE; t.hwndTrack = h;
    TrackMouseEvent(&t);  // 补发 WM_MOUSELEAVE，把假鼠标消息模拟出的悬停态清掉
#endif
    return 0;
  }
  case WM_MOUSELEAVE: st.hot = -1; InvalidateRect(h, nullptr, FALSE); return 0;
  case WM_LBUTTONDOWN: { st.press = HitTest(GET_X_LPARAM(l), GET_Y_LPARAM(l)); return 0; }
  case WM_LBUTTONUP: {
    int id = HitTest(GET_X_LPARAM(l), GET_Y_LPARAM(l));
    if (id == st.press) {
      bool saveNow = false;
      if (id >= 0 && id < OPT_COUNT) { st.on[id] = !st.on[id]; InvalidateRect(h, nullptr, FALSE); saveNow = true; }
      else if (id >= 100 && id < 103) { st.subs = id - 100; st.comboOpen = -1; InvalidateRect(h, nullptr, FALSE); saveNow = true; }
      else if (id >= 400 && id < 400 + OUTFIT_N) { st.outfit = id - 400; st.comboOpen = -1; InvalidateRect(h, nullptr, FALSE); saveNow = true; }
      else if (id == ID_COMBO_SUBS) { st.comboOpen = (st.comboOpen == 0) ? -1 : 0; InvalidateRect(h, nullptr, FALSE); }
      else if (id == ID_COMBO_OUTFIT) { st.comboOpen = (st.comboOpen == 1) ? -1 : 1; InvalidateRect(h, nullptr, FALSE); }
      else if (id == ID_START) { LaunchGame(); }
      // 立刻落盘：玩家可能在这里改完就关窗口、再用 Steam 或 boot.bat 直启游戏
      if (saveNow) SaveConfig();
    } else if (st.comboOpen >= 0 && id == -1) { st.comboOpen = -1; InvalidateRect(h, nullptr, FALSE); }
    st.press = -1; return 0;
  }
  case WM_PAINT: { PAINTSTRUCT ps; HDC dc = BeginPaint(h, &ps); Paint(dc); EndPaint(h, &ps); return 0; }
  case WM_ERASEBKGND: return 1;
  case WM_KEYDOWN: if (w == VK_ESCAPE) PostMessageW(h, WM_CLOSE, 0, 0); return 0;
  case WM_CLOSE: SaveConfig(); DestroyWindow(h); return 0;
  case WM_DESTROY: PostQuitMessage(0); return 0;
  }
  return DefWindowProcW(h, m, w, l);
}

int WINAPI wWinMain(HINSTANCE hInst, HINSTANCE, PWSTR, int) {
  g_dir = ExeDir();

  // /settitle <pid>：游戏窗口标题劫持（「开始游戏」分离出来的隐藏实例）。
  // 不建窗口，随游戏退出自动结束。必须放在一切窗口逻辑之前。
  {
    std::wstring cl = GetCommandLineW();
    for (auto& c : cl) c = (wchar_t)towlower(c);
    size_t p = cl.find(L"/settitle");
    if (p != std::wstring::npos) {
      DWORD pid = (DWORD)_wtoi(GetCommandLineW() + p + 9);
      if (pid) return RunSetTitle(pid);
      return 0;
    }
  }

  GdiplusStartupInput gi; ULONG_PTR token;
  GdiplusStartup(&token, &gi, nullptr);

  // 字体：GDI+ 的 PrivateFontCollection 无法加载 CFF/OTF 轮廓（本项目的
  // NotoSansCJKsc-Regular.otf 会返回 FontFamilyNotFound），故直接用系统中文字体。
  {
    const wchar_t* cand[] = { L"Microsoft YaHei UI", L"Microsoft YaHei",
                              L"SimHei", L"SimSun", L"MS Gothic" };
    for (auto nm : cand) {
      FontFamily* f = new FontFamily(nm);
      if (f->IsAvailable()) { g_ff = f; break; }
      delete f;
    }
    if (!g_ff) { g_ff = new FontFamily(L"Arial"); }
  }
  {
    const wchar_t* cand[] = { L"Bahnschrift", L"Segoe UI", L"Arial" };
    for (auto nm : cand) {
      FontFamily* f = new FontFamily(nm);
      if (f->IsAvailable()) { g_ffTech = f; break; }
      delete f;
    }
    if (!g_ffTech) g_ffTech = g_ff;   // 兜底的兜底：中文字体也能画拉丁字母
  }
  LoadAppIconFromResource();
  LoadThemeImage();
  // ★ 必须在建窗口之前：窗口尺寸取决于左栏宽度，而左栏宽度由主题图比例算出来。
  ApplyThemeGeometry();
  LoadConfig();

  WNDCLASSEXW wc{ sizeof(wc) };
  wc.lpfnWndProc = WndProc; wc.hInstance = hInst; wc.hCursor = LoadCursor(nullptr, IDC_ARROW);
  wc.lpszClassName = L"RNDZhLauncherWnd"; wc.hbrBackground = nullptr;
  wc.hIcon = LoadIconW(hInst, MAKEINTRESOURCEW(101));
  wc.hIconSm = wc.hIcon;
  RegisterClassExW(&wc);

  DWORD style = WS_OVERLAPPEDWINDOW & ~(WS_THICKFRAME | WS_MAXIMIZEBOX);
  // DPI 感知：先声明，再按【当前窗口 DPI】换算客户区尺寸。
  // 不声明的话 Windows 会把整个窗口位图拉伸（125% 缩放下发虚），
  // 而且 SetProcessDPIAware 之后再取 DPI 才是真实值。
  SetProcessDPIAware();
  HDC screen = GetDC(nullptr);
  float dpi = (float)GetDeviceCaps(screen, LOGPIXELSX);
  ReleaseDC(nullptr, screen);
  if (dpi <= 0) dpi = 96.f;
  S = dpi / 96.f;

  int cw = (int)(WIN_W * S + 0.5f), ch = (int)(WIN_H * S + 0.5f);
  RECT r{ 0, 0, cw, ch };
  AdjustWindowRect(&r, style, FALSE);
  int ww = r.right - r.left, wh = r.bottom - r.top;
  int sw = GetSystemMetrics(SM_CXSCREEN), sh = GetSystemMetrics(SM_CYSCREEN);
  g_hwnd = CreateWindowExW(0, wc.lpszClassName, APP_TITLE.c_str(),
                           style, (sw - ww) / 2, (sh - wh) / 2, ww, wh,
                           nullptr, nullptr, hInst, nullptr);
  ShowWindow(g_hwnd, SW_SHOW); UpdateWindow(g_hwnd);

  MSG msg;
  while (GetMessageW(&msg, nullptr, 0, 0)) { TranslateMessage(&msg); DispatchMessageW(&msg); }
  GdiplusShutdown(token);
  return 0;
}
