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
4. Argumentos: `--headless`  (modo sin ventana)

Cada mañana el dashboard se genera solo. Los directivos solo abren el HTML guardado en `Documentos\HUVN-Dashboard\dashboard.html`.

## Modificar tareas / añadir nuevas

1. Edita `actualizar_dashboard.py` con Visual Studio Code o Notepad++. Busca el bloque `TAREAS = [...]`.
2. Vuelve a compilar con el mismo comando.
3. Redistribuye el nuevo `.exe`.

## Problemas habituales

* **"Windows protegió tu PC" / SmartScreen**: es normal para un .exe sin firma digital. Botón "Más información" → "Ejecutar de todos modos".
* **El antivirus lo borra**: PyInstaller a veces da falsos positivos. Si pasa, añade una excepción en el antivirus (o que IT firme el .exe con un certificado corporativo si los tienen).
* **La ventana de Python negra aparece igualmente**: te falta el flag `--noconsole` al compilar.
* **"No se encuentra plantilla.html"** al ejecutar el .exe: te falta `--add-data "plantilla.html;."` al compilar.
* **Quiero un icono propio**: añade `--icon "ruta\al\icono.ico"` al comando de compilación.
