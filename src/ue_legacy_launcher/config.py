import os
import platform
import sys
from importlib import resources

__version__ = "1.4.0"
USER_AGENT = f"LegacyLauncher/{__version__}"
IS_TERMUX = "TERMUX_VERSION" in os.environ

if getattr(sys, 'frozen', False):
    _base_dir = os.path.join(sys._MEIPASS, 'ue_legacy_launcher')
    jar_name = 'apktool-2.12.1-termux.jar' if IS_TERMUX else 'apktool_2.12.0.jar'
    KEYSTORE_FILE = os.path.join(_base_dir, 'LegacyDev.keystore')
    APKTOOL_JAR = os.path.join(_base_dir, jar_name)
    AAPT2_PATH = os.path.join(_base_dir, 'aapt2-ARM64')
else:
    try:
        from importlib.resources import files
        jar_name = 'apktool-2.12.1-termux.jar' if IS_TERMUX else 'apktool_2.12.0.jar'
        KEYSTORE_FILE_REF = files('ue_legacy_launcher').joinpath('LegacyDev.keystore')
        APKTOOL_JAR_REF = files('ue_legacy_launcher').joinpath(jar_name)
        AAPT2_PATH_REF = files('ue_legacy_launcher').joinpath('aapt2-ARM64')
    except ImportError:
        from importlib.resources import path as resource_path
        jar_name = 'apktool-2.12.1-termux.jar' if IS_TERMUX else 'apktool_2.12.0.jar'
        KEYSTORE_FILE_REF = resource_path('ue_legacy_launcher', 'LegacyDev.keystore')
        APKTOOL_JAR_REF = resource_path('ue_legacy_launcher', jar_name)
        AAPT2_PATH_REF = resource_path('ue_legacy_launcher', 'aapt2-ARM64')
    
    with resources.as_file(KEYSTORE_FILE_REF) as keystore_path:
        KEYSTORE_FILE = str(keystore_path)
    with resources.as_file(APKTOOL_JAR_REF) as apktool_path:
        APKTOOL_JAR = str(apktool_path)
    with resources.as_file(AAPT2_PATH_REF) as aapt2_ref:
        AAPT2_PATH = str(aapt2_ref)

def get_app_data_dir():
    home = os.path.expanduser("~")
    if platform.system() == "Linux":
        data_dir = os.path.join(home, ".config", "ue-legacy-launcher")
    else:
        data_dir = os.path.join(home, ".ue-legacy-launcher")
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
else:
    CMD_TOOLS_URL = "https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip"
CMD_TOOLS_ZIP = os.path.join(APP_DATA_DIR, "commandlinetools.zip")

BANNER = r"""
  _   _ _____   _     _____ ____    _    ______   __  _        _   _   _ _   _  ____ _   _ _____ ____  
 | | | | ____| | |   | ____/ ___|  / \  / ___\ \ / / | |      / \ | | | | \ | |/ ___| | | | ____|  _ \ 
 | | | |  _|   | |   |  _|| |  _  / _ \| |    \ V /  | |     / _ \| | | |  \| | |   | |_| |  _| | |_) |
 | |_| | |___  | |___| |__| |_| |/ ___ \ |___  | |   | |___ / ___ \ |_| | |\  | |___|  _  | |___|  _ < 
  \___/|_____| |_____|_____\____/_/   \_\____| |_|   |_____/_/   \_\___/|_| \_|\____|_| |_|_____|_| \_\
"""
