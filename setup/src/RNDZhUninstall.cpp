// 卸载汉化 — ROBOTICS;NOTES DaSH 简体中文补丁 卸载程序
// 放在补丁包根目录（= 游戏根目录），双击运行。
//
// ★ 关于文件名：产物叫「卸载汉化.exe」，不叫 RNDZhUninstall.exe。
//   原因：RNDZhLauncher.exe 与 RNDZhUninstall.exe 长得太像，两个 exe 又并排躺在
//   游戏目录里，玩家很容易点错 —— 而点错的代价是「把汉化卸了」。
//   中文名一眼就能区分，图标也换成红底垃圾桶（见 make_uninstall_icon.py）。
//   源码文件名保留 RNDZhUninstall.cpp，只有产物名改了，历史记录好对照。
//
// 卸载逻辑：
//   1. 删除补丁写入的文件（按包内清单，避免误删游戏本体）
//   2. 从最近的 _cn_patch_backup_* 备份恢复被覆盖的原文件
//   3. 恢复 _cn_patch_boot_orig.bat → boot.bat（游戏原版启动脚本）
//   4. 清理字体缓存
//
// 编译：见 build_uninstall.bat

#define WIN32_LEAN_AND_MEAN
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <windowsx.h>
#include <objidl.h>
#include <gdiplus.h>
#include <shlobj.h>
#include <string>
#include <vector>
#include <map>
#include <fstream>
#include <sstream>

#pragma comment(lib, "gdiplus.lib")
#pragma comment(lib, "shell32.lib")
#pragma comment(lib, "user32.lib")
#pragma comment(lib, "gdi32.lib")
#pragma comment(lib, "ole32.lib")

using namespace Gdiplus;

// 配色与安装器/启动器一致（纯白极简）。以前这里是深色霓虹，跟安装器对不上。
static const int WIN_W = 480, WIN_H = 300;
static const Color
  C_BG      (255, 255, 255, 255),
  C_PANEL   (255, 245, 246, 248),
  C_FIELD   (255, 255, 255, 255),
  C_BORDER  (255, 216, 220, 227),
  C_TEXT    (255,  31,  35,  40),
  C_DIM     (255, 107, 114, 128),
  C_MUTED   (255, 156, 163, 175),
  C_ACCENT  (255,  11, 107, 203),   // 主按钮（与安装器同色）
  C_ACCENTH (255,  10,  95, 176),
  C_TRACK   (255, 232, 235, 240),
  C_WHITE   (255, 255, 255, 255),
  C_OK      (255,  26, 127,  55),
  C_WARN    (255, 154, 103,   0),
  C_ERR     (255, 207,  34,  46);

// DPI 缩放（与安装器/启动器同一套做法）：声明感知 + ScaleTransform，
// 界面物理尺寸不变、但不再被系统位图拉伸变糊。
static float S = 1.0f;
static inline float unscale(int v) { return (float)v / S; }

static HWND g_hwnd;
static FontFamily* g_ff = nullptr;
static Gdiplus::Bitmap* g_iconBmp = nullptr;
static std::wstring g_dir;              // 游戏目录（= 本程序所在）
static std::wstring g_status = L"将移除补丁文件，并恢复安装前的原始文件。";
static std::wstring g_info;
static int g_pct = -1;
static bool g_done = false, g_failed = false;
static int g_hot = -1;

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
// Steam 注册表里的 SteamPath 可能是 `d:/ruanjian/steam`（小写盘符 + 正斜杠），
// 直接显示就是 `d:/ruanjian/steam\steamapps\...` 这种混合样子，看着像坏路径。
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
static std::wstring ExePath() {
  wchar_t buf[MAX_PATH]; GetModuleFileNameW(nullptr, buf, MAX_PATH);
  return buf;
}

