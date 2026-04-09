# UE Legacy Launcher

A modular version manager for Oculus VR games built with Unreal Engine.

[Repo Mirror](https://git.obelous.dev/obelous/UE-Legacy-Launcher)

## Get started

1. Navigate to releases
2. Download the version for your OS
3. Run it once to register the application URI
4. You are now ready to use legacy launcher with compatible APK archives

## Usage

```
usage: uell.exe [-h] [-v] [-y] [--archive ARCHIVE] [-a APK] [-o OBB] [-i INI] [-m MAP] [-c COMMANDLINE] [-so SO] [-rn RENAME] [-p PATCH] [-rm] [-l] [-ls] [-op] [-sp] [-sk] [-cc] [-r]
                [--set-config VALUE] [--adb ...] [-sw] [--stay] [--message MESSAGE]
                [download ...]

Legacy Launcher 1.4

positional arguments:
  download              Build version to download and install -

options:
  -h, --help            show this help message and exit
  -v, --version         show program's version number and exit
  -y, --yes, --auto-confirm
                        Automatically confirm prompts
  --archive ARCHIVE     Path/URL to a zip archive (use archive:/path/inside.apk)
  -a APK, --apk APK     Path/URL to an APK file
  -o OBB, --obb OBB     Path/URL to an OBB file
  -i INI, --ini INI     Path/URL for Engine.ini
  -m MAP, --map MAP     What map to load in format "Label|Path/To/Map"
  -c COMMANDLINE, --commandline COMMANDLINE
                        Launch arguments for UE
  -so SO, --so SO       Inject a custom .so file
  -rn RENAME, --rename RENAME
                        Rename the package to com.LegacyLauncher.<VALUE>
  -p PATCH, --patch PATCH
                        Byte pattern to patch
  -rm, --remove         Uninstall all versions
  -l, --logs            Pull game logs from the headset
  -ls, --list           List available versions
  -op, --open           Launch the game once finished
  -sp, --strip          Strip permissions to skip pompts on first launch
  -sk, --skipdecompile  Reuse previously decompiled files
  -cc, --clearcache     Delete cached downloads
  -r, --restore         Restore to the latest version
  --set-config VALUE
                        Set the manifest URL in the config
  --adb ...             Run a custom adb command using bundled adb (example: --adb devices)
  -sw, --switch-map     Change which map to load
  --stay                Keep the window open until Enter is pressed
  --message MESSAGE
```

#### Extra context:

- `uell [Date/version code/CL/1.0.CL]` This automatically downloads a version and uses the correct flags to install it, renaming if possible.

- `--clearcache` When providing a URL to the APK OBB or INI argument the script downloads and caches the file, to free up storage and delete cached downloads run the script with this argument.

- `--skipdecompile` When iterating on a single version you may wish to skip the decopilation step to save time by using the previously decompiled files, this also allows for manual modification of game files in the temp/decompiled folder.

- `--rename` This renames the package to allow for multiple versions to be installed at once.

   > If a renamed version is installed the `--log` argument pulls the logs of the last version to run.

- `--commandline` Various features can be unlocked through the use of commandline options, for example: `-c="-nullrhi"`

- `--ini` is unique because it can be ran on its own without rebuilding or reinstalling to almost instantly swap out an ini file

### Config:

The config.yml file located at `~/.ue-legacy-launcher/config.yml` has these settings by default:

```yml
autoupdate: true
logging_mode: default / info
manifest_url: (Manifest URL Here)
```
