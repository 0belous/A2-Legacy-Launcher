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
import shutil
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

__version__ = "1.3.6"
USER_AGENT = f"LegacyLauncher/{__version__}"
IS_TERMUX = "TERMUX_VERSION" in os.environ

try:
    from importlib.resources import files
    jar_name = 'apktool-2.12.1-termux.jar' if IS_TERMUX else 'apktool_2.12.0.jar'
    KEYSTORE_FILE_REF = files('a2_legacy_launcher').joinpath('LegacyDev.keystore')
    APKTOOL_JAR_REF = files('a2_legacy_launcher').joinpath(jar_name)
except ImportError:
    from importlib.resources import path as resource_path
    jar_name = 'apktool-2.12.1-termux.jar' if IS_TERMUX else 'apktool_2.12.0.jar'
    KEYSTORE_FILE_REF = resource_path('a2_legacy_launcher', 'LegacyDev.keystore')
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
KEYSTORE_PASS = "legacylauncher"

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

os.makedirs(CACHE_DIR, exist_ok=True)

if is_windows:
    CMD_TOOLS_URL = "https://dl.google.com/android/repository/commandlinetools-win-13114758_latest.zip"
    UPDATE_SCRIPT_URL = "https://raw.githubusercontent.com/0belous/A2-Legacy-Launcher/main/update.bat"
else:
    CMD_TOOLS_URL = "https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip"
    UPDATE_SCRIPT_URL = "https://raw.githubusercontent.com/0belous/A2-Legacy-Launcher/main/update.sh"
CMD_TOOLS_ZIP = os.path.join(APP_DATA_DIR, "commandlinetools.zip")

BANNER = r"""
  _   _ _____   _     _____ ____    _    ______   __  _        _   _   _ _   _  ____ _   _ _____ ____  
 | | | | ____| | |   | ____/ ___|  / \  / ___\ \ / / | |      / \ | | | | \ | |/ ___| | | | ____|  _ \ 
 | | | |  _|   | |   |  _|| |  _  / _ \| |    \ V /  | |     / _ \| | | |  \| | |   | |_| |  _| | |_) |
 | |_| | |___  | |___| |__| |_| |/ ___ \ |___  | |   | |___ / ___ \ |_| | |\  | |___|  _  | |___|  _ < 
  \___/|_____| |_____|_____\____/_/   \_\____| |_|   |_____/_/   \_\___/|_| \_|\____|_| |_|_____|_| \_\
"""

def load_config():
    if not os.path.exists(CONFIG_FILE):
        print_info(f"Creating default configuration at {CONFIG_FILE}")
        default_config = {
            'manifest_url': '(Manifest URL Here)',
            'autoupdate': True,
            'oculus_token': ''
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

    versions = manifest.get('versions', [])
    for version_data in versions:
        if identifier_int is not None and version_data.get('version_number') == identifier_int:
            return version_data
        if identifier_int is not None and version_data.get('version_code') == identifier_int:
            return version_data
        if version_data.get('version') == identifier_str:
            return version_data
        if version_data.get('version') == f"1.0.{identifier_str}":
            return version_data

    date_match = re.match(r'^(\d{4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?$', identifier_str)
    if date_match:
        year, month, day = date_match.groups()
        target_date = year
        if month: target_date += f"-{month.zfill(2)}"
        if day: target_date += f"-{day.zfill(2)}"
        versions_with_dates = [v for v in versions if v.get('build_date')]
        sorted_versions = sorted(versions_with_dates, key=lambda x: x['build_date'])
        for v in sorted_versions:
            if v['build_date'] >= target_date:
                return v
    return None

def fetch_manifest(config):
    url = config.get('manifest_url')
    if not url or url == '(Manifest URL Here)': return {}
    try:
        r = requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=10); r.raise_for_status()
        m = r.json(); mv = m.get('manifest_version')
        rv = ".".join(__version__.split(".")[:2])
        if mv != rv: print(Fore.YELLOW + f"Incompatible Manifest: {mv}, Launcher: {rv}")
        return m
    except Exception as e:
        print_error(f"Failed to fetch manifest: {e}", exit_code=None)
        return {}

