
import os
import subprocess
import argparse
import sys
import shutil
import requests
import zipfile
import platform
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

SDK_ROOT = "android-sdk"
BUILD_TOOLS_VERSION = "34.0.0"
PACKAGE_NAME = "com.AnotherAxiom.A2"
KEYSTORE_PASS = "com.AnotherAxiom.A2"

is_windows = platform.system() == "Windows"
exe_ext = ".exe" if is_windows else ""
bat_ext = ".bat" if is_windows else ""

ADB_PATH = os.path.join(SDK_ROOT, "platform-tools", f"adb{exe_ext}")
SDK_MANAGER_PATH = os.path.join(SDK_ROOT, "cmdline-tools", "bin", f"sdkmanager{bat_ext}")
BUILD_TOOLS_PATH = os.path.join(SDK_ROOT, "build-tools", BUILD_TOOLS_VERSION)
ZIPALIGN_PATH = os.path.join(BUILD_TOOLS_PATH, f"zipalign{exe_ext}")
APKSIGNER_PATH = os.path.join(BUILD_TOOLS_PATH, f"apksigner{bat_ext}")

TEMP_DIR = "tmp"
DECOMPILED_DIR = os.path.join(TEMP_DIR, "decompiled")
COMPILED_APK = os.path.join(TEMP_DIR, "compiled.apk")
ALIGNED_APK = os.path.join(TEMP_DIR, "compiled.aligned.apk")
SIGNED_APK = os.path.join(TEMP_DIR, "compiled.aligned.signed.apk")

CMD_TOOLS_URL = "https://dl.google.com/android/repository/commandlinetools-win-13114758_latest.zip"
CMD_TOOLS_ZIP = "commandlinetools.zip"

BANNER = r"""
     _    ____    _     _____ ____    _    ______   __  _        _   _   _ _   _  ____ _   _ _____ ____  
    / \  |___ \  | |   | ____/ ___|  / \  / ___\ \ / / | |      / \ | | | | \ | |/ ___| | | | ____|  _ \ 
   / _ \   __) | | |   |  _|| |  _  / _ \| |    \ V /  | |     / _ \| | | |  \| | |   | |_| |  _| | |_) |
  / ___ \ / __/  | |___| |__| |_| |/ ___ \ |___  | |   | |___ / ___ \ |_| | |\  | |___|  _  | |___|  _ < 
 /_/   \_\_____| |_____|_____\____/_/   \_\____| |_|   |_____/_/   \_\___/|_| \_|\____|_| |_|_____|_| \_\
"""

# A2 Legacy Launcher by Obelous

def print_info(message):
    print(f"[INFO] {message}")

def print_success(message):
    print(f"[SUCCESS] {message}")

def print_error(message, exit_code=1):
    print(f"[ERROR] {message}")
    if exit_code is not None:
        sys.exit(exit_code)

def get_app_data_dir():
    """Gets a reliable directory to store app data like the portable JRE."""
    home = os.path.expanduser("~")
    data_dir = os.path.join(home, ".a2-legacy-launcher")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

def run_command(command, suppress_output=False, env=None):
    try:
        process = subprocess.run(
            command,
            check=True,
            text=True,
            capture_output=True,
            env=env
        )
        if not suppress_output and process.stdout:
            print(process.stdout.strip())
        return process.stdout.strip()
    except FileNotFoundError:
        if command[0] == ADB_PATH or command[0] == SDK_MANAGER_PATH or command[0] == ZIPALIGN_PATH or command[0] == APKSIGNER_PATH:
            print_info(f"Required SDK component not found: {command[0]}. Re-initializing SDK setup.")
            if os.path.exists(SDK_ROOT):
                shutil.rmtree(SDK_ROOT)
            setup_sdk()
            print_info(f"SDK Redownloaded: re-run the script.")
            sys.exit()
        else:
            print_error(f"Command not found: {command[0]}. Please ensure it's installed and in your PATH.")
    except subprocess.CalledProcessError as e:
        error_message = (
            f"Command failed with exit code {e.returncode}:\n"
            f">>> {' '.join(command)}\n"
            f"--- STDOUT ---\n{e.stdout.strip()}\n"
            f"--- STDERR ---\n{e.stderr.strip()}"
        )
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
    if cleaned_path.startswith('& '):
        cleaned_path = cleaned_path[2:]
    return cleaned_path.strip('"\'')

def clean_temp_dir():
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
    os.makedirs(TEMP_DIR)