// 让本程序把自己也删掉。
//
// 难点：运行中的 exe 不能直接 DeleteFile —— 映像被映射着，删不掉。
// 做法分两步：
//   1) **改名**成一个不显眼的名字（改"路径"是允许的，实测可行）——
//      这样游戏目录里当场就看不到"卸载汉化.exe"了，玩家观感即达成。
//   2) 起一个**隐藏的** cmd 子进程，循环尝试删除那个改名后的文件，
//      删掉就退出。它自旋等待本进程结束（本进程一退出，文件就能删了）。
//
// 为什么用"循环重试"而不是让 cmd 睡固定时长：进程退出与文件句柄释放的时机
// 不能精确保证，固定 sleep 可能睡不够（删不掉）或睡过头（白等）。重试最稳。
//
// 为什么还是用了 cmd：不依赖任何外部工具自删的办法只有
// "登记重启后删除"，那会让文件留到重启为止 —— 玩家会以为没卸干净。
// cmd.exe 是 Windows 自带的，且这里用 CREATE_NO_WINDOW 起进程，**不会闪黑框**。
// 万一 cmd 起不来，还有 MoveFileEx(重启后删除) 兜底。
static void ScheduleSelfDelete() {
  std::wstring self = ExePath();
  std::wstring dir = ExeDir();
  std::wstring tmp = Join(dir, L"_uninstall_del.exe");

  // 清掉上次可能留下的残留
  DeleteFileW(tmp.c_str());

  std::wstring target = self;
  if (MoveFileW(self.c_str(), tmp.c_str())) {
    target = tmp;                      // 改名成功 → 删这个新名字
    MoveFileExW(tmp.c_str(), nullptr, MOVEFILE_DELAY_UNTIL_REBOOT);   // 兜底
  } else {
    MoveFileExW(self.c_str(), nullptr, MOVEFILE_DELAY_UNTIL_REBOOT);  // 兜底
  }

  // 起隐藏 cmd：最多重试 120 次（约 2 分钟），文件一消失就退出。
  // 路径用引号包住，避免空格/中文出问题。
  std::wstring cmd = L"cmd.exe /c for /l %i in (1,1,120) do @("
                     L"del /f /q \"" + target + L"\" >nul 2>&1 & "
                     L"if not exist \"" + target + L"\" exit /b)";
  std::vector<wchar_t> buf(cmd.begin(), cmd.end());
  buf.push_back(0);

  STARTUPINFOW si{};
  si.cb = sizeof(si);
  PROCESS_INFORMATION pi{};
  if (CreateProcessW(nullptr, buf.data(), nullptr, nullptr, FALSE,
                     CREATE_NO_WINDOW | DETACHED_PROCESS, nullptr, dir.c_str(),
                     &si, &pi)) {
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
  }
}
static std::wstring FileName(const std::wstring& p) {
  size_t s = p.find_last_of(L"\\/");
  return s == std::wstring::npos ? p : p.substr(s + 1);
}

// 删除目录树（先删文件再删目录）
static void RemoveTree(const std::wstring& root, bool removeRoot = true) {
  WIN32_FIND_DATAW fd;
  HANDLE h = FindFirstFileW(Join(root, L"*").c_str(), &fd);
  if (h != INVALID_HANDLE_VALUE) {
    do {
      std::wstring n = fd.cFileName;
      if (n == L"." || n == L"..") continue;
      std::wstring p = Join(root, n);
      if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
        RemoveTree(p, true);
      } else {
        SetFileAttributesW(p.c_str(), FILE_ATTRIBUTE_NORMAL);
        DeleteFileW(p.c_str());
      }
    } while (FindNextFileW(h, &fd));
    FindClose(h);
  }
  if (removeRoot) RemoveDirectoryW(root.c_str());
}

// 列出最近的备份目录
static std::wstring FindLatestBackup() {
  std::wstring best; FILETIME bestT{};
  WIN32_FIND_DATAW fd;
  HANDLE h = FindFirstFileW(Join(g_dir, L"_cn_patch_backup_*").c_str(), &fd);
  if (h == INVALID_HANDLE_VALUE) return L"";
  do {
    if (!(fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)) continue;
    if (CompareFileTime(&fd.ftLastWriteTime, &bestT) > 0) {
      bestT = fd.ftLastWriteTime; best = fd.cFileName;
    }
  } while (FindNextFileW(h, &fd));
  FindClose(h);
  return best.empty() ? L"" : Join(g_dir, best);
}

static std::vector<std::wstring> g_files, g_dirs;   // 待删除（包内清单）
static std::vector<std::wstring> g_fragDirs;        // 分号路径兼容目录（只清我们的文件）

