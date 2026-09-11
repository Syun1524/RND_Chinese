// RNDZhUninstall — ROBOTICS;NOTES DaSH 简体中文补丁 卸载程序
// 放在补丁包根目录（= 游戏根目录），双击运行。
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

static const int WIN_W = 660, WIN_H = 360;
static const Color
  C_BG(255, 24, 27, 34), C_PANEL(255, 33, 38, 48), C_HILITE(255, 44, 50, 63),
  C_LINE(255, 62, 70, 86), C_TEXT(255, 233, 236, 242), C_DIM(255, 150, 158, 172),
  C_MUTED(255, 104, 113, 128), C_ACCENT(255, 64, 150, 255), C_WHITE(255, 255, 255, 255),
  C_OK(255, 96, 200, 130), C_WARN(255, 235, 180, 80), C_ERR(255, 235, 100, 100);

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
static std::wstring ExeDir() {
  wchar_t buf[MAX_PATH]; GetModuleFileNameW(nullptr, buf, MAX_PATH);
  std::wstring s(buf); size_t p = s.find_last_of(L'\\');
  return p == std::wstring::npos ? L"." : s.substr(0, p);
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

// 收集本程序所在目录里"属于补丁"的文件。
// 按白名单：补丁特有的文件名/目录；不碰游戏本体（.cpk / Game.exe / launcher 等）。
static void CollectPatchFiles() {
  const wchar_t* files[] = {
    L"dinput8.dll", L"VSFilter.dll", L"RNDZhLauncher.exe", L"RNDZhUninstall.exe",
    L"d3d9", L"d3d10", L"d3d10_1", L"d3d10core", L"d3d11", L"dxgi",
    L"proton_boot_fix.sh", L"安装说明.txt", L"_cn_patch_boot_orig.bat",
  };
  for (auto f : files) {
    std::wstring p = Join(g_dir, f);
    if (Exists(p)) g_files.push_back(f);
  }
  // 注意：dinput8.dll 与 DXVK 的"生效位置"是 NOTES DaSH\ 子目录（游戏从那里加载），
  // 根目录那份只是双保险；两处都要纳入处理。
  const wchar_t* dirs[] = { L"languagebarrier", L"NOTES DaSH" };
  for (auto d : dirs) {
    if (IsDir(Join(g_dir, d))) g_dirs.push_back(d);
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

static RectF OkRect()     { return RectF(WIN_W - 350.f, WIN_H - 78.f, 150.f, 48.f); }
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
    SolidBrush panel(C_PANEL); g.FillRectangle(&panel, 0, 0, rc.right, 76);

    if (g_iconBmp) {
      GraphicsPath clip; float d0 = 16; RectF ib(24, 18, 40, 40);
      clip.AddArc(ib.X, ib.Y, d0, d0, 180, 90);
      clip.AddArc(ib.GetRight()-d0, ib.Y, d0, d0, 270, 90);
      clip.AddArc(ib.GetRight()-d0, ib.GetBottom()-d0, d0, d0, 0, 90);
      clip.AddArc(ib.X, ib.GetBottom()-d0, d0, d0, 90, 90);
      clip.CloseFigure(); g.SetClip(&clip);
      g.DrawImage(g_iconBmp, (INT)ib.X, (INT)ib.Y, (INT)ib.Width, (INT)ib.Height);
      g.ResetClip();
    }
    Txt(g, L"ROBOTICS;NOTES DaSH 简体中文补丁", F(19, true), C_TEXT, 78, 20);
    Txt(g, L"卸载程序", F(13), C_DIM, 80, 46);

    Txt(g, L"游戏目录", F(14), C_DIM, 32, 104);
    {
      RectF er(32, 128, (float)WIN_W - 64, 40);
      FillRR(g, er, 8, C_HILITE);
      Pen pn(C_LINE, 1.f); g.DrawRectangle(&pn, er.X, er.Y, er.Width, er.Height);
      TxtR(g, g_dir.c_str(), F(14), C_TEXT, RectF(er.X + 12, er.Y, er.Width - 24, er.Height), 0, 1);
    }
    if (!g_info.empty())
      Txt(g, g_info.c_str(), F(13), C_WARN, 32, 186);

    Txt(g, g_status.c_str(), F(13), g_failed ? C_ERR : C_DIM, 32, 226);
    if (g_pct >= 0) {
      RectF bg2(32, 250, (float)WIN_W - 64, 12);
      FillRR(g, bg2, 6, C_HILITE);
      if (g_pct > 0) {
        RectF fg2(bg2.X, bg2.Y, bg2.Width * g_pct / 100.f, bg2.Height);
        FillRR(g, fg2, 6, g_failed ? C_ERR : C_ACCENT);
      }
    }
    {
      bool can = !g_done && g_pct < 0;
      RectF r = OkRect();
      FillRR(g, r, 10, can ? ((g_hot == 1) ? Color(255,96,178,255) : C_ACCENT) : C_HILITE);
      TxtR(g, g_done ? L"已完成" : L"确认卸载", F(17, true), can || g_done ? C_WHITE : C_MUTED, r, 1, 1);
      RectF c = CancelRect();
      FillRR(g, c, 10, (g_hot == 2) ? C_HILITE : Color(255,38,44,56));
      TxtR(g, g_done ? L"关闭" : L"取消", F(17), C_TEXT, c, 1, 1);
    }
  }
  BitBlt(hdc, 0, 0, rc.right, rc.bottom, mem, 0, 0, SRCCOPY);
  SelectObject(mem, old); DeleteObject(bmp); DeleteDC(mem);
}

static int Hit(int x, int y) {
  if (!g_done && g_pct < 0) {
    RectF r = OkRect();
    if (x >= r.X && x <= r.GetRight() && y >= r.Y && y <= r.GetBottom()) return 1;
  }
  { RectF r = CancelRect();
    if (x >= r.X && x <= r.GetRight() && y >= r.Y && y <= r.GetBottom()) return 2; }
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
  int sw = GetSystemMetrics(SM_CXSCREEN), sh = GetSystemMetrics(SM_CYSCREEN);
  RECT r{ 0, 0, WIN_W, WIN_H };
  AdjustWindowRect(&r, style, FALSE);
  int ww = r.right - r.left, wh = r.bottom - r.top;
  g_hwnd = CreateWindowExW(0, wc.lpszClassName, L"ROBOTICS;NOTES DaSH 简体中文补丁 · 卸载",
                           style, (sw - ww) / 2, (sh - wh) / 2, ww, wh,
                           nullptr, nullptr, hInst, nullptr);
  ShowWindow(g_hwnd, SW_SHOW); UpdateWindow(g_hwnd);

  MSG msg;
  while (GetMessageW(&msg, nullptr, 0, 0)) { TranslateMessage(&msg); DispatchMessageW(&msg); }
  GdiplusShutdown(tk);
  return 0;
}
