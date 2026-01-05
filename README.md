# Orion Drift Legacy Launcher

Run old versions of Orion Drift

## Dependencies
- Python 3

## Get started

<details>
   <summary>Windows instructions:</summary>

   <br>
   
**Install:**

1. Install pipx

   `py -m pip install --user pipx`

2. Add pipx to PATH

   `py -m pipx ensurepath`

3. **Close and re-open command prompt**

4. Install legacy launcher

   `pipx install a2-legacy-launcher`

5. Run Legacy Launcher

   Check `a2ll -ls` or [the archive](https://dl.obelous.dev/public/A2-archive/) for available versions.
   
   ```
   These all install the same version:
   a2ll 1.0.25889
   a2ll 25889
   a2ll 41924491
   ```
   
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

5. Run Legacy Launcher

   Check `a2ll -ls` or [the archive](https://dl.obelous.dev/public/A2-archive/) for available versions.
   
   ```
   These all install the same version:
   a2ll 1.0.25889
   a2ll 25889
   a2ll 41924491
   ```

</details>

<details>
   <summary>MacOS instructions:</summary>
   
   <br>

   > Currently only Intel Macs are supported, if you own an ARM Mac please DM me
   
   **Install:**

1. Install homebrew

   `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`

2. Install dependencies

   `brew install python3 pipx openjdk`

3. Add pipx to PATH

   `pipx ensurepath`

4. **Close and re-open terminal**

5. Add java to PATH

   `sudo ln -sfn /usr/local/opt/openjdk/libexec/openjdk.jdk /Library/Java/JavaVirtualMachines/openjdk.jdk`
   `echo 'export PATH="/opt/homebrew/opt/openjdk/bin:$PATH"' >> ~/.zshrc`
   `echo 'export CPPFLAGS="-I/opt/homebrew/opt/openjdk/include"' >> ~/.zshrc`
   `source ~/.zshrc`

6. Install legacy launcher

   `pipx install a2-legacy-launcher`

7. Run Legacy Launcher

   Check `a2ll -ls` or [the archive](https://dl.obelous.dev/public/A2-archive/) for available versions.
   
   ```
   These all install the same version:
   a2ll 1.0.25889
   a2ll 25889
   a2ll 41924491
   ```

</details>

<details>
   <summary>Quest instructions</summary>
   
   <br>
   
   **Install:**

1. Connect to a computer or [android phone](https://play.google.com/store/apps/details?id=eu.sisik.hackendebug)

   Run `adb tcpip 5555`

3. Install termux

   [Termux APK](https://github.com/termux/termux-app/releases/download/v0.118.3/termux-app_v0.118.3+github-debug_arm64-v8a.apk)

4. Run the helper script in termux
   
   ```
   curl -L https://obelous.dev/a2ll.sh | bash
   ```
   
   I suggest opening this page on the quest browser and copy pasting this command.

</details>

## Usage

```
usage: a2ll [-h] [-v] [-a APK] [-o OBB] [-i INI] [-c COMMANDLINE] [-so SO] [-rn] [-p] [-rm] [-l] [-ls] [-op] [-sp] [-sk] [-cc] [-r] [download]

A2 Legacy Launcher

positional arguments:
  download              Build version to download and install -

options:
  -h, --help            show this help message and exit
  -v, --version         show program's version number and exit
  -a APK, --apk APK     Path/URL to an APK file
  -o OBB, --obb OBB     Path/URL to an OBB file
  -i INI, --ini INI     Path/URL/Preset for Engine.ini
                        Presets: Engine.ini, EngineVegas.ini, Engine4v4.ini, EngineNetworked.ini, EnginePlayerstart.ini
  -c COMMANDLINE, --commandline COMMANDLINE
                        Launch arguments for A2
  -so SO, --so SO       Inject a custom .so file
  -rn, --rename         Rename the package for parallel installs
  -p, --patch           Remove entitlement check from libUnreal.so
  -rm, --remove         Uninstall all versions
  -l, --logs            Pull game logs from the headset
  -ls, --list           List available versions
  -op, --open           Launch the game once finished
  -sp, --strip          Strip permissions to skip pompts on first launch
  -sk, --skipdecompile  Reuse previously decompiled files
  -cc, --clearcache     Delete cached downloads
  -r, --restore         Restore to the latest version
```

#### Extra context:

- `a2ll [version code/CL/1.0.CL]` This automatically downloads a version and uses the correct flags to install it, renaming if possible (see compatibility below).

- `--clearcache` When providing a URL to the APK OBB or INI argument the script downloads and caches the file, to free up storage and delete cached downloads run the script with this argument.

- `--skipdecompile` When iterating on a single version you may wish to skip the decopilation step to save time by using the previously decompiled files, this also allows for manual modification of game files.

- `--rename` This renames the package to com.LegacyLauncher.A2 to allow for multiple versions to be installed at once, but it must be used in conjunction with `-c="-useinsecure"` on a version where this argument exists.

   > If a renamed version is installed the `--log` argument pulls the logs of the last version to that ran.

- `--commandline` Various features can be unlocked through the use of commandline options, for example: `-c="-loadreplay=../../../A2/Content/Replays/Quests/1DE99EFE4BF8C9948F487DA231824A75.a2replay` or `-c="-nullrhi"`

- `--ini` Supports local path, url and these presets `-i Engine.ini`, `-i EngineVegas.ini`, `-i Engine4V4.ini`, `-i EngineNetworked.ini` however nearly all builds use Engine.ini

   > --ini is unique because it can be ran on its own without rebuilding or reinstalling to almost instantly swap out an ini file

### Config:

The config.yml file located at `%USERPROFILE%/.a2-legacy-launcher/config.yml` currently has these settings:

```yml
autoupdate: true
manifest_url: https://dl.obelous.dev/api/raw/?path=/public/A2-archive/manifest.json
```
Auto update defaults to true so the script will update itself using update.bat or update.sh

The default manifest points to my APK archive, should you want to intergrate your own archive (further than manually using -a and -o) create a manifest like this: https://dl.obelous.dev/public/A2-archive/manifest.json and replace the url in the config.

<hr>

This product is not affiliated with Another Axiom Inc. or its videogames Gorilla Tag and Orion Drift and is not endorsed or otherwise sponsored by Another Axiom.
