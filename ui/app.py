import os
import zipfile
import json
import customtkinter as ctk
from tkinter import filedialog, messagebox, simpledialog

from core.modpack_service import ModpackService
from utils.system_utils import autodetect_mods_path, open_folder, resource_path
from core.config import ensure_dirs, MODPACKS_DIR

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

MANIFEST_FILE = "emmanager.json"
FONT_TITLE = None
FONT_MAIN = None


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        global FONT_TITLE, FONT_MAIN
        FONT_TITLE = ctk.CTkFont(family="Segoe UI", size=26, weight="bold")
        FONT_MAIN = ctk.CTkFont(family="Segoe UI", size=13)

        ensure_dirs()

        self.service = ModpackService(None)

        self.title("EMManager")
        try:
            self.iconbitmap(resource_path("icon.ico"))
        except:
            pass
        self.geometry("820x620")

        ctk.CTkLabel(self, text="EMManager", font=FONT_TITLE).pack(pady=10)

        self.label_ruta = ctk.CTkLabel(self, text="Ruta: no seleccionada", font=FONT_MAIN)
        self.label_ruta.pack()

        self.label_actual = ctk.CTkLabel(self, text="Actual: ninguno", font=FONT_MAIN)
        self.label_actual.pack(pady=5)

        top = ctk.CTkFrame(self)
        top.pack(pady=10)

        ctk.CTkButton(top, text="Seleccionar carpeta", command=self.select_mods).pack(side="left", padx=5)
        ctk.CTkButton(top, text="Abrir carpeta", command=self.open_folder).pack(side="left", padx=5)
        ctk.CTkButton(top, text="Limpiar mods", fg_color="#aa3333", command=self.clear_mods).pack(side="left", padx=5)

        self.list_frame = ctk.CTkScrollableFrame(self)
        self.list_frame.pack(fill="both", expand=True, padx=10, pady=10)

        bottom = ctk.CTkFrame(self)
        bottom.pack(pady=10)

        ctk.CTkButton(bottom, text="Guardar modpack", command=self.save).pack(side="left", padx=5)
        ctk.CTkButton(bottom, text="Importar ZIP", command=self.import_zip).pack(side="left", padx=5)
        ctk.CTkButton(bottom, text="Exportar ZIP", command=self.export_zip).pack(side="left", padx=5)

        detected = autodetect_mods_path()
        if detected:
            self.set_mods_path(detected)

        self.refresh()

    # -------- CORE --------

    def set_mods_path(self, path):
        self.service.set_mods_path(path)
        self.label_ruta.configure(text=f"Ruta: {path}")

    def select_mods(self):
        path = filedialog.askdirectory()
        if path:
            self.set_mods_path(path)
            self.refresh()

    def open_folder(self):
        if not self.service.mods_path:
            messagebox.showerror("Error", "Selecciona carpeta")
            return
        open_folder(self.service.mods_path)

    # -------- SAVE --------

    def save(self):
        name = simpledialog.askstring("Nombre", "Nombre del modpack:")
        if not name:
            return

        mc_version = simpledialog.askstring("Minecraft", "Versión de Minecraft:")
        modloader = simpledialog.askstring("Modloader", "Forge / Fabric / Quilt:")
        version = simpledialog.askstring("Versión", "Versión del modpack:")

        if not all([mc_version, modloader, version]):
            messagebox.showerror("Error", "Faltan datos")
            return

        try:
            self.service.save_modpack(name)

            manifest = {
                "name": name,
                "minecraft_version": mc_version,
                "modloader": modloader,
                "version": version
            }

            path = os.path.join(MODPACKS_DIR, name, MANIFEST_FILE)
            with open(path, "w") as f:
                json.dump(manifest, f, indent=4)

            self.refresh()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def load(self, name):
        try:
            confirm = messagebox.askyesno(
                "Cargar modpack",
                f"Vas a cargar '{name}'. Esto reemplazará los mods actuales. ¿Continuar?"
            )
            if not confirm:
                return

            self.service.load_modpack(name)

            messagebox.showinfo("Modpack cargado", f"'{name}' se cargó correctamente")
            self.refresh()
        except Exception as e:
            messagebox.showerror("Error", str(e))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def delete(self, name):
        if messagebox.askyesno("Confirmar", f"Eliminar '{name}'?"):
            self.service.delete_modpack(name)
            self.refresh()

    def clear_mods(self):
        if not self.service.mods_path:
            return
        self.service.load_modpack("__EMPTY__")
        self.refresh()

    # -------- VIEW CONTENT --------

    def view_modpack(self, name):
        window = ctk.CTkToplevel(self)
        window.title(f"Contenido: {name}")
        window.geometry("500x500")

        frame = ctk.CTkScrollableFrame(window)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        path = os.path.join(MODPACKS_DIR, name)

        # Manifest info
        manifest_path = os.path.join(path, MANIFEST_FILE)
        if os.path.exists(manifest_path):
            with open(manifest_path) as f:
                data = json.load(f)

            info = f"{data.get('name')}\nMC: {data.get('minecraft_version')}\nLoader: {data.get('modloader')}\nVersion: {data.get('version')}"
            ctk.CTkLabel(frame, text=info, font=FONT_MAIN, justify="left").pack(anchor="w", pady=5)

        ctk.CTkLabel(frame, text="Mods:", font=FONT_MAIN).pack(anchor="w", pady=5)

        for file in os.listdir(path):
            if file.endswith(".jar"):
                ctk.CTkLabel(frame, text="- " + file, font=FONT_MAIN).pack(anchor="w")

    # -------- IMPORT / EXPORT --------

    def import_zip(self):
        file = filedialog.askopenfilename(filetypes=[("ZIP", "*.zip")])
        if not file:
            return

        with zipfile.ZipFile(file, 'r') as zip_ref:
            if MANIFEST_FILE not in zip_ref.namelist():
                messagebox.showerror("Error", "ZIP inválido")
                return

            with zip_ref.open(MANIFEST_FILE) as f:
                manifest = json.load(f)

            name = manifest.get("name", "importado")
            dest = os.path.join(MODPACKS_DIR, name)
            os.makedirs(dest, exist_ok=True)

            zip_ref.extractall(dest)

        self.refresh()

    def export_zip(self):
        name = self.service.get_current()
        if not name or name == "< Sin mods >":
            return

        source = os.path.join(MODPACKS_DIR, name)
        file = filedialog.asksaveasfilename(defaultextension=".zip")
        if not file:
            return

        with zipfile.ZipFile(file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(source):
                for f in files:
                    full = os.path.join(root, f)
                    arc = os.path.relpath(full, source)
                    zipf.write(full, arc)

    # -------- UI --------

    def refresh(self):
        for w in self.list_frame.winfo_children():
            w.destroy()

        current = self.service.get_current()

        btn_empty = ctk.CTkButton(
            self.list_frame,
            text="< Sin mods >",
            fg_color="#2e7d32" if current == "< Sin mods >" else "#444",
            command=self.clear_mods
        )
        btn_empty.pack(fill="x", pady=5)

        for m in self.service.list_modpacks():
            frame = ctk.CTkFrame(self.list_frame)
            frame.pack(fill="x", pady=5)

            btn = ctk.CTkButton(
                frame,
                text=("🟢 " if m == current else "📦 ") + m,
                command=lambda name=m: self.load(name)
            )
            btn.pack(side="left", fill="x", expand=True, padx=5)

            view_btn = ctk.CTkButton(
                frame,
                text="👁",
                width=40,
                command=lambda name=m: self.view_modpack(name)
            )
            view_btn.pack(side="left")

            del_btn = ctk.CTkButton(
                frame,
                text="🗑",
                width=40,
                fg_color="#aa3333",
                command=lambda name=m: self.delete(name)
            )
            del_btn.pack(side="right")

        self.label_actual.configure(text=f"Actual: {current}")


if __name__ == "__main__":
    app = App()
    app.mainloop()
