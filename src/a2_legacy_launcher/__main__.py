import os
import subprocess
import argparse
import sys
import shutil
import requests
import zipfile
import platform
import xml.etree.ElementTree as ET
from importlib import resources

try:
    from importlib.resources import files
    KEYSTORE_FILE_REF = files('a2_legacy_launcher').joinpath('dev.keystore')
    APKTOOL_JAR_REF = files('a2_legacy_launcher').joinpath('apktool_2.12.0.jar')
except ImportError:
    from importlib.resources import path as resource_path
    KEYSTORE_FILE_REF = resource_path('a2_legacy_launcher', 'dev.keystore')
    APKTOOL_JAR_REF = resource_path('a2_legacy_launcher', 'apktool_2.12.0.jar')

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

BUILD_TOOLS_VERSION = "34.0.0"
PACKAGE_NAME = "com.AnotherAxiom.A2"
KEYSTORE_PASS = "com.AnotherAxiom.A2"

is_windows = os.name == "nt"
exe_ext = ".exe" if is_windows else ""
script_ext = ".bat" if is_windows else ""

ADB_PATH = os.path.join(SDK_ROOT, "platform-tools", f"adb{exe_ext}")
SDK_MANAGER_PATH = os.path.join(SDK_ROOT, "cmdline-tools", "latest", "bin", f"sdkmanager{script_ext}")
BUILD_TOOLS_PATH = os.path.join(SDK_ROOT, "build-tools", BUILD_TOOLS_VERSION)
ZIPALIGN_PATH = os.path.join(BUILD_TOOLS_PATH, f"zipalign{exe_ext}")
APKSIGNER_PATH = os.path.join(BUILD_TOOLS_PATH, f"apksigner{script_ext}")

DECOMPILED_DIR = os.path.join(TEMP_DIR, "decompiled")
COMPILED_APK = os.path.join(TEMP_DIR, "compiled.apk")
ALIGNED_APK = os.path.join(TEMP_DIR, "compiled.aligned.apk")
SIGNED_APK = os.path.join(TEMP_DIR, "compiled.aligned.signed.apk")

if is_windows:
    CMD_TOOLS_URL = "https://dl.google.com/android/repository/commandlinetools-win-13114758_latest.zip"
else:
    CMD_TOOLS_URL = "https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip"
CMD_TOOLS_ZIP = os.path.join(APP_DATA_DIR, "commandlinetools.zip")

BANNER = r"""
     _    ____    _     _____ ____    _    ______   __  _        _   _   _ _   _  ____ _   _ _____ ____
    / \  |___ \  | |   | ____/ ___|  / \  / ___\ \ / / | |      / \ | | | | \ | |/ ___| | | | ____|  _ \
   / _ \   __) | | |   |  _|| |  _  / _ \| |    \ V /  | |     / _ \| | | |  \| | |   | |_| |  _| | |_) |
  / ___ \ / __/  | |___| |__| |_| |/ ___ \ |___  | |   | |___ / ___ \ |_| | |\  | |___|  _  | |___|  _ <
 /_/   \_\_____| |_____|_____\____/_/   \_\____| |_|   |_____/_/   \_\___/|_| \_|\____|_| |_|_____|_| \_\
"""

def print_info(message):
    print(f"[INFO] {message}")

def print_success(message):
    print(f"[SUCCESS] {message}")

def print_error(message, exit_code=1):
    print(f"[ERROR] {message}")
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

def download_with_progress(url, filename):
    print_info(f"Downloading {filename} from {url}...")
    try:
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            with open(filename, 'wb') as f:
                chunk_size = 8192
                for chunk in r.iter_content(chunk_size=chunk_size):
                    f.write(chunk)
                    print(f"\rDownloading... {f.tell() / (1024*1024):.2f} MB of {total_size / (1024*1024):.2f} MB", end="")
        print("\nDownload complete.")
        return True
    except requests.exceptions.RequestException as e:
        print_error(f"Failed to download file: {e}")
        return False

