#!/bin/bash
set -uo pipefail

PYI_EXCLUDES=(--exclude-module tkinter --exclude-module unittest --exclude-module test --exclude-module tests --exclude-module pydoc --exclude-module lib2to3 --exclude-module setuptools --exclude-module distutils --exclude-module pip --exclude-module wheel --exclude-module IPython --exclude-module jupyter --exclude-module notebook --exclude-module matplotlib --exclude-module numpy --exclude-module pandas --exclude-module scipy --exclude-module PIL --exclude-module cryptography --exclude-module OpenSSL --exclude-module bcrypt --exclude-module nacl)

case "$(uname -m)" in
  x86_64|amd64) ARCH="amd64" ;;
  aarch64|arm64) ARCH="arm64" ;;
  *) echo "[ERROR] Unsupported host architecture: $(uname -m)"; exit 1 ;;
esac

rm -rf build
mkdir -p dist

python3 -m pip install --upgrade pip >/dev/null
python3 -m pip install pyinstaller pySmartDL colorama requests pyyaml
if [ $? -ne 0 ]; then
  echo "[ERROR] Failed to install Python dependencies."
  exit 1
fi

python3 -m PyInstaller --onefile --strip --name "uell-linux-${ARCH}" \
  --paths src \
  --add-data "src/ue_legacy_launcher/*.keystore:ue_legacy_launcher" \
  --clean "${PYI_EXCLUDES[@]}" \
  run_cli.py

if [ $? -ne 0 ] || [ ! -f "dist/uell-linux-${ARCH}" ]; then
  echo "[ERROR] Build failed: dist/uell-linux-${ARCH} not found."
  exit 1
fi

echo "[SUCCESS] Built dist/uell-linux-${ARCH}"