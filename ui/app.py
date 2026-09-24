import queue
import threading

import customtkinter as ctk
from tkinter import filedialog, messagebox

from core.config import ensure_dirs
from core.modpack_service import ModpackService, EMPTY_LABEL
from utils.system_utils import autodetect_mods_path, open_folder, resource_path

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

LOADERS = ["Forge", "NeoForge", "Fabric", "Quilt", "Otro"]

GREEN, GREEN_HOVER = "#2e7d32", "#388e3c"
RED, RED_HOVER = "#aa3333", "#c94444"
CARD_BG = ("gray88", "gray17")
MUTED = ("gray40", "gray62")

BUTTON_STYLES = {
    "primary": {},
    "success": {"fg_color": GREEN, "hover_color": GREEN_HOVER},
    "neutral": {"fg_color": ("gray70", "gray30"), "hover_color": ("gray60", "gray40"),
                "text_color": ("gray10", "gray92")},
    "danger": {"fg_color": RED, "hover_color": RED_HOVER},
}


def fmt_size(n):
    n = float(n)
    for unit in ("B", "KB", "MB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.2f} GB"


def make_fonts():
    return {
        "title": ctk.CTkFont(family="Segoe UI", size=26, weight="bold"),
        "h2": ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
        "main": ctk.CTkFont(family="Segoe UI", size=13),
        "small": ctk.CTkFont(family="Segoe UI", size=12),
    }


def focus_dialog(win):
    """Trae la ventana al frente y la hace modal (con retraso: CTkToplevel aún no es visible)."""
    def _go():
        try:
            win.lift()
            win.focus_force()
            win.grab_set()
        except Exception:
            pass
    win.after(150, _go)


# ------------------------------------------------------------------ DIÁLOGOS

class SaveDialog(ctk.CTkToplevel):
    """Un solo formulario en vez de cuatro preguntas seguidas."""

    def __init__(self, master, fonts, validator, on_submit):
        super().__init__(master)
        self.title("Guardar modpack")
        self.geometry("440x455")
        self.resizable(False, False)
        self.transient(master)
        self.fonts = fonts
        self._validator = validator
        self._on_submit = on_submit

        ctk.CTkLabel(self, text="Guardar modpack actual", font=fonts["h2"]).pack(anchor="w", padx=20, pady=(18, 2))
        ctk.CTkLabel(
            self,
            text="Se guardarán las carpetas mods, config y resourcepacks tal como están ahora, "
                 "comprimidas en un solo .zip.",
            font=fonts["small"], text_color=MUTED, wraplength=390, justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 6))

        self.name_entry = ctk.CTkEntry(self, placeholder_text="Ej: Tecnología 1.20.1")
        self._field("Nombre del modpack", self.name_entry)
        self.mc_entry = ctk.CTkEntry(self, placeholder_text="Ej: 1.20.1")
        self._field("Versión de Minecraft", self.mc_entry)
        self.loader_menu = ctk.CTkOptionMenu(self, values=LOADERS)
        self._field("Modloader", self.loader_menu)
        self.ver_entry = ctk.CTkEntry(self)
        self.ver_entry.insert(0, "1.0.0")
        self._field("Versión del modpack", self.ver_entry)

        self.error = ctk.CTkLabel(self, text="", font=fonts["small"], text_color="#e05555")
        self.error.pack(anchor="w", padx=20, pady=(10, 0))

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(6, 16), side="bottom")
        ctk.CTkButton(row, text="Guardar", width=100, command=self._submit).pack(side="right")
        ctk.CTkButton(row, text="Cancelar", width=100, command=self.destroy,
                      **BUTTON_STYLES["neutral"]).pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda e: self._submit())
        self.bind("<Escape>", lambda e: self.destroy())
        self.after(200, self.name_entry.focus)
        focus_dialog(self)

    def _field(self, label, widget):
        ctk.CTkLabel(self, text=label, font=self.fonts["main"]).pack(anchor="w", padx=20, pady=(8, 2))
        widget.pack(fill="x", padx=20)

    def _submit(self):
        mc = self.mc_entry.get().strip()
        ver = self.ver_entry.get().strip()
        try:
            name = self._validator(self.name_entry.get())
        except ValueError as e:
            self.error.configure(text=str(e))
            return
        if not mc or not ver:
            self.error.configure(text="Faltan datos: completa la versión de Minecraft y del modpack.")
            return
        self.destroy()
        self._on_submit(name, mc, self.loader_menu.get(), ver)


