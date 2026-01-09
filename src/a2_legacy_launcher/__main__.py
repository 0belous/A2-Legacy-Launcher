import os
import subprocess
import argparse
import sys
import shutil
import requests
import zipfile
import platform
import re
import mmap
import xml.etree.ElementTree as ET
from importlib import resources
import json
import hashlib
from urllib.parse import urlparse, unquote, parse_qs
import urllib3
from pySmartDL import SmartDL
from colorama import Fore
from colorama import init
import shlex
import yaml
import time
import threading

init(autoreset=True)

__version__ = "1.1.19"
IS_TERMUX = "TERMUX_VERSION" in os.environ

try:
    from importlib.resources import files
    jar_name = 'apktool-2.12.1-termux.jar' if IS_TERMUX else 'apktool_2.12.0.jar'
    KEYSTORE_FILE_REF = files('a2_legacy_launcher').joinpath('dev.keystore')
    APKTOOL_JAR_REF = files('a2_legacy_launcher').joinpath(jar_name)
except ImportError:
    from importlib.resources import path as resource_path
    jar_name = 'apktool-2.12.1-termux.jar' if IS_TERMUX else 'apktool_2.12.0.jar'
    KEYSTORE_FILE_REF = resource_path('a2_legacy_launcher', 'dev.keystore')
    APKTOOL_JAR_REF = resource_path('a2_legacy_launcher', jar_name)

with resources.as_file(KEYSTORE_FILE_REF) as keystore_path:
    KEYSTORE_FILE = str(keystore_path)
with resources.as_file(APKTOOL_JAR_REF) as apktool_path:
    APKTOOL_JAR = str(apktool_path)

def get_app_data_dir():
    home = os.path.expanduser("~")
    if platform.system() == "Linux":
        data_dir = os.path.join(home, ".config", "a2-legacy-launcher")
    else:
        data_dir = os.path.join(home, ".a2-legacy-launcher")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

APP_DATA_DIR = get_app_data_dir()
SDK_ROOT = os.path.join(APP_DATA_DIR, "android-sdk")
TEMP_DIR = os.path.join(APP_DATA_DIR, "tmp")
CACHE_DIR = os.path.join(APP_DATA_DIR, "cache")
CONFIG_FILE = os.path.join(APP_DATA_DIR, "config.yml")

BUILD_TOOLS_VERSION = "34.0.0"
PACKAGE_NAME = "com.AnotherAxiom.A2"
NEW_PACKAGE_NAME = "com.LegacyLauncher.A2"
KEYSTORE_PASS = "com.AnotherAxiom.A2"

is_windows = os.name == "nt"
exe_ext = ".exe" if is_windows else ""
script_ext = ".bat" if is_windows else ""

if IS_TERMUX:
    ADB_PATH = "adb"
    ZIPALIGN_PATH = "zipalign"
    APKSIGNER_PATH = "apksigner"
    SDK_MANAGER_PATH = ""
    BUILD_TOOLS_PATH = ""
else:
    ADB_PATH = os.path.join(SDK_ROOT, "platform-tools", f"adb{exe_ext}")
    SDK_MANAGER_PATH = os.path.join(SDK_ROOT, "cmdline-tools", "latest", "bin", f"sdkmanager{script_ext}")
    BUILD_TOOLS_PATH = os.path.join(SDK_ROOT, "build-tools", BUILD_TOOLS_VERSION)
    ZIPALIGN_PATH = os.path.join(BUILD_TOOLS_PATH, f"zipalign{exe_ext}")
    APKSIGNER_PATH = os.path.join(BUILD_TOOLS_PATH, f"apksigner{script_ext}")

DECOMPILED_DIR = os.path.join(TEMP_DIR, "decompiled")
COMPILED_APK = os.path.join(TEMP_DIR, "compiled.apk")
ALIGNED_APK = os.path.join(TEMP_DIR, "compiled.aligned.apk")
SIGNED_APK = os.path.join(TEMP_DIR, "compiled.aligned.signed.apk")
CACHE_INDEX = os.path.join(CACHE_DIR, "cache_index.json")
PRESET_INI_FILES = ["Engine.ini", "EngineVegas.ini", "Engine4v4.ini", "EngineNetworked.ini", "EnginePlayerstart.ini"]

os.makedirs(CACHE_DIR, exist_ok=True)

if is_windows:
    CMD_TOOLS_URL = "https://dl.google.com/android/repository/commandlinetools-win-13114758_latest.zip"
    UPDATE_SCRIPT_URL = "https://raw.githubusercontent.com/0belous/A2-Legacy-Launcher/main/update.bat"
else:
    CMD_TOOLS_URL = "https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip"
    UPDATE_SCRIPT_URL = "https://raw.githubusercontent.com/0belous/A2-Legacy-Launcher/main/update.sh"
CMD_TOOLS_ZIP = os.path.join(APP_DATA_DIR, "commandlinetools.zip")

BANNER = r"""
     _    ____    _     _____ ____    _    ______   __  _        _   _   _ _   _  ____ _   _ _____ ____
    / \  |___ \  | |   | ____/ ___|  / \  / ___\ \ / / | |      / \ | | | | \ | |/ ___| | | | ____|  _ \
   / _ \   __) | | |   |  _|| |  _  / _ \| |    \ V /  | |     / _ \| | | |  \| | |   | |_| |  _| | |_) |
  / ___ \ / __/  | |___| |__| |_| |/ ___ \ |___  | |   | |___ / ___ \ |_| | |\  | |___|  _  | |___|  _ <
 /_/   \_\_____| |_____|_____\____/_/   \_\____| |_|   |_____/_/   \_\___/|_| \_|\____|_| |_|_____|_| \_\
"""

