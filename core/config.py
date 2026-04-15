import os

BASE_DIR = os.path.abspath("modpacks_manager")
MODPACKS_DIR = os.path.join(BASE_DIR, "modpacks_guardados")
BACKUP_DIR = os.path.join(BASE_DIR, "mods_backup")

def ensure_dirs():
    os.makedirs(MODPACKS_DIR, exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)