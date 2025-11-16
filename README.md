<!-- @import "[TOC]" {cmd="toc" depthFrom=1 depthTo=6 orderedList=false} -->
# Orion Drift Legacy Launcher

A script to manipulate Orion Drift APKs

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

5. Provide a CL, Version number or Version code to install

   `a2ll 5491`
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

5. Provide a CL, Version number or Version code to install

   `a2ll 5491`
    All old versions can be found here: https://dl.obelous.dev/public/A2-archive/

</details>

## Usage

```
a2ll [-h] [--version] [-a APK] [-o OBB] [-i INI] [-c COMMANDLINE] [-so SO] [-rn] [-p] [-rm] [-l] [-op] [-sp] [-sk] [-cc]

A2 Legacy Launcher

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

#### Extra context:

- `--clearcache` When providing a URL to the APK OBB or INI argument the script downloads and caches the file, to free up storage and delete cached downloads run the script with this argument.

- `--skipdecompile` When iterating on a single version you may wish to skip the decopilation step to save time by using the previously decompiled files, this also allows for manual modification of game files.

- `--rename` This renames the package to com.LegacyLauncher.A2 to allow for multiple versions to be installed at once, but it must be used in conjunction with `-c="-useinsecure"` on a version where this argument exists.

   > If a renamed version is installed the `--log` argument can be used with `--rename` to pull the logs of the renamed app.

- `--commandline` Various features can be unlocked through the use of commandline options, for example: `-c="-loadreplay=../../../A2/Content/Replays/Quests/1DE99EFE4BF8C9948F487DA231824A75.a2replay` or `-c="-nullrhi"`

- `--ini` Supports local path, url and these presets `-i Engine.ini`, `-i EngineVegas.ini`, `-i Engine4V4.ini`, `-i EngineNetworked.ini` however nearly all builds use Engine.ini

   > --ini is unique because it can be ran on its own without rebuilding or reinstalling to almost instantly swap out an ini file

## Comaptibility:

**ALL** Known versions can be made to run

However: Versions **11235 - 23189** cannot be renamed

And versions that released within the last week may not have patterns available

## How does it work?
Rebuilding the APK with debugging enabled gives permission to access the game files without root. <br>
From there we can place an Engine.ini which overrides the games file letting us load straight into the map without connecting to any servers.