def check_and_install_java():
    if shutil.which("java"):
        print_success("Java detected")
        return

    print_error("Java not found. The Java Runtime Environment (JRE) is required.", exit_code=None)
    
    if is_windows:
        url = "https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.8%2B9/OpenJDK21U-jre_x64_windows_hotspot_21.0.8_9.msi"
        installer_path = os.path.join(APP_DATA_DIR, "OpenJDK.msi")
        
        if not download_with_progress(url, installer_path):
            print_error("Failed to download Java installer. Please install it manually.")
            return

        print_info("Running the Java installer... Please accept the UAC prompt and follow the installation steps.")
        run_interactive_command(["msiexec", "/i", installer_path])
        
        print_success("Java installation finished.")
        os.remove(installer_path)
        print_info("Please close and re-open your terminal, then run a2ll again.")
        sys.exit(0)
    else:
        print_error("Please install Java by running: 'sudo apt update && sudo apt install default-jre'", exit_code=None)
        print_info("Once Java is installed, please re-run a2ll")
        sys.exit(1)

def setup_sdk():
    print_info("Android SDK not found. Starting automatic setup...")
    if not download_with_progress(CMD_TOOLS_URL, CMD_TOOLS_ZIP):
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
        for line in lines:
            if any(permission in line for permission in permissions_to_remove):
                continue
            if 'android.hardware.microphone' in line and 'android:required="true"' in line:
                modified_lines.append(line.replace('android:required="true"', 'android:required="false"'))
                continue
            modified_lines.append(line)
        with open(manifest_path, 'w', encoding='utf-8') as f:
            f.writelines(modified_lines)
    except Exception as e:
        print_error(f"Failed to modify AndroidManifest.xml: {e}")

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
    if not args.usecache:
        print_info("Decompiling APK...")
        run_command(["java", "-jar", APKTOOL_JAR, "d", "-s", apk_path, "-o", DECOMPILED_DIR])
    else:
        os.remove(COMPILED_APK)
        os.remove(ALIGNED_APK)
        os.remove(SIGNED_APK)
    if args.strip:
        print_info("Stripping permissions...")
        modify_manifest(DECOMPILED_DIR)
    if args.commandline:
        user_profile = os.environ.get('USERNAME') or os.environ.get('USER')
        appdata_base = os.path.expanduser("~")
        ue_cmdline_path = os.path.join(appdata_base, ".a2-legacy-launcher", "tmp", "decompiled", "assets", "UECommandLine.txt")
        os.makedirs(os.path.dirname(ue_cmdline_path), exist_ok=True)
        with open(ue_cmdline_path, 'w') as f:
            f.write(args.commandline)
    print_info("Recompiling APK with debug flag...")
    run_command(["java", "-jar", APKTOOL_JAR, "b", DECOMPILED_DIR, "-d", "-o", COMPILED_APK])
    print_info("Aligning APK...")
    run_command([ZIPALIGN_PATH, "-v", "4", COMPILED_APK, ALIGNED_APK], suppress_output=True)
    print_info("Signing APK...")
    signing_env = os.environ.copy()
    signing_env["KEYSTORE_PASSWORD"] = KEYSTORE_PASS
    run_command([APKSIGNER_PATH, "sign", "--ks", KEYSTORE_FILE, "--ks-pass", f"env:KEYSTORE_PASSWORD", "--out", SIGNED_APK, ALIGNED_APK], env=signing_env)
    print_success("APK processing complete.")

def install_modded_apk(device_id):
    print_info(f"Uninstalling {PACKAGE_NAME}...")
    subprocess.run([ADB_PATH, "-s", device_id, "uninstall", PACKAGE_NAME], check=False, capture_output=True)
    print_info("Installing modified APK...")
    run_command([ADB_PATH, "-s", device_id, "install", "-r", SIGNED_APK])
    print_success("Installation complete.")

