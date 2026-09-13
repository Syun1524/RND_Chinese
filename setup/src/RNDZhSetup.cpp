// RNDZhSetup — ROBOTICS;NOTES DaSH 简体中文补丁 安装程序
// 原生 Win32 + GDI+，无外部依赖。由 7z SFX 解包后自动运行：
//   SFX 把「Setup.exe + 全部补丁文件」解到临时目录 → 运行本程序 → 本程序把文件装进游戏目录。
//
// 编译：见 build_setup.bat

#define WIN32_LEAN_AND_MEAN
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <windowsx.h>
#include <objidl.h>
#include <gdiplus.h>
#include <shlobj.h>
#include <shellapi.h>
#include <tlhelp32.h>
#include <commctrl.h>
#include <string>
#include <vector>
#include <map>
#include <fstream>
#include <sstream>

#pragma comment(lib, "gdiplus.lib")
#pragma comment(lib, "shell32.lib")
#pragma comment(lib, "comctl32.lib")
#pragma comment(lib, "user32.lib")
#pragma comment(lib, "gdi32.lib")
#pragma comment(lib, "ole32.lib")

using namespace Gdiplus;

// ───────────────────────── 外观常量（纯白极简） ─────────────────────────
// 配色刻意贴近 Windows 原生安装程序：白底、浅灰边框、深灰文字、蓝色主按钮。
// 不用深色/霓虹色 —— 安装器只是走个过场，不该抢游戏本身的风头。
static const int WIN_W = 480, WIN_H = 268;
// 产品版本。⚠ 改版本要同步三处：这里、launcher/RNDZhLauncher.cpp 的 VER、
// 成品ing/setup/build/build_installer.py 的 VERSION（决定包文件名）。
static const wchar_t* VER = L"1.0";
static const Color
  C_BG      (255, 255, 255, 255),   // 窗口底
  C_PANEL   (255, 245, 246, 248),   // 顶部标题条
  C_FIELD   (255, 255, 255, 255),   // 输入框底
  C_BORDER  (255, 216, 220, 227),   // 边框
  C_TEXT    (255,  31,  35,  40),   // 正文
  C_DIM     (255, 107, 114, 128),   // 次要文字
  C_MUTED   (255, 156, 163, 175),   // 更淡（禁用态）
  C_ACCENT  (255,  11, 107, 203),   // 主按钮
  C_ACCENTH (255,  10,  95, 176),   // 主按钮悬停
  C_TRACK   (255, 232, 235, 240),   // 进度条底槽
  C_WHITE   (255, 255, 255, 255),
  C_OK      (255,  26, 127,  55),   // 成功
  C_WARN    (255, 154, 103,   0),   // 警告
  C_ERR     (255, 207,  34,  46);   // 失败

static HWND g_hwnd;
static FontFamily* g_ff = nullptr;
static Gdiplus::Bitmap* g_iconBmp = nullptr;
static std::wstring g_srcDir;      // 本程序所在目录（= 补丁文件所在）
static std::wstring g_gameDir;     // 目标游戏目录
static std::wstring g_lang = L"JP";
static std::wstring g_status = L"点击「安装」开始（请先完全关闭游戏）";
static int g_pct = -1;             // -1 = 未开始
static bool g_done = false, g_failed = false;
static int g_hot = -1;
static std::wstring g_gameVer;     // 一行状态提示（如「已找到游戏（日文版）」）
// 目录框用原生 EDIT 子控件：插入符、选区、剪贴板、输入法全部自带。
// 之前手绘输入框只能处理 ASCII 按键，打中文/粘贴都不行。
static const int ID_EDIT_DIR = 1001;   // 目录 EDIT 控件 ID
static LRESULT CALLBACK EditSubclass(HWND, UINT, WPARAM, LPARAM, UINT_PTR, DWORD_PTR);
static void RefreshDirHint();          // EditSubclass 会用到
static HWND g_hEdit = nullptr;
static bool g_syncingEdit = false;   // 防止 文本变更 与 设置文本 互相触发

// ───────────────────────── 工具 ─────────────────────────
static bool Exists(const std::wstring& p) {
  return GetFileAttributesW(p.c_str()) != INVALID_FILE_ATTRIBUTES;
}
static bool IsDir(const std::wstring& p) {
  DWORD a = GetFileAttributesW(p.c_str());
  return a != INVALID_FILE_ATTRIBUTES && (a & FILE_ATTRIBUTE_DIRECTORY);
}
static std::wstring Join(const std::wstring& a, const std::wstring& b) {
  if (a.empty()) return b;
  if (a.back() == L'\\') return a + b;
  return a + L"\\" + b;
}

// 规整路径用于**显示**：统一分隔符 + 盘符大写。
// 为什么需要：Steam 注册表里的 SteamPath 可能是 `d:/ruanjian/steam`（小写盘符 + 正斜杠），
// 直接拼出来就是 `d:/ruanjian/steam\steamapps\common\...` 这种混合样子，
// 在界面里看着像坏掉的路径（实际能用）。只影响显示，不改内部用的字符串。
static std::wstring PrettyPath(const std::wstring& p) {
  std::wstring s = p;
  for (auto& c : s) if (c == L'/') c = L'\\';
  if (s.size() >= 2 && s[1] == L':') s[0] = (wchar_t)towupper(s[0]);
  return s;
}
static std::wstring ExeDir() {
  wchar_t buf[MAX_PATH]; GetModuleFileNameW(nullptr, buf, MAX_PATH);
  std::wstring s(buf); size_t p = s.find_last_of(L'\\');
  return p == std::wstring::npos ? L"." : s.substr(0, p);
}
static std::wstring FileName(const std::wstring& p) {
  size_t s = p.find_last_of(L"\\/");
  return s == std::wstring::npos ? p : p.substr(s + 1);
}