def load_config():
    if not os.path.exists(CONFIG_FILE):
        print_info(f"Creating default configuration at {CONFIG_FILE}")
        default_config = {
            'manifest_url': 'https://dl.obelous.dev/api/raw/?path=/public/A2-archive/manifest.json',
            'autoupdate': True
        }
        with open(CONFIG_FILE, 'w') as f:
            yaml.dump(default_config, f)
        return default_config
    try:
        with open(CONFIG_FILE, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print_error(f"Failed to load or parse {CONFIG_FILE}: {e}")

def find_version_in_manifest(manifest, identifier):
    identifier_str = str(identifier).strip()
    try:
        identifier_int = int(identifier_str)
    except ValueError:
        identifier_int = None

    for version_data in manifest.get('versions', []):
        if identifier_int is not None and version_data.get('version_number') == identifier_int:
            return version_data
        if identifier_int is not None and version_data.get('version_code') == identifier_int:
            return version_data
        if version_data.get('version') == identifier_str:
            return version_data
        if version_data.get('version') == f"1.0.{identifier_str}":
            return version_data
            
    return None

def apply_manifest_flags(args, flags_str):
    if not flags_str:
        return
    parsed_flags = shlex.split(flags_str)
    i = 0
    while i < len(parsed_flags):
        flag = parsed_flags[i]
        if flag == "--patch":
            args.patch = True
        elif flag == "--rename":
            args.rename = True
        elif flag == "--strip":
            args.strip = True
        elif flag in ("-i", "--ini"):
            if args.ini is None and i + 1 < len(parsed_flags):
                args.ini = parsed_flags[i+1]
                i += 1
        elif flag == "--commandline":
            if args.commandline is None and i + 1 < len(parsed_flags):
                args.commandline = parsed_flags[i+1]
                i += 1
        i += 1

def check_for_updates():
    def run_update():
        config = load_config()
        if config.get('autoupdate', True):
            script_name = "update.bat" if is_windows else "update.sh"
            script_path = os.path.join(TEMP_DIR, script_name)
            if download(UPDATE_SCRIPT_URL, script_path):
                if is_windows:
                    subprocess.Popen([script_path], shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:
                    os.chmod(script_path, 0o755)
                    subprocess.Popen(["bash", script_path])
                print_info("Now updating: Please wait 5-10 seconds before running the next command")
                sys.exit(0)
            else:
                print_error("Failed to download update script.")
        else:
            return
    try:
        pypi_url = "https://pypi.org/pypi/a2-legacy-launcher/json"
        response = requests.get(pypi_url, timeout=3)
        response.raise_for_status()
        latest_version_str = response.json()["info"]["version"] 
        def parse_version(v):
            return [int(x) for x in v.split('.') if x.isdigit()]
        current_version = parse_version(__version__)
        latest_version = parse_version(latest_version_str)
        if latest_version > current_version:
            print(Fore.YELLOW + f"\n[UPDATE] A new version ({latest_version_str}) is available!")
            run_update()
    except Exception:
        run_update()

def print_info(message):
    print(f"[INFO] {message}")

def print_success(message):
    print(Fore.GREEN + f"[SUCCESS] {message}")

def print_error(message, exit_code=1):
    print(Fore.RED + f"[ERROR] {message}")

    if exit_code is not None:
        sys.exit(exit_code)

def run_command(command, suppress_output=False, env=None):
    try:
        process = subprocess.run(command, check=True, text=True, capture_output=True, env=env)
        if not suppress_output and process.stdout:
            print(process.stdout.strip())
        return process.stdout.strip()
    except FileNotFoundError:
        if command[0] in [ADB_PATH, SDK_MANAGER_PATH, ZIPALIGN_PATH, APKSIGNER_PATH]:
            print_info(f"Required SDK component not found: {command[0]}. Re-initializing SDK setup.")
            if os.path.exists(SDK_ROOT):
                shutil.rmtree(SDK_ROOT)
            setup_sdk()
            print_info("SDK Redownloaded: re-run the script.")
            sys.exit()
        else:
            print_error(f"Command not found: {command[0]}. Please ensure it's installed and in your PATH.")
    except subprocess.CalledProcessError as e:
        error_message = (f"Command failed with exit code {e.returncode}:\n>>> {' '.join(command)}\n--- STDOUT ---\n{e.stdout.strip()}\n--- STDERR ---\n{e.stderr.strip()}")
        print_error(error_message)
    except Exception as e:
        print_error(f"An unexpected error occurred: {e}")

def run_interactive_command(command, env=None):
    try:
        subprocess.run(command, check=True, env=env)
    except FileNotFoundError:
        print_error(f"Command not found: {command[0]}. Please ensure it's in your PATH.")
    except subprocess.CalledProcessError as e:
        print_error(f"Command failed with exit code {e.returncode}: {' '.join(command)}")
    except Exception as e:
        print_error(f"An unexpected error occurred: {e}")

def parse_file_drop(raw_path):
    cleaned_path = raw_path.strip()
    if is_windows and cleaned_path.startswith('& '):
        cleaned_path = cleaned_path[2:].strip()
    return cleaned_path.strip("'\"")

def clean_temp_dir():
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
    os.makedirs(TEMP_DIR)

def download(url, filename):
    print_info(f"Downloading {os.path.basename(filename)} from {url}...")
    try:
        obj = SmartDL(url, dest=filename, progress_bar=True)
        obj.start()
        if obj.isSuccessful():
            return True
        else:
            print_error(f"Failed to download file: {obj.get_errors()}")
            return False

    except Exception as e:
        print_error(f"Failed to download file: {e}")
        return False

def check_and_install_java():
    if shutil.which("java"):
        return
    print_error("Java not found. The Java Runtime Environment (JRE) is required.", exit_code=None)
    if is_windows:
        url = "https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.8%2B9/OpenJDK21U-jre_x64_windows_hotspot_21.0.8_9.msi"
        installer_path = os.path.join(APP_DATA_DIR, "OpenJDK.msi")
        if not download(url, installer_path):
            print_error("Failed to download Java installer. Please install it manually.")
            return
        print_info("Running the Java installer... Please accept the UAC prompt and follow the installation steps.")
        run_interactive_command(["msiexec", "/i", installer_path])
        print_success("Java installation finished.")
        os.remove(installer_path)
        print_info("Please close and re-open your terminal, then run a2ll again.")
        return
    else:
        print_error("Please install Java by running: 'sudo apt update && sudo apt install default-jre'", exit_code=None)
        print_info("Once Java is installed, please re-run a2ll")
        sys.exit(1)

def setup_sdk():
    if IS_TERMUX:
        return
    print_info("Android SDK not found. Starting automatic setup...")
    if not download(CMD_TOOLS_URL, CMD_TOOLS_ZIP):
        return
    print_info(f"Extracting {CMD_TOOLS_ZIP}...")
    if os.path.exists(SDK_ROOT):
        shutil.rmtree(SDK_ROOT)
    temp_extract_dir = os.path.join(APP_DATA_DIR, "temp_extract")
    if os.path.exists(temp_extract_dir):
        shutil.rmtree(temp_extract_dir)
    with zipfile.ZipFile(CMD_TOOLS_ZIP, 'r') as zip_ref:
        zip_ref.extractall(temp_extract_dir)
    source_tools_dir = os.path.join(temp_extract_dir, "cmdline-tools")
    target_dir = os.path.join(SDK_ROOT, "cmdline-tools", "latest")
    os.makedirs(os.path.dirname(target_dir), exist_ok=True)
    shutil.move(source_tools_dir, target_dir)
    shutil.rmtree(temp_extract_dir)
    os.remove(CMD_TOOLS_ZIP)
    if not is_windows:
        print_info("Setting executable permissions for SDK tools...")
        for root, _, files in os.walk(os.path.join(SDK_ROOT, "cmdline-tools", "latest")):
            for filename in files:
                if filename in ["sdkmanager", "avdmanager"]:
                    try:
                        os.chmod(os.path.join(root, filename), 0o755)
                    except Exception as e:
                        print_info(f"Could not set permissions for {filename}: {e}")

    print_info("Installing platform-tools...")
    run_interactive_command([SDK_MANAGER_PATH, "--install", "platform-tools"])
    
    print_info(f"Installing build-tools;{BUILD_TOOLS_VERSION}...")
    run_interactive_command([SDK_MANAGER_PATH, f"--install", f"build-tools;{BUILD_TOOLS_VERSION}"])
    
    print_success("Android SDK setup complete.")

def get_connected_device():
    print_info("Looking for connected devices...")
    output = run_command([ADB_PATH, "devices"])
    devices = [line.split('\t')[0] for line in output.strip().split('\n')[1:] if "device" in line and "unauthorized" not in line]
    if len(devices) == 1:
        print_success(f"Found one connected device: {devices[0]}")
        return devices[0]
    elif len(devices) > 1:
        print_error(f"Multiple devices found: {devices}. Please connect only one headset.")
    else:
        print_error("No authorized ADB device found. Check headset for an authorization prompt.")

def modify_manifest(decompiled_dir):
    manifest_path = os.path.join(decompiled_dir, "AndroidManifest.xml")
    permissions_to_remove = [
        "android.permission.RECORD_AUDIO",
        "android.permission.BLUETOOTH",
        "android.permission.BLUETOOTH_CONNECT"
    ]
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        modified_lines = []
        added_hand_tracking = False
        for line in lines:
            if any(permission in line for permission in permissions_to_remove):
                continue
            if 'android.hardware.microphone' in line and 'android:required="true"' in line:
                modified_lines.append(line.replace('android:required="true"', 'android:required="false"'))
                continue
            if 'com.epicgames.unreal.GameActivity.bVerifyOBBOnStartUp' in line:
                modified_lines.append(line.replace('android:value="true"', 'android:value="false"'))
                continue
            if not added_hand_tracking and "<application" in line:
                modified_lines.append('    <uses-permission android:name="com.oculus.permission.HAND_TRACKING"/>\n')
                modified_lines.append('    <uses-feature android:name="oculus.software.handtracking" android:required="false"/>\n')
                added_hand_tracking = True
            modified_lines.append(line)
        with open(manifest_path, 'w', encoding='utf-8') as f:
            f.writelines(modified_lines)
    except Exception as e:
        print_error(f"Failed to modify AndroidManifest.xml: {e}")

def rename_package(decompiled_dir, old_pkg, new_pkg):
    print_info(f"Renaming package...")
    manifest_path = os.path.join(decompiled_dir, "AndroidManifest.xml")
    yml_path = os.path.join(decompiled_dir, "apktool.yml")
    try:
        ET.register_namespace('android', 'http://schemas.android.com/apk/res/android')
        tree = ET.parse(manifest_path)
        root = tree.getroot()
        if root.get('package') == old_pkg:
            root.set('package', new_pkg)
        ns = {'android': 'http://schemas.android.com/apk/res/android'}
        component_tags = {'application', 'activity', 'activity-alias', 'service', 'receiver', 'provider'}
        for elem in root.iter():
            tag_name = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            if tag_name in component_tags:
                aname = f"{{{ns['android']}}}name"
                val = elem.get(aname)
                if val:
                    if val.startswith('.'):
                        elem.set(aname, old_pkg + val)
                    elif '.' not in val:
                        elem.set(aname, old_pkg + '.' + val)
            if tag_name == 'provider':
                auth = f"{{{ns['android']}}}authorities"
                val = elem.get(auth)
                if val and old_pkg in val:
                    elem.set(auth, val.replace(old_pkg, new_pkg))
        tree.write(manifest_path, encoding='utf-8', xml_declaration=True)
        with open(yml_path, 'r', encoding='utf-8') as f:
            content = f.read()
        content = content.replace(old_pkg, new_pkg)
        with open(yml_path, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        print_error(f"Failed to modify manifest: {e}")

def inject_so(decompiled_dir, so_filename):
    print_info(f"Injecting {so_filename}...")
    so_file_path = os.path.join(os.getcwd(), so_filename)
    if not os.path.exists(so_file_path):
        print_error(f"Could not find .so file: {so_file_path}")
    target_lib_dir = os.path.join(decompiled_dir, "lib", "arm64-v8a")
    os.makedirs(target_lib_dir, exist_ok=True)
    shutil.copy(so_file_path, os.path.join(target_lib_dir, os.path.basename(so_filename)))
    print_success("Copied .so file successfully.")
    manifest_path = os.path.join(decompiled_dir, "AndroidManifest.xml")
    ns = {'android': 'http://schemas.android.com/apk/res/android'}
    ET.register_namespace('android', ns['android'])
    tree = ET.parse(manifest_path)
    main_activity_name = None
    for activity in tree.findall('.//activity'):
        for intent_filter in activity.findall('intent-filter'):
            if any(a.get(f'{{{ns["android"]}}}name') == 'android.intent.action.MAIN' for a in intent_filter.findall('action')):
                main_activity_name = activity.get(f'{{{ns["android"]}}}name')
                break
        if main_activity_name: break
    if not main_activity_name:
        print_error("Could not find main activity in AndroidManifest.xml.")
        return
    print_info(f"Found main activity: {main_activity_name}")
    smali_filename = main_activity_name.split('.')[-1] + ".smali"
    smali_path = None
    for root, _, files in os.walk(decompiled_dir):
        if smali_filename in files:
            smali_path = os.path.join(root, smali_filename)
            break
    if not smali_path:
        print_error(f"Smali file '{smali_filename}' not found in decompiled folder.")
        return
    print_info(f"Modifying smali file: {smali_path}")
    with open(smali_path, 'r+', encoding='utf-8') as f:
        lines = f.readlines()
        on_create_index = next((i for i, line in enumerate(lines) if ".method" in line and "onCreate(Landroid/os/Bundle;)V" in line), -1)
        if on_create_index == -1:
            print_error(f"Could not find 'onCreate' method in {smali_filename}.")
            return
        lib_name = os.path.basename(so_filename)
        if lib_name.startswith("lib"): lib_name = lib_name[3:]
        if lib_name.endswith(".so"): lib_name = lib_name[:-3]
        smali_injection = [
            '\n',
            f'    const-string v0, "{lib_name}"\n',
            '    invoke-static {v0}, Ljava/lang/System;->loadLibrary(Ljava/lang/String;)V\n'
        ]
        insert_pos = on_create_index + 1
        while lines[insert_pos].strip().startswith((".locals", ".param", ".prologue")):
             insert_pos += 1
        lines[insert_pos:insert_pos] = smali_injection
        f.seek(0)
        f.writelines(lines)
    print_success(f"Successfully injected loadLibrary call for '{lib_name}'.")

def process_apk(apk_path, args):
    java_heap = "-Xmx512m" if IS_TERMUX else "-Xmx2048m"
    if not args.skipdecompile:
        print_info("Decompiling APK...")
        if not args.so:
            run_command(["java", java_heap, "-jar", APKTOOL_JAR, "d", "-s", apk_path, "-o", DECOMPILED_DIR])
        else: 
            run_command(["java", java_heap, "-jar", APKTOOL_JAR, "d", apk_path, "-o", DECOMPILED_DIR])
    else:
        print_info("Skipping decompilation, using previously decompiled files.")
        if not os.path.isdir(DECOMPILED_DIR):
            print_error(f"Cannot skip decompilation: Directory '{DECOMPILED_DIR}' not found.")
        for f in [COMPILED_APK, ALIGNED_APK, SIGNED_APK]:
            if os.path.exists(f):
                os.remove(f)
    if args.rename:
        rename_package(DECOMPILED_DIR, PACKAGE_NAME, NEW_PACKAGE_NAME)
    if args.strip:
        print_info("Stripping permissions...")
        modify_manifest(DECOMPILED_DIR)
    if args.commandline:
        ue_cmdline_path = os.path.join(DECOMPILED_DIR, "assets", "UECommandLine.txt")
        os.makedirs(os.path.dirname(ue_cmdline_path), exist_ok=True)
        with open(ue_cmdline_path, 'w') as f:
            f.write(args.commandline)
    if args.so:
        so_path = get_path_from_input(args.so, "so")
        if so_path:
            inject_so(DECOMPILED_DIR, so_path)
    if args.patch:
        if not args.obb:
            print_error("Cannot use --patch without an --obb file.", exit_code=None)
        patch_libunreal(get_path_from_input(args.obb, "obb"))
    print_info("Recompiling APK...")
    recompile_cmd = ["java", "-jar", APKTOOL_JAR, "b", DECOMPILED_DIR, "-d", "-o", COMPILED_APK]
    if IS_TERMUX:
        recompile_cmd.insert(4, "--aapt")
        recompile_cmd.insert(5, str(files('a2_legacy_launcher').joinpath("aapt2-ARM64")))
    run_command(recompile_cmd)

    print_info("Aligning APK...")
    run_command([ZIPALIGN_PATH, "-v", "4", COMPILED_APK, ALIGNED_APK], suppress_output=True)
    print_info("Signing APK...")
    signing_env = os.environ.copy()
    signing_env["KEYSTORE_PASSWORD"] = KEYSTORE_PASS
    run_command([APKSIGNER_PATH, "sign", "--ks", KEYSTORE_FILE, "--ks-pass", f"env:KEYSTORE_PASSWORD", "--out", SIGNED_APK, ALIGNED_APK], env=signing_env)
    print_success("APK processing complete.")

def install_modded_apk(device_id, package_name):
    print_info("Installing modified APK...")
    proc = subprocess.run([ADB_PATH, "-s", device_id, "install", "-r", "--streaming", "--no-incremental", SIGNED_APK], capture_output=True, text=True)
    if "Success" in proc.stdout:
        return False
    if "INSTALL_FAILED_UPDATE_INCOMPATIBLE" in proc.stderr or "INSTALL_FAILED_VERSION_DOWNGRADE" in proc.stderr:
        subprocess.run([ADB_PATH, "-s", device_id, "uninstall", package_name], capture_output=True)
        proc = subprocess.run([ADB_PATH, "-s", device_id, "install", "--streaming", "--no-incremental", SIGNED_APK], capture_output=True, text=True)
        if "Success" in proc.stdout:
            return True
    print_error(f"Installation failed: {proc.stdout}\n{proc.stderr}")
    return False

def upload_obb(device_id, obb_file, effective_package_name, is_renamed):
    if is_renamed:
        new_obb_name = os.path.basename(obb_file).replace(PACKAGE_NAME, effective_package_name)
        final_obb_name = new_obb_name
    else:
        final_obb_name = os.path.basename(obb_file)
    destination_dir = f"/sdcard/Android/obb/{effective_package_name}/"
    destination_path = destination_dir + final_obb_name
    try:
        local_size = os.path.getsize(obb_file)
        subprocess.run([ADB_PATH, "-s", device_id, "shell", f"mkdir -p {destination_dir}"], capture_output=True)
        res = subprocess.run([ADB_PATH, "-s", device_id, "shell", f"stat -c %s {destination_path}"], capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip().isdigit():
            remote_size = int(res.stdout.strip())
            if remote_size == local_size:
                print_success("OBB already exists. Skipping OBB upload.")
                return
    except Exception as e:
        print_info(f"Error checking OBB status: {e}. Proceeding with upload.")

    print_info(f"Uploading OBB...")
    run_command([ADB_PATH, "-s", device_id, "push", obb_file, destination_path])
    print_success("OBB upload complete.")

def push_ini(device_id, ini_file, package_name):
    print_info("Pushing INI file...")
    tmp_ini_path = "/data/local/tmp/Engine.ini"
    run_command([ADB_PATH, "-s", device_id, "push", ini_file, tmp_ini_path])
    target_dir = f"files/UnrealGame/A2/A2/Saved/Config/Android"
    shell_command = f"""
    run-as {package_name} sh -c '
    mkdir -p {target_dir} 2>/dev/null;
    chmod -R 755 {target_dir} 2>/dev/null;
    cp {tmp_ini_path} {target_dir}/Engine.ini 2>/dev/null;
    chmod -R 555 {target_dir} 2>/dev/null
    '
    """
    run_command([ADB_PATH, "-s", device_id, "shell", shell_command])
    print_success("INI file pushed successfully.")

def get_cache_index():
    if not os.path.exists(CACHE_INDEX):
        return {}
    try:
        with open(CACHE_INDEX, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}

def update_cache_index(index):
    with open(CACHE_INDEX, 'w') as f:
        json.dump(index, f, indent=4)

def get_path_from_input(input_str, file_type):
    if not input_str:
        return None
    if input_str.startswith(('http://', 'https://')):
        url = input_str
        cache_index = get_cache_index()
        filename = None
        if file_type == 'apk':
            url_hash = hashlib.sha256(url.encode()).hexdigest()
            filename = f"{url_hash}.apk"
        else:
            try:
                parsed_url = urlparse(url)
                query_params = parse_qs(parsed_url.query)
                path_from_query = query_params.get('path', [None])[0]
                if path_from_query:
                    potential_filename = os.path.basename(unquote(path_from_query))
                    if '.' in potential_filename:
                        filename = potential_filename
                if not filename:
                    path_segment = unquote(parsed_url.path)
                    potential_filename = os.path.basename(path_segment)
                    if '.' in potential_filename:
                        filename = potential_filename
            except Exception as e:
                 print_info(f"Could not parse filename from URL, falling back to hash. Error: {e}")
            if not filename:
                url_hash = hashlib.sha256(url.encode()).hexdigest()
                filename = f"{url_hash}.{file_type}"
        cached_file_path = os.path.join(CACHE_DIR, filename)
        if url in cache_index and os.path.exists(cache_index.get(url, {}).get("path")):
            is_expired = False
            if file_type == 'json':
                cached_time = cache_index[url].get('timestamp', 0)
                if (time.time() - cached_time) > 86400:
                    print_info("Updating manifest...")
                    is_expired = True
                    try:
                        os.remove(cache_index[url]['path'])
                    except OSError:
                        pass
                    del cache_index[url]
                    update_cache_index(cache_index)
            if not is_expired:
                cached_path = cache_index[url]['path']
                print_info(f"Using cached {file_type}: {cached_path}")
                return cached_path
        if download(url, cached_file_path):
            cache_entry = {"path": cached_file_path}
            if file_type == 'json':
                cache_entry['timestamp'] = time.time()
            cache_index[url] = cache_entry
            update_cache_index(cache_index)
            print_success(f"Successfully downloaded {file_type}.")
            return cached_file_path
        else:
            print_error(f"Failed to download {file_type} from {url}.")
            return None
    if os.path.isfile(input_str):
        print_info(f"Using local {file_type}: {input_str}")
        return input_str
    if file_type == 'ini' and input_str in PRESET_INI_FILES:
        try:
            try:
                ini_file_ref = files('a2_legacy_launcher').joinpath(input_str)
                with resources.as_file(ini_file_ref) as p:
                    ini_path = str(p)
            except (ImportError, AttributeError):
                with resources.path('a2_legacy_launcher', input_str) as p:
                    ini_path = str(p)
            return ini_path
        except Exception as e:
            print_error(f"Could not load preset INI file '{input_str}'. It may be missing from the package. Error: {e}")
            return None
    error_msg = f"Invalid {file_type} input: '{input_str}'.\n"
    if file_type == 'ini':
        error_msg += "Please provide a valid URL, a local file path, or one of the preset names: " + ", ".join(PRESET_INI_FILES)
    else:
        error_msg += "Please provide a valid URL or a local file path."
    print_error(error_msg)
    return None

def find_pattern(label, pattern, text, default_value="Not Found"):
    match = re.search(pattern, text)
    if match:
        print(f"{label}: {match.group(1)}")
    else:
        print(f"{label}: {default_value}")

def patch_libunreal(obb_path):
    so_file_path = os.path.join(DECOMPILED_DIR, "lib", "arm64-v8a", "libUnreal.so")
    if not os.path.exists(so_file_path):
        print_error(f"Could not find libUnreal.so at:\n{so_file_path}", exit_code=None)
        return

    version_patterns = {
        '71516834': b'\x9A\xFD\x08\x97\xF5\x03\x13\xAA\xE8\x03\x40\xF9', #1.0.50939
        '70070810': b'\xA0\xFD\x08\x97\xF5\x03\x13\xAA\xE8\x03\x40\xF9', #1.0.50516
        '69971476': b'\xA0\xFD\x08\x97\xF5\x03\x13\xAA\xE8\x03\x40\xF9', #1.0.50451
        '69639244': b'\xA0\xFD\x08\x97\xF5\x03\x13\xAA\xE8\x03\x40\xF9', #1.0.50346
        '68839491': b'\xA6\x02\x09\x97\xF5\x03\x13\xAA\xE8\x03\x40\xF9', #1.0.49567
        '68442501': b'\xA6\x02\x09\x97\xF5\x03\x13\xAA\xE8\x03\x40\xF9', #1.0.49423
        '68229017': b'\x2E\x03\x09\x97\xF5\x03\x13\xAA\xE8\x03\x40\xF9', #1.0.49041
        '67287493': b'\x2E\x03\x09\x97\xF5\x03\x13\xAA\xE8\x03\x40\xF9', #1.0.48674
        '66591868': b'\x40\x0A\x09\x97\xF5\x03\x13\xAA\xE8\x03\x40\xF9', #1.0.48110
        '65824486': b'\x3F\x0B\x09\x97\xF5\x03\x13\xAA\xE8\x03\x40\xF9', #1.0.47702
        '65425880': b'\x3F\x0B\x09\x97\xF5\x03\x13\xAA\xE8\x03\x40\xF9', #1.0.47514
        '65291532': b'\x9A\x10\x09\x97\xF5\x03\x13\xAA\xE8\x03\x40\xF9', #1.0.47251
        '65134129': b'\x9A\x10\x09\x97\xF5\x03\x13\xAA\xE8\x03\x40\xF9', #1.0.47133
        '65065687': b'\xA0\x10\x09\x97\xF5\x03\x13\xAA\xE8\x03\x40\xF9', #1.0.47057
        '64955222': b'\xA0\x10\x09\x97\xF5\x03\x13\xAA\xE8\x03\x40\xF9', #1.0.47031
        '64880848': b'\x9E\x10\x09\x97\xF5\x03\x13\xAA\xE8\x03\x40\xF9', #1.0.46986
        '64081339': b'\xA0\x80\x0E\x97\xF5\x03\x13\xAA\xE8\x03\x40\xF9', #1.0.45885
        '63387609': b'\xAC\x80\x0E\x97\xF5\x03\x13\xAA\xE8\x03\x40\xF9', #1.0.45185
        '37050250': b'\xB5\x9B\xFF\x96\xF5\x03\x13\xAA\xE8\x03\x40\xF9', #1.0.23189
        '36101401': b'\xD0\x9D\xFF\x96\xF5\x03\x13\xAA\xE8\x03\x40\xF9', #1.0.22682
        '35588567': b'\xFA\xB3\xFF\x96\xF5\x03\x13\xAA\xE8\x03\x40\xF9', #1.0.22519
        '35232627': b'\xB9\xB9\xFF\x96\xF5\x03\x13\xAA\xE8\x03\x40\xF9', #1.0.22284
        '34973026': b'\x2F\xBA\xFF\x96\xF5\x03\x13\xAA\xE8\x03\x40\xF9', #1.0.22029
        '33694970': b'\x86\x0C\x01\x97\xF5\x03\x13\xAA\xE8\x03\x40\xF9', #1.0.20996
        '32836111': b'\x86\x0C\x01\x97\xF5\x03\x13\xAA\xE8\x03\x40\xF9', #1.0.20557
        '31960569': b'\xC9\x0C\x01\x97\xF5\x03\x13\xAA\xE8\x03\x40\xF9', #1.0.20221
        '31620962': b'\x51\x0C\x01\x97\xF5\x03\x13\xAA\xE8\x03\x40\xF9', #1.0.20066
        '29783267': b'\x39\x2F\x0E\x97\xF5\x03\x13\xAA\xE8\x03\x40\xF9', #1.0.18559
    }

    obb_filename = os.path.basename(obb_path)
    match = re.search(r'main\.(\d+)\.', obb_filename)
    if not match:
        print_error(f"Could not parse version code from OBB filename: '{obb_filename}'. Expected format: main.VERSION.package.obb", exit_code=None)
        return
    version_code = match.group(1)
    original_pattern = version_patterns.get(version_code)
    if not original_pattern:
        print_error(f"No pattern found for: '{version_code}'.", exit_code=None)
        return
    print_info(f"Patching version {version_code}...")
    patched_bytes = b'\x1F\x20\x03\xD5'
    patched_pattern = patched_bytes + original_pattern[len(patched_bytes):]
    try:
        with open(so_file_path, 'r+b') as f:
            with mmap.mmap(f.fileno(), 0) as mm:
                if mm.find(patched_pattern) != -1:
                    print_info("File already patched.")
                    return

                offset = mm.find(original_pattern)
                if offset != -1:
                    print_info(f"Found offset: {hex(offset)}...")
                    mm.seek(offset)
                    mm.write(patched_bytes)
                    mm.flush()
                    print_success("File successfully patched.")
                else:
                    print_error("Pattern not found.", exit_code=None)
    except Exception as e:
        print_error(f"An unexpected error occurred during patching: {e}")

def a2ll():
    parser = argparse.ArgumentParser(
        description="A2 Legacy Launcher "+__version__+" by Obelous ",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument('download', nargs='?', default=None, help="Build version to download and install -")
    parser.add_argument("-v", "--version", action="version", version=f"Legacy Launcher {__version__}")
    parser.add_argument("-a", "--apk", help="Path/URL to an APK file")
    parser.add_argument("-o", "--obb", help="Path/URL to an OBB file")
    parser.add_argument("-i", "--ini", help="Path/URL/Preset for Engine.ini\nPresets: " + ", ".join(PRESET_INI_FILES))
    parser.add_argument("-c", "--commandline", help="Launch arguments for A2")
    parser.add_argument("-so", "--so", help="Inject a custom .so file")
    parser.add_argument("-rn", "--rename", action="store_true", help="Rename the package for parallel installs")
    parser.add_argument("-p", "--patch", action="store_true", help="Remove entitlement check from libUnreal.so")
    parser.add_argument("-rm", "--remove", action="store_true", help="Uninstall all versions")
    parser.add_argument("-l", "--logs", action="store_true", help="Pull game logs from the headset")
    parser.add_argument("-ls", "--list", action="store_true", help="List available versions")
    parser.add_argument("-op", "--open", action="store_true", help="Launch the game once finished")
    parser.add_argument("-sp", "--strip", action="store_true", help="Strip permissions to skip pompts on first launch")
    parser.add_argument("-sk", "--skipdecompile", action="store_true", help="Reuse previously decompiled files")
    parser.add_argument("-cc", "--clearcache", action="store_true", help="Delete cached downloads")
    parser.add_argument("-r", "--restore", action="store_true", help="Restore to the latest version")
    args = parser.parse_args()
    print(Fore.LIGHTYELLOW_EX + BANNER)
    
    if args.clearcache or args.remove:
        action_performed = True
        if os.path.exists(CACHE_DIR):
            shutil.rmtree(CACHE_DIR)
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR)
        print_success("Cache and temporary files cleared.")
        if not args.remove:
            return

    if args.download and args.apk:
        print_error("Cannot specify a version to download and an APK file at the same time.", exit_code=1)
    config = load_config()
    if args.download:
        manifest_url = config.get('manifest_url')
        if not manifest_url:
            print_error(f"Manifest URL not found in {CONFIG_FILE}. Please add it.")
        try:
            print_info("Fetching manifest...")
            response = requests.get(manifest_url, timeout=10)
            response.raise_for_status()
            manifest = response.json()
        except Exception as e:
            print_error(f"Failed to download manifest: {e}")
        version_data = find_version_in_manifest(manifest, args.download)
        if not version_data:
            print_error(f"Version '{args.download}' not found in the manifest.")
        
        global NEW_PACKAGE_NAME
        NEW_PACKAGE_NAME = f"com.LegacyLauncher.V{version_data['version_number']}"
        
        print_success(f"Installing version: {version_data['version']}")
        flags_str = version_data.get('flags', '')
        print_info(f"Using flags: {flags_str}")
        manifest_args = parser.parse_args(shlex.split(flags_str))
        if args.ini is None:
            args.ini = manifest_args.ini
        if args.commandline is None:
            args.commandline = manifest_args.commandline
        if not args.patch:
            args.patch = manifest_args.patch
        if not args.rename:
            args.rename = manifest_args.rename
        if not args.strip:
            args.strip = manifest_args.strip

        args.apk = version_data.get('apk_url')
        args.obb = version_data.get('obb_url')

    if args.list:
        manifest_url = config.get('manifest_url')
        if not manifest_url:
            print_error(f"Manifest URL not found in {CONFIG_FILE}. Please add it.")
        
        try:
            print_info("Fetching manifest...")
            response = requests.get(manifest_url, timeout=10)
            response.raise_for_status()
            manifest = response.json()
        except Exception as e:
            print_error(f"Failed to download manifest: {e}")
        
        versions = manifest.get('versions', [])
        if not versions:
            print_info("No versions found in manifest.")
        else:
            print_info("Available versions:")
            for version_data in versions:
                version_str = version_data.get('version', 'N/A')
                version_code = version_data.get('version_code', 'N/A')
                print(f"  - Version: {version_str} ({version_code})")
        return

    if not IS_TERMUX:
        check_and_install_java()
        if not os.path.exists(SDK_MANAGER_PATH):
            setup_sdk()

    if not os.path.exists(APKTOOL_JAR):
        print_error(f"Packaged component {APKTOOL_JAR} not found.")
    if not os.path.exists(KEYSTORE_FILE):
        print_error(f"Packaged component {KEYSTORE_FILE} not found.")
    device_id = get_connected_device()
    effective_package_name = NEW_PACKAGE_NAME if args.rename else PACKAGE_NAME
    action_performed = False
    if args.remove:
        action_performed = True
        packages_output = run_command([ADB_PATH, "-s", device_id, "shell", "pm", "list", "packages"], suppress_output=True)
        packages_to_remove = [PACKAGE_NAME]
        for line in packages_output.splitlines():
            package = line.replace("package:", "").strip()
            if package.startswith("com.LegacyLauncher."):
                packages_to_remove.append(package)
        
        uninstalled_count = 0
        for package in set(packages_to_remove):
            target_dir = f"files/UnrealGame/A2/A2/Saved/Config/Android"
            shell_command = f"run-as {package} sh -c 'chmod -R 777 {target_dir} 2>/dev/null;'"
            subprocess.run([ADB_PATH, "-s", device_id, "shell", shell_command], capture_output=True, text=True)
            uninstall_result = subprocess.run([ADB_PATH, "-s", device_id, "uninstall", package], capture_output=True, text=True)
            if "Success" in uninstall_result.stdout:
                uninstalled_count += 1

        if uninstalled_count > 0:
            print_success(f"Uninstalled {uninstalled_count} package(s).")
        else:
            print_info("No relevant packages found to uninstall.")
        return

    if args.restore:
        action_performed = True
        config = load_config()
        manifest_url = config.get('manifest_url')
        if not manifest_url:
            print_error(f"Manifest URL not found in {CONFIG_FILE}. Please add it.")
        try:
            print_info("Fetching manifest...")
            response = requests.get(manifest_url, timeout=10)
            response.raise_for_status()
            manifest = response.json()
        except Exception as e:
            print_error(f"Failed to download manifest: {e}")
        versions = manifest.get('versions', [])
        if not versions:
            print_error("No versions found in manifest.")
        latest_version = max(versions, key=lambda v: v.get('version_code') or 0)
        print_success(f"Restoring to latest version: {latest_version.get('version')}")
        apk_path = get_path_from_input(latest_version.get('apk_url'), "apk")
        obb_path = get_path_from_input(latest_version.get('obb_url'), "obb")
        subprocess.run([ADB_PATH, "-s", device_id, "uninstall", PACKAGE_NAME], check=False, capture_output=True)
        obb_thread = threading.Thread(target=upload_obb, args=(device_id, obb_path, PACKAGE_NAME, False))
        obb_thread.start()
        print_info("Installing APK...")
        run_command([ADB_PATH, "-s", device_id, "install", "-r", apk_path])
        obb_thread.join()

    try:
        if args.logs:
            tip = False
            action_performed = True
            packages_output = run_command([ADB_PATH, "-s", device_id, "shell", "pm", "list", "packages"], suppress_output=True)
            installed_packages = []
            for line in packages_output.splitlines():
                package = line.replace("package:", "").strip()
                if package == PACKAGE_NAME or package.startswith("com.LegacyLauncher."):
                    installed_packages.append(package)
            
            if installed_packages:
                print_info(f"Installed versions: {', '.join(installed_packages)}")

            pulled_logs = []
            for package in installed_packages:
                remote_log_path = f"/sdcard/Android/data/{package}/files/UnrealGame/A2/A2/Saved/Logs/A2.log"
                local_log_filename = f"A2_{package}.log"
                
                timestamp = 0
                try:
                    stat_cmd = [ADB_PATH, "-s", device_id, "shell", "stat", "-c", "%Y", remote_log_path]
                    stat_result = subprocess.run(stat_cmd, capture_output=True, text=True)
                    if stat_result.returncode == 0 and stat_result.stdout.strip().isdigit():
                        timestamp = int(stat_result.stdout.strip())
                except Exception:
                    pass

                if timestamp > 0:
                    run_command([ADB_PATH, "-s", device_id, "pull", remote_log_path, local_log_filename], suppress_output=True)
                    if os.path.exists(local_log_filename):
                        pulled_logs.append((local_log_filename, timestamp))
                else:
                    check_result = subprocess.run([ADB_PATH, "-s", device_id, "shell", "ls", remote_log_path], capture_output=True)
                    if check_result.returncode == 0:
                        run_command([ADB_PATH, "-s", device_id, "pull", remote_log_path, local_log_filename], suppress_output=True)
                        if os.path.exists(local_log_filename):
                            pulled_logs.append((local_log_filename, os.path.getmtime(local_log_filename)))
            
            if not pulled_logs:
                print_error("No logs found on any installed version.", exit_code=None)
            else:
                newest_log = max(pulled_logs, key=lambda x: x[1])[0]
                print_success(f"Newest log found from: {newest_log.replace('A2_', '').replace('.log', '')}")
                
                if os.path.exists("A2.log"):
                    os.remove("A2.log")
                shutil.move(newest_log, "A2.log")
                
                for log_file, _ in pulled_logs:
                    if log_file != newest_log and os.path.exists(log_file):
                        os.remove(log_file)

                with open("A2.log", "r", encoding='utf-8', errors='replace') as file:
                    content = file.read()
                    print(Fore.LIGHTYELLOW_EX + "\n--- Build Info ---")
                    find_pattern("Log date", r'Log file open,(.*)', content)
                    find_pattern("Unreal version/Build Name", r'LogInit: Engine Version: (.*)', content)
                    find_pattern("Build Date", r'LogInit: Compiled \(64-bit\): (.*)', content)
                    find_pattern("Headset", r'LogAndroid:   SRC_HMDSystemName: (.*)', content)
                    defaultmap = re.search('Browse Started Browse: "(.*)"', content)
                    if defaultmap and "/Game/A2/Maps/Station_Prime/Station_Prime_P" in defaultmap.group(1):
                        print("Modified APK: True")
                        tip = True
                    else:
                        print("Modified APK: False")
                    print(Fore.LIGHTYELLOW_EX + "\n--- Session Info ---")
                    find_pattern("External Provider ID", r'"ExternalProviderId":"(.*?)"', content)
                    find_pattern("Mothership ID", r'Mothership token generated; ID: (.*?),', content)
                    find_pattern("Mothership Token", r'Token: (.*)', content)
                    print(Fore.LIGHTYELLOW_EX + "\n--- User Info ---")
                    find_pattern("Username", r'"ExternalProviderUsername":"(.*?)"', content)
                    find_pattern("Level", r'"Progress":(.*?),"', content)
                    find_pattern("Driftium Balance", r'"name":"Drivium","quantity":(.*?)}', content)
                    find_pattern("Hypercube Balance", r'"name":"TechPoints","quantity":(.*?)}', content)
                    match = cosmetics = re.findall('"name":"(.*?)","quantity":1', content)
                    if match:
                        print("Owned Costmetics: " + str(len(list(set(cosmetics)))))
                    else: 
                        print("Owned Costmetics: Not Found")
                    print('')
            if tip:
                print(Fore.LIGHTYELLOW_EX + "Tip: Session and user info is only included in logs generated by an unmodified game")
    except FileNotFoundError:
        print_info("Error: A2.log not found.")
    except Exception as e:
        print_info(f"An unexpected error occurred: {e}")
    apk_path = None
    obb_path = None
    obb_thread = None
    if args.apk:
        action_performed = True
        apk_path = get_path_from_input(args.apk, "apk")
        if not apk_path.lower().endswith(".apk"):
            print_error(f"Invalid APK: File is not an .apk file.\nPath: '{apk_path}'")
    if args.obb:
        action_performed = True
        obb_path = get_path_from_input(args.obb, "obb")
        if not obb_path.lower().endswith(".obb"):
            print_error(f"Invalid OBB: File is not an .obb file.\nPath: '{obb_path}'")
        obb_thread = threading.Thread(target=upload_obb, args=(device_id, obb_path, effective_package_name, args.rename))
        obb_thread.start()
    if apk_path:
        if not args.skipdecompile:
            clean_temp_dir()
        process_apk(apk_path, args)
        was_wiped = install_modded_apk(device_id, effective_package_name)
    if obb_thread:
        obb_thread.join()
        if was_wiped and obb_path:
            upload_obb(device_id, obb_path, effective_package_name, args.rename)
    if args.ini:
        action_performed = True
        ini_path = get_path_from_input(args.ini, "ini")
        push_ini(device_id, ini_path, effective_package_name)
    if args.open:
        action_performed = True
        print_info("Opening game...")
        intent = effective_package_name+'/com.epicgames.unreal.GameActivity'
        subprocess.run([ADB_PATH, 'shell', 'input', 'keyevent', '26'],capture_output=True)
        subprocess.run([ADB_PATH, 'shell', 'am', 'broadcast', '-a', 'com.oculus.vrpowermanager.prox_close'],capture_output=True)
        subprocess.run([ADB_PATH, 'shell', 'am', 'start', '-n', intent],capture_output=True)
        subprocess.run([ADB_PATH, 'shell', 'am', 'broadcast', '-a', 'com.oculus.vrpowermanager.automation_disable'],capture_output=True)
    if not action_performed:
        print_error("No action specified. Please provide a task like --apk, --ini, etc. Use -h for help.", exit_code=0)
    print(Fore.LIGHTYELLOW_EX + "\n[DONE] All tasks complete. Have fun!")

def main():
    try:
        a2ll()
    finally:
        check_for_updates()

if __name__ == "__main__":
    main()