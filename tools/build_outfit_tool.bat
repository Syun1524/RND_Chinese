@echo off
REM Build RNDZhOutfitTool.exe (dev-only outfit verification tool).
REM Needs VS2022 (local: C:\VS2022BT). Keep comments ASCII (cmd parses REM in OEM codepage).
setlocal
call "C:\VS2022BT\VC\Auxiliary\Build\vcvars32.bat" >nul
cd /d "%~dp0"
cl /nologo /std:c++17 /EHsc /utf-8 /O2 /MT ^
   RNDZhOutfitTool.cpp ^
   /link /SUBSYSTEM:WINDOWS /ENTRY:wWinMainCRTStartup ^
   gdiplus.lib shell32.lib user32.lib gdi32.lib ole32.lib ^
   /OUT:RNDZhOutfitTool.exe
if errorlevel 1 ( echo BUILD FAILED & exit /b 1 )
echo BUILD OK
dir /b RNDZhOutfitTool.exe