// 两个文件内容是否相同（用于判断"这文件是不是我们自己上次装进去的"）
static bool SameContents(const std::wstring& a, const std::wstring& b) {
  HANDLE ha = CreateFileW(a.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr,
                          OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
  if (ha == INVALID_HANDLE_VALUE) return false;
  HANDLE hb = CreateFileW(b.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr,
                          OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
  if (hb == INVALID_HANDLE_VALUE) { CloseHandle(ha); return false; }
  LARGE_INTEGER sa, sb;
  bool same = GetFileSizeEx(ha, &sa) && GetFileSizeEx(hb, &sb) && sa.QuadPart == sb.QuadPart;
  if (same) {
    char ba[65536], bb[65536];
    for (;;) {
      DWORD na = 0, nb = 0;
      if (!ReadFile(ha, ba, sizeof(ba), &na, nullptr) ||
          !ReadFile(hb, bb, sizeof(bb), &nb, nullptr) || na != nb) { same = false; break; }
      if (na == 0) break;
      if (memcmp(ba, bb, na) != 0) { same = false; break; }
    }
  }
  CloseHandle(ha);
  CloseHandle(hb);
  return same;
}

// 存档目录里唯一存在的语言（eng / jpn）。这是玩家实际在用的语言，最可信；
// 两个都有（都玩过）或都没有时返回空，交给调用方看 boot.bat。
static std::wstring LangFromSaveDir() {
  wchar_t* docs = nullptr;
  if (SHGetKnownFolderPath(FOLDERID_Documents, 0, nullptr, &docs) != S_OK)
    return L"";
  std::wstring base = docs;
  CoTaskMemFree(docs);
  base += L"\\My Games\\mages_steam\\Robotics Notes DASH";
  bool eng = IsDir(Join(base, L"eng")), jpn = IsDir(Join(base, L"jpn"));
  if (eng && !jpn) return L"EN";
  if (jpn && !eng) return L"JP";
  return L"";
}

// 判定游戏语言（JP / EN）。
//
// 依据的可靠性排序：
//   1) 文本归档 —— 这才是真正决定游戏是日版还是英文版的东西。
//      mes00.cpk = 日文文本，mes01.cpk = 英文文本。只存在其一时可直接定论。
//      实测：3DM 盗版包只有 mes01.cpk（英文），但它的 boot.bat 却写着 JP，
//      旧逻辑读 boot.bat 就把 JP 传了下去 —— 而玩家在玩英文版。
//   2) 存档目录 eng / jpn 只存在其一 —— 玩家实际在用的那个。
//   3) boot.bat —— 游戏启动参数。
//   4) _cn_patch_boot_orig.bat —— 上次安装留下的原件，仅兜底。
static std::wstring DetectLangFrom(const std::wstring& gameDir) {
  // 1) 文本归档
  bool has_jp = Exists(Join(gameDir, L"mes00.cpk"));
  bool has_en = Exists(Join(gameDir, L"mes01.cpk"));
  if (has_en && !has_jp) return L"EN";
  if (has_jp && !has_en) return L"JP";

  // 2) 存档目录
  std::wstring save_lang = LangFromSaveDir();
  if (!save_lang.empty()) return save_lang;

  // 3) boot.bat，其次 4) 上次安装的残留
  std::wstring boot_lang;
  const wchar_t* names[] = { L"boot.bat", L"_cn_patch_boot_orig.bat" };
  for (auto n : names) {
    std::ifstream f(Join(gameDir, n), std::ios::binary);
    if (!f) continue;
    std::stringstream ss; ss << f.rdbuf();
    std::string t = ss.str();
    for (auto& c : t) c = (char)toupper((unsigned char)c);
    size_t e = t.find("EN"), j = t.find("JP");
    if (e != std::string::npos && (j == std::string::npos || e < j)) { boot_lang = L"EN"; break; }
    if (j != std::string::npos) { boot_lang = L"JP"; break; }
  }
  return boot_lang;
}

static bool ValidGameDir(const std::wstring& d) {
  return Exists(Join(d, L"Game.exe")) && Exists(Join(d, L"script.cpk"));
}

// 玩家目录名里有分号（;）时，加载器怎么找本地 DLL —— 本补丁最重要的环境事实。
//
// 游戏静态导入 DINPUT8.dll，靠 Windows 加载器在 exe 所在目录找到我们的代理 DLL。
// 目录名**含分号**时，加载器把目录路径按 `;` 切开，**分号后面每一段都被当成相对
// 目录名**，相对游戏目录再搜一遍；只有那个子目录存在且放了 DLL，补丁才会启动。
//
// 实测（scripts/diagnostics/predict_mechanism.py，三条预测全部命中）：
//
//   目录名                分号后的片段   片段子目录     实际加载的 dinput8
//   RNDt                  （无）         —            本地 ✓
//   RND;t                 t              不存在        系统 ✗
//   RND;t 且建了 t\ 子目录  t              存在          本地 ✓（从 t\ 里加载）
//   RND;NOTES DaSH        NOTES DaSH     已存在        本地 ✓（从 NOTES DaSH\ 加载）
//
// 长度与中文都不影响（早先记的"长路径""中文导致"都是从一个混了多个变量的样本
// 推出来的误判，separate_variables 实测：短/长 × 有/无中文 全部通过，
// 唯一决定成败的是分号）。
//
// **所以补丁侧是可以修的**：把分号后的片段名建成子目录、把代理 DLL 放进去即可。
// CoZ 原版补丁其实一直在这么做 —— 它的 payload 里带着一个写死名字的 `NOTES DaSH\`
// 子目录，那正是 Steam 正本目录名 `ROBOTICS;NOTES DaSH` 分号后的片段。
// 只是写死了，玩家一旦把游戏目录改名（做副本）就失效，补丁便"静默不加载"。
//
// 下面把它推广成按实际目录名计算，任何名字都能自动兼容 ——
// 因此**我们自己不再需要在 payload 里预置那个目录**（2026-09-12 已移除，实测冗余：
// 见 scripts/diagnostics/probe_notes_subdir.py，装到 Steam 正本时由这里现算现建）。
// 归档在 成品ing/_backup/notes_dash_hardcoded_20260912/。
static std::vector<std::wstring> SemicolonFragments(const std::wstring& d) {
  std::vector<std::wstring> out;
  std::wstring name = FileName(d);
  size_t p = name.find(L';');
  while (p != std::wstring::npos) {
    size_t q = name.find(L';', p + 1);
    std::wstring seg = (q == std::wstring::npos) ? name.substr(p + 1)
                                                 : name.substr(p + 1, q - p - 1);
    p = q;
    // Win32 建目录时会静默去掉尾随的点/空格，那样子目录名与片段对不上、白建，跳过
    while (!seg.empty() && (seg.back() == L' ' || seg.back() == L'.')) seg.pop_back();
    if (!seg.empty()) out.push_back(seg);
  }
  return out;
}

// 代理文件：游戏静态导入 dinput8；dxgi/d3d* 是 DXVK 的；VSFilter 是字幕渲染。
// 片段子目录里各放一份 —— 路径含分号时，根目录那份压根进不了加载器的搜索路径。
static const wchar_t* kProxyFiles[] = {
  L"dinput8.dll", L"d3d9", L"d3d10", L"d3d10_1", L"d3d10core", L"d3d11", L"dxgi",
  L"VSFilter.dll" };

// 注：曾经这里有个 PathLoadNotice()/NeedsFragmentDirs()，用来在界面上显示
// 「路径含分号，将自动建 xxx\ 兼容」。已删除 —— 那是实现细节，玩家看不懂也不需要知道，
// 安装器自己处理好即可。需要判断"是否含分号"时直接调 SemicolonFragments()。

// 在常见位置找游戏
// 取「启动本程序的进程」所在目录。
//
// 单文件安装包运行时，SFX 是安装器的父进程，而 SFX 就位于用户放置安装包的目录，
// 所以父进程的目录 = 用户期望的游戏目录（若用户确实把它放进了游戏目录）。
// 这是从 SFX 场景反推"原始位置"最可靠的手段 —— 环境变量/argv/cwd 都拿不到。
static std::wstring ParentProcessDir() {
  DWORD me = GetCurrentProcessId();
  DWORD parent = 0;
  HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
  if (snap != INVALID_HANDLE_VALUE) {
    PROCESSENTRY32W pe;
    pe.dwSize = sizeof(pe);
    if (Process32FirstW(snap, &pe)) {
      do {
        if (pe.th32ProcessID == me) { parent = pe.th32ParentProcessID; break; }
      } while (Process32NextW(snap, &pe));
    }
    CloseHandle(snap);
  }
  if (!parent) return L"";
  HANDLE h = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, parent);
  if (!h) return L"";
  wchar_t path[MAX_PATH] = {0};
  DWORD sz = MAX_PATH;
  std::wstring dir;
  if (QueryFullProcessImageNameW(h, 0, path, &sz) && sz > 0) {
    std::wstring p = path;
    size_t q = p.find_last_of(L'\\');
    if (q != std::wstring::npos) dir = p.substr(0, q);
  }
  CloseHandle(h);
  return dir;
}

static std::wstring AutoDetectGame() {
  // 从单文件安装包运行时，SFX 把本程序解压到 %TEMP%zXXXX\ 再启动，
  // 因此 cwd / g_srcDir 都是临时目录，**看不到安装包原本放在哪**。
  // 定位顺序：
  //   1) 父进程目录 —— SFX 是父进程，它就是安装包的真实位置（最可靠）
  //   2) 自身目录/上级 —— 手动把补丁解压进游戏目录时有效
  //   3) Steam 库扫描 —— 兜底
  // 父进程目录：从单文件安装包启动时，SFX 是父进程，它的位置就是
  // 用户放置安装包的目录 —— 正是用户期望的目标游戏目录。
  // （实测：SFX 场景下 cwd/srcDir 全是 %TEMP%zXXXX\，只有父进程路径可用。）
  {
    std::wstring pd = ParentProcessDir();
    if (!pd.empty()) {
      if (ValidGameDir(pd)) return pd;
      size_t q = pd.find_last_of(L'\\');
      if (q != std::wstring::npos) {
        std::wstring up = pd.substr(0, q);
        if (ValidGameDir(up)) return up;
      }
    }
  }

  // 自身所在目录及其上级（手动把补丁解压进游戏目录时有效）
  if (ValidGameDir(g_srcDir)) return g_srcDir;
  std::wstring parent = g_srcDir;
  size_t p = parent.find_last_of(L'\\');
  if (p != std::wstring::npos) { parent = parent.substr(0, p);
    if (ValidGameDir(parent)) return parent; }

  // 2) 注册表 Steam 路径 + 常见库目录
  std::vector<std::wstring> roots;
  {
    HKEY k; wchar_t buf[MAX_PATH]; DWORD sz = sizeof(buf);
    if (RegOpenKeyExW(HKEY_CURRENT_USER, L"Software\\Valve\\Steam", 0, KEY_READ, &k) == ERROR_SUCCESS) {
      if (RegQueryValueExW(k, L"SteamPath", nullptr, nullptr, (LPBYTE)buf, &sz) == ERROR_SUCCESS)
        roots.push_back(buf);
      RegCloseKey(k);
    }
  }
  const wchar_t* drives[] = { L"C:", L"D:", L"E:", L"F:", L"G:", L"H:" };
  std::vector<std::wstring> bases;
  for (auto r : roots) bases.push_back(Join(r, L"steamapps\\common"));
  for (auto d : drives) {
    bases.push_back(std::wstring(d) + L"\\Steam\\steamapps\\common");
    bases.push_back(std::wstring(d) + L"\\SteamLibrary\\steamapps\\common");
    bases.push_back(std::wstring(d) + L"\\SteamLibrary\\SteamApps\\common");
  }
  for (auto& b : bases) {
    std::wstring g = Join(b, L"ROBOTICS;NOTES DaSH");
    if (ValidGameDir(g)) return g;
  }
  return L"";
}

// ───────────────────────── 安装 ─────────────────────────
static std::vector<std::pair<std::wstring, std::wstring>> g_tasks;  // (相对路径, 是否目录)

static void CollectFiles(const std::wstring& base, const std::wstring& rel,
                         std::vector<std::pair<std::wstring, std::wstring>>& out) {
  std::wstring full = rel.empty() ? base : Join(base, rel);
  WIN32_FIND_DATAW fd;
  HANDLE h = FindFirstFileW(Join(full, L"*").c_str(), &fd);
  if (h == INVALID_HANDLE_VALUE) return;
  do {
    std::wstring name = fd.cFileName;
    if (name == L"." || name == L"..") continue;
    std::wstring r = rel.empty() ? name : Join(rel, name);
    if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
      out.push_back({ r, L"d" });
      CollectFiles(base, r, out);
    } else {
      // 跳过安装程序自身与 SFX 配置
      // boot.bat 一并跳过：包内那份写死 JP，中途失败会把语言卡在 JP。
      // 安装最后一步会按检测到的语言自己写一份。
      if (rel.empty() && (name == L"Setup.exe" || name == L"7zSFX.txt" ||
                          name == L"boot.bat")) continue;
      out.push_back({ r, L"f" });
    }
  } while (FindNextFileW(h, &fd));
  FindClose(h);
}