class ContentsWindow(ctk.CTkToplevel):
    def __init__(self, master, fonts, name, data):
        super().__init__(master)
        self.title(f"Contenido: {name}")
        self.geometry("560x580")
        self.transient(master)

        info = data["info"]
        parts = []
        if info["minecraft_version"] != "?":
            parts.append(f"Minecraft {info['minecraft_version']}")
        if info["modloader"] != "?":
            parts.append(info["modloader"])
        if info["version"] != "?":
            parts.append(f"v{info['version']}")
        parts.append(fmt_size(info["size"]))

        ctk.CTkLabel(self, text=name, font=fonts["h2"]).pack(anchor="w", padx=16, pady=(14, 0))
        ctk.CTkLabel(self, text="  ·  ".join(parts), font=fonts["small"], text_color=MUTED).pack(anchor="w", padx=16)

        lines = [f"MODS ({len(data['mods'])})"]
        lines += [f"  - {m}" for m in data["mods"]] or ["  (vacía)"]
        lines += ["", "CONFIG", f"  {data['config_files']} archivo(s)" if data["config_files"] else "  (vacía)"]
        lines += ["", f"RESOURCEPACKS ({len(data['resourcepacks'])})"]
        lines += [f"  - {r}" for r in data["resourcepacks"]] or ["  (vacía)"]

        # Un solo cuadro de texto: mucho más ligero que una etiqueta por mod
        box = ctk.CTkTextbox(self, font=fonts["main"], wrap="none")
        box.pack(fill="both", expand=True, padx=16, pady=14)
        box.insert("end", "\n".join(lines))
        box.configure(state="disabled")
        focus_dialog(self)