static std::wstring ParentDir(const std::wstring& p) {
  size_t s = p.find_last_of(L"\\/");
  return s == std::wstring::npos ? std::wstring() : p.substr(0, s);
}

// 收集本程序所在目录里"属于补丁"的文件。
// 按白名单：补丁特有的文件名/目录；不碰游戏本体（.cpk / Game.exe / launcher 等）。
static void CollectPatchFiles() {
  const wchar_t* files[] = {
    L"dinput8.dll", L"VSFilter.dll", L"RNDZhLauncher.exe",
    L"卸载汉化.exe",              // 本程序（新版名）
    L"RNDZhUninstall.exe",        // 旧版名：装着旧补丁的目录里可能还有它
    L"RNDZhSetup.exe",            // 更早的安装器副本（现在不再安装，但历史残留要清）
    L"d3d9", L"d3d10", L"d3d10_1", L"d3d10core", L"d3d11", L"dxgi",
    L"proton_boot_fix.sh", L"安装说明.txt", L"_cn_patch_boot_orig.bat",
    // 早期版本调试用的日志；万一旧副本里有，卸载时一并清掉
    L"RNDZhSetup_silent_log.txt",
  };
  for (auto f : files) {
    std::wstring p = Join(g_dir, f);
    if (Exists(p)) g_files.push_back(f);
  }
  // 注意：dinput8.dll 与 DXVK 的"生效位置"不止根目录 —— 目录名含分号时，
  // 加载器会去「分号后片段同名」的子目录里找（机制见安装器 SemicolonFragments 的注释），
  // 安装器会把代理 DLL 复制进那些子目录，卸载时同样要清掉。
  // `NOTES DaSH` 是 Steam 正本目录名 `ROBOTICS;NOTES DaSH` 算出来的那一个，
  // 这里保留是为了兼容早期版本（当时还没按名字动态计算）留下的目录。
  const wchar_t* dirs[] = { L"languagebarrier", L"NOTES DaSH" };
  for (auto d : dirs) {
    if (IsDir(Join(g_dir, d))) g_dirs.push_back(d);
  }
  // 按当前目录名算出来的片段，单独放 g_fragDirs：
  // 它们是**通用**目录名（比如游戏副本名里带的那一长串），不能像 languagebarrier
  // 那样整树删 —— 万一里面本来就有用户自己的东西，整树删就成了删人数据。
  // 对它们只做文件级处理（我们放进去的那几个代理文件），清空后才删目录。
  {
    std::wstring name = FileName(g_dir);
    size_t p = name.find(L';');
    while (p != std::wstring::npos) {
      size_t q = name.find(L';', p + 1);
      std::wstring seg = (q == std::wstring::npos) ? name.substr(p + 1)
                                                   : name.substr(p + 1, q - p - 1);
      p = q;
      while (!seg.empty() && (seg.back() == L' ' || seg.back() == L'.')) seg.pop_back();
      if (seg.empty()) continue;
      // 去重：Steam 正本会同时命中硬编码的 `NOTES DaSH` 和这里算出来的同一个名字，
      // 处理两遍会把第一遍刚从备份恢复出来的文件再删掉。
      bool dup = false;
      for (auto& d : g_dirs) if (_wcsicmp(d.c_str(), seg.c_str()) == 0) { dup = true; break; }
      for (auto& d : g_fragDirs) if (_wcsicmp(d.c_str(), seg.c_str()) == 0) { dup = true; break; }
      if (!dup && IsDir(Join(g_dir, seg))) g_fragDirs.push_back(seg);
    }
  }
}

static void SetStatus(const std::wstring& s, int pct) {
  g_status = s; g_pct = pct;
  InvalidateRect(g_hwnd, nullptr, FALSE);
  UpdateWindow(g_hwnd);
  MSG m; while (PeekMessageW(&m, nullptr, 0, 0, PM_REMOVE)) { TranslateMessage(&m); DispatchMessageW(&m); }
}

