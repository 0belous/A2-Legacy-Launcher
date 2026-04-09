import os
import subprocess
import sys
import shutil
import requests
import zipfile
import re
import json
import hashlib
import time
import threading
from urllib.parse import urlparse, unquote, parse_qs
from colorama import Fore
import yaml
try:
    import certifi
except ImportError:
    certifi = None

from .config import *
from .config import __version__

CACHE_INDEX_LOCK = threading.Lock()
PROGRESS_LOCK = threading.Lock()
DOWNLOAD_INTERRUPT_EVENT = threading.Event()

LOGGING_MODE = "default"
PROGRESS_VISIBLE = False
PROGRESS_ENABLED = False
PROGRESS_BARS = {"apk": 0.0, "obb": 0.0}
PROGRESS_COMPONENTS = {
    "apk_download": 0.0,
    "apk_stage": 0.0,
    "apk_install": 0.0,
    "obb_download": 0.0,
    "obb_upload": 0.0,
}

APK_WEIGHTS = {"download": 0.45, "stage": 0.45, "install": 0.10}
OBB_WEIGHTS = {"download": 0.60, "upload": 0.40}

def _get_requests_session():
    session = requests.Session()
    if certifi:
        session.verify = certifi.where()
    else:
        session.verify = True
    return session

def _configure_ssl():
    """Configure SSL/HTTPS certificate verification using certifi."""
    if certifi and "SSL_CERT_FILE" not in os.environ:
        os.environ["SSL_CERT_FILE"] = certifi.where()
        os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

def request_interrupt():
    DOWNLOAD_INTERRUPT_EVENT.set()

def is_interrupt_requested():
    return DOWNLOAD_INTERRUPT_EVENT.is_set()

def _prepare_subprocess_env(env=None, for_sdk_command=False):
    """Prepare environment for subprocess execution, handling readline conflicts on Linux."""
    if env is None:
        env = os.environ.copy()
    else:
        env = dict(env)

    if not is_windows and for_sdk_command:
        env.pop('LD_LIBRARY_PATH', None)
        env.pop('LD_PRELOAD', None)
    
    return env

def is_info_mode():
    return LOGGING_MODE == "info"

def set_logging_mode(mode):
    global LOGGING_MODE
    normalized = (mode or "default").strip().lower()
    LOGGING_MODE = "info" if normalized == "info" else "default"

def _bar_line(label, percent):
    width = 34
    clamped = max(0.0, min(100.0, float(percent)))
    done = int((clamped / 100.0) * width)
    return f"{label:<3} [{'#' * done}{'-' * (width - done)}] {clamped:6.2f}%"

def _clear_progress_locked():
    global PROGRESS_VISIBLE
    if not PROGRESS_VISIBLE:
        return
    sys.stdout.write("\x1b[2F\x1b[2K\x1b[1E\x1b[2K\x1b[1F")
    sys.stdout.flush()
    PROGRESS_VISIBLE = False

def _print_line(message):
    with PROGRESS_LOCK:
        should_restore = PROGRESS_ENABLED and not is_info_mode()
        if should_restore:
            _clear_progress_locked()
        sys.stdout.write(f"{message}\n")
        sys.stdout.flush()
        if should_restore:
            _render_progress_locked()

def _render_progress_locked():
    global PROGRESS_VISIBLE
    if not PROGRESS_ENABLED or is_info_mode():
        return
    apk_line = _bar_line("APK", PROGRESS_BARS["apk"])
    obb_line = _bar_line("OBB", PROGRESS_BARS["obb"])
    if PROGRESS_VISIBLE:
        sys.stdout.write("\x1b[2F")
    sys.stdout.write(f"\x1b[2K{apk_line}\n\x1b[2K{obb_line}\n")
    sys.stdout.flush()
    PROGRESS_VISIBLE = True

