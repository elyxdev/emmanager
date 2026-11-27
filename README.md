# 🧩 EMManager

> Un gestor de modpacks **simple, rápido y sin complicaciones** para usuarios **no premium** de Minecraft.

---

## 🚀 ¿Qué es EMManager?

**EMManager** es una herramienta ligera diseñada para facilitar la gestión de modpacks sin depender de launchers complejos. Está pensado para usuarios que solo quieren **cambiar mods rápido y jugar**.

---

## ✨ Características principales

* 📦 **Guardar modpack**

  * Guarda tus **mods, config y resourcepacks** actuales (van siempre, aunque estén vacías) y también **shaderpacks y kubejs** si existen.
  * Se comprime en un único `.zip` y se añade a la lista de modpacks disponibles.
  * Solo se descomprime en la carpeta de Minecraft cuando lo usas.

* 📥 **Importar ZIP**

  * Importa modpacks previamente exportados con EMManager (también los del formato antiguo).
  * Ideal para compartir configuraciones.

* 📤 **Exportar ZIP**

  * Exporta cualquier modpack de la lista.
  * Fácil de enviar o respaldar.

* 🧹 **Limpiar mods**

  * Elimina todos los mods de la carpeta (no toca config ni resourcepacks).

* 🚫 **Sin mods**

  * Deja la carpeta completamente vacía para jugar vanilla.

---

## 📂 Gestión de la carpeta de mods

* 🔍 **Autodetección automática**

  * EMManager detecta la carpeta de mods por sí solo.

* 📁 **Selección manual**

  * Puedes cambiarla usando el botón **"Seleccionar carpeta"**.

---

## ⚠️ Importante

* EMManager **ya no guarda backups** de tus mods: al usar un modpack o limpiar mods, lo que no esté guardado en un modpack se pierde.
* Al usar un modpack, los **mods anteriores se eliminan** y se reemplazan por los del modpack (para evitar conflictos).
* `config`, `resourcepacks` y `shaderpacks` se **fusionan**: se sobrescribe lo que ya existe y se añade lo nuevo, sin borrar lo que ya tenías.
* `kubejs` se **reemplaza** por completo, pero solo si el modpack la incluye.
* Los modpacks guardados con versiones anteriores (carpetas) se convierten solos a `.zip` la primera vez que abres la app.

---

## 🎯 Objetivo

Eliminar la fricción al cambiar modpacks:

> Sin launchers pesados
> Sin configuraciones complicadas
> Sin perder tiempo

---

## ⚙️ Uso básico

1. Abre EMManager
2. Selecciona o detecta tu carpeta de mods
3. Elige una acción:

   * Guardar modpack
   * Importar ZIP
   * Exportar ZIP
   * Limpiar mods
4. ¡Listo! 🎮

---