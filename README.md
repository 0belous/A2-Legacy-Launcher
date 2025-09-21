<!-- @import "[TOC]" {cmd="toc" depthFrom=1 depthTo=6 orderedList=false} -->
# Orion Drift Legacy Launcher

A small script to patch Orion Drift APKs to run offline.

Particularly useful when running old versions of Orion Drift that don't have servers anymore.

> [!NOTE]
> This script is not compatible with linux, if you manage to make it work feel free to create a pull request.

## Dependencies
- Python 3

## Get started

**Install:**

1. Insall pipx

   `pip install --user pipx`

2. Add pipx to PATH

   `pipx ensurepath`

3. Reopen command prompt

4. Install legacy launcher

   `pipx install git+https://github.com/0belous/A2-Legacy-Launcher.git`

5. Run the script

   `a2ll`

7. Provide it with an APK and OBB to install

    All old versions can be found here: https://dl.obelous.dev/public/A2-archive/

## Usage

```
USAGE:
py main.py [no parameters: interactive mode]
py main.py [-a --apk <path_to_apk>] [-o --obb <path_to_obb>] [-i --ini <path_to_ini>] [-help]
```

## How does it work?
Rebuilding the APK with debugging enabled gives permission to access the game files without root. <br>
From there we can place an Engine.ini which overrides the games file letting us bypass authentication and load straight into the map without connecting to any servers.

It's simple but tedious