static bool RunUninstall() {
  // 规则（避免误删游戏文件 / 误删用户原有补丁）：
  //   · boot.bat        —— 游戏文件，**只恢复、不删除**
  //   · 安装前就存在的文件（备份里有）—— **恢复**原文件
  //   · 安装时才新增的文件（备份里没有）—— **删除**
  //   · languagebarrier/ —— 补丁专属目录；若备份里有它的内容则先删再恢复
  std::wstring bak = FindLatestBackup();
  auto InBackup = [&](const std::wstring& rel) {
    return !bak.empty() && Exists(Join(bak, rel));
  };

  // 1) boot.bat：优先用安装时保留的游戏原版；否则用备份里的
  SetStatus(L"正在恢复启动脚本…", 5);
  {
    std::wstring orig = Join(g_dir, L"_cn_patch_boot_orig.bat");
    std::wstring bb = Join(g_dir, L"boot.bat");
    if (Exists(orig)) {
      CopyFileW(orig.c_str(), bb.c_str(), FALSE);
    } else if (InBackup(L"boot.bat")) {
      CopyFileW(Join(bak, L"boot.bat").c_str(), bb.c_str(), FALSE);
    } else if (Exists(bb)) {
      // 无备份：把它改回不触发劫持的样子
      std::ifstream in(bb, std::ios::binary);
      std::stringstream ss; ss << in.rdbuf();
      std::string t = ss.str();
      if (t.find("RNDZhLauncher") != std::string::npos ||
          t.find("LauncherC0") != std::string::npos) {
        std::ofstream f(bb, std::ios::binary | std::ios::trunc);
        f << "@echo off\r\n\r\nstart launcher.exe JP\r\n";
      }
    }
  }

  // 2) languagebarrier：备份里有内容 → 先删后恢复；否则整目录删除
  for (size_t i = 0; i < g_dirs.size(); i++) {
    std::wstring d = g_dirs[i];
    SetStatus(L"正在处理 " + d + L" …", 20 + (int)(40.0 * i / (g_dirs.size() + g_files.size())));
    std::wstring dst = Join(g_dir, d);
    bool hadBefore = false;
    if (!bak.empty()) {
      WIN32_FIND_DATAW fd;
      HANDLE h = FindFirstFileW(Join(Join(bak, d), L"*").c_str(), &fd);
      if (h != INVALID_HANDLE_VALUE) { hadBefore = true; FindClose(h); }
    }
    RemoveTree(dst, true);
    if (hadBefore) {
      // 恢复备份里该目录下的所有文件（保留结构）
      std::vector<std::pair<std::wstring, std::wstring>> items;   // (rel, isDir)
      std::vector<std::pair<std::wstring, std::wstring>> stack;
      stack.push_back({ d, L"d" });
      while (!stack.empty()) {
        auto cur = stack.back(); stack.pop_back();
        WIN32_FIND_DATAW fd;
        HANDLE hh = FindFirstFileW(Join(Join(bak, cur.first), L"*").c_str(), &fd);
        if (hh == INVALID_HANDLE_VALUE) continue;
        do {
          std::wstring n = fd.cFileName;
          if (n == L"." || n == L"..") continue;
          std::wstring rel = cur.first + L"\\" + n;
          if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
            stack.push_back({ rel, L"d" });
          } else {
            items.push_back({ rel, L"f" });
          }
        } while (FindNextFileW(hh, &fd));
        FindClose(hh);
      }
      for (auto& it : items) {
        std::wstring src = Join(bak, it.first);
        std::wstring dd = Join(g_dir, it.first);
        // 确保父目录存在
        size_t pos = dd.find_last_of(L'\\');
        if (pos != std::wstring::npos) {
          std::wstring parent = dd.substr(0, pos);
          // 逐级创建
          for (size_t k = parent.find(L':'); k != std::wstring::npos; ) {
            size_t nx = parent.find(L'\\', k + 2);
            if (nx == std::wstring::npos) break;
            CreateDirectoryW(parent.substr(0, nx).c_str(), nullptr);
            k = nx;
          }
          CreateDirectoryW(parent.c_str(), nullptr);
        }
        CopyFileW(src.c_str(), dd.c_str(), FALSE);
      }
    }
  }

  // 3) 补丁文件：备份里有 → 恢复；没有 → 删除
  for (size_t i = 0; i < g_files.size(); i++) {
    std::wstring f = g_files[i];
    SetStatus(L"正在处理 " + f + L" …",
              60 + (int)(35.0 * i / (g_files.size() + g_dirs.size())));
    std::wstring p = Join(g_dir, f);
    if (!Exists(p)) continue;
    if (InBackup(f)) {
      CopyFileW(Join(bak, f).c_str(), p.c_str(), FALSE);
    } else {
      SetFileAttributesW(p.c_str(), FILE_ATTRIBUTE_NORMAL);
      if (!DeleteFileW(p.c_str())) {
        // 正在运行的自身 → 安排重启后删除
        MoveFileExW(p.c_str(), nullptr, MOVEFILE_DELAY_UNTIL_REBOOT);
      }
    }
  }

  // 3.5) 分号路径兼容目录：只删我们放进去的代理 DLL。
  //      这些目录名来自游戏目录名本身（可能是玩家自己的命名），里面未必只有我们的东西，
  //      所以逐文件删、且只删 kProxyFiles 里那几个名字；目录空了才顺手删掉，
  //      非空就留着 —— 绝不能整树删，那会连玩家的文件一起清掉。
  for (auto& d : g_fragDirs) {
    SetStatus(L"正在清理 " + d + L" …", 95);
    std::wstring dir = Join(g_dir, d);
    static const wchar_t* proxy[] = {
      L"dinput8.dll", L"d3d9", L"d3d10", L"d3d10_1", L"d3d10core", L"d3d11", L"dxgi",
      L"VSFilter.dll" };
    for (auto n : proxy) {
      std::wstring rel = Join(d, n);
      std::wstring p = Join(g_dir, rel);
      if (!Exists(p)) continue;
      // 备份里有的（= 安装前就存在于该子目录）要恢复，不能删
      if (InBackup(rel)) {
        CopyFileW(Join(bak, rel).c_str(), p.c_str(), FALSE);
      } else {
        SetFileAttributesW(p.c_str(), FILE_ATTRIBUTE_NORMAL);
        DeleteFileW(p.c_str());
      }
    }
    // 目录已空则删掉；非空（RemoveDirectory 失败）说明还有别人的东西，保留
    RemoveDirectoryW(dir.c_str());
  }

  // 5) 删除本次/历史安装留下的备份目录。
  //    备份里有的是游戏原文件（恢复后就不再需要），有的是补丁文件（已删）。
  //    旧版安装器把备份建到了【上级目录】（路径少了分隔符），所以两处都要扫。
  {
    const std::wstring dirs_to_scan[] = { g_dir, ParentDir(g_dir) };
    for (auto& base : dirs_to_scan) {
      if (base.empty()) continue;
      WIN32_FIND_DATAW fd;
      HANDLE h = FindFirstFileW(Join(base, L"_cn_patch_backup_*").c_str(), &fd);
      if (h == INVALID_HANDLE_VALUE) continue;
      do {
        if (!(fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)) continue;
        RemoveTree(Join(base, fd.cFileName), true);
      } while (FindNextFileW(h, &fd));
      FindClose(h);
    }
    // 还有本次安装记录的原版 boot 备份
    DeleteFileW(Join(g_dir, L"_cn_patch_boot_orig.bat").c_str());
  }

  // 6) 把自己也删掉。
  //    卸载器是补丁的一部分，补丁没了它就没有存在意义 ——
  //    留在游戏目录里只会让玩家以为"还没卸干净"。
  //    注意放在**最后**：前面所有步骤都依赖本进程在运行。
  //
  //    有个坑：调用方（OnUninstall / 静默模式）在本函数返回后还要用窗口/返回值，
  //    所以这里只做"改名 + 登记重启删除"，不真的把 exe 删掉
  //    （运行中的 exe 也删不掉，见 ScheduleSelfDelete 的注释）。
  ScheduleSelfDelete();


  SetStatus(L"卸载完成", 100);
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