// 递归复制（带进度）
static int g_copied = 0, g_total = 1;

static bool CopyOne(const std::wstring& rel, bool isDir) {
  std::wstring src = Join(g_srcDir, rel);
  std::wstring dst = Join(g_gameDir, rel);
  if (isDir) {
    CreateDirectoryW(dst.c_str(), nullptr);
    return true;
  }
  CreateDirectoryW(Join(dst, L"..").c_str(), nullptr);   // 确保父目录存在
  if (!CopyFileW(src.c_str(), dst.c_str(), FALSE)) {
    // 目标被占用/只读时，尝试清只读再复制
    SetFileAttributesW(dst.c_str(), FILE_ATTRIBUTE_NORMAL);
    if (!CopyFileW(src.c_str(), dst.c_str(), FALSE)) return false;
  }
  return true;
}

static void PumpMessages() {
  MSG m;
  while (PeekMessageW(&m, nullptr, 0, 0, PM_REMOVE)) {
    TranslateMessage(&m); DispatchMessageW(&m);
  }
}

static void SetStatus(const std::wstring& s, int pct) {
  g_status = s; g_pct = pct;
  InvalidateRect(g_hwnd, nullptr, FALSE);
  UpdateWindow(g_hwnd);
  PumpMessages();
}

// 删除 SFX 自解压残留目录。
//
// 7z SFX 会把整个包解到 %TEMP%\7zXXXXXXX\ 再运行本安装器；装完那个目录仍然存在
// （内含完整补丁，约 450MB）。这里在收尾时把它删掉。
//
// 只删"确实是 SFX 解压目录"的：一是路径必须在 %TEMP% 下，二是目录名要匹配 7z 的
// 命名（7z + 十六进制），三是目录里必须有安装器自身。三条都满足才删 —— 用户把包
// 手动解压到别处（比如桌面）时，这里不会去动他的文件。
// 递归删除目录（先清属性再删，避免只读文件卡住）。
static void RemoveTree(const std::wstring& dir, bool removeSelf) {
  WIN32_FIND_DATAW fd;
  HANDLE h = FindFirstFileW(Join(dir, L"*").c_str(), &fd);
  if (h != INVALID_HANDLE_VALUE) {
    do {
      std::wstring n = fd.cFileName;
      if (n == L"." || n == L"..") continue;
      std::wstring p = Join(dir, n);
      if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
        RemoveTree(p, true);
      } else {
        SetFileAttributesW(p.c_str(), FILE_ATTRIBUTE_NORMAL);
        DeleteFileW(p.c_str());
      }
    } while (FindNextFileW(h, &fd));
    FindClose(h);
  }
  if (removeSelf) {
    SetFileAttributesW(dir.c_str(), FILE_ATTRIBUTE_NORMAL);
    RemoveDirectoryW(dir.c_str());
  }
}

static void CleanupSfxTemp() {
  wchar_t temp[MAX_PATH] = {0};
  if (!GetTempPathW(MAX_PATH, temp)) return;
  std::wstring tdir = temp;
  while (!tdir.empty() && (tdir.back() == L'\\' || tdir.back() == L'/')) tdir.pop_back();
  std::wstring src = g_srcDir;
  while (!src.empty() && (src.back() == L'\\' || src.back() == L'/')) src.pop_back();

  // 必须位于 %TEMP% 之内（不区分大小写）
  if (src.size() <= tdir.size()) return;
  std::wstring head = src.substr(0, tdir.size());
  for (auto& c : head) c = (wchar_t)towlower(c);
  std::wstring tl = tdir;
  for (auto& c : tl) c = (wchar_t)towlower(c);
  if (head != tl) return;

  // 目录名必须是 7z 的临时命名
  std::wstring leaf = FileName(src);
  if (leaf.size() < 3) return;
  if (!(leaf[0] == L'7' && leaf[1] == L'z')) return;

  // 必须确实是解压出来的补丁（含安装器自身）
  wchar_t self[MAX_PATH]; GetModuleFileNameW(nullptr, self, MAX_PATH);
  if (FileName(self) != FileName(Join(src, FileName(self)))) return;

  // 本进程正从该目录运行，删不掉自己的 exe；先把其余内容删掉（立即回收绝大部分空间），
  // 再把 exe 与目录登记为"重启后删除"。
  RemoveTree(src, false);                                   // 清内容
  MoveFileExW(self, nullptr, MOVEFILE_DELAY_UNTIL_REBOOT);  // 自己：重启后删
  MoveFileExW(src.c_str(), nullptr, MOVEFILE_DELAY_UNTIL_REBOOT);   // 空目录
}

