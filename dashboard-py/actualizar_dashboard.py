#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dashboard de Tareas Periódicas · HUVN · RRHH

Escanea las carpetas de red configuradas, comprueba qué archivos
existen para cada periodo y genera un dashboard HTML que se abre
automáticamente en el navegador.

Diseñado para ser compilado con PyInstaller a un único .exe que
los directivos puedan ejecutar con doble clic, sin instalar nada.

Uso desde código:
    python actualizar_dashboard.py

Compilación a .exe:
    Ver COMPILAR.md
"""

import os
import re
import sys
import json
import calendar
import threading
import traceback
from pathlib import Path
from datetime import datetime, date

import tkinter as tk
from tkinter import scrolledtext, font as tkfont

# ======================================================================
#                           CONFIGURACIÓN
# ======================================================================
# Cada tarea define dónde están sus archivos y cómo se llaman.
# Tokens admitidos en 'ruta' y 'patron':
#     {YYYY}       año actual (2026)
#     {MM}         mes 2 dígitos (01-12)
#     {DD}         día 2 dígitos (01-31, solo en 'patron')
#     {MES_TEXTO}  nombre del mes en español (enero, febrero...)
#
# periodicidad: "mensual" | "diaria" | "anual"
# subcarpeta_por_mes: True si dentro de 'ruta' hay una subcarpeta por
#     cada mes (Mayo, MAYO, mayo, 05-Mayo...). Detecta variantes.
# dias_laborables: solo en diarias. Si True, fines de semana no
#     se contabilizan como pendientes.
TAREAS = [
    {
        "id": "continuidad_asistencial",
        "nombre": "Continuidad Asistencial",
        "area": "Dirección Médica",
        "ruta": r"\\Alhambra\grupo$\GrupodeApoyoGestion\H. VIRGEN NIEVES 2026\SEGUIMIENTO JC_CA\CONTINUIDAD ASISTENCIAL\C.A. X MESES",
        "periodicidad": "mensual",
        "patron": "{MM}-{YYYY}-CA",
        "extension": "xlsx",
        "subcarpeta_por_mes": False,
        "dias_laborables": False,
    },
    {
        "id": "personal_activo",
        "nombre": "Personal Activo",
        "area": "RRHH",
        "ruta": r"\\Alhambra\grupo$\HUVN-PERSONAL-ACTIVO\Personal Activo\{YYYY}",
        "periodicidad": "diaria",
        "patron": "PA-{YYYY}-{MM}-{DD}",
        "extension": "xlsx",
        "subcarpeta_por_mes": False,
        "dias_laborables": True,
    },
    {
        "id": "it_diaria",
        "nombre": "IT Diaria",
        "area": "RRHH",
        "ruta": r"\\Alhambra\grupo$\HUVN-PERSONAL-ACTIVO\IT DIARIA\IT DIARIA\{YYYY}",
        "periodicidad": "diaria",
        "patron": "IT-HVN-{YYYY}-{MM}-{DD}",
        "extension": "xlsx",
        "subcarpeta_por_mes": True,
        "dias_laborables": True,
    },
    {
        "id": "altas_it",
        "nombre": "Altas IT",
        "area": "RRHH",
        "ruta": r"\\Alhambra\grupo$\HUVN-PERSONAL-ACTIVO\IT DIARIA\ALTAS IT\{YYYY}",
        "periodicidad": "diaria",
        "patron": "ALTAS IT A {YYYY}-{MM}-{DD}",
        "extension": "xlsx",
        "subcarpeta_por_mes": True,
        "dias_laborables": True,
    },
]

# ======================================================================
#                               MOTOR
# ======================================================================
MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

NOW = datetime.now()
YEAR = NOW.year
MONTH = NOW.month
DAY = NOW.day


def resolver(texto: str, year: int, month: int = 1, day: int = 0) -> str:
    """Sustituye tokens {YYYY}, {MM}, {DD}, {MES_TEXTO} en un string."""
    t = texto.replace("{YYYY}", str(year))
    t = t.replace("{MM}", f"{month:02d}")
    if 1 <= month <= 12:
        t = t.replace("{MES_TEXTO}", MESES[month - 1])
    if day > 0:
        t = t.replace("{DD}", f"{day:02d}")
    return t


def listar_archivos(carpeta: Path, extension: str):
    if not carpeta.exists():
        return []
    try:
        return [p for p in carpeta.iterdir()
                if p.is_file() and p.suffix.lower() == "." + extension.lower()]
    except (OSError, PermissionError):
        return []


def buscar_subcarpeta_mes(base: Path, mes: int):
    """Busca una subcarpeta cuyo nombre coincida con el mes (insensible
    a may/min y a variantes como '05-Mayo', 'MAYO', 'mayo')."""
    if not base.exists():
        return None
    nombre_mes = MESES[mes - 1]
    mm = f"{mes:02d}"
    try:
        for sub in base.iterdir():
            if not sub.is_dir():
                continue
            low = sub.name.lower()
            if (low == nombre_mes or nombre_mes in low or
                    low == mm or low.startswith(mm + "-") or low.startswith(mm + " ")):
                return sub
    except (OSError, PermissionError):
        pass
    return None


def comprobar_mensual(tarea):
    resultado = {
        "id": tarea["id"], "nombre": tarea["nombre"], "area": tarea["area"],
        "periodicidad": "mensual", "ruta": tarea["ruta"],
        "rutaResuelta": "", "carpetaExiste": False, "error": None,
        "meses": {},
    }
    ruta = resolver(tarea["ruta"], YEAR, 1)
    resultado["rutaResuelta"] = ruta
    carpeta = Path(ruta)
    if not carpeta.exists():
        resultado["error"] = "No se localiza la carpeta"
        for m in range(1, 13):
            resultado["meses"][str(m)] = {"estado": "sin-carpeta"}
        return resultado
    resultado["carpetaExiste"] = True
    archivos = listar_archivos(carpeta, tarea["extension"])

    for m in range(1, 13):
        patron = resolver(tarea["patron"], YEAR, m)
        regex = re.compile(re.escape(patron), re.IGNORECASE)
        match = next((a for a in archivos if regex.search(a.name)), None)
        if match:
            resultado["meses"][str(m)] = {
                "estado": "verde", "archivo": match.name, "ruta": str(match),
            }
        elif m > MONTH:
            resultado["meses"][str(m)] = {"estado": "gris"}
        elif m == MONTH:
            resultado["meses"][str(m)] = {"estado": "amber"}
        else:
            resultado["meses"][str(m)] = {"estado": "rojo"}
    return resultado


def comprobar_diaria(tarea):
    resultado = {
        "id": tarea["id"], "nombre": tarea["nombre"], "area": tarea["area"],
        "periodicidad": "diaria", "ruta": tarea["ruta"],
        "diasLaborables": tarea["dias_laborables"],
        "rutaResuelta": "", "carpetaExiste": False, "error": None,
        "dias": {},
    }
    base = Path(resolver(tarea["ruta"], YEAR, MONTH))
    resultado["rutaResuelta"] = str(base)
    if not base.exists():
        resultado["error"] = "No se localiza la carpeta"
        return resultado
    resultado["carpetaExiste"] = True

    meses_a_explorar = [MONTH] if MONTH == 1 else [MONTH - 1, MONTH]

    for mes in meses_a_explorar:
        carpeta_mes = base
        if tarea["subcarpeta_por_mes"]:
            sm = buscar_subcarpeta_mes(base, mes)
            if not sm:
                continue
            carpeta_mes = sm

        archivos = listar_archivos(carpeta_mes, tarea["extension"])
        dias_mes = calendar.monthrange(YEAR, mes)[1]

        for d in range(1, dias_mes + 1):
            patron = resolver(tarea["patron"], YEAR, mes, d)
            regex = re.compile(re.escape(patron), re.IGNORECASE)
            match = next((a for a in archivos if regex.search(a.name)), None)
            clave = f"{mes}-{d}"
            fecha = date(YEAR, mes, d)
            fin_semana = fecha.weekday() >= 5  # 5=sábado, 6=domingo
            futuro = (mes > MONTH) or (mes == MONTH and d > DAY)
            entry = {"finSemana": fin_semana, "mes": mes, "dia": d}
            if match:
                entry.update({"estado": "verde", "archivo": match.name, "ruta": str(match)})
            elif futuro:
                entry["estado"] = "gris"
            elif tarea["dias_laborables"] and fin_semana:
                entry["estado"] = "gris"
            elif mes == MONTH and d == DAY:
                entry["estado"] = "amber"
            else:
                entry["estado"] = "rojo"
            resultado["dias"][clave] = entry
    return resultado


def ruta_recurso(nombre: str) -> Path:
    """Devuelve la ruta a un recurso, sea ejecutando como .py o como .exe
    empaquetado con PyInstaller (en cuyo caso los recursos viven en
    sys._MEIPASS)."""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / nombre
    return Path(__file__).resolve().parent / nombre


# ======================================================================
#                          GENERAR DASHBOARD
# ======================================================================
def generar_dashboard(callback_log):
    """Hace todo el trabajo: escanea tareas, genera HTML y lo guarda.
    Devuelve la ruta del HTML generado."""
    callback_log("Comprobando tareas...\n")
    datos = []
    for t in TAREAS:
        try:
            if t["periodicidad"] == "mensual":
                r = comprobar_mensual(t)
            elif t["periodicidad"] == "diaria":
                r = comprobar_diaria(t)
            else:
                callback_log(f"  - {t['nombre']:<32} (periodicidad no soportada)\n")
                continue

            if r.get("error"):
                callback_log(f"  - {t['nombre']:<32} [!] {r['error']}\n")
            elif r["periodicidad"] == "mensual":
                hechos = sum(1 for v in r["meses"].values() if v.get("estado") == "verde")
                callback_log(f"  - {t['nombre']:<32} [OK] {hechos} / 12 meses\n")
            else:
                hechos = sum(1 for v in r["dias"].values() if v.get("estado") == "verde")
                callback_log(f"  - {t['nombre']:<32} [OK] {hechos} archivos\n")
            datos.append(r)
        except Exception as e:
            callback_log(f"  - {t['nombre']:<32} [ERROR] {e}\n")
            datos.append({
                "id": t["id"], "nombre": t["nombre"], "area": t["area"],
                "periodicidad": t["periodicidad"], "ruta": t["ruta"],
                "error": str(e), "meses": {}, "dias": {},
            })

    plantilla_path = ruta_recurso("plantilla.html")
    if not plantilla_path.exists():
        raise FileNotFoundError(
            f"No se encuentra plantilla.html (esperado en: {plantilla_path})"
        )

    plantilla = plantilla_path.read_text(encoding="utf-8")
    datos_json = json.dumps(datos, ensure_ascii=False)
    fecha = NOW.strftime("%d/%m/%Y %H:%M")
    mes_texto_mayus = MESES[MONTH - 1].upper()

    html = (plantilla
            .replace("__DATOS_JSON__", datos_json)
            .replace("__FECHA_ACTUALIZACION__", fecha)
            .replace("__ANIO__", str(YEAR))
            .replace("__MES_TEXTO__", mes_texto_mayus)
            .replace("__MES_NUMERO__", str(MONTH))
            .replace("__DIA__", str(DAY)))

    # Guardamos en Documentos del usuario para que cada directivo tenga
    # su propia copia y no se pisen entre ellos.
    docs = Path.home() / "Documents"
    if not docs.exists():
        docs = Path.home()
    out_dir = docs / "HUVN-Dashboard"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "dashboard.html"
    out_path.write_text(html, encoding="utf-8")

    callback_log(f"\nDashboard generado:\n  {out_path}\n")
    return out_path


def abrir_en_navegador(path: Path):
    """Abre el HTML con la aplicación asociada (navegador por defecto)."""
    try:
        if sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            import webbrowser
            webbrowser.open(path.as_uri())
    except Exception as e:
        print(f"No se pudo abrir el navegador: {e}")


# ======================================================================
#                       INTERFAZ GRÁFICA (TKINTER)
# ======================================================================
COLOR_BG       = "#eef4f9"
COLOR_BG_CARD  = "#ffffff"
COLOR_PRIMARY  = "#0a4d8c"
COLOR_PRIM_DK  = "#073a6e"
COLOR_INK      = "#0b2545"
COLOR_INK_SOFT = "#1c3d5e"
COLOR_INK_MUTE = "#6c84a0"
COLOR_LINE     = "#c4d6e6"
COLOR_GREEN    = "#1a7548"
COLOR_RED      = "#b3261e"
COLOR_CYAN     = "#0c8aaf"


class DashboardApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.html_path = None
        self.error = False

        root.title("Dashboard de Tareas · HUVN")
        root.geometry("620x500")
        root.configure(bg=COLOR_BG)
        root.minsize(560, 420)

        # Centrar en pantalla
        root.update_idletasks()
        w = root.winfo_width()
        h = root.winfo_height()
        x = (root.winfo_screenwidth() // 2) - (w // 2)
        y = (root.winfo_screenheight() // 2) - (h // 2)
        root.geometry(f"+{x}+{y}")

        try:
            # Mejor escalado en pantallas HiDPI Windows
            root.tk.call("tk", "scaling", 1.2)
        except tk.TclError:
            pass

        # --- Cabecera ---
        cabecera = tk.Frame(root, bg=COLOR_PRIMARY, height=64)
        cabecera.pack(fill="x")
        cabecera.pack_propagate(False)

        logo_canvas = tk.Canvas(cabecera, width=44, height=44,
                                bg=COLOR_PRIMARY, highlightthickness=0)
        logo_canvas.pack(side="left", padx=(20, 14), pady=10)
        # Cruz médica blanca
        logo_canvas.create_rectangle(8, 19, 36, 25, fill="white", outline="")
        logo_canvas.create_rectangle(19, 8, 25, 36, fill="white", outline="")

        titulo_wrap = tk.Frame(cabecera, bg=COLOR_PRIMARY)
        titulo_wrap.pack(side="left", anchor="w", pady=12)
        tk.Label(titulo_wrap, text="Dashboard de Tareas Periódicas",
                 font=("Segoe UI", 13, "bold"),
                 bg=COLOR_PRIMARY, fg="white").pack(anchor="w")
        tk.Label(titulo_wrap, text=f"HUVN · Recursos Humanos · {YEAR}",
                 font=("Consolas", 9),
                 bg=COLOR_PRIMARY, fg="#cde8f0").pack(anchor="w")

        # Línea cian de acento debajo de la cabecera
        tk.Frame(root, bg=COLOR_CYAN, height=3).pack(fill="x")

        # --- Cuerpo ---
        cuerpo = tk.Frame(root, bg=COLOR_BG)
        cuerpo.pack(fill="both", expand=True, padx=24, pady=(18, 18))

        self.estado_label = tk.Label(
            cuerpo, text="Generando dashboard…",
            font=("Segoe UI", 12, "bold"),
            bg=COLOR_BG, fg=COLOR_INK, anchor="w",
        )
        self.estado_label.pack(fill="x", pady=(0, 8))

        self.sub_label = tk.Label(
            cuerpo, text="Escaneando carpetas de red — esto tardará unos segundos.",
            font=("Segoe UI", 9), bg=COLOR_BG, fg=COLOR_INK_MUTE, anchor="w",
        )
        self.sub_label.pack(fill="x", pady=(0, 12))

        log_frame = tk.Frame(cuerpo, bg=COLOR_LINE, bd=1)
        log_frame.pack(fill="both", expand=True)
        self.log = scrolledtext.ScrolledText(
            log_frame, height=12, font=("Consolas", 9),
            bg=COLOR_BG_CARD, fg=COLOR_INK_SOFT,
            relief="flat", padx=12, pady=10, wrap="word",
        )
        self.log.pack(fill="both", expand=True)
        self.log.configure(state="disabled")

        # --- Botones ---
        botones = tk.Frame(root, bg=COLOR_BG)
        botones.pack(fill="x", padx=24, pady=(0, 18))

        self.btn_abrir = tk.Button(
            botones, text="Abrir dashboard",
            font=("Segoe UI", 10, "bold"),
            bg=COLOR_PRIMARY, fg="white",
            activebackground=COLOR_PRIM_DK, activeforeground="white",
            bd=0, padx=22, pady=10, cursor="hand2",
            state="disabled", command=self._abrir,
        )
        self.btn_abrir.pack(side="right", padx=(8, 0))

        self.btn_cerrar = tk.Button(
            botones, text="Cerrar",
            font=("Segoe UI", 10),
            bg=COLOR_BG_CARD, fg=COLOR_INK_SOFT,
            bd=1, padx=18, pady=10, cursor="hand2",
            state="disabled", command=root.destroy,
        )
        self.btn_cerrar.pack(side="right")

        # Lanzar el trabajo en un hilo aparte para no congelar la UI
        threading.Thread(target=self._trabajar, daemon=True).start()

    def _log(self, msg: str):
        self.log.configure(state="normal")
        self.log.insert("end", msg)
        self.log.see("end")
        self.log.configure(state="disabled")
        self.root.update_idletasks()

    def _trabajar(self):
        try:
            self.html_path = generar_dashboard(self._log)
            self.estado_label.config(text="Dashboard listo", fg=COLOR_GREEN)
            self.sub_label.config(
                text="Se ha guardado en tu carpeta Documentos/HUVN-Dashboard."
            )
            self.btn_abrir.config(state="normal")
            self.btn_cerrar.config(state="normal")
            # Abrir solo automáticamente
            self.root.after(400, self._abrir)
        except Exception as e:
            self.error = True
            self.estado_label.config(text="Se ha producido un error", fg=COLOR_RED)
            self.sub_label.config(
                text="Copia el mensaje de abajo y avisa a Recursos Humanos."
            )
            self._log(f"\n[ERROR] {e}\n\n")
            self._log(traceback.format_exc())
            self.btn_cerrar.config(state="normal")

    def _abrir(self):
        if self.html_path:
            abrir_en_navegador(self.html_path)


def main_gui():
    root = tk.Tk()
    DashboardApp(root)
    root.mainloop()


def main_cli():
    """Modo línea de comandos (sin GUI). Útil para programar en una
    tarea programada con --headless."""
    def log(msg):
        sys.stdout.write(msg)
        sys.stdout.flush()
    print("Dashboard de Tareas Periódicas - HUVN - RRHH")
    print("=" * 48)
    print()
    try:
        path = generar_dashboard(log)
        print(f"\nAbriendo: {path}")
        abrir_en_navegador(path)
    except Exception as e:
        print(f"\nERROR: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    if "--headless" in sys.argv or "--cli" in sys.argv:
        main_cli()
    else:
        main_gui()
