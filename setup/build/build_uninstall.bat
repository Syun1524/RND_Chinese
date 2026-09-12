@echo off
REM Build RNDZhUninstall.exe (native Win32 + GDI+, no external deps).
REM Sources are in ..\src, the finished exe goes to ..\bin.
REM Always recompile the resource: uninstall.rc carries the icon AND the
REM requireAdministrator manifest. The old "if not exist uninstall.res" guard meant a
REM stale .res was reused forever, and it also regenerated uninstall.rc, silently
REM dropping the manifest.
REM The .res and .obj go under %TEMP% so no build junk lands in the tree.
REM Keep comments ASCII (cmd parses REM in the OEM codepage).
setlocal
call "C:\VS2022BT\VC\Auxiliary\Build\vcvars32.bat" >nul
set "RES=%TEMP%\rnd_uninstall.res"

pushd "%~dp0..\src"
rc /nologo /fo "%RES%" uninstall.rc
if errorlevel 1 ( echo RC FAILED & popd & exit /b 1 )
popd

pushd "%TEMP%"
cl /nologo /std:c++17 /EHsc /utf-8 /O2 /MT /DUNICODE /D_UNICODE ^
   "%~dp0..\src\RNDZhUninstall.cpp" ^
   /link /SUBSYSTEM:WINDOWS /ENTRY:wWinMainCRTStartup ^
   gdiplus.lib shell32.lib user32.lib gdi32.lib ole32.lib ^
   "%RES%" /OUT:"%~dp0..\bin\RNDZhUninstall.exe"
if errorlevel 1 ( echo BUILD FAILED & popd & exit /b 1 )
popd

del "%RES%" >nul 2>&1
echo BUILD OK
