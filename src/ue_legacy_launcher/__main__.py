import os
import subprocess
import argparse
import sys
import shutil
import re
import threading
import concurrent.futures
import atexit
import shlex
import signal
import yaml
from colorama import Fore, init

from .config import *
from .config import __version__
from .utils import (
    load_config, find_version_in_manifest, fetch_manifest, get_launcher_pkgs,
    check_for_updates, print_info, print_success, print_error, run_command,
    run_interactive_command, parse_file_drop, clean_temp_dir, download,
    check_and_install_java, setup_sdk, get_connected_device, prompt_user_selection,
    get_cache_index, update_cache_index, get_path_from_input, find_pattern,
    set_logging_mode, is_info_mode, begin_install_progress, finish_install_progress,
    print_status, _configure_ssl, ensure_runtime_tools, request_interrupt
)
from .modify import (
    modify_manifest, rename_package, inject_so, process_apk, install_modded_apk,
    upload_obb, push_ini, create_map_ini, patch_libunreal
)

init(autoreset=True)

_interrupt_event = threading.Event()

def _signal_handler(signum, frame):
    _interrupt_event.set()
    request_interrupt()
    print(Fore.RED + "\n[!] Keyboard Interrupt.")
    os._exit(130)

signal.signal(signal.SIGINT, _signal_handler)

def pause_on_exit():
    if "--stay" in sys.argv:
        try:
            input(Fore.YELLOW + "Press Enter to exit...")
        except Exception:
            pass

atexit.register(pause_on_exit)