# ------------------------------------------------------------------ APP

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.fonts = make_fonts()
        ensure_dirs()

        self.service = ModpackService(None)
        self.service.cleanup_tmp()

        self.busy = False
        self._events = queue.Queue()
        self._packs = []
        self._toolbar_buttons = []
        self._card_buttons = []

        self.title("EMManager")
        try:
            self.iconbitmap(resource_path("icon.ico"))
        except Exception:
            pass
        self.geometry("900x700")
        self.minsize(780, 560)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self._build_ui()

        detected = autodetect_mods_path()
        if detected:
            self.set_mods_path(detected)

        self.refresh()
        self.after(300, self.migrate_legacy)

    # -------- CONSTRUCCIÓN --------

    def _build_ui(self):
        pad = 18
        f = self.fonts

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=pad, pady=(pad, 6))
        ctk.CTkLabel(header, text="EMManager", font=f["title"]).pack(side="left")
        ctk.CTkLabel(header, text="Gestor de modpacks", font=f["main"], text_color=MUTED
                     ).pack(side="left", padx=12, pady=(10, 0))

        # Tarjeta de estado: carpeta + modpack en uso + acciones sobre la carpeta
        status_card = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=12)
        status_card.pack(fill="x", padx=pad, pady=6)
        status_card.grid_columnconfigure(0, weight=1)

        self.label_ruta = ctk.CTkLabel(status_card, text="Carpeta de Minecraft: no seleccionada",
                                       font=f["small"], text_color=MUTED, anchor="w")
        self.label_ruta.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 0))
        self.label_actual = ctk.CTkLabel(status_card, text="En uso: ninguno", font=f["h2"], anchor="w")
        self.label_actual.grid(row=1, column=0, sticky="ew", padx=16, pady=(2, 12))

        tools = ctk.CTkFrame(status_card, fg_color="transparent")
        tools.grid(row=0, column=1, rowspan=2, padx=12, pady=12)
        for text, cmd, style in (
            ("Seleccionar carpeta", self.select_mods, "primary"),
            ("Abrir carpeta", self.open_game_folder, "neutral"),
            ("Limpiar mods", self.clear_mods, "danger"),
        ):
            b = ctk.CTkButton(tools, text=text, command=cmd, **BUTTON_STYLES[style])
            b.pack(side="left", padx=4)
            self._toolbar_buttons.append(b)

        # Cabecera de la lista: título + buscador
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=pad, pady=(12, 0))
        self.label_count = ctk.CTkLabel(head, text="Modpacks", font=f["h2"])
        self.label_count.pack(side="left")
        self.search_entry = ctk.CTkEntry(head, placeholder_text="Buscar modpack...", width=220)
        self.search_entry.pack(side="right")
        self.search_entry.bind("<KeyRelease>", lambda e: self.render_list())

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list_frame.pack(fill="both", expand=True, padx=pad - 6, pady=8)

        # Acciones principales
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=pad, pady=(2, 4))
        for text, cmd, style in (
            ("Guardar modpack actual", self.save, "primary"),
            ("Importar ZIP", self.import_zip, "neutral"),
        ):
            b = ctk.CTkButton(actions, text=text, command=cmd, height=36, **BUTTON_STYLES[style])
            b.pack(side="left", padx=(0, 8))
            self._toolbar_buttons.append(b)

        # Barra de estado + progreso
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=pad, pady=(2, pad))
        self.status = ctk.CTkLabel(footer, text="Listo", font=f["small"], text_color=MUTED, anchor="w")
        self.status.pack(fill="x")
        self.progress = ctk.CTkProgressBar(footer)
        self.progress.set(0)

    # -------- TAREAS EN SEGUNDO PLANO --------

    def run_task(self, label, func, on_success=None):
        """Ejecuta func(progress) en un hilo para que la ventana no se congele."""
        if self.busy:
            return
        self.busy = True
        self._apply_state()
        self.status.configure(text=label)
        self.progress.set(0)
        self.progress.pack(fill="x", pady=(6, 0))

        def report(fraction, text=None):
            self._events.put(("progress", fraction, text))

        def worker():
            try:
                self._events.put(("done", func(report), on_success))
            except Exception as e:
                self._events.put(("error", e))

        threading.Thread(target=worker, daemon=True).start()
        self.after(50, self._poll)

    def _poll(self):
        last_progress = None
        try:
            while True:
                ev = self._events.get_nowait()
                if ev[0] == "progress":
                    last_progress = ev
                elif ev[0] == "done":
                    self._finish()
                    if ev[2]:
                        try:
                            ev[2](ev[1])
                        except Exception as e:
                            messagebox.showerror("Error", str(e))
                elif ev[0] == "error":
                    self._finish()
                    messagebox.showerror("Error", str(ev[1]))
                    self.refresh()
        except queue.Empty:
            pass

        if last_progress and self.busy:
            self.progress.set(last_progress[1])
            if last_progress[2]:
                self.status.configure(text=last_progress[2])
        if self.busy:
            self.after(50, self._poll)

    def _finish(self):
        self.busy = False
        self.progress.pack_forget()
        self.status.configure(text="Listo")
        self._apply_state()

    def _apply_state(self):
        state = "disabled" if self.busy else "normal"
        for b in self._toolbar_buttons + self._card_buttons:
            try:
                b.configure(state=state)
            except Exception:
                pass

    def set_status(self, text):
        self.status.configure(text=text)

    def on_close(self):
        if self.busy and not messagebox.askyesno(
            "Operación en curso",
            "Hay una operación en curso. Salir ahora puede dejar un modpack incompleto.\n\n¿Salir de todos modos?"
        ):
            return
        self.destroy()

    # -------- CARPETA --------

    def _require_path(self):
        if not self.service.mods_path:
            messagebox.showerror("Error", "Selecciona primero la carpeta de mods.")
            return False
        return True

    def set_mods_path(self, path):
        self.service.set_mods_path(path)
        self.label_ruta.configure(text=f"Carpeta de Minecraft: {self.service.game_dir}")

    def select_mods(self):
        if self.busy:
            return
        path = filedialog.askdirectory(title="Selecciona la carpeta 'mods' (o la carpeta .minecraft)")
        if path:
            self.set_mods_path(self.service.resolve_mods_path(path))
            self.refresh()

    def open_game_folder(self):
        if self.busy or not self._require_path():
            return
        open_folder(self.service.game_dir)

    # -------- ACCIONES --------

    def save(self):
        if self.busy or not self._require_path():
            return
        SaveDialog(self, self.fonts, self.service.check_new_name, self._do_save)

    def _do_save(self, name, mc_version, modloader, version):
        self.run_task(
            f"Guardando '{name}'...",
            lambda p: self.service.save_modpack(name, mc_version, modloader, version, p),
            on_success=lambda _: (self.refresh(), self.set_status(f"Modpack '{name}' guardado.")),
        )

    def load(self, name):
        if self.busy or not self._require_path():
            return
        if not messagebox.askyesno(
            "Usar modpack",
            f"Vas a usar '{name}'.\n\n"
            f"Se eliminarán los mods actuales de:\n{self.service.mods_path}\n"
            "y se reemplazarán por los del modpack. Los que no estén guardados en un modpack se perderán.\n\n"
            "Config y resourcepacks se fusionan: se añaden o sobrescriben los del modpack "
            "y se conserva lo que ya tenías.\n¿Continuar?"
        ):
            return
        self.run_task(
            f"Preparando '{name}'...",
            lambda p: self.service.load_modpack(name, p),
            on_success=lambda _: (self.refresh(), self.set_status(f"Modpack '{name}' listo para jugar.")),
        )

    def clear_mods(self):
        if self.busy or not self._require_path():
            return
        if not messagebox.askyesno(
            "Limpiar mods",
            f"Se eliminarán TODOS los mods de:\n{self.service.mods_path}\n\n"
            "Los que no estén guardados en un modpack se perderán.\n¿Continuar?"
        ):
            return
        self.run_task(
            "Limpiando mods...",
            lambda p: self.service.clear_mods(),
            on_success=lambda _: (self.refresh(), self.set_status("Carpeta de mods vacía.")),
        )

    def delete(self, name):
        if self.busy:
            return
        if messagebox.askyesno("Confirmar", f"¿Eliminar el modpack '{name}'?"):
            try:
                self.service.delete_modpack(name)
            except OSError as e:
                messagebox.showerror("Error", str(e))
            self.refresh()

    def view_modpack(self, name):
        try:
            data = self.service.list_contents(name)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo leer el modpack:\n{e}")
            return
        ContentsWindow(self, self.fonts, name, data)

    def import_zip(self):
        if self.busy:
            return
        file = filedialog.askopenfilename(filetypes=[("ZIP", "*.zip")])
        if not file:
            return
        self.run_task(
            "Importando modpack...",
            lambda p: self.service.import_zip(file, p),
            on_success=lambda name: (self.refresh(), self.set_status(f"Modpack importado como '{name}'.")),
        )

    def export_zip(self, name):
        if self.busy:
            return
        dest = filedialog.asksaveasfilename(defaultextension=".zip", initialfile=f"{name}.zip",
                                            filetypes=[("ZIP", "*.zip")])
        if not dest:
            return
        self.run_task(
            f"Exportando '{name}'...",
            lambda p: self.service.export_zip(name, dest, p),
            on_success=lambda _: self.set_status(f"Exportado a {dest}"),
        )

    def migrate_legacy(self):
        """Convierte a .zip los modpacks guardados con la versión anterior (carpetas)."""
        if self.busy or not self.service.legacy_folders():
            return
        self.run_task("Comprimiendo modpacks antiguos a ZIP...", self.service.migrate_legacy,
                      on_success=self._migrated)

    def _migrated(self, result):
        migrated, errors = result
        self.refresh()
        if errors:
            messagebox.showwarning(
                "Migración incompleta",
                "Estos modpacks antiguos no se pudieron convertir (siguen intactos):\n\n" + "\n".join(errors))
        if migrated:
            self.set_status(f"{migrated} modpack(s) antiguo(s) comprimido(s) a ZIP.")

    # -------- VISTA --------

    def refresh(self):
        self._packs = []
        for name in self.service.list_modpacks():
            try:
                self._packs.append(self.service.get_info(name))
            except OSError:
                pass
        self.render_list()
        current = self.service.get_current()
        self.label_actual.configure(text=f"En uso: {current or 'ninguno'}")

    def _card(self, title, subtitle, active, actions):
        card = ctk.CTkFrame(self.list_frame, fg_color=CARD_BG, corner_radius=12,
                            border_width=2 if active else 0, border_color=GREEN)
        card.pack(fill="x", pady=5, padx=4)
        card.grid_columnconfigure(0, weight=1)

        head = ctk.CTkFrame(card, fg_color="transparent")
        head.grid(row=0, column=0, sticky="w", padx=16, pady=(12, 0))
        ctk.CTkLabel(head, text=title, font=self.fonts["h2"]).pack(side="left")
        if active:
            ctk.CTkLabel(head, text="  EN USO  ", font=self.fonts["small"], fg_color=GREEN,
                         text_color="white", corner_radius=6).pack(side="left", padx=10)
        ctk.CTkLabel(card, text=subtitle, font=self.fonts["small"], text_color=MUTED, anchor="w"
                     ).grid(row=1, column=0, sticky="w", padx=16, pady=(0, 12))

        bar = ctk.CTkFrame(card, fg_color="transparent")
        bar.grid(row=0, column=1, rowspan=2, padx=12, pady=12)
        for text, cmd, style in actions:
            b = ctk.CTkButton(bar, text=text, width=80, command=cmd, **BUTTON_STYLES[style])
            b.pack(side="left", padx=3)
            self._card_buttons.append(b)

    def render_list(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        self._card_buttons = []

        current = self.service.get_current()
        query = self.search_entry.get().strip().lower()

        self._card(
            EMPTY_LABEL, "Deja la carpeta de mods vacía para jugar vanilla.",
            current == EMPTY_LABEL,
            [("Usar", self.clear_mods, "success" if current == EMPTY_LABEL else "primary")],
        )

        shown = 0
        for info in self._packs:
            name = info["name"]
            if query and query not in name.lower():
                continue
            shown += 1

            if info["broken"]:
                subtitle = "ZIP dañado o ilegible"
            else:
                parts = []
                if info["minecraft_version"] != "?":
                    parts.append(f"Minecraft {info['minecraft_version']}")
                if info["modloader"] != "?":
                    parts.append(info["modloader"])
                if info["version"] != "?":
                    parts.append(f"v{info['version']}")
                parts.append(f"{info['mods']} mods")
                parts.append(fmt_size(info["size"]))
                subtitle = "  ·  ".join(parts)

            active = name == current
            self._card(
                name, subtitle, active,
                [
                    ("Usar", lambda n=name: self.load(n), "success" if active else "primary"),
                    ("Ver", lambda n=name: self.view_modpack(n), "neutral"),
                    ("Exportar", lambda n=name: self.export_zip(n), "neutral"),
                    ("Eliminar", lambda n=name: self.delete(n), "danger"),
                ],
            )

        if not self._packs:
            ctk.CTkLabel(
                self.list_frame, text_color=MUTED, font=self.fonts["main"], justify="center",
                text="Aún no hay modpacks guardados.\nUsa «Guardar modpack actual» o «Importar ZIP» para empezar.",
            ).pack(pady=30)
        elif query and not shown:
            ctk.CTkLabel(self.list_frame, text="Ningún modpack coincide con la búsqueda.",
                         text_color=MUTED, font=self.fonts["main"]).pack(pady=20)

        total = len(self._packs)
        self.label_count.configure(text=f"Modpacks ({total})" if total else "Modpacks")
        self._apply_state()


if __name__ == "__main__":
    app = App()
    app.mainloop()