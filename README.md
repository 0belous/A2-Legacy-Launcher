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

   `sudo apt install pipx`

2. Add pipx to PATH

   `pipx ensurepath`

4. Install legacy launcher

   `pipx install a2-legacy-launcher`

5. Install java

   `sudo apt install openjdk-21-jdk`

7. Run the script

   `a2ll`

8. If you are prompted to install java follow the instructions and restart your command prompt after.

9. Provide it with an APK and OBB to install

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