def register_uri_handler():
    if IS_TERMUX:
        return
    if is_windows:
        try:
            import winreg
            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
            else:
                exe_path = os.path.abspath(sys.argv[0])
            if not exe_path.lower().endswith(".exe"):
                found_exe = shutil.which("uell")
                if found_exe:
                    exe_path = os.path.abspath(found_exe)

            key_path = r"Software\Classes\uell"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "URL:uell Protocol")
                winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
                with winreg.CreateKey(key, r"shell\open\command") as cmd_key:
                    winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, f'"{exe_path}" "%1"')
        except Exception:
            pass
    elif platform.system() == "Linux":
        try:
            desktop_dir = os.path.expanduser("~/.local/share/applications")
            os.makedirs(desktop_dir, exist_ok=True)
            desktop_path = os.path.join(desktop_dir, "uell.desktop")
            exe_path = sys.executable if getattr(sys, 'frozen', False) else "uell"
            desktop_content = f"""[Desktop Entry]
Name=UE Legacy Launcher
Exec={exe_path} %u
Type=Application
Terminal=true
MimeType=x-scheme-handler/uell;
"""
            with open(desktop_path, "w") as f:
                f.write(desktop_content)
            subprocess.run(["xdg-mime", "default", "uell.desktop", "x-scheme-handler/uell"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if shutil.which("update-desktop-database"):
                subprocess.run(["update-desktop-database", desktop_dir], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

def parse_uri_args():
    if len(sys.argv) == 2 and sys.argv[1].startswith("uell://"):
        uri = sys.argv[1][7:]
        if uri.endswith('/'):
            uri = uri[:-1]
        new_args = uri.split('&')
        sys.argv = [sys.argv[0]] + [arg for arg in new_args if arg]
    sys.argv = [arg.replace("https//", "https://").replace("http//", "http://") for arg in sys.argv]

def uell():
    parser = argparse.ArgumentParser(
        description="Legacy Launcher "+__version__+" by Obelous ",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument('download', nargs='*', default=[], help="Build version to download and install -")
    parser.add_argument("-v", "--version", action="version", version=f"Legacy Launcher {__version__}")
    parser.add_argument("-y", "--yes", "--auto-confirm", action="store_true", dest="auto_confirm", help="Automatically confirm prompts")
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
    parser.add_argument("--adb", nargs=argparse.REMAINDER, help="Run a custom adb command using bundled adb (example: --adb devices)")
    parser.add_argument("-sw", "--switch-map", action="store_true", dest="switch_version", help="Change which map to load")
    parser.add_argument("--stay", action="store_true", help="Keep the window open until Enter is pressed")
    parser.add_argument("--message")
    args = parser.parse_args()
    print(Fore.LIGHTBLUE_EX + BANNER)
    
    config = load_config()
    set_logging_mode(config.get('logging_mode', 'default'))
    
    if args.set_manifest:
        config['manifest_url'] = args.set_manifest
        with open(CONFIG_FILE, 'w') as f:
            yaml.dump(config, f)
        print_success(f"Manifest updated: {args.set_manifest}")
        if not any([args.download, args.apk, args.obb, args.ini, args.remove, 
                    args.logs, args.list, args.open, args.clearcache, 
                    args.restore, args.switch_version, args.adb]):
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

    download_tasks = []
    if args.download:
        if not manifest:
            print_error("A manifest is required to use the download argument. Please configure manifest_url in "+CONFIG_FILE)

        for identifier in args.download:
            version_data = find_version_in_manifest(manifest, identifier)
            if not version_data:
                print_error(f"Version '{identifier}' not found in the manifest.")

            task_args = argparse.Namespace(**vars(args))
            flags_str = version_data.get('flags', '')
            manifest_tokens = shlex.split(flags_str)
            if task_args.rename:
                manifest_tokens = [t for t in manifest_tokens if t not in ("-rn", "--rename")]
            manifest_args, _ = parser.parse_known_args(manifest_tokens)

            if task_args.ini is None:
                task_args.ini = manifest_args.ini or version_data.get('ini_url')
            if task_args.map is None:
                task_args.map = manifest_args.map
            if task_args.commandline is None:
                task_args.commandline = manifest_args.commandline
            if task_args.patch is None:
                task_args.patch = manifest_args.patch
            if task_args.rename is None:
                task_args.rename = manifest_args.rename
            if task_args.strip is None:
                task_args.strip = manifest_args.strip
            if task_args.open is None:
                task_args.open = manifest_args.open
            if task_args.skipdecompile is None:
                task_args.skipdecompile = manifest_args.skipdecompile

            task_args.apk = version_data.get('apk_url')
            task_args.obb = version_data.get('obb_url')
            download_tasks.append((identifier, version_data, flags_str, task_args))

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
    ensure_runtime_tools()

    if args.adb is not None:
        adb_args = [arg for arg in args.adb if arg]
        if not adb_args:
            print_error("No adb subcommand provided. Example: --adb devices", exit_code=1)
        print_info(f"Running bundled adb: {ADB_PATH} {' '.join(adb_args)}")
        run_interactive_command([ADB_PATH] + adb_args)
        return

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
            idx = prompt_user_selection([c[0] for c in candidates], "Choice", auto_confirm=args.auto_confirm)
            selected_candidate = candidates[idx]
            
        ver, pkg, maps = selected_candidate
        
        print(Fore.LIGHTBLUE_EX + "\nSelect map:")
        map_labels = [m.split('|')[0] for m in maps]
        map_idx = prompt_user_selection(map_labels, "Choice", auto_confirm=args.auto_confirm)
        
        ini_path = create_map_ini(maps[map_idx])
        push_ini(device_id, ini_path, pkg, APP_PATH)
        return

    action_performed = False

    def run_install_flow(task_args):
        nonlocal action_performed
        effective_package_name = f"com.LegacyLauncher.{task_args.rename}" if task_args.rename else BASE_PACKAGE
        apk_path = None
        obb_path = None
        was_wiped = False
        has_apk = bool(task_args.apk)
        has_obb = bool(task_args.obb)

        if has_apk or has_obb:
            begin_install_progress(has_apk, has_obb)

        def resolve_and_upload_obb():
            local_obb_path = get_path_from_input(task_args.obb, "obb", local_archive)
            if not local_obb_path:
                print_error("Failed to process OBB file.")
            if not local_obb_path.lower().endswith(".obb"):
                print_error(f"Invalid OBB: File is not an .obb file.\nPath: '{local_obb_path}'")
            upload_obb(device_id, local_obb_path, effective_package_name, task_args.rename, BASE_PACKAGE)
            return local_obb_path

        obb_future = None
        obb_executor = None
        try:
            if task_args.apk:
                action_performed = True
                if task_args.obb:
                    action_performed = True
                obb_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="uell-obb-")
                for thread in obb_executor._threads:
                    thread.daemon = True
                if task_args.obb:
                    obb_future = obb_executor.submit(resolve_and_upload_obb)
                apk_path = get_path_from_input(task_args.apk, "apk", local_archive)
                if not apk_path.lower().endswith(".apk"):
                    print_error(f"Invalid APK: File is not an .apk file.\nPath: '{apk_path}'")

                if not task_args.skipdecompile:
                    clean_temp_dir()
                process_apk(apk_path, task_args, BASE_PACKAGE, effective_package_name)
                was_wiped = install_modded_apk(device_id, effective_package_name)
            elif task_args.obb:
                action_performed = True
                obb_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                obb_future = obb_executor.submit(resolve_and_upload_obb)

            if obb_future:
                obb_path = obb_future.result()
                if was_wiped and obb_path:
                    upload_obb(device_id, obb_path, effective_package_name, task_args.rename, BASE_PACKAGE)
        finally:
            if obb_executor:
                obb_executor.shutdown(wait=not _interrupt_event.is_set())
            if has_apk or has_obb:
                finish_install_progress()

        if task_args.map:
            selected_map = task_args.map[0]
            if len(task_args.map) > 1:
                print(Fore.LIGHTBLUE_EX + "\nMultiple maps available for this version:")
                idx = prompt_user_selection([m.split('|')[0] if '|' in m else m for m in task_args.map], "Select a map", auto_confirm=task_args.auto_confirm)
                selected_map = task_args.map[idx]

            task_args.ini = create_map_ini(selected_map)

        if task_args.ini:
            action_performed = True
            ini_path = get_path_from_input(task_args.ini, "ini")
            push_ini(device_id, ini_path, effective_package_name, APP_PATH)

        if task_args.open:
            action_performed = True
            print_info("Opening game...")
            intent = effective_package_name+'/com.epicgames.unreal.GameActivity'
            subprocess.run([ADB_PATH, 'shell', 'input', 'keyevent', '26'], capture_output=True)
            subprocess.run([ADB_PATH, 'shell', 'am', 'broadcast', '-a', 'com.oculus.vrpowermanager.prox_close'], capture_output=True)
            subprocess.run([ADB_PATH, 'shell', 'am', 'start', '-n', intent], capture_output=True)
            subprocess.run([ADB_PATH, 'shell', 'am', 'broadcast', '-a', 'com.oculus.vrpowermanager.automation_disable'], capture_output=True)
    
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
        print_status(f"Restoring to latest: {latest.get('version')}")
        begin_install_progress(True, True)

        def restore_obb_worker():
            resolved_obb = get_path_from_input(latest.get('obb_url'), "obb", local_archive)
            if not resolved_obb:
                print_error("Failed to process OBB file.")
            if not resolved_obb.lower().endswith(".obb"):
                print_error(f"Invalid OBB: File is not an .obb file.\nPath: '{resolved_obb}'")
            upload_obb(device_id, resolved_obb, BASE_PACKAGE, False, BASE_PACKAGE)

        obb_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        obb_future = obb_executor.submit(restore_obb_worker)

        try:
            apk_path = get_path_from_input(latest.get('apk_url'), "apk", local_archive)
            if not apk_path.lower().endswith(".apk"):
                print_error(f"Invalid APK: File is not an .apk file.\nPath: '{apk_path}'")
            subprocess.run([ADB_PATH, "-s", device_id, "uninstall", BASE_PACKAGE], capture_output=True)
            run_command([ADB_PATH, "-s", device_id, "install", "-r", apk_path])
            obb_future.result()
        finally:
            obb_executor.shutdown(wait=not _interrupt_event.is_set())
            finish_install_progress()

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
                    match = cosmetics = re.findall('"name":"(.*?)","quantity":1', content)
    except Exception as e:
        print_info(f"An unexpected error occurred: {e}")
    if download_tasks:
        for idx, (identifier, version_data, flags_str, task_args) in enumerate(download_tasks, start=1):
            print_status(f"Installing ({idx}/{len(download_tasks)}): {version_data.get('version', identifier)}")
            if flags_str and is_info_mode():
                print_info(f"Using flags: {flags_str}")
            run_install_flow(task_args)
    else:
        if args.apk or args.obb:
            print_status("Installing (1/1): custom input")
        run_install_flow(args)

    if not action_performed:
        print_error("No action specified. Please provide a task like --apk, --ini, etc. Use -h for help.", exit_code=0)
    print(Fore.LIGHTBLUE_EX + "\n[DONE] All tasks complete. Have fun!")

def main():
    _configure_ssl()
    
    register_uri_handler()
    parse_uri_args()
    
    if len(sys.argv) == 1:
        print(Fore.GREEN + "[SUCCESS] Application URL registered successfully.")
        sys.argv.extend(["-h", "--stay"])
        
    try:
        uell()
    except KeyboardInterrupt:
        print(Fore.RED + "\n[!] Keyboard Interrupt.")
        sys.exit(0)

    check_for_updates()

if __name__ == "__main__":
    main()