static RectF OkRect()     { return RectF(WIN_W - 24.f - 150.f - 12.f - 100.f,
                                         WIN_H - 24.f - 40.f, 150.f, 40.f); }
static RectF CancelRect() { return RectF(WIN_W - 24.f - 100.f, WIN_H - 24.f - 40.f,
                                         100.f, 40.f); }

static void Paint(HDC hdc) {
  RECT rc; GetClientRect(g_hwnd, &rc);
  // 物理客户区尺寸：绘制用 ScaleTransform 缩到逻辑尺寸，BitBlt 要用物理值
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
    SolidBrush panel(C_PANEL); g.FillRectangle(&panel, 0, 0, WIN_W, 72);
    Pen edge(C_BORDER, 1.f); g.DrawLine(&edge, 0, 72, WIN_W, 72);

    if (g_iconBmp) {
      GraphicsPath clip; float d0 = 14; RectF ib(20, 16, 40, 40);
      clip.AddArc(ib.X, ib.Y, d0, d0, 180, 90);
      clip.AddArc(ib.GetRight()-d0, ib.Y, d0, d0, 270, 90);
      clip.AddArc(ib.GetRight()-d0, ib.GetBottom()-d0, d0, d0, 0, 90);
      clip.AddArc(ib.X, ib.GetBottom()-d0, d0, d0, 90, 90);
      clip.CloseFigure(); g.SetClip(&clip);
      g.DrawImage(g_iconBmp, (INT)ib.X, (INT)ib.Y, (INT)ib.Width, (INT)ib.Height);
      g.ResetClip();
    }
    Txt(g, L"卸载汉化", F(16, true), C_TEXT, 72, 18);
    Txt(g, L"ROBOTICS;NOTES DaSH 简体中文补丁", F(12), C_DIM, 74, 44);

    Txt(g, L"游戏目录", F(13), C_DIM, 24, 92);
    {
      RectF er(24, 112, (float)WIN_W - 48, 34);
      FillRR(g, er, 6, C_FIELD);
      StrokeRR(g, er, 6, C_BORDER, 1.f);
      TxtR(g, PrettyPath(g_dir).c_str(), F(13), C_TEXT,
           RectF(er.X + 10, er.Y, er.Width - 20, er.Height), 0, 1);
    }
    // 状态行：只是一句"在做什么/做完了"，不写实现细节。
    Txt(g, g_status.c_str(), F(12), g_failed ? C_ERR : (g_done ? C_OK : C_DIM),
        24, 168);
    if (g_pct >= 0) {
      RectF bg2(24, 196, (float)WIN_W - 48, 10);
      FillRR(g, bg2, 5, C_TRACK);
      if (g_pct > 0) {
        RectF fg2(bg2.X, bg2.Y, bg2.Width * g_pct / 100.f, bg2.Height);
        FillRR(g, fg2, 5, g_failed ? C_ERR : C_ACCENT);
      }
    }
    {
      // 按钮只画**一个**：
      //   未开始 → 「确认卸载」（红色＝破坏性操作）
      //   已完成 → 「关闭」
      // 以前完成态会把主按钮改成灰色「已完成」并保留「关闭」，等于留个点不动的按钮，
      // 看着像还没做完。
      bool can = !g_done && g_pct < 0;
      if (!g_done) {
        RectF r = OkRect();
        bool rHot = (g_hot == 1) && can;
        FillRR(g, r, 6, can ? (rHot ? Color(255, 176, 28, 38) : C_ERR) : C_TRACK);
        TxtR(g, g_failed ? L"重试" : L"确认卸载", F(15, true),
             can ? C_WHITE : C_MUTED, r, 1, 1);
        RectF c = CancelRect();
        bool cHot = (g_hot == 2);
        FillRR(g, c, 6, cHot ? C_PANEL : C_FIELD);
        StrokeRR(g, c, 6, cHot ? C_DIM : C_BORDER, 1.f);
        TxtR(g, L"取消", F(15), C_TEXT, c, 1, 1);
      } else {
        RectF c = CancelRect();          // 完成态：单个按钮，放右下
        bool cHot = (g_hot == 2);
        FillRR(g, c, 6, cHot ? C_PANEL : C_FIELD);
        StrokeRR(g, c, 6, cHot ? C_DIM : C_BORDER, 1.f);
        TxtR(g, L"关闭", F(15), C_TEXT, c, 1, 1);
      }
    }
  }
  BitBlt(hdc, 0, 0, pw, ph, mem, 0, 0, SRCCOPY);
  SelectObject(mem, old); DeleteObject(bmp); DeleteDC(mem);
}