def get_launcher_pkgs(device_id, base_package):
    out = run_command([ADB_PATH, "-s", device_id, "shell", "pm", "list", "packages"], True)
    return [l.replace("package:", "").strip() for l in out.splitlines() if l.strip().endswith(base_package) or "com.LegacyLauncher." in l]

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
        pypi_url = "https://pypi.org/pypi/a2-legacy-Launcher/json"
        response = requests.get(pypi_url, headers={'User-Agent': USER_AGENT}, timeout=3)
        response.raise_for_status()
        latest_version_str = response.json()["info"]["version"] 
        def parse_version(v):
            return [int(x) for x in v.split('.') if x.isdigit()]
        current_version = parse_version(__version__)
        latest_version = parse_version(latest_version_str)
        if latest_version > current_version:
            print(Fore.YELLOW + f"Update: A new version ({latest_version_str}) is available!")
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
    max_retries = 3
    for attempt in range(max_retries):
        try:
            parsed_url = urlparse(url)
            is_oculus = False
            if parsed_url.scheme == 'https' and parsed_url.netloc == 'securecdn.oculus.com':
                is_oculus = True
                config = load_config()
                token = config.get('oculus_token')
                if token:
                    query = parse_qs(parsed_url.query)
                    if 'access_token' not in query:
                        separator = '&' if parsed_url.query else '?'
                        url += f"{separator}access_token={token}"
            print_info(f"Downloading {os.path.basename(filename)} from {url}... (Attempt {attempt + 1}/{max_retries})")
            obj = SmartDL(url, dest=filename, progress_bar=True, threads=1, timeout=20)
            obj.start()
            if obj.isSuccessful():
                return True
            else:
                errors = obj.get_errors()
                print_error(f"Failed to download file: {errors}", exit_code=None)
        except Exception as e:
            print_error(f"Failed to download file: {e}", exit_code=None)
        if attempt < max_retries - 1:
            print_info("Retrying in 2 seconds...")
            time.sleep(2)
        else:
            return False
            
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

def process_apk(apk_path, args, base_package, effective_package_name):
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
        rename_package(DECOMPILED_DIR, base_package, effective_package_name)
    if args.strip:
        print_info("Stripping permissions...")
        modify_manifest(DECOMPILED_DIR)
    if args.commandline:
        ue_cmdline_path = os.path.join(DECOMPILED_DIR, "assets", "UECommandLine.txt")
        os.makedirs(os.path.dirname(ue_cmdline_path), exist_ok=True)
        with open(ue_cmdline_path, 'w') as f:
            f.write(args.commandline)
    if args.so:
        so_path = get_path_from_input(args.so, "so", getattr(args, 'local_archive', None))
        if so_path:
            inject_so(DECOMPILED_DIR, so_path)
    if args.patch:
        patch_libunreal(args.patch)
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
    subprocess.run([ADB_PATH, "-s", device_id, "uninstall", package_name], capture_output=True)
    print_info("Installing modified APK...")
    proc = subprocess.run([ADB_PATH, "-s", device_id, "install", "--streaming", "--no-incremental", SIGNED_APK], capture_output=True, text=True)
    if "Success" in proc.stdout:
        return True
    
    print_error(f"Installation failed: {proc.stdout}\n{proc.stderr}")
    return False

def upload_obb(device_id, obb_file, effective_package_name, is_renamed, original_package):
    if is_renamed:
        new_obb_name = os.path.basename(obb_file).replace(original_package, effective_package_name)
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

def push_ini(device_id, ini_file, package_name, app_path):
    print_info("Pushing INI file...")
    tmp_ini_path = "/data/local/tmp/Engine.ini"
    run_command([ADB_PATH, "-s", device_id, "push", ini_file, tmp_ini_path])
    target_dir = f"files/UnrealGame/{app_path}/Saved/Config/Android"
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

def create_map_ini(map_name):
    real_map = map_name.split('|')[1] if '|' in map_name else map_name
    ini_content = f"[/Script/EngineSettings.GameMapsSettings]\nGameDefaultMap={real_map}\n\n"
    ini_path = os.path.join(TEMP_DIR, "Engine.ini")
    os.makedirs(TEMP_DIR, exist_ok=True)
    with open(ini_path, "w") as f:
        f.write(ini_content)
    return ini_path

def prompt_user_selection(options, prompt_text="Select an option:"):
    if not options: return None
    for i, opt in enumerate(options):
        print(f"  {i+1}) {opt}")
    while True:
        try:
            choice = int(input(f"{prompt_text} (1-{len(options)}): ")) - 1
            if 0 <= choice < len(options):
                return choice
        except (ValueError, KeyboardInterrupt):
            pass

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