static bool RunInstall() {
  // 1) 目标校验
  if (!ValidGameDir(g_gameDir)) {
    MessageBoxW(g_hwnd, L"所选目录不是有效的游戏目录。\n\n需要包含 Game.exe 与 script.cpk。",
                L"目录无效", MB_ICONERROR);
    return false;
  }
  // 2) 语言（决定存档目录）
  std::wstring lang = DetectLangFrom(g_gameDir);
  if (lang.empty()) lang = L"JP";
  g_lang = lang;

  // 3) 收集文件
  SetStatus(L"正在统计文件…", 0);
  g_tasks.clear();
  CollectFiles(g_srcDir, L"", g_tasks);
  g_total = (int)g_tasks.size();
  if (g_total == 0) {
    MessageBoxW(g_hwnd, L"未找到可安装的补丁文件。", L"错误", MB_ICONERROR);
    return false;
  }
  // 4) 备份
  SetStatus(L"正在备份原文件…", 2);
  SYSTEMTIME st; GetLocalTime(&st);
  wchar_t stamp[64];
  wsprintfW(stamp, L"_cn_patch_backup_%04d%02d%02d_%02d%02d%02d",
            st.wYear, st.wMonth, st.wDay, st.wHour, st.wMinute, st.wSecond);
  // 必须用 Join：g_gameDir 以『游戏目录名』结尾（自动探测时没有尾部分隔符），
  // 直接相加会把备份建到游戏目录的【同级】，卸载器就再也找不到它
  // （实测为此在 steamapps/common 下散落了 41 个 _cn_patch_backup_*）。
  std::wstring bak = Join(g_gameDir, stamp);
  CreateDirectoryW(bak.c_str(), nullptr);
  // 备份将被覆盖的既有文件（根目录 + 分号路径兼容子目录）。
  //
  // ★ 别备份"已经是我们自己"的文件 —— 重装时那个位置本来就是我们上次装的补丁，
  //   备份它没有意义，而且会害了卸载：卸载器看到"备份里有这个文件"就当作
  //   "安装前就存在"去**恢复**它，于是补丁文件被原样留下，卸载不干净。
  //   （实测：对已装过补丁的目录再装一次，卸载后 dinput8/d3d9/dxgi/VSFilter
  //     都还留在游戏目录里，而纯净母本并没有这些文件。）
  //   判据用内容比对：payload 里有同名文件、且内容一致 → 是自己人，不备份。
  //   内容不同说明玩家装的是别家的补丁/原版文件，那必须备份，卸载时得以还原。
  //
  //   注意比对的是 payload **根目录**的同名文件，不是相同相对路径 ——
  //   兼容子目录里的那份正是我们从根目录拷进去的（见步骤 6.5），
  //   payload 里压根没有那个子目录，按相对路径找会一律找不到。
  auto IsOursAlready = [&](const std::wstring& candidate) {
    std::wstring inPayload = Join(g_srcDir, FileName(candidate));
    return Exists(inPayload) && SameContents(candidate, inPayload);
  };
  // 代理文件（不含 boot.bat）：装完会被我们的版本覆盖，卸载时该删除而不是恢复，
  // 所以"内容已经是我们自己的"时候不备份。
  const wchar_t* proxyKeep[] = { L"dinput8.dll", L"VSFilter.dll",
                                 L"d3d9", L"d3d10", L"d3d10_1", L"d3d10core",
                                 L"d3d11", L"dxgi" };
  for (auto n : proxyKeep) {
    std::wstring s = Join(g_gameDir, n);
    if (!Exists(s)) continue;
    if (IsOursAlready(s)) continue;              // 上次装的补丁，不备份
    CopyFileW(s.c_str(), Join(bak, n).c_str(), FALSE);
  }
  // boot.bat 单独处理：它是**游戏自己的文件**（我们只改写内容），
  // 卸载时必须还原成原版那行 launcher.exe —— 所以它永远要备份，不做内容比对
  // （比对反而会误判：boot.bat 在"已装过补丁"的目录里内容也跟我们写的一样，
  //   但它不是补丁文件，卸载后不能删掉）。
  {
    std::wstring s = Join(g_gameDir, L"boot.bat");
    if (Exists(s)) CopyFileW(s.c_str(), Join(bak, L"boot.bat").c_str(), FALSE);
  }
  // 子目录清单：按当前目录名算出来的分号片段 + 硬编码的 NOTES DaSH
  //（后者兼容早期版本留下的目录；重名去重，免得同一份文件备份两次）
  {
    std::vector<std::wstring> subs = SemicolonFragments(g_gameDir);
    bool hasNotes = false;
    for (auto& s : subs) if (_wcsicmp(s.c_str(), L"NOTES DaSH") == 0) hasNotes = true;
    if (!hasNotes) subs.push_back(L"NOTES DaSH");
    for (auto& sub : subs) {
      // 别把备份目录自己（_cn_patch_backup_*）当成兼容子目录
      if (sub.rfind(L"_cn_patch_backup", 0) == 0) continue;
      if (!IsDir(Join(g_gameDir, sub))) continue;
      for (auto n : proxyKeep) {
        std::wstring s2 = Join(Join(g_gameDir, sub), n);
        if (!Exists(s2)) continue;
        if (IsOursAlready(s2)) continue;         // 同理：自己人不备份
        CreateDirectoryW(Join(bak, sub).c_str(), nullptr);
        CopyFileW(s2.c_str(), Join(Join(bak, sub), n).c_str(), FALSE);
      }
    }
  }
  if (!Exists(Join(g_gameDir, L"_cn_patch_boot_orig.bat")) && Exists(Join(g_gameDir, L"boot.bat")))
    CopyFileW(Join(g_gameDir, L"boot.bat").c_str(),
              Join(g_gameDir, L"_cn_patch_boot_orig.bat").c_str(), TRUE);

  // 5) 清字体缓存
  SetStatus(L"正在清理旧字体缓存…", 4);
  const wchar_t* fpats[] = { L"font_", L"outline_" };
  std::wstring fdir = Join(g_gameDir, L"languagebarrier\\fonts");
  for (auto p : fpats) {
    WIN32_FIND_DATAW fd;
    HANDLE h = FindFirstFileW(Join(fdir, std::wstring(p) + L"*.dds").c_str(), &fd);
    if (h != INVALID_HANDLE_VALUE) {
      do { DeleteFileW(Join(fdir, fd.cFileName).c_str()); } while (FindNextFileW(h, &fd));
      FindClose(h);
    }
  }
  DeleteFileW(Join(fdir, L"fontData.bin").c_str());

  // 6) 复制
  g_copied = 0;
  for (auto& t : g_tasks) {
    // 安装器自己不需要进游戏目录 —— 卸载靠「卸载汉化.exe」，
    // 重装直接再跑一次安装包即可。留着它只是多一个看不懂的文件。
    if (t.second == L"f" && FileName(t.first) == L"RNDZhSetup.exe") continue;
    if (!CopyOne(t.first, t.second == L"d")) {
      std::wstring msg = L"复制失败：\n" + t.first +
                         L"\n\n可能原因：游戏正在运行、文件被占用、或无写入权限。";
      MessageBoxW(g_hwnd, msg.c_str(), L"安装失败", MB_ICONERROR);
      return false;
    }
    g_copied++;
    if ((g_copied & 7) == 0 || g_copied == g_total) {
      int pct = 5 + (int)(92.0 * g_copied / g_total);
      SetStatus(L"正在安装…", pct);
    }
  }

  // 6.5) 目录名含分号时，补一个「分号后片段同名」的子目录，把代理 DLL 放进去。
  //      加载器把目录名按 `;` 切开后，是拿这些片段当**相对目录名**去搜的，
  //      所以本地 DLL 只有放进去才会被加载（机制见 SemicolonFragments 的注释）。
  //      名字按 g_gameDir 实时算，Steam 正本 / 任意副本 / 用户改名后的目录都能自动兼容。
  {
    std::vector<std::wstring> frags = SemicolonFragments(g_gameDir);
    // 进度文案不写"分号兼容目录"这种实现词 —— 玩家看进度条时只需要知道"还在装"。
    if (!frags.empty()) SetStatus(L"正在安装…", 95);
    for (auto& frag : frags) {
      std::wstring sub = Join(g_gameDir, frag);
      CreateDirectoryW(sub.c_str(), nullptr);
      if (!IsDir(sub)) continue;          // 建不出来（名字非法/权限）就跳过，下面还有 step 9 兜底
      for (auto n : kProxyFiles) {
        std::wstring src = Join(g_gameDir, n);
        if (Exists(src)) CopyFileW(src.c_str(), Join(sub, n).c_str(), FALSE);
      }
    }
  }

  // 7) 写回 boot.bat
  SetStatus(L"正在完成…", 97);
  {
    std::wstring bb = Join(g_gameDir, L"boot.bat");
    std::ofstream f(bb, std::ios::binary | std::ios::trunc);
    f << "@echo off\r\n\r\nstart launcher.exe " << (lang == L"EN" ? "EN" : "JP") << "\r\n";
  }

  // 8) 清掉历史安装留下的残留。
  //    · RNDZhSetup.exe —— 旧版本会把它一起拷进游戏目录；没有任何用处
  //      （重装直接再跑一次安装包），留着只是多一个看不懂的文件。
  //    · RNDZhUninstall.exe —— 卸载器**旧名**。新版改名成「卸载汉化.exe」
  //      （旧名与 RNDZhLauncher.exe 太像，容易误点成卸载）。
  //      升级安装时这里不清，游戏目录里会同时躺着新旧两个卸载器。
  //    只删「不是我正在运行的那一份」—— 比较**完整路径**，不能只比文件名，
  //    否则从游戏目录内运行时会把两者视为同一个而永远跳过。
  {
    wchar_t self[MAX_PATH]; GetModuleFileNameW(nullptr, self, MAX_PATH);
    std::wstring selfPath = self;
    const wchar_t* staleNames[] = { L"RNDZhSetup.exe", L"RNDZhUninstall.exe",
                                    L"RNDZh-Uninstall.exe" };
    for (auto n : staleNames) {
      std::wstring stale = Join(g_gameDir, n);
      if (Exists(stale) && _wcsicmp(stale.c_str(), selfPath.c_str()) != 0) {
        SetFileAttributesW(stale.c_str(), FILE_ATTRIBUTE_NORMAL);
        DeleteFileW(stale.c_str());
      }
    }
  }

  // 9) 自检：路径含分号时，确认片段子目录里真的有 dinput8.dll。
  //    这一步是给"静默失效"兜底的 —— 加载器找不到本地 DLL 时，游戏不会报错，
  //    只是显示原版语言，玩家和我们都发现不了（这个坑排查了很久）。
  //    所以宁可这里明确报一次错，也不要装完等玩家来反馈"补丁没用"。
  //
  //    文案只说**发生了什么 + 怎么办**，不解释分号/加载器这些机制 ——
  //    玩家看到"分号会让加载器跳过 DLL"也做不了什么，只会更困惑。
  {
    std::vector<std::wstring> frags = SemicolonFragments(g_gameDir);
    for (auto& frag : frags) {
      std::wstring probe = Join(Join(g_gameDir, frag), L"dinput8.dll");
      if (!Exists(probe)) {
        std::wstring msg = L"安装已完成，但补丁可能无法生效。\n\n"
            L"请把游戏文件夹改成不含分号（;）的名字，然后重新安装一次。";
        MessageBoxW(g_hwnd, msg.c_str(), L"补丁可能不会生效", MB_ICONWARNING);
        break;
      }
    }
  }

  SetStatus(L"安装完成", 100);
  return true;
}

