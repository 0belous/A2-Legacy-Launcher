<!-- @import "[TOC]" {cmd="toc" depthFrom=1 depthTo=6 orderedList=false} -->
# Orion Drift Legacy Launcher

A small script to patch Orion Drift APKs to run offline.

Particularly useful when running old versions of Orion Drift that don't have servers anymore.

> [!NOTE]
> This project has NOT been extensively tested, please report bugs in [issues](https://github.com/0belous/A2-Legacy-Launcher/issues)

## Dependencies
- Python 3

## Get started

**Setup:**

- Open cmd (without admin)
- `cd Documents`

1. Clone this repo

    `git clone https://github.com/0belous/A2-Legacy-Launcher.git`

2. Change directory

    `cd A2-Legacy-Launcher`

4. Connect your headset and autorize usb debugging (developer mode required)

5. Run the script

    `py main.py`

6. Provide it with an APK and OBB to install

    All old versions can be found here: https://dl.obelous.dev/public/A2-archive/

## Usage
`./main.ps1` Interactive installer, drag and drop files

Alternatively you can use arguments
```
USAGE:
./main.ps1 (no parameters, interactive mode)
./main.ps1 [-apk <path_to_apk>] [-obb <path_to_obb>] [-ini <path_to_ini>] [-help]
```

## How does it work?
Rebuilding the APK with debugging enabled gives permission to access the game files without root. <br>
From there we can place an Engine.ini which overrides the games file letting us bypass authentication and load straight into the map without connecting to any servers.

It's simple but tedious
