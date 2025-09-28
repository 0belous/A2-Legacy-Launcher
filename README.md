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

## Usage

```
a2ll [no parameters: interactive mode]
a2ll [-a --apk <path_to_apk>] [-o --obb <path_to_obb>] [-i --ini <path_to_ini>] [-r --remove] [-help]
```

If reinstalling normally does not install the latest version please run:

`a2ll --remove`

## How does it work?
Rebuilding the APK with debugging enabled gives permission to access the game files without root. <br>
From there we can place an Engine.ini which overrides the games file letting us bypass authentication and load straight into the map without connecting to any servers.