// ───────────────────────── 绘制 ─────────────────────────
static Font* F(float sz, bool bold = false) {
  static std::map<int, Font*> cache;
  int k = (int)(sz * 10) + (bold ? 100000 : 0);
  auto it = cache.find(k);
  if (it != cache.end()) return it->second;
  Font* f = new Font(g_ff, sz, bold ? FontStyleBold : FontStyleRegular, UnitPixel);
  cache[k] = f; return f;
}
static void FillRR(Graphics& g, const RectF& r, float rad, const Color& c) {
  GraphicsPath p; float d = rad * 2;
  p.AddArc(r.X, r.Y, d, d, 180, 90);
  p.AddArc(r.GetRight() - d, r.Y, d, d, 270, 90);
  p.AddArc(r.GetRight() - d, r.GetBottom() - d, d, d, 0, 90);
  p.AddArc(r.X, r.GetBottom() - d, d, d, 90, 90);
  p.CloseFigure(); SolidBrush b(c); g.FillPath(&b, &p);
}
static void StrokeRR(Graphics& g, const RectF& r, float rad, const Color& c, float w) {
  GraphicsPath p; float d = rad * 2;
  p.AddArc(r.X, r.Y, d, d, 180, 90);
  p.AddArc(r.GetRight() - d, r.Y, d, d, 270, 90);
  p.AddArc(r.GetRight() - d, r.GetBottom() - d, d, d, 0, 90);
  p.AddArc(r.X, r.GetBottom() - d, d, d, 90, 90);
  p.CloseFigure(); Pen pen(c, w); g.DrawPath(&pen, &p);
}
static void Txt(Graphics& g, const wchar_t* s, Font* f, const Color& c, float x, float y, int align = 0) {
  SolidBrush b(c); StringFormat sf; sf.SetAlignment((StringAlignment)align);
  g.DrawString(s, -1, f, RectF(x, y, 0, 0), &sf, &b);
}
static void TxtR(Graphics& g, const wchar_t* s, Font* f, const Color& c, const RectF& r,
                 int align = 0, int valign = 1) {
  SolidBrush b(c); StringFormat sf;
  sf.SetAlignment((StringAlignment)align); sf.SetLineAlignment((StringAlignment)valign);
  g.DrawString(s, -1, f, r, &sf, &b);
}

// ── 布局（单一栅格：左边距 24，内容宽 432）──
// 所有控件都从这几个常量推导，改窗口大小时不会散架。
// 注意：这些是**逻辑**坐标。实际绘制时 Paint 会先 ScaleTransform 到物理像素，
// 鼠标消息进来则用 unscale() 换回逻辑坐标；原生 EDIT 子控件是物理坐标，
// 创建与 WM_SIZE 时都要乘 S。三处不一致就会「看着对、点不准」。
static const float PAD = 24.f;                       // 左右边距
static const float CW  = (float)WIN_W - PAD * 2;     // 内容宽度
static RectF TitleRect()   { return RectF(PAD, 18.f, CW, 26.f); }
static RectF DirLabelRect(){ return RectF(PAD, 62.f, CW, 18.f); }
static RectF FieldRect()   { return RectF(PAD, 84.f, CW - 76.f, 34.f); }
static RectF BrowseRect()  { return RectF(PAD + CW - 68.f, 84.f, 68.f, 34.f); }
static RectF HintRect()    { return RectF(PAD, 124.f, CW, 18.f); }
static RectF TrackRect()   { return RectF(PAD, 152.f, CW, 6.f); }
static RectF StatusRect()  { return RectF(PAD, 166.f, CW, 18.f); }
static RectF InstallRect() { return RectF(PAD + CW - 196.f, WIN_H - 54.f, 96.f, 34.f); }
static RectF CancelRect()  { return RectF(PAD + CW - 92.f, WIN_H - 54.f, 92.f, 34.f); }

// DPI 缩放（三个窗口同一套做法）。安装器带原生 EDIT 子控件，所以除了绘制坐标，
// 子控件的位置/尺寸也要按 S 换算 —— 见 SyncEditRect()。
static float S = 1.0f;
static inline float unscale(int v) { return (float)v / S; }

// 把 EDIT 子控件摆到 FieldRect() 的位置（物理像素）
static void SyncEditRect() {
  if (!g_hEdit) return;
  RectF f = FieldRect();
  SetWindowPos(g_hEdit, nullptr,
               (int)(f.X * S), (int)(f.Y * S),
               (int)(f.Width * S), (int)(f.Height * S),
               SWP_NOZORDER | SWP_NOACTIVATE);
}

static void Paint(HDC hdc) {
  RECT rc; GetClientRect(g_hwnd, &rc);
  const int pw = rc.right, ph = rc.bottom;
  HDC mem = CreateCompatibleDC(hdc);
  HBITMAP bmp = CreateCompatibleBitmap(hdc, pw, ph);
  HBITMAP old = (HBITMAP)SelectObject(mem, bmp);
  {
    Graphics g(mem);
    g.SetSmoothingMode(SmoothingModeAntiAlias);
    g.SetTextRenderingHint(TextRenderingHintAntiAliasGridFit);
    g.ScaleTransform((float)pw / WIN_W, (float)ph / WIN_H);
    S = (float)pw / WIN_W;
    SolidBrush bg(C_BG); g.FillRectangle(&bg, 0, 0, WIN_W, WIN_H);

    // 顶部标题条（浅灰 + 图标 + 标题一行）
    SolidBrush panel(C_PANEL); g.FillRectangle(&panel, 0, 0, WIN_W, 54);
    if (g_iconBmp) {
      GraphicsPath clip; float d0 = 10;
      RectF ib(PAD, 14, 26, 26);
      clip.AddArc(ib.X, ib.Y, d0, d0, 180, 90);
      clip.AddArc(ib.GetRight()-d0, ib.Y, d0, d0, 270, 90);
      clip.AddArc(ib.GetRight()-d0, ib.GetBottom()-d0, d0, d0, 0, 90);
      clip.AddArc(ib.X, ib.GetBottom()-d0, d0, d0, 90, 90);
      clip.CloseFigure(); g.SetClip(&clip);
      g.DrawImage(g_iconBmp, (INT)ib.X, (INT)ib.Y, (INT)ib.Width, (INT)ib.Height);
      g.ResetClip();
    }
    Txt(g, L"ROBOTICS;NOTES DaSH 简中补丁 AI人工精校版", F(15, true), C_TEXT, PAD + 36, 19);
    // 版本号右对齐放同一条栏的右端（整串连排太挤，实测 389/396 px）
    TxtR(g, (std::wstring(L"v") + VER).c_str(), F(12), C_DIM,
         RectF(PAD, 22.f, CW, 18.f), 2, 1);

    // 游戏目录：真正的 EDIT 子控件负责显示与编辑（见 g_hEdit），
    // 这里只画标签、外框和「浏览」按钮。
    // 不再手绘输入框 —— 手绘版没有插入符、选区、剪贴板和输入法支持，
    // 用户反馈"打不了字"正是这个原因。原生 EDIT 这些全都自带。
    Txt(g, L"游戏目录", F(13), C_DIM, DirLabelRect().X, DirLabelRect().Y);
    {
      RectF fr = FieldRect();
      // 只画边框：EDIT 自己填白底，画重了会盖住文字
      StrokeRR(g, fr, 4, C_BORDER, 1.f);

      RectF br = BrowseRect();
      bool hot = (g_hot == 1);
      FillRR(g, br, 4, hot ? C_PANEL : C_BG);
      StrokeRR(g, br, 4, hot ? C_DIM : C_BORDER, 1.f);
      TxtR(g, L"浏览…", F(13), C_TEXT, br, 1, 1);
    }

    // 一行提示（找到/没找到/装过）
    if (!g_gameVer.empty()) {
      Color hc = g_failed ? C_ERR : (g_done ? C_OK : C_DIM);
      if (g_gameDir.empty()) hc = C_WARN;
      Txt(g, g_gameVer.c_str(), F(12), hc, HintRect().X, HintRect().Y);
    }

    // 进度条（未开始时只显示状态文字，不画空槽，避免界面看起来"半成品"）
    if (g_pct >= 0) {
      RectF tr = TrackRect();
      FillRR(g, tr, 3, C_TRACK);
      if (g_pct > 0) {
        RectF fg(tr.X, tr.Y, tr.Width * g_pct / 100.f, tr.Height);
        FillRR(g, fg, 3, g_failed ? C_ERR : C_ACCENT);
      }
    }
    if (!g_status.empty())
      Txt(g, g_status.c_str(), F(12), g_failed ? C_ERR : C_DIM,
          StatusRect().X, StatusRect().Y);

    // 按钮（右对齐）
    {
      RectF ir = InstallRect();
      if (g_done) {
        // 完成态：蓝色「启动游戏」= 真按钮。以前这里是灰色「已完成」，
        // 占着主按钮的位置却什么都干不了（用户：还不如显示启动游戏）。
        bool hot = (g_hot == 2);
        FillRR(g, ir, 4, hot ? C_ACCENTH : C_ACCENT);
        TxtR(g, L"启动游戏", F(14, true), C_WHITE, ir, 1, 1);
      } else {
        bool can = !g_gameDir.empty() && g_pct < 0;
        Color ic = !can ? C_TRACK : (g_hot == 2 ? C_ACCENTH : C_ACCENT);
        FillRR(g, ir, 4, ic);
        TxtR(g, L"安装", F(14, true), can ? C_WHITE : C_MUTED, ir, 1, 1);
      }

      RectF cr = CancelRect();
      bool ch = (g_hot == 3);
      FillRR(g, cr, 4, ch ? C_PANEL : C_BG);
      StrokeRR(g, cr, 4, ch ? C_DIM : C_BORDER, 1.f);
      TxtR(g, g_done ? L"关闭" : L"取消", F(14), C_TEXT, cr, 1, 1);
    }
  }
  BitBlt(hdc, 0, 0, pw, ph, mem, 0, 0, SRCCOPY);
  SelectObject(mem, old); DeleteObject(bmp); DeleteDC(mem);
}