def get_path_from_input(input_str, file_type, archive_path=None):
    if not input_str:
        return None
    if input_str.startswith("archive:/"):
        if not archive_path:
            print_error(f"Cannot resolve {input_str}: --archive was not provided.")
            return None
        internal_path = input_str[9:].lstrip('/')
        file_hash = hashlib.sha256(f"{archive_path}:{internal_path}".encode()).hexdigest()
        _, ext = os.path.splitext(internal_path)
        if not ext: ext = f".{file_type}"
        target_filename = f"{file_hash}{ext}"
        target_path = os.path.join(CACHE_DIR, target_filename)
        if os.path.exists(target_path):
             print_info(f"Using cached extracted file: {target_path}")
             return target_path
        try:
             print_info(f"Extracting {internal_path} from archive...")
             with zipfile.ZipFile(archive_path, 'r') as zf:
                 with zf.open(internal_path) as source, open(target_path, "wb") as target:
                     shutil.copyfileobj(source, target)
             return target_path
        except KeyError:
             print_error(f"File '{internal_path}' not found inside the archive.")
             return None
        except Exception as e:
             print_error(f"Failed to extract file: {e}")
             return None

    if input_str.startswith(('http://', 'https://')):
        url = input_str
        cache_index = get_cache_index()
        filename = None
        parsed_url = urlparse(url)
        is_oculus_cdn = parsed_url.scheme == 'https' and parsed_url.netloc == 'securecdn.oculus.com'
        if file_type == 'apk':
            url_hash = hashlib.sha256(url.encode()).hexdigest()
            filename = f"{url_hash}.apk"
        else:
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
            if is_oculus_cdn and file_type == 'obb':
                config = load_config()
                token = config.get('oculus_token')
                head_url = url
                if token:
                        query = parse_qs(parsed_url.query)
                        if 'access_token' not in query:
                            separator = '&' if parsed_url.query else '?'
                            head_url += f"{separator}access_token={token}"
                r = requests.head(head_url, allow_redirects=True, timeout=10, headers={'User-Agent': USER_AGENT})
                cd = r.headers.get('content-disposition')
                if cd:
                    fname = re.findall(r'filename=([^;]+)', cd)
                    if fname:
                        filename = fname[0].strip()
                        print_info(f"Resolved OBB filename: {filename}")
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
    error_msg = f"Invalid {file_type} input: '{input_str}'.\n"
    if file_type == 'ini':
        error_msg += "Please provide a valid URL or a local file path"
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

