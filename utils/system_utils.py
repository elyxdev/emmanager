import os
import subprocess

def autodetect_mods_path():
    appdata = os.getenv("APPDATA")
    if appdata:
        path = os.path.join(appdata, ".minecraft", "mods")
        if os.path.exists(path):
            return path

    home = os.path.expanduser("~")

    path_linux = os.path.join(home, ".minecraft", "mods")
    if os.path.exists(path_linux):
        return path_linux

    path_mac = os.path.join(home, "Library", "Application Support", "minecraft", "mods")
    if os.path.exists(path_mac):
        return path_mac

    return None

def resource_path(relative_path):
    import sys
    import os

    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def open_folder(path):
    if os.name == 'nt':
        os.startfile(path)
    else:
        subprocess.Popen(['xdg-open', path])