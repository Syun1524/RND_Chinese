@echo off
REM 编译 LanguageBarrier dinput8.dll（dinput8-Release / Win32）
REM 工具链：C:\VS2022BT（MSVC v142）+ C:\vcpkg（x86-windows-static）
setlocal
call "C:\VS2022BT\VC\Auxiliary\Build\vcvars32.bat" >nul
if errorlevel 1 ( echo VCVARS FAILED & exit /b 1 )
cd /d "%~dp0"
msbuild LanguageBarrier.vcxproj /nologo /v:minimal /t:Build /p:Configuration=dinput8-Release /p:Platform=Win32
if errorlevel 1 ( echo BUILD FAILED & exit /b 1 )
echo BUILD OK
dir /b /-c dinput8-Release\dinput8.dll