// 命中判定：入参是**物理**像素（鼠标消息给的），先换回逻辑坐标再比。
static int Hit(int px, int py) {
  int x = (int)unscale(px), y = (int)unscale(py);
  auto in = [&](const RectF& r) {
    return x >= r.X && x <= r.GetRight() && y >= r.Y && y <= r.GetBottom();
  };
  if (g_done) {
    if (in(InstallRect())) return 2;    // 完成态 = 「启动游戏」
  } else if (g_pct < 0) {
    if (in(InstallRect())) return 2;
    if (in(FieldRect())) return 4;      // 点目录框 = 聚焦编辑
  }
  if (in(CancelRect())) return 3;
  if (!g_done && g_pct < 0 && in(BrowseRect())) return 1;
  return -1;
}

// 把 g_gameDir 写进 EDIT 控件（外部改变目录时调用）
static void PushDirToEdit() {
  if (!g_hEdit) return;
  g_syncingEdit = true;
  // 显示用规整过的路径（盘符大写、统一反斜杠）；g_gameDir 本身保持原样
  SetWindowTextW(g_hEdit, PrettyPath(g_gameDir).c_str());
  g_syncingEdit = false;
}

// 从 EDIT 控件读回目录（用户编辑后调用）
static void PullDirFromEdit() {
  if (!g_hEdit) return;
  int n = GetWindowTextLengthW(g_hEdit);
  std::wstring s(n + 1, L'\0');
  if (n > 0) GetWindowTextW(g_hEdit, &s[0], n + 1);
  s.resize(n);
  while (!s.empty() && (s.front() == L'"' || s.front() == L' ')) s.erase(s.begin());
  while (!s.empty() && (s.back() == L'"' || s.back() == L' ' || s.back() == L'\r')) s.pop_back();
  for (auto& c : s) if (c == L'/') c = L'\\';
  g_gameDir = s;
  RefreshDirHint();
}

// EDIT 子控件过程：内容变化时同步到 g_gameDir，并在按下回车时立即校验。
static LRESULT CALLBACK EditSubclass(HWND h, UINT m, WPARAM w, LPARAM l,
                                     UINT_PTR, DWORD_PTR) {
  switch (m) {
  case WM_CHAR:
    if (w == VK_RETURN) {                 // 回车 = 确认输入
      PullDirFromEdit();
      if (g_hwnd) InvalidateRect(g_hwnd, nullptr, FALSE);
      return 0;                           // 吞掉回车，避免系统提示音
    }
    break;
  case WM_KEYUP:
  case WM_PASTE:
  case WM_CUT:
  case WM_CLEAR:
    // 处理完再同步（用 PostMessage 让控件先更新文本）
    PostMessageW(g_hwnd, WM_APP + 1, 0, 0);
    break;
  case WM_KILLFOCUS:
    PullDirFromEdit();                    // 失焦时也确认一次
    InvalidateRect(g_hwnd, nullptr, FALSE);
    break;
  }
  return DefSubclassProc(h, m, w, l);
}

// 校验并刷新目录框下方那行提示。文本刻意保持简短 ——
// 玩家只需要知道"找到了没有"，不需要知道存档目录叫什么。
static void RefreshDirHint() {
  if (g_gameDir.empty()) { g_gameVer.clear(); return; }
  if (!ValidGameDir(g_gameDir)) {
    g_gameVer = L"这里没有 Game.exe，请选择游戏根目录";
    return;
  }
  std::wstring lg = DetectLangFrom(g_gameDir);
  g_gameVer = (lg == L"EN") ? L"已找到游戏（英文版）" : L"已找到游戏（日文版）";
  if (Exists(Join(g_gameDir, L"languagebarrier\\patchdef.json")))
    g_gameVer += L"，将覆盖旧补丁";
  // 注意：目录名含分号导致的兼容处理**不要在这里提示**。
  // 那是我们的实现细节，玩家既看不懂"分号片段"也不知道分子目录是干什么的；
  // 而且现在安装器会自动处理好，根本不需要玩家知情（详见 SemicolonFragments）。
  // 以前这里有句「路径含分号，已自动兼容」，属于自说自话的废话 —— 已删。
}

static void PickFolder() {
  // 用 IFileDialog（Vista+ 的"选择文件夹"）而不是 95 年代的 SHBrowseForFolder ——
  // 前者就是用户在资源管理器里熟悉的那个界面：左侧导航栏、能粘贴路径、能新建文件夹。
  IFileDialog* dlg = nullptr;
  HRESULT hr = CoCreateInstance(CLSID_FileOpenDialog, nullptr, CLSCTX_INPROC_SERVER,
                                IID_PPV_ARGS(&dlg));
  if (FAILED(hr) || !dlg) return;
  DWORD opts = 0;
  if (SUCCEEDED(dlg->GetOptions(&opts)))
    dlg->SetOptions(opts | FOS_PICKFOLDERS | FOS_FORCEFILESYSTEM | FOS_PATHMUSTEXIST);
  dlg->SetTitle(L"请选择游戏目录（内含 Game.exe）");
  if (SUCCEEDED(dlg->Show(g_hwnd))) {
    IShellItem* item = nullptr;
    if (SUCCEEDED(dlg->GetResult(&item)) && item) {
      PWSTR psz = nullptr;
      if (SUCCEEDED(item->GetDisplayName(SIGDN_FILESYSPATH, &psz)) && psz) {
        g_gameDir = psz;
        PushDirToEdit();
        CoTaskMemFree(psz);
      }
      item->Release();
    }
  }
  dlg->Release();
  RefreshDirHint();
  g_status = g_gameDir.empty() ? L"点击「安装」开始（请先完全关闭游戏）"
                               : L"点击「安装」开始（请先完全关闭游戏）";
  InvalidateRect(g_hwnd, nullptr, FALSE);
}


static void OnInstall() {
  // 目录名含分号时不再阻止安装 —— 安装过程会自动把分号后的片段名建成子目录，
  // 把代理 DLL 放进去，加载器就能找到（机制见 SemicolonFragments 的注释）。
  // 以前这里会弹窗要用户自己改名或建 junction，那是在"无法规避"的误判下写的。
  g_pct = 0; g_failed = false;
  if (!RunInstall()) { g_failed = true; g_done = false; }
  else g_done = true;
  InvalidateRect(g_hwnd, nullptr, FALSE);
  UpdateWindow(g_hwnd);
}

