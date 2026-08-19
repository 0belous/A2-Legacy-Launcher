# UE Legacy Launcher

Legacy Launcher installs and manages legacy versions of Unreal Engine games on Meta Quest headsets. It can download versions from a manifest, modify APK files, upload OBB and configuration files, and run ADB commands.

## Requirements

- A supported Meta Quest headset
- A USB connection with USB debugging enabled
- Java Runtime Environment (JRE)
- Windows, Linux, or MacOS pc

The launcher checks for one authorized headset. Disconnect additional Android devices before you install a game.

## Install

Download the executable for your operating system from the [latest release](https://github.com/0belous/UE-Legacy-Launcher/releases/latest). Run it once. The launcher registers the `uell://` application URI and creates its application-data directory.

On the first install, the launcher downloads the Android SDK command-line tools, platform tools, Android build tools, and Apktool when it needs them. On Linux, install Java before you run the launcher:

```sh
sudo apt update
sudo apt install default-jre
```

## Configure a manifest

The launcher uses a JSON manifest to find downloadable game versions. Set the manifest URL with:

```sh
uell --set-config manifest_url https://example.com/manifest.json
```

The manifest must include the launcher-compatible version and game metadata. See [`example.json`](example.json) for the supported structure. A version can include `apk_url`, `obb_url`, and a `flags` string containing launcher options.

The configuration file is stored at the following path:

- Linux: `~/.config/ue-legacy-launcher/config.yml`
- Windows and Termux: `~/.ue-legacy-launcher/config.yml`

The default settings are:

```yaml
autoupdate: true
logging_mode: default
manifest_url: (Manifest URL Here)
```

Use `--set-config KEY VALUE` to change an existing setting. Use `--set-KEY VALUE` for dynamically recognized configuration keys.

## Install a version

Pass a version, changelist, version code, or build date from the manifest:

```sh
uell 1.0.12345
uell 12345
uell 2024-06-01
```

List versions without installing one:

```sh
uell --list
```

The launcher downloads the APK and OBB, decompiles and rebuilds the APK, signs it, installs it on the headset, and uploads the OBB. The manifest can supply additional options for each version.

## Install local files

Install an APK and its OBB from local paths or URLs:

```sh
uell --apk ./game.apk --obb ./main.obb
uell --apk https://example.com/game.apk --obb https://example.com/main.obb
```

You can provide files from one ZIP archive with the `archive:/` path format:

```sh
uell --archive ./game-files.zip \
  --apk archive:/game.apk \
  --obb archive:/main.obb
```

URL downloads and extracted archive files are cached. Run this command to remove the cache and temporary build files:

```sh
uell --clearcache
```

## Modify a version

Use these options when you install an APK:

| Option | Description |
| --- | --- |
| `--rename NAME` | Install the package as `com.LegacyLauncher.NAME`, which lets you keep multiple versions installed. |
| `--strip` | Removes many permission requirements including networking and hand tracking. |
| `--commandline ARGUMENTS` | Add Unreal Engine launch arguments to `UECommandLine.txt`. |
| `--ini FILE_OR_URL` | Push an `Engine.ini` file to the game. |
| `--map LABEL\|PATH` | Generate an `Engine.ini` file that selects a map. Repeat the option to offer a selection. |
| `--so FILE_OR_URL` | Inject a shared library into the APK. |
| `--patch HEX_PATTERN` | Patch instructions matching the pattern to NOP `libUnreal.so`. |
| `--skipdecompile` | Reuse the previous decompiled files in the temporary directory. |
| `--open` | Launch the game after installation. |

For example:

```sh
uell --apk ./game.apk --obb ./main.obb \
  --rename test-build \
  --commandline "-nullrhi" \
  --open
```

Use `--skipdecompile` only when the decompiled files belong to the APK you are rebuilding. They are stored in the temporary application-data directory.

## Manage installed versions

```sh
uell --remove       # Uninstall all matching versions
uell --restore      # Install the latest manifest version
uell --logs         # Pull the latest game log
uell --switch-map   # Change the map for an installed configurable version
```

Run a command through the bundled ADB executable:

```sh
uell --adb devices
```

Add `--yes` to automatically select the first option and confirm prompts. Add `--stay` to keep the window open after the command finishes. Use `--help` to print the complete option list.

## Build from source

Build a Linux executable on Linux:

```sh
./build_local.sh
```

On Windows, use `build_local.bat`. Run it without arguments to build the Windows executable, or use `--target` and `--all` to select targets. Linux cross-builds require Docker.

## License

UE Legacy Launcher is distributed under the [MIT License](LICENSE).