static int Hit(int px, int py) {
  int x = (int)unscale(px), y = (int)unscale(py);
  auto in = [&](const RectF& r) {
    return x >= r.X && x <= r.GetRight() && y >= r.Y && y <= r.GetBottom();
  };
  if (!g_done && g_pct < 0 && in(OkRect())) return 1;
  if (in(CancelRect())) return 2;
  return -1;
}

static void OnUninstall() {
  if (MessageBoxW(g_hwnd, L"将移除中文补丁并恢复安装前的文件。\n\n确定继续吗？",
                  L"确认卸载", MB_YESNO | MB_ICONQUESTION) != IDYES) return;
  g_pct = 0; g_failed = false;
  if (!RunUninstall()) { g_failed = true; }
  else g_done = true;
  InvalidateRect(g_hwnd, nullptr, FALSE);
  UpdateWindow(g_hwnd);
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
  case WM_LBUTTONUP: {
    int id = Hit(GET_X_LPARAM(l), GET_Y_LPARAM(l));
    if (id == 1) OnUninstall();
    else if (id == 2) PostMessageW(h, WM_CLOSE, 0, 0);
    return 0;
  }
  case WM_PAINT: { PAINTSTRUCT ps; HDC dc = BeginPaint(h, &ps); Paint(dc); EndPaint(h, &ps); return 0; }
  case WM_ERASEBKGND: return 1;
  case WM_CLOSE: DestroyWindow(h); return 0;
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
  g_dir = ExeDir();

  const wchar_t* cand[] = { L"Microsoft YaHei UI", L"Microsoft YaHei", L"SimHei", L"SimSun", L"MS Gothic" };
  for (auto nm : cand) {
    FontFamily* f = new FontFamily(nm);
    if (f->IsAvailable()) { g_ff = f; break; }
    delete f;
  }
  if (!g_ff) g_ff = new FontFamily(L"Arial");
  LoadIconRes();

  // 自检：必须在游戏目录里运行
  if (!Exists(Join(g_dir, L"Game.exe"))) {
    MessageBoxW(nullptr, L"请把本程序放在游戏目录（内含 Game.exe）里运行。",
                L"位置不正确", MB_ICONERROR);
    return 1;
  }
  CollectPatchFiles();
  // 静默模式（/silent）：不建窗口，直接跑卸载并返回。
  // 用途：自动化验证「安装->启动->卸载->回到纯净」，以及玩家/脚本一键卸载。
  {
    std::wstring cl = GetCommandLineW();
    for (auto& c : cl) c = (wchar_t)towlower(c);
    if (cl.find(L"/silent") != std::wstring::npos) {
      bool ok = RunUninstall();
      GdiplusShutdown(tk);
      return ok ? 0 : 1;
    }
  }
  std::wstring bak = FindLatestBackup();
  {
    wchar_t buf[256];
    wsprintfW(buf, L"将移除 %d 个文件、%d 个目录。%s",
              (int)g_files.size(), (int)g_dirs.size(),
              bak.empty() ? L"（未找到备份，将仅删除补丁文件）" : L"已找到安装备份，将恢复原文件。");
    g_info = buf;
  }
  if (g_files.empty() && g_dirs.empty()) {
    MessageBoxW(nullptr, L"未检测到已安装的补丁文件。", L"无需卸载", MB_ICONINFORMATION);
    return 0;
  }

  WNDCLASSEXW wc{ sizeof(wc) };
  wc.lpfnWndProc = WndProc; wc.hInstance = hInst;
  wc.hCursor = LoadCursor(nullptr, IDC_ARROW);
  wc.lpszClassName = L"RNDZhUninstallWnd"; wc.hbrBackground = nullptr;
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
  RECT r{ 0, 0, cw, ch };
  AdjustWindowRect(&r, style, FALSE);
  int ww = r.right - r.left, wh = r.bottom - r.top;
  int sw = GetSystemMetrics(SM_CXSCREEN), sh = GetSystemMetrics(SM_CYSCREEN);
  g_hwnd = CreateWindowExW(0, wc.lpszClassName, L"卸载汉化 — ROBOTICS;NOTES DaSH 简体中文补丁",
                           style, (sw - ww) / 2, (sh - wh) / 2, ww, wh,
                           nullptr, nullptr, hInst, nullptr);
  ShowWindow(g_hwnd, SW_SHOW); UpdateWindow(g_hwnd);

  MSG msg;
  while (GetMessageW(&msg, nullptr, 0, 0)) { TranslateMessage(&msg); DispatchMessageW(&msg); }
  GdiplusShutdown(tk);
  return 0;
}