def _recompute_bars_locked():
    PROGRESS_BARS["apk"] = (
        APK_WEIGHTS["download"] * PROGRESS_COMPONENTS["apk_download"]
        + APK_WEIGHTS["stage"] * PROGRESS_COMPONENTS["apk_stage"]
        + APK_WEIGHTS["install"] * PROGRESS_COMPONENTS["apk_install"]
    )
    PROGRESS_BARS["obb"] = (
        OBB_WEIGHTS["download"] * PROGRESS_COMPONENTS["obb_download"]
        + OBB_WEIGHTS["upload"] * PROGRESS_COMPONENTS["obb_upload"]
    )

def _set_component(component, value):
    with PROGRESS_LOCK:
        PROGRESS_COMPONENTS[component] = max(0.0, min(100.0, float(value)))
        _recompute_bars_locked()
        _render_progress_locked()

def begin_install_progress(apk_active, obb_active):
    global PROGRESS_ENABLED, PROGRESS_VISIBLE
    with PROGRESS_LOCK:
        PROGRESS_ENABLED = True
        PROGRESS_VISIBLE = False
        PROGRESS_COMPONENTS["apk_download"] = 0.0 if apk_active else 100.0
        PROGRESS_COMPONENTS["apk_stage"] = 0.0 if apk_active else 100.0
        PROGRESS_COMPONENTS["apk_install"] = 0.0 if apk_active else 100.0
        PROGRESS_COMPONENTS["obb_download"] = 0.0 if obb_active else 100.0
        PROGRESS_COMPONENTS["obb_upload"] = 0.0 if obb_active else 100.0
        _recompute_bars_locked()
        _render_progress_locked()

def finish_install_progress():
    global PROGRESS_ENABLED
    with PROGRESS_LOCK:
        if not PROGRESS_ENABLED:
            return
        for key in PROGRESS_COMPONENTS:
            PROGRESS_COMPONENTS[key] = 100.0
        _recompute_bars_locked()
        _render_progress_locked()
        PROGRESS_ENABLED = False

def set_download_progress(file_type, progress_percent):
    if file_type == "apk":
        _set_component("apk_download", progress_percent)
    elif file_type == "obb":
        _set_component("obb_download", progress_percent)

def mark_download_complete(file_type):
    set_download_progress(file_type, 100.0)

def set_apk_stage_progress(progress_percent):
    _set_component("apk_stage", progress_percent)

def set_apk_install_progress(progress_percent):
    _set_component("apk_install", progress_percent)

def set_obb_upload_progress(progress_percent):
    _set_component("obb_upload", progress_percent)

def print_info(message):
    if is_info_mode():
        _print_line(f"[INFO] {message}")

def print_success(message):
    _print_line(Fore.GREEN + f"[SUCCESS] {message}")

def print_status(message):
    _print_line(message)

def print_error(message, exit_code=1):
    _print_line(Fore.RED + f"[ERROR] {message}")
    if exit_code is not None:
        sys.exit(exit_code)

def run_command(command, suppress_output=False, env=None):
    try:
        is_sdk_cmd = len(command) > 0 and any(sdk_tool in command[0] for sdk_tool in [SDK_MANAGER_PATH, ADB_PATH, ZIPALIGN_PATH, APKSIGNER_PATH, "sdkmanager", "adb", "zipalign", "apksigner"])
        prepared_env = _prepare_subprocess_env(env, for_sdk_command=is_sdk_cmd)
        
        process = subprocess.run(command, check=True, text=True, capture_output=True, env=prepared_env)
        if is_info_mode() and not suppress_output and process.stdout:
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
        is_sdk_cmd = len(command) > 0 and any(sdk_tool in command[0] for sdk_tool in [SDK_MANAGER_PATH, ADB_PATH, ZIPALIGN_PATH, APKSIGNER_PATH, "sdkmanager", "adb", "zipalign", "apksigner"])
        prepared_env = _prepare_subprocess_env(env, for_sdk_command=is_sdk_cmd)
        
        subprocess.run(command, check=True, env=prepared_env)
    except FileNotFoundError:
        print_error(f"Command not found: {command[0]}. Please ensure it's in your PATH.")
    except subprocess.CalledProcessError as e:
        print_error(f"Command failed with exit code {e.returncode}: {' '.join(command)}")
    except Exception as e:
        print_error(f"An unexpected error occurred: {e}")

