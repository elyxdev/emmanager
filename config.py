import os

BASE_DIR = os.path.abspath("modpacks_manager")
MODPACKS_DIR = os.path.join(BASE_DIR, "modpacks_guardados")

def ensure_dirs():
    os.makedirs(MODPACKS_DIR, exist_ok=True)
