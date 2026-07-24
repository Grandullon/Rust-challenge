# Cómo generar el `.exe` para distribuir

Estas instrucciones son para **ti** (Paco), no para los directivos.
Una sola vez en tu PC compilas el script a un ejecutable, y luego
distribuyes el `.exe` por correo / pendrive / red. Los directivos
NO necesitan instalar nada.

## Requisitos (solo en tu PC, una vez)

1. **Python 3.10 o superior**. Descárgalo de [python.org](https://www.python.org/downloads/windows/) — durante la instalación marca **"Add Python to PATH"**.
2. **PyInstaller**. Abre PowerShell o CMD y ejecuta:
   ```
   pip install --upgrade pyinstaller
   ```

## Compilar

1. Abre PowerShell o CMD en la carpeta donde tengas estos archivos:
   - `actualizar_dashboard.py`
   - `plantilla.html`
2. Ejecuta:
   ```
   pyinstaller --onefile --noconsole --add-data "plantilla.html;." --name "Dashboard-HUVN" actualizar_dashboard.py
   ```

3. Espera unos 30-60 segundos. PyInstaller te dejará el resultado en:
   ```
   dist\Dashboard-HUVN.exe
   ```
   (un único archivo de ~12-15 MB, sin dependencias externas).

## Probar antes de distribuir

Haz doble clic en `dist\Dashboard-HUVN.exe`. Tiene que aparecer:

- Una ventana con cabecera azul, título "Dashboard de Tareas Periódicas".
- Mensajes de progreso por cada tarea (`[OK] X archivos`, `[!] No se localiza la carpeta`, etc.).
- Cuando termina, abre automáticamente el dashboard en el navegador.

Si todo va bien → listo para distribuir.

## Distribución a los directivos

Tienes tres formas:

### Forma 1 — Copia local en cada PC (recomendada)
1. Envíales el `.exe` por correo o copia a su Escritorio.
2. Que hagan doble clic.
3. La primera vez Windows SmartScreen puede preguntar si confían en el archivo. Pulsan **"Más información" → "Ejecutar de todos modos"**.
4. A partir de ahí, doble clic y ya.

### Forma 2 — Una sola copia en la red
1. Pon `Dashboard-HUVN.exe` en `\\Alhambra\grupo$\CapituloI\`.
2. Cada directivo crea un acceso directo a ese .exe en su Escritorio (botón derecho → Enviar a → Escritorio).
3. Doble clic en el acceso directo.

Ventaja: actualizar el .exe (si añades una tarea nueva, por ejemplo) es cambiar un único archivo.
Desventaja: Windows puede mostrar advertencia al ejecutar .exe desde red.

### Forma 3 — Tarea programada (sin clics)
Si quieres que el dashboard se refresque automáticamente cada mañana sin que nadie haga nada:

1. Programador de tareas de Windows → Crear tarea básica
2. Desencadenador: diariamente a las 7:30
3. Acción: Iniciar un programa → `Dashboard-HUVN.exe`
4. Argumentos: `--headless --no-abrir`  (sin ventana y sin abrir el navegador)

Cada mañana el dashboard se genera solo. Los directivos solo abren el HTML guardado en `Documentos\HUVN-Dashboard\dashboard.html`.

## Historial y tendencia

Cada ejecución guarda un punto de historial (un punto por día, los
últimos 90 días) en `Documentos\HUVN-Dashboard\historial.json`. A
partir de la segunda actualización, el dashboard muestra una línea
de evolución del % de cumplimiento — útil para que dirección vea si
el equipo mejora o empeora a lo largo del tiempo.

## Modificar tareas / añadir nuevas — SIN recompilar

Las tareas ya **no** viven dentro del .exe. La primera vez que se
ejecuta, el programa crea un `config.json` editable:

1. Junto al `.exe` si esa carpeta tiene permiso de escritura, o
2. En `Documentos\HUVN-Dashboard\config.json` si no.

Para añadir/cambiar tareas: abre ese `config.json` con el Bloc de
notas, edita el bloque `"tareas"`, guarda y vuelve a ejecutar el
programa. **No hace falta recompilar ni redistribuir nada.**

El propio archivo incluye un bloque `_ayuda` con los tokens
disponibles (`{YYYY}`, `{MM}`, `{DD}`, `{WW}`, `{MES_TEXTO}`) y la
descripción de cada campo. Periodicidades soportadas: `diaria`,
`semanal`, `mensual`, `anual`.

**Truco para gestión centralizada:** si pones el `.exe` en la red
(p. ej. `\\Alhambra\grupo$\CapituloI\`) y creas el `config.json` en
esa misma carpeta, todos los directivos que ejecuten ese .exe usarán
la MISMA configuración. Tú editas el JSON una vez y todos ven los
cambios en su próxima actualización.

Si el config tiene un error (una coma de más, una periodicidad mal
escrita...), el programa lo dice con el detalle exacto (archivo,
línea y qué falta) en la ventana — no se queda en blanco.

Solo hay que recompilar si cambias el CÓDIGO o la PLANTILLA
(nueva funcionalidad, cambio de diseño).

## Problemas habituales

* **"Windows protegió tu PC" / SmartScreen**: es normal para un .exe sin firma digital. Botón "Más información" → "Ejecutar de todos modos".
* **El antivirus lo borra**: PyInstaller a veces da falsos positivos. Si pasa, añade una excepción en el antivirus (o que IT firme el .exe con un certificado corporativo si los tienen).
* **La ventana de Python negra aparece igualmente**: te falta el flag `--noconsole` al compilar.
* **"No se encuentra plantilla.html"** al ejecutar el .exe: te falta `--add-data "plantilla.html;."` al compilar.
* **Quiero un icono propio**: añade `--icon "ruta\al\icono.ico"` al comando de compilación.
