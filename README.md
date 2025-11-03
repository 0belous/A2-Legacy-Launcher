<!-- @import "[TOC]" {cmd="toc" depthFrom=1 depthTo=6 orderedList=false} -->
# Orion Drift Legacy Launcher

A small script to make Orion Drift APKs run offline.

Particularly useful when running old versions of Orion Drift that don't have servers anymore.

## Dependencies
- Python 3

## Get started

<details>
   <summary>Windows instructions:</summary>

   <br>
   
**Install:**

1. Install pipx

   `pip install --user pipx`

2. Add pipx to PATH

   `py -m pipx ensurepath`

3. Reopen command prompt

4. Install legacy launcher

   `pipx install a2-legacy-launcher`

5. Run the script

   `a2ll`

6. If you are prompted to install java follow the instructions and restart your command prompt after.

7. Provide an APK and OBB to install

    All old versions can be found here: https://dl.obelous.dev/public/A2-archive/
</details>

<details>
   <summary>Debian instructions:</summary>
   
   <br>
   
   **Install:**

1. Insall pipx

   `sudo apt install pipx`

2. Add pipx to PATH

   `pipx ensurepath`

3. Install java

   `sudo apt install openjdk-21-jdk`

4. Install legacy launcher

   `pipx install a2-legacy-launcher`

5. Run the script

   `a2ll`

6. Provide an APK and OBB to install

    All old versions can be found here: https://dl.obelous.dev/public/A2-archive/

</details>

To update run:

`pipx upgrade a2-legacy-launcher`

## Usage

```
a2ll [-h] [-a APK] [-o OBB] [-i INI] [-c COMMANDLINE] [-so SO] [-rn] [-rm] [-l] [-op] [-sp] [-sk] [-cc]

A2 Legacy Launcher by Obelous

options:
  -h, --help            show this help message and exit
  -a APK, --apk APK     Path/URL to the source APK file
  -o OBB, --obb OBB     Path/URL to the OBB file
  -i INI, --ini INI     Path/URL to an Engine.ini
  -c COMMANDLINE, --commandline COMMANDLINE
                        What commandline options to run A2 with
  -so SO, --so SO       Inject a custom .so file
  -rn, --rename         Rename the package to allow multiple installs
  -rm, --remove         Use this if reinstalling doesnt bring you back to latest
  -l, --logs            Pull game logs from the headset
  -op, --open           Open the game once finished
  -sp, --strip          Strip permissions to skip pompts on first launch
  -sk, --skipdecompile  Reuse previously decompiled files
  -cc, --clearcache     Delete cached downloads
```

## How does it work?
Rebuilding the APK with debugging enabled gives permission to access the game files without root. <br>
From there we can place an Engine.ini which overrides the games file letting us load straight into the map without connecting to any servers.
