@echo off
REM Build RNDZhLauncher.exe (native Win32 + GDI+, no Qt).
REM Needs VS2022 (local: C:\VS2022BT). v142 (x86) toolset to match the rest of the patch.
REM NOTE: keep comments in this file ASCII. cmd parses REM lines in the OEM codepage,
REM and non-ASCII text there gets split into bogus commands before the build runs.
setlocal
call "C:\VS2022BT\VC\Auxiliary\Build\vcvars32.bat" >nul
cd /d "%~dp0"
rc /nologo /fo launcher.res launcher.rc
if errorlevel 1 ( echo RC FAILED & exit /b 1 )
cl /nologo /std:c++17 /EHsc /utf-8 /O2 /MT ^
   RNDZhLauncher.cpp ^
   /link /SUBSYSTEM:WINDOWS /ENTRY:wWinMainCRTStartup ^
   gdiplus.lib shell32.lib user32.lib gdi32.lib ole32.lib ^
   launcher.res /OUT:RNDZhLauncher.exe
if errorlevel 1 ( echo BUILD FAILED & exit /b 1 )
echo BUILD OK
dir /b RNDZhLauncher.exe
