@echo off
rmdir /s /q build
rmdir /s /q dist

pip install pyinstaller pySmartDL colorama requests pyyaml

python -m PyInstaller --onefile --name uell-windows.exe ^
  --paths src ^
  --add-data "src/ue_legacy_launcher/*.jar;ue_legacy_launcher" ^
  --add-data "src/ue_legacy_launcher/*.keystore;ue_legacy_launcher" ^
  --add-data "src/ue_legacy_launcher/aapt2-ARM64;ue_legacy_launcher" ^
  run_cli.py

if not exist "dist\uell-windows.exe" (
  echo Build failed: dist\uell-windows.exe not found.
  pause
  exit /b 1
)

if not exist "%USERPROFILE%\.local\bin" mkdir "%USERPROFILE%\.local\bin"
taskkill /F /IM uell.exe >nul 2>&1
copy /Y "dist\uell-windows.exe" "%USERPROFILE%\.local\bin\uell.exe" >nul
echo Updated %USERPROFILE%\.local\bin\uell.exe

dist\uell-windows.exe -ls
pause
