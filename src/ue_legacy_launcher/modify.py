import os
import shutil
import xml.etree.ElementTree as ET
import mmap
import subprocess

try:
    from importlib.resources import files
except ImportError:
    pass

from .config import *
from .utils import (
    print_info, print_success, print_error, run_command, get_path_from_input,
    set_apk_stage_progress, set_apk_install_progress, set_obb_upload_progress
)

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
    for root, _, found_files in os.walk(decompiled_dir):
        if smali_filename in found_files:
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

def process_apk(apk_path, args, base_package, effective_package_name):
    java_heap = "-Xmx512m" if IS_TERMUX else "-Xmx2048m"
    if not args.skipdecompile:
        print_info("Decompiling APK...")
        set_apk_stage_progress(20)
        if not args.so:
            run_command(["java", java_heap, "-jar", APKTOOL_JAR, "d", "-s", apk_path, "-o", DECOMPILED_DIR])
        else: 
            run_command(["java", java_heap, "-jar", APKTOOL_JAR, "d", apk_path, "-o", DECOMPILED_DIR])
    else:
        print_info("Skipping decompilation, using previously decompiled files.")
        set_apk_stage_progress(25)
        if not os.path.isdir(DECOMPILED_DIR):
            print_error(f"Cannot skip decompilation: Directory '{DECOMPILED_DIR}' not found.")
        for f in [COMPILED_APK, ALIGNED_APK, SIGNED_APK]:
            if os.path.exists(f):
                os.remove(f)
    if args.rename:
        set_apk_stage_progress(40)
        rename_package(DECOMPILED_DIR, base_package, effective_package_name)
    if args.strip:
        print_info("Stripping permissions...")
        set_apk_stage_progress(50)
        modify_manifest(DECOMPILED_DIR)
    if args.commandline:
        set_apk_stage_progress(60)
        ue_cmdline_path = os.path.join(DECOMPILED_DIR, "assets", "UECommandLine.txt")
        os.makedirs(os.path.dirname(ue_cmdline_path), exist_ok=True)
        with open(ue_cmdline_path, 'w') as f:
            f.write(args.commandline)
    if args.so:
        set_apk_stage_progress(65)
        so_path = get_path_from_input(args.so, "so", getattr(args, 'local_archive', None))
        if so_path:
            inject_so(DECOMPILED_DIR, so_path)
    if args.patch:
        set_apk_stage_progress(70)
        patch_libunreal(args.patch)
    print_info("Recompiling APK...")
    set_apk_stage_progress(80)
    recompile_cmd = ["java", "-jar", APKTOOL_JAR, "b", DECOMPILED_DIR, "-d", "-o", COMPILED_APK]
    if IS_TERMUX:
        recompile_cmd.insert(4, "--aapt")
        recompile_cmd.insert(5, AAPT2_PATH)
    run_command(recompile_cmd)

    print_info("Aligning APK...")
    set_apk_stage_progress(90)
    run_command([ZIPALIGN_PATH, "-v", "4", COMPILED_APK, ALIGNED_APK], suppress_output=True)
    print_info("Signing APK...")
    set_apk_stage_progress(97)
    signing_env = os.environ.copy()
    signing_env["KEYSTORE_PASSWORD"] = KEYSTORE_PASS
    run_command([APKSIGNER_PATH, "sign", "--ks", KEYSTORE_FILE, "--ks-pass", f"env:KEYSTORE_PASSWORD", "--out", SIGNED_APK, ALIGNED_APK], env=signing_env)
    set_apk_stage_progress(100)
    print_success("APK processing complete.")

def install_modded_apk(device_id, package_name):
    subprocess.run([ADB_PATH, "-s", device_id, "uninstall", package_name], capture_output=True)
    print_info("Installing modified APK...")
    set_apk_install_progress(20)
    proc = subprocess.run([ADB_PATH, "-s", device_id, "install", "--streaming", "--no-incremental", SIGNED_APK], capture_output=True, text=True)
    if "Success" in proc.stdout:
        set_apk_install_progress(100)
        return True

    set_apk_install_progress(100)
    print_error(f"Installation failed: {proc.stdout}\n{proc.stderr}")
    return False

def upload_obb(device_id, obb_file, effective_package_name, is_renamed, original_package):
    set_obb_upload_progress(5)
    if is_renamed:
        new_obb_name = os.path.basename(obb_file).replace(original_package, effective_package_name)
        final_obb_name = new_obb_name
    else:
        final_obb_name = os.path.basename(obb_file)
    destination_dir = f"/sdcard/Android/obb/{effective_package_name}/"
    destination_path = destination_dir + final_obb_name
    subprocess.run([ADB_PATH, "-s", device_id, "shell", f"mkdir -p {destination_dir}"], capture_output=True)

    print_info(f"Uploading OBB...")
    set_obb_upload_progress(30)
    run_command([ADB_PATH, "-s", device_id, "push", obb_file, destination_path])
    set_obb_upload_progress(100)
    print_info("OBB upload complete.")

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