// 完成态的「启动游戏」= 打开**汉化启动器**（RNDZhLauncher.exe）——
// Steam 检查、DXVK 开关、字幕/cosplay 设置、游戏窗口标题劫持全在它那边，
// 绕过它直接拉游戏等于让玩家错过整套补丁设置（2026-09-13 用户指正）。
// 启动器不在了才退回：Steam 库走 steam:// 协议（客户端没开自动拉起 Steam），
// 非 Steam 目录直接跑 Game.exe。
static void LaunchGameFromSetup() {
  if (g_gameDir.empty()) return;
  // ★ 用 CreateProcess 直接拉起，不走 ShellExecute(Ex)：
  //   SEE_MASK_NOASYNC 会等 shell 把进程完全拉起来才返回，叠加杀软对
  //   刚落盘 exe 的首次扫描，点下按钮会"卡一下"才出启动器（2026-09-13 用户反馈）。
  //   CreateProcess 在进程对象建立后立即返回，启动器窗口自己慢慢出。
  std::wstring launcher = g_gameDir + L"\\RNDZhLauncher.exe";
  if (Exists(launcher)) {
    std::wstring cmd = L"\"" + launcher + L"\"";
    std::vector<wchar_t> buf(cmd.begin(), cmd.end()); buf.push_back(0);
    STARTUPINFOW si{ sizeof(si) };
    PROCESS_INFORMATION pi{};
    if (CreateProcessW(nullptr, buf.data(), nullptr, nullptr, FALSE, 0,
                       nullptr, g_gameDir.c_str(), &si, &pi)) {
      CloseHandle(pi.hThread);
      CloseHandle(pi.hProcess);
      return;
    }
  }
  // 启动器不在（异常情况）才退回：Steam 库走 steam:// 协议（客户端没开会自动
  // 先拉起 Steam 再进游戏）；非 Steam 目录直接跑 Game.exe。
  std::wstring low = g_gameDir;
  for (auto& c : low) c = (wchar_t)towlower(c);
  if (low.find(L"steamapps") != std::wstring::npos) {
    ShellExecuteW(g_hwnd, L"open", L"steam://rungameid/1111390", nullptr, nullptr, SW_SHOWNORMAL);
  } else {
    std::wstring exe = L"\"" + g_gameDir + L"\\Game.exe\"";
    std::vector<wchar_t> b2(exe.begin(), exe.end()); b2.push_back(0);
    STARTUPINFOW si2{ sizeof(si2) };
    PROCESS_INFORMATION pi2{};
    if (CreateProcessW(nullptr, b2.data(), nullptr, nullptr, FALSE, 0,
                       nullptr, g_gameDir.c_str(), &si2, &pi2)) {
      CloseHandle(pi2.hThread);
      CloseHandle(pi2.hProcess);
    }
  }
}

static LRESULT CALLBACK WndProc(HWND h, UINT m, WPARAM w, LPARAM l) {
  switch (m) {
  case WM_MOUSEMOVE: {
    int id = (g_pct >= 0 && !g_done) ? -1 : Hit(GET_X_LPARAM(l), GET_Y_LPARAM(l));
    if (id != g_hot) { g_hot = id; InvalidateRect(h, nullptr, FALSE); }
    TRACKMOUSEEVENT t{ sizeof(t) }; t.dwFlags = TME_LEAVE; t.hwndTrack = h; TrackMouseEvent(&t);
    return 0;
  }
  case WM_MOUSELEAVE: g_hot = -1; InvalidateRect(h, nullptr, FALSE); return 0;
  case WM_SETCURSOR: {
    // 若鼠标在 EDIT 子控件上，交给它自己设光标（文本区标准是 I 型）。
    // 父窗口若在这里抢着设，就会把手绘时代的"手型"盖到输入框上 ——
    // 用户反馈"移到地址框变手型而不是 I 型"就是这个原因。
    if (LOWORD(l) == HTCLIENT && g_hEdit) {
      POINT p; GetCursorPos(&p);
      RECT er; GetWindowRect(g_hEdit, &er);
      if (PtInRect(&er, p)) return DefWindowProcW(h, m, w, l);
    }
    POINT p; GetCursorPos(&p); ScreenToClient(h, &p);
    if (g_pct < 0 || g_done) {   // 完成态也要给「启动游戏」手型光标
      int id = Hit(p.x, p.y);
      if (id == 4) SetCursor(LoadCursor(nullptr, IDC_IBEAM));      // 目录框 = I 型
      else if (id >= 0) SetCursor(LoadCursor(nullptr, IDC_HAND));  // 按钮 = 手型
      else SetCursor(LoadCursor(nullptr, IDC_ARROW));
    } else SetCursor(LoadCursor(nullptr, IDC_ARROW));
    return TRUE;
  }
  case WM_LBUTTONDOWN: {
    // 点目录框区域时把焦点交给 EDIT（原生控件自己处理插入符与选区）
    if (Hit(GET_X_LPARAM(l), GET_Y_LPARAM(l)) == 4 && g_hEdit)
      SetFocus(g_hEdit);
    return 0;
  }
  case WM_LBUTTONUP: {
    int id = Hit(GET_X_LPARAM(l), GET_Y_LPARAM(l));
    if (id == 1) { PickFolder(); }
    else if (id == 2) {
      if (g_done) { LaunchGameFromSetup(); PostMessageW(h, WM_CLOSE, 0, 0); }
      else OnInstall();
    }
    else if (id == 3) { PostMessageW(h, WM_CLOSE, 0, 0); }
    else if (id == 4) {
      if (g_hEdit) SetFocus(g_hEdit);
    }
    return 0;
  }
  case WM_SETFOCUS: return 0;
  case WM_KILLFOCUS: return 0;
  // 支持把文件夹从资源管理器拖进窗口
  case WM_DROPFILES: {
    HDROP dp = (HDROP)w;
    wchar_t path[MAX_PATH] = {0};
    if (DragQueryFileW(dp, 0, path, MAX_PATH)) {
      std::wstring d = path;
      // 拖进来的可能是个子文件/子目录，往上找到含 Game.exe 的那层
      if (!ValidGameDir(d)) {
        size_t pos = d.find_last_of(L'\\');
        if (pos != std::wstring::npos) {
          std::wstring up = d.substr(0, pos);
          if (ValidGameDir(up)) d = up;
        }
      }
      g_gameDir = d;
      PushDirToEdit();
      RefreshDirHint();
      InvalidateRect(h, nullptr, FALSE);
    }
    DragFinish(dp);
    return 0;
  }
  case WM_APP + 1:            // EDIT 内容变化 → 同步并刷新提示
    PullDirFromEdit();
    InvalidateRect(h, nullptr, FALSE);
    return 0;
  case WM_PAINT: { PAINTSTRUCT ps; HDC dc = BeginPaint(h, &ps); Paint(dc); EndPaint(h, &ps); return 0; }
  case WM_ERASEBKGND: return 1;
  case WM_CLOSE:
    if (g_pct >= 0 && !g_done && !g_failed) {
      if (MessageBoxW(h, L"安装尚未完成，确定要退出吗？", L"确认", MB_YESNO | MB_ICONQUESTION) != IDYES)
        return 0;
    }
    // 安装已成功时，顺手清掉 SFX 自解压目录（那里是完整补丁副本，约 450MB）。
    // 放在关窗时做，是因为要等安装全部落盘，且此时本进程仍在运行不会删到自己。
    if (g_done) CleanupSfxTemp();
    DestroyWindow(h); return 0;
  case WM_DESTROY: PostQuitMessage(0); return 0;
  }
  return DefWindowProcW(h, m, w, l);
}

static void LoadIconRes() {
  int bestW = 0;
  for (int id = 1; id <= 8; id++) {
    HRSRC hr = FindResourceW(nullptr, MAKEINTRESOURCEW(id), MAKEINTRESOURCEW(3));
    if (!hr) continue;
    DWORD sz = SizeofResource(nullptr, hr);
    HGLOBAL hg = LoadResource(nullptr, hr); void* p = LockResource(hg);
    if (!p) continue;
    HICON ico = CreateIconFromResourceEx((PBYTE)p, sz, TRUE, 0x00030000, 0, 0, LR_DEFAULTCOLOR);
    if (!ico) continue;
    ICONINFO ii = { 0 }; GetIconInfo(ico, &ii);
    BITMAP bm = { 0 }; GetObject(ii.hbmColor, sizeof(bm), &bm);
    int W = bm.bmWidth, H = bm.bmHeight;
    if (W > bestW) {
      Gdiplus::Bitmap* b = new Gdiplus::Bitmap(W, H, PixelFormat32bppARGB);
      Graphics gg(b); HDC dc = gg.GetHDC();
      DrawIconEx(dc, 0, 0, ico, W, H, 0, nullptr, DI_NORMAL);
      gg.ReleaseHDC(dc);
      if (b->GetLastStatus() == Ok) { if (g_iconBmp) delete g_iconBmp; g_iconBmp = b; bestW = W; }
      else delete b;
    }
    if (ii.hbmColor) DeleteObject(ii.hbmColor);
    if (ii.hbmMask) DeleteObject(ii.hbmMask);
    DestroyIcon(ico);
  }
}

