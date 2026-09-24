import json
import os
import shutil
import stat
import sys
import zipfile

from core.config import MODPACKS_DIR

CURRENT_FILE = "current_modpack.txt"
MANIFEST_FILE = "emmanager.json"
EMPTY_LABEL = "< Sin mods >"

# Carpetas que forman un modpack. Dentro del .zip van una al lado de la otra
# (aunque estén vacías) y al usar el modpack se colocan junto a la carpeta mods.
PACK_DIRS = ("mods", "config", "resourcepacks")

TMP_DIRNAME = ".emmanager_tmp"
RECOVER_FILE = "RECUPERAR.txt"
INVALID_CHARS = '<>:"/\\|?*'
CHUNK = 1024 * 1024


class ModpackError(Exception):
    """Error pensado para mostrarse tal cual al usuario."""


class _RollbackFailed(Exception):
    pass


class ModpackService:
    """
    Los modpacks se guardan como  modpacks_guardados/<nombre>.zip  con esta forma:

        emmanager.json
        mods/
        config/
        resourcepacks/

    Solo se descomprimen en la carpeta de Minecraft cuando se van a usar.
    """

    def __init__(self, mods_path=None):
        self.mods_path = None
        self._info_cache = {}
        self.set_mods_path(mods_path)

    # ---------- RUTAS ----------
    def set_mods_path(self, path):
        self.mods_path = os.path.abspath(path) if path else None

    @property
    def game_dir(self):
        """Carpeta de Minecraft: la que contiene a mods, config y resourcepacks."""
        return os.path.dirname(self.mods_path) if self.mods_path else None

    @staticmethod
    def resolve_mods_path(path):
        """Si el usuario elige .minecraft en vez de mods, usa su subcarpeta mods."""
        path = os.path.abspath(path)
        if os.path.basename(path).lower() != "mods":
            sub = os.path.join(path, "mods")
            if os.path.isdir(sub):
                return sub
        return path

    def zip_path(self, nombre):
        return os.path.join(MODPACKS_DIR, nombre + ".zip")

    def _targets(self):
        game = self.game_dir
        return {
            "mods": self.mods_path,
            "config": os.path.join(game, "config"),
            "resourcepacks": os.path.join(game, "resourcepacks"),
        }

    def _require_path(self):
        if not self.mods_path:
            raise ModpackError("Selecciona primero la carpeta de mods.")

    # ---------- NOMBRES ----------
    @staticmethod
    def validate_name(nombre):
        nombre = (nombre or "").strip()
        if not nombre:
            raise ValueError("Escribe un nombre para el modpack.")
        if any(c in INVALID_CHARS or ord(c) < 32 for c in nombre) or nombre.endswith("."):
            raise ValueError('El nombre no puede contener  < > : " / \\ | ? *  ni terminar en punto.')
        return nombre

    def check_new_name(self, nombre):
        nombre = self.validate_name(nombre)
        if os.path.exists(self.zip_path(nombre)):
            raise ValueError("Ya existe un modpack con ese nombre.")
        return nombre

    def _unique_name(self, base):
        nombre, n = base, 2
        while os.path.exists(self.zip_path(nombre)):
            nombre = f"{base} ({n})"
            n += 1
        return nombre

    @staticmethod
    def _clean_name(nombre):
        limpio = "".join("_" if (c in INVALID_CHARS or ord(c) < 32) else c for c in nombre).strip().rstrip(".")
        return limpio or "importado"

    # ---------- LISTADO / INFO ----------
    def list_modpacks(self):
        try:
            files = os.listdir(MODPACKS_DIR)
        except FileNotFoundError:
            return []
        names = [f[:-4] for f in files
                 if f.lower().endswith(".zip") and os.path.isfile(os.path.join(MODPACKS_DIR, f))]
        return sorted(names, key=str.lower)

    def get_info(self, nombre):
        path = self.zip_path(nombre)
        st = os.stat(path)
        key = (st.st_mtime_ns, st.st_size)
        cached = self._info_cache.get(nombre)
        if cached and cached[0] == key:
            return cached[1]

        info = {"name": nombre, "minecraft_version": "?", "modloader": "?", "version": "?",
                "size": st.st_size, "mods": 0, "broken": False}
        try:
            with zipfile.ZipFile(path) as zf:
                names = zf.namelist()
                if MANIFEST_FILE in names:
                    data = json.loads(zf.read(MANIFEST_FILE).decode("utf-8"))
                    for k in ("minecraft_version", "modloader", "version"):
                        info[k] = str(data.get(k) or "?")
                info["mods"] = sum(1 for n in names if n.startswith("mods/") and n.lower().endswith(".jar"))
        except Exception:
            info["broken"] = True

        self._info_cache[nombre] = (key, info)
        return info

    def list_contents(self, nombre):
        mods, packs, config_files = [], [], 0
        with zipfile.ZipFile(self.zip_path(nombre)) as zf:
            for n in zf.namelist():
                if n.endswith("/"):
                    continue
                top, _, rest = n.partition("/")
                if top == "mods":
                    mods.append(rest)
                elif top == "resourcepacks":
                    packs.append(rest)
                elif top == "config":
                    config_files += 1
        return {
            "info": self.get_info(nombre),
            "mods": sorted(mods, key=str.lower),
            "resourcepacks": sorted(packs, key=str.lower),
            "config_files": config_files,
        }

    def get_current(self):
        if not self.mods_path:
            return None
        file_path = os.path.join(self.mods_path, CURRENT_FILE)
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read().strip()
        return None

    # ---------- GUARDAR ----------
    def save_modpack(self, nombre, mc_version, modloader, version, progress=None):
        """Comprime mods + config + resourcepacks actuales en modpacks_guardados/<nombre>.zip"""
        self._require_path()
        nombre = self.check_new_name(nombre)
        destino = self.zip_path(nombre)

        manifest = {
            "name": nombre,
            "minecraft_version": mc_version,
            "modloader": modloader,
            "version": version,
        }

        files, dirs = [], []
        for key, base in self._targets().items():
            if not os.path.isdir(base):
                continue
            for root, dnames, fnames in os.walk(base):
                rel_root = os.path.relpath(root, base)
                prefix = key if rel_root == "." else key + "/" + rel_root.replace(os.sep, "/")
                for d in dnames:
                    dirs.append(f"{prefix}/{d}")
                for f in fnames:
                    if key == "mods" and rel_root == "." and f == CURRENT_FILE:
                        continue
                    full = os.path.join(root, f)
                    try:
                        size = os.path.getsize(full)
                    except OSError:
                        size = 0
                    files.append((full, f"{prefix}/{f}", size))

        tmp = destino + ".tmp"
        try:
            self._write_zip(tmp, manifest, files, dirs, progress)
            os.replace(tmp, destino)
        except BaseException:
            self._silent_remove(tmp)
            raise

        # Lo que hay ahora en la carpeta de mods es justo este modpack
        self._write_current(nombre)

    # ---------- USAR ----------
    def load_modpack(self, nombre, progress=None):
        """Descomprime el .zip y reemplaza mods, config y resourcepacks de Minecraft."""
        self._require_path()
        zpath = self.zip_path(nombre)
        if not os.path.isfile(zpath):
            raise ModpackError("El modpack no existe.")

        self._replace(("mods",), lambda staging: self._extract(zpath, staging, progress),
                      merge=("config", "resourcepacks"))
        self._report(progress, 1.0, "Listo")
        self._write_current(nombre)

    def clear_mods(self):
        """Deja la carpeta de mods vacía (vanilla). No toca config ni resourcepacks."""
        self._require_path()
        self._replace(("mods",), lambda staging: None)
        self._write_current(EMPTY_LABEL)

    def delete_modpack(self, nombre):
        ruta = self.zip_path(nombre)
        if os.path.isfile(ruta):
            os.remove(ruta)
        self._info_cache.pop(nombre, None)

    # ---------- IMPORTAR / EXPORTAR ----------
    def import_zip(self, path, progress=None):
        """Importa un ZIP de EMManager (formato nuevo o antiguo). Devuelve el nombre final."""
        try:
            src_zip = zipfile.ZipFile(path)
        except zipfile.BadZipFile:
            raise ModpackError("El archivo no es un ZIP válido.")

        with src_zip as src:
            names = [n.replace("\\", "/") for n in src.namelist()]
            if MANIFEST_FILE not in names:
                raise ModpackError("ZIP inválido: no contiene emmanager.json")

            try:
                manifest = json.loads(src.read(MANIFEST_FILE).decode("utf-8"))
            except Exception:
                raise ModpackError("ZIP inválido: emmanager.json está dañado")
            if not isinstance(manifest, dict):
                raise ModpackError("ZIP inválido: emmanager.json está dañado")

            base = manifest.get("name") or os.path.splitext(os.path.basename(path))[0]
            nombre = self._unique_name(self._clean_name(str(base)))
            manifest["name"] = nombre

            # Formato antiguo: los mods iban sueltos en la raíz del zip
            new_layout = any(n.split("/", 1)[0] in PACK_DIRS for n in names if "/" in n)

            infos = src.infolist()
            total = sum(i.file_size for i in infos) or 1
            done = 0
            destino = self.zip_path(nombre)
            tmp = destino + ".tmp"
            try:
                with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as dst:
                    dst.writestr(MANIFEST_FILE, json.dumps(manifest, indent=4))
                    written = set()
                    for key in PACK_DIRS:
                        self._add_dir(dst, key)
                        written.add(key + "/")

                    for info in infos:
                        n = info.filename.replace("\\", "/")
                        parts = n.split("/")
                        if n == MANIFEST_FILE or n.startswith("/") or ".." in parts or ":" in n:
                            continue
                        if new_layout:
                            if parts[0] not in PACK_DIRS:
                                continue
                            arc = n
                        else:
                            if n == CURRENT_FILE:
                                continue
                            arc = "mods/" + n

                        if info.is_dir() or arc.endswith("/"):
                            arc = arc.rstrip("/") + "/"
                            if arc not in written:
                                self._add_dir(dst, arc)
                                written.add(arc)
                            continue
                        if arc in written:
                            continue

                        zi = zipfile.ZipInfo(arc, date_time=info.date_time)
                        zi.compress_type = zipfile.ZIP_DEFLATED
                        zi.external_attr = 0o644 << 16
                        zi.file_size = info.file_size
                        with src.open(info) as s, dst.open(zi, "w") as d:
                            shutil.copyfileobj(s, d, CHUNK)
                        written.add(arc)

                        done += info.file_size
                        self._report(progress, done / total, f"Importando {os.path.basename(arc)}")
                os.replace(tmp, destino)
            except BaseException:
                self._silent_remove(tmp)
                raise
        return nombre

    def export_zip(self, nombre, destino, progress=None):
        src = self.zip_path(nombre)
        if not os.path.isfile(src):
            raise ModpackError("El modpack no existe.")
        if os.path.abspath(destino) == os.path.abspath(src):
            raise ModpackError("Elige un destino distinto a la carpeta interna de EMManager.")

        total = os.path.getsize(src) or 1
        done = 0
        try:
            with open(src, "rb") as s, open(destino, "wb") as d:
                while True:
                    chunk = s.read(CHUNK)
                    if not chunk:
                        break
                    d.write(chunk)
                    done += len(chunk)
                    self._report(progress, done / total, f"Exportando {nombre}")
        except BaseException:
            self._silent_remove(destino)
            raise

    # ---------- MANTENIMIENTO / MIGRACIÓN ----------
    def cleanup_tmp(self):
        """Borra .zip.tmp huérfanos de operaciones interrumpidas."""
        try:
            for f in os.listdir(MODPACKS_DIR):
                if f.lower().endswith(".zip.tmp"):
                    self._silent_remove(os.path.join(MODPACKS_DIR, f))
        except OSError:
            pass

    def legacy_folders(self):
        """Modpacks del formato antiguo (carpetas sueltas en vez de .zip)."""
        try:
            return sorted(d for d in os.listdir(MODPACKS_DIR)
                          if os.path.isdir(os.path.join(MODPACKS_DIR, d)))
        except OSError:
            return []

    def migrate_legacy(self, progress=None):
        """Convierte las carpetas antiguas en .zip. Devuelve (convertidos, errores)."""
        folders = self.legacy_folders()
        migrated, errors = 0, []
        for i, nombre in enumerate(folders):
            def sub(frac, text=None, i=i):
                self._report(progress, (i + frac) / len(folders), text)
            try:
                self._migrate_folder(nombre, sub)
                migrated += 1
            except Exception as e:
                errors.append(f"{nombre}: {e}")
        return migrated, errors

    def _migrate_folder(self, nombre, progress):
        src = os.path.join(MODPACKS_DIR, nombre)
        destino = self.zip_path(nombre)
        if os.path.exists(destino):
            raise ModpackError("ya existe un ZIP con ese nombre")

        manifest = {"name": nombre, "minecraft_version": "?", "modloader": "?", "version": "?"}
        mpath = os.path.join(src, MANIFEST_FILE)
        if os.path.isfile(mpath):
            try:
                with open(mpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    manifest.update(data)
            except Exception:
                pass
        manifest["name"] = nombre

        files, dirs = [], []
        for root, dnames, fnames in os.walk(src):
            rel_root = os.path.relpath(root, src)
            for d in dnames:
                rel = d if rel_root == "." else os.path.join(rel_root, d)
                dirs.append("mods/" + rel.replace(os.sep, "/"))
            for f in fnames:
                full = os.path.join(root, f)
                rel = os.path.relpath(full, src).replace(os.sep, "/")
                if rel in (MANIFEST_FILE, CURRENT_FILE):
                    continue
                files.append((full, "mods/" + rel, os.path.getsize(full)))

        tmp = destino + ".tmp"
        try:
            self._write_zip(tmp, manifest, files, dirs, progress)
            with zipfile.ZipFile(tmp) as zf:
                if zf.testzip() is not None:
                    raise ModpackError("el ZIP generado no pasó la verificación")
                stored = sum(1 for n in zf.namelist() if not n.endswith("/"))
            if stored != len(files) + 1:
                raise ModpackError("el ZIP generado no coincide con la carpeta original")
            os.replace(tmp, destino)
        except BaseException:
            self._silent_remove(tmp)
            raise

        # Solo se borra la carpeta antigua cuando el ZIP ya quedó verificado
        self._rmtree(src)

    # ---------- PRIVADOS ----------
    @staticmethod
    def _report(progress, fraction, text=None):
        if progress:
            progress(max(0.0, min(1.0, fraction)), text)

    @staticmethod
    def _add_dir(zf, arc):
        zi = zipfile.ZipInfo(arc.rstrip("/") + "/")
        zi.external_attr = (0o40755 << 16) | 0x10
        zf.writestr(zi, b"")

    def _write_zip(self, tmp, manifest, files, dirs, progress=None):
        total = sum(s for _, _, s in files) or 1
        done = 0
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(MANIFEST_FILE, json.dumps(manifest, indent=4))
            for key in PACK_DIRS:          # siempre, aunque estén vacías
                self._add_dir(zf, key)
            for d in dirs:
                self._add_dir(zf, d)
            for full, arc, size in files:
                zf.write(full, arc)
                done += size
                self._report(progress, done / total, f"Comprimiendo {os.path.basename(arc)}")

    def _extract(self, zpath, dest, progress=None):
        with zipfile.ZipFile(zpath) as zf:
            infos = zf.infolist()
            total = sum(i.file_size for i in infos) or 1
            done = 0
            dest_real = os.path.realpath(dest)
            for info in infos:
                name = info.filename.replace("\\", "/")
                parts = name.split("/")
                if parts[0] not in PACK_DIRS:      # ignora emmanager.json y cualquier otra cosa
                    continue
                target = os.path.realpath(os.path.join(dest, *parts))
                if target != dest_real and not target.startswith(dest_real + os.sep):
                    continue                       # protege contra rutas maliciosas (zip-slip)
                if info.is_dir() or name.endswith("/"):
                    os.makedirs(target, exist_ok=True)
                    continue
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with zf.open(info) as s, open(target, "wb") as out:
                    shutil.copyfileobj(s, out, CHUNK)
                done += info.file_size
                self._report(progress, 0.95 * done / total, f"Descomprimiendo {parts[-1]}")

    def _replace(self, keys, populate, merge=()):
        """
        Reemplaza las carpetas indicadas por contenido nuevo sin dejar el estado a medias:
        primero se prepara todo en una carpeta temporal y solo entonces se intercambia.
        Si algo falla, lo que el usuario tenía se restaura.
        """
        game = self.game_dir
        os.makedirs(game, exist_ok=True)
        work = os.path.join(game, TMP_DIRNAME)
        staging = os.path.join(work, "new")
        trash = os.path.join(work, "old")

        if os.path.exists(os.path.join(work, RECOVER_FILE)):
            raise ModpackError(
                f"Quedaron archivos pendientes de recuperar de una operación anterior en:\n{work}\n"
                "Revísalos y borra esa carpeta cuando termines.")
        self._rmtree(work)
        os.makedirs(staging)
        os.makedirs(trash)

        keep = False
        try:
            populate(staging)
            for key in keys:
                os.makedirs(os.path.join(staging, key), exist_ok=True)
            self._swap_in(staging, trash, keys)
            targets = self._targets()
            for key in merge:
                self._merge_dir(os.path.join(staging, key), targets[key])
        except _RollbackFailed:
            keep = True
            with open(os.path.join(work, RECOVER_FILE), "w", encoding="utf-8") as f:
                f.write("EMManager no pudo restaurar automáticamente tus archivos anteriores.\n"
                        "Están en la carpeta 'old' de esta misma carpeta.\n")
            raise ModpackError(
                "Ocurrió un error y no se pudo restaurar todo automáticamente.\n"
                f"Tus archivos anteriores están en:\n{trash}")
        except zipfile.BadZipFile as e:
            raise ModpackError("El ZIP del modpack está dañado. No se modificó nada.") from e
        except PermissionError as e:
            raise ModpackError(
                "No se pudieron reemplazar las carpetas porque están en uso.\n"
                "Cierra Minecraft (y su launcher) e inténtalo de nuevo. "
                "No se modificó nada.") from e
        finally:
            if not keep:
                self._rmtree(work)

    def _swap_in(self, staging, trash, keys):
        targets = self._targets()
        done = []   # [target, old, había_algo, colocado]
        try:
            for key in keys:
                target = targets[key]
                new = os.path.join(staging, key)
                old = os.path.join(trash, key)
                had_old = os.path.isdir(target)
                if had_old:
                    os.rename(target, old)
                entry = [target, old, had_old, False]
                done.append(entry)
                os.rename(new, target)
                entry[3] = True
        except Exception:
            failed = False
            for target, old, had_old, placed in reversed(done):
                try:
                    if placed:
                        self._rmtree(target)
                    if had_old:
                        os.rename(old, target)
                except OSError:
                    failed = True
            if failed:
                raise _RollbackFailed()
            raise

    @staticmethod
    def _merge_dir(src, dst):
        """Copia src dentro de dst: sobrescribe lo que exista y añade lo nuevo, sin borrar nada."""
        if not os.path.isdir(src):
            return
        for root, _, files in os.walk(src):
            rel = os.path.relpath(root, src)
            target_root = dst if rel == "." else os.path.join(dst, rel)
            os.makedirs(target_root, exist_ok=True)
            for f in files:
                os.replace(os.path.join(root, f), os.path.join(target_root, f))

    def _write_current(self, nombre):
        os.makedirs(self.mods_path, exist_ok=True)
        with open(os.path.join(self.mods_path, CURRENT_FILE), "w", encoding="utf-8") as f:
            f.write(nombre)

    @staticmethod
    def _rmtree(path):
        if not os.path.exists(path):
            return

        def _fix(func, p, *_):
            try:
                os.chmod(p, stat.S_IWRITE)
                func(p)
            except OSError:
                pass

        kwargs = {"onexc": _fix} if sys.version_info >= (3, 12) else {"onerror": _fix}
        shutil.rmtree(path, **kwargs)

    @staticmethod
    def _silent_remove(path):
        try:
            os.remove(path)
        except OSError:
            pass