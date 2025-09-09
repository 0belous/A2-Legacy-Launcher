<!-- @import "[TOC]" {cmd="toc" depthFrom=1 depthTo=6 orderedList=false} -->
# Orion Drift Legacy Launcher

A small script to patch Orion Drift APKs to run offline.

Particularly useful when running old versions of Orion Drift that don't have servers anymore.

> [!NOTE]
> This project has NOT been extensively tested, please report bugs in [issues](https://github.com/0belous/A2-Legacy-Launcher)

## Dependencies
- Java 8+ in PATH

## Get started
1. Clone this repo

    `git clone https://github.com/0belous/A2-Legacy-Launcher.git`

2. Change directory

    `cd A2-Legacy-Launcher`

3. Enable powershell execution

    `Set-ExecutionPolicy Unrestricted`

3. Install the Android SDK

    - Download [commandline-tools](https://dl.google.com/android/repository/commandlinetools-win-13114758_latest.zip)

    - Run `./install.ps1` and drop the file in

4. Connect your headset run this then click authorize (developer mode required)

    `./android-sdk/platform-tools/adb.exe devices`

5. Run the script

    `./main.ps1`

6. Provide it wil an APK and OBB to install

    All old versions can be found here: https://dl.obelous.dev/public/A2-archive/
