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

// ───────────────────────── 外观常量（与启动器一致） ─────────────────────────
static const int WIN_W = 660, WIN_H = 360;
static const Color
  C_BG(255, 24, 27, 34), C_PANEL(255, 33, 38, 48), C_HILITE(255, 44, 50, 63),
  C_LINE(255, 62, 70, 86), C_TEXT(255, 233, 236, 242), C_DIM(255, 150, 158, 172),
  C_MUTED(255, 104, 113, 128), C_ACCENT(255, 64, 150, 255), C_WHITE(255, 255, 255, 255),
  C_OK(255, 96, 200, 130), C_WARN(255, 235, 180, 80), C_ERR(255, 235, 100, 100);

static HWND g_hwnd;
static FontFamily* g_ff = nullptr;
static Gdiplus::Bitmap* g_iconBmp = nullptr;
static std::wstring g_srcDir;      // 本程序所在目录（= 补丁文件所在）
static std::wstring g_gameDir;     // 目标游戏目录
static std::wstring g_lang = L"JP";
static std::wstring g_status = L"安装前请先完全关闭游戏，然后点击「开始安装」";
static int g_pct = -1;             // -1 = 未开始
static bool g_done = false, g_failed = false;
static int g_hot = -1;
static std::wstring g_gameVer;     // 检测到的版本描述

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
static std::wstring ExeDir() {
  wchar_t buf[MAX_PATH]; GetModuleFileNameW(nullptr, buf, MAX_PATH);
  std::wstring s(buf); size_t p = s.find_last_of(L'\\');
  return p == std::wstring::npos ? L"." : s.substr(0, p);
}
static std::wstring FileName(const std::wstring& p) {
  size_t s = p.find_last_of(L"\\/");
  return s == std::wstring::npos ? p : p.substr(s + 1);
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

// 在常见位置找游戏
static std::wstring AutoDetectGame() {
  // 1) 本程序所在目录的上层（万一被手动解压到游戏里）
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
  // 备份将被覆盖的既有文件（根目录 + NOTES DaSH 子目录）。
  // 注意 dinput8.dll / DXVK 实际生效位置是 NOTES DaSH\（游戏从那里加载），
  // 根目录那份只是双保险，两处都要备份才能完整还原。
  const wchar_t* keep[] = { L"boot.bat", L"dinput8.dll", L"VSFilter.dll",
                            L"d3d9", L"d3d10", L"d3d10_1", L"d3d10core", L"d3d11", L"dxgi" };
  for (auto n : keep) {
    std::wstring s = Join(g_gameDir, n);
    if (Exists(s)) CopyFileW(s.c_str(), Join(bak, n).c_str(), FALSE);
    std::wstring s2 = Join(Join(g_gameDir, L"NOTES DaSH"), n);
    if (Exists(s2)) {
      CreateDirectoryW(Join(bak, L"NOTES DaSH").c_str(), nullptr);
      CopyFileW(s2.c_str(), Join(Join(bak, L"NOTES DaSH"), n).c_str(), FALSE);
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

  // 7) 写回 boot.bat
  SetStatus(L"正在完成…", 97);
  {
    std::wstring bb = Join(g_gameDir, L"boot.bat");
    std::ofstream f(bb, std::ios::binary | std::ios::trunc);
    f << "@echo off\r\n\r\nstart launcher.exe " << (lang == L"EN" ? "EN" : "JP") << "\r\n";
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

static RectF BrowseRect() { return RectF(WIN_W - 130.f, 96.f, 100.f, 34.f); }
static RectF InstallRect() { return RectF(WIN_W - 350.f, WIN_H - 78.f, 150.f, 48.f); }
static RectF CancelRect() { return RectF(WIN_W - 180.f, WIN_H - 78.f, 150.f, 48.f); }

static void Paint(HDC hdc) {
  RECT rc; GetClientRect(g_hwnd, &rc);
  HDC mem = CreateCompatibleDC(hdc);
  HBITMAP bmp = CreateCompatibleBitmap(hdc, rc.right, rc.bottom);
  HBITMAP old = (HBITMAP)SelectObject(mem, bmp);
  {
    Graphics g(mem);
    g.SetSmoothingMode(SmoothingModeAntiAlias);
    g.SetTextRenderingHint(TextRenderingHintAntiAliasGridFit);
    SolidBrush bg(C_BG); g.FillRectangle(&bg, 0, 0, rc.right, rc.bottom);

    // 顶部标题栏
    SolidBrush panel(C_PANEL); g.FillRectangle(&panel, 0, 0, rc.right, 76);
    if (g_iconBmp) {
      GraphicsPath clip; float d0 = 16;
      RectF ib(24, 18, 40, 40);
      clip.AddArc(ib.X, ib.Y, d0, d0, 180, 90);
      clip.AddArc(ib.GetRight()-d0, ib.Y, d0, d0, 270, 90);
      clip.AddArc(ib.GetRight()-d0, ib.GetBottom()-d0, d0, d0, 0, 90);
      clip.AddArc(ib.X, ib.GetBottom()-d0, d0, d0, 90, 90);
      clip.CloseFigure(); g.SetClip(&clip);
      g.DrawImage(g_iconBmp, (INT)ib.X, (INT)ib.Y, (INT)ib.Width, (INT)ib.Height);
      g.ResetClip();
    }
    Txt(g, L"ROBOTICS;NOTES DaSH 简体中文补丁", F(19, true), C_TEXT, 78, 20);
    Txt(g, L"安装程序", F(13), C_DIM, 80, 46);

    // 游戏目录
    Txt(g, L"游戏目录", F(14), C_DIM, 32, 96);
    {
      RectF er(32, 118, (float)WIN_W - 200, 40);
      FillRR(g, er, 8, C_HILITE);
      Pen pn(C_LINE, 1.f); g.DrawRectangle(&pn, er.X, er.Y, er.Width, er.Height);
      TxtR(g, g_gameDir.empty() ? L"（未自动找到，请点「浏览」选择含 Game.exe 的文件夹）" : g_gameDir.c_str(),
           F(14), g_gameDir.empty() ? C_WARN : C_TEXT, RectF(er.X + 12, er.Y, er.Width - 24, er.Height), 0, 1);
      RectF br = BrowseRect();
      FillRR(g, br, 8, (g_hot == 1) ? C_ACCENT : C_HILITE);
      TxtR(g, L"浏览…", F(14), C_TEXT, br, 1, 1);
    }

    // 状态区
    {
      Color sc = g_failed ? C_ERR : (g_done ? C_OK : (g_gameDir.empty() ? C_WARN : C_DIM));
      if (g_gameDir.empty()) {
        Txt(g, L"未找到游戏目录", F(14), C_WARN, 32, 180);
      } else if (!g_gameVer.empty()) {
        Txt(g, g_gameVer.c_str(), F(14), C_OK, 32, 180);
      }

      // 进度条
      if (g_pct >= 0) {
        RectF bg2(32, 232, (float)WIN_W - 64, 12);
        FillRR(g, bg2, 6, C_HILITE);
        if (g_pct > 0) {
          RectF fg2(bg2.X, bg2.Y, bg2.Width * g_pct / 100.f, bg2.Height);
          FillRR(g, fg2, 6, g_failed ? C_ERR : C_ACCENT);
        }
        Txt(g, g_status.c_str(), F(13), g_failed ? C_ERR : C_DIM, 32, 252);
        wchar_t pb[32]; wsprintfW(pb, L"%d%%", g_pct);
        TxtR(g, pb, F(13), C_DIM, RectF(32, 252, (float)WIN_W - 64, 18), 2, 1);
      } else {
        Txt(g, g_status.c_str(), F(13), C_DIM, 32, 252);
      }
    }

    // 按钮
    {
      bool can = !g_gameDir.empty() && !g_done && g_pct < 0;
      RectF ir = InstallRect();
      FillRR(g, ir, 10, can ? ((g_hot == 2) ? Color(255,96,178,255) : C_ACCENT) : C_HILITE);
      TxtR(g, g_done ? L"已完成" : L"开始安装", F(17, true),
           can || g_done ? C_WHITE : C_MUTED, ir, 1, 1);
      RectF cr = CancelRect();
      FillRR(g, cr, 10, (g_hot == 3) ? C_HILITE : Color(255,38,44,56));
      TxtR(g, g_done ? L"关闭" : L"取消", F(17), C_TEXT, cr, 1, 1);
    }

  }
  BitBlt(hdc, 0, 0, rc.right, rc.bottom, mem, 0, 0, SRCCOPY);
  SelectObject(mem, old); DeleteObject(bmp); DeleteDC(mem);
}

static int Hit(int x, int y) {
  if (!g_gameDir.empty() && !g_done && g_pct < 0) {
    RectF r = InstallRect();
    if (x >= r.X && x <= r.GetRight() && y >= r.Y && y <= r.GetBottom()) return 2;
  }
  { RectF r = CancelRect();
    if (x >= r.X && x <= r.GetRight() && y >= r.Y && y <= r.GetBottom()) return 3; }
  { RectF r = BrowseRect();
    if (x >= r.X && x <= r.GetRight() && y >= r.Y && y <= r.GetBottom()) return 1; }
  return -1;
}

static void PickFolder() {
  BROWSEINFOW bi{}; bi.hwndOwner = g_hwnd; bi.lpszTitle = L"请选择游戏目录（内含 Game.exe）";
  bi.ulFlags = BIF_RETURNONLYFSDIRS | BIF_NEWDIALOGSTYLE;
  LPITEMIDLIST id = SHBrowseForFolderW(&bi);
  if (!id) return;
  wchar_t path[MAX_PATH];
  if (SHGetPathFromIDListW(id, path)) {
    g_gameDir = path;
    if (ValidGameDir(g_gameDir)) {
      std::wstring lg = DetectLangFrom(g_gameDir);
      g_gameVer = L"✓ 游戏目录有效";
      if (!lg.empty()) g_gameVer += (lg == L"EN") ? L"（英文版，存档目录 eng）" : L"（日文版，存档目录 jpn）";
      // 检查是否已装过
      if (Exists(Join(g_gameDir, L"languagebarrier\\patchdef.json")))
        g_gameVer += L"　· 检测到已安装过补丁，将覆盖";
    } else {
      g_gameVer = L"⚠ 该目录没有 Game.exe / script.cpk，请重新选择";
    }
    g_status = L"请点击「开始安装」";
    InvalidateRect(g_hwnd, nullptr, FALSE);
  }
  CoTaskMemFree(id);
}

static void OnInstall() {
  g_pct = 0; g_failed = false;
  if (!RunInstall()) { g_failed = true; g_done = false; }
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
  case WM_SETCURSOR: {
    POINT p; GetCursorPos(&p); ScreenToClient(h, &p);
    if (g_pct < 0 && !g_done && Hit(p.x, p.y) >= 0) SetCursor(LoadCursor(nullptr, IDC_HAND));
    else SetCursor(LoadCursor(nullptr, IDC_ARROW));
    return TRUE;
  }
  case WM_LBUTTONUP: {
    int id = Hit(GET_X_LPARAM(l), GET_Y_LPARAM(l));
    if (id == 1) PickFolder();
    else if (id == 2) OnInstall();
    else if (id == 3) PostMessageW(h, WM_CLOSE, 0, 0);
    return 0;
  }
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
    std::wstring lg = DetectLangFrom(g_gameDir);
    g_gameVer = L"✓ 已自动找到游戏目录";
    if (!lg.empty()) g_gameVer += (lg == L"EN") ? L"（英文版，存档目录 eng）" : L"（日文版，存档目录 jpn）";
    if (Exists(Join(g_gameDir, L"languagebarrier\\patchdef.json")))
      g_gameVer += L"　· 检测到已安装过，将覆盖";
  }

  WNDCLASSEXW wc{ sizeof(wc) };
  wc.lpfnWndProc = WndProc; wc.hInstance = hInst;
  wc.hCursor = LoadCursor(nullptr, IDC_ARROW);
  wc.lpszClassName = L"RNDZhSetupWnd"; wc.hbrBackground = nullptr;
  wc.hIcon = LoadIconW(hInst, MAKEINTRESOURCEW(101)); wc.hIconSm = wc.hIcon;
  RegisterClassExW(&wc);

  DWORD style = WS_OVERLAPPEDWINDOW & ~(WS_THICKFRAME | WS_MAXIMIZEBOX);
  int sw = GetSystemMetrics(SM_CXSCREEN), sh = GetSystemMetrics(SM_CYSCREEN);
  RECT r{ 0, 0, WIN_W, WIN_H };
  AdjustWindowRect(&r, style, FALSE);
  int ww = r.right - r.left, wh = r.bottom - r.top;
  g_hwnd = CreateWindowExW(0, wc.lpszClassName, L"ROBOTICS;NOTES DaSH 简体中文补丁 · 安装程序",
                           style, (sw - ww) / 2, (sh - wh) / 2, ww, wh,
                           nullptr, nullptr, hInst, nullptr);
  ShowWindow(g_hwnd, SW_SHOW); UpdateWindow(g_hwnd);

  MSG msg;
  while (GetMessageW(&msg, nullptr, 0, 0)) { TranslateMessage(&msg); DispatchMessageW(&msg); }
  GdiplusShutdown(tk);
  return 0;
}