def upload_obb(device_id, obb_file):
    destination_dir = f"/sdcard/Android/obb/{PACKAGE_NAME}/"
    print_info(f"Creating OBB directory on device: {destination_dir}")
    run_command([ADB_PATH, "-s", device_id, "shell", "mkdir", "-p", destination_dir])
    print_info(f"Uploading OBB file to {destination_dir}...")
    run_command([ADB_PATH, "-s", device_id, "push", obb_file, destination_dir])
    print_success("OBB upload complete.")

def push_ini(device_id, ini_file):
    print_info("Pushing INI file...")
    tmp_ini_path = "/data/local/tmp/Engine.ini"
    run_command([ADB_PATH, "-s", device_id, "push", ini_file, tmp_ini_path])
    target_dir = f"files/UnrealGame/A2/A2/Saved/Config/Android"
    
    shell_command = f"""
    run-as {PACKAGE_NAME} sh -c '
    mkdir -p {target_dir} 2>/dev/null;
    chmod -R 755 {target_dir} 2>/dev/null;
    cp {tmp_ini_path} {target_dir}/Engine.ini 2>/dev/null;
    chmod -R 555 {target_dir} 2>/dev/null
    '
    """
    run_command([ADB_PATH, "-s", device_id, "shell", shell_command])
    print_success("INI file pushed successfully.")

