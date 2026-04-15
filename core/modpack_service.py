import os
import shutil
from core.config import MODPACKS_DIR, BACKUP_DIR

CURRENT_FILE = "current_modpack.txt"


class ModpackService:
    def __init__(self, mods_path: str):
        self.mods_path = mods_path

    def set_mods_path(self, path):
        self.mods_path = path

    def save_modpack(self, nombre):
        destino = os.path.join(MODPACKS_DIR, nombre)

        if os.path.exists(destino):
            raise Exception("El modpack ya existe")

        shutil.copytree(self.mods_path, destino)

    def load_modpack(self, nombre):
        self._backup_current()

        if nombre == "__EMPTY__":
            self._write_current("< Sin mods >")
            return

        origen = os.path.join(MODPACKS_DIR, nombre)

        for archivo in os.listdir(origen):
            shutil.copy(os.path.join(origen, archivo), self.mods_path)

        self._write_current(nombre)

    def delete_modpack(self, nombre):
        ruta = os.path.join(MODPACKS_DIR, nombre)
        if os.path.exists(ruta):
            shutil.rmtree(ruta)

    def list_modpacks(self):
        return os.listdir(MODPACKS_DIR)

    def get_current(self):
        file_path = os.path.join(self.mods_path, CURRENT_FILE)
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                return f.read().strip()
        return None

    # ---------- PRIVADOS ----------
    def _backup_current(self):
        for archivo in os.listdir(self.mods_path):
            if archivo == CURRENT_FILE:
                continue

            origen = os.path.join(self.mods_path, archivo)
            destino = os.path.join(BACKUP_DIR, archivo)

            if os.path.exists(destino):
                os.remove(destino)

            shutil.move(origen, destino)

    def _write_current(self, nombre):
        with open(os.path.join(self.mods_path, CURRENT_FILE), "w") as f:
            f.write(nombre)