def load_config():
    if not os.path.exists(CONFIG_FILE):
        print_info(f"Creating default configuration at {CONFIG_FILE}")
        default_config = {
            'manifest_url': '(Manifest URL Here)',
            'autoupdate': True,
            'oculus_token': '',
            'logging_mode': 'default'
        }
        with open(CONFIG_FILE, 'w') as f:
            yaml.dump(default_config, f)
        return default_config
    try:
        with open(CONFIG_FILE, 'r') as f:
            loaded = yaml.safe_load(f) or {}
        updated = False
        if 'logging_mode' not in loaded:
            loaded['logging_mode'] = 'default'
            updated = True
        if updated:
            with open(CONFIG_FILE, 'w') as f:
                yaml.dump(loaded, f)
        return loaded
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
        session = _get_requests_session()
        r = session.get(url, headers={'User-Agent': USER_AGENT}, timeout=10); r.raise_for_status()
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

def check_for_updates(force=False):
    config = load_config()
    if not config.get('autoupdate', True):
        return

    try:
        repo_api = "https://api.github.com/repos/0belous/UE-Legacy-Launcher/releases/latest"
        session = _get_requests_session()
        response = session.get(repo_api, headers={'User-Agent': USER_AGENT}, timeout=3)
        response.raise_for_status()
        data = response.json()
        latest_version_str = data.get("tag_name", "").lstrip('v')
        
        def parse_version(v):
            return [int(x) for x in v.split('.') if x.isdigit()]
        
        has_newer_release = parse_version(latest_version_str) > parse_version(__version__)
        if has_newer_release or force:
            print(Fore.YELLOW + f"\nUpdate: A new version ({latest_version_str}) is available!")

            _os_name = platform.system().lower()
            asset_name = "uell-windows.exe" if "windows" in _os_name else "uell-macos" if "darwin" in _os_name else "uell-linux"
            asset_url = next((a["browser_download_url"] for a in data.get("assets", []) if a["name"] == asset_name), None)
            
            if not asset_url:
                return

            os.makedirs(TEMP_DIR, exist_ok=True)
            new_exe = os.path.join(TEMP_DIR, f"new_{asset_name}")
            if download(asset_url, new_exe):
                current_exe = sys.executable
                if is_windows:
                    up_bat = os.path.join(TEMP_DIR, "updater.bat")
                    with open(up_bat, "w") as f:
                        f.write(
                            f'@echo off\n'
                            f'setlocal\n'
                            f'set "SRC={new_exe}"\n'
                            f'set "DST={current_exe}"\n'
                            f'for /L %%i in (1,1,30) do (\n'
                            f'  move /Y "%SRC%" "%DST%" >nul 2>&1 && goto launch\n'
                            f'  timeout /t 1 /nobreak >nul\n'
                            f')\n'
                            f'echo [ERROR] Failed to replace binary after 30 retries. > "%TEMP%\\uell-updater-error.log"\n'
                            f'echo Source: %SRC% >> "%TEMP%\\uell-updater-error.log"\n'
                            f'echo Destination: %DST% >> "%TEMP%\\uell-updater-error.log"\n'
                            f'goto end\n'
                            f':launch\n'
                            f'start "" "%DST%"\n'
                            f':end\n'
                            f'del "%~f0"\n'
                        )
                    subprocess.Popen([up_bat], shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:
                    up_sh = os.path.join(TEMP_DIR, "updater.sh")
                    with open(up_sh, "w") as f:
                        f.write(f'#!/bin/bash\nsleep 1\nmv -f "{new_exe}" "{current_exe}"\nchmod +x "{current_exe}"\n"{current_exe}" &\nrm -- "$0"\n')
                    os.chmod(up_sh, 0o755)
                    subprocess.Popen(["bash", up_sh])
                print(Fore.YELLOW + "Applying update and restarting...")
                sys.exit(0)
    except Exception as e:
        print_error(f"Auto-update check failed: {e}", exit_code=None)

def parse_file_drop(raw_path):
    cleaned_path = raw_path.strip()
    if is_windows and cleaned_path.startswith('& '):
        cleaned_path = cleaned_path[2:].strip()
    return cleaned_path.strip("'\"")

def clean_temp_dir():
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
    os.makedirs(TEMP_DIR)

def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().lower()

def download(url, filename, file_type=None, expected_sha256=None):
    _configure_ssl()
    
    max_retries = 3
    for attempt in range(max_retries):
        if is_interrupt_requested():
            return False
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
            
            from pySmartDL import SmartDL
            
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
            obj = SmartDL(url, filename, progress_bar=False, threads=8, request_args={"headers": headers})
            obj.start(blocking=False)
            
            while not obj.isFinished():
                if is_interrupt_requested():
                    try:
                        obj.stop()
                    except Exception:
                        pass
                    try:
                        if os.path.exists(filename):
                            os.remove(filename)
                    except OSError:
                        pass
                    return False
                speed = obj.get_speed(human=True)
                downloaded = obj.get_dl_size()
                total = obj.get_final_filesize()
                
                if total > 0:
                    downloaded_mb = downloaded / (1024 * 1024)
                    total_mb = total / (1024 * 1024)
                    progress = obj.get_progress()
                    if file_type in ("apk", "obb"):
                        set_download_progress(file_type, progress * 100.0)
                    done = int(50 * progress)
                    if is_info_mode():
                        sys.stdout.write(f"\r[{'=' * done}{' ' * (50-done)}] {progress*100:.1f}% ({downloaded_mb:.2f}/{total_mb:.2f} MB) - {speed}          ")
                else:
                    if is_info_mode():
                        sys.stdout.write(f"\rDownloading... {speed}          ")
                if is_info_mode():
                    sys.stdout.flush()
                time.sleep(0.5)

            if obj.isSuccessful():
                if expected_sha256:
                    actual_sha256 = _sha256_file(filename)
                    expected = expected_sha256.lower()
                    if actual_sha256 != expected:
                        raise Exception(
                            f"Checksum mismatch for {os.path.basename(filename)}: expected {expected}, got {actual_sha256}"
                        )
                total = obj.get_final_filesize()
                if file_type in ("apk", "obb"):
                    mark_download_complete(file_type)
                if is_info_mode():
                    if total > 0:
                        total_mb = total / (1024 * 1024)
                        sys.stdout.write(f"\r[{'=' * 50}] 100.0% ({total_mb:.2f}/{total_mb:.2f} MB) - Done.          \n")
                    else:
                        sys.stdout.write(f"\rDownload Complete.          \n")
                    sys.stdout.flush()
                return True
            else:
                raise Exception(f"pySmartDL failed: {obj.get_errors()}")
        except Exception as e:
            if is_interrupt_requested():
                return False
            print_error(f"Failed to download file: {e}", exit_code=None)
        if attempt < max_retries - 1:
            if is_interrupt_requested():
                return False
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

def ensure_runtime_tools():
    apktool_ok = False
    if os.path.exists(APKTOOL_JAR):
        try:
            apktool_ok = _sha256_file(APKTOOL_JAR) == APKTOOL_SHA256
            if not apktool_ok:
                print_info("Existing apktool checksum mismatch. Re-downloading...")
                os.remove(APKTOOL_JAR)
        except Exception:
            apktool_ok = False

    if not apktool_ok:
        if not download(APKTOOL_DOWNLOAD_URL, APKTOOL_JAR, expected_sha256=APKTOOL_SHA256):
            print_error(f"Failed to download apktool from {APKTOOL_DOWNLOAD_URL}")

    aapt2_ok = True
    if IS_TERMUX:
        aapt2_ok = False
        if os.path.exists(AAPT2_PATH):
            try:
                aapt2_ok = _sha256_file(AAPT2_PATH) == AAPT2_TERMUX_SHA256
                if not aapt2_ok:
                    print_info("Existing aapt2 checksum mismatch. Re-downloading...")
                    os.remove(AAPT2_PATH)
            except Exception:
                aapt2_ok = False

    if IS_TERMUX and not aapt2_ok:
        if not download(AAPT2_TERMUX_URL, AAPT2_PATH, expected_sha256=AAPT2_TERMUX_SHA256):
            print_error(f"Failed to download aapt2 from {AAPT2_TERMUX_URL}")
        try:
            os.chmod(AAPT2_PATH, 0o755)
        except Exception:
            pass

def _is_supported_quest_device(device_id):
    supported_codenames = {"MONTEREY", "HOLLYWOOD", "SEACLIFF", "EUREKA", "PANTHER"}
    supported_model_aliases = {
        "QUEST",
        "QUEST 2",
        "QUEST PRO",
        "QUEST 3",
        "QUEST 3S",
        "META QUEST",
        "OCULUS QUEST",
    }

    props = {}
    for prop_name in ("ro.product.device", "ro.product.name", "ro.product.model"):
        value = run_command([ADB_PATH, "-s", device_id, "shell", "getprop", prop_name], suppress_output=True) or ""
        cleaned = value.strip()
        if cleaned:
            props[prop_name] = cleaned

    if not props:
        return False, ""

    upper_values = [p.upper() for p in props.values()]
    for value in upper_values:
        if any(code in value for code in supported_codenames):
            return True, ", ".join(props.values())
    model_and_name = " ".join(
        [
            props.get("ro.product.model", ""),
            props.get("ro.product.name", ""),
        ]
    ).upper()
    if any(alias in model_and_name for alias in supported_model_aliases):
        return True, ", ".join(props.values())

    return False, ", ".join(props.values())

def get_connected_device():
    print_info("Looking for connected devices...")
    output = run_command([ADB_PATH, "devices"])
    devices = [line.split('\t')[0] for line in output.strip().split('\n')[1:] if "device" in line and "unauthorized" not in line]
    if len(devices) == 1:
        device_id = devices[0]
        is_supported, device_info = _is_supported_quest_device(device_id)
        if not is_supported:
                print_error("Connected device is not a Quest headset.")
        print_success(f"Found one connected device: {device_id}")
        return device_id
    elif len(devices) > 1:
        print_error(f"Multiple devices found: {devices}. Please connect only one headset.")
    else:
        print_error("No authorized ADB device found. Check headset for an authorization prompt.")

def prompt_user_selection(options, prompt_text="Select an option:", auto_confirm=False):
    if not options: return None
    for i, opt in enumerate(options):
        print(f"  {i+1}) {opt}")
    if auto_confirm:
        return 0
    while True:
        try:
            choice = int(input(f"{prompt_text} (1-{len(options)}): ")) - 1
            if 0 <= choice < len(options):
                return choice
        except (ValueError, KeyboardInterrupt):
            pass

def get_cache_index():
    with CACHE_INDEX_LOCK:
        if not os.path.exists(CACHE_INDEX):
            return {}
        try:
            with open(CACHE_INDEX, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

def update_cache_index(index):
    with CACHE_INDEX_LOCK:
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
                session = _get_requests_session()
                r = session.head(head_url, allow_redirects=True, timeout=10, headers={'User-Agent':USER_AGENT})
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
                if file_type in ('apk', 'obb'):
                    mark_download_complete(file_type)
                return cached_path
        if download(url, cached_file_path, file_type=file_type):
            cache_entry = {"path": cached_file_path}
            if file_type == 'json':
                cache_entry['timestamp'] = time.time()
            latest_cache_index = get_cache_index()
            latest_cache_index[url] = cache_entry
            update_cache_index(latest_cache_index)
            print_info(f"Successfully downloaded {file_type}.")
            return cached_file_path
        else:
            print_error(f"Failed to download {file_type} from {url}.")
            return None
    if os.path.isfile(input_str):
        print_info(f"Using local {file_type}: {input_str}")
        if file_type in ('apk', 'obb'):
            mark_download_complete(file_type)
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