def main():
    parser = argparse.ArgumentParser(description="A2 Legacy Launcher by Obelous", formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-a", "--apk", help="Path to the source APK file.")
    parser.add_argument("-o", "--obb", help="Path to the OBB file.")
    parser.add_argument("-i", "--ini", help="Path to a custom Engine.ini file.")
    parser.add_argument("-r", "--remove", action="store_true", help="Use this if reinstalling doesnt bring you back to latest.")
    parser.add_argument("-l", "--logs", action="store_true", help="Pull game logs from the headset")
    parser.add_argument("-c", "--commandline", help="What commandline options to inject in UECommandline.txt")
    parser.add_argument("-so", "--so", help="Inject a custom .so file")
    parser.add_argument("-p", "--open", action="store_true", help="Open the game once finished")
    parser.add_argument("-s", "--strip", action="store_true", help="Strip permissions from manifest (to skip pompts)")
    parser.add_argument("-b", "--usecache", action="store_true", help="Skip deleting build cache and re-decompiling")
    args = parser.parse_args()

    print(BANNER)

    check_and_install_java()

    if not os.path.exists(SDK_MANAGER_PATH):
        setup_sdk()
    else:
        print_success("Android SDK found")
    
    if not os.path.exists(APKTOOL_JAR):
        print_error(f"Packaged component {APKTOOL_JAR} not found.")
    if not os.path.exists(KEYSTORE_FILE):
        print_error(f"Packaged component {KEYSTORE_FILE} not found.")

    device_id = get_connected_device()

    if args.remove:
        print_info(f"Attempting to uninstall {PACKAGE_NAME}...")
        
        target_dir = f"files/UnrealGame/A2/A2/Saved/Config/Android"
        shell_command = f"run-as {PACKAGE_NAME} sh -c 'chmod -R 777 {target_dir} 2>/dev/null;'"
        
        subprocess.run([ADB_PATH, "-s", device_id, "shell", shell_command], capture_output=True, text=True)
        
        run_command([ADB_PATH, "-s", device_id, "uninstall", PACKAGE_NAME])
        sys.exit(0)

    if args.logs:
        print_info(f"Pulling logs...")
        if os.path.exists('./A2.log'):
            os.remove("./A2.log")
        run_command([ADB_PATH, "pull", "/sdcard/Android/data/com.AnotherAxiom.A2/files/UnrealGame/A2/A2/Saved/Logs/A2.log", "./A2.log"])
        sys.exit(0)

    is_manual_mode = any([args.apk, args.obb, args.ini])
    if is_manual_mode:
        if args.apk:
            apk_path = args.apk
            if not os.path.isfile(apk_path) or not apk_path.lower().endswith(".apk"):
                print_error(f"Invalid APK path: File does not exist or is not an .apk file.\nPath: '{apk_path}'")
            print_success(f"Found APK: {apk_path}")
            if not args.usecache:
                clean_temp_dir()
            process_apk(apk_path, args)
            install_modded_apk(device_id)

        if args.obb:
            obb_path = args.obb
            if not os.path.isfile(obb_path) or not obb_path.lower().endswith(".obb"):
                print_error(f"Invalid OBB path: File does not exist or is not an .obb file.\nPath: '{obb_path}'")
            print_success(f"Found OBB: {obb_path}")
            upload_obb(device_id, obb_path)

        if args.ini:
            ini_path = args.ini
            if not os.path.isfile(ini_path):
                 print_error(f"Invalid INI path: File does not exist.\nPath: '{ini_path}'")
            print_success(f"Found INI: {ini_path}")
            push_ini(device_id, ini_path)
    else:
        clean_temp_dir()
        apk_path = parse_file_drop(input("Drag and drop the APK you want to use onto this terminal, then press Enter: "))
        if not os.path.isfile(apk_path) or not apk_path.lower().endswith(".apk"):
            print_error(f"Invalid path: Not an APK file or file doesn't exist.\nParsed path: '{apk_path}'")
        print_success("Found APK")
        process_apk(apk_path, args)
        install_modded_apk(device_id)

        obb_path = parse_file_drop(input("Drag and drop the OBB you want to use, or press Enter to skip: "))
        if obb_path:
            if os.path.isfile(obb_path) and obb_path.lower().endswith(".obb"):
                print_success("Found OBB")
                upload_obb(device_id, obb_path)
            else:
                print_error("OBB file not found or invalid. Continuing without OBB.", exit_code=None)
        else:
            print_info("Skipping OBB upload.")

        ini_path = ""
        print("\n[1] - Default: will work for most builds <-- Recommended")
        print("[2] - Vegas: default level used in the vegas build")
        print("[3] - 4v4: 4v4 level used in the competitive branch")
        print("[4] - Custom: provide a custom ini file")
        choice = input("Enter 1-4 to pick which ini file to use (press Enter for default): ").strip()
        
        ini_file_name = None
        if choice == "1" or not choice:
            ini_file_name = "Engine.ini"
        elif choice == "2":
            ini_file_name = "EngineVegas.ini"
        elif choice == "3":
            ini_file_name = "Engine4v4.ini"
        elif choice == "4":
            ini_path = parse_file_drop(input("Drag and drop your custom .ini file here, then press Enter: "))
        else:
            print_error("Invalid option.")

        if ini_file_name:
            try:
                with resources.as_file(files('a2_legacy_launcher').joinpath(ini_file_name)) as p:
                    ini_path = str(p)
            except (ImportError, AttributeError):
                with resources.path('a2_legacy_launcher', ini_file_name) as p:
                    ini_path = str(p)
    
        if os.path.isfile(ini_path):
            push_ini(device_id, ini_path)
        else:
            if ini_path:
                print_error(f"INI file not found: {ini_path}")

    intent = PACKAGE_NAME+'/com.epicgames.unreal.GameActivity'
    if args.open:
        print_info("Opening game...")
        subprocess.run([ADB_PATH, 'shell', 'input', 'keyevent', '26'],capture_output=True)
        subprocess.run([ADB_PATH, 'shell', 'am', 'broadcast', '-a', 'com.oculus.vrpowermanager.prox_close'],capture_output=True)
        subprocess.run([ADB_PATH, 'shell', 'am', 'start', '-n', intent],capture_output=True)
        subprocess.run([ADB_PATH, 'shell', 'am', 'broadcast', '-a', 'com.oculus.vrpowermanager.automation_disable'],capture_output=True)
    print("\n[DONE] All tasks complete. Have fun!")

if __name__ == "__main__":
    main()