def get_java_path():
    system_java = shutil.which("java")

    if system_java:
        print_info(f"Found system Java at: {system_java}")
        return system_java
    app_data_dir = get_app_data_dir()
    jre_dir = os.path.join(app_data_dir, "jre-17")

    if platform.system() == "Windows":
        java_executable = os.path.join(jre_dir, "bin", "java.exe")
    else:
        java_executable = os.path.join(jre_dir, "bin", "java")

    if os.path.exists(java_executable):
        print_info(f"Found portable Java at: {java_executable}")
        return java_executable
    print_error("Java not found. A portable version will be downloaded.", exit_code=None)
    
    if platform.system() == "Windows" and platform.machine().endswith('64'):
        url = "https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.8%2B9/OpenJDK21U-jre_x64_windows_hotspot_21.0.8_9.zip"
        archive_path = os.path.join(app_data_dir, "jre.zip")
    else:
        print_error(f"Automatic java download not supported for your OS ({platform.system()}). Please install Java 17+ manually.")
        return None
    download_with_progress(url, archive_path)
    print_info(f"Extracting JRE to {jre_dir}...")
    with zipfile.ZipFile(archive_path, 'r') as zip_ref:
        top_level_dir = zip_ref.namelist()[0].split('/')[0]
        zip_ref.extractall(app_data_dir)
        os.rename(os.path.join(app_data_dir, top_level_dir), jre_dir)

    os.remove(archive_path)
    print_success("Portable JRE setup complete.")

    if os.path.exists(java_executable):
        return java_executable
    else:
        print_error("Failed to setup portable JRE.")
        return None

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

def setup_sdk():
    print_info("Android SDK not found. Starting automatic setup...")
    if not download_with_progress(CMD_TOOLS_URL, CMD_TOOLS_ZIP):
        return

    print_info(f"Extracting {CMD_TOOLS_ZIP}...")
    if os.path.exists(SDK_ROOT):
        shutil.rmtree(SDK_ROOT)
    
    with zipfile.ZipFile(CMD_TOOLS_ZIP, 'r') as zip_ref:
        temp_extract = "temp_extract_sdk"
        zip_ref.extractall(temp_extract)
        shutil.move(os.path.join(temp_extract, "cmdline-tools"), os.path.join(os.getcwd(), SDK_ROOT, "cmdline-tools"))
        shutil.rmtree(temp_extract)

    print_info("Cleaning up downloaded zip file...")
    os.remove(CMD_TOOLS_ZIP)

    print_info("Installing platform-tools...")
    run_interactive_command(
        [SDK_MANAGER_PATH, f"--sdk_root={SDK_ROOT}", "platform-tools"]
    )
    
    print_info(f"Installing build-tools;{BUILD_TOOLS_VERSION}...")
    run_interactive_command(
        [SDK_MANAGER_PATH, f"--sdk_root={SDK_ROOT}", f"build-tools;{BUILD_TOOLS_VERSION}"]
    )
    
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

def process_apk(apk_path, java_path):
    print_info("Decompiling APK...")
    run_command([java_path, "-jar", APKTOOL_JAR, "d", "-s", apk_path, "-o", DECOMPILED_DIR])
    
    print_info("Recompiling APK with debug flag...")
    run_command([java_path, "-jar", APKTOOL_JAR, "b", DECOMPILED_DIR, "-d", "-o", COMPILED_APK])

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
    parser = argparse.ArgumentParser(
        description="Orion Drift Legacy Launcher by Obelous",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("-a", "--apk", help="Path to the source APK file.")
    parser.add_argument("-o", "--obb", help="Path to the OBB file.")
    parser.add_argument("-i", "--ini", help="Path to a custom Engine.ini file.")
    args = parser.parse_args()

    print(BANNER)

    java_executable_path = get_java_path()
    if not java_executable_path:
        print_error("Could not find or install a valid Java runtime. Please install Java 17+ and ensure it's in your PATH.")
        sys.exit(1)
    
    is_manual_mode = any([args.apk, args.obb, args.ini])

    if not os.path.exists(SDK_MANAGER_PATH):
        setup_sdk()
    else:
        print_success("Android SDK found")
    
    if not os.path.exists(APKTOOL_JAR):
        print_error(f"{APKTOOL_JAR} not found. Please download it and place it in the same directory as this script.")
    if not os.path.exists(KEYSTORE_FILE):
        print_error(f"{KEYSTORE_FILE} not found. Please ensure it's in the same directory.")

    device_id = get_connected_device()

    if is_manual_mode:
        if args.apk:
            apk_path = args.apk
            if not os.path.isfile(apk_path) or not apk_path.lower().endswith(".apk"):
                print_error(f"Invalid APK path: File does not exist or is not an .apk file.\nPath: '{apk_path}'")
            print_success(f"Found APK: {apk_path}")
            clean_temp_dir()
            process_apk(apk_path)
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
        process_apk(apk_path)
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
            print_error(f"INI file not found: {ini_path}")

    print("\n[DONE] All tasks complete. Have fun!")

if __name__ == "__main__":
    main()