int WINAPI wWinMain(HINSTANCE hInst, HINSTANCE, PWSTR, int) {
  GdiplusStartupInput gi; ULONG_PTR tk; GdiplusStartup(&tk, &gi, nullptr);
  g_srcDir = ExeDir();

  const wchar_t* cand[] = { L"Microsoft YaHei UI", L"Microsoft YaHei", L"SimHei", L"SimSun", L"MS Gothic" };
  for (auto nm : cand) {
    FontFamily* f = new FontFamily(nm);
    if (f->IsAvailable()) { g_ff = f; break; }
    delete f;
  }
  if (!g_ff) g_ff = new FontFamily(L"Arial");
  LoadIconRes();

  g_gameDir = AutoDetectGame();

  // 静默模式（/silent [目标目录]）：不建窗口，直接安装并返回退出码。
  // 用途：自动化验证「安装->启动->卸载->回到纯净」，也方便玩家脚本化部署。
  // 目标目录优先取命令行里的第二个参数，否则用自动探测结果。
  {
    std::wstring cl = GetCommandLineW();
    std::wstring lower = cl;
    for (auto& c : lower) c = (wchar_t)towlower(c);

    // 自检模式（/selftest）：不开窗口，把语言判定与路径规范化跑一遍并写结果。
    // 提权窗口无法被自动化截图/点击（UIPI），所以把"能不能正确判定"这件事
    // 做成可脚本验证的纯逻辑测试，避免只能靠人眼看。
    if (lower.find(L"/selftest") != std::wstring::npos) {
      int argc = 0;
      LPWSTR* argv = CommandLineToArgvW(GetCommandLineW(), &argc);
      std::wstring target;
      if (argv && argc >= 2 && argv[1][0] != L'/') {
        target = argv[1];
        for (auto& c : target) if (c == L'/') c = L'\\';
        while (!target.empty() && target.back() == L'\\') target.pop_back();
      }
      if (argv) LocalFree(argv);

      // 用 UTF-8 字节写文件，不要用 std::wofstream ——
      // wofstream 用默认 locale，遇到第一个非 ASCII 字符就会截断，
      // 结果中文路径在日志里"消失"，看起来像判定失败（其实是日志的问题）。
      {
        std::ofstream out("D:\\rnd_selftest.txt", std::ios::binary | std::ios::trunc);
        auto put = [&](const char* k, const std::wstring& v) {
          int n = WideCharToMultiByte(CP_UTF8, 0, v.c_str(), (int)v.size(),
                                      nullptr, 0, nullptr, nullptr);
          std::string u8(n, 0);
          if (n) WideCharToMultiByte(CP_UTF8, 0, v.c_str(), (int)v.size(),
                                     &u8[0], n, nullptr, nullptr);
          out << k << u8 << "\n";
        };
        auto putb = [&](const char* k, bool b) { out << k << (b ? "1" : "0") << "\n"; };
        if (out) {
          put("target=", target);
          {
            wchar_t cw[MAX_PATH] = {0};
            GetCurrentDirectoryW(MAX_PATH, cw);
            put("cwd=", cw);
            wchar_t mp[MAX_PATH] = {0};
            GetModuleFileNameW(nullptr, mp, MAX_PATH);
            put("module=", mp);
            put("srcDir=", g_srcDir);
            wchar_t lb[MAX_PATH] = {0};
            DWORD ln = GetEnvironmentVariableW(L"RNDZH_LAUNCH_DIR", lb, MAX_PATH);
            put("env_launch_dir=", (ln > 0 && ln < MAX_PATH) ? std::wstring(lb) : L"(none)");
            std::wstring autoDir = AutoDetectGame();
            put("detected_auto=", autoDir);
            // 对自动探测到的目录也判一次语言 —— 这才是"用户双击安装包"时
            // 真正会被使用的值（target 为空表示没传参数）。
            put("auto_lang=", DetectLangFrom(autoDir));
            putb("auto_valid=", ValidGameDir(autoDir));
            putb("auto_patched=", Exists(Join(autoDir, L"languagebarrier\patchdef.json")));
          }
          putb("exists=", IsDir(target));
          putb("validGameDir=", ValidGameDir(target));
          put("detectedLang=", DetectLangFrom(target));
          putb("alreadyPatched=", Exists(Join(target, L"languagebarrier\\patchdef.json")));
        }
      }
      GdiplusShutdown(tk);
      return 0;
    }

    if (lower.find(L"/silent") != std::wstring::npos) {
      // 解析第二个参数作为目标目录（跳过 exe 路径本身）
      int argc = 0;
      LPWSTR* argv = CommandLineToArgvW(GetCommandLineW(), &argc);
      // 关键：给出目标目录时必须以它为准。旧逻辑写成
      //     if (IsDir(argv[1])) g_gameDir = argv[1];
      // 于是 IsDir 一旦失败就**静默保留 AutoDetectGame() 的结果**，把补丁装到了
      // 自动探测到的另一个游戏目录（实测：传 D:\ZZGAME\...，日志却显示
      // dst=...\Steam\...\ROBOTICS;NOTES DaSH）。现在明确失败，绝不悄悄换目标。
      if (argv && argc >= 2 && argv[1][0] != L'/') {
        std::wstring d = argv[1];
        if (!d.empty() && (d.back() == L'"')) d.pop_back();
        for (auto& c : d) if (c == L'/') c = L'\\';
        while (!d.empty() && d.back() == L'\\') d.pop_back();
        if (!IsDir(d)) {
          if (argv) LocalFree(argv);
          GdiplusShutdown(tk);
          return 2;
        }
        g_gameDir = d;
        g_gameVer = L"(silent) 指定目录";
      }
      if (argv) LocalFree(argv);
      bool ok = !g_gameDir.empty() && RunInstall();
      if (ok) CleanupSfxTemp();       // 装完清掉 SFX 解压残留
      GdiplusShutdown(tk);
      return ok ? 0 : 1;
    }
  }

  if (!g_gameDir.empty()) {
    RefreshDirHint();
  } else {
    g_gameVer = L"未自动找到游戏，请点「浏览…」或直接把游戏文件夹拖进来";
  }

  WNDCLASSEXW wc{ sizeof(wc) };
  wc.lpfnWndProc = WndProc; wc.hInstance = hInst;
  wc.hCursor = LoadCursor(nullptr, IDC_ARROW);
  wc.lpszClassName = L"RNDZhSetupWnd"; wc.hbrBackground = nullptr;
  wc.hIcon = LoadIconW(hInst, MAKEINTRESOURCEW(101)); wc.hIconSm = wc.hIcon;
  RegisterClassExW(&wc);

  DWORD style = WS_OVERLAPPEDWINDOW & ~(WS_THICKFRAME | WS_MAXIMIZEBOX);
  // DPI 感知：先声明，再按真实 DPI 换算客户区尺寸（否则 125% 下被位图拉伸变糊）
  SetProcessDPIAware();
  HDC screen = GetDC(nullptr);
  float dpi = (float)GetDeviceCaps(screen, LOGPIXELSX);
  ReleaseDC(nullptr, screen);
  if (dpi <= 0) dpi = 96.f;
  S = dpi / 96.f;
  int cw = (int)(WIN_W * S + 0.5f), ch = (int)(WIN_H * S + 0.5f);
  int sw = GetSystemMetrics(SM_CXSCREEN), sh = GetSystemMetrics(SM_CYSCREEN);
  RECT r{ 0, 0, cw, ch };
  AdjustWindowRect(&r, style, FALSE);
  int ww = r.right - r.left, wh = r.bottom - r.top;
  g_hwnd = CreateWindowExW(0, wc.lpszClassName, (std::wstring(L"ROBOTICS;NOTES DaSH 简体中文 AI人工精校版 v") + VER + L" · 安装程序").c_str(),
                           style, (sw - ww) / 2, (sh - wh) / 2, ww, wh,
                           nullptr, nullptr, hInst, nullptr);

  // 目录框：原生 EDIT 子控件。
  // 它自带插入符、选区、剪贴板、输入法（中文输入）、自动横向滚动 ——
  // 之前手绘的输入框只能处理 ASCII 按键，用户反馈"打不了字"就是这个原因。
  // 子控件用**物理**像素定位，所以 SyncEditRect() 里乘了 S。
  {
    RectF f = FieldRect();
    std::wstring shown = PrettyPath(g_gameDir);   // 盘符大写 + 统一反斜杠
    g_hEdit = CreateWindowExW(
        WS_EX_CLIENTEDGE, L"EDIT", shown.c_str(),
        WS_CHILD | WS_VISIBLE | WS_TABSTOP | ES_AUTOHSCROLL,
        (int)(f.X * S), (int)(f.Y * S),
        (int)(f.Width * S), (int)(f.Height * S),
        g_hwnd, (HMENU)ID_EDIT_DIR, hInst, nullptr);
    SendMessageW(g_hEdit, WM_SETFONT, (WPARAM)GetStockObject(DEFAULT_GUI_FONT), TRUE);
    SendMessageW(g_hEdit, EM_SETLIMITTEXT, MAX_PATH * 2, 0);
    SetWindowSubclass(g_hEdit, EditSubclass, 1, 0);
    SyncEditRect();
  }

  DragAcceptFiles(g_hwnd, TRUE);     // 允许把游戏文件夹拖进窗口
  ShowWindow(g_hwnd, SW_SHOW); UpdateWindow(g_hwnd);

  MSG msg;
  while (GetMessageW(&msg, nullptr, 0, 0)) { TranslateMessage(&msg); DispatchMessageW(&msg); }
  GdiplusShutdown(tk);
  return 0;
}
