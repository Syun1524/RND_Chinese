@echo off
REM Build RNDZhUninstall.exe (native Win32 + GDI+, no external deps).
REM Always recompile the resource: uninstall.rc carries the icon AND the
REM requireAdministrator manifest. The old "if not exist uninstall.res" guard meant a
REM stale .res was reused forever, and it also regenerated uninstall.rc, silently
REM dropping the manifest. Keep comments ASCII (cmd parses REM in the OEM codepage).
setlocal
call "C:\VS2022BT\VC\Auxiliary\Build\vcvars32.bat" >nul
cd /d "%~dp0"
rc /nologo /fo uninstall.res uninstall.rc
if errorlevel 1 ( echo RC FAILED & exit /b 1 )
cl /nologo /std:c++17 /EHsc /utf-8 /O2 /MT /DUNICODE /D_UNICODE ^
   RNDZhUninstall.cpp ^
   /link /SUBSYSTEM:WINDOWS /ENTRY:wWinMainCRTStartup ^
   gdiplus.lib shell32.lib user32.lib gdi32.lib ole32.lib ^
   uninstall.res /OUT:RNDZhUninstall.exe
if errorlevel 1 ( echo BUILD FAILED & exit /b 1 )
echo BUILD OK
