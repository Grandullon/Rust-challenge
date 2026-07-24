#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dashboard de Tareas Periódicas · HUVN · RRHH

Escanea las carpetas de red configuradas, comprueba qué archivos
existen para cada periodo y genera un dashboard HTML que se abre
automáticamente en el navegador.

Diseñado para ser compilado con PyInstaller a un único .exe que
los directivos puedan ejecutar con doble clic, sin instalar nada.

NOVEDAD: las tareas ya NO van dentro del código. Se leen de un
config.json que vive junto al .exe (o en Documentos\\HUVN-Dashboard).
Añadir o cambiar tareas = editar ese JSON. Sin recompilar.

Uso:
    python actualizar_dashboard.py               (con ventana)
    python actualizar_dashboard.py --headless    (sin ventana, para tareas programadas)

Compilación a .exe: ver COMPILAR.md
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

# tkinter se importa de forma perezosa dentro de main_gui() para que el
# modo --headless funcione también en equipos/servidores sin entorno gráfico.

# ======================================================================
#                    TAREAS POR DEFECTO (solo primera vez)
# ======================================================================
# Estas tareas solo se usan para CREAR el config.json inicial si no
# existe. A partir de ahí, la verdad vive en config.json — edítalo
# con el Bloc de notas y vuelve a ejecutar. NO hace falta recompilar.
TAREAS_DEFECTO = [
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

AYUDA_CONFIG = {
    "_como_editar": "Edita el bloque 'tareas' con el Bloc de notas. Guarda y vuelve a ejecutar el programa. NO hace falta recompilar nada.",
    "_tokens": {
        "{YYYY}": "año actual (2026)",
        "{MM}": "mes 2 dígitos (01-12)",
        "{DD}": "día 2 dígitos (solo en 'patron')",
        "{WW}": "semana ISO 2 dígitos (solo tareas semanales)",
        "{MES_TEXTO}": "nombre del mes en español (enero, febrero...)",
    },
    "_campos": {
        "id": "identificador único, sin espacios",
        "nombre": "nombre visible en el dashboard",
        "area": "agrupación para el filtro (RRHH, Dirección Médica...)",
        "ruta": "ruta UNC de la carpeta. Las barras invertidas van dobles: \\\\",
        "periodicidad": "diaria | semanal | mensual | anual",
        "patron": "texto que identifica el archivo del periodo, con tokens",
        "extension": "xlsx, xls, pdf, docx...",
        "subcarpeta_por_mes": "true si dentro de 'ruta' hay una carpeta por mes (Mayo, MARZO...)",
        "dias_laborables": "solo diarias: true para ignorar fines de semana",
    },
}

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
SEMANA_ACTUAL = NOW.isocalendar()[1]

CAMPOS_OBLIGATORIOS = ("id", "nombre", "area", "ruta", "periodicidad", "patron", "extension")
PERIODICIDADES = ("diaria", "semanal", "mensual", "anual")


def dir_base() -> Path:
    """Carpeta donde vive el .exe (si está compilado) o el .py."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def dir_salida() -> Path:
    docs = Path.home() / "Documents"
    if not docs.exists():
        docs = Path.home()
    out = docs / "HUVN-Dashboard"
    out.mkdir(parents=True, exist_ok=True)
    return out


def cargar_config(log):
    """Busca config.json: 1º junto al .exe, 2º en Documentos\\HUVN-Dashboard.
    Si no existe en ninguno, lo crea (junto al .exe si se puede, si no
    en Documentos) con las tareas por defecto y avisa."""
    candidatos = [dir_base() / "config.json", dir_salida() / "config.json"]
    for cfg in candidatos:
        if cfg.exists():
            try:
                data = json.loads(cfg.read_text(encoding="utf-8-sig"))
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"El archivo de configuración tiene un error de sintaxis:\n"
                    f"  {cfg}\n"
                    f"  Línea {e.lineno}, columna {e.colno}: {e.msg}\n\n"
                    f"Revisa comas, comillas y barras dobles (\\\\)."
                ) from e
            tareas = data.get("tareas")
            if not isinstance(tareas, list) or not tareas:
                raise ValueError(f"El config no contiene ninguna tarea en 'tareas':\n  {cfg}")
            validar_tareas(tareas, cfg)
            log(f"Configuración: {cfg}  ({len(tareas)} tareas)\n\n")
            return tareas

    # No existe: crear uno editable
    contenido = dict(AYUDA_CONFIG)
    contenido["tareas"] = TAREAS_DEFECTO
    texto = json.dumps(contenido, ensure_ascii=False, indent=2)
    for destino in candidatos:
        try:
            destino.write_text(texto, encoding="utf-8")
            log(f"Se ha creado la configuración inicial en:\n  {destino}\n"
                f"Edítala con el Bloc de notas para añadir o cambiar tareas.\n\n")
            return TAREAS_DEFECTO
        except OSError:
            continue
    log("Aviso: no se pudo guardar config.json — se usa la configuración interna.\n\n")
    return TAREAS_DEFECTO


def validar_tareas(tareas, origen):
    """Valida el config y da errores útiles, no un traceback críptico."""
    ids = set()
    for i, t in enumerate(tareas, 1):
        etiqueta = t.get("nombre") or t.get("id") or f"tarea nº {i}"
        for campo in CAMPOS_OBLIGATORIOS:
            if not t.get(campo):
                raise ValueError(
                    f"A la tarea '{etiqueta}' le falta el campo obligatorio '{campo}'.\n"
                    f"Config: {origen}"
                )
        if t["periodicidad"] not in PERIODICIDADES:
            raise ValueError(
                f"La tarea '{etiqueta}' tiene periodicidad '{t['periodicidad']}'.\n"
                f"Valores válidos: {', '.join(PERIODICIDADES)}.\nConfig: {origen}"
            )
        if t["id"] in ids:
            raise ValueError(f"Hay dos tareas con el mismo id '{t['id']}'. Config: {origen}")
        ids.add(t["id"])
        t.setdefault("subcarpeta_por_mes", False)
        t.setdefault("dias_laborables", False)


def resolver(texto: str, year: int, month: int = 1, day: int = 0, week: int = 0) -> str:
    """Sustituye tokens {YYYY}, {MM}, {DD}, {WW}, {MES_TEXTO}."""
    t = texto.replace("{YYYY}", str(year))
    t = t.replace("{MM}", f"{month:02d}")
    if 1 <= month <= 12:
        t = t.replace("{MES_TEXTO}", MESES[month - 1])
    if day > 0:
        t = t.replace("{DD}", f"{day:02d}")
    if week > 0:
        t = t.replace("{WW}", f"{week:02d}")
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
    """Subcarpeta cuyo nombre coincide con el mes, insensible a
    mayúsculas y variantes ('05-Mayo', 'MAYO', 'mayo')."""
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


def _base_resultado(tarea, periodicidad):
    return {
        "id": tarea["id"], "nombre": tarea["nombre"], "area": tarea["area"],
        "periodicidad": periodicidad, "ruta": tarea["ruta"],
        "rutaResuelta": "", "carpetaExiste": False, "error": None,
    }


def comprobar_mensual(tarea):
    resultado = _base_resultado(tarea, "mensual")
    resultado["meses"] = {}
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


def comprobar_anual(tarea):
    """Basta un archivo del año en curso para estar al día."""
    resultado = _base_resultado(tarea, "anual")
    ruta = resolver(tarea["ruta"], YEAR, 1)
    resultado["rutaResuelta"] = ruta
    carpeta = Path(ruta)
    if not carpeta.exists():
        resultado["error"] = "No se localiza la carpeta"
        resultado["anual"] = {"estado": "sin-carpeta"}
        return resultado
    resultado["carpetaExiste"] = True
    archivos = listar_archivos(carpeta, tarea["extension"])
    patron = resolver(tarea["patron"], YEAR, MONTH)
    regex = re.compile(re.escape(patron), re.IGNORECASE)
    match = next((a for a in archivos if regex.search(a.name)), None)
    if match:
        resultado["anual"] = {"estado": "verde", "archivo": match.name, "ruta": str(match)}
    else:
        # el año sigue abierto: pendiente pero no atrasado
        resultado["anual"] = {"estado": "amber"}
    return resultado


def comprobar_semanal(tarea):
    resultado = _base_resultado(tarea, "semanal")
    resultado["semanas"] = {}
    ruta = resolver(tarea["ruta"], YEAR, MONTH)
    resultado["rutaResuelta"] = ruta
    carpeta = Path(ruta)
    if not carpeta.exists():
        resultado["error"] = "No se localiza la carpeta"
        return resultado
    resultado["carpetaExiste"] = True
    archivos = listar_archivos(carpeta, tarea["extension"])

    total_semanas = date(YEAR, 12, 28).isocalendar()[1]
    for w in range(1, total_semanas + 1):
        patron = resolver(tarea["patron"], YEAR, MONTH, week=w)
        regex = re.compile(re.escape(patron), re.IGNORECASE)
        match = next((a for a in archivos if regex.search(a.name)), None)
        lunes = date.fromisocalendar(YEAR, w, 1)
        domingo = date.fromisocalendar(YEAR, w, 7)
        rango = f"{lunes.day}/{lunes.month} – {domingo.day}/{domingo.month}"
        entry = {"rango": rango}
        if match:
            entry.update({"estado": "verde", "archivo": match.name, "ruta": str(match)})
        elif w > SEMANA_ACTUAL:
            entry["estado"] = "gris"
        elif w == SEMANA_ACTUAL:
            entry["estado"] = "amber"
        else:
            entry["estado"] = "rojo"
        resultado["semanas"][str(w)] = entry
    return resultado


def comprobar_diaria(tarea):
    resultado = _base_resultado(tarea, "diaria")
    resultado["dias"] = {}
    resultado["diasLaborables"] = tarea["dias_laborables"]
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
            fin_semana = fecha.weekday() >= 5
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


COMPROBADORES = {
    "mensual": comprobar_mensual,
    "diaria": comprobar_diaria,
    "semanal": comprobar_semanal,
    "anual": comprobar_anual,
}


def contar_estados(r):
    """Cuenta verde/amber/rojo de un resultado, ignorando grises."""
    per = r.get("periodicidad")
    if per == "diaria":
        coleccion = r.get("dias", {}).values()
    elif per == "semanal":
        coleccion = r.get("semanas", {}).values()
    elif per == "anual":
        coleccion = [r.get("anual", {})]
    else:
        coleccion = r.get("meses", {}).values()
    v = a = rj = 0
    for c in coleccion:
        e = c.get("estado")
        if e == "verde":
            v += 1
        elif e == "amber":
            a += 1
        elif e in ("rojo", "sin-carpeta"):
            rj += 1
    return v, a, rj


def actualizar_historial(out_dir: Path, verdes: int, ambers: int, rojos: int):
    """Guarda un punto de historial por día (el último de cada día gana)
    y devuelve la lista completa para incrustar en el HTML."""
    hist_path = out_dir / "historial.json"
    historial = []
    if hist_path.exists():
        try:
            historial = json.loads(hist_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            historial = []
    hoy = NOW.strftime("%Y-%m-%d")
    punto = {
        "fecha": hoy,
        "verdes": verdes, "ambers": ambers, "rojos": rojos,
        "total": verdes + ambers + rojos,
    }
    historial = [h for h in historial if h.get("fecha") != hoy]
    historial.append(punto)
    historial = historial[-90:]  # últimos 90 días
    try:
        hist_path.write_text(json.dumps(historial, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return historial


def ruta_recurso(nombre: str) -> Path:
    """Recurso empaquetado: en .exe vive en sys._MEIPASS."""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / nombre
    return Path(__file__).resolve().parent / nombre


# ======================================================================
#                          GENERAR DASHBOARD
# ======================================================================
def generar_dashboard(callback_log):
    tareas = cargar_config(callback_log)

    callback_log("Comprobando tareas...\n")
    datos = []
    for t in tareas:
        try:
            comprobador = COMPROBADORES[t["periodicidad"]]
            r = comprobador(t)
            if r.get("error"):
                callback_log(f"  - {t['nombre']:<32} [!] {r['error']}\n")
            else:
                v, a, rj = contar_estados(r)
                unidad = {"mensual": "meses", "diaria": "archivos",
                          "semanal": "semanas", "anual": "archivo"}[r["periodicidad"]]
                callback_log(f"  - {t['nombre']:<32} [OK] {v} {unidad} al día"
                             + (f", {rj} pendientes" if rj else "") + "\n")
            datos.append(r)
        except Exception as e:
            callback_log(f"  - {t['nombre']:<32} [ERROR] {e}\n")
            datos.append({
                "id": t["id"], "nombre": t["nombre"], "area": t["area"],
                "periodicidad": t["periodicidad"], "ruta": t["ruta"],
                "error": str(e),
            })

    plantilla_path = ruta_recurso("plantilla.html")
    if not plantilla_path.exists():
        raise FileNotFoundError(
            f"No se encuentra plantilla.html (esperado en: {plantilla_path})"
        )
    plantilla = plantilla_path.read_text(encoding="utf-8")

    out_dir = dir_salida()
    tot_v = tot_a = tot_r = 0
    for r in datos:
        v, a, rj = contar_estados(r)
        tot_v += v; tot_a += a; tot_r += rj
    historial = actualizar_historial(out_dir, tot_v, tot_a, tot_r)

    fecha = NOW.strftime("%d/%m/%Y %H:%M")
    html = (plantilla
            .replace("__DATOS_JSON__", json.dumps(datos, ensure_ascii=False))
            .replace("__HISTORIAL_JSON__", json.dumps(historial, ensure_ascii=False))
            .replace("__FECHA_ACTUALIZACION__", fecha)
            .replace("__ANIO__", str(YEAR))
            .replace("__MES_TEXTO__", MESES[MONTH - 1].upper())
            .replace("__MES_NUMERO__", str(MONTH))
            .replace("__DIA__", str(DAY))
            .replace("__SEMANA__", str(SEMANA_ACTUAL)))

    out_path = out_dir / "dashboard.html"
    out_path.write_text(html, encoding="utf-8")

    callback_log(f"\nDashboard generado:\n  {out_path}\n")
    return out_path


def abrir_en_navegador(path: Path):
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
    def __init__(self, root):
        self.root = root
        self.html_path = None

        root.title("Dashboard de Tareas · HUVN")
        root.geometry("640x520")
        root.configure(bg=COLOR_BG)
        root.minsize(560, 420)

        root.update_idletasks()
        w, h = root.winfo_width(), root.winfo_height()
        x = (root.winfo_screenwidth() // 2) - (w // 2)
        y = (root.winfo_screenheight() // 2) - (h // 2)
        root.geometry(f"+{x}+{y}")

        try:
            root.tk.call("tk", "scaling", 1.2)
        except tk.TclError:
            pass

        cabecera = tk.Frame(root, bg=COLOR_PRIMARY, height=64)
        cabecera.pack(fill="x")
        cabecera.pack_propagate(False)

        logo = tk.Canvas(cabecera, width=44, height=44, bg=COLOR_PRIMARY, highlightthickness=0)
        logo.pack(side="left", padx=(20, 14), pady=10)
        logo.create_rectangle(8, 19, 36, 25, fill="white", outline="")
        logo.create_rectangle(19, 8, 25, 36, fill="white", outline="")

        titulo = tk.Frame(cabecera, bg=COLOR_PRIMARY)
        titulo.pack(side="left", anchor="w", pady=12)
        tk.Label(titulo, text="Dashboard de Tareas Periódicas",
                 font=("Segoe UI", 13, "bold"), bg=COLOR_PRIMARY, fg="white").pack(anchor="w")
        tk.Label(titulo, text=f"HUVN · Recursos Humanos · {YEAR}",
                 font=("Consolas", 9), bg=COLOR_PRIMARY, fg="#cde8f0").pack(anchor="w")

        tk.Frame(root, bg=COLOR_CYAN, height=3).pack(fill="x")

        cuerpo = tk.Frame(root, bg=COLOR_BG)
        cuerpo.pack(fill="both", expand=True, padx=24, pady=(18, 18))

        self.estado_label = tk.Label(cuerpo, text="Generando dashboard…",
                                     font=("Segoe UI", 12, "bold"),
                                     bg=COLOR_BG, fg=COLOR_INK, anchor="w")
        self.estado_label.pack(fill="x", pady=(0, 8))

        self.sub_label = tk.Label(
            cuerpo, text="Escaneando carpetas de red — esto tardará unos segundos.",
            font=("Segoe UI", 9), bg=COLOR_BG, fg=COLOR_INK_MUTE, anchor="w")
        self.sub_label.pack(fill="x", pady=(0, 12))

        marco = tk.Frame(cuerpo, bg=COLOR_LINE, bd=1)
        marco.pack(fill="both", expand=True)
        self.log = scrolledtext.ScrolledText(
            marco, height=12, font=("Consolas", 9),
            bg=COLOR_BG_CARD, fg=COLOR_INK_SOFT,
            relief="flat", padx=12, pady=10, wrap="word")
        self.log.pack(fill="both", expand=True)
        self.log.configure(state="disabled")

        botones = tk.Frame(root, bg=COLOR_BG)
        botones.pack(fill="x", padx=24, pady=(0, 18))

        self.btn_abrir = tk.Button(
            botones, text="Abrir dashboard", font=("Segoe UI", 10, "bold"),
            bg=COLOR_PRIMARY, fg="white",
            activebackground=COLOR_PRIM_DK, activeforeground="white",
            bd=0, padx=22, pady=10, cursor="hand2",
            state="disabled", command=self._abrir)
        self.btn_abrir.pack(side="right", padx=(8, 0))

        self.btn_cerrar = tk.Button(
            botones, text="Cerrar", font=("Segoe UI", 10),
            bg=COLOR_BG_CARD, fg=COLOR_INK_SOFT,
            bd=1, padx=18, pady=10, cursor="hand2",
            state="disabled", command=root.destroy)
        self.btn_cerrar.pack(side="right")

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
            self.sub_label.config(text="Guardado en Documentos/HUVN-Dashboard.")
            self.btn_abrir.config(state="normal")
            self.btn_cerrar.config(state="normal")
            self.root.after(400, self._abrir)
        except Exception as e:
            self.estado_label.config(text="Se ha producido un error", fg=COLOR_RED)
            self.sub_label.config(text="Copia el mensaje de abajo y avisa a Recursos Humanos.")
            self._log(f"\n[ERROR] {e}\n\n")
            self._log(traceback.format_exc())
            self.btn_cerrar.config(state="normal")

    def _abrir(self):
        if self.html_path:
            abrir_en_navegador(self.html_path)


def main_gui():
    global tk, scrolledtext
    import tkinter as tk
    from tkinter import scrolledtext
    root = tk.Tk()
    DashboardApp(root)
    root.mainloop()


def main_cli():
    def log(msg):
        sys.stdout.write(msg)
        sys.stdout.flush()
    print("Dashboard de Tareas Periódicas - HUVN - RRHH")
    print("=" * 48)
    print()
    try:
        path = generar_dashboard(log)
        if "--no-abrir" not in sys.argv:
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
