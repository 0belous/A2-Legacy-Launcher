@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "TARGETS="
set "BUILD_ALL=0"
set "HAS_ERRORS=0"
set "PYI_COMMON_OPTS=--clean --exclude-module tkinter --exclude-module unittest --exclude-module test --exclude-module tests --exclude-module pydoc --exclude-module lib2to3 --exclude-module setuptools --exclude-module distutils --exclude-module pip --exclude-module wheel --exclude-module IPython --exclude-module jupyter --exclude-module notebook --exclude-module matplotlib --exclude-module numpy --exclude-module pandas --exclude-module scipy --exclude-module PIL --exclude-module cryptography --exclude-module OpenSSL --exclude-module bcrypt --exclude-module nacl"

if "%~1"=="" (
  set "TARGETS=windows-x64"
) else (
  call :parse_args %*
  if errorlevel 2 exit /b 0
  if errorlevel 1 exit /b %errorlevel%
)

if "%BUILD_ALL%"=="1" (
  set "TARGETS=windows-x64 linux-x64 linux-arm64"
)

if "%TARGETS%"=="" (
  echo [ERROR] No targets selected.
  call :usage
  exit /b 1
)

echo [INFO] Targets: %TARGETS%

for %%T in (%TARGETS%) do (
  call :build_target %%T
)

if "%HAS_ERRORS%"=="1" (
  echo.
  echo [ERROR] One or more targets failed.
  exit /b 1
)

echo.
echo [SUCCESS] All requested targets completed.
exit /b 0

:parse_args
if "%~1"=="" goto :eof

if /I "%~1"=="--help" (
  call :usage
  exit /b 2
)

if /I "%~1"=="-h" (
  call :usage
  exit /b 2
)

if /I "%~1"=="--all" (
  set "BUILD_ALL=1"
  shift
  goto parse_args
)

if /I "%~1"=="--target" (
  if "%~2"=="" (
    echo [ERROR] --target requires a value.
    call :usage
    exit /b 1
  )
  call :append_target "%~2"
  shift
  shift
  goto parse_args
)

echo [ERROR] Unknown argument: %~1
call :usage
exit /b 1

:append_target
for %%V in (%~1) do (
  set "TARGETS=!TARGETS! %%~V"
)
goto :eof

:usage
echo Usage: %~n0 [--all] [--target TARGET]...
echo.
echo Targets:
echo   windows-x64    Build Windows executable on host.
echo   linux-x64      Build Linux amd64 binary via Docker.
echo   linux-arm64    Build Linux arm64 binary via Docker.
echo.
echo Options:
echo   --all          Build all supported targets.
echo   --target NAME  Add a specific target (can be repeated).
echo   -h, --help     Show this help message.
goto :eof

:build_target
set "TARGET=%~1"
echo.
echo [INFO] Building !TARGET!...

if /I "!TARGET!"=="windows-x64" (
  call :build_windows_x64
  goto :eof
)

if /I "!TARGET!"=="linux-x64" (
  call :build_linux amd64
  goto :eof
)

if /I "!TARGET!"=="linux-arm64" (
  call :build_linux arm64
  goto :eof
)

echo [ERROR] Unknown target: !TARGET!
set "HAS_ERRORS=1"
goto :eof

:build_windows_x64
rmdir /s /q build >nul 2>&1
if exist "dist\uell-windows.exe" del /q "dist\uell-windows.exe" >nul 2>&1

python -m pip install pyinstaller pySmartDL colorama requests pyyaml
if errorlevel 1 (
  echo [ERROR] Failed to install Python dependencies for Windows build.
  set "HAS_ERRORS=1"
  goto :eof
)

python -m PyInstaller --onefile --name uell-windows.exe ^
  --paths src ^
  --add-data "src/ue_legacy_launcher/*.keystore;ue_legacy_launcher" ^
  %PYI_COMMON_OPTS% ^
  run_cli.py

if not exist "dist\uell-windows.exe" (
  echo [ERROR] Build failed: dist\uell-windows.exe not found.
  set "HAS_ERRORS=1"
  goto :eof
)

if not exist "%USERPROFILE%\.local\bin" mkdir "%USERPROFILE%\.local\bin"
taskkill /F /IM uell.exe >nul 2>&1
copy /Y "dist\uell-windows.exe" "%USERPROFILE%\.local\bin\uell.exe" >nul
echo [INFO] Updated %USERPROFILE%\.local\bin\uell.exe

dist\uell-windows.exe -ls
goto :eof

:build_linux
set "DOCKER_ARCH=%~1"

docker --version >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Docker is required for linux builds but was not found in PATH.
  set "HAS_ERRORS=1"
  goto :eof
)

if not exist "dist" mkdir "dist"

docker run --rm --platform linux/%DOCKER_ARCH% -v "%cd%:/workspace" -w /workspace python:3.11-bullseye /bin/bash -lc "set -euo pipefail; rm -rf build; python -m pip install --upgrade pip >/dev/null; python -m pip install pyinstaller pySmartDL colorama requests pyyaml >/dev/null; pyinstaller --onefile --strip --name uell-linux-%DOCKER_ARCH% --paths src --add-data 'src/ue_legacy_launcher/*.keystore:ue_legacy_launcher' --clean --exclude-module tkinter --exclude-module unittest --exclude-module test --exclude-module tests --exclude-module pydoc --exclude-module lib2to3 --exclude-module setuptools --exclude-module distutils --exclude-module pip --exclude-module wheel --exclude-module IPython --exclude-module jupyter --exclude-module notebook --exclude-module matplotlib --exclude-module numpy --exclude-module pandas --exclude-module scipy --exclude-module PIL --exclude-module cryptography --exclude-module OpenSSL --exclude-module bcrypt --exclude-module nacl run_cli.py"

if errorlevel 1 (
  echo [ERROR] Linux %DOCKER_ARCH% build failed.
  set "HAS_ERRORS=1"
  goto :eof
)

if not exist "dist\uell-linux-%DOCKER_ARCH%" (
  echo [ERROR] Build failed: dist\uell-linux-%DOCKER_ARCH% not found.
  set "HAS_ERRORS=1"
  goto :eof
)

echo [INFO] Built dist\uell-linux-%DOCKER_ARCH%
goto :eof