def patch_libunreal(pattern_hex):
    so_file_path = os.path.join(DECOMPILED_DIR, "lib", "arm64-v8a", "libUnreal.so")
    if not os.path.exists(so_file_path):
        print_error(f"Could not find libUnreal.so at:\n{so_file_path}", exit_code=None)
        return

    try:
        original_pattern = bytes.fromhex(pattern_hex)
    except ValueError:
        print_error(f"Invalid hex pattern provided: {pattern_hex}", exit_code=None)
        return
    print_info(f"Patching {pattern_hex[:8]}...")
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
        description="Legacy Launcher "+__version__+" by Obelous ",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument('download', nargs='?', default=None, help="Build version to download and install -")
    parser.add_argument("-v", "--version", action="version", version=f"Legacy Launcher {__version__}")
    parser.add_argument("--archive", help="Path/URL to a zip archive (use archive:/path/inside.apk)")
    parser.add_argument("-a", "--apk", help="Path/URL to an APK file")
    parser.add_argument("-o", "--obb", help="Path/URL to an OBB file")
    parser.add_argument("-i", "--ini", help="Path/URL for Engine.ini")
    parser.add_argument("-m", "--map", action="append", help="What map to load in format \"Label|Path/To/Map\"")
    parser.add_argument("--no-ini", action="store_false", dest="ini", help=argparse.SUPPRESS)
    parser.add_argument("-c", "--commandline", help="Launch arguments for UE")
    parser.add_argument("--no-commandline", action="store_false", dest="commandline", help=argparse.SUPPRESS)
    parser.add_argument("-so", "--so", help="Inject a custom .so file")
    parser.add_argument("-rn", "--rename", help="Rename the package to com.LegacyLauncher.<VALUE>")
    parser.add_argument("-p", "--patch", help="Byte pattern to patch")
    parser.add_argument("--no-patch", action="store_false", dest="patch", help=argparse.SUPPRESS)
    parser.add_argument("-rm", "--remove", action="store_true", dest="remove", default=None, help="Uninstall all versions")
    parser.add_argument("--no-remove", action="store_false", dest="remove", help=argparse.SUPPRESS)
    parser.add_argument("-l", "--logs", action="store_true", dest="logs", default=None, help="Pull game logs from the headset")
    parser.add_argument("--no-logs", action="store_false", dest="logs", help=argparse.SUPPRESS)
    parser.add_argument("-ls", "--list", action="store_true", dest="list", default=None, help="List available versions")
    parser.add_argument("--no-list", action="store_false", dest="list", help=argparse.SUPPRESS)
    parser.add_argument("-op", "--open", action="store_true", dest="open", default=None, help="Launch the game once finished")
    parser.add_argument("--no-open", action="store_false", dest="open", help=argparse.SUPPRESS)
    parser.add_argument("-sp", "--strip", action="store_true", dest="strip", default=None, help="Strip permissions to skip pompts on first launch")
    parser.add_argument("--no-strip", action="store_false", dest="strip", help=argparse.SUPPRESS)
    parser.add_argument("-sk", "--skipdecompile", action="store_true", dest="skipdecompile", default=None, help="Reuse previously decompiled files")
    parser.add_argument("--no-skipdecompile", action="store_false", dest="skipdecompile", help=argparse.SUPPRESS)
    parser.add_argument("-cc", "--clearcache", action="store_true", dest="clearcache", default=None, help="Delete cached downloads")
    parser.add_argument("--no-clearcache", action="store_false", dest="clearcache", help=argparse.SUPPRESS)
    parser.add_argument("-r", "--restore", action="store_true", dest="restore", default=None, help="Restore to the latest version")
    parser.add_argument("--no-restore", action="store_false", dest="restore", help=argparse.SUPPRESS)
    parser.add_argument("--set-manifest", dest="set_manifest", help="Set the manifest URL in the config")
    parser.add_argument("-sw", "--switch-map", action="store_true", dest="switch_version", help="Change which map to load")
    parser.add_argument("--message")
    args = parser.parse_args()
    print(Fore.LIGHTBLUE_EX + BANNER)
    
    config = load_config()
    
    if args.set_manifest:
        config['manifest_url'] = args.set_manifest
        with open(CONFIG_FILE, 'w') as f:
            yaml.dump(config, f)
        print_success(f"Manifest updated: {args.set_manifest}")
        return
    local_archive = None
    if args.archive:
        local_archive = get_path_from_input(args.archive, "zip")
        if not local_archive:
            print_error("Failed to process archive argument.")
            return
        args.local_archive = local_archive
    manifest = fetch_manifest(config)
    
    if not manifest and (not config.get('manifest_url') or config.get('manifest_url') == '(Manifest URL Here)'):
        print(Fore.YELLOW + f"Warning: No manifest configured at {CONFIG_FILE} Automatic download and configuration is unavailable.")

    BASE_PACKAGE = manifest.get('package_name', 'com.example.app')
    APP_NAME = manifest.get('app_name', 'App')
    APP_PATH = manifest.get('app_path', f'{APP_NAME}/{APP_NAME}')
    
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

    if args.download:
        if not manifest:
            print_error("A manifest is required to use the download argument. Please configure manifest_url in "+CONFIG_FILE)
        version_data = find_version_in_manifest(manifest, args.download)
        if not version_data:
            print_error(f"Version '{args.download}' not found in the manifest.")
        
        print_success(f"Installing: {version_data['version']}")
        flags_str = version_data.get('flags', '')
        print_info(f"Using flags: {flags_str}")
        manifest_tokens = shlex.split(flags_str)
        if args.rename:
            manifest_tokens = [t for t in manifest_tokens if t not in ("-rn", "--rename")]
        manifest_args, _ = parser.parse_known_args(manifest_tokens)
        if args.ini is None:
            args.ini = manifest_args.ini or version_data.get('ini_url')
        if args.map is None:
            args.map = manifest_args.map
        if args.commandline is None:
            args.commandline = manifest_args.commandline
        if args.patch is None:
            args.patch = manifest_args.patch
        if args.rename is None:
            args.rename = manifest_args.rename
        if args.strip is None:
            args.strip = manifest_args.strip
        if args.open is None:
            args.open = manifest_args.open
        if args.skipdecompile is None:
            args.skipdecompile = manifest_args.skipdecompile

        args.apk = version_data.get('apk_url')
        args.obb = version_data.get('obb_url')

    if args.message:
        print(Fore.RED + args.message)
    
    if args.list:
        versions = manifest.get('versions', [])
        if not versions:
            print_info("No versions found in manifest.")
        else:
            print_info("Available versions:")
            for v in versions:
                print(f"  - Version: {v.get('version', 'N/A')} ({v.get('version_code', 'N/A')})")
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

    if args.switch_version:
        if not manifest: print_error("Manifest required.")
        pkgs = set(get_launcher_pkgs(device_id, BASE_PACKAGE))
        candidates = []
        for v in manifest.get('versions', []):
            v_flags = v.get('flags', '')
            v_args, _ = parser.parse_known_args(shlex.split(v_flags))
            if v_args.rename:
                pkg = f"com.LegacyLauncher.{v_args.rename}"
            else:
                pkg = BASE_PACKAGE
            if pkg not in pkgs: continue
            if v_args.map and len(v_args.map) > 1:
                candidates.append((v['version'], pkg, v_args.map))
        if not candidates: print_error("No configurable versions found.")
        
        selected_candidate = candidates[0]
        if len(candidates) > 1:
            print(Fore.LIGHTBLUE_EX + "\nSelect version:")
            idx = prompt_user_selection([c[0] for c in candidates], "Choice")
            selected_candidate = candidates[idx]
            
        ver, pkg, maps = selected_candidate
        
        print(Fore.LIGHTBLUE_EX + "\nSelect map:")
        map_labels = [m.split('|')[0] for m in maps]
        map_idx = prompt_user_selection(map_labels, "Choice")
        
        ini_path = create_map_ini(maps[map_idx])
        push_ini(device_id, ini_path, pkg, APP_PATH)
        return

    effective_package_name = f"com.LegacyLauncher.{args.rename}" if args.rename else BASE_PACKAGE
    action_performed = False
    if args.remove:
        action_performed = True
        pkgs = get_launcher_pkgs(device_id, BASE_PACKAGE)
        count = 0
        for pkg in set(pkgs):
            target_dir = f"files/UnrealGame/{APP_PATH}/Saved/Config/Android"
            subprocess.run([ADB_PATH, "-s", device_id, "shell", f"run-as {pkg} sh -c 'chmod -R 777 {target_dir} 2>/dev/null'"], capture_output=True)
            if "Success" in subprocess.run([ADB_PATH, "-s", device_id, "uninstall", pkg], capture_output=True, text=True).stdout:
                count += 1
        print_success(f"Uninstalled {count} package(s).") if count > 0 else print_info("No relevant packages found.")
        return

    if args.restore:
        action_performed = True
        versions = manifest.get('versions', [])
        if not versions: print_error("No versions found.")
        latest = max(versions, key=lambda v: v.get('version_code') or 0)
        print_success(f"Restoring to latest: {latest.get('version')}")
        apk_path = get_path_from_input(latest.get('apk_url'), "apk", local_archive)
        obb_path = get_path_from_input(latest.get('obb_url'), "obb", local_archive)
        subprocess.run([ADB_PATH, "-s", device_id, "uninstall", BASE_PACKAGE], capture_output=True)
        obb_thread = threading.Thread(target=upload_obb, args=(device_id, obb_path, BASE_PACKAGE, False, BASE_PACKAGE))
        obb_thread.start()
        run_command([ADB_PATH, "-s", device_id, "install", "-r", apk_path])
        obb_thread.join()

    try:
        if args.logs:
            action_performed = True
            pkgs = get_launcher_pkgs(device_id, BASE_PACKAGE)
            pulled_logs = []
            for pkg in pkgs:
                remote_log = f"/sdcard/Android/data/{pkg}/files/UnrealGame/{APP_PATH}/Saved/Logs/{APP_NAME}.log"
                local_log = f"{APP_NAME}_{pkg}.log"
                ts = 0

                check_cmd = [ADB_PATH, "-s", device_id, "shell", f"if [ -f {remote_log} ]; then stat -c %Y {remote_log}; fi"]
                res = subprocess.run(check_cmd, capture_output=True, text=True)
                if res.returncode == 0 and res.stdout.strip().isdigit():
                    ts = int(res.stdout.strip())
                    run_command([ADB_PATH, "-s", device_id, "pull", remote_log, local_log], True)
                    if os.path.exists(local_log):
                        pulled_logs.append((local_log, ts or os.path.getmtime(local_log)))

            if not pulled_logs:
                print_error("No logs found.", None)
            else:
                newest = max(pulled_logs, key=lambda x: x[1])[0]
                log_final_name = f"{APP_NAME}.log"
                if os.path.exists(log_final_name): os.remove(log_final_name)
                shutil.move(newest, log_final_name)
                for f, _ in pulled_logs: 
                    if f != newest and os.path.exists(f): os.remove(f)

                with open(log_final_name, "r", encoding='utf-8', errors='replace') as file:
                    content = file.read()
                    print(Fore.LIGHTBLUE_EX + f"\n--- {APP_NAME} Build Info ---")
                    find_pattern("Log date", r'Log file open,(.*)', content)
                    find_pattern("Unreal version/Build Name", r'LogInit: Engine Version: (.*)', content)
                    find_pattern("Build Date", r'LogInit: Compiled \(64-bit\): (.*)', content)
                    find_pattern("Headset", r'LogAndroid:   SRC_HMDSystemName: (.*)', content)
                    defaultmap = re.search('Browse Started Browse: "(.*)"', content)
                    if defaultmap and "/Game/A2/Maps/Station_Prime/Station_Prime_P" in defaultmap.group(1):
                        print("Modified APK: True"); tip = True
                    else:
                        print("Modified APK: False")
                    print(Fore.LIGHTBLUE_EX + "\n--- Session Info ---")
                    find_pattern("Mothership ID", r'Mothership token generated; ID: (.*?),', content)
                    find_pattern("Mothership Token", r'Token: (.*)', content)
                    match = cosmetics = re.findall('"name":"(.*?)","quantity":1', content)
            if tip: print(Fore.LIGHTBLUE_EX + "Tip: Session and user info is only included in logs generated by an unmodified game")
    except Exception as e:
        print_info(f"An unexpected error occurred: {e}")
    apk_path = None
    obb_path = None
    obb_thread = None
    if args.apk:
        action_performed = True
        apk_path = get_path_from_input(args.apk, "apk", local_archive)
        if not apk_path.lower().endswith(".apk"):
            print_error(f"Invalid APK: File is not an .apk file.\nPath: '{apk_path}'")
    if args.obb:
        action_performed = True
        obb_path = get_path_from_input(args.obb, "obb", local_archive)
        if not obb_path:
             print_error("Failed to process OBB file.")
        if not obb_path.lower().endswith(".obb"):
            print_error(f"Invalid OBB: File is not an .obb file.\nPath: '{obb_path}'")
        obb_thread = threading.Thread(target=upload_obb, args=(device_id, obb_path, effective_package_name, args.rename, BASE_PACKAGE))
        obb_thread.start()
    if apk_path:
        if not args.skipdecompile:
            clean_temp_dir()
        process_apk(apk_path, args, BASE_PACKAGE, effective_package_name)
        was_wiped = install_modded_apk(device_id, effective_package_name)
    if obb_thread:
        obb_thread.join()
        if was_wiped and obb_path:
            upload_obb(device_id, obb_path, effective_package_name, args.rename, BASE_PACKAGE)

    if args.map:
        selected_map = args.map[0]
        if len(args.map) > 1:
            print(Fore.LIGHTBLUE_EX + "\nMultiple maps available for this version:")
            idx = prompt_user_selection([m.split('|')[0] if '|' in m else m for m in args.map], "Select a map")
            selected_map = args.map[idx]
            
        args.ini = create_map_ini(selected_map)

    if args.ini:
        action_performed = True
        ini_path = get_path_from_input(args.ini, "ini")
        push_ini(device_id, ini_path, effective_package_name, APP_PATH)
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
    print(Fore.LIGHTBLUE_EX + "\n[DONE] All tasks complete. Have fun!")

def main():
    try:
        a2ll()
    except KeyboardInterrupt:
        print(Fore.RED + "\n[!] Keyboard Interrupt.")
        os._exit(0)

    check_for_updates()

if __name__ == "__main__":